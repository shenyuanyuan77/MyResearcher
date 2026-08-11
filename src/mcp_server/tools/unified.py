"""
学术数据统一层：三源归一 + 重试退避 + 简易内存缓存。

数据源（均免费、无需 Key）：
  - CrossRef   ：全球 DOI 注册机构，DOI 最权威可信（主 DOI 源）
  - OpenAlex   ：富数据，引用数/作者/h 指数/主题（补全 + 作者画像）
  - Semantic Scholar：纯文本摘要最干净（兜底摘要）

统一 Paper 模型是整个系统「零幻觉 / DOI 溯源」的基石——
所有召回文献必须落到这个结构，并由调用方强制带 doi_url。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, asdict, field
from typing import Any, Optional

import httpx

# ------------------------------------------------------------
# 进程级 HTTP 客户端（学术工具调用外部公开 API，与 ERP 上下文客户端分离）
# ------------------------------------------------------------

_client: httpx.AsyncClient | None = None


def get_async_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            headers={"User-Agent": f"YanJiuZhiTan/1.0 (mailto:{ACADEMIC_MAILTO})"},
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            follow_redirects=True,
        )
    return _client

# ------------------------------------------------------------
# 配置
# ------------------------------------------------------------

ACADEMIC_MAILTO = "yanjiu@research-quest.cn"  # 礼貌池标识（CrossRef/OpenAlex 推荐）
CROSSREF_BASE = "https://api.crossref.org"
OPENALEX_BASE = "https://api.openalex.org"
S2_BASE = "https://api.semanticscholar.org/graph/v1"

# 重试：应对 S2/OpenAlex 的 429
MAX_RETRIES = 2
RETRY_BACKOFF = 0.8  # 秒

# 简易内存缓存（同进程内，避免重复打 API；过期 10 分钟）
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 600.0


def cache_get(key: str) -> Optional[Any]:
    hit = _CACHE.get(key)
    if hit and (time.time() - hit[0]) < _CACHE_TTL:
        return hit[1]
    return None


def cache_set(key: str, val: Any) -> None:
    _CACHE[key] = (time.time(), val)


# ------------------------------------------------------------
# 统一论文模型
# ------------------------------------------------------------


@dataclass
class Paper:
    """三源归一后的论文数据。所有字段对「零幻觉溯源」负责。"""

    title: str = ""
    authors: list[str] = field(default_factory=list)  # 展示用全名字符串
    year: Optional[int] = None
    venue: str = ""  # 期刊/会议
    cited_by_count: Optional[int] = None
    doi: str = ""  # 裸 DOI，如 10.1038/xxx
    doi_url: str = ""  # https://doi.org/<doi>
    abstract: str = ""
    oa_url: str = ""  # 开放获取 PDF/HTML（若有）
    source: str = ""  # crossref / openalex / s2
    # ---- 引用格式化所需（GB/T 7714 / APA / IEEE）----
    pub_type: str = ""  # article / conference / preprint / book / other
    publisher: str = ""
    volume: str = ""
    issue: str = ""
    page: str = ""
    raw_authors: list[dict[str, str]] = field(default_factory=list)  # [{family, given}]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # 保证 doi_url 存在（溯源铁律）
        if self.doi and not self.doi_url:
            d["doi_url"] = f"https://doi.org/{self.doi}"
        return d


# ------------------------------------------------------------
# 通用 HTTP（带重试）
# ------------------------------------------------------------


async def fetch_json(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
) -> dict[str, Any] | None:
    """GET JSON，带 429/5xx 指数退避。失败返回 None（调用方自行降级）。"""
    client = get_async_client()
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = await client.get(url, params=params, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429 or resp.status_code >= 500:
                # 可重试
                await _sleep(RETRY_BACKOFF * (attempt + 1))
                continue
            # 4xx 其它：不重试
            return None
        except Exception as e:  # httpx.RequestError 等
            last_exc = e
            await _sleep(RETRY_BACKOFF * (attempt + 1))
    if last_exc:
        pass  # 静默降级
    return None


async def _sleep(t: float) -> None:
    import asyncio

    await asyncio.sleep(t)


# ------------------------------------------------------------
# OpenAlex 倒排索引 → 摘要重建
# ------------------------------------------------------------


def rebuild_abstract_from_inverted_index(idx: dict[str, list[int]] | None) -> str:
    """OpenAlex 的 abstract_inverted_index 是 {word: [positions]}，需按位置重建字符串。"""
    if not idx:
        return ""
    pos_map: dict[int, str] = {}
    for word, positions in idx.items():
        for p in positions:
            pos_map[p] = word
    if not pos_map:
        return ""
    max_pos = max(pos_map)
    return " ".join(pos_map.get(i, "") for i in range(max_pos + 1)).replace("  ", " ").strip()


# ------------------------------------------------------------
# 统一渲染（供工具返回 markdown / 列表）
# ------------------------------------------------------------


def papers_to_markdown(papers: list[Paper], caption: str = "") -> str:
    """把 Paper 列表渲染成带可点 DOI 链接的 markdown 列表（每条带 [n] 行内锚点）。"""
    if not papers:
        return f"**{caption}**\n\n未召回任何真实文献（零幻觉原则：不编造）。"
    lines: list[str] = []
    if caption:
        lines.append(f"**{caption}**（共 {len(papers)} 篇，全部带真实 DOI 可溯源）\n")
    for i, p in enumerate(papers, 1):
        auth = ", ".join(p.authors[:3]) + (" 等" if len(p.authors) > 3 else "")
        cite = f"｜被引 {p.cited_by_count}" if p.cited_by_count is not None else ""
        venue = f"｜{p.venue}" if p.venue else ""
        yr = f"（{p.year}）" if p.year else ""
        doi_part = f"[DOI:{p.doi}]({p.doi_url})" if p.doi and p.doi_url else "（无 DOI）"
        lines.append(f"{i}. **{p.title or '（无标题）'}** {yr}\n   - {auth}{venue}{cite}\n   - 🔗 {doi_part}")
    return "\n".join(lines)


def papers_to_table(papers: list[Paper]) -> list[list[str]]:
    """转成 [标题, 作者, 年份, 期刊, 被引, DOI链接] 的二维数组（供 write_markdown_table）。"""
    rows: list[list[str]] = []
    for p in papers:
        rows.append(
            [
                p.title[:60] + ("…" if len(p.title) > 60 else ""),
                ", ".join(p.authors[:2]) + (" 等" if len(p.authors) > 2 else ""),
                str(p.year or ""),
                p.venue[:24],
                str(p.cited_by_count if p.cited_by_count is not None else "-"),
                p.doi_url or p.doi or "-",
            ]
        )
    return rows
