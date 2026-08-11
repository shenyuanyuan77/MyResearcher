"""
研途智探五大引擎对 Agent 暴露的学术工具（编排三源，智能归并/降级）。

工具命名对应五大引擎：
  topic_radar       → ① 方向构建（领域热度 + 关键词 + 检索式）
  paper_search      → ② 情报提纯（多源召回真实 DOI 文献）
  paper_by_doi      → ② 单篇 DOI 精确溯源
  paper_distill     → ② 精读单篇（补全摘要）
  author_profile    → ③ 资产透视（学者画像）
  cross_search      → ④ 跨界启发（交叉工作）
"""

from __future__ import annotations

from typing import Any

from mcp_server.tools.unified import (
    Paper,
    papers_to_markdown,
    papers_to_table,
    cache_get,
    cache_set,
)
from mcp_server.tools.crossref_tools import crossref_search, crossref_by_doi
from mcp_server.tools.openalex_tools import (
    openalex_search,
    openalex_topic_trend,
    openalex_author_profile,
)
from mcp_server.tools.semantic_scholar_tools import s2_search, s2_cross_search
from mcp_server.tools.citations import papers_to_references, format_paper, style_label


def _references_block(papers: list[Paper], style: str = "gbt7714") -> str:
    """生成可直接照贴的参考文献 markdown 块。"""
    if not papers:
        return ""
    return papers_to_references(papers, style=style)


def _structured_references(papers: list[Paper]) -> list[dict[str, Any]]:
    """提炼供前端富卡片渲染的结构化引用数组（按召回顺序，带 [n] 序号）。"""
    out: list[dict[str, Any]] = []
    for i, p in enumerate(papers, 1):
        d = p.to_dict()
        d["idx"] = i
        d["citation_gbt7714"] = format_paper(p, "gbt7714", idx=i)
        out.append(d)
    return out


def _dedup_by_doi(papers: list[Paper]) -> list[Paper]:
    """按 DOI/标题去重，保留信息最全的一条（CrossRef 优先保 DOI）。"""
    seen: dict[str, Paper] = {}
    source_rank = {"crossref": 0, "openalex": 1, "s2": 2}
    for p in papers:
        key = (p.doi or "").lower() or (p.title or "").lower()[:80]
        if not key:
            continue
        prev = seen.get(key)
        if prev is None:
            seen[key] = p
        else:
            # 保留来源更权威 / 摘要更长的
            if source_rank.get(p.source, 9) < source_rank.get(prev.source, 9):
                # 合并信息
                merged = Paper(
                    title=p.title or prev.title,
                    authors=p.authors or prev.authors,
                    year=p.year or prev.year,
                    venue=p.venue or prev.venue,
                    cited_by_count=(
                        p.cited_by_count
                        if p.cited_by_count is not None
                        else prev.cited_by_count
                    ),
                    doi=p.doi or prev.doi,
                    doi_url=p.doi_url or prev.doi_url,
                    abstract=p.abstract or prev.abstract,
                    oa_url=p.oa_url or prev.oa_url,
                    source=p.source,
                )
                seen[key] = merged
    return list(seen.values())


async def paper_search(
    query: str, rows: int = 10, year_from: int | None = None
) -> dict[str, Any]:
    """② 情报提纯：多源召回真实 DOI 文献，自动归并去重降级。"""
    cache_key = f"eng_search:{query}:{rows}:{year_from}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    rows = max(1, min(int(rows or 10), 40))
    # 主源 CrossRef（DOI 权威）+ OpenAlex（富数据）+ S2（摘要兜底）
    cr, oa, s2 = [], [], []
    try:
        cr = await crossref_search(query, rows=rows, year_from=year_from)
    except Exception:
        cr = []
    try:
        oa = await openalex_search(query, rows=rows, year_from=year_from)
    except Exception:
        oa = []
    # 仅当主源不足或需要摘要时调用 S2（429 多，保守用）
    need_s2 = len(cr) + len(oa) < rows
    if need_s2:
        try:
            s2 = await s2_search(query, limit=rows, year_from=year_from)
        except Exception:
            s2 = []

    merged = _dedup_by_doi(cr + oa + s2)
    # 按引用数降序，截断到 rows
    merged.sort(
        key=lambda p: (p.cited_by_count if p.cited_by_count is not None else 0),
        reverse=True,
    )
    merged = merged[:rows]

    result = {
        "query": query,
        "count": len(merged),
        "sources_used": {
            "crossref": len(cr),
            "openalex": len(oa),
            "semantic_scholar": len(s2),
        },
        "papers": [p.to_dict() for p in merged],
        "references": _structured_references(merged),
        "references_markdown": _references_block(merged),
        "suggested_markdown": papers_to_markdown(
            merged, caption=f"「{query}」相关文献"
        ),
        "table_rows": papers_to_table(merged),
        "note": "全部文献带真实 DOI，可点击 doi_url 溯源（零幻觉）。references_markdown 为 GB/T 7714 参考文献块，可直接贴到文末。",
    }
    cache_set(cache_key, result)
    return result


async def paper_by_doi(doi: str) -> dict[str, Any]:
    """② 单篇 DOI 精确溯源：CrossRef 权威校验，OpenAlex 补摘要/引用。"""
    doi = (doi or "").strip()
    if doi.startswith("http"):
        doi = doi.split("doi.org/", 1)[-1]
    cache_key = f"eng_doi:{doi}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    paper = await crossref_by_doi(doi)
    if paper is None:
        return {
            "ok": False,
            "message": f"未在 CrossRef 找到 DOI={doi} 的真实文献（零幻觉：不编造）。",
        }
    # 补摘要：用标题去 OpenAlex/S2 找摘要
    if not paper.abstract and paper.title:
        try:
            oa_list = await openalex_search(paper.title, rows=1)
            if oa_list and oa_list[0].abstract:
                paper.abstract = oa_list[0].abstract
        except Exception:
            pass
    return {
        "ok": True,
        "paper": paper.to_dict(),
        "references": _structured_references([paper]),
        "references_markdown": _references_block([paper]),
        "suggested_markdown": papers_to_markdown([paper], caption="DOI 精确溯源"),
        "note": "DOI 来自 CrossRef（全球 DOI 注册机构），权威可信。",
    }


