"""
OpenAlex 工具集 —— 富数据补全 + 作者画像 + 主题热度。

免费、无需 Key（共享池）；mailto 进礼貌池。
端点：GET https://api.openalex.org/works | /authors
"""

from __future__ import annotations

from typing import Any

from mcp_server.tools.unified import (
    ACADEMIC_MAILTO,
    OPENALEX_BASE,
    Paper,
    fetch_json,
    rebuild_abstract_from_inverted_index,
    cache_get,
    cache_set,
)


_WORK_SELECT = (
    "id,doi,title,authorships,publication_year,cited_by_count,"
    "primary_location,abstract_inverted_index,type,open_access,biblio"
)


def _parse_openalex_work(w: dict[str, Any]) -> Paper:
    authors: list[str] = []
    raw_authors: list[dict[str, str]] = []
    for au in w.get("authorships") or []:
        a = au.get("author") or {}
        name = a.get("display_name") or au.get("raw_author_name") or ""
        if name:
            authors.append(name)
        # OpenAlex 无 family/given 拆分，用 raw_author_name 或 display_name 反推
        raw_name = au.get("raw_author_name") or name
        if raw_name:
            parts = raw_name.rsplit(" ", 1)
            if len(parts) == 2:
                raw_authors.append({"given": parts[0], "family": parts[1]})
            else:
                raw_authors.append({"given": "", "family": raw_name})
    doi = (w.get("doi") or "")
    if doi and doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/") :]
    loc = w.get("primary_location") or {}
    source = (loc.get("source") or {}) if loc else {}
    venue = source.get("display_name") or ""
    publisher = source.get("host_organization_name") or ""
    oa = w.get("open_access") or {}
    oa_url = oa.get("oa_url") or (loc.get("pdf_url") if loc else "") or ""
    abstract = rebuild_abstract_from_inverted_index(w.get("abstract_inverted_index"))
    biblio = w.get("biblio") or {}
    pub_type = _map_openalex_type((w.get("type") or "").lower())
    return Paper(
        title=(w.get("title") or w.get("display_name") or "").strip(),
        authors=authors,
        year=w.get("publication_year"),
        venue=venue.strip(),
        cited_by_count=w.get("cited_by_count"),
        doi=doi.strip(),
        doi_url=(f"https://doi.org/{doi}" if doi else ""),
        abstract=abstract,
        oa_url=oa_url or "",
        source="openalex",
        pub_type=pub_type,
        publisher=publisher.strip(),
        volume=str((biblio.get("volume") or "").strip()),
        issue=str((biblio.get("issue") or "").strip()),
        page="".join(
            filter(
                None,
                [
                    str(biblio.get("first_page") or "").strip(),
                    (
                        "-" + str(biblio.get("last_page") or "").strip()
                        if biblio.get("last_page")
                        else ""
                    ),
                ],
            )
        ),
        raw_authors=raw_authors,
    )


def _map_openalex_type(oa_type: str) -> str:
    if not oa_type:
        return "article"
    if "article" in oa_type:
        return "article"
    if "book-chapter" in oa_type or "chapter" in oa_type:
        return "chapter"
    if "book" in oa_type and "chapter" not in oa_type:
        return "book"
    if "proceedings" in oa_type or "conference" in oa_type:
        return "conference"
    if "preprint" in oa_type:
        return "preprint"
    if "dissertation" in oa_type or "thesis" in oa_type:
        return "thesis"
    return "other"


async def openalex_search(
    query: str, rows: int = 10, year_from: int | None = None
) -> list[Paper]:
    rows = max(1, min(int(rows or 10), 40))
    cache_key = f"oa_search:{query}:{rows}:{year_from}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    params: dict[str, Any] = {
        "search": query,
        "per-page": rows,
        "select": _WORK_SELECT,
        "mailto": ACADEMIC_MAILTO,
    }
    if year_from:
        params["filter"] = f"from_publication_date:{year_from}-01-01"
    data = await fetch_json(f"{OPENALEX_BASE}/works", params=params)
    if not data:
        return []
    papers = [_parse_openalex_work(w) for w in (data.get("results") or [])]
    papers = [p for p in papers if p.title or p.doi]
    cache_set(cache_key, papers)
    return papers


async def openalex_topic_trend(keyword: str) -> dict[str, Any]:
    """近 3 年某关键词的论文数趋势（领域热度）。"""
    cache_key = f"oa_trend:{keyword}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    import datetime

    this_year = datetime.date.today().year
    trend: dict[int, int] = {}
    for y in range(this_year - 2, this_year + 1):
        params = {
            "search": keyword,
            "filter": f"publication_year:{y}",
            "per-page": 1,
            "mailto": ACADEMIC_MAILTO,
        }
        data = await fetch_json(f"{OPENALEX_BASE}/works", params=params)
        count = ((data or {}).get("meta") or {}).get("count", 0) if data else 0
        trend[y] = count
    result = {
        "keyword": keyword,
        "trend": [{"year": y, "count": c} for y, c in trend.items()],
        "total_recent3y": sum(trend.values()),
        "source": "openalex",
    }
    cache_set(cache_key, result)
    return result


async def openalex_author_profile(
    name: str, institution: str | None = None
) -> dict[str, Any] | None:
    """学者画像：h 指数、论文数、代表作 Top-K、主题分布。"""
    cache_key = f"oa_author:{name}:{institution}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    # 1. 搜作者
    aparams: dict[str, Any] = {
        "search": name,
        "select": "id,display_name,works_count,cited_by_count,summary_stats,affiliations,topics,last_known_institutions,ids",
        "per-page": 5,
        "mailto": ACADEMIC_MAILTO,
    }
    if institution:
        aparams["filter"] = f"affiliations.search:{institution}"
    adata = await fetch_json(f"{OPENALEX_BASE}/authors", params=aparams)
    if not adata:
        return None
    results = adata.get("results") or []
    if not results:
        return None
    author = results[0]
    author_id = (author.get("id") or "").rsplit("/", 1)[-1]

    # 2. 取该作者被引最高的代表作
    wparams = {
        "filter": f"author.id:{author_id}",
        "sort": "cited_by_count:desc",
        "per-page": 8,
        "select": "id,doi,title,publication_year,cited_by_count,primary_location",
        "mailto": ACADEMIC_MAILTO,
    }
    wdata = await fetch_json(f"{OPENALEX_BASE}/works", params=wparams)
    top_works: list[Paper] = []
    if wdata:
        for w in (wdata.get("results") or [])[:8]:
            top_works.append(_parse_openalex_work(w))

    stats = author.get("summary_stats") or {}
    h_index = (stats.get("h_index") if isinstance(stats, dict) else None)
    topics = [
        {"name": (t.get("display_name") or ""), "count": t.get("count", 0)}
        for t in (author.get("topics") or [])[:6]
    ]
    result = {
        "name": author.get("display_name") or name,
        "openalex_id": author_id,
        "works_count": author.get("works_count", 0),
        "cited_by_count": author.get("cited_by_count", 0),
        "h_index": h_index,
        "topics": topics,
        "top_papers": [p.to_dict() for p in top_works],
        "source": "openalex",
    }
    cache_set(cache_key, result)
    return result
