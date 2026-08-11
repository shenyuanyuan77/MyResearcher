"""
可观测性：请求 ID、结构化日志、审计日志。
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from agent.settings import settings

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="-")

_AUDIT_DIR = Path(__file__).resolve().parents[2] / "logs"
_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
_AUDIT_FILE = _AUDIT_DIR / "audit.jsonl"


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("-")
        record.user_id = user_id_ctx.get("-")
        return True


def setup_logging() -> None:
    """配置带 request_id / user_id 的结构化日志。"""
    root = logging.getLogger()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | rid=%(request_id)s | uid=%(user_id)s | "
        "%(name)s | %(message)s"
    )
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(fmt)
        handler.addFilter(RequestContextFilter())
        root.addHandler(handler)
    else:
        for h in root.handlers:
            h.setFormatter(fmt)
            h.addFilter(RequestContextFilter())


class RequestIdMiddleware(BaseHTTPMiddleware):
    """为每个请求注入 X-Request-ID，并记录耗时。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            request_id_ctx.reset(token)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
        logging.getLogger("api.access").info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


def write_audit(
    action: str,
    *,
    user_id: Optional[str] = None,
    detail: Optional[dict] = None,
    success: bool = True,
    # 结构化写操作字段（阶段 2 新增，向后兼容旧调用）
    entity_type: Optional[str] = None,
    entity_id: Optional[Any] = None,
    before: Optional[Any] = None,
    after: Optional[Any] = None,
    erp_action_id: Optional[str] = None,
    approval_id: Optional[str] = None,
    task_id: Optional[str] = None,
    idemp_key: Optional[str] = None,
) -> None:
    """
    写入审计日志（订单/审批/写工具调用等敏感操作）。

    新增结构化字段（向后兼容）：
    - entity_type/entity_id: 操作实体类型与主键（如 order/123）
    - before/after: 改前/改后字段快照（便于回溯）
    - erp_action_id: ERP 写操作调用 ID（与 task_id 一般不同）
    - approval_id: 关联审批中心记录
    - idemp_key: 幂等键
    """
    if not settings.audit_log_enabled:
        return
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id_ctx.get("-"),
        "user_id": user_id or user_id_ctx.get("-"),
        "action": action,
        "success": success,
        "detail": detail or {},
    }
    # 仅在有值时写入结构化字段，避免日志膨胀
    for key, val in [("entity_type", entity_type), ("entity_id", entity_id),
                     ("before", before), ("after", after),
                     ("erp_action_id", erp_action_id), ("approval_id", approval_id),
                     ("task_id", task_id), ("idemp_key", idemp_key)]:
        if val is not None:
            payload[key] = val
    try:
        with _AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception:
        logging.getLogger(__name__).exception("写入审计日志失败")
