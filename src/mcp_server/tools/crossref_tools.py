"""
CrossRef 工具集 —— 全球 DOI 注册机构，DOI 最权威可信（主 DOI 源）。

免费、无需 Key；加 mailto 走礼貌池（提升速率上限）。
端点：GET https://api.crossref.org/works
"""

from __future__ import annotations

from typing import Any

from mcp_server.tools.unified import (
    ACADEMIC_MAILTO,
    CROSSREF_BASE,
    Paper,
    fetch_json,
    cache_get,
    cache_set,
)


def _parse_crossref_item(item: dict[str, Any]) -> Paper:
    """把 CrossRef 单条 work 解析成统一 Paper。"""
    # 作者
    authors: list[str] = []
    raw_authors: list[dict[str, str]] = []
    for a in item.get("author", []) or []:
        given = (a.get("given") or "").strip()
        family = (a.get("family") or "").strip()
        name = f"{given} {family}".strip() or a.get("name") or ""
        if name:
            authors.append(name)
        if family or given:
            raw_authors.append({"family": family, "given": given})
    # 年份
    year = None
    issued = item.get("issued") or {}
    dp = issued.get("date-parts") or []
    if dp and dp[0] and dp[0][0]:
        try:
            year = int(dp[0][0])
        except (ValueError, TypeError):
            year = None
    # 标题（数组）
    titles = item.get("title") or []
    title = titles[0] if titles else ""
    # 期刊/会议
    venues = item.get("container-title") or []
    venue = venues[0] if venues else (item.get("publisher") or "")
    doi = (item.get("DOI") or "").strip()
    cited = item.get("is-referenced-by-count")
    abstract = item.get("abstract") or ""
    # CrossRef 摘要为 JATS XML，粗去标签
    if abstract and "<" in abstract:
        import re

        abstract = re.sub(r"<[^>]+>", " ", abstract)
        abstract = re.sub(r"\s+", " ", abstract).strip()
    # 文献类型映射（CrossRef type → 统一 pub_type）
    cr_type = (item.get("type") or "").lower()
    pub_type = _map_crossref_type(cr_type)
    return Paper(
        title=title.strip(),
        authors=authors,
        year=year,
        venue=venue.strip(),
        cited_by_count=cited if isinstance(cited, int) else None,
        doi=doi,
        doi_url=(f"https://doi.org/{doi}" if doi else ""),
        abstract=abstract,
        source="crossref",
        pub_type=pub_type,
        publisher=(item.get("publisher") or "").strip(),
        volume=str(item.get("volume") or "").strip(),
        issue=str(item.get("issue") or "").strip(),
        page=str(item.get("page") or "").strip(),
        raw_authors=raw_authors,
    )


def _map_crossref_type(cr_type: str) -> str:
    """CrossRef type → 统一 pub_type。"""
    if not cr_type:
        return "article"
    if "journal-article" in cr_type or "article" in cr_type:
        return "article"
    if "proceedings" in cr_type or "conference" in cr_type or "paper" in cr_type:
        return "conference"
    if "preprint" in cr_type or "posted-content" in cr_type:
        return "preprint"
    if "book" in cr_type and "chapter" not in cr_type:
        return "book"
    if "chapter" in cr_type:
        return "chapter"
    if "dissertation" in cr_type or "thesis" in cr_type:
        return "thesis"
    return "other"


async def crossref_search(
    query: str,
    rows: int = 10,
    year_from: int | None = None,
    sort: str = "relevance",
) -> list[Paper]:
    """CrossRef 关键词检索，返回真实 DOI 文献列表。"""
    rows = max(1, min(int(rows or 10), 40))
    cache_key = f"cr_search:{query}:{rows}:{year_from}:{sort}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    params: dict[str, Any] = {
        "query": query,
        "rows": rows,
        "select": "DOI,title,author,container-title,issued,is-referenced-by-count,abstract,publisher,type,volume,issue,page,URL",
        "mailto": ACADEMIC_MAILTO,
        "sort": sort,
    }
    filters: list[str] = []
    if year_from:
        filters.append(f"from-pub-date:{year_from}-01-01")
    if filters:
        params["filter"] = ",".join(filters)

    data = await fetch_json(f"{CROSSREF_BASE}/works", params=params)
    if not data:
        return []
    items = (((data.get("message") or {}).get("items")) or [])
    papers = [_parse_crossref_item(it) for it in items]
    papers = [p for p in papers if p.title or p.doi]
    cache_set(cache_key, papers)
    return papers


async def crossref_by_doi(doi: str) -> Paper | None:
    """按裸 DOI 精确取一条（DOI 权威校验）。"""
    doi = doi.strip()
    if doi.startswith("http"):
        # 兼容 https://doi.org/10.xxx
        doi = doi.split("doi.org/", 1)[-1]
    cache_key = f"cr_doi:{doi}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    data = await fetch_json(
        f"{CROSSREF_BASE}/works/{doi}", params={"mailto": ACADEMIC_MAILTO}
    )
    if not data:
        return None
    item = (data.get("message") or {})
    if not item:
        return None
    paper = _parse_crossref_item(item)
    cache_set(cache_key, paper)
    return paper
