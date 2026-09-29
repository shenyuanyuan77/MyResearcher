"""
MyResearcher · 学术引用格式化器。

支持三种学术引用格式：
  - GB/T 7714-2015（中国国标，默认）
  - APA（第 7 版）
  - IEEE

输入：Paper 对象（unified.Paper）；输出：单条引用字符串 / 编号参考文献列表 markdown。

规则参考：
  - GB/T 7714-2015《信息与文献 参考文献著录规则》
  - APA Publication Manual 7th edition
  - IEEE Citation Reference

注意：纯 Python 自实现，字段来自 Paper（需 pub_type/raw_authors/volume/issue/page）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_server.tools.unified import Paper

# 文献类型标识（GB/T 7714 用）
_GBT_TYPE_MARK = {
    "article": "[J]",
    "conference": "[C]",
    "book": "[M]",
    "chapter": "[M]",
    "preprint": "[EB/OL]",
    "thesis": "[D]",
    "other": "[J]",
}


def _join_authors_gbt(raw_authors: list[dict[str, str]], authors: list[str]) -> str:
    """GB/T 7714 作者：姓全大写, 名取首字母; 3 人内全列, 超过用 '等'。"""
    if not raw_authors and not authors:
        return ""
    formatted: list[str] = []
    for ra in (raw_authors or []):
        family = (ra.get("family") or "").strip()
        given = (ra.get("given") or "").strip()
        if not family:
            continue
        # 名取首字母（英文场景）；中文姓名原样
        if given and all(c.isascii() for c in given):
            initials = " ".join(f"{g[0].upper()}" for g in given.split() if g)
            formatted.append(f"{family.upper()} {initials}")
        else:
            formatted.append(family if not given else f"{family}{given}")
    # 若 raw_authors 缺失，退回 authors 全名
    if not formatted and authors:
        formatted = list(authors[:3])
    if len(formatted) > 3:
        return ", ".join(formatted[:3]) + ", 等"
    return ", ".join(formatted)


def _join_authors_apa(raw_authors: list[dict[str, str]], authors: list[str]) -> tuple[list[str], bool]:
    """APA：Family, I. I.。返回 (格式化作者列表, 是否超过3人)。"""
    formatted: list[str] = []
    for ra in (raw_authors or []):
        family = (ra.get("family") or "").strip()
        given = (ra.get("given") or "").strip()
        if not family and not given:
            continue
        if given and all(c.isascii() for c in given):
            initials = "".join(f"{g[0].upper()}." for g in given.split() if g)
            formatted.append(f"{family}, {initials}")
        elif family and given:
            formatted.append(f"{family}, {given}")
        else:
            formatted.append(family or given)
    if not formatted and authors:
        formatted = list(authors)
    over = len(formatted) > 3
    return formatted, over


def _join_authors_ieee(raw_authors: list[dict[str, str]], authors: list[str]) -> str:
    """IEEE：I. I. Family; 6 人内全列, 超过用 'et al.'。"""
    formatted: list[str] = []
    for ra in (raw_authors or []):
        family = (ra.get("family") or "").strip()
        given = (ra.get("given") or "").strip()
        if not family and not given:
            continue
        if given and all(c.isascii() for c in given):
            initials = " ".join(f"{g[0].upper()}." for g in given.split() if g)
            formatted.append(f"{initials} {family}")
        elif family and given:
            formatted.append(f"{given} {family}")
        else:
            formatted.append(family or given)
    if not formatted and authors:
        formatted = list(authors)
    if len(formatted) > 6:
        return ", ".join(formatted[:6]) + ", et al."
    return ", ".join(formatted)


def format_paper_gbt7714(paper: "Paper", idx: int | None = None) -> str:
    """GB/T 7714-2015 格式。

    期刊文章：作者. 标题[J]. 期刊, 年, 卷(期): 页. DOI:xxx
    会议论文：作者. 标题[C]. 会议名, 年: 页. DOI:xxx
    预印本：  作者. 标题[EB/OL]. (年). DOI:xxx
    """
    ptype = paper.pub_type or "article"
    type_mark = _GBT_TYPE_MARK.get(ptype, "[J]")
    authors = _join_authors_gbt(paper.raw_authors, paper.authors)
    title = paper.title or "（无标题）"
    parts: list[str] = []
    prefix = f"[{idx}] " if idx is not None else ""
    head = f"{prefix}{authors}. {title}{type_mark}." if authors else f"{prefix}{title}{type_mark}."
    parts.append(head)
    # 出版项
    venue = paper.venue.strip()
    year = paper.year or ""
    vol_issue = ""
    if paper.volume:
        vol_issue = paper.volume
        if paper.issue:
            vol_issue += f"({paper.issue})"
    pages = paper.page.strip()

    if ptype == "article":
        seg = " ".join(filter(None, [venue, (f"{year}" if year else ""), (f"{vol_issue}" if vol_issue else ""), (f": {pages}" if pages else "")]))
        # 格式：期刊, 年, 卷(期): 页
        pub = ", ".join(filter(None, [venue, (str(year) if year else ""), vol_issue, pages]))
        parts.append(pub + "." if pub else "")
    elif ptype == "conference":
        pub = ", ".join(filter(None, [venue, (str(year) if year else ""), pages]))
        parts.append(pub + "." if pub else "")
    elif ptype == "preprint":
        parts.append(f"({year})." if year else "")
    elif ptype in ("book", "chapter"):
        pub = ". ".join(filter(None, [venue or paper.publisher, (str(year) if year else ""), vol_issue, pages]))
        parts.append(pub + "." if pub else "")
    else:
        pub = ", ".join(filter(None, [venue, (str(year) if year else ""), vol_issue, pages]))
        parts.append(pub + "." if pub else "")
    # DOI
    if paper.doi:
        parts.append(f"DOI: {paper.doi}.")
    # 拼接（去掉空段）
    body = " ".join(x for x in parts if x)
    return body


def format_paper_apa(paper: "Paper", idx: int | None = None) -> str:
    """APA 第 7 版格式。

    期刊：Author, A. A., & Author, B. B. (Year). Title. Journal Name, vol(issue), pages. https://doi.org/xxx
    """
    authors_list, over = _join_authors_apa(paper.raw_authors, paper.authors)
    # APA-7：<=20 位作者全部列出，最后一位用 & 连接；>20 才用 前19 + ... + 最后一位。
    # 学术场景作者通常 <20，这里直接全列 + 最后一位 & 连接。
    if len(authors_list) > 20:
        authors = ", ".join(authors_list[:19]) + ", … " + authors_list[-1]
    elif len(authors_list) > 1:
        authors = ", ".join(authors_list[:-1]) + ", & " + authors_list[-1]
    elif authors_list:
        authors = authors_list[0]
    else:
        authors = ""
    title = paper.title or "（无标题）"
    year = f"({paper.year})" if paper.year else "(n.d.)"
    venue = paper.venue.strip()
    vol_issue = ""
    if paper.volume:
        vol_issue = paper.volume
        if paper.issue:
            vol_issue += f"({paper.issue})"
    pages = paper.page.strip()
    prefix = f"[{idx}] " if idx is not None else ""

    seg_parts: list[str] = []
    if authors:
        seg_parts.append(authors)
    seg_parts.append(f"{year}.")
    seg_parts.append(f"{title}.")
    if venue:
        venue_seg = f"*{venue}*"
        if vol_issue:
            venue_seg += f", {vol_issue}"
        if pages:
            venue_seg += f", {pages}"
        seg_parts.append(venue_seg + ".")
    if paper.doi_url:
        seg_parts.append(paper.doi_url)
    return prefix + " ".join(seg_parts)


def format_paper_ieee(paper: "Paper", idx: int | None = None) -> str:
    """IEEE 格式。

    [idx] A. Author and B. Author, "Title," Journal Name, vol. x, no. y, pp. a-b, Year. doi:xxx
    """
    authors = _join_authors_ieee(paper.raw_authors, paper.authors)
    # IEEE 多作者用 "and" 连接最后一位
    if authors and ", " in authors:
        idx_and = authors.rfind(", ")
        if idx_and > -1:
            authors = authors[:idx_and] + " and" + authors[idx_and + 1 :]
    title = paper.title or "（无标题）"
    venue = paper.venue.strip()
    year = str(paper.year) if paper.year else ""
    parts: list[str] = []
    if idx is not None:
        parts.append(f"[{idx}]")
    if authors:
        parts.append(authors)
    parts.append(f'"{title},"')
    pub_bits: list[str] = []
    if venue:
        pub_bits.append(f"*{venue}*")
    if paper.volume:
        pub_bits.append(f"vol. {paper.volume}")
    if paper.issue:
        pub_bits.append(f"no. {paper.issue}")
    if paper.page:
        pub_bits.append(f"pp. {paper.page}")
    if year:
        pub_bits.append(year)
    if pub_bits:
        parts.append(", ".join(pub_bits) + ".")
    if paper.doi:
        parts.append(f"doi: {paper.doi}")
    return " ".join(parts)


def papers_to_references(papers: list["Paper"], style: str = "gbt7714") -> str:
    """生成编号参考文献列表 markdown（## 参考文献 + [1] ... [2] ...），每条带可点 DOI。"""
    if not papers:
        return ""
    fn = _FORMATTERS.get((style or "").lower(), format_paper_gbt7714)
    lines = ["## 参考文献", ""]
    for i, p in enumerate(papers, 1):
        entry = fn(p, idx=i)
        # 确保含可点 DOI（若格式化未带 doi_url，补一个）
        if p.doi_url and p.doi_url not in entry and p.doi and f"doi.org/{p.doi}" not in entry:
            entry += f" {p.doi_url}"
        lines.append(entry)
    return "\n".join(lines)


