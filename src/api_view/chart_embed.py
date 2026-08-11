"""研途智探AI · 图表/图片嵌入辅助（轻量存根）。

研途 MVP 不生成图表（无 chart MCP），这里提供空实现保持 chat.py 兼容。
后续如接入图表工具，再实现真实逻辑。
"""

from __future__ import annotations

import re
from typing import Any


def collect_tool_chart_images(messages: list) -> list:
    """收集工具结果中的图片 URL（研途场景一般无图）。"""
    charts: list[str] = []
    for m in messages or []:
        for img in m.get("images", []) or []:
            if img and img not in charts:
                charts.append(img)
    return charts


def dedupe_markdown_images(text: str) -> str:
    """去掉重复的 markdown 图片链接。"""
    if not text:
        return text
    seen: set[str] = set()
    out: list[str] = []
    last_end = 0
    for m in re.finditer(r"!\[.*?\]\((.*?)\)", text):
        url = m.group(1)
        if url in seen:
            out.append(text[last_end:m.start()])
            last_end = m.end()
        else:
            seen.add(url)
    out.append(text[last_end:])
    return "".join(out)


def embed_orphan_chart_images(text: str, charts: list) -> str:
    """把未嵌入正文的图片追加到末尾（研途场景一般空操作）。"""
    if not charts:
        return text
    for url in charts:
        if url and f"]({url})" not in (text or ""):
            text = (text or "").rstrip() + f"\n\n![]({url})"
    return text
