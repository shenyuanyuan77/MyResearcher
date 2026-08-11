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
    OPENALEX_API_KEY,
    Paper,
    fetch_json,
    rebuild_abstract_from_inverted_index,
    cache_get,
    cache_set,
)


_WORK_SELECT = (
    "id,doi,title,authorships,publication_year,cited_by_count,"
    "primary_location,abstract_inverted_index,type,open_access,biblio,retracted,ids"
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
    # 撤稿：OpenAlex 在 work.retracted 或 best_oa_location 无直接字段，用 topics/keywords 间接；保守读 'retracted'
    is_retracted = bool(w.get("retracted") or False)
    oa_bool = bool((oa or {}).get("is_oa") or bool(oa_url))
    # external_ids
    ext_ids: dict[str, str] = {}
    oa_id = (w.get("id") or "").rsplit("/", 1)[-1]
    if oa_id:
        ext_ids["openalex"] = oa_id
    pmid = (w.get("ids") or {}).get("pmid") if isinstance(w.get("ids"), dict) else None
    if pmid:
        ext_ids["pmid"] = str(pmid)
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
        is_retracted=is_retracted,
        oa=oa_bool,
        external_ids=ext_ids,
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
    query: str,
    rows: int = 10,
    year_from: int | None = None,
    year_to: int | None = None,
    pub_type: str | None = None,
    oa_only: bool = False,
    min_citations: int | None = None,
    sort: str = "relevance",
    exclude_dois: list[str] | None = None,
) -> list[Paper]:
    """OpenAlex 检索，支持年份范围/类型/OA/最低引用/排序/排除 DOI。"""
    rows = max(1, min(int(rows or 10), 40))
    cache_key = f"oa_search:{query}:{rows}:{year_from}:{year_to}:{pub_type}:{oa_only}:{min_citations}:{sort}:{sorted(exclude_dois or [])}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    # sort 映射
    oa_sort = {
        "cited": "cited_by_count:desc",
        "newest": "publication_date:desc",
        "relevance": "relevance_score:desc",
    }.get(sort, "relevance_score:desc")
    params: dict[str, Any] = {
        "search": query,
        "per-page": rows,
        "select": _WORK_SELECT,
        "mailto": ACADEMIC_MAILTO,
        "sort": oa_sort,
    }
    # filter 组合
    filters: list[str] = []
    if year_from:
        filters.append(f"from_publication_date:{year_from}-01-01")
    if year_to:
        filters.append(f"to_publication_date:{year_to}-12-31")
    if pub_type:
        filters.append(f"type:{pub_type}")
    if oa_only:
        filters.append("is_oa:true")
    if min_citations:
        filters.append(f"cited_by_count:>{int(min_citations) - 1}")
    if filters:
        params["filter"] = ",".join(filters)
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    data = await fetch_json(f"{OPENALEX_BASE}/works", params=params, source="openalex")
    if not data:
        return []
    papers = [_parse_openalex_work(w) for w in (data.get("results") or [])]
    papers = [p for p in papers if p.title or p.doi]
    if exclude_dois:
        excl = {d.lower() for d in exclude_dois}
        papers = [p for p in papers if (p.doi or "").lower() not in excl]
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
        if OPENALEX_API_KEY:
            params["api_key"] = OPENALEX_API_KEY
        data = await fetch_json(f"{OPENALEX_BASE}/works", params=params, source="openalex")
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
    # 1. 搜作者（补 coauthors/orcid/affiliations，供合作网络/消歧）
    aparams: dict[str, Any] = {
        "search": name,
        "select": "id,display_name,works_count,cited_by_count,summary_stats,affiliations,topics,last_known_institutions,ids,coauthors",
        "per-page": 5,
        "mailto": ACADEMIC_MAILTO,
    }
    if institution:
        aparams["filter"] = f"affiliations.search:{institution}"
    if OPENALEX_API_KEY:
        aparams["api_key"] = OPENALEX_API_KEY
    adata = await fetch_json(f"{OPENALEX_BASE}/authors", params=aparams, source="openalex")
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
    if OPENALEX_API_KEY:
        wparams["api_key"] = OPENALEX_API_KEY
    wdata = await fetch_json(f"{OPENALEX_BASE}/works", params=wparams, source="openalex")
    top_works: list[Paper] = []
    if wdata:
        for w in (wdata.get("results") or [])[:8]:
            top_works.append(_parse_openalex_work(w))

    stats = author.get("summary_stats") or {}
    h_index = (stats.get("h_index") if isinstance(stats, dict) else None)
    # 近 2 年/5 年 h 指数（OpenAlex summary_stats 含 h_index_recent，或 fallback）
    h_index_recent = None
    if isinstance(stats, dict):
        h_index_recent = stats.get("h_index_recent") or stats.get("2yr_h_index")
    topics = [
        {"name": (t.get("display_name") or ""), "count": t.get("count", 0)}
        for t in (author.get("topics") or [])[:6]
    ]
    # 合作网络（coauthors Top 10）
    coauthors = []
    for ca in (author.get("coauthors") or [])[:10]:
        coauthors.append({
            "name": ca.get("display_name") or "",
            "id": (ca.get("id") or "").rsplit("/", 1)[-1],
            "works_count": ca.get("works_count", 0),
        })
    # ORCID / 机构
    author_ids = author.get("ids") or {}
    orcid = author_ids.get("orcid") or ""
    if orcid and orcid.startswith("http"):
        orcid = orcid.rsplit("/", 1)[-1]
    affiliations = [
        {
            "name": (af.get("display_name") or ""),
            "id": (af.get("id") or "").rsplit("/", 1)[-1],
        }
        for af in (author.get("affiliations") or [])[:5]
    ]
    institutions = [
        (inst.get("display_name") or "")
        for inst in (author.get("last_known_institutions") or [])[:3]
        if inst.get("display_name")
    ]
    result = {
        "name": author.get("display_name") or name,
        "openalex_id": author_id,
        "orcid": orcid,
        "works_count": author.get("works_count", 0),
        "cited_by_count": author.get("cited_by_count", 0),
        "h_index": h_index,
        "h_index_recent": h_index_recent,
        "topics": topics,
        "coauthors": coauthors,
        "affiliations": affiliations,
        "institutions": institutions,
        "top_papers": [p.to_dict() for p in top_works],
        "source": "openalex",
    }
    cache_set(cache_key, result)
    return result


