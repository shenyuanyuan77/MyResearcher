"""
研途智探AI · 报告导出（Markdown → DOCX / PDF / MD）。

- DOCX：python-docx，解析 markdown 结构（标题/段落/列表/表格/链接）。
- PDF：markdown → HTML → xhtml2pdf（纯 Python，无需 GTK）。
- MD：规范化后直接返回。

中文字体：PDF 默认嵌入 STSong-Light / 宋体（reportlab CJK）。
"""

from __future__ import annotations

import io
import re
from typing import Optional

import markdown as md_lib


def _md_to_html(text: str, template: str = "report") -> str:
    """Markdown → 带学术样式的 HTML（供 PDF 渲染）。

    template:
      - report（默认）：单栏 STSong，阅读友好
      - academic：双栏 Times+宋体，学术论文样式
    """
    html_body = md_lib.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists", "toc"],
    )
    if template == "academic":
        css = """
@page { size: A4; margin: 1.8cm; @frame content_frame { left: 0cm; right: 0cm; } }
body { font-family: 'Times New Roman','STSong-Light','SimSun','宋体',serif; font-size: 10pt; line-height: 1.5; color: #000; }
/* 双栏（xhtml2pdf 对 column-count 支持有限，用分栏边距模拟） */
.main-content { column-count: 2; column-gap: 0.6cm; }
h1 { font-size: 15pt; margin: 0 0 8pt; text-align: center; border-bottom: 1px solid #000; padding-bottom: 4pt; }
h2 { font-size: 12pt; margin: 10pt 0 5pt; }
h3 { font-size: 11pt; margin: 8pt 0 4pt; }
p { margin: 4pt 0; text-align: justify; text-indent: 2em; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; font-size: 9pt; }
th, td { border: 1px solid #000; padding: 3pt 5pt; text-align: left; }
th { background: #e8e8e8; font-weight: bold; }
a { color: #000; text-decoration: underline; }
code { background: #f0f0f0; padding: 1pt 2pt; font-family: monospace; font-size: 9pt; }
blockquote { border-left: 2px solid #999; padding-left: 8pt; color: #333; margin: 6pt 0; font-size: 9pt; }
hr { border: none; border-top: 1px solid #999; margin: 8pt 0; }
"""
        wrapped = f'<div class="main-content">{html_body}</div>'
    else:
        css = """
@page { size: A4; margin: 2cm; }
body { font-family: 'STSong-Light','SimSun','宋体','Microsoft YaHei',sans-serif; font-size: 11pt; line-height: 1.7; color: #1d1d1f; }
h1 { font-size: 20pt; margin: 18pt 0 10pt; border-bottom: 2px solid #007AFF; padding-bottom: 6pt; }
h2 { font-size: 15pt; margin: 14pt 0 8pt; color: #007AFF; }
h3 { font-size: 13pt; margin: 12pt 0 6pt; }
p { margin: 6pt 0; text-align: justify; }
table { border-collapse: collapse; width: 100%; margin: 10pt 0; font-size: 10pt; }
th, td { border: 1px solid #999; padding: 5pt 7pt; text-align: left; }
th { background: #f0f4ff; font-weight: bold; }
a { color: #007AFF; text-decoration: none; }
code { background: #f5f5f7; padding: 1pt 3pt; border-radius: 3pt; font-family: monospace; font-size: 10pt; }
blockquote { border-left: 3px solid #007AFF; padding-left: 10pt; color: #555; margin: 8pt 0; }
hr { border: none; border-top: 1px solid #ddd; margin: 12pt 0; }
"""
        wrapped = html_body
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>{css}</style></head><body>{wrapped}</body></html>"""


def render_pdf(text: str, template: str = "report") -> bytes:
    """Markdown → PDF bytes。template: report（单栏）/ academic（双栏论文）。"""
    from xhtml2pdf import pisa

    html = _md_to_html(text, template=template)
    buf = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html), dest=buf, encoding="utf-8")
    if pisa_status.err:
        raise RuntimeError(f"PDF 渲染失败：{pisa_status.err} 个错误")
    return buf.getvalue()


def render_docx(text: str) -> bytes:
    """Markdown → DOCX bytes。支持标题/段落/有序无序列表/表格/链接/引用。"""
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.oxml.ns import qn

    doc = Document()
    # 默认中文字体
    style = doc.styles["Normal"]
    style.font.name = "Microsoft YaHei"
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    style.font.size = Pt(11)

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        # 跳过空行
        if not stripped:
            i += 1
            continue

        # 标题
        hm = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if hm:
            level = len(hm.group(1))
            heading = doc.add_heading(level=min(level, 4))
            _render_inline_md_to_runs(heading, hm.group(2))
            if level <= 2:
                for run in heading.runs:
                    run.font.color.rgb = RGBColor(0x00, 0x7A, 0xFF)
            i += 1
            continue

        # 表格（GFM）
        if "|" in stripped and i + 1 < len(lines) and re.match(
            r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?$", lines[i + 1].strip()
        ):
            rows = []
            j = i
            while j < len(lines) and "|" in lines[j].strip():
                rows.append(lines[j].strip())
                j += 1
            _add_docx_table(doc, rows)
            i = j
            continue

        # 引用
        if stripped.startswith(">"):
            quote_text = stripped.lstrip("> ").strip()
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(18)
            _render_inline_md_to_runs(p, quote_text)
            for run in p.runs:
                run.italic = True
                run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
            i += 1
            continue

        # 无序列表
        if re.match(r"^[-*+]\s+", stripped):
            p = doc.add_paragraph(style="List Bullet")
            _render_inline_md_to_runs(p, re.sub(r"^[-*+]\s+", "", stripped))
            i += 1
            continue

        # 有序列表
        if re.match(r"^\d+\.\s+", stripped):
            p = doc.add_paragraph(style="List Number")
            _render_inline_md_to_runs(p, re.sub(r"^\d+\.\s+", "", stripped))
            i += 1
            continue

        # 分隔线
        if stripped in {"---", "***", "___"}:
            doc.add_paragraph().add_run("─" * 40).font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
            i += 1
            continue

        # 普通段落
        p = doc.add_paragraph()
        _render_inline_md_to_runs(p, stripped)
        i += 1

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _add_docx_table(doc, rows: list[str]) -> None:
    """把 GFM 表格行加入 docx。"""
    from docx.shared import Pt

    def parse_row(r: str) -> list[str]:
        r = r.strip()
        if r.startswith("|"):
            r = r[1:]
        if r.endswith("|"):
            r = r[:-1]
        return [c.strip() for c in r.split("|")]

    # 跳过分隔行（第 2 行）
    data_rows = []
    for idx, r in enumerate(rows):
        if re.match(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?$", r.strip()):
            continue
        data_rows.append(parse_row(r))
    if not data_rows:
        return
    cols = max(len(r) for r in data_rows)
    table = doc.add_table(rows=len(data_rows), cols=cols)
    table.style = "Light Grid Accent 1"
    for ri, row in enumerate(data_rows):
        for ci in range(cols):
            cell = table.cell(ri, ci)
            cell.text = row[ci] if ci < len(row) else ""
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(10)
                    if ri == 0:
                        run.bold = True


def _strip_md_inline(text: str) -> str:
    """去掉行内 markdown 标记（供 PDF/MD 纯文本场景）。"""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1（\2）", text)
    return text


def _render_inline_md_to_runs(paragraph, text: str) -> None:
    """把行内 markdown 渲染为 docx runs，保留粗体/斜体/代码/链接格式。

    替代原 _strip_md_inline（丢失所有格式）。支持：
    - **bold** → run.bold = True
    - *italic* → run.italic = True
    - `code` → 等宽字体
    - [text](url) → 超链接（带蓝色下划线）
    """
    from docx.shared import RGBColor

    # 行内元素正则：**bold** | *italic* | `code` | [text](url)
    token_re = re.compile(
        r"\*\*(.+?)\*\*"        # bold
        r"|\*(.+?)\*"           # italic
        r"|`(.+?)`"             # code
        r"|\[([^\]]+)\]\(([^)]+)\)",  # link
    )
    pos = 0
    for m in token_re.finditer(text):
        # 前导普通文本
        if m.start() > pos:
            paragraph.add_run(text[pos:m.start()])
        if m.group(1) is not None:  # bold
            run = paragraph.add_run(m.group(1))
            run.bold = True
        elif m.group(2) is not None:  # italic
            run = paragraph.add_run(m.group(2))
            run.italic = True
        elif m.group(3) is not None:  # code
            run = paragraph.add_run(m.group(3))
            run.font.name = "Consolas"
        elif m.group(4) is not None:  # link
            _add_hyperlink_run(paragraph, m.group(4), m.group(5))
        pos = m.end()
    # 尾部普通文本
    if pos < len(text):
        paragraph.add_run(text[pos:])


def _add_hyperlink_run(paragraph, text: str, url: str) -> None:
    """向 paragraph 添加超链接 run（蓝色下划线）。"""
    from docx.shared import RGBColor, Pt
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    part = paragraph.part
    r_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    new_run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    # 蓝色
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "007AFF")
    rPr.append(color)
    # 下划线
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rPr.append(u)
    new_run.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)


def render_md(text: str) -> bytes:
    """规范化后返回 Markdown bytes。"""
    cleaned = text.strip() + "\n"
    return cleaned.encode("utf-8")


def render_report(
    text: str, fmt: str = "docx", pdf_template: str = "report"
) -> tuple[bytes, str, str]:
    """渲染报告。返回 (content_bytes, media_type, ext)。

    pdf_template: report（单栏）/ academic（双栏论文样式，仅 PDF 生效）
    """
    fmt = (fmt or "docx").lower()
    if fmt == "pdf":
        return render_pdf(text, template=pdf_template), "application/pdf", "pdf"
    if fmt == "md":
        return render_md(text), "text/markdown", "md"
    # 默认 docx
    return render_docx(text), (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ), "docx"


# ============================================================
# FastAPI 路由
# ============================================================

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from api_view.agent_loader import agent_loader
from api_view.auth import UserInfo, get_current_user, require_permission

router = APIRouter()


class ExportRequest(BaseModel):
    thread_id: str = Field(..., description="会话 ID")
    format: str = Field("docx", description="导出格式：docx / pdf / md")
    citation_style: str = Field(
        "gbt7714",
        description="参考文献格式：gbt7714 / apa / ieee / chicago / vancouver / mla",
    )
    pdf_template: str = Field(
        "report", description="PDF 模板：report（单栏）/ academic（双栏论文）"
    )


async def _collect_thread_markdown(thread_id: str, citation_style: str = "gbt7714") -> str:
    """从会话展示消息拼接报告 markdown（取 assistant + tool 文献块）。

    citation_style: 参考文献 formatting 风格（gbt7714/apa/ieee/chicago/vancouver/mla）。
    会话中 tool 消息的 references 含结构化引用，按选择风格重新格式化。
    """
    msgs = await agent_loader.get_display_messages(thread_id)
    if not msgs:
        from api_view import local_session_store

        msgs = local_session_store.load_messages(thread_id) or []

    if not msgs:
        raise HTTPException(status_code=404, detail="会话无内容，无法导出")

    from mcp_server.tools.unified import Paper
    from mcp_server.tools.citations import papers_to_references, format_paper

    parts: list[str] = []
    refs_added = False
    for m in msgs:
        role = m.get("role")
        if role == "assistant" and m.get("content"):
            parts.append(m["content"])
        elif role == "tool" and m.get("references") and not refs_added:
            refs = m["references"]
            if isinstance(refs, list) and refs:
                # 按 citation_style 重新格式化参考文献（而非硬编码 gbt7714）
                try:
                    paper_objs = []
                    for r in refs:
                        pk = {k: v for k, v in r.items() if k in Paper.__dataclass_fields__}
                        if pk:
                            paper_objs.append(Paper(**pk))
                    if paper_objs:
                        parts.append(papers_to_references(paper_objs, style=citation_style))
                    else:
                        parts.append("## 参考文献\n")
                        for r in refs:
                            parts.append(r.get("doi_url") or r.get("title", ""))
                except Exception:
                    # 回退：用存储的 citation_gbt7714 或 doi_url
                    parts.append("## 参考文献\n")
                    for r in refs:
                        parts.append(r.get("citation_gbt7714") or r.get("doi_url") or r.get("title", ""))
                refs_added = True
    return "\n\n".join(p for p in parts if p and p.strip())


@router.post("/report/export")
async def export_report(
    body: ExportRequest,
    user: UserInfo = Depends(require_permission("report:export")),
):
    """导出会话报告为 DOCX / PDF / Markdown。

    从会话展示消息拼接正文，渲染为目标格式，返回文件下载。
    RBAC：需要 report:export 权限（admin/researcher 角色具备）。
    """
    # 所有权校验（结构化错误）
    if not agent_loader.assert_session_owner(body.thread_id, user.user_id):
        raise HTTPException(
            status_code=403,
            detail={"code": "SESSION_FORBIDDEN", "message": "无权导出该会话", "detail": body.thread_id},
        )

    text = await _collect_thread_markdown(body.thread_id, citation_style=body.citation_style)
    if not text.strip():
        raise HTTPException(
            status_code=404,
            detail={"code": "SESSION_EMPTY", "message": "会话内容为空，无法导出", "detail": ""},
        )

    try:
        content, media_type, ext = render_report(text, fmt=body.format, pdf_template=body.pdf_template)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "RENDER_FAILED", "message": "渲染失败", "detail": str(e)},
        )

    from urllib.parse import quote

    filename = f"研途智探报告_{body.thread_id[:8]}.{ext}"
    # 中文文件名需 RFC 5987 编码（latin-1 header 限制）
    filename_ascii = f"report_{body.thread_id[:8]}.{ext}"
    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"{filename_ascii}\"; "
            f"filename*=UTF-8''{quote(filename)}"
        )
    }
    return Response(content=content, media_type=media_type, headers=headers)


class ExportMultiRequest(BaseModel):
    """批量/合并导出请求：多个会话合并为一份综述报告。"""
    thread_ids: list[str] = Field(..., description="会话 ID 列表（按序合并）")
    format: str = Field("docx", description="导出格式：docx / pdf / md")
    citation_style: str = Field("gbt7714", description="参考文献格式")
    pdf_template: str = Field("report", description="PDF 模板：report / academic")


@router.post("/report/export-multi")
async def export_multi(
    body: ExportMultiRequest,
    user: UserInfo = Depends(require_permission("report:export")),
):
    """批量导出：将多个会话合并为一份报告（综述场景）。

    RBAC：需要对每个 thread_id 有所有权。
    """
    if not body.thread_ids:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_THREADS", "message": "thread_ids 不能为空", "detail": ""},
        )
    # 逐个校验所有权 + 收集 markdown
    sections: list[str] = []
    for idx, tid in enumerate(body.thread_ids, 1):
        if not agent_loader.assert_session_owner(tid, user.user_id):
            raise HTTPException(
                status_code=403,
                detail={"code": "SESSION_FORBIDDEN", "message": f"无权导出会话 {tid}", "detail": tid},
            )
        md = await _collect_thread_markdown(tid, citation_style=body.citation_style)
        if md.strip():
            sections.append(f"## 第 {idx} 部分（会话 {tid[:8]}）\n\n{md}")
    if not sections:
        raise HTTPException(
            status_code=404,
            detail={"code": "ALL_EMPTY", "message": "所选会话内容均为空", "detail": ""},
        )
    text = "\n\n---\n\n".join(sections)
    try:
        content, media_type, ext = render_report(text, fmt=body.format, pdf_template=body.pdf_template)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "RENDER_FAILED", "message": "渲染失败", "detail": str(e)},
        )
    from urllib.parse import quote
    filename = f"研途智探合并报告_{len(body.thread_ids)}会话.{ext}"
    filename_ascii = f"report_multi_{len(body.thread_ids)}.{ext}"
    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"{filename_ascii}\"; "
            f"filename*=UTF-8''{quote(filename)}"
        )
    }
    return Response(content=content, media_type=media_type, headers=headers)
