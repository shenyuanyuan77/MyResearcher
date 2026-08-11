"""报告表格唯一出口 + 通用健康检查。

根因对策：对用户可见的表格不信任模型手写管道表；一律经 render_gfm_table 产出。
健康检查只做通用 GFM 结构校验（与领域无关），供前端决定是否跳过二次 normalize。
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence


def cell_safe(c: object) -> str:
    """单元格安全化：转义管道符、去除换行、清理破损代理对。"""
    s = str(c or "").replace("|", "｜").replace("\n", " ")
    s = s.replace("\ufffd", "")
    s = re.sub(r"[\ud800-\udfff]", "", s)
    return s.strip()


def render_gfm_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    *,
    min_sep: int = 6,
) -> str:
    """唯一合法的 GFM 表生成器。保证表头 / 分隔行 / 数据行列数一致。"""
    hdrs = [cell_safe(h) for h in headers]
    if len(hdrs) < 2:
        raise ValueError("table needs ≥2 columns")
    n = len(hdrs)
    lines = [
        "| " + " | ".join(hdrs) + " |",
        "| " + " | ".join("-" * max(min_sep, len(h)) for h in hdrs) + " |",
    ]
    for row in rows:
        cells = [cell_safe(x) for x in row]
        if len(cells) < n:
            cells.extend(["-"] * (n - len(cells)))
        elif len(cells) > n:
            cells = cells[: n - 1] + [" ".join(cells[n - 1 :])]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _iter_table_blocks(text: str) -> Iterable[tuple[int, int, list[str]]]:
    """Yield (start, end, lines) for consecutive pipe-row blocks."""
    lines = (text or "").split("\n")
    i = 0
    while i < len(lines):
        if not lines[i].strip().startswith("|"):
            i += 1
            continue
        start = i
        block: list[str] = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            block.append(lines[i])
            i += 1
        yield start, i, block


def _col_count(line: str) -> int:
    t = line.strip()
    if not t.startswith("|"):
        return 0
    return max(0, len([c for c in t.strip("|").split("|")]))


def _is_sep_line(line: str) -> bool:
    t = line.strip()
    return bool(re.match(r"^\|(?:[ \t]*:?-{1,}:?[ \t]*\|)+\s*$", t))


def find_table_health_issues(text: str) -> list[str]:
    """返回通用 GFM 不健康信号；空列表 = 结构健康。

    只做领域无关的结构检查（塌缩表、缺分隔行、列数错位、标题/说明误入表格），
    不含任何采购/ERP 业务关键词。
    """
    issues: list[str] = []
    s = text or ""
    lines = s.split("\n")

    # 塌缩表：|| 粘行 / 单行含表头+分隔 —— 绝不能跳过 normalize
    if re.search(r"\|\|[ \t]*(?:[^|\s\n]|:?-{2,})", s) or re.search(
        r"\|\|[ \t]*\|", s
    ):
        issues.append("collapsed_double_pipes")
    for line in lines:
        if (
            "||" in line
            and line.count("|") >= 6
            and re.search(r"\|[ \t]*:?-{2,}", line)
        ):
            issues.append("collapsed_single_line_table")
            break

    # 标题塞进首列表头（通用：含「明细/汇总/一览/清单 + 共N/：」的长标题）
    if re.search(
        r"^\|\s*[^|\n]*(?:明细|汇总|一览|清单).{0,12}(?:共\s*\d+|：)[^|\n]*\|",
        s,
        re.M,
    ):
        issues.append("title_in_table_header")
    # 说明/合计塞进单元格（通用：合计/结论/总结）
    if re.search(
        r"^\|[^\n]*\|[^|\n]*(?:合计[：:]|总计[：:]|结论[：:]|总结[：:])[^|\n]*\|",
        s,
        re.M,
    ):
        issues.append("summary_in_table_cell")

    # 表行之间插入编号散文
    for i, line in enumerate(lines):
        t = line.strip()
        if re.match(r"^\d+[\.、]\s+", t) and not t.startswith("|"):
            prev = lines[i - 1].strip() if i else ""
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if prev.startswith("|") and (nxt.startswith("|") or nxt.startswith("**")):
                issues.append("intrusion_between_table_rows")
                break

    # 多重伪分隔行
    if re.search(
        r"^\|[\s|:\-]+\|\s*\n\|[\s|:\-]+\|\s*\n\|[\s|:\-]+\|",
        s,
        re.M,
    ):
        issues.append("multi_fake_separators")

    # 逐块结构检查
    for _, _, block in _iter_table_blocks(s):
        if len(block) < 2:
            continue
        cols = [_col_count(ln) for ln in block if not _is_sep_line(ln)]
        if not cols:
            continue
        if max(cols) >= 4 and min(cols) <= 2 and len(set(cols)) >= 3:
            issues.append("ragged_column_counts")
            break
        if not any(_is_sep_line(ln) for ln in block[:3]) and len(block) >= 3:
            issues.append("missing_separator")
            break

    # 单元格内破损加粗
    if re.search(r"\|\s*\d+\s*\|[^|\n]*\*\*\s*\|", s):
        issues.append("broken_bold_in_cell")

    return issues


def report_tables_healthy(text: str) -> bool:
    """True = 前端可跳过 normalize，直接 markdown-it 渲染。"""
    if not text or len(text) < 20:
        return True
    return not find_table_health_issues(text)
