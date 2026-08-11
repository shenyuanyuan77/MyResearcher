"""
可观测性：请求 ID、结构化日志、审计日志。
"""

from __future__ import annotations

import json
import logging
import logging.handlers
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

# 审计日志轮转：单文件最大 10MB，保留 5 份历史，避免无限增长
_AUDIT_ROTATOR = logging.handlers.RotatingFileHandler(
    _AUDIT_FILE,
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
_AUDIT_ROTATOR.setFormatter(logging.Formatter("%(message)s"))
_AUDIT_LOGGER = logging.getLogger("api.audit")
_AUDIT_LOGGER.setLevel(logging.INFO)
_AUDIT_LOGGER.propagate = False
if not _AUDIT_LOGGER.handlers:
    _AUDIT_LOGGER.addHandler(_AUDIT_ROTATOR)


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
    # 学术场景结构化字段
    thread_id: Optional[str] = None,
    tool: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[Any] = None,
    before: Optional[Any] = None,
    after: Optional[Any] = None,
    task_id: Optional[str] = None,
) -> None:
    """
    写入审计日志（学术敏感操作：检索/导出/会话变更/库收藏等）。

    结构化字段：
    - thread_id: 会话 ID
    - tool: 触发的 MCP 工具名（如 paper_search / paper_distill）
    - entity_type/entity_id: 操作实体类型与主键（如 library/<doi>）
    - before/after: 改前/改后字段快照（便于回溯）
    - task_id: 子代理任务 ID
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
    for key, val in [("thread_id", thread_id), ("tool", tool),
                     ("entity_type", entity_type), ("entity_id", entity_id),
                     ("before", before), ("after", after),
                     ("task_id", task_id)]:
        if val is not None:
            payload[key] = val
    try:
        _AUDIT_LOGGER.info(json.dumps(payload, ensure_ascii=False, default=str))
    except Exception:
        logging.getLogger(__name__).exception("写入审计日志失败")
