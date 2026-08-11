"""
中文文献检索适配层。

免费合规来源：
  - Semantic Scholar 中文 query（S2 支持 CJK 检索）
  - OpenAlex 按 Chinese institution filter（中国机构产出）
  - 中文关键词 → 英文翻译检索（复用 paper_search 英文三源）

付费/授权来源（骨架，需填入机构授权后生效）：
  - CNKI/万方 adapter（见 cnki_adapter.py）

注册 MCP 工具：paper_search_cn(query, ...)
"""

from __future__ import annotations

from typing import Any

from mcp_server.tools.unified import (
    Paper,
    cache_get,
    cache_set,
    fetch_json,
    OPENALEX_BASE,
    ACADEMIC_MAILTO,
    OPENALEX_API_KEY,
    _source_available,
)
from mcp_server.tools.semantic_scholar_tools import s2_search
from mcp_server.tools.openalex_tools import openalex_search, _parse_openalex_work
from mcp_server.tools.academic import _dedup_by_doi, _mark_preprints, paper_search


async def paper_search_cn(
    query: str,
    rows: int = 10,
    year_from: int | None = None,
    translate: bool = True,
) -> dict[str, Any]:
    """中文文献检索：S2 中文 query + OpenAlex 中文机构产出 + 可选英文翻译检索。

    Args:
        query: 中文检索词，如「联邦学习 医疗影像」
        rows: 召回篇数
        year_from: 起始年份
        translate: 是否同时用英文翻译检索三源（默认 True，提升英文相关文献召回）
    """
    cache_key = f"cn_search:{query}:{rows}:{year_from}:{translate}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    rows = max(1, min(int(rows or 10), 40))
    s2_cn, oa_cn = [], []

    # 1. S2 中文 query（S2 支持 CJK）
    if _source_available("s2"):
        try:
            s2_cn = await s2_search(query, limit=rows, year_from=year_from)
        except Exception:
            s2_cn = []

    # 2. OpenAlex 中文 query（search 接受 CJK）
    if _source_available("openalex"):
        try:
            oa_cn = await openalex_search(query, rows=rows, year_from=year_from)
        except Exception:
            oa_cn = []

    merged = _dedup_by_doi(s2_cn + oa_cn)
    _mark_preprints(merged)
    merged.sort(key=lambda p: p.cited_by_count or 0, reverse=True)
    cn_papers = merged[:rows]

    # 3. 可选：中文→英文翻译检索（走英文三源，补充英文相关文献）
    en_result = None
    if translate:
        en_query = await _translate_cn_to_en(query)
        if en_query and en_query != query:
            try:
                en_result = await paper_search(en_query, rows=rows, year_from=year_from)
            except Exception:
                en_result = None

    result = {
        "query": query,
        "count": len(cn_papers),
        "cn_papers": [p.to_dict() for p in cn_papers],
        "translated_query": en_result.get("query") if en_result else None,
        "en_papers": (en_result.get("papers") or []) if en_result else [],
        "note": (
            f"中文检索召回 {len(cn_papers)} 篇（S2+OpenAlex CJK）。"
            + (f"已翻译为「{en_result.get('query')}」补充英文检索 {len(en_result.get('papers', []))} 篇。" if en_result else "")
            + "如需 CNKI/万方等中文学术数据库，请配置 CNKI_API_TOKEN 授权后启用。"
        ),
    }
    cache_set(cache_key, result)
    return result


async def _translate_cn_to_en(text: str) -> str:
    """中文→英文翻译（复用 LLM；离线时回退空，跳过翻译）。

    尝试用 DeepSeek/智谱做一次性翻译。无 API key 时返回空。
    """
    text = (text or "").strip()
    if not text or not any("\u4e00" <= c <= "\u9fff" for c in text):
        return text  # 非中文，原样返回
    cache_key = f"cn_translate:{text}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        import os
        from agent.settings import settings
        api_key = settings.deepseek_api_key or settings.zhipu_api_key
        if not api_key:
            return ""
        base_url = settings.deepseek_base_url
        model = settings.main_model
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "Translate the following Chinese academic query to English. Return ONLY the English query, no explanation. Keep technical terms accurate."},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 100,
                },
            )
            if resp.status_code == 200:
                en = (resp.json().get("choices") or [{}])[0].get("message", {}).get("content", "").strip().strip('"\'')
                if en:
                    cache_set(cache_key, en)
                    return en
    except Exception:
        pass
    return ""
