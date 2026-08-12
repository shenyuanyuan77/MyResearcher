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
    _source_available,
)
from mcp_server.tools.crossref_tools import crossref_search, crossref_by_doi, crossref_by_dois
from mcp_server.tools.openalex_tools import (
    openalex_search,
    openalex_topic_trend,
    openalex_author_profile,
    openalex_cited_by,
    openalex_references,
    openalex_related,
)
from mcp_server.tools.semantic_scholar_tools import s2_search, s2_cross_search
from mcp_server.tools.citations import papers_to_references, format_paper, style_label


# jieba 分词（中文关键词切分）；未安装时回退到空格切分
try:
    import jieba  # type: ignore
    jieba.setLogLevel(20)  # 抑制 jieba 初始化日志
    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False

# 中文停用词（粗表）
_CN_STOPWORDS = set("的与和及在对于通过基于从向等为是以用被把给让使".split() + [
    "研究", "方法", "应用", "结合", "基于", "通过", "一种", "一个", "这个",
    "如何", "什么", "为什么", "可以", "能够", "进行", "分析", "问题",
])


def _tokenize_topic(topic: str, max_n: int = 8) -> list[str]:
    """主题词切分：CJK 用 jieba，英文用空格；去停用词，去短词。"""
    topic = (topic or "").strip()
    if not topic:
        return []
    tokens: list[str] = []
    if _HAS_JIEBA and any("\u4e00" <= c <= "\u9fff" for c in topic):
        # 中文：jieba 分词 + 停用词过滤
        raw = [w.strip() for w in jieba.cut(topic, cut_all=False) if w.strip()]
        tokens = [w for w in raw if len(w) > 1 and w not in _CN_STOPWORDS]
    # 英文/混合：空格切分补入
    for w in topic.replace(",", " ").replace("，", " ").split():
        w = w.strip().strip("\"'()[]")
        if len(w) > 1 and w not in tokens and w.lower() not in {"the", "a", "an", "of", "for", "and", "in", "on", "with", "to"}:
            tokens.append(w)
    return tokens[:max_n]


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


def _dedup_by_doi(papers: list[Paper], drop_retracted: bool = False) -> list[Paper]:
    """按 DOI/标题去重，合并多源信息 + 累积 sources 列表 + 预印本配对标记。

    - 同一文献在多源命中：累积到 Paper.sources，保留信息最全的字段。
    - 预印本与正式版配对：若同一 DOI-root 或标题高度相似，标记 is_preprint。
    - drop_retracted=True 时过滤撤稿论文。
    """
    if drop_retracted:
        papers = [p for p in papers if not p.is_retracted]
    seen: dict[str, Paper] = {}
    source_rank = {"crossref": 0, "openalex": 1, "s2": 2}
    for p in papers:
        key = (p.doi or "").lower() or (p.title or "").lower()[:80]
        if not key:
            continue
        prev = seen.get(key)
        if prev is None:
            p.sources = [p.source] if p.source else []
            seen[key] = p
        else:
            # 累积来源
            if p.source and p.source not in prev.sources:
                prev.sources.append(p.source)
            # 合并字段：取非空值，cited_by 取最大
            if not prev.title and p.title:
                prev.title = p.title
            if not prev.abstract and p.abstract:
                prev.abstract = p.abstract
            if not prev.doi and p.doi:
                prev.doi = p.doi
                prev.doi_url = prev.doi_url or p.doi_url or f"https://doi.org/{p.doi}"
            if p.cited_by_count is not None:
                prev.cited_by_count = max(
                    prev.cited_by_count or 0, p.cited_by_count
                ) if prev.cited_by_count is not None else p.cited_by_count
            if not prev.oa_url and p.oa_url:
                prev.oa_url = p.oa_url
                prev.oa = True
            if not prev.year and p.year:
                prev.year = p.year
            if not prev.venue and p.venue:
                prev.venue = p.venue
            # external_ids 合并
            if p.external_ids:
                merged_ids = dict(prev.external_ids)
                merged_ids.update(p.external_ids)
                prev.external_ids = merged_ids
            # 撤稿标记传递
            if p.is_retracted:
                prev.is_retracted = True
            # 主来源取更权威的
            if source_rank.get(p.source, 9) < source_rank.get(prev.source, 9):
                prev.source = p.source
    return list(seen.values())


def _mark_preprints(papers: list[Paper]) -> None:
    """标记预印本：若存在正式版（pub_type 非 preprint，标题相似），则标记 is_preprint。"""
    # 收集正式版标题
    formal_titles = [(p.title.lower()[:60], p) for p in papers if p.pub_type != "preprint" and p.title]
    for p in papers:
        if p.pub_type == "preprint" and p.title:
            pkey = p.title.lower()[:60]
            # 简单前缀匹配（标题前 60 字符相同视为同一工作）
            for ft, _ in formal_titles:
                if ft == pkey:
                    p.is_preprint = True
                    break


