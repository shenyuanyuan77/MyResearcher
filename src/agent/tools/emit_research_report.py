"""深度报告终稿工具：一次性发布完整科研报告（综述/学者透视/跨界推演）。

用 write_markdown_table 备料后，必须且只能调用本工具输出完整 Markdown，
避免与助手正文抢输出，也避免半截报告。
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.tools import tool

_DOWNLOAD_ASK = "是否需要将此报告下载到本地？回复「下载」即可。"

_MIN_LEN = 600
# 研究报告标题：综述/透视/推演/分析报告/审稿报告 等
_TITLE_RE = re.compile(
    r"综述|研究报告|文献综述|学者透视|资产透视|跨界推演|可行性|分析报告|审稿报告|^#\s*📊",
    re.M,
)


def normalize_report_markdown(markdown: str) -> str:
    body = (markdown or "").strip()
    if not body:
        raise ValueError("markdown 不能为空")
    if len(body) < _MIN_LEN:
        raise ValueError(
            f"报告过短（{len(body)} 字，至少 {_MIN_LEN}）：请嵌入表格原文与文献 DOI 后重试"
        )
    if not _TITLE_RE.search(body):
        raise ValueError("报告须含标题（如「文献综述」「研究报告」「学者透视」「跨界推演」「审稿报告」等）")
    # 软提醒：文献类报告应含参考文献章节（不阻断，仅追加提示）
    if any(
        kw in body for kw in ("文献", "综述", "学者", "审稿", "DOI")
    ) and "参考文献" not in body:
        body += "\n\n> ⚠️ 提示：本报告引用了文献但未含「## 参考文献」章节，建议补全（可照贴工具返回的 references_markdown）。\n"
    tail = body[-400:]
    if "下载" not in tail:
        body = body.rstrip() + f"\n\n---\n\n{_DOWNLOAD_ASK}\n"
    return body


def build_emit_payload(markdown: str, *, title: str = "") -> dict[str, Any]:
    body = normalize_report_markdown(markdown)
    display_title = (title or "").strip() or "研究报告"
    return {
        "ok": True,
        "tool": "emit_research_report",
        "title": display_title,
        "message": f"✅ 《{display_title}》已生成完整正文，见下方报告。",
        "suggested_markdown": body,
        "char_count": len(body),
    }


@tool
def emit_research_report(markdown: str, title: str = "研究报告") -> str:
    """发布完整科研报告（深度分析唯一成稿出口）。

    **必须在数据收集全部完成之后调用**（paper_search/author_profile/cross_search
    已返回，且全部 write_markdown_table 写表均已返回）。

    把工具返回的文献表格 Markdown 原文（含 DOI 链接）嵌进 markdown，
    按章节一次性传入。本工具返回后禁止再调 write_markdown_table，
    也禁止用多段短回复拆开报告。

    Args:
        markdown: 完整报告 Markdown 正文（须含标题、章节、文献表、DOI 链接；文末可询问下载）。
        title: 报告短标题，如「大模型推理文献综述」。

    Returns:
        JSON：含 suggested_markdown（完整报告）与短 message（工具卡片用）。
    """
    try:
        payload = build_emit_payload(markdown, title=title or "研究报告")
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps(
            {"ok": False, "error": str(exc), "tool": "emit_research_report"},
            ensure_ascii=False,
        )