async def openalex_cited_by(openalex_id: str, rows: int = 10) -> list[Paper]:
    """施引文献（cited_by）：谁引用了这篇论文。openalex_id 如 W123456789。"""
    rows = max(1, min(int(rows or 10), 40))
    oid = openalex_id.strip()
    if not oid:
        return []
    cache_key = f"oa_cited_by:{oid}:{rows}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    params = {
        "filter": f"cites:{oid}",
        "per-page": rows,
        "select": _WORK_SELECT,
        "mailto": ACADEMIC_MAILTO,
        "sort": "cited_by_count:desc",
    }
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    data = await fetch_json(f"{OPENALEX_BASE}/works", params=params, source="openalex")
    if not data:
        return []
    papers = [_parse_openalex_work(w) for w in (data.get("results") or [])]
    cache_set(cache_key, papers)
    return papers


async def openalex_references(openalex_id: str, rows: int = 10) -> list[Paper]:
    """参考文献（references）：这篇论文引用了谁。openalex_id 如 W123456789。"""
    rows = max(1, min(int(rows or 10), 40))
    oid = openalex_id.strip()
    if not oid:
        return []
    cache_key = f"oa_refs:{oid}:{rows}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    # 先取 referenced_works 列表
    params = {"select": "referenced_works", "mailto": ACADEMIC_MAILTO}
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    data = await fetch_json(f"{OPENALEX_BASE}/works/{oid}", params=params, source="openalex")
    if not data:
        return []
    ref_ids = ((data.get("referenced_works") or []) or [])[:rows]
    if not ref_ids:
        return []
    # 批量取这些 work 的详情（filter: W1|W2|...）
    filter_val = "|".join(r.rsplit("/", 1)[-1] for r in ref_ids)
    params2 = {
        "filter": f"openalex:{filter_val}",
        "per-page": len(ref_ids),
        "select": _WORK_SELECT,
        "mailto": ACADEMIC_MAILTO,
    }
    if OPENALEX_API_KEY:
        params2["api_key"] = OPENALEX_API_KEY
    data2 = await fetch_json(f"{OPENALEX_BASE}/works", params=params2, source="openalex")
    if not data2:
        return []
    papers = [_parse_openalex_work(w) for w in (data2.get("results") or [])]
    cache_set(cache_key, papers)
    return papers


async def openalex_related(openalex_id: str, rows: int = 10) -> list[Paper]:
    """相关文献（related_works）：OpenAlex 标注的相关论文。"""
    rows = max(1, min(int(rows or 10), 40))
    oid = openalex_id.strip()
    if not oid:
        return []
    cache_key = f"oa_related:{oid}:{rows}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    params = {"select": "related_works", "mailto": ACADEMIC_MAILTO}
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    data = await fetch_json(f"{OPENALEX_BASE}/works/{oid}", params=params, source="openalex")
    if not data:
        return []
    rel_ids = ((data.get("related_works") or []) or [])[:rows]
    if not rel_ids:
        return []
    filter_val = "|".join(r.rsplit("/", 1)[-1] for r in rel_ids)
    params2 = {
        "filter": f"openalex:{filter_val}",
        "per-page": len(rel_ids),
        "select": _WORK_SELECT,
        "mailto": ACADEMIC_MAILTO,
    }
    if OPENALEX_API_KEY:
        params2["api_key"] = OPENALEX_API_KEY
    data2 = await fetch_json(f"{OPENALEX_BASE}/works", params=params2, source="openalex")
    if not data2:
        return []
    papers = [_parse_openalex_work(w) for w in (data2.get("results") or [])]
    cache_set(cache_key, papers)
    return papers