def style_label(style: str) -> str:
    return {
        "gbt7714": "GB/T 7714-2015",
        "apa": "APA 第7版",
        "ieee": "IEEE",
        "chicago": "Chicago（注释-书目）",
        "vancouver": "Vancouver",
        "mla": "MLA 第9版",
    }.get((style or "").lower(), "GB/T 7714-2015")


# ============================================================
# Chicago（注释与书目风格，第17版）样式的参考文献表
# ============================================================


def format_paper_chicago(paper: "Paper", idx: int | None = None) -> str:
    """Chicago 参考文献表格式。

    期刊：Author Last, First. Year. "Title." *Journal Name* vol, no. (year): pages.
    会议：Author Last, First. Year. "Title." In *Conference*, pages. Publisher.
    """
    authors = _join_authors_chicago(paper.raw_authors, paper.authors)
    title = paper.title or "（无标题）"
    year = str(paper.year) if paper.year else "n.d."
    venue = paper.venue.strip()
    prefix = f"[{idx}] " if idx is not None else ""
    parts: list[str] = []
    if authors:
        parts.append(authors + ".")
    parts.append(f"{year}.")
    parts.append(f'"{title}."')
    pub_bits: list[str] = []
    if venue:
        pub_bits.append(f"*{venue}*")
    if paper.volume:
        vol_str = paper.volume
        if paper.issue:
            vol_str += f", no. {paper.issue}"
        pub_bits.append(vol_str)
    if paper.page:
        pub_bits.append(f": {paper.page}")
    if pub_bits:
        parts.append(" ".join(pub_bits) + ".")
    if paper.doi:
        parts.append(f"https://doi.org/{paper.doi}.")
    return prefix + " ".join(parts)


