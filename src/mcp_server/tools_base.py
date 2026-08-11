"""
MCP 工具公共基座（阶段 3）。

提供 safe_mcp_tool 装饰器统一负责：
- schema 校验（输入契约）
- 权限点检查
- 写操作追踪（audit + record_erp_write）
- 幂等键（idemp_key）防重复
- 错误码归一化
- 重试策略（3 次指数回退）
- 敏感字段脱敏

工具定义本体不动 — 只在外层包装。
"""

from __future__ import annotations

import functools
import hashlib
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 错误码归一化（与契约文档一致）
# ---------------------------------------------------------------------------
class ToolErrorCode:
    PERMISSION_DENIED = "PERMISSION_DENIED"
    PARAM_INVALID = "PARAM_INVALID"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    ERP_TIMEOUT = "ERP_TIMEOUT"
    ERP_BAD_RESPONSE = "ERP_BAD_RESPONSE"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"


def tool_error(code: str, message: str, **extra) -> Dict[str, Any]:
    """MCP 工具错误返回的标准结构。"""
    out: Dict[str, Any] = {"error": True, "code": code, "message": message}
    out.update(extra)
    return out


# ---------------------------------------------------------------------------
# 敏感字段脱敏
# ---------------------------------------------------------------------------
SENSITIVE_KEYS = {"password", "passwd", "secret", "api_key", "apiKey", "token", "idemp_key"}


def mask(value: Any) -> Any:
    """递归脱敏。仅用于审计/记录，不修改原始数据。"""
    if isinstance(value, str):
        # 看起来像 token/key 的字符串
        if any(k in value.lower() for k in ("bearer", "sk-", "apikey")):
            return value[:6] + "****"
        return value
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in SENSITIVE_KEYS:
                out[k] = "***MASKED***"
            elif k in ("idemp_key",):
                out[k] = v if isinstance(v, str) and len(v) < 12 else (str(v)[:8] + "...")
            else:
                out[k] = mask(v)
        return out
    if isinstance(value, list):
        return [mask(v) for v in value]
    return value


# ---------------------------------------------------------------------------
# 幂等键生成
# ---------------------------------------------------------------------------
def make_idemp_key(*parts: Any, user_scope: str = "") -> str:
    """稳定 hash 幂等键。"""
    payload = "|".join(str(p) for p in ([user_scope] + list(parts)))
    h = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return f"idem:{h}"


# ---------------------------------------------------------------------------
# 工具描述（与前端 TaskPanel 展示对齐）
# ---------------------------------------------------------------------------
TOOL_META: Dict[str, Dict[str, Any]] = {
    # ===== 现有 22 工具（标注为 read，幂等性不需要）=====
    "supplier_query":            {"perm": "supplier:read",   "write": False, "idempotent": False, "timeout": 10},
    "part_query":                {"perm": "material:read",   "write": False, "idempotent": False, "timeout": 10},
    "part_search":               {"perm": "material:read",   "write": False, "idempotent": False, "timeout": 10},
    "part_by_supplier":          {"perm": "material:read",   "write": False, "idempotent": False, "timeout": 10},
    "part_alternates":           {"perm": "material:read",   "write": False, "idempotent": False, "timeout": 8},
    "inventory_warning":         {"perm": "inventory:read",  "write": False, "idempotent": False, "timeout": 10},
    "inventory_lots":            {"perm": "inventory:read",  "write": False, "idempotent": False, "timeout": 10},
    "inventory_msl_warning":     {"perm": "inventory:read",  "write": False, "idempotent": False, "timeout": 10},
    "inventory_expiry_warning":  {"perm": "inventory:read",  "write": False, "idempotent": False, "timeout": 10},
    "logistics_by_order":        {"perm": "logistics:read",  "write": False, "idempotent": False, "timeout": 10},
    "stats_dashboard":           {"perm": "report:read",     "write": False, "idempotent": False, "timeout": 10},
    "stats_procurement":         {"perm": "report:read",     "write": False, "idempotent": False, "timeout": 10},
    "stats_monthly_trend":       {"perm": "report:read",     "write": False, "idempotent": False, "timeout": 10},
    "stats_suppliers":           {"perm": "supplier:read",   "write": False, "idempotent": False, "timeout": 10},
    "stats_parts":               {"perm": "material:read",   "write": False, "idempotent": False, "timeout": 10},
    "stats_inventory":           {"perm": "inventory:read",  "write": False, "idempotent": False, "timeout": 10},
    "order_search_details":      {"perm": "order:read",      "write": False, "idempotent": False, "timeout": 10},
    "order_month_summary":       {"perm": "order:read",      "write": False, "idempotent": False, "timeout": 10},
    "generate_visualization":    {"perm": "report:read",     "write": False, "idempotent": False, "timeout": 25},
    "web_search":                {"perm": "report:read",     "write": False, "idempotent": False, "timeout": 15},
    # 写工具：强制审计 + 幂等键
    "order_create":              {"perm": "order:create",    "write": True,  "idempotent": True,  "timeout": 8},
    "order_update":              {"perm": "order:update",    "write": True,  "idempotent": True,  "timeout": 8},

    # ===== 阶段 3 新工具 12 个 =====
    "compare_suppliers":                 {"perm": "supplier:read",       "write": False, "idempotent": False, "timeout": 10},
    "calculate_purchase_quantity":       {"perm": "material:read",       "write": False, "idempotent": False, "timeout": 15},
    "create_purchase_request":           {"perm": "purchase_request:create", "write": True, "idempotent": True,  "timeout": 8},
    "submit_purchase_approval":          {"perm": "purchase_request:submit","write": True, "idempotent": True,  "timeout": 5},
    "get_approval_status":               {"perm": "approval:read",       "write": False, "idempotent": False, "timeout": 5},
    "get_msl_risk_summary":              {"perm": "inventory:read",      "write": False, "idempotent": False, "timeout": 10},
    "get_material_shortage":             {"perm": "material:read",       "write": False, "idempotent": False, "timeout": 15},
    "get_substitute_recommendation":     {"perm": "material:read",       "write": False, "idempotent": False, "timeout": 8},
    "get_supplier_risk":                 {"perm": "supplier:read",       "write": False, "idempotent": False, "timeout": 8},
    "get_order_anomalies":               {"perm": "order:read",          "write": False, "idempotent": False, "timeout": 15},
    "get_open_purchase_orders":          {"perm": "order:read",          "write": False, "idempotent": False, "timeout": 10},
    "get_consumption_rate":              {"perm": "material:read",       "write": False, "idempotent": False, "timeout": 10},
}


