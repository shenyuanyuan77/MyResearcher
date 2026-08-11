"""
研途智探AI · 学术数据 MCP 服务

五大引擎对 Agent 暴露的学术工具：
  topic_radar      ① 方向构建（领域热度 + 关键词 + 检索式）
  paper_search     ② 情报提纯（多源召回真实 DOI 文献）
  paper_by_doi     ② 单篇 DOI 精确溯源
  paper_distill    ② 精读单篇
  author_profile   ③ 资产透视（学者画像）
  cross_search     ④ 跨界启发（交叉工作）

数据源：CrossRef（权威 DOI）+ OpenAlex（富数据）+ Semantic Scholar（摘要兜底）
全部免费、无需 Key；返回结构统一带真实 DOI，是「零幻觉溯源」基石。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastmcp import FastMCP

from mcp_server.server_config import MCP_HOST, MCP_PORT, MCP_PATH
from mcp_server.tools import unified
from mcp_server.tools.academic import (
    author_profile as _author_profile,
    cross_search as _cross_search,
    paper_by_doi as _paper_by_doi,
    paper_distill as _paper_distill,
    paper_search as _paper_search,
    topic_radar as _topic_radar,
)


@asynccontextmanager
async def mcp_lifespan(server: FastMCP):
    """生命周期：预热 HTTP 客户端，关闭时清理。"""
    # 触发进程级客户端创建（academic 工具内部使用）
    _ = unified.get_async_client()
    try:
        yield {"status": "ok"}
    finally:
        client = unified._client
        if client is not None and not client.is_closed:
            await client.aclose()
            unified._client = None


mcp = FastMCP(
    name="YanJiuZhiTan-Academic-MCP",
    instructions=(
        "研途智探学术数据工具集。所有工具返回真实学术数据（带 DOI），"
        "禁止编造未召回的文献。调用方应将 doi_url 作为溯源指针展示给用户。"
    ),
    version="1.0.0",
    lifespan=mcp_lifespan,
)


def register_academic_tools(server: FastMCP) -> None:
    """注册五大引擎学术工具。"""

    @server.tool(name="topic_radar")
    async def topic_radar(topic: str) -> dict:
        """
        ①【方向构建·专属雷达配置】输入研究方向（自然语言），输出领域热度趋势、
        核心关键词、推荐检索式与高引代表作。用于科研选题与方向规划。

        Args:
            topic: 研究方向/主题，如「大模型思维链与机器人控制结合」
        """
        return await _topic_radar(topic)

    @server.tool(name="paper_search")
    async def paper_search(
        query: str, rows: int = 10, year_from: int = 0
    ) -> dict:
        """
        ②【情报提纯·核心干货引擎】按主题/关键词召回真实学术文献（多源归并去重）。
        每篇均带真实 DOI 与 doi_url，可点击溯源。用于文献检索与综述素材收集。

        Args:
            query: 检索词/主题，如「retrieval augmented generation survey」
            rows: 召回篇数，默认10，上限40
            year_from: 仅保留该年及之后发表的（0 表示不限制）
        """
        yf = int(year_from) if year_from else None
        return await _paper_search(query, rows=rows, year_from=yf)

    @server.tool(name="paper_by_doi")
    async def paper_by_doi(doi: str) -> dict:
        """
        ②【情报提纯·DOI 精确溯源】按裸 DOI（或 doi.org 链接）取单篇权威文献信息。
        DOI 来自 CrossRef（全球 DOI 注册机构），最权威可信。用于核验引用真实性。

        Args:
            doi: 裸 DOI（如 10.1038/s41586-021-03819-2）或完整 doi.org 链接
        """
        return await _paper_by_doi(doi)

    @server.tool(name="paper_distill")
    async def paper_distill(identifier: str) -> dict:
        """
        ②【情报提纯·沉浸式精读】输入标题或 DOI，返回单篇结构化精读要点：
        标题/作者/年份/期刊/被引/真实摘要/可引用格式。用于快速吃透一篇文献。

        Args:
            identifier: 文献标题或 DOI
        """
        return await _paper_distill(identifier)

    @server.tool(name="author_profile")
    async def author_profile(name: str, institution: str = "") -> dict:
        """
        ③【资产透视·学者资产雷达】输入学者姓名（可选机构），返回学者画像：
        h 指数、论文数、被引、代表作 Top-K、研究主题分布。用于导师选择/学者调研。

        Args:
            name: 学者姓名（中文或英文），如「Jason Wei」「李飞飞」
            institution: 机构名（可选，用于消歧），如「Stanford」
        """
        return await _author_profile(name, institution or None)

    @server.tool(name="cross_search")
    async def cross_search(domain_a: str, domain_b: str, limit: int = 8) -> dict:
        """
        ④【跨界启发·边界推演实验室】检索两个领域已存在的交叉工作（真实文献），
        为融合可行性评估提供佐证。融合推演本身由主模型完成。

        Args:
            domain_a: 领域 A，如「large language model」
            domain_b: 领域 B，如「quantum computing」
            limit: 召回交叉工作数，默认8，上限20
        """
        return await _cross_search(domain_a, domain_b, limit=limit)


register_academic_tools(mcp)


def main() -> None:
    print(f"[研途智探] 学术 MCP 启动 → http://{MCP_HOST}:{MCP_PORT}{MCP_PATH}")
    if MCP_HOST not in {"127.0.0.1", "localhost", "::1"}:
        print(
            f"[SECURITY] MCP 监听 {MCP_HOST}，建议仅绑定 127.0.0.1"
        )
    mcp.run(
        transport="streamable-http", host=MCP_HOST, port=MCP_PORT, path=MCP_PATH
    )


if __name__ == "__main__":
    main()