def _join_authors_chicago(raw_authors: list[dict[str, str]], authors: list[str]) -> str:
    """Chicago：Last, First（首位）; First Last（后续）; 10 人以上用 et al.。"""
    formatted: list[str] = []
    for ra in (raw_authors or []):
        family = (ra.get("family") or "").strip()
        given = (ra.get("given") or "").strip()
        if not family and not given:
            continue
        if given and family:
            formatted.append(f"{family}, {given}")
        else:
            formatted.append(family or given)
    if not formatted and authors:
        formatted = list(authors)
    if len(formatted) > 10:
        return f"{formatted[0]} et al."
    if len(formatted) > 1:
        # 首位 "Last, First"，后续 "First Last"
        first = formatted[0]
        rest = []
        for ra in (raw_authors or [])[1:10]:
            family = (ra.get("family") or "").strip()
            given = (ra.get("given") or "").strip()
            if given and family:
                rest.append(f"{given} {family}")
            elif family or given:
                rest.append(family or given)
        if not rest and len(authors) > 1:
            rest = list(authors[1:10])
        return first + " and " + ", ".join(rest) if len(rest) == 1 else first + ", " + ", ".join(rest)
    return formatted[0] if formatted else ""


# ============================================================
# Vancouver（生物医学常用，ICMJE）
# ============================================================


