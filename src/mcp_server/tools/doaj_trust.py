"""
DOAJ（Directory of Open Access Journals）白名单校验。

DOAJ 是免费开放的高质量 OA 期刊目录。不在 DOAJ 的期刊不一定是掠夺性的，
但可作为"非白名单"警示信号（标黄提示用户核验）。

数据：DOAJ 提供 CC-BY 开放的期刊 CSV（约 2 万条），定期更新。
  下载：https://doaj.org/faq#metadata
首次调用时从 DOAJ API 拉取 ISSN 白名单（按需缓存，7 天 TTL）。

提供：
  - is_in_doaj(issn) / is_venue_trusted(venue_name)
  - enrich_papers_with_trust(papers) 批量标注
"""

from __future__ import annotations

import logging
import time
from typing import Any

from mcp_server.tools.unified import fetch_json, cache_get, cache_set

logger = logging.getLogger(__name__)

DOAJ_BASE = "https://doaj.org/api/v2"
_DOAJ_CACHE_TTL = 7 * 24 * 3600  # 7 天
_DOAJ_KEY = "doaj_issn_set"


async def _load_doaj_issn_set() -> set[str]:
    """加载 DOAJ ISSN 白名单（缓存 7 天）。

    DOAJ API 支持 search/journals，但全量需翻页。这里用宽松策略：
    按需查询（单刊校验时直接 API），而非全量预加载。
    返回空 set 时走单刊查询。
    """
    cached = cache_get(_DOAJ_KEY)
    if cached is not None:
        return cached
    return set()


async def is_in_doaj(issn: str) -> bool:
    """检查某 ISSN 是否在 DOAJ 白名单。

    DOAJ API：GET /api/v2/search/journals/issn:{issn}
    """
    issn = (issn or "").strip()
    if not issn:
        return False
    cache_key = f"doaj_issn:{issn}"
    cached = cache_get(cache_key)
    if cached is not None:
        return bool(cached)
    try:
        data = await fetch_json(
            f"{DOAJ_BASE}/search/journals/issn:{issn}",
            source="doaj",
        )
        result = bool(data and data.get("results"))
        cache_set(cache_key, result)
        return result
    except Exception:
        cache_set(cache_key, False)
        return False


async def is_venue_trusted(venue: str, issn: str = "") -> dict[str, Any]:
    """检查期刊可信度（DOAJ 白名单校验）。

    返回 {trusted, reason, source}。
    无 ISSN 或 venue 时无法校验，返回 unknown（不误报）。
    """
    venue = (venue or "").strip()
    issn = (issn or "").strip()
    if not venue and not issn:
        return {"trusted": None, "reason": "无期刊信息无法校验", "source": "doaj"}

    # 有 ISSN 优先用 ISSN 查
    if issn:
        ok = await is_in_doaj(issn)
        if ok:
            return {"trusted": True, "reason": "在 DOAJ 开放获取白名单", "source": "doaj"}
        return {
            "trusted": None,
            "reason": "不在 DOAJ 白名单（非掠夺确证，建议核验）",
            "source": "doaj",
        }

    # 无 ISSN：无法精确校验（DOAJ 按 ISSN 索引）
    return {
        "trusted": None,
        "reason": "缺 ISSN 无法精确校验（建议补 ISSN）",
        "source": "doaj",
    }


async def enrich_papers_with_trust(papers: list[dict]) -> list[dict]:
    """批量给 paper dict 列表标注 venue_trust 字段（限前 N 篇，避免 API 过载）。

    只对有 venue 的前 10 篇做校验（成本控制），其余标 unknown。
    """
    if not papers:
        return papers
    for i, p in enumerate(papers[:10]):
        try:
            venue = p.get("venue") or ""
            # ISSN 暂不可得（Paper 无 issn 字段）；用 venue 名走 unknown 提示
            trust = await is_venue_trusted(venue, p.get("issn", ""))
            p["venue_trust"] = trust
        except Exception:
            p["venue_trust"] = {"trusted": None, "reason": "校验失败", "source": "doaj"}
    # 其余标 unknown
    for p in papers[10:]:
        if "venue_trust" not in p:
            p["venue_trust"] = {"trusted": None, "reason": "未校验（超批量上限）", "source": "doaj"}
    return papers
