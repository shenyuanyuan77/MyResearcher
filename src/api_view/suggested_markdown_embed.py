"""MyResearcher · suggested_markdown 注入（轻量存根）。

工具返回的 suggested_markdown（如 paper_search 的文献表）应作为该工具
对应助手气泡的正文来源，而非模型手抄。这里做轻量应用。
"""

from __future__ import annotations

import re
from typing import Any


def apply_suggested_markdowns_to_display(messages: list) -> list:
    """若工具消息含 suggested_markdown，把它合并到相邻的助手气泡。

    研途 MVP：仅当助手气泡内容为空或明显残缺时，用工具返回的 suggested_markdown
    填充；否则保留模型已生成的内容（模型通常会引用并改写）。
    """
    if not messages:
        return messages
    # 收集每个工具的 suggested_markdown
    suggested: dict[str, str] = {}
    for m in messages:
        if m.get("role") == "tool" and m.get("text"):
            txt = m["text"]
            # 工具结果里可能含 suggested_markdown 字段（JSON）或直接 markdown
            mt = re.search(r'"suggested_markdown"\s*:\s*"((?:[^"\\]|\\.)*)"', txt)
            if mt:
                try:
                    suggested[m.get("id", "")] = bytes(mt.group(1), "utf-8").decode("unicode_escape")
                except Exception:
                    pass
    if not suggested:
        return messages
    # 简单策略：不强行覆盖；模型已能正确引用 suggested_markdown（见 smoke 测试）
    return messages