def format_paper_vancouver(paper: "Paper", idx: int | None = None) -> str:
    """Vancouver 格式（ICMJE）。

    期刊：Author AA, Author BB. Title. Journal Name. Year;vol(issue):pages.
    """
    authors = _join_authors_vancouver(paper.raw_authors, paper.authors)
    title = paper.title or "（无标题）"
    venue = paper.venue.strip()
    year = str(paper.year) if paper.year else ""
    prefix = f"[{idx}] " if idx is not None else ""
    parts: list[str] = []
    if authors:
        parts.append(authors + ".")
    parts.append(f"{title}.")
    pub_bits: list[str] = []
    if venue:
        pub_bits.append(venue + ".")
    vol_str = ""
    if paper.volume:
        vol_str = paper.volume
        if paper.issue:
            vol_str += f"({paper.issue})"
    if year:
        vol_str = (year + ";" + vol_str) if vol_str else year
    if vol_str:
        pub_bits.append(vol_str + ":")
    if paper.page:
        pub_bits.append(paper.page + ".")
    if pub_bits:
        parts.append(" ".join(pub_bits))
    if paper.doi:
        parts.append(f"https://doi.org/{paper.doi}.")
    return prefix + " ".join(parts)


def _join_authors_vancouver(raw_authors: list[dict[str, str]], authors: list[str]) -> str:
    """Vancouver：Family Initials（无空格/无句点）; 6 人以上 et al。"""
    formatted: list[str] = []
    for ra in (raw_authors or []):
        family = (ra.get("family") or "").strip()
        given = (ra.get("given") or "").strip()
        if not family:
            continue
        if given and all(c.isascii() for c in given):
            initials = "".join(f"{g[0].upper()}" for g in given.split() if g)
            formatted.append(f"{family} {initials}")
        else:
            formatted.append(family if not given else f"{family}{given}")
    if not formatted and authors:
        formatted = list(authors)
    if len(formatted) > 6:
        return ", ".join(formatted[:6]) + ", et al"
    return ", ".join(formatted)


# ============================================================
# MLA（第9版）Works Cited
# ============================================================


def format_paper_mla(paper: "Paper", idx: int | None = None) -> str:
    """MLA 第9版 Works Cited 格式。

    期刊：Author Last, First. "Title." *Journal Name*, vol., no., Year, pp.
    """
    authors = _join_authors_mla(paper.raw_authors, paper.authors)
    title = paper.title or "（无标题）"
    venue = paper.venue.strip()
    year = str(paper.year) if paper.year else ""
    prefix = f"[{idx}] " if idx is not None else ""
    parts: list[str] = []
    if authors:
        parts.append(authors + ".")
    parts.append(f'"{title}."')
    pub_bits: list[str] = []
    if venue:
        pub_bits.append(f"*{venue}*,")
    if paper.volume:
        vol_str = f"vol. {paper.volume}"
        if paper.issue:
            vol_str += f", no. {paper.issue}"
        pub_bits.append(vol_str + ",")
    if year:
        pub_bits.append(year + ",")
    if paper.page:
        pub_bits.append(f"pp. {paper.page}.")
    if pub_bits:
        parts.append(" ".join(pub_bits))
    if paper.doi:
        parts.append(f"https://doi.org/{paper.doi}.")
    return prefix + " ".join(parts)


def _join_authors_mla(raw_authors: list[dict[str, str]], authors: list[str]) -> str:
    """MLA：Last, First（首位）; First Last（后续）; 3+ 用 et al。"""
    formatted: list[str] = []
    for ra in (raw_authors or []):
        family = (ra.get("family") or "").strip()
        given = (ra.get("given") or "").strip()
        if not family and not given:
            continue
        if given and family:
            formatted.append({"family": family, "given": given})
        else:
            formatted.append({"family": family or given, "given": ""})
    if not formatted and authors:
        # 退回全名
        if len(authors) >= 3:
            return authors[0] + ", et al"
        return ", ".join(authors)
    if len(formatted) >= 3:
        first = formatted[0]
        return f"{first['family']}, {first['given']}" + ", et al"
    out: list[str] = []
    for i, a in enumerate(formatted):
        if i == 0:
            out.append(f"{a['family']}, {a['given']}" if a['given'] else a['family'])
        else:
            out.append(f"{a['given']} {a['family']}" if a['given'] else a['family'])
    return ", ".join(out)


_FORMATTERS = {
    "gbt7714": format_paper_gbt7714,
    "apa": format_paper_apa,
    "ieee": format_paper_ieee,
    "chicago": format_paper_chicago,
    "vancouver": format_paper_vancouver,
    "mla": format_paper_mla,
}


def format_paper(paper: "Paper", style: str = "gbt7714", idx: int | None = None) -> str:
    """按指定风格格式化单篇。style ∈ gbt7714/apa/ieee/chicago/vancouver/mla。"""
    fn = _FORMATTERS.get((style or "").lower(), format_paper_gbt7714)
    return fn(paper, idx=idx)


def supported_styles() -> list[str]:
    """返回支持的引用格式列表。"""
    return list(_FORMATTERS.keys())
