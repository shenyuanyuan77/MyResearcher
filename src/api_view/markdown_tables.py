"""Markdown 报告重整（与 frontend/src/utils/markdownTables.js 对齐的核心能力）。"""

from __future__ import annotations

import re

_PROSE_START = re.compile(
    r"^(?:>+\s*)?(需要进一步|需要查看|全部来自|全部|供应商统一|以上|综上|所有|备注|如果你|若需|覆盖|均符合|关键发现|期内)"
)
_NAME_LIKE = re.compile(
    r"^(?:[0-9一二三四五六七八九十]+层|铝基|铜基|FR4|FR-?4|PCB|沉金|HDI|CCL|高TG|半固化)",
    re.I,
)
_MPN_LIKE = re.compile(r"^(?:PCB|ALPCB|CCL|IC|R|C|L|FR4|LOT)[-_A-Z0-9]", re.I)
_SEP_RE = re.compile(r"\|(?:[ \t]*:?-{1,}:?[ \t]*\|){2,}")
_DASH_RE = re.compile(r"[—–﹣－―]")
_PIPE_ROW = re.compile(r"^\|.*\|")
_SEP_LINE = re.compile(r"^\|(?:[ \t]*:?-{1,}:?[ \t]*\|)+$")


def normalize_markdown(text: str) -> str:
    """渲染前 / 保存前 / 流结束后调用的主入口。

    产出应通过 report_tables_healthy；前端对健康正文跳过二次 normalize。
    """
    if not text:
        return text
    from api_view.rebuild_pipe_tables import (
        fix_dense_report_prose,
        rebuild_pipe_tables,
        split_heading_tables,
    )
    from api_view.report_layout import (
        detach_media_from_pipe_tables,
        format_report_layout,
        merge_orphan_table_name_rows,
        repair_supplier_amount_share_tables,
        repair_order_integrity_tables,
    )
    from api_view.report_table_canon import report_tables_healthy

    # 已是健康终态 → 直接返回，保证幂等且避免越修越坏
    if report_tables_healthy(text) and "**供应结构**" in text and "| 供应商 |" in text:
        # 仍做轻量空白折叠，保持与 trim 行为一致
        return re.sub(r"\n{3,}", "\n\n", text.replace("\u00a0", " ")).strip()

    s = text.replace("\u00a0", " ")
    s = _explode_double_pipes(s)
    s = fix_headings_and_structure(s)
    s = fix_meta_and_lists(s)
    s = re.sub(r"^(#{1,6})([^\s#\n])", r"\1 \2", s, flags=re.M)
    s = separate_media_and_blocks(s)
    s = detach_media_from_pipe_tables(s)
    s = split_heading_tables(s)
    s = ensure_table_starts_on_own_line(s)
    s = fix_glued_table_headers(s)
    s = fix_markdown_tables(s)
    s = fix_dense_report_prose(s)
    s = peel_glued_table_row_prose(s)
    s = peel_table_caption_and_footer(s)
    s = merge_orphan_table_name_rows(s)
    # 供应商金额分布锯齿表：须在 rebuild 发明「项目|内容」之前纠正
    s = repair_supplier_amount_share_tables(s)
    s = repair_order_integrity_tables(s)
    s = rebuild_pipe_tables(s)
    s = repair_supplier_amount_share_tables(s)
    s = repair_order_integrity_tables(s)
    s = fix_space_separated_tables(s)
    s = peel_glued_table_row_prose(s)
    s = peel_table_caption_and_footer(s)
    s = break_tables_on_section_intrusions(s)
    s = collapse_order_dump_tables(s)
    s = format_report_layout(s)
    s = detach_media_from_pipe_tables(s)
    s = _peel_inline_notes(s)
    s = dedupe_repeated_sections(s)
    s = trim_after_download_cta(s)
    from api_view.dashboard_layout import ensure_blank_line_after_tables

    s = ensure_blank_line_after_tables(s)
    s = re.sub(r"^#{1,6}\s*$", "", s, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def separate_media_and_blocks(text: str) -> str:
    """图、表、标题分块，避免图和表头并排。"""
    s = text or ""
    s = re.sub(r"([^\n\s!])(!\[[^\]]*\]\()", r"\1\n\n\2", s)
    s = re.sub(r"(\]\([^)\n]+\))\s*(\|(?=[^|\n]*\|))", r"\1\n\n\2", s)
    s = re.sub(r"(\]\([^)\n]+\))\s*(-\s+)", r"\1\n\n\2", s)
    s = re.sub(r"(\]\([^)\n]+\))\s*(---)", r"\1\n\n\2", s)
    s = re.sub(r"(\]\([^)\n]+\))\s*(#{1,3}\s)", r"\1\n\n\2", s)
    s = re.sub(r"^(#{1,6}[^\n!]+?)(!\[[^\]]*\]\()", r"\1\n\n\2", s, flags=re.M)
    return s


def break_tables_on_section_intrusions(text: str) -> str:
    """表行里塞进下一节标题时拆表。"""
    out: list[str] = []
    in_table = False

    def flush_intrusion(cells: list[str]) -> bool:
        first = (cells[0] or "").strip()
        if not (
            re.match(r"^#{1,3}", first)
            or re.search(r"月度价格走势|成交价趋势", first)
            or ("###" in first)
        ):
            return False
        cleaned = re.sub(r"^#+\s*", "", first).replace("**", "").strip()
        title = re.split(r"[：:]", cleaned, maxsplit=1)[0].strip() or "补充说明"
        parts = re.split(r"[：:]", cleaned, maxsplit=1)
        after = parts[1].strip() if len(parts) > 1 else ""
        out.extend(["", f"### {title}"])
        maybe = [c for c in cells[1:] if c and not re.fullmatch(r"-+", c)]
        if (
            len(maybe) >= 2
            and all(len(c) < 20 for c in maybe)
            and re.search(r"日期|数量|单价|金额|订单", "".join(maybe))
        ):
            out.extend(["", "|" + "|".join(maybe) + "|"])
        elif after:
            out.extend(["", after])
        elif maybe:
            out.extend(["", " ".join(maybe)])
        out.append("")
        return True

    for line in (text or "").split("\n"):
        trimmed = line.strip()
        is_sep = bool(_SEP_LINE.match(trimmed))
        is_pipe = trimmed.startswith("|") and trimmed.count("|") >= 2
        if is_sep:
            in_table = True
            out.append(line)
            continue
        if in_table and is_pipe:
            body = trimmed[1:] if trimmed.startswith("|") else trimmed
            if body.endswith("|"):
                body = body[:-1]
            cells = [c.strip() for c in body.split("|")]
            intrusion_at = next(
                (
                    i
                    for i, c in enumerate(cells)
                    if re.match(r"^#{1,3}", c)
                    or re.search(r"月度价格走势|成交价趋势", c)
                    or ("###" in c and len(c) > 8)
                    or re.search(r"\*\*[^*]*成交价趋势\*\*", c)
                ),
                -1,
            )
            if intrusion_at >= 0:
                in_table = False
                flush_intrusion(cells[intrusion_at:])
                continue
            out.append(line)
            continue
        if in_table and trimmed and not is_pipe:
            in_table = False
        out.append(line)
    return "\n".join(out)


def collapse_order_dump_tables(text: str) -> str:
    """塌缩 Order# 流水为区间说明；若后文已有趋势研判则直接删除密表。"""
    lines = (text or "").split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        looks_header = line.strip().startswith("|") and re.search(
            r"订单日期|成交单价|数量\s*\(", line
        )
        looks_order = bool(re.search(r"Order#\s*\d+", line, re.I))
        if looks_header or looks_order:
            j = i
            block: list[str] = []
            while j < len(lines):
                L = lines[j]
                t = L.strip()
                if re.search(r"Order#\s*\d+", L, re.I) or (
                    t.startswith("|")
                    and (
                        re.search(r"订单日期|成交单价|数量\s*\(", t)
                        or re.fullmatch(r"\|[-:\s|]+\|", t)
                        or (re.search(r"\d+\.\d{2}", t) and block)
                    )
                ):
                    block.append(L)
                    j += 1
                    continue
                if t.startswith("|") and re.search(r"Order#|\d+\.\d{2}", t) and len(block) >= 2:
                    block.append(L)
                    j += 1
                    continue
                break
            order_hits = sum(1 for b in block if re.search(r"Order#", b, re.I))
            if order_hits >= 2 or (looks_header and order_hits >= 1 and len(block) >= 3):
                prices: list[float] = []
                for b in block:
                    for m in re.finditer(r"(?<![\d.])(\d{2,3}\.\d{2})(?![\d.])", b):
                        v = float(m.group(1))
                        if 20 <= v <= 500:
                            prices.append(v)
                ahead = "\n".join(lines[j : j + 6])
                has_judgement = bool(re.search(r"趋势研判|从\s*~?¥|涨至|升到", ahead))
                if not has_judgement and len(prices) >= 2:
                    lo, hi = min(prices), max(prices)
                    out.append(
                        f"用大白话概括：这段成交价大约从 ¥{lo:.2f} 到 ¥{hi:.2f}，逐笔订单不再展开。"
                    )
                    out.append("")
                while out:
                    last = out[-1].strip()
                    if not last or re.match(r"^\|订单日期\|", last) or re.fullmatch(
                        r"\|[-:\s|]+\|", last
                    ):
                        out.pop()
                        continue
                    break
                i = j
                continue
        out.append(line)
        i += 1
    return "\n".join(out)


def _explode_double_pipes(text: str) -> str:
    s = text or ""
    s = re.sub(r"\|[ \t]*\|(?=[ \t]*:?-{2,})", "|\n|", s)
    s = re.sub(r"(\|:?-{2,}:?\|)[ \t]*\|+", r"\1\n|", s)
    s = re.sub(r"\|{2,}(?=[ \t]*:?-{2,})", "|\n|", s)
    s = re.sub(r"([✅❌])\|[ \t]*\|+(?=[ \t]*[A-Za-z0-9\u4e00-\u9fff])", r"\1|\n|", s)
    s = re.sub(
        r"\|{2,}(?=[ \t]*(?:CCL|PCB|ALPCB|SUP|板|阿|合|FR|高TG|维度|供应商))",
        "|\n|",
        s,
    )
    s = re.sub(r"\|{2,}(?=[ \t]*[^|\s\n])", "|\n|", s)
    return s


def fix_meta_and_lists(text: str) -> str:
    s = text or ""
    s = re.sub(r"(可视化图表已生成[^\n#]*)(#{1,3})", r"\1\n\n\2", s)
    s = re.sub(r"([。．])(#{1,3})([^\s#\n])", r"\1\n\n\2 \3", s)
    s = re.sub(
        r"\s*>\s*(?=(?:\*{0,2})(?:报告日期|分析区间|编制对象|编制人|币种|货币|分析对象|统计周期|报告时间|生成时间|公司)[：:*])",
        "\n> ",
        s,
    )
    s = re.sub(
        r"([^\n])[ \t]+(?=(?:报告日期|分析区间|编制对象|编制人|币种|货币)[：:])",
        r"\1\n> ",
        s,
    )
    s = re.sub(r"\n>\s*\n", "\n", s)
    def _break_glued_nums_outside_tables(text: str) -> str:
        """编号列表粘连拆行；表行（以 | 开头）一律跳过，保证幂等。"""
        out: list[str] = []
        for line in text.split("\n"):
            if line.strip().startswith("|"):
                out.append(line)
                continue
            line = re.sub(r"([。；!！])\s*(?=[2-9]\d?\.\s+)", r"\1\n", line)
            line = re.sub(r"[ \t]+(?=[2-9]\d?\.\s+\*\*)", "\n", line)
            line = re.sub(
                r"([。；）%）\u4e00-\u9fff])\s+([2-9]\d?)\s+(\*\*[^*\n]{2,80}\*\*)",
                r"\1\n\2. \3",
                line,
            )
            line = re.sub(
                r"([。；）%）\u4e00-\u9fff])\s+([2-9]\d?)\s+(?=[\u4e00-\u9fffA-Za-z*])",
                r"\1\n\2. ",
                line,
            )
            line = re.sub(
                r"([^\n])([2-9]\d?\.\s+(?:\*\*[^*]{2,40}\*\*|[\u4e00-\u9fff]{2,20}[（(]))",
                r"\1\n\2",
                line,
            )
            out.append(line)
        return "\n".join(out)

    s = _break_glued_nums_outside_tables(s)
    s = s.replace("报告下载下载", "")
    # 下载 CTA 前加分隔线；已有独立 --- 行则不动（避免二次 normalize 把表尾 | 与 --- 拆乱）
    if not re.search(r"(?:^|\n)---\s*\n+\s*是否需要将此报告下载", s):
        s = re.sub(r"([^\n])\s*(是否需要将此报告下载)", r"\1\n\n---\n\n\2", s)
    # 表行紧贴 --- 时补空行（幂等：已有空行则不匹配）
    s = re.sub(r"(^\|[^\n]*\|)\n(---\s*$)", r"\1\n\n\2", s, flags=re.M)
    return s


def ensure_table_starts_on_own_line(text: str) -> str:
    """中文说明后紧跟表头时拆行；已在表内的行（以 | 开头）绝不拆。"""
    out: list[str] = []
    for line in (text or "").split("\n"):
        if line.strip().startswith("|"):
            out.append(line)
            continue
        line = re.sub(
            r"([：:。；）】\]])\s*(\|(?:[^|\n]+\|){2,})",
            r"\1\n\n\2",
            line,
        )
        line = re.sub(
            r"(#{1,6}[^\n|]+[）)\u4e00-\u9fff])\s*(\|(?:[^|\n]+\|){2,})",
            r"\1\n\n\2",
            line,
        )
        out.append(line)
    return "\n".join(out)


def fix_glued_table_headers(text: str) -> str:
    """表头不以 | 开头时 GFM 不渲染，用户会看到原始 markdown。"""
    lines = (text or "").split("\n")
    out: list[str] = []
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        next_is_sep = bool(
            re.match(r"^\s*\|(?:[ \t]*:?-{1,}:?[ \t]*\|)+\s*$", nxt)
            or re.match(r"^\s*\|?-{3,}.*\|.*-{3,}", nxt)
        )
        pipe_count = line.count("|")
        if (
            next_is_sep
            and pipe_count >= 2
            and not re.match(r"^\s*\|", line)
            and not re.match(r"^\s*#{1,6}\s", line)
            and not re.match(r"^\s*>", line)
        ):
            idx = line.find("|")
            if idx > 0:
                label = line[:idx].strip()
                header = line[idx:].strip()
                if not header.startswith("|"):
                    header = "|" + header
                if not header.endswith("|"):
                    header = header + "|"
                if label and (
                    re.search(r"(?:对比|方案|清单|概览|分析|明细)$", label)
                    or re.match(r"^(?:板\s*)?FR-?4|^板\s*FR|^覆铜板?", label, re.I)
                ):
                    out.extend([label, "", header])
                elif label:
                    out.append("|" + label + header)
                else:
                    out.append(header)
                continue
        if (
            pipe_count >= 2
            and not re.match(r"^\s*\|", line)
            and re.match(r"^[ \t]*:?-{2,}", line.strip())
        ):
            out.append("|" + line.strip())
            continue
        out.append(line)
    return "\n".join(out)


def fix_headings_and_structure(text: str) -> str:
    s = text or ""
    s = re.sub(r"[—–﹣－]+(#{1,6})(?=[^\n#])", r"\n\n\1", s)
    s = re.sub(r"(#{1,6})[—–﹣－]+", r"\1\n\n", s)
    s = re.sub(
        r"(#{1,3}[ \t]*[^\n#>]+?)>([ \t]*(?:分析对象|统计周期|报告时间|生成时间|公司|报告日期|分析区间|编制对象|编制人|币种|货币)[^\n#]*)",
        r"\1\n\n> \2",
        s,
    )
    s = re.sub(
        r"([一二三四五六七八九十]+)、?[ \t]*(#{1,3})[ \t]*([一二三四五六七八九十]+、[^\n]*)",
        r"\n\n\2 \3",
        s,
    )
    s = re.sub(r"([^\n#])(#{1,3})[ \t]*([一二三四五六七八九十]+、)", r"\1\n\n\2 \3", s)
    s = re.sub(r"([^\n])(#{2,3})(\d+\.\d+)", r"\1\n\n\2 \3", s)
    s = re.sub(r"(#{2,3})(\d+\.\d+)", r"\1 \2", s)
    s = re.sub(r"(#{1,3})([一二三四五六七八九十]+、)", r"\1 \2", s)
    s = re.sub(r"([。：；）\])])(#{1,3}[ \t])", r"\1\n\n\2", s)
    s = re.sub(r"^(#{1,6})([^\s#\n])", r"\1 \2", s, flags=re.M)

    def _split_section(m: re.Match[str]) -> str:
        hash_ = m.group(1) or "## "
        num, title, rest = m.group(2), m.group(3), m.group(4) or ""
        body = re.sub(r"^[：:\s]+", "", rest)
        if body and (re.match(r"^(由|覆铜板|共|期内|主要|本|该)", body) or len(body) > 4):
            return f"{hash_}{num}{title}\n\n{body}"
        return f"{hash_}{num}{title}{rest}"

    s = re.sub(
        r"^(#{1,3}[ \t]+)?([一二三四五六七八九十]+、)"
        r"(供应商概览|物料清单|替代料分析|采购趋势|库存分析|比价分析|风险|结论|摘要|仪表盘|行动建议)"
        r"([^\n]*)$",
        _split_section,
        s,
        flags=re.M,
    )

    def _split_sub(m: re.Match[str]) -> str:
        h, rest = m.group(1), m.group(2)
        mm = re.match(
            r"^([\u4e00-\u9fffA-Za-z0-9（）()_-]{2,16}?)"
            r"((?:物料编码|规格|供应商|期内|主|其|本|FR|CCL|板).+)$",
            rest,
        )
        if mm:
            return f"{h} {mm.group(1)}\n\n{mm.group(2)}"
        return f"{h} {rest}"

    s = re.sub(
        r"^(#{2,3}[ \t]+\d+\.\d+)([\u4e00-\u9fff][^\n]*)$",
        _split_sub,
        s,
        flags=re.M,
    )
    return s


def _peel_inline_notes(text: str) -> str:
    s = text
    s = re.sub(r"(\S)(>\s*[⚠️🔴🟠])", r"\1\n\n\2", s)
    s = re.sub(r"(\S)(🔴\s*风险提示)", r"\1\n\n\2", s)
    s = re.sub(r"([✅❌])\s*(>\s*)", r"\1\n\n\2", s)
    s = re.sub(r"([^\n|])(>\s*⚠️)", r"\1\n\n\2", s)
    s = re.sub(r"(>[^\n]*?)\s*[一二三四五六七八九十]+\|\s*$", r"\1", s, flags=re.M)
    return s


_TITLE_IN_HEADER = re.compile(
    r"(?:明细|汇总|一览|清单).{0,12}(?:共\s*\d+|：|:)"
    r"|本月.{0,16}(?:采购|订单).{0,12}(?:明细|共)"
    r"|共\s*\d+\s*单"
)
_SUMMARY_IN_CELL = re.compile(
    r"(?:本月合计|合计[：:]|均无[「\"“]?已取消|共\s*\d+\s*单|"
    r"按供应商|结论[：:]|请原样采用)"
)
_DATE_THEN_PROSE = re.compile(r"^(\d{1,2}\s*/\s*\d{1,2}|\d{4}-\d{2}-\d{2})\s*(.+)$")
_MONEY_THEN_PROSE = re.compile(r"^([¥￥]\s*[\d,]+(?:\.\d+)?)\s+(.+)$")


def looks_like_title_header(cell: object) -> bool:
    s = str(cell or "").strip()
    if len(s) < 10:
        return False
    if _TITLE_IN_HEADER.search(s):
        return True
    return len(s) >= 16 and ("：" in s or "共" in s)


def _normalize_date_token(raw: str) -> str:
    return re.sub(r"\s*", "", (raw or "").strip())


def peel_summary_cell(last: str) -> tuple[str, str | None]:
    """若末格含合计/按供应商等说明：金额或日期留格内，说明出表。"""
    s = (last or "").strip()
    if not s or not _SUMMARY_IN_CELL.search(s):
        return s, None
    mm = _MONEY_THEN_PROSE.match(s)
    if mm and _SUMMARY_IN_CELL.search(mm.group(2)):
        money = re.sub(r"\s+", "", mm.group(1))
        return money, mm.group(2).strip()
    m = _DATE_THEN_PROSE.match(s)
    if m:
        date = _normalize_date_token(m.group(1))
        rest = m.group(2).strip()
        if rest and _SUMMARY_IN_CELL.search(rest):
            return date, rest
        if rest:
            return date, rest
    if len(s) >= 10:
        return "-", s
    return s, None


def _looks_like_date_cell(v: str) -> bool:
    t = (v or "").strip()
    return bool(
        re.match(r"^\d{1,2}/\d{1,2}\b", t) or re.match(r"^\d{4}-\d{2}-\d{2}\b", t)
    )


def _looks_like_money_cell(v: str) -> bool:
    t = (v or "").strip()
    return "¥" in t or "￥" in t or bool(
        re.match(r"^\d{1,3}(?:,\d{3})*(?:\.\d+)?$", t)
    )


def infer_trailing_header(data_rows: list[list[str]], existing: list[str]) -> str:
    if not data_rows:
        return "备注"
    lasts = [str(r[-1] or "").strip() for r in data_rows if r]
    if lasts and all(_looks_like_date_cell(v) for v in lasts):
        return "日期"
    if lasts and any(_looks_like_money_cell(v) for v in lasts):
        joined = " ".join(existing)
        if "单价" in joined and "金额" not in joined:
            return "金额"
        if "金额" in joined and "单价" not in joined:
            return "单价"
        if "数量" in joined:
            return "单价"
        return "金额"
    return "备注"


def _drop_redundant_row_index_column(
    hdr_cells: list[str], data_rows: list[list[str]]
) -> tuple[list[str], list[list[str]]]:
    if len(hdr_cells) < 3 or not data_rows:
        return hdr_cells, data_rows
    if hdr_cells[0].strip() not in ("行号", "#", "No", "NO", "no"):
        return hdr_cells, data_rows
    vals = [str(r[0]).strip() if r else "" for r in data_rows]
    if not vals or not all(v.isdigit() for v in vals):
        return hdr_cells, data_rows
    nums = [int(v) for v in vals]
    if nums != list(range(nums[0], nums[0] + len(nums))):
        return hdr_cells, data_rows
    return hdr_cells[1:], [r[1:] for r in data_rows]


def peel_table_caption_and_footer(text: str) -> str:
    """表头误塞标题 → caption 并左移表头；去掉假行号列；末格合计出表。"""
    lines = (text or "").split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        if not lines[i].strip().startswith("|"):
            out.append(lines[i])
            i += 1
            continue
        block: list[str] = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            block.append(lines[i])
            i += 1
        if len(block) < 2:
            out.extend(block)
            continue

        def split_cells(line: str) -> list[str]:
            body = line.strip()
            if body.startswith("|"):
                body = body[1:]
            if body.endswith("|"):
                body = body[:-1]
            return [c.strip() for c in body.split("|")]

        hdr_idx = 0
        sep_idx = -1
        if len(block) >= 2 and _SEP_LINE.match(block[1].strip()):
            sep_idx = 1
            hdr_idx = 0
        elif len(block) >= 3 and _SEP_LINE.match(block[2].strip()):
            hdr_idx = 1
            sep_idx = 2

        hdr_cells = split_cells(block[hdr_idx])
        data_start = sep_idx + 1 if sep_idx >= 0 else 1
        data_rows: list[list[str]] = []
        for r in range(data_start, len(block)):
            if _SEP_LINE.match(block[r].strip()):
                continue
            data_rows.append(split_cells(block[r]))

        footers: list[str] = []
        caption = None
        mutated = False
        if len(hdr_cells) >= 2 and looks_like_title_header(hdr_cells[0]):
            caption = hdr_cells[0]
            n = len(hdr_cells)
            rest = hdr_cells[1:]
            if data_rows and len(data_rows[0]) == n and len(rest) == n - 1:
                rest = rest + [infer_trailing_header(data_rows, rest)]
            hdr_cells = rest
            mutated = True

        before_drop = len(hdr_cells)
        hdr_cells, data_rows = _drop_redundant_row_index_column(hdr_cells, data_rows)
        if len(hdr_cells) != before_drop:
            mutated = True

        for cells in data_rows:
            if len(cells) < 2:
                continue
            kept, prose = peel_summary_cell(cells[-1])
            if prose:
                cells[-1] = kept
                footers.append(prose)
                mutated = True

        # 表外误带「7/22 本月合计…」且末格为 -：把日期填回末格
        for fi, ftext in enumerate(list(footers)):
            fm = re.match(
                r"^(\d{1,2}/\d{1,2}|\d{4}-\d{2}-\d{2})\s+((?:本月合计|合计[：:]).+)$",
                str(ftext),
            )
            if not fm or not data_rows:
                continue
            last_row = data_rows[-1]
            last_cell = str(last_row[-1] or "").strip()
            if last_cell in ("-", ""):
                last_row[-1] = fm.group(1)
                footers[fi] = fm.group(2).strip()
                mutated = True

        if not mutated:
            # 合计已在表外下一行，末格为 -：把日期填回
            j = i
            while j < len(lines) and not lines[j].strip():
                j += 1
            nxt = lines[j].strip() if j < len(lines) else ""
            fm = re.match(
                r"^(\d{1,2}/\d{1,2}|\d{4}-\d{2}-\d{2})\s+((?:本月合计|合计[：:]).+)$",
                nxt,
            )
            if fm and data_rows:
                last_row = data_rows[-1]
                last_cell = str(last_row[-1] or "").strip()
                if last_cell in ("-", ""):
                    last_row[-1] = fm.group(1)
                    footers.append(fm.group(2).strip())
                    mutated = True
                    i = j + 1
            if not mutated:
                out.extend(block)
                continue
        else:
            j = i
            while j < len(lines) and not lines[j].strip():
                j += 1
            nxt = lines[j].strip() if j < len(lines) else ""
            if re.match(
                r"^(?:\d{1,2}/\d{1,2}|\d{4}-\d{2}-\d{2}\s+)?(?:本月合计|合计[：:])",
                nxt,
            ):
                i = j + 1

        sep_cols = max(len(hdr_cells), 2)
        sep = "| " + " | ".join(["---"] * sep_cols) + " |"
        if caption:
            out.extend([f"**{caption}**", ""])
        out.append("| " + " | ".join(hdr_cells) + " |")
        out.append(sep)
        for cells in data_rows:
            row = list(cells)
            while len(row) < len(hdr_cells):
                row.append("-")
            if len(row) > len(hdr_cells):
                head = row[: len(hdr_cells) - 1]
                tail = " ".join(row[len(hdr_cells) - 1 :])
                out.append("| " + " | ".join(head + [tail]) + " |")
            else:
                out.append("| " + " | ".join(row) + " |")
        for f in footers:
            out.extend(["", f])
    return "\n".join(out)


def peel_glued_table_row_prose(text: str) -> str:
    """表行末粘连说明：`| … | 🟢安全 |>所有…` / `| … |**供应结构**：…`"""
    prose_start = re.compile(
        r"^(?:>\s*)?(所有|分析|供应商画像|需要|以上|综上|备注|"
        r"\*\*供应商|\*\*分析|\*\*风险|\*\*供应结构|\*\*风险要点|供应结构|风险要点)"
    )
    out: list[str] = []
    for line in (text or "").split("\n"):
        trimmed = line.strip()
        if not trimmed.startswith("|") or trimmed.count("|") < 2:
            out.append(line)
            continue
        if _SEP_LINE.match(trimmed):
            out.append(line)
            continue
        glued = re.match(r"^((?:\|[^|\n]*)+\|)\s*>(.+)$", trimmed)
        if glued:
            out.extend([glued.group(1), "", glued.group(2).strip()])
            continue
        trail = re.match(
            r"^((?:\|[^|\n]*)+\|)\s*"
            r"((?:你要|你需要|请问|请选择|请确认|确认后|需要我|是否需要|请告诉|若需|如果你|哪一款)[\s\S]{2,})$",
            trimmed,
        )
        if trail:
            out.extend([trail.group(1), "", trail.group(2).strip()])
            continue
        # |cells|- **说明… 粘在最后一格外
        dash_note = re.match(r"^((?:\|[^|\n]*)+\|)\s*(-\s+\*\*.+)$", trimmed)
        if dash_note:
            out.extend([dash_note.group(1), "", dash_note.group(2).lstrip("- ").strip()])
            continue
        body = trimmed[1:] if trimmed.startswith("|") else trimmed
        if body.endswith("|"):
            body = body[:-1]
        cells = [c.strip() for c in body.split("|")]
        if len(cells) >= 2:
            last = cells[-1] or ""
            order_ask = bool(
                re.match(r"^(?:你要|你需要|请问|请选择|请确认|确认后|是否需要|需要我|哪一款)", last)
                or (
                    re.search(r"[？?]$", last)
                    and len(last) >= 6
                    and re.search(r"(?:你要|你需要|哪种|哪一款|确认后|立刻下单|下单|选哪|请确认)", last)
                )
                or (
                    re.search(r"[？?]", last)
                    and len(last) >= 8
                    and re.search(r"(?:下单|物料名称|哪一款|哪种)", last)
                )
            )
            kept, summary_prose = peel_summary_cell(last)
            if (
                order_ask
                or (len(last) > 24 and prose_start.match(last))
                or re.match(r"^\*\*(?:供应商画像|分析|风险|供应结构|风险要点)", last)
                or last.startswith("供应结构")
                or last.startswith("风险要点")
                or summary_prose
            ):
                if summary_prose:
                    cells[-1] = kept
                    out.extend(["|" + "|".join(cells) + "|", "", summary_prose])
                else:
                    cells.pop()
                    out.extend(
                        [
                            "|" + "|".join(cells) + "|",
                            "",
                            re.sub(r"^>\s*", "", last),
                        ]
                    )
                continue
        out.append(line)
    return "\n".join(out)


def dedupe_repeated_sections(text: str) -> str:
    """同一章节号（一、二、…）只保留首次出现，去掉模型重复输出的六/七。"""
    out: list[str] = []
    seen: set[str] = set()
    skipping = False
    section_re = re.compile(r"^(#{1,3})\s+([一二三四五六七八九十]+)、")
    for line in (text or "").split("\n"):
        m = section_re.match(line)
        if m:
            num = m.group(2)
            if num in seen:
                skipping = True
                continue
            seen.add(num)
            skipping = False
        if skipping:
            continue
        out.append(line)
    return "\n".join(out)


def trim_after_download_cta(text: str) -> str:
    """下载询问之后的仪表盘残片（总库存/供应结构等）一律丢弃。"""
    s = text or ""
    m = re.search(r"是否需要将此报告下载[^\n]*", s)
    if not m:
        return s
    end = m.end()
    line = m.group(0)
    line = re.sub(r"[。．]?\s*保存\s*$", "", line)
    return (s[: m.start()] + line).rstrip()


def fix_space_separated_tables(text: str) -> str:
    def _repl(m: re.Match[str]) -> str:
        header, sep, body = m.group(1), m.group(2), m.group(3)
        full = m.group(0)
        # 选型速查 / 行动优先级溢出密文：交给专用修复，禁止建成超宽假表
        if (
            "选型建议" in full
            or "###" in full
            or re.search(r"[🔴🟡🟢🟠]", full)
            or re.search(r"\d+\.\s+\S.+\s+[🔴🟡🟢]", full)
        ):
            return full
        if "。" in header and len(header) > 60:
            return full
        cols = [x for x in sep.strip().split() if re.fullmatch(r"-{3,}", x)]
        if len(cols) < 2:
            return full
        headers = _split_header_cells(header.strip(), len(cols))
        if len(headers) < 2:
            return full
        rows, trailing = _split_space_data_rows(body.strip(), len(cols))
        if not rows:
            return full
        out = _format_gfm(headers, rows)
        if trailing:
            out += "\n\n" + trailing
        return out

    s = re.sub(
        r"([^\n|#][^\n|]{4,}?)\s+((?:-{3,}[ \t]+){2,}-{3,})\s+([^\n]+)",
        _repl,
        text or "",
    )
    return s


def _split_header_cells(header: str, col_count: int) -> list[str]:
    if re.search(r"\s{2,}", header):
        parts = [x.strip() for x in re.split(r"\s{2,}", header) if x.strip()]
        if len(parts) == col_count:
            return parts
    known = (
        r"物料编码|名称|MPN|制造商|规格|采购单价|建议零售价|MOQ|交期\(天\)|效期\(天\)|"
        r"RoHS|无卤|供应商|角色|覆铜板采购额|覆铜板物料数|状态|板多多单价|1688单价|"
        r"价差|降幅|风险等级|主供|替代料|库存|效期|预警"
    )
    parts = re.findall(f"({known})", header)
    if len(parts) >= 2:
        return parts
    ws = header.split()
    if len(ws) == col_count:
        return ws
    return ws if len(ws) >= 2 else []


def _split_space_data_rows(body: str, col_count: int) -> tuple[list[list[str]], str]:
    b = body
    b = re.sub(r"([✅❌])[ \t]*([✅❌])[ \t]*(?=[A-Z0-9\u4e00-\u9fff])", r"\1 \2\n", b)
    b = re.sub(r"(无替代|⚠️注意|⚠️[^\s]*)[ \t]+(?=FR|高TG|CCL|PCB|铝)", r"\1\n", b)
    b = re.sub(r"[ \t]+(?=(?:CCL|PCB|ALPCB|FR4|LOT)-[A-Z0-9])", "\n", b)
    b = re.sub(r"[ \t]+(?=FR4?\d)", "\n", b)
    b = re.sub(r"[ \t]+(?=高TG)", "\n", b)
    b = re.sub(r"([^\n])(>\s*⚠️)", r"\1\n\2", b)
    rows: list[list[str]] = []
    trailing: list[str] = []
    for line in [l.strip() for l in b.split("\n") if l.strip()]:
        if _is_prose_cell(line) or re.match(r"^[>🔴]", line) or re.match(r"^⚠️\s*1688", line):
            trailing.append(line)
            continue
        rows.append(_split_space_row(line, col_count))
    return rows, "\n".join(trailing)


def _split_space_row(line: str, col_count: int) -> list[str]:
    tokens = re.findall(
        r"¥-?[\d,.]+|-?\d+\.\d+%?|-?\d+%|✅|❌|⚠️[^\s]*|N/A|无替代|-|"
        r"[A-Za-z0-9\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff._/\-μ%]*",
        line,
    )
    if len(tokens) == col_count:
        return tokens
    if len(tokens) > col_count:
        first = tokens[: min(2, col_count - 1)]
        last = tokens[-(col_count - len(first)) :]
        middle = tokens[len(first) : len(tokens) - len(last)]
        if len(first) + 1 + len(last) == col_count:
            return first + ([" ".join(middle)] if middle else []) + last
        return tokens[: col_count - 1] + [" ".join(tokens[col_count - 1 :])]
    while len(tokens) < col_count:
        tokens.append("")
    return tokens


def _format_gfm(headers: list[str], rows: list[list[str]]) -> str:
    col = len(headers)
    sep = "|" + "|".join(["---"] * col) + "|"
    h = "|" + "|".join(headers) + "|"
    body = []
    for r in rows:
        cells = list(r) + [""] * col
        body.append("|" + "|".join(cells[:col]) + "|")
    return "\n\n" + "\n".join([h, sep, *body]) + "\n\n"


def fix_markdown_tables(text: str) -> str:
    """安全修复塌缩 GFM 表：不吞掉后文章节。"""
    if not text or "|" not in text:
        return text

    s = _DASH_RE.sub("-", text)
    s = _peel_prose_rows_from_multiline_table(s)

    if _has_healthy_multiline_table(s) and not _has_collapsed_pipe_table(s):
        return s

    out: list[str] = []
    last = 0
    for sep_match in _SEP_RE.finditer(s):
        if sep_match.start() < last:
            continue
        sep_start, sep_end = sep_match.start(), sep_match.end()
        before = s[last:sep_start]
        rest = s[sep_end:]
        body_end = _find_pipe_table_body_end(rest)
        after = rest[:body_end]

        header_start = _find_header_start(before)
        prefix = before[:header_start].rstrip()
        header_raw = before[header_start:]

        if (
            re.search(r"\n\|", header_raw + "\n|" + after[:80])
            and not _is_collapsed_segment(header_raw, after)
        ):
            out.append(s[last : sep_end + body_end])
            last = sep_end + body_end
            continue

        header = _normalize_pipe_row(header_raw)
        col_count = _count_columns(header)
        if col_count < 2:
            out.append(s[last : sep_end + body_end])
            last = sep_end + body_end
            continue

        body = re.sub(
            r"([✅❌])\s*(需要进一步|需要查看|全部来自|全部|供应商统一|以上|综上|所有|4层板有|备注|如果你|若需|🔴|⚠️)",
            r"\1|\2",
            after,
        )
        cells = _extract_cells(body)
        rows, trailing = _build_rows(cells, col_count)
        if not rows:
            out.append(s[last : sep_end + body_end])
            last = sep_end + body_end
            continue

        sep = "|" + "|".join(["---"] * col_count) + "|"
        block_parts: list[str] = []
        if prefix:
            block_parts.extend([prefix, ""])
        block_parts.extend([header, sep, *rows])
        if trailing:
            block_parts.extend(["", trailing])
        # 禁止把 body 之后的全文拼进本段，否则每修一张塌缩表就会把后半篇再复制一遍。
        out.append("\n".join(block_parts))
        last = sep_end + body_end

    if not out:
        return s
    out.append(s[last:])
    return re.sub(r"\n{3,}", "\n\n", "".join(out)).strip()


def _has_healthy_multiline_table(s: str) -> bool:
    return bool(re.search(r"^\|.*\|\s*\n\|[-:\s|]+\|\s*\n\|", s, re.M))


def _has_collapsed_pipe_table(s: str) -> bool:
    if re.search(r"\|(?:[ \t]*:?-{1,}:?[ \t]*\|){2,}[^\n]*\|", s):
        return True
    if re.search(r"\|(?:[ \t]*:?-{1,}:?[ \t]*\|){2,}\s*\|", s):
        return True
    return "\n" not in s and "|---" in s


def _is_collapsed_segment(header_raw: str, after: str) -> bool:
    chunk = header_raw + after
    if "\n" not in chunk:
        return True
    if re.search(r"\|(?:[ \t]*:?-{1,}:?[ \t]*\|){2,}[^\n|]", chunk):
        return True
    return chunk.count("\n") < 2 and chunk.count("|") > 12


def _find_pipe_table_body_end(rest: str) -> int:
    if not rest:
        return 0
    if "\n" not in rest or re.match(r"^[^\n]{0,20}\|", rest):
        m = re.search(
            r"(?:#{1,3}[ \t]|[—-]{1,}#{1,3}|[一二三四五六七八九十]+##|>\s*[⚠️🔴]|🔴\s*风险|关键发现|###\d)",
            rest,
        )
        return m.start() if m and m.start() > 0 else len(rest)

    lines = rest.split("\n")
    i = 1 if lines and "|" in lines[0] else 0
    for i in range(i, len(lines)):
        L = lines[i].strip()
        if not L:
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if nxt and not nxt.startswith("|"):
                return len("\n".join(lines[:i]))
            continue
        if re.match(r"^#{1,6}(\s|$)", L) or re.match(r"^#{1,6}[一二三四五\d]", L):
            return len("\n".join(lines[:i]))
        if L.startswith(">") and not L.startswith("|"):
            return len("\n".join(lines[:i]))
        if re.match(r"^[-—]{3,}$", L) or L.startswith("!["):
            return len("\n".join(lines[:i]))
        if not L.startswith("|") and len(L) > 8 and not re.match(r"^[:\-|]+$", L):
            return len("\n".join(lines[:i]))
    return len(rest)


def _peel_prose_rows_from_multiline_table(text: str) -> str:
    lines = text.split("\n")
    if len(lines) < 3:
        return text
    out: list[str] = []
    peeled: list[str] = []
    in_table = False
    saw_sep = False

    def flush_peeled() -> None:
        nonlocal peeled
        if not peeled:
            return
        out.append("")
        for t in dict.fromkeys(x.strip() for x in peeled if x.strip()):
            out.append(t)
        peeled = []

    for line in lines:
        trimmed = line.strip()
        is_pipe = bool(_PIPE_ROW.match(trimmed))
        is_sep = bool(_SEP_LINE.match(trimmed))
        if is_sep:
            in_table = True
            saw_sep = True
            out.append(line)
            continue
        if in_table and saw_sep and is_pipe:
            cells = _split_row_cells(trimmed)
            if _is_prose_row(cells):
                peeled.append(" ".join(c for c in cells if c))
                continue
            out.append(line)
            continue
        if in_table and saw_sep and not is_pipe:
            flush_peeled()
            in_table = False
            saw_sep = False
        out.append(line)
    flush_peeled()
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


def _split_row_cells(row: str) -> list[str]:
    r = (row or "").strip()
    if r.startswith("|"):
        r = r[1:]
    if r.endswith("|"):
        r = r[:-1]
    return [c.strip() for c in r.split("|")]


def _is_prose_cell(cell: str) -> bool:
    c = (cell or "").strip()
    if not c:
        return False
    bare = re.sub(r"^>+\s*", "", c)
    if c.startswith(">"):
        return True
    if _PROSE_START.match(c) or _PROSE_START.match(bare):
        return True
    if re.search(r"需要查看|可告诉我|均符合\s*RoHS|效期|MSL\s*为|风险提示|持续验证|比板多多便宜", c):
        return True
    if (
        len(c) > 28
        and re.search(r"[，。；]", c)
        and not _NAME_LIKE.match(bare)
        and not _MPN_LIKE.match(bare)
    ):
        return True
    return False


def _is_prose_row(cells: list[str]) -> bool:
    nonempty = [c for c in cells if (c or "").strip()]
    if not nonempty:
        return False
    # 风险/行动等「序号 | 说明」数据行：绝不能当散文剥出
    if len(nonempty) >= 2 and re.match(r"^\d{1,3}$", nonempty[0].strip()):
        return False
    # 对比表 / 下单完整性字段行不是正文
    if re.match(
        r"^(对比项|角色|金额占比|覆盖物料|交期|信用|优势与风险|序号|事项|"
        r"字段|值|状态|物料名称|partId|MPN|供应商|数量|单价|创建人|预计交货日期|备注)$",
        re.sub(r"\*+", "", nonempty[0].strip()),
    ):
        return False
    if _is_prose_cell(nonempty[0]):
        return True
    joined = " ".join(nonempty)
    if re.search(r"需要查看|可告诉我|均符合\s*RoHS|效期180|MSL|风险提示|比板多多便宜", joined):
        has_mpn = any(_MPN_LIKE.match(c) for c in nonempty)
        has_name = any(_NAME_LIKE.match(re.sub(r"^>+\s*", "", c)) for c in nonempty)
        if not has_mpn and not has_name:
            return True
    return False


def _find_header_start(before: str) -> int:
    yi = max(before.rfind("："), before.rfind(":"))
    if yi >= 0:
        p = before.find("|", yi)
        if p >= 0:
            return p
    lines = before.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        if "|" in lines[i] and not re.match(r"^\|[-:\s|]+\|$", lines[i].strip()):
            prefix = "\n".join(lines[:i])
            return len(prefix) + (1 if i > 0 else 0)
    p = before.find("|")
    return p if p >= 0 else 0


def _normalize_pipe_row(row: str) -> str:
    r = re.sub(r"\s*\n\s*", " ", row or "")
    r = re.sub(r"[ \t]+", " ", r).strip()
    r = re.sub(r"\|{2,}", "|", r)
    if not r.startswith("|"):
        p = r.find("|")
        if p > 0:
            r = r[p:]
    if not r.startswith("|"):
        r = "|" + r
    if not r.endswith("|"):
        r = r + "|"
    return r


def _count_columns(header_row: str) -> int:
    return max(0, len(header_row.split("|")) - 2)


def _extract_cells(after: str) -> list[str]:
    s = re.sub(r"\n+", "|", after or "")
    s = re.sub(r"^\|+", "", s)
    parts = [c.strip() for c in s.split("|")]
    while parts and parts[-1] == "":
        parts.pop()
    return parts


def _is_index_start(cell: str, nxt: str) -> bool:
    if not re.fullmatch(r"\d+", (cell or "").strip()):
        return False
    return bool(_NAME_LIKE.match((nxt or "").strip()))


def _find_index_starts(cells: list[str]) -> list[int]:
    return [i for i in range(len(cells) - 1) if _is_index_start(cells[i], cells[i + 1])]


def _align_to_col_count(raw: list[str], col_count: int) -> tuple[list[str], str]:
    cells = [str(c or "").strip() for c in raw if str(c or "").strip() != ""]
    trailing = ""
    while cells and _is_prose_cell(cells[-1]):
        trailing = (cells.pop() + (" " + trailing if trailing else "")).strip()
    if cells and _is_prose_cell(cells[0]):
        trailing = (" ".join(cells) + (" " + trailing if trailing else "")).strip()
        return [], trailing
    if cells:
        last = cells[-1]
        m = re.match(
            r"^([✅❌]*)\s*(需要进一步|需要查看|全部来自|全部|供应商统一|以上|综上|所有|4层板有|备注|如果你|若需|🔴|⚠️)(.*)$",
            last,
        )
        if m and m.group(2):
            cells[-1] = m.group(1) or ""
            if not cells[-1]:
                cells.pop()
            trailing = (m.group(2) + (m.group(3) or "") + (" " + trailing if trailing else "")).strip()
    if len(cells) > col_count:
        cells = cells[: col_count - 2] + cells[-2:]
    while len(cells) < col_count:
        cells.append("")
    return cells[:col_count], trailing


def _build_rows(cells: list[str], col_count: int) -> tuple[list[str], str]:
    rows: list[str] = []
    trailing_parts: list[str] = []
    index_starts = _find_index_starts(cells)

    if len(index_starts) >= 2:
        for s_idx, from_i in enumerate(index_starts):
            to = index_starts[s_idx + 1] if s_idx + 1 < len(index_starts) else len(cells)
            while to > from_i and cells[to - 1] == "":
                to -= 1
            row_cells, trailing = _align_to_col_count(cells[from_i:to], col_count)
            if row_cells and not _is_prose_row(row_cells) and any(row_cells):
                rows.append("|" + "|".join(row_cells) + "|")
            elif trailing or _is_prose_row(row_cells):
                t = trailing or " ".join(c for c in row_cells if c)
                if t:
                    trailing_parts.append(t)
            if trailing:
                trailing_parts.append(trailing)
        last_start = index_starts[-1]
        i, taken = last_start, 0
        while i < len(cells) and taken < col_count:
            if cells[i] != "":
                taken += 1
            i += 1
        while i < len(cells) and cells[i] == "":
            i += 1
        if i < len(cells):
            rest = " ".join(c for c in cells[i:] if c).lstrip("✅❌|").strip()
            if rest:
                trailing_parts.append(rest)
    else:
        i, n = 0, len(cells)
        while i < n:
            while i < n and cells[i] == "":
                i += 1
            if i >= n:
                break
            if _is_prose_cell(cells[i]):
                trailing_parts.append(" ".join(c for c in cells[i:] if c).strip())
                break
            raw: list[str] = []
            while len(raw) < col_count and i < n:
                if raw and _is_prose_cell(cells[i]):
                    break
                raw.append(cells[i])
                i += 1
            row_cells, trailing = _align_to_col_count(raw, col_count)
            if any(row_cells) and not _is_prose_row(row_cells):
                rows.append("|" + "|".join(row_cells) + "|")
            elif _is_prose_row(row_cells):
                trailing_parts.append(" ".join(c for c in row_cells if c))
            if trailing:
                trailing_parts.append(trailing)
        if i < n:
            rest = " ".join(c for c in cells[i:] if c).strip()
            if rest:
                trailing_parts.append(rest)

    uniq = list(dict.fromkeys(t.strip() for t in trailing_parts if t.strip()))
    return rows, "\n".join(uniq)
