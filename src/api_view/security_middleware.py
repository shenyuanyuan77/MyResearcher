"""
安全中间件：安全响应头 + API 全局限流。

限流后端抽象：默认进程内内存（单实例）；生产多实例可配 RATELIMIT_BACKEND=redis +
REDIS_URL 走 Redis 共享计数（自动回退内存）。
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict, Optional, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from agent.settings import settings

# 限流白名单：探活与文档
_RATE_LIMIT_SKIP: Set[str] = {
    "/",
    "/health",
    "/health/live",
    "/health/ready",
    "/docs",
    "/openapi.json",
    "/redoc",
}

# 内存限流器的 IP 表上限（避免攻击者用海量伪造 IP 耗尽内存）
_MAX_TRACKED_IPS = 10_000


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class _MemoryRateLimiter:
    """进程内滑动窗口限流（单实例）。"""

    def __init__(self):
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    async def allow(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        now = time.time()
        # 上限保护：超过跟踪上限时清空最旧（粗粒度防 OOM）
        if len(self._hits) > _MAX_TRACKED_IPS:
            self._hits.clear()
        q = self._hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False, window
        q.append(now)
        return True, 0


class _RedisRateLimiter:
    """Redis 共享限流（多实例）。惰性初始化，连接失败自动回退内存。"""

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._client = None
        self._fallback = _MemoryRateLimiter()
        self._init_error: Optional[str] = None

    async def _ensure_client(self):
        if self._client is not None or self._init_error:
            return self._client
        try:
            import redis.asyncio as aioredis  # type: ignore
            self._client = aioredis.from_url(
                self._redis_url, decode_responses=True, socket_connect_timeout=2
            )
            await self._client.ping()
        except Exception as e:
            self._init_error = str(e)
            import logging
            logging.getLogger(__name__).warning(
                "Redis 限流后端不可用，回退到内存限流：%s", e
            )
        return self._client

    async def allow(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        client = await self._ensure_client()
        if client is None:
            return await self._fallback.allow(key, limit, window)
        try:
            import time as _t
            rk = f"rl:{key}:{int(_t.time() // window)}"
            pipe = client.pipeline()
            pipe.incr(rk)
            pipe.expire(rk, window)
            results = await pipe.execute()
            count = int(results[0])
            return (count <= limit, window)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Redis 限流失败，回退内存：%s", e)
            return await self._fallback.allow(key, limit, window)


def _build_rate_limiter():
    """根据 RATELIMIT_BACKEND 构建限流器。redis 失败自动回退内存。"""
    import os
    backend = os.getenv("RATELIMIT_BACKEND", "memory").strip().lower()
    if backend == "redis":
        redis_url = os.getenv("REDIS_URL", "").strip()
        if redis_url:
            return _RedisRateLimiter(redis_url)
    return _MemoryRateLimiter()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """基础安全响应头（API 场景，无 CSP 强约束以免破坏 /docs）。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        if not settings.security_headers_enabled:
            return response
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        response.headers.setdefault("X-XSS-Protection", "0")
        # API 默认不缓存敏感响应
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """按 IP 滑动窗口限流（内存 / Redis 可选）。"""

    def __init__(self, app):
        super().__init__(app)
        self._limiter = _build_rate_limiter()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        if path in _RATE_LIMIT_SKIP or path.startswith("/docs"):
            return await call_next(request)

        ip = _client_ip(request)
        window = settings.rate_limit_window_sec
        limit = settings.rate_limit_max_requests
        allowed, retry = await self._limiter.allow(ip, limit, window)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "code": "RATE_LIMITED",
                    "message": "请求过于频繁，请稍后再试",
                    "detail": f"limit={limit}/{window}s ip={ip}",
                    "retry_after_sec": retry or window,
                },
                headers={"Retry-After": str(retry or window)},
            )
        return await call_next(request)

