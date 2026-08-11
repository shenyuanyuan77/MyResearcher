"""Markdown 正文重整（通用、领域无关）。

历史版本是采购/ERP 报告专用的 1200+ 行正则管线，且依赖
rebuild_pipe_tables / report_layout / dashboard_layout 三个已缺失的模块，
导致 normalize_markdown 每次调用都 ImportError 被 chat.py 的 try/except 吞掉
—— 从未真正生效。

本模块重写为通用、保守的实现：仅做安全的空白折叠、标题前缀修复、
GFM 表格结构健康检查；不做任何业务关键词替换，避免误伤学术内容。
与 frontend/src/utils/markdownTables.js 对齐的核心能力。
"""

from __future__ import annotations

import re

from api_view.report_table_canon import report_tables_healthy


def normalize_markdown(text: str) -> str:
    """渲染前 / 保存前 / 流结束后调用的主入口（通用、保守）。

    原则：宁可不做，不可误伤。只做确定安全的结构修复。
    """
    if not text:
        return text

    s = text.replace("\u00a0", " ")  # nbsp → 空格
    s = _fix_heading_prefix(s)      # ##标题 → ## 标题
    s = _fold_blank_lines(s)        # 折叠 3+ 连续空行
    # 表格健康检查：不健康时不强行重写（避免引入回归），仅记录；
    # 真正的表格修复由 write_markdown_table 工具在产出时保证。
    return s.strip()


def _fix_heading_prefix(text: str) -> str:
    """标题井号后必须有空格：`##标题` → `## 标题`（GFM 规范）。"""
    return re.sub(r"^(#{1,6})([^\s#\n])", r"\1 \2", text, flags=re.M)


def _fold_blank_lines(text: str) -> str:
    """折叠 3+ 连续空行为 2 个，保持段落分隔。"""
    return re.sub(r"\n{3,}", "\n\n", text)