async def paper_search(
    query: str,
    rows: int = 10,
    year_from: int | None = None,
    year_to: int | None = None,
    pub_type: str | None = None,
    oa_only: bool = False,
    min_citations: int | None = None,
    sort: str = "cited",
    exclude_dois: list[str] | None = None,
    exclude_retracted: bool = True,
) -> dict[str, Any]:
    """② 情报提纯：多源召回真实 DOI 文献，自动归并去重降级。

    支持过滤：年份范围 / 文献类型 / 仅 OA / 最低引用数 / 排序（cited/newest/relevance）/ 排除 DOI / 过滤撤稿。
    降级透明：返回 meta.sources_tried/sources_failed/degraded_reason，供前端展示召回质量。
    """
    cache_key = (
        f"eng_search:{query}:{rows}:{year_from}:{year_to}:{pub_type}:"
        f"{oa_only}:{min_citations}:{sort}:{sorted(exclude_dois or [])}:{exclude_retracted}"
    )
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    rows = max(1, min(int(rows or 10), 40))
    sources_tried: list[str] = []
    sources_failed: list[str] = []

    cr, oa, s2 = [], [], []
    # CrossRef（跳过熔断源）
    if _source_available("crossref"):
        sources_tried.append("crossref")
        try:
            cr = await crossref_search(
                query, rows=rows, year_from=year_from, year_to=year_to,
                pub_type=pub_type, sort=sort, exclude_dois=exclude_dois,
            )
        except Exception:
            cr = []
        if not cr:
            sources_failed.append("crossref")
    else:
        sources_failed.append("crossref(circuit-open)")

    # OpenAlex
    if _source_available("openalex"):
        sources_tried.append("openalex")
        try:
            oa = await openalex_search(
                query, rows=rows, year_from=year_from, year_to=year_to,
                pub_type=pub_type, oa_only=oa_only, min_citations=min_citations,
                sort=sort, exclude_dois=exclude_dois,
            )
        except Exception:
            oa = []
        if not oa:
            sources_failed.append("openalex")
    else:
        sources_failed.append("openalex(circuit-open)")

    # S2（仅当主源不足或需要摘要时；429 多，保守用）
    need_s2 = len(cr) + len(oa) < rows
    if need_s2 and _source_available("s2"):
        sources_tried.append("semantic_scholar")
        try:
            s2 = await s2_search(
                query, limit=rows, year_from=year_from, year_to=year_to,
                pub_type=pub_type, oa_only=oa_only,
            )
        except Exception:
            s2 = []
        if not s2:
            sources_failed.append("semantic_scholar")

    merged = _dedup_by_doi(cr + oa + s2, drop_retracted=exclude_retracted)
    _mark_preprints(merged)

    # 客户端侧排序（三源 sort 可能不一致，统一重排）
    sort_key = {
        "cited": lambda p: p.cited_by_count or 0,
        "newest": lambda p: p.year or 0,
        "relevance": lambda p: 0,  # 保留源返回顺序
    }.get(sort, lambda p: p.cited_by_count or 0)
    reverse = sort != "relevance"
    merged.sort(key=sort_key, reverse=reverse)
    merged = merged[:rows]

    # 降级原因
    degraded_reason = ""
    if not merged:
        degraded_reason = f"所有数据源未召回（尝试：{','.join(sources_tried)}；失败：{','.join(sources_failed)}）"
    elif len(merged) < rows and sources_failed:
        degraded_reason = f"已尽力召回 {len(merged)} 篇（目标 {rows}），部分数据源受限：{','.join(sources_failed)}"

    result = {
        "query": query,
        "count": len(merged),
        "sources_used": {
            "crossref": len(cr),
            "openalex": len(oa),
            "semantic_scholar": len(s2),
        },
        "meta": {
            "requested": rows,
            "returned": len(merged),
            "sources_tried": sources_tried,
            "sources_failed": sources_failed,
            "filters": {
                "year_from": year_from, "year_to": year_to,
                "pub_type": pub_type, "oa_only": oa_only,
                "min_citations": min_citations, "sort": sort,
                "exclude_retracted": exclude_retracted,
            },
            "degraded_reason": degraded_reason,
        },
        "papers": [p.to_dict() for p in merged],
        "references": _structured_references(merged),
        "references_markdown": _references_block(merged),
        "suggested_markdown": papers_to_markdown(
            merged, caption=f"「{query}」相关文献"
        ),
        "table_rows": papers_to_table(merged),
        "note": "全部文献带真实 DOI，可点击 doi_url 溯源。撤稿论文默认过滤；references_markdown 为 GB/T 7714 参考文献块。",
    }
    cache_set(cache_key, result)
    return result


