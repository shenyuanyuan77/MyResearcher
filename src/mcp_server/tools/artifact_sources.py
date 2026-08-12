"""
数据集与代码检索适配器。

来源（免费/开放）：
  - Zenodo（DataCite 元数据，开放检索）
  - PapersWithCode（论文 + 代码 + 数据集，开放 API）
  - GitHub（代码搜索，需 token 提升配额；无 token 走匿名低配额）

注册 MCP 工具：dataset_search / code_search
"""

from __future__ import annotations

from typing import Any

from mcp_server.tools.unified import fetch_json, cache_get, cache_set, _source_available

ZENODO_BASE = "https://zenodo.org/api"
PWC_BASE = "https://paperswithcode.com/api/v1"
GITHUB_BASE = "https://api.github.com"


async def dataset_search(query: str, rows: int = 10) -> dict[str, Any]:
    """检索公开数据集（Zenodo + PapersWithCode）。

    用于找实验所需的公开数据集。
    """
    cache_key = f"dataset:{query}:{rows}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    rows = max(1, min(int(rows or 10), 40))
    zenodo_results = []
    pwc_results = []

    # Zenodo（开放数据仓库）
    try:
        params = {"q": query, "size": min(rows, 20), "type": "dataset"}
        data = await fetch_json(
            f"{ZENODO_BASE}/records", params=params, source="zenodo"
        )
        for hit in ((data or {}).get("hits") or {}).get("hits", []):
            m = hit.get("metadata") or {}
            zenodo_results.append({
                "source": "zenodo",
                "title": m.get("title", ""),
                "authors": [c.get("name", "") for c in (m.get("creators") or [])][:5],
                "year": (m.get("publication_date") or "")[:4],
                "doi": m.get("doi", ""),
                "doi_url": m.get("doi_url", "") or f"https://doi.org/{m.get('doi','')}",
                "description": (m.get("description") or "")[:500],
                "url": f"https://zenodo.org/record/{hit.get('id','')}",
            })
    except Exception:
        pass

    # PapersWithCode（数据集）
    try:
        params = {"q": query, "page": 1}
        data = await fetch_json(
            f"{PWC_BASE}/datasets", params=params, source="pwc"
        )
        for d in ((data or {}).get("results") or [])[:rows]:
            pwc_results.append({
                "source": "paperswithcode",
                "title": d.get("name", ""),
                "description": (d.get("description") or "")[:500],
                "url": d.get("url", ""),
            })
    except Exception:
        pass

    merged = zenodo_results[:rows] + pwc_results[: max(0, rows - len(zenodo_results))]
    result = {
        "query": query,
        "count": len(merged),
        "datasets": merged[:rows],
        "note": "数据集来自 Zenodo（开放数据仓库）+ PapersWithCode。带 DOI 可溯源。",
    }
    cache_set(cache_key, result)
    return result


async def code_search(query: str, rows: int = 10) -> dict[str, Any]:
    """检索开源代码实现（GitHub code search + PapersWithCode repositories）。

    用于找论文的开源实现或 baseline 代码。
    """
    import os
    cache_key = f"code:{query}:{rows}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    rows = max(1, min(int(rows or 10), 40))
    gh_token = os.getenv("GITHUB_TOKEN", "").strip()
    github_results = []
    pwc_results = []

    # GitHub 仓库搜索（无需 token 可用，有 token 配额更高）
    try:
        params = {"q": query, "sort": "stars", "order": "desc", "per_page": min(rows, 30)}
        headers = {"Accept": "application/vnd.github+json"}
        if gh_token:
            headers["Authorization"] = f"Bearer {gh_token}"
        data = await fetch_json(
            f"{GITHUB_BASE}/search/repositories",
            params=params, headers=headers, source="github",
        )
        for repo in ((data or {}).get("items") or [])[:rows]:
            github_results.append({
                "source": "github",
                "name": repo.get("full_name", ""),
                "title": repo.get("full_name", ""),
                "description": (repo.get("description") or "")[:300],
                "url": repo.get("html_url", ""),
                "stars": repo.get("stargazers_count", 0),
                "language": repo.get("language", ""),
                "updated": (repo.get("updated_at") or "")[:10],
            })
    except Exception:
        pass

    # PapersWithCode（论文代码实现）
    try:
        params = {"q": query, "page": 1}
        data = await fetch_json(
            f"{PWC_BASE}/repositories", params=params, source="pwc"
        )
        for r in ((data or {}).get("results") or [])[:rows]:
            pwc_results.append({
                "source": "paperswithcode",
                "name": r.get("url", "").rsplit("/", 1)[-1],
                "title": r.get("url", "").rsplit("/", 1)[-1],
                "description": f"官方/社区实现，{r.get('papers_count', 0)} 篇相关论文",
                "url": r.get("url", ""),
                "stars": r.get("stars", 0),
            })
    except Exception:
        pass

    merged = github_results[:rows] + pwc_results[: max(0, rows - len(github_results))]
    result = {
        "query": query,
        "count": len(merged),
        "repositories": merged[:rows],
        "note": "代码来自 GitHub（star 排序）+ PapersWithCode。无 GITHUB_TOKEN 时配额较低。",
    }
    cache_set(cache_key, result)
    return result
