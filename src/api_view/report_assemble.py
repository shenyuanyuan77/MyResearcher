"""研途智探AI · 深度报告组装（轻量存根）。

采购助手里会把子代理碎片化正文合成单一完整报告气泡。
研途 MVP 由 emit_research_report 统一成稿，这里做最小合并：仅合并相邻的
同源助手空/极短气泡，保持其余不变。
"""

from __future__ import annotations

from typing import Any


def assemble_deep_analysis_report(messages: list) -> list:
    """合并相邻同源助手气泡（研途轻量版）。

    深度报告已由 emit_research_report 通过 suggested_markdown 流式投影到
    助手气泡，这里仅做去重与相邻合并，避免重复内容。
    """
    if not messages:
        return messages
    out: list[Any] = []
    for m in messages:
        if (
            out
            and out[-1].get("role") == "assistant"
            and m.get("role") == "assistant"
            and out[-1].get("source") == m.get("source")
            and (not m.get("content") or m["content"] in (out[-1].get("content") or ""))
        ):
            # 跳过空或重复的助手气泡
            if not out[-1].get("content") and m.get("content"):
                out[-1]["content"] = m["content"]
            continue
        out.append(m)
    return out
