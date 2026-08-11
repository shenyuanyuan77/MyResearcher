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
    CROSSREF_API_TOKEN,
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
    # 撤稿标记（CrossRef 的 is-retracted 字段，list 里含 type:retracted）
    is_retracted = False
    rel = item.get("relation") or {}
    if isinstance(rel, dict) and "is-preprint-of" not in rel:
        pass
    # CrossRef 在 assertion 或 type 中标记撤稿
    assertions = item.get("assertion") or []
    if isinstance(assertions, list):
        for a in assertions:
            if isinstance(a, dict) and "retraction" in str(a.get("value", "")).lower():
                is_retracted = True
                break
    if cr_type and "retraction" in cr_type:
        is_retracted = True
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
        is_retracted=is_retracted,
        external_ids={"doi": doi} if doi else {},
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
    year_to: int | None = None,
    pub_type: str | None = None,
    sort: str = "relevance",
    exclude_dois: list[str] | None = None,
) -> list[Paper]:
    """CrossRef 关键词检索，返回真实 DOI 文献列表。

    支持：年份范围、文献类型过滤、排序、DOI 排除。
    sort: relevance（默认）/ published / is-referenced-by-count
    pub_type: article / conference / preprint / book / chapter
    """
    rows = max(1, min(int(rows or 10), 40))
    cache_key = f"cr_search:{query}:{rows}:{year_from}:{year_to}:{pub_type}:{sort}:{sorted(exclude_dois or [])}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # sort 映射：relevance/published/cited
    cr_sort = {
        "cited": "is-referenced-by-count",
        "published": "published",
        "newest": "published",
    }.get(sort, "relevance")

    params: dict[str, Any] = {
        "query": query,
        "rows": rows,
        "select": "DOI,title,author,container-title,issued,is-referenced-by-count,abstract,publisher,type,volume,issue,page,URL,relation",
        "mailto": ACADEMIC_MAILTO,
        "sort": cr_sort,
    }
    filters: list[str] = []
    if year_from:
        filters.append(f"from-pub-date:{year_from}-01-01")
    if year_to:
        filters.append(f"until-pub-date:{year_to}-12-31")
    if pub_type:
        type_map = {
            "article": "journal-article",
            "conference": "proceedings-article",
            "preprint": "posted-content",
            "book": "book",
            "chapter": "book-chapter",
        }
        cr_t = type_map.get(pub_type, pub_type)
        filters.append(f"type:{cr_t}")
    if filters:
        params["filter"] = ",".join(filters)

    headers: dict[str, str] = {}
    if CROSSREF_API_TOKEN:
        headers["Crossref-Plus-Token"] = CROSSREF_API_TOKEN

    data = await fetch_json(
        f"{CROSSREF_BASE}/works", params=params, headers=headers, source="crossref"
    )
    if not data:
        return []
    items = (((data.get("message") or {}).get("items")) or [])
    papers = [_parse_crossref_item(it) for it in items]
    papers = [p for p in papers if p.title or p.doi]
    # 排除指定 DOI
    if exclude_dois:
        excl = {d.lower() for d in exclude_dois}
        papers = [p for p in papers if (p.doi or "").lower() not in excl]
    cache_set(cache_key, papers)
    return papers


async def crossref_by_doi(doi: str) -> Paper | None:
    """按裸 DOI 精确取一条（DOI 权威校验）。"""
    doi = _normalize_doi(doi)
    if not doi:
        return None
    cache_key = f"cr_doi:{doi}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    headers: dict[str, str] = {}
    if CROSSREF_API_TOKEN:
        headers["Crossref-Plus-Token"] = CROSSREF_API_TOKEN
    data = await fetch_json(
        f"{CROSSREF_BASE}/works/{doi}",
        params={"mailto": ACADEMIC_MAILTO},
        headers=headers,
        source="crossref",
    )
    if not data:
        return None
    item = (data.get("message") or {})
    if not item:
        return None
    paper = _parse_crossref_item(item)
    cache_set(cache_key, paper)
    return paper


async def crossref_by_dois(dois: list[str]) -> list[Paper]:
    """批量按 DOI 取（CrossRef filter batch）。"""
    clean = [_normalize_doi(d) for d in (dois or [])]
    clean = [d for d in clean if d]
    if not clean:
        return []
    cache_key = f"cr_dois:{','.join(sorted(clean))}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    headers: dict[str, str] = {}
    if CROSSREF_API_TOKEN:
        headers["Crossref-Plus-Token"] = CROSSREF_API_TOKEN
    # CrossRef filter 支持多 DOI：doi:10.a|10.b
    params = {
        "filter": "doi:" + "|".join(clean),
        "rows": len(clean),
        "select": "DOI,title,author,container-title,issued,is-referenced-by-count,abstract,publisher,type,volume,issue,page",
        "mailto": ACADEMIC_MAILTO,
    }
    data = await fetch_json(
        f"{CROSSREF_BASE}/works", params=params, headers=headers, source="crossref"
    )
    if not data:
        return []
    items = (((data.get("message") or {}).get("items")) or [])
    papers = [_parse_crossref_item(it) for it in items]
    cache_set(cache_key, papers)
    return papers


def _normalize_doi(doi: str) -> str:
    """DOI 输入容错：剥各种前缀，大小写归一。"""
    if not doi:
        return ""
    d = doi.strip()
    # 剥 https://doi.org/ / http://dx.doi.org/ / www.doi.org/ 等
    import re
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d, flags=re.I)
    d = re.sub(r"^doi:\s*", "", d, flags=re.I)
    return d.strip()