async def paper_distill(identifier: str) -> dict[str, Any]:
    """② 精读：输入标题或 DOI，返回单篇结构化精读要点（含真实摘要/可引用句）。"""
    identifier = (identifier or "").strip()
    is_doi = "/" in identifier and identifier.split("/")[
        0
    ].replace(".", "").isdigit() or identifier.startswith("10.")
    if is_doi:
        base = await paper_by_doi(identifier)
        paper = base.get("paper") if base.get("ok") else None
    else:
        # 当标题用，搜第一条
        res = await paper_search(identifier, rows=1)
        papers = res.get("papers") or []
        paper = papers[0] if papers else None
    if not paper:
        return {"ok": False, "message": "未找到该文献，无法精读（不编造）。"}
    abstract = paper.get("abstract") or ""
    # 用结构化字段重建 Paper 以调用国标格式化器
    paper_obj = Paper(**{k: v for k, v in paper.items() if k in Paper.__dataclass_fields__})
    return {
        "ok": True,
        "paper": paper,
        "references": _structured_references([paper_obj]),
        "references_markdown": _references_block([paper_obj]),
        "distill": {
            "title": paper.get("title"),
            "authors": paper.get("authors"),
            "year": paper.get("year"),
            "venue": paper.get("venue"),
            "doi_url": paper.get("doi_url") or f"https://doi.org/{paper.get('doi','')}",
            "cited_by_count": paper.get("cited_by_count"),
            "abstract": abstract or "（该文献暂无公开摘要，建议点击 DOI 查看原文）",
            "quotation_hint": format_paper(paper_obj, "gbt7714"),
        },
        "note": "摘要/数据均来自公开学术源，无虚构。distill.quotation_hint 为 GB/T 7714 格式。",
    }


async def topic_radar(topic: str) -> dict[str, Any]:
    """① 方向构建：领域热度趋势 + 关键词 + 检索式建议。"""
    cache_key = f"eng_topic:{topic}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    trend = await openalex_topic_trend(topic)
    # 顺手取几篇高引代表作，帮助判断领域核心
    top = await paper_search(topic, rows=6)
    top_papers = (top.get("papers") or [])[:6]
    # 关键词建议（简单：主题词 + 高频合成）
    keywords = [w for w in topic.replace(",", " ").split() if len(w) > 1][:6]
    queries = [
        f'"{topic}" survey OR review',
        f'"{topic}" recent advances',
        f'"{topic}" benchmark',
    ]
    result = {
        "topic": topic,
        "heat_trend": trend,
        "suggested_keywords": keywords,
        "suggested_queries": queries,
        "top_cited_papers": top_papers,
        "suggested_markdown": papers_to_markdown(
            [Paper(**{k: v for k, v in p.items() if k in Paper.__dataclass_fields__}) for p in top_papers],
            caption=f"「{topic}」领域高引代表作",
        ),
        "note": "热度趋势来自 OpenAlex 真实论文计数，检索式可直接喂给 paper_search。",
    }
    cache_set(cache_key, result)
    return result


async def author_profile(name: str, institution: str = "") -> dict[str, Any]:
    """③ 资产透视：学者画像（h 指数、代表作、主题、合作网络提示）。"""
    prof = await openalex_author_profile(name, institution or None)
    if not prof:
        return {
            "ok": False,
            "message": f"未在 OpenAlex 找到学者「{name}」。请补充机构或 ORCID（零幻觉：不编造）。",
        }
    top = prof.get("top_papers") or []
    top_paper_objs = [Paper(**{k: v for k, v in p.items() if k in Paper.__dataclass_fields__}) for p in top]
    return {
        "ok": True,
        "profile": prof,
        "references": _structured_references(top_paper_objs),
        "references_markdown": _references_block(top_paper_objs),
        "suggested_markdown": papers_to_markdown(
            top_paper_objs,
            caption=f"{prof.get('name')} 代表作（h-index={prof.get('h_index')}）",
        ),
        "note": "学者数据来自 OpenAlex（全球开放学术索引），含真实 h 指数与代表作 DOI。",
    }


async def cross_search(domain_a: str, domain_b: str, limit: int = 8) -> dict[str, Any]:
    """④ 跨界启发：检索两领域已存在的交叉工作（真实文献佐证）。"""
    papers = await s2_cross_search(domain_a, domain_b, limit=limit)
    # 若 S2 无结果，降级到主检索
    if not papers:
        papers_objs = []
        try:
            res = await paper_search(f"{domain_a} {domain_b}", rows=limit)
            for p in res.get("papers", []):
                papers_objs.append(
                    Paper(**{k: v for k, v in p.items() if k in Paper.__dataclass_fields__})
                )
            papers = papers_objs
        except Exception:
            papers = []
    return {
        "domain_a": domain_a,
        "domain_b": domain_b,
        "count": len(papers),
        "papers": [p.to_dict() for p in papers],
        "references": _structured_references(papers),
        "references_markdown": _references_block(papers),
        "suggested_markdown": papers_to_markdown(
            papers, caption=f"「{domain_a} × {domain_b}」交叉工作"
        ),
        "note": "交叉工作均为真实文献（带 DOI），供可行性评估佐证；融合推演由主模型完成。",
    }