async def paper_by_doi(doi: str) -> dict[str, Any]:
    """② 单篇 DOI 精确溯源：CrossRef 权威校验，OpenAlex 补摘要/引用。"""
    from mcp_server.tools.crossref_tools import _normalize_doi
    doi = _normalize_doi(doi)
    if not doi:
        return {"ok": False, "message": "DOI 输入为空或格式无法识别。"}
    cache_key = f"eng_doi:{doi}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    paper = await crossref_by_doi(doi)
    if paper is None:
        return {
            "ok": False,
            "message": f"未在 CrossRef 找到 DOI={doi} 的真实文献。请检查 DOI 是否正确（零幻觉：不编造）。",
            "doi_tried": doi,
        }
    # 补摘要/oa：用标题去 OpenAlex/S2 找摘要
    if not paper.abstract and paper.title:
        try:
            oa_list = await openalex_search(paper.title, rows=1)
            if oa_list and oa_list[0].abstract:
                paper.abstract = oa_list[0].abstract
            if oa_list and oa_list[0].oa_url and not paper.oa_url:
                paper.oa_url = oa_list[0].oa_url
                paper.oa = True
        except Exception:
            pass
    # 撤稿警告
    warning = ""
    if paper.is_retracted:
        warning = "⚠️ 该论文已被撤稿（CrossRef 标记），引用前请核实撤稿原因。"
    return {
        "ok": True,
        "paper": paper.to_dict(),
        "references": _structured_references([paper]),
        "references_markdown": _references_block([paper]),
        "suggested_markdown": papers_to_markdown([paper], caption="DOI 精确溯源"),
        "warning": warning,
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
    is_retracted = paper.get("is_retracted", False)
    abstract_note = ""
    if not abstract:
        abstract_note = "（该文献无公开摘要：已尝试 CrossRef/OpenAlex/S2。建议点击 DOI 查看原文，或上传 PDF 全文精读。）"
    # 用结构化字段重建 Paper 以调用国标格式化器
    paper_obj = Paper(**{k: v for k, v in paper.items() if k in Paper.__dataclass_fields__})
    warning = "⚠️ 该论文已被撤稿，引用前请核实。" if is_retracted else ""

    # PDF 全文精读：有 oa_url 时优先用全文（深度远超摘要）
    full_text_distill = None
    oa_url = paper.get("oa_url") or ""
    if oa_url:
        try:
            from mcp_server.tools.pdf_distill import distill_with_full_text
            full_text_distill = await distill_with_full_text(oa_url, abstract)
        except Exception:
            full_text_distill = None

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
            "abstract": abstract or abstract_note,
            "is_retracted": is_retracted,
            "quotation_hint": format_paper(paper_obj, "gbt7714"),
            "full_text_available": bool(full_text_distill and full_text_distill.get("available")),
            "quotable_sentences": (full_text_distill or {}).get("quotable_sentences", []),
            "sections": (full_text_distill or {}).get("sections", {}),
        },
        "full_text_distill": full_text_distill,
        "warning": warning,
        "note": "摘要/数据均来自公开学术源，无虚构。有 OA 全文时已用 pymupdf 抽取全文精读（quotable_sentences 为可引用句）。",
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
    # 关键词：jieba 分词（替代原 split() 粗切）
    keywords = _tokenize_topic(topic, max_n=6)
    # 检索式：动态生成（含中英双语，若主题含中文则补英文检索式）
    has_cn = any("\u4e00" <= c <= "\u9fff" for c in topic)
    queries = [
        f'"{topic}" survey OR review',
        f'"{topic}" recent advances',
        f'"{topic}" benchmark OR dataset',
    ]
    if has_cn and keywords:
        # 中文主题：补中文检索式（关键词 OR 组合）
        cn_q = " ".join(keywords[:3])
        queries.insert(0, f'"{cn_q}" 综述')
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
        "note": "热度趋势来自 OpenAlex 真实论文计数，检索式可直接喂给 paper_search。中文主题已用 jieba 分词优化关键词。",
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


