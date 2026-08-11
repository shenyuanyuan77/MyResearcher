"""MCP 工具公共 HTTP 辅助。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import httpx
from fastmcp import Context


def get_http_client(ctx: Context) -> httpx.AsyncClient:
    client = ctx.request_context.lifespan_context.get("http_client")
    if client is None:
        raise RuntimeError("HTTP 客户端未初始化，请检查 MCP Server 生命周期")
    return client


async def erp_get(
    ctx: Context,
    path: str,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    """GET Java ERP API，返回 data；失败抛出带可读信息的异常。"""
    http_client = get_http_client(ctx)
    response = await http_client.get(path, params=params or {})
    response.raise_for_status()
    result = response.json()
    if result.get("code") != 200:
        raise RuntimeError(
            f"API error: code={result.get('code')}, message={result.get('message')}"
        )
    return result.get("data")


async def erp_post(ctx: Context, path: str, json_body: Dict[str, Any]) -> Any:
    http_client = get_http_client(ctx)
    response = await http_client.post(path, json=json_body)
    response.raise_for_status()
    result = response.json()
    if result.get("code") != 200:
        raise RuntimeError(
            f"API error: code={result.get('code')}, message={result.get('message')}"
        )
    return result.get("data", {})


async def erp_put(ctx: Context, path: str, json_body: Dict[str, Any]) -> Any:
    http_client = get_http_client(ctx)
    response = await http_client.put(path, json=json_body)
    response.raise_for_status()
    result = response.json()
    if result.get("code") != 200:
        raise RuntimeError(
            f"API error: code={result.get('code')}, message={result.get('message')}"
        )
    return result.get("data", {})


def as_list(data: Any) -> List:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    return [data]


def tool_error(e: Exception) -> List[str]:
    return [f"查询失败: {e}"]


def tool_error_dict(e: Exception) -> Dict[str, str]:
    return {"error": str(e)}
