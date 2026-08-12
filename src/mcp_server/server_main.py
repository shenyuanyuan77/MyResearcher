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
    paper_by_dois as _paper_by_dois,
    paper_distill as _paper_distill,
    paper_search as _paper_search,
    paper_cited_by as _paper_cited_by,
    paper_references as _paper_references,
    related_papers as _related_papers,
    topic_radar as _topic_radar,
)
from mcp_server.tools.cn_sources import paper_search_cn as _paper_search_cn
from mcp_server.tools.artifact_sources import dataset_search as _dataset_search, code_search as _code_search


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
        query: str,
        rows: int = 10,
        year_from: int = 0,
        year_to: int = 0,
        pub_type: str = "",
        oa_only: bool = False,
        min_citations: int = 0,
        sort: str = "cited",
        exclude_retracted: bool = True,
    ) -> dict:
        """
        ②【情报提纯·核心干货引擎】按主题/关键词召回真实学术文献（多源归并去重）。
        每篇均带真实 DOI 与 doi_url，可点击溯源。撤稿论文默认过滤。

        Args:
            query: 检索词/主题
            rows: 召回篇数，默认10，上限40
            year_from: 起始年份（0=不限）
            year_to: 截止年份（0=不限）
            pub_type: 文献类型过滤：article/conference/preprint/book/chapter（空=不限）
            oa_only: 仅返回开放获取文献（默认 False）
            min_citations: 最低引用数过滤（0=不限）
            sort: 排序：cited（引用数，默认）/ newest（新近）/ relevance（相关）
            exclude_retracted: 过滤撤稿论文（默认 True）
        """
        yf = int(year_from) if year_from else None
        yt = int(year_to) if year_to else None
        mc = int(min_citations) if min_citations else None
        return await _paper_search(
            query, rows=rows, year_from=yf, year_to=yt,
            pub_type=(pub_type or None), oa_only=bool(oa_only),
            min_citations=mc, sort=sort, exclude_retracted=bool(exclude_retracted),
        )

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

    @server.tool(name="paper_by_dois")
    async def paper_by_dois(dois: list[str]) -> dict:
        """
        ②【情报提纯·批量 DOI 核验】输入 DOI 列表，批量返回真实文献信息。
        用于从 EndNote/Mendeley 导出的 DOI 列表批量核验引用真实性。

        Args:
            dois: DOI 数组，如 ["10.1038/xxx", "10.1109/yyy"]
        """
        return await _paper_by_dois(dois)

    @server.tool(name="paper_cited_by")
    async def paper_cited_by(identifier: str, rows: int = 10) -> dict:
        """
        ②【情报提纯·施引文献】查找谁引用了这篇论文（OpenAlex）。
        用于追踪某篇论文的后续影响。

        Args:
            identifier: DOI（如 10.1038/xxx）或 OpenAlex ID（如 W123456789）
            rows: 返回篇数，默认10
        """
        return await _paper_cited_by(identifier, rows=rows)

    @server.tool(name="paper_references")
    async def paper_references(identifier: str, rows: int = 10) -> dict:
        """
        ②【情报提纯·参考文献】查找这篇论文引用了谁（OpenAlex）。
        用于深入理解论文的理论基础。

        Args:
            identifier: DOI 或 OpenAlex ID
            rows: 返回篇数，默认10
        """
        return await _paper_references(identifier, rows=rows)

    @server.tool(name="related_papers")
    async def related_papers(identifier: str, rows: int = 10) -> dict:
        """
        ②【情报提纯·相关文献】查找 OpenAlex 标注的相关论文。
        用于扩展阅读范围。

        Args:
            identifier: DOI 或 OpenAlex ID
            rows: 返回篇数，默认10
        """
        return await _related_papers(identifier, rows=rows)

    @server.tool(name="paper_search_cn")
    async def paper_search_cn(query: str, rows: int = 10, year_from: int = 0, translate: bool = True) -> dict:
        """
        ②【情报提纯·中文文献检索】中文关键词召回中文学术文献（S2/OpenAlex CJK）。
        可选自动翻译为英文补充检索三源。CNKI/万方需授权配置（见 .env CNKI_API_TOKEN）。

        Args:
            query: 中文检索词，如「联邦学习 医疗影像」
            rows: 召回篇数，默认10
            year_from: 起始年份（0=不限）
            translate: 是否翻译为英文补充检索（默认 True）
        """
        yf = int(year_from) if year_from else None
        return await _paper_search_cn(query, rows=rows, year_from=yf, translate=bool(translate))

    @server.tool(name="dataset_search")
    async def dataset_search(query: str, rows: int = 10) -> dict:
        """
        ②【情报提纯·数据集检索】检索公开数据集（Zenodo + PapersWithCode）。
        用于找实验所需的公开数据集。

        Args:
            query: 数据集关键词，如「image classification」「medical imaging」
            rows: 召回数，默认10
        """
        return await _dataset_search(query, rows=rows)

    @server.tool(name="code_search")
    async def code_search(query: str, rows: int = 10) -> dict:
        """
        ②【情报提纯·代码检索】检索开源代码实现（GitHub + PapersWithCode）。
        用于找论文的开源实现或 baseline 代码。

        Args:
            query: 代码关键词，如「transformer pytorch」「resnet implementation」
            rows: 召回数，默认10
        """
        return await _code_search(query, rows=rows)


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
