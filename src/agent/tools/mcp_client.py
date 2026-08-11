"""
学术 MCP 工具加载器。

连接学术 MCP 服务（streamable_http），加载五大引擎工具。
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.env_utils import MCP_ACADEMIC_URL, MCP_API_KEY
from agent.settings import settings

logger = logging.getLogger(__name__)


def default_mcp_server_config() -> dict:
    """构建学术 MCP server 配置。"""
    headers: dict[str, str] = {}
    if MCP_API_KEY or settings.mcp_api_key:
        headers["Authorization"] = f"Bearer {MCP_API_KEY or settings.mcp_api_key}"
    return {
        "academic-api": {
            "url": MCP_ACADEMIC_URL or settings.mcp_academic_url,
            "transport": "streamable_http",
            **({"headers": headers} if headers else {}),
        }
    }


MCP_SERVER_CONFIG = default_mcp_server_config()


async def load_mcp_tools(server_config: dict | None = None) -> Tuple[List, List]:
    """
    加载学术 MCP 工具。

    Returns:
        (all_tools, academic_tools)：全部工具 + 学术工具分组（MVP 单服务，二者相同）
    """
    cfg = server_config or MCP_SERVER_CONFIG
    try:
        client = MultiServerMCPClient(cfg)
        academic_tools = await client.get_tools(server_name="academic-api")
        logger.info("学术 MCP 工具加载完成：%s", [t.name for t in academic_tools])
        all_tools = list(academic_tools)
        return all_tools, academic_tools
    except Exception as e:
        logger.exception("学术 MCP 工具加载失败")
        if settings.require_mcp and not settings.allow_degraded_start:
            raise RuntimeError(f"学术 MCP 工具加载失败，无法创建 Agent: {e}")
        return [], []
