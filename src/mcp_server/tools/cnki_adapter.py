"""
CNKI / 万方 / VIP 中文学术数据库适配器骨架。

⚠️ 合规说明：CNKI/万方/VIP 的全文与元数据受版权保护，需机构授权或付费 API。
本模块定义 adapter 接口与配置入口，**不包含任何爬虫或绕过授权的代码**。
配置 CNKI_API_TOKEN / CNKI_BASE_URL 后，adapter 自动启用；
无 token 时该源不启用且不报错（降级到免费中文源 cn_sources.py）。

授权获取方式：
  - CNKI 开放 API：联系同方知网商务（https://open.cnki.net）
  - 万方数据 API：https://www.wanfangdata.com.cn（机构合作）
  - 填入 .env: CNKI_API_TOKEN=xxx / CNKI_BASE_URL=https://...
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from mcp_server.tools.unified import Paper, fetch_json, cache_get, cache_set

logger = logging.getLogger(__name__)

# 配置入口（无 token 时不启用）
CNKI_API_TOKEN = os.getenv("CNKI_API_TOKEN", "").strip() or None
CNKI_BASE_URL = os.getenv("CNKI_BASE_URL", "https://api.cnki.net").strip().rstrip("/")


def cnki_enabled() -> bool:
    """CNKI 源是否可用（有 token 即启用）。"""
    return bool(CNKI_API_TOKEN)


async def cnki_search(query: str, rows: int = 10, year_from: int | None = None) -> list[Paper]:
    """CNKI 检索（需授权）。

    无 CNKI_API_TOKEN 时返回空列表（降级）。
    有 token 时按 CNKI OpenAPI 约定请求；具体字段映射需按实际 API 文档调整。
    """
    if not cnki_enabled():
        logger.debug("CNKI 未启用（无 CNKI_API_TOKEN），跳过")
        return []
    rows = max(1, min(int(rows or 10), 40))
    cache_key = f"cnki:{query}:{rows}:{year_from}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    params: dict[str, Any] = {"q": query, "rows": rows, "token": CNKI_API_TOKEN}
    if year_from:
        params["year_from"] = year_from
    # ⚠️ CNKI OpenAPI 的实际端点/参数需按授权文档调整，此处为占位约定
    data = await fetch_json(
        f"{CNKI_BASE_URL}/works/search",
        params=params,
        headers={"Authorization": f"Bearer {CNKI_API_TOKEN}"},
        source="cnki",
    )
    if not data:
        return []
    papers = [_parse_cnki_item(it) for it in (data.get("results") or [])]
    papers = [p for p in papers if p.title]
    cache_set(cache_key, papers)
    return papers


def _parse_cnki_item(item: dict[str, Any]) -> Paper:
    """CNKI 条目 → 统一 Paper。

    ⚠️ 字段映射需按 CNKI OpenAPI 实际返回结构调整（占位）。
    """
    return Paper(
        title=(item.get("title") or "").strip(),
        authors=[a.get("name", "") for a in (item.get("authors") or []) if a.get("name")],
        year=item.get("year"),
        venue=(item.get("source") or item.get("journal") or "").strip(),
        cited_by_count=item.get("cited"),
        doi=(item.get("doi") or "").strip(),
        doi_url=f"https://doi.org/{item['doi']}" if item.get("doi") else "",
        abstract=(item.get("abstract") or "").strip(),
        source="cnki",
        pub_type=(item.get("type") or "article"),
        external_ids={"cnki": item.get("id", "")} if item.get("id") else {},
    )