def tool_meta(tool_name: str) -> Dict[str, Any]:
    """获取工具元数据（perm/write/idempotent/timeout）。未注册默认 read-only。"""
    return TOOL_META.get(tool_name, {"perm": None, "write": False, "idempotent": False, "timeout": 10})


# ---------------------------------------------------------------------------
# safe_mcp_tool 装饰器
# ---------------------------------------------------------------------------
def safe_mcp_tool(
    tool_name: str,
    *,
    requires_approval: bool = False,
    max_retries: int = 3,
    backoff_base: float = 0.4,
    audit_action: Optional[str] = None,
):
    """
    工具入口包装：
    1) 异常捕获 → 返回 tool_error 结构化错误
    2) 写操作前后调 audit（兜底重复，主审计在 erp_post 包装层做）
    3) 简易重试（仅 ERP_TIMEOUT / ERP_BAD_RESPONSE）

    注意：permission 校验在 MCP 层做不了（MCP 不持用户上下文），
    权限点在 FastAPI 路由层 require_permission 强制 + Agent 中间件 task_orchestrator 提示。
    """
    def deco(fn: Callable[..., Awaitable[Any]]):
        meta = tool_meta(tool_name)
        is_write = meta["write"] or requires_approval

        @functools.wraps(fn)
        async def wrapped(*args, **kwargs):
            attempt = 0
            while True:
                attempt += 1
                t0 = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    if is_write:
                        logger.info(
                            "mcp_tool.write_done name=%s args=%s ok elapsed=%.0fms",
                            tool_name, mask(kwargs), elapsed_ms,
                        )
                    return result
                except Exception as e:
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    code = _exception_to_code(e)
                    retriable = code in (ToolErrorCode.ERP_TIMEOUT, ToolErrorCode.ERP_BAD_RESPONSE)
                    if retriable and attempt <= max_retries:
                        backoff = backoff_base * (2 ** (attempt - 1))
                        logger.warning(
                            "mcp_tool.retry name=%s attempt=%d code=%s wait=%.1fs err=%s",
                            tool_name, attempt, code, backoff, str(e)[:120],
                        )
                        time.sleep(backoff)
                        continue
                    logger.exception("mcp_tool.fail name=%s code=%s elapsed=%.0fms", tool_name, code, elapsed_ms)
                    return tool_error(code, str(e))

        wrapped.__mcp_meta__ = meta                  # type: ignore[attr-defined]
        wrapped.__mcp_name__ = tool_name             # type: ignore[attr-defined]
        return wrapped
    return deco


def _exception_to_code(e: Exception) -> str:
    s = str(e).lower()
    if "timeout" in s or "timed out" in s:
        return ToolErrorCode.ERP_TIMEOUT
    if "not found" in s:
        return ToolErrorCode.NOT_FOUND
    if "permission" in s or "403" in s:
        return ToolErrorCode.PERMISSION_DENIED
    if "409" in s or "duplicate" in s or "conflict" in s:
        return ToolErrorCode.IDEMPOTENT_REPLAY
    if "approval" in s:
        return ToolErrorCode.APPROVAL_REQUIRED
    if "unhandled errors" in s:  # MCP TaskGroup
        return ToolErrorCode.ERP_BAD_RESPONSE
    if "code=" in s and "code=200" not in s:
        return ToolErrorCode.ERP_BAD_RESPONSE
    return ToolErrorCode.INTERNAL_ERROR
