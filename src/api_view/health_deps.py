"""
研途智探AI · 服务依赖健康探测（学术 MCP）。
精简版：仅探测 MCP（去 sandbox/mongo/java_erp）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from agent.settings import settings

logger = logging.getLogger(__name__)


def _check_mcp() -> Dict[str, Any]:
    """MCP streamable HTTP：能连通即视为存活（GET 可能 405/406）。"""
    url = settings.mcp_academic_url
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(url)
            return {"ok": resp.status_code < 500, "status_code": resp.status_code, "url": url}
    except Exception as e:
        return {"ok": False, "error": str(e), "url": url}


def collect_dependency_status() -> Dict[str, Any]:
    """快速探测依赖；单项失败不影响整体返回。"""
    deps: Dict[str, Any] = {}
    try:
        deps["academic_mcp"] = _check_mcp()
    except Exception as e:
        deps["academic_mcp"] = {"ok": False, "error": str(e)}

    critical_ok = True
    if settings.require_mcp:
        critical_ok = critical_ok and deps["academic_mcp"].get("ok", False)

    degraded = not deps["academic_mcp"].get("ok", False)
    return {"dependencies": deps, "critical_ok": critical_ok, "degraded": degraded}
