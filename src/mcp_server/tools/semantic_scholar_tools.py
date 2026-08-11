"""
Semantic Scholar 工具集 —— 纯文本摘要最干净（兜底摘要源）+ 跨领域检索。

免费、无需 Key（共享池，429 较多，重试退避已在 unified.fetch_json）。
端点：GET https://api.semanticscholar.org/graph/v1/paper/search
"""

from __future__ import annotations

from typing import Any

from mcp_server.tools.unified import (
    S2_BASE,
    S2_API_KEY,
    Paper,
    fetch_json,
    cache_get,
    cache_set,
)

_S2_FIELDS = (
    "title,authors,abstract,year,venue,citationCount,"
    "externalIds,openAccessPdf,publicationVenue,influentialCitationCount"
)


def _parse_s2_paper(p: dict[str, Any]) -> Paper:
    authors: list[str] = []
    for a in (p.get("authors") or []):
        nm = a.get("name") or ""
        if nm:
            authors.append(nm)
    ext = p.get("externalIds") or {}
    doi = (ext.get("DOI") or "").strip()
    pv = p.get("publicationVenue") or {}
    venue = pv.get("name") or p.get("venue") or ""
    oa = p.get("openAccessPdf") or {}
    oa_url = oa.get("url") or ""
    return Paper(
        title=(p.get("title") or "").strip(),
        authors=authors,
        year=p.get("year"),
        venue=venue,
        cited_by_count=p.get("citationCount"),
        doi=doi,
        doi_url=(f"https://doi.org/{doi}" if doi else ""),
        abstract=p.get("abstract") or "",
        oa_url=oa_url,
        source="s2",
    )


async def s2_search(
    query: str,
    limit: int = 10,
    year_from: int | None = None,
    year_to: int | None = None,
    pub_type: str | None = None,
    oa_only: bool = False,
) -> list[Paper]:
    limit = max(1, min(int(limit or 10), 40))
    cache_key = f"s2_search:{query}:{limit}:{year_from}:{year_to}:{pub_type}:{oa_only}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    params: dict[str, Any] = {
        "query": query,
        "limit": limit,
        "fields": _S2_FIELDS,
    }
    if year_from and year_to:
        params["year"] = f"{year_from}-{year_to}"
    elif year_from:
        params["year"] = f"{year_from}-"
    elif year_to:
        params["year"] = f"-{year_to}"
    if pub_type:
        # S2 publicationTypes 过滤
        params["publicationTypes"] = pub_type
    if oa_only:
        params["openAccessPdf"] = ""
    headers: dict[str, str] = {}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY
    data = await fetch_json(f"{S2_BASE}/paper/search", params=params, headers=headers, source="s2")
    if not data:
        return []
    papers = [_parse_s2_paper(p) for p in (data.get("data") or [])]
    papers = [p for p in papers if p.title or p.doi]
    cache_set(cache_key, papers)
    return papers


async def s2_cross_search(domain_a: str, domain_b: str, limit: int = 8) -> list[Paper]:
    """跨领域交叉检索：找两个领域已有的交叉工作（真实文献佐证）。"""
    limit = max(1, min(int(limit or 8), 20))
    query = f"{domain_a} {domain_b}"
    cache_key = f"s2_cross:{query}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    params = {"query": query, "limit": limit, "fields": _S2_FIELDS}
    headers: dict[str, str] = {}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY
    data = await fetch_json(f"{S2_BASE}/paper/search", params=params, headers=headers, source="s2")
    if not data:
        return []
    papers = [_parse_s2_paper(p) for p in (data.get("data") or [])]
    papers = [p for p in papers if p.title or p.doi]
    cache_set(cache_key, papers)
    return papers
