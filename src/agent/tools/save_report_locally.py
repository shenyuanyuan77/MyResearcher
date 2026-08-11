"""本机保存报告为 Markdown（默认保存到用户桌面；跨平台）。

研途智探 MVP 版：仅输出 .md（避免 weasyprint 重依赖）；PDF 留作后续增强。
"""

from __future__ import annotations

import os
import platform
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


def _windows_home() -> Path:
    profile = os.environ.get("USERPROFILE") or os.environ.get("HOME")
    if profile:
        return Path(profile)
    return Path.home()


def resolve_desktop_dir() -> Path:
    """解析本机「桌面」目录，兼容 Windows / macOS / Linux。"""
    system = platform.system()
    candidates: list[Path] = []
    if system == "Windows":
        home = _windows_home()
        candidates.extend(
            [
                home / "Desktop",
                home / "桌面",
                home / "OneDrive" / "Desktop",
                home / "OneDrive" / "桌面",
            ]
        )
        for key, val in os.environ.items():
            if key.startswith("OneDrive") and val:
                candidates.append(Path(val) / "Desktop")
                candidates.append(Path(val) / "桌面")
    elif system == "Darwin":
        home = Path.home()
        candidates.extend([home / "Desktop", home / "桌面"])
    else:
        home = Path.home()
        candidates.extend([home / "Desktop", home / "桌面"])

    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve(strict=False)
        except Exception:
            resolved = candidate.expanduser()
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if resolved.is_dir():
            return resolved
    fallback = _windows_home() if system == "Windows" else Path.home()
    desktop = fallback / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    return desktop.resolve()


def _sanitize_stem(filename: str) -> str:
    name = Path(str(filename).replace("\\", "/")).name
    name = re.sub(r"[^\w\u4e00-\u9fff.\-]+", "_", name)
    stem = Path(name).stem or "研途智探报告"
    return stem


def create_save_report_tool(download_dir: Optional[Path] = None):
    """创建 save_report_locally 工具；默认写入用户桌面。"""
    from langchain_core.tools import tool

    fixed_dir = download_dir

    @tool
    def save_report_locally(content: str, filename: str = "", format: str = "") -> str:
        """
        将科研报告保存到用户电脑桌面，支持 Markdown / Word(.docx) / PDF 三种格式。

        适用：用户已阅读报告并**明确确认下载**后调用。
        用户说「下载为 Word/下载 docx」→ format=docx；「下载为 PDF」→ format=pdf；默认或「下载 Markdown」→ format=md。

        Args:
            content: 完整报告 Markdown 正文（必填，须含文献 DOI 链接）。
            filename: 本地文件名，如「大模型推理综述_20260809」（无需带后缀，会按 format 自动补）。
            format: 导出格式：md（默认）/ docx / pdf。

        Returns:
            保存结果与桌面上的文件绝对路径。
        """
        text = (content or "").strip()
        if not text:
            return "错误：content 为空，无法保存"
        text = re.sub(
            r'\s*\{[^{}]*"(?:papers|query)"[^{}]*\}\s*$',
            "",
            text,
            flags=re.DOTALL,
        ).strip()
        fmt = (format or "md").lower().strip()
        if fmt not in {"md", "docx", "pdf"}:
            fmt = "md"
        if not filename:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"研途智探报告_{stamp}"
        stem = _sanitize_stem(filename)

        target_dir = fixed_dir or resolve_desktop_dir()
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return f"错误：无法创建目录 {target_dir}: {e}"

        # 始终保留 .md 备份
        md_path = target_dir / f"{stem}.md"
        try:
            md_path.write_text(text, encoding="utf-8")
        except Exception as e:
            return f"错误：写入 Markdown 备份失败: {e}"

        if fmt == "md":
            size = md_path.stat().st_size
            size_str = f"{size} B" if size < 1024 else f"{size/1024:.1f} KB"
            return (
                f"✅ 报告已保存到桌面（Markdown）\n"
                f"路径: {md_path}\n大小: {size_str}\n"
                f"请到桌面打开「{md_path.name}」查看（含文献 DOI 链接，可溯源）。"
            )

        # docx / pdf：调用渲染器
        try:
            from api_view.report_export import render_report

            content_bytes, _media, ext = render_report(text, fmt=fmt)
            out_path = target_dir / f"{stem}.{ext}"
            out_path.write_bytes(content_bytes)
            size = out_path.stat().st_size
            size_str = f"{size} B" if size < 1024 else f"{size/1024:.1f} KB"
            label = "Word" if fmt == "docx" else "PDF"
            return (
                f"✅ 报告已保存到桌面（{label}）\n"
                f"路径: {out_path}\n大小: {size_str}\n"
                f"Markdown 备份: {md_path}\n"
                f"请到桌面打开「{out_path.name}」查看。"
            )
        except Exception as e:
            return (
                f"⚠️ {fmt.upper()} 导出失败：{e}\n"
                f"已保留 Markdown 备份：{md_path}\n"
                f"你也可在前端点「导出」按钮重试 {fmt.upper()}。"
            )

    save_report_locally.name = "save_report_locally"
    return save_report_locally
