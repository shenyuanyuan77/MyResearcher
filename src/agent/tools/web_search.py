"""
网络搜索工具（基于智谱 AI Web Search API）。

用于补充最新资讯/会议截稿/政策等非论文情报（学术文献一律走学术工具）。
KEY 缺失时降级返回提示，避免 import 失败阻断 Agent 启动。
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.tools import tool

from agent.env_utils import ZHIPU_API_KEY


@lru_cache(maxsize=1)
def _client():
    if not ZHIPU_API_KEY:
        return None
    try:
        from zai import ZhipuAiClient

        return ZhipuAiClient(api_key=ZHIPU_API_KEY)
    except Exception:
        return None


@tool("web_search", parse_docstring=True)
def web_search(query: str) -> str:
    """
    使用 Web 搜索获取最新资讯（智谱 search_pro）。

    适用于：会议截稿日期、科研政策、行业资讯、学者最新动态等非论文情报。
    **不适用于**学术文献检索（请用 paper_search / paper_by_doi 等学术工具，保证 DOI 溯源）。

    Args:
        query: 需要搜索的内容或关键字。

    Returns:
        搜索结果文本；未配置 Key 或失败时给出降级提示。
    """
    cli = _client()
    if cli is None:
        return (
            "网络搜索未启用（未配置 ZHIPU_API_KEY）。"
            "学术文献请直接使用 paper_search / paper_by_doi / author_profile 等学术工具。"
        )
    try:
        response = cli.web_search.web_search(
            search_engine="search_pro",
            search_query=query,
            count=3,
            search_recency_filter="noLimit",
        )
        if response.search_result:
            return "\n\n".join([d.content for d in response.search_result])
        return "没有搜索到任何内容！"
    except Exception as e:
        return f"搜索失败: {e}"
