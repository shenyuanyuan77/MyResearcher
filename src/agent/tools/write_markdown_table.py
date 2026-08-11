"""通用写表工具：任意表头/行 → 合法 GFM，禁止模型手写管道表。"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.tools import tool

from api_view.report_table_canon import render_gfm_table

# 表头里误塞的标题（应作 caption）——通用，领域无关
_TITLE_IN_HEADER = re.compile(
    r"(明细|汇总|一览|清单|概览).{0,12}(共\s*\d+|：|:)"
    r"|共\s*\d+\s*(条|篇|项|个)"
)
# 单元格里误塞的合计/说明（应出表）——通用，领域无关
_SUMMARY_IN_CELL = re.compile(
    r"(?:合计[：:]|总计[：:]|结论[：:]|总结[：:]|"
    r"均无[「\"']?已删除|共\s*\d+\s*(条|篇|项|个)|"
    r"注[：:]|备注[：:]|说明[：:]|请原样采用)"
)
# 日期可紧贴说明（允许 7/22本月合计 / 7 / 22 本月合计）
_DATE_THEN_PROSE = re.compile(
    r"^(\d{1,2}\s*/\s*\d{1,2}|\d{4}-\d{2}-\d{2})\s*(.+)$"
)
# 金额后误粘表外说明（¥480.00 按供应商…）
_MONEY_THEN_PROSE = re.compile(r"^([¥￥]\s*[\d,]+(?:\.\d+)?)\s+(.+)$")


def _normalize_date_token(raw: str) -> str:
    return re.sub(r"\s*", "", (raw or "").strip())


def _parse_list(value: Any, *, name: str) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{name} 必须是 JSON 数组，解析失败: {exc}") from exc
    if not isinstance(value, list):
        raise ValueError(f"{name} 必须是数组，当前类型: {type(value).__name__}")
    return value


def _normalize_rows(rows: list) -> list[list[object]]:
    out: list[list[object]] = []
    for i, row in enumerate(rows):
        if isinstance(row, dict):
            raise ValueError(
                f"rows[{i}] 不能是对象；请传二维数组，例如 [[\"a\",\"b\"],[\"c\",\"d\"]]"
            )
        if not isinstance(row, (list, tuple)):
            raise ValueError(f"rows[{i}] 必须是数组，当前类型: {type(row).__name__}")
        out.append(list(row))
    return out


def looks_like_title_header(cell: object) -> bool:
    s = str(cell or "").strip()
    if len(s) < 10:
        return False
    if _TITLE_IN_HEADER.search(s):
        return True
    if len(s) >= 16 and ("：" in s or "共" in s):
        return True
    return False


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
    return "¥" in t or "￥" in t or bool(re.search(r"^\d{1,3}(?:,\d{3})*(?:\.\d+)?$", t))


def infer_trailing_header(rows: list[list[object]], existing: list[str]) -> str:
    """标题占了首列后，末列名常被挤掉；按末列内容推断。"""
    if not rows:
        return "备注"
    lasts = [str(r[-1] or "").strip() for r in rows if r]
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


def drop_redundant_row_index_column(
    headers: list[str],
    rows: list[list[object]],
) -> tuple[list[str], list[list[object]]]:
    """去掉误加的「行号」列（1,2,3… 且下一列头已是序号/订单等）。"""
    if len(headers) < 3 or not rows:
        return headers, rows
    if headers[0].strip() not in ("行号", "#", "No", "NO", "no"):
        return headers, rows
    vals = [str(r[0]).strip() if r else "" for r in rows]
    if not vals or not all(v.isdigit() for v in vals):
        return headers, rows
    nums = [int(v) for v in vals]
    if nums != list(range(nums[0], nums[0] + len(nums))):
        return headers, rows
    return headers[1:], [r[1:] for r in rows]


def unshift_title_header(
    headers: list[str],
    rows: list[list[object]],
    caption: str,
) -> tuple[list[str], list[list[object]], str]:
    """标题误作首列表头 → caption，表头整体左移一格并补末列名（避免错位+假行号）。"""
    if not headers or not looks_like_title_header(headers[0]):
        return headers, rows, caption
    cap = caption or headers[0].strip()
    n = len(headers)
    rest = [str(h) for h in headers[1:]]
    if rows and len(rows[0]) == n and len(rest) == n - 1:
        rest = rest + [infer_trailing_header(rows, rest)]
    elif len(rest) < 2:
        # 退化：无法左移时用短列名占首列，绝不造「行号」宽列语义
        rest = ["序号"] + rest
        while rows and len(rest) < len(rows[0]):
            rest.append(infer_trailing_header(rows, rest))
    return rest, rows, cap


def sanitize_table_payload(
    headers: list[str],
    rows: list[list[object]],
    caption: str = "",
) -> tuple[list[str], list[list[object]], str, list[str]]:
    """标题→caption，合计→表后；修正标题占位导致的表头错位。"""
    hdrs = [str(h) for h in headers]
    raw_rows = [list(r) for r in rows]
    cap = " ".join((caption or "").split()).strip()
    footers: list[str] = []

    hdrs, raw_rows, cap = unshift_title_header(hdrs, raw_rows, cap)
    hdrs, raw_rows = drop_redundant_row_index_column(hdrs, raw_rows)

    for row in raw_rows:
        if not row:
            continue
        kept, prose = peel_summary_cell(str(row[-1] or ""))
        if prose:
            row[-1] = kept
            footers.append(prose)

    # 表外误带日期且末格为 -：日期回填（通用，领域无关）
    for i, ftext in enumerate(list(footers)):
        fm = re.match(
            r"^(\d{1,2}/\d{1,2}|\d{4}-\d{2}-\d{2})\s+((?:合计[：:]|总计[：:]).+)$",
            str(ftext),
        )
        if not fm or not raw_rows:
            continue
        last_cell = str(raw_rows[-1][-1] or "").strip()
        if last_cell in ("-", ""):
            raw_rows[-1][-1] = fm.group(1)
            footers[i] = fm.group(2).strip()

    return hdrs, raw_rows, cap, footers


def build_markdown_table(
    headers: Any,
    rows: Any,
    caption: str = "",
) -> str:
    """纯函数：供工具与单测共用。成功返回 Markdown；失败返回 error JSON。"""
    try:
        hdrs = [str(h) for h in _parse_list(headers, name="headers")]
        raw_rows = _normalize_rows(_parse_list(rows, name="rows"))
        if len(hdrs) < 2:
            raise ValueError("headers 至少需要 2 列")
        hdrs, raw_rows, cap, footers = sanitize_table_payload(hdrs, raw_rows, caption)
        md = render_gfm_table(hdrs, raw_rows)
        parts: list[str] = []
        if cap:
            parts.append(f"**{cap}**")
            parts.append("")
        parts.append(md)
        for f in footers:
            parts.append("")
            parts.append(f)
        return "\n".join(parts)
    except Exception as exc:  # noqa: BLE001 — 工具侧永不抛崩 agent
        return json.dumps(
            {"ok": False, "error": str(exc)},
            ensure_ascii=False,
        )


@tool
def write_markdown_table(
    headers: list[str],
    rows: list[list[str]],
    caption: str = "",
) -> str:
    """生成可直接粘贴进回复的 Markdown 表格（任意列、任意含义）。

    **任何对用户可见的表格都必须先调用本工具**，把返回原文贴进回复。
    禁止手写 `| ... |` 管道表（易错列、竖切、把合计塞进末格）。

    Args:
        headers: 表头列名数组，至少 2 列。例：["标题","作者","年份","被引","DOI"]。
                 **不要**把「文献检索结果一览：共N篇」放进 headers，用 caption。
        rows: 二维数组，每行与表头列数一致。
              **不要**把「合计…/结论…」写进单元格；工具会剥到表后。
        caption: 表前标题（加粗一行）。合计/说明写表后，勿塞进表头或末格。

    Returns:
        合法 GFM Markdown 字符串；参数非法时返回 JSON：{"ok":false,"error":"..."}
    """
    return build_markdown_table(headers, rows, caption=caption or "")