async def paper_by_dois(dois: list[str]) -> dict[str, Any]:
    """② 批量 DOI 核验：输入 DOI 列表，批量返回真实文献信息。

    用于从 EndNote/参考书目批量核验引用真实性。
    """
    from mcp_server.tools.crossref_tools import _normalize_doi
    clean = [_normalize_doi(d) for d in (dois or [])]
    clean = [d for d in clean if d]
    if not clean:
        return {"ok": False, "message": "DOI 列表为空或格式无效。", "count": 0, "papers": []}
    cache_key = f"eng_dois:{','.join(sorted(clean))}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    papers = await crossref_by_dois(clean)
    # 区分找到/未找到
    found_dois = {(p.doi or "").lower() for p in papers}
    missing = [d for d in clean if d.lower() not in found_dois]
    result = {
        "ok": True,
        "requested": len(clean),
        "count": len(papers),
        "found": len(papers),
        "missing": missing,
        "papers": [p.to_dict() for p in papers],
        "references": _structured_references(papers),
        "references_markdown": _references_block(papers),
        "suggested_markdown": papers_to_markdown(papers, caption=f"批量 DOI 核验（{len(papers)}/{len(clean)} 命中）"),
        "note": f"批量核验：{len(papers)}/{len(clean)} 个 DOI 在 CrossRef 命中。" + (f"未找到：{missing}" if missing else ""),
    }
    cache_set(cache_key, result)
    return result


async def paper_cited_by(identifier: str, rows: int = 10) -> dict[str, Any]:
    """施引文献：谁引用了这篇论文（需 OpenAlex ID 或 DOI）。"""
    oid = await _resolve_openalex_id(identifier)
    if not oid:
        return {"ok": False, "message": f"无法解析「{identifier}」的 OpenAlex ID。请提供 DOI 或 OpenAlex ID（如 W123）。"}
    papers = await openalex_cited_by(oid, rows=rows)
    return _expand_result(papers, f"「{identifier}」的施引文献（Top {rows}）", "cited_by")


async def paper_references(identifier: str, rows: int = 10) -> dict[str, Any]:
    """参考文献：这篇论文引用了谁（需 OpenAlex ID 或 DOI）。"""
    oid = await _resolve_openalex_id(identifier)
    if not oid:
        return {"ok": False, "message": f"无法解析「{identifier}」的 OpenAlex ID。请提供 DOI 或 OpenAlex ID。"}
    papers = await openalex_references(oid, rows=rows)
    return _expand_result(papers, f"「{identifier}」的参考文献（Top {rows}）", "references")


async def related_papers(identifier: str, rows: int = 10) -> dict[str, Any]:
    """相关文献：OpenAlex 标注的相关论文（需 OpenAlex ID 或 DOI）。"""
    oid = await _resolve_openalex_id(identifier)
    if not oid:
        return {"ok": False, "message": f"无法解析「{identifier}」的 OpenAlex ID。请提供 DOI 或 OpenAlex ID。"}
    papers = await openalex_related(oid, rows=rows)
    return _expand_result(papers, f"「{identifier}」的相关文献", "related")


async def _resolve_openalex_id(identifier: str) -> str:
    """把 DOI/标题/OpenAlex ID 解析为 OpenAlex work ID（如 W123456789）。"""
    from mcp_server.tools.crossref_tools import _normalize_doi
    ident = (identifier or "").strip()
    if not ident:
        return ""
    # 已是 OpenAlex ID
    if ident.upper().startswith("W") and ident[1:].isdigit():
        return ident
    # DOI → 用 OpenAlex filter 解析
    doi = _normalize_doi(ident)
    if doi and doi.startswith("10."):
        from mcp_server.tools.unified import fetch_json, OPENALEX_BASE, ACADEMIC_MAILTO, OPENALEX_API_KEY
        params: dict[str, Any] = {"filter": f"doi:{doi}", "select": "id", "per-page": 1, "mailto": ACADEMIC_MAILTO}
        if OPENALEX_API_KEY:
            params["api_key"] = OPENALEX_API_KEY
        data = await fetch_json(f"{OPENALEX_BASE}/works", params=params, source="openalex")
        results = (data or {}).get("results") or []
        if results:
            return (results[0].get("id") or "").rsplit("/", 1)[-1]
    # 标题 → 搜索取第一条的 id
    try:
        oa_list = await openalex_search(ident, rows=1)
        if oa_list and oa_list[0].external_ids.get("openalex"):
            return oa_list[0].external_ids["openalex"]
    except Exception:
        pass
    return ""


def _expand_result(papers: list[Paper], caption: str, relation: str) -> dict[str, Any]:
    """cited_by/references/related 通用返回结构。"""
    return {
        "ok": bool(papers),
        "count": len(papers),
        "relation": relation,
        "papers": [p.to_dict() for p in papers],
        "references": _structured_references(papers),
        "references_markdown": _references_block(papers),
        "suggested_markdown": papers_to_markdown(papers, caption=caption),
        "table_rows": papers_to_table(papers),
        "note": f"{relation} 均为真实文献（带 DOI）。" if papers else "未召回相关文献。",
    }
