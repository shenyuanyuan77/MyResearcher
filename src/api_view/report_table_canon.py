"""报告表格唯一出口 + 健康检查。

根因对策：关键区块不信任模型手写管道表；一律经 render_gfm_table 产出。
健康正文禁止再二次「创意」重整（前端可直接跳过 normalize）。
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence


def cell_safe(c: object) -> str:
    s = str(c or "").replace("|", "｜").replace("\n", " ")
    # 去掉替换符 / 残破代理对，避免界面出现 �
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
        # 允许块内空行打断？健康表不应有 — 空行即结束
        yield start, i, block


def _col_count(line: str) -> int:
    t = line.strip()
    if not t.startswith("|"):
        return 0
    return max(0, len([c for c in t.strip("|").split("|")]) )


def _is_sep_line(line: str) -> bool:
    t = line.strip()
    return bool(re.match(r"^\|(?:[ \t]*:?-{1,}:?[ \t]*\|)+\s*$", t))


def find_table_health_issues(text: str) -> list[str]:
    """返回不健康信号；空列表 = 可跳过二次 normalize。"""
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

    # 竖切供应表头
    if re.search(r"^\|\s*(占比|角色|信用|涉及物料)\s*\|?\s*$", s, re.M):
        issues.append("vertical_supply_header")
    if re.search(r"\*\*供应结构\*\*[：:]*[ \t]*\|", s):
        issues.append("glued_supply_header")
    if re.search(r"\*\*风险要点\*\*[：:]*[ \t]*\|", s):
        issues.append("glued_risk_header")
    if re.search(r"(?<!\*)(?:供应结构|风险要点)[：:][ \t]*\|", s):
        issues.append("glued_plain_section_header")
    # 仅同行粘连；换行后的 ]\n\n** 是正常排版
    if re.search(r"\]\([^)]+\)[ \t]*\*\*", s):
        issues.append("image_glued_to_heading")
    # 图/图表进了管道表单元格（常见于风险说明第 N 行）
    if re.search(r"^\|[^\n]*!\[[^\]]*\]\([^)]+\)", s, re.M):
        issues.append("image_in_table")
    # 多条风险 emoji 挤在同一格
    if re.search(
        r"^\|\s*\d+\s*\|[^|\n]*(?:[🔴🟡🟢🟠]|⚠️)[^|\n]*(?:[🔴🟡🟢🟠]|⚠️)",
        s,
        re.M,
    ):
        issues.append("mashed_risk_emojis")
    if len(re.findall(r"\*\*风险要点\*\*", s)) >= 2:
        issues.append("duplicate_risk_sections")
    # 份额伪行：短描述「供应商 ¥金额（占比%）」；勿误伤含涨幅的真价格风险
    for line in lines:
        rm = re.match(r"^\|\s*\d+\s*\|\s*([^|]+?)\s*\|?", line)
        if not rm:
            continue
        d = rm.group(1).strip()
        if re.search(
            r"(库存|安全|替代|单源|涨|交期|效期|到期|预警|断供|缺口|无替代|缺料)",
            d,
        ):
            continue
        if re.search(r"¥\s*[\d,]+\s*[（(]?\s*\d+\.?\d*\s*%", d) or (
            "¥" in d and "%" in d and len(d) < 48
        ):
            issues.append("fake_risk_amount_row")
            break

    # 表行之间插入编号散文
    for i, line in enumerate(lines):
        t = line.strip()
        if re.match(r"^\d+[\.、]\s+", t) and not t.startswith("|"):
            prev = lines[i - 1].strip() if i else ""
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if prev.startswith("|") and (nxt.startswith("|") or nxt.startswith("**")):
                issues.append("intrusion_between_table_rows")
                break

    if re.search(
        r"^\|[\s|:\-]+\|\s*\n\|[\s|:\-]+\|\s*\n\|[\s|:\-]+\|",
        s,
        re.M,
    ):
        issues.append("multi_fake_separators")

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

    if re.search(r"\|\s*\d+\s*\|[^|\n]*\*\*\s*\|", s):
        issues.append("broken_bold_in_cell")
    if re.search(r"^\d+[\.、]\s*\*\*CCL\s*\|", s, re.M):
        issues.append("split_material_code")

    # 价格趋势密文或残表（有 1688/高TG 却无板多多主行）
    if re.search(r"价格趋势\s*FR\s*4|稳步上行：\s*-?\s*最低", s):
        issues.append("mashed_price_trend_prose")
    pt = re.search(
        r"#{2,3}\s+[^\n]*价格趋势([\s\S]{0,1200}?)(?=\n#{2,3}\s+|\n##\s|\n---\s*\n|$)",
        s,
    )
    if pt:
        block = pt.group(1)
        has_bdd_row = bool(
            re.search(r"^\|\s*[^|\n]*板多多[^|\n]*\|", block, re.M)
        )
        if (
            re.search(r"\|[^\n]*规格[^\n]*渠道", block)
            and re.search(r"1688|高TG|高\s*TG", block)
            and not has_bdd_row
        ):
            issues.append("incomplete_price_trend_table")

    # 仪表盘残表
    if re.search(r"\|\s*列\s*[12]\s*\|", s):
        issues.append("fake_column_headers")
    if re.search(r"\|\s*项目\s*\|\s*内容\s*\|", s) and re.search(
        r"\|\s*(?:0?\d{1,2}\s*月|20\d{2}-\d{2})\s*\|", s
    ):
        issues.append("fake_project_content_headers")
    if re.search(
        r"月度采购趋势[^\n]{0,40}?月份[ \t]+(?:采购额|订单数)",
        s,
    ):
        issues.append("glued_monthly_trend_header")
    if re.search(r"\|[^\n]*\|\n\*\*?趋势小结", s):
        issues.append("trend_summary_glued_to_table")
    # KPI 表吞月度行
    if re.search(
        r"\|\s*(?:本月订单数|本月采购额|物料总数)[^\n]*\|\n"
        r"(?:\|[-:| \t]+\|\n)*(?:\|\s*(?:列\s*[12]|项目|内容)[^\n]*\|\n)*"
        r"\|\s*(?:0?\d{1,2}\s*月|20\d{2}-\d{2})\s*\|",
        s,
    ):
        issues.append("kpi_holds_month_rows")
    if re.search(r"风险要点[\s\S]{0,400}月度采购趋势", s):
        issues.append("risk_holds_monthly_trend")
    # 行动表残行 + 表外 emoji 溢出 / 选型速查密文
    if re.search(
        r"\|\s*\d+\s*\|[^|\n]+\|\s*\|\s*\|",
        s,
    ) and re.search(r"(?:^|\n)[🔴🟡🟢]", s):
        issues.append("incomplete_action_row_spill")
    if re.search(
        r"选型建议速查[^\n]*场景[ \t]+推荐渠道[ \t]+理由",
        s,
    ):
        issues.append("mashed_selection_quickcheck")
    # 下单追问粘在表行末
    if re.search(
        r"^\|[^\n]*\|\s*(?:你要|你需要|请问|请选择|请确认|确认后|哪一款)",
        s,
        re.M,
    ) or re.search(
        r"^\|[^\n]*\|[^|\n]*(?:哪一款|哪种铜箔|立刻下单|请确认物料)",
        s,
        re.M,
    ):
        issues.append("glued_order_ask_to_table")
    if (
        re.search(r"\*{0,2}已收集的(?:订单)?数据\*{0,2}", s)
        and re.search(r"物料(?:名称|ID)|partId", s, re.I)
        and not re.search(r"\|\s*字段\s*\|\s*值\s*\|", s)
    ):
        issues.append("mashed_order_collected_prose")
    # 标题塞进首列表头 / 合计塞进末格
    if re.search(
        r"^\|\s*[^|\n]*(?:明细|汇总|一览).{0,12}(?:共\s*\d+|：)[^|\n]*\|",
        s,
        re.M,
    ):
        issues.append("title_in_table_header")
    if re.search(
        r"^\|[^\n]*\|[^|\n]*(?:本月合计|合计[：:]|均无[「\"“]?已取消|按供应商|结论[：:])[^|\n]*\|",
        s,
        re.M,
    ):
        issues.append("summary_in_table_cell")
    # 仅当「预警」小节内部（到下一个 ###/## 之前）出现 YYYY-MM / N月 月度行
    for wm in re.finditer(
        r"#{2,3}\s*[^\n]*预警[^\n]*\n([\s\S]*?)(?=\n#{1,3}\s|\Z)",
        s,
    ):
        if re.search(
            r"\|\s*(?:20\d{2}-(?:0[1-9]|1[0-2])|0?\d{1,2}\s*月)\s*\|",
            wm.group(1),
        ):
            issues.append("monthly_data_in_warning_section")
            break

    return issues


def report_tables_healthy(text: str) -> bool:
    """True = 前端可跳过 normalize，直接 markdown-it 渲染。"""
    if not text or len(text) < 20:
        return True
    return not find_table_health_issues(text)


def emit_supply_table(rows: Sequence[Sequence[object]]) -> str:
    return (
        "**供应结构**\n\n"
        + render_gfm_table(
            ["供应商", "物料", "金额 (¥)", "占比", "角色", "信用"],
            rows,
        )
        + "\n\n"
    )


def emit_risk_table(items: Sequence[str]) -> str:
    rows = [[str(i), cell_safe(desc)] for i, desc in enumerate(items, 1)]
    return (
        "**风险要点**\n\n"
        + render_gfm_table(["序号", "风险说明"], rows)
        + "\n\n"
    )


def emit_order_integrity_table(rows: Sequence[Sequence[object]]) -> str:
    """下单完整性校验表（字段 | 值 | 状态）。"""
    return render_gfm_table(["字段", "值", "状态"], rows) + "\n"
