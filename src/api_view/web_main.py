"""
研途智探AI · FastAPI 主应用。

登录/健康检查不阻塞 Agent 初始化：Agent 在后台加载，
避免 MCP 慢启动时前端登录转圈。
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.settings import settings
from api_view.api import auth_routes, chat, history
from api_view.report_export import router as report_router
from api_view.agent_loader import agent_loader
from api_view.health_deps import collect_dependency_status
from api_view.observability import RequestIdMiddleware, setup_logging
from api_view.runtime_status import runtime_status
from api_view.security_middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from api_view.web_config import API_DESCRIPTION, API_TITLE, API_VERSION

setup_logging()

try:
    settings.validate_startup()
except Exception as e:
    print(f"[FATAL] 配置校验失败: {e}")
    raise


async def _init_agent_background():
    await asyncio.sleep(0.05)
    try:
        print("[Startup] Agent 后台初始化开始...")
        await agent_loader.initialize()
        print(f"[Startup] {API_TITLE} Agent 就绪")
        if runtime_status.degraded:
            print(f"[Startup] 降级模式 warnings={runtime_status.warnings}")
    except Exception as e:
        runtime_status.ready = False
        runtime_status.degraded = True
        runtime_status.warnings.append(f"agent_init_failed: {e}")
        print(f"[Startup] Agent 初始化失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 50)
    print(f"正在启动 {API_TITLE}...")
    print("API 立即可用（/api/auth、/health）；Agent 后台加载中")
    print("=" * 50)
    task = asyncio.create_task(_init_agent_background())
    app.state.agent_init_task = task
    yield
    print("=" * 50)
    print(f"正在关闭 {API_TITLE}...")
    print("=" * 50)
    if not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time-Ms", "Retry-After"],
)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

app.include_router(auth_routes.router, prefix="/api", tags=["认证"])
app.include_router(chat.router, prefix="/api", tags=["对话"])
app.include_router(history.router, prefix="/api", tags=["历史记录"])
app.include_router(report_router, prefix="/api", tags=["报告导出"])


@app.get("/", tags=["首页"])
async def root():
    return {
        "name": API_TITLE,
        "version": API_VERSION,
        "description": API_DESCRIPTION,
        "docs": "/docs",
        "health": "/health",
        "auth_enabled": settings.auth_enabled,
        "agent_ready": runtime_status.ready,
    }


def _health_payload() -> dict:
    deps = collect_dependency_status()
    status_label = "healthy"
    if not runtime_status.ready:
        status_label = "starting"
    elif runtime_status.degraded or deps["degraded"]:
        status_label = "degraded"
    if not deps["critical_ok"] and runtime_status.ready:
        status_label = "unhealthy"
    return {
        "status": status_label,
        "service": API_TITLE,
        "version": API_VERSION,
        "runtime": {
            "ready": runtime_status.ready,
            "degraded": runtime_status.degraded,
            "mcp_academic_ok": runtime_status.mcp_academic_ok,
            "checkpoint_backend": runtime_status.checkpoint_backend,
            "warnings": runtime_status.warnings,
        },
        "config": settings.public_dict(),
        "dependencies": deps["dependencies"],
    }


@app.get("/health", tags=["健康检查"])
async def health():
    return _health_payload()


@app.get("/health/live", tags=["健康检查"])
async def health_live():
    return {"status": "alive"}


@app.get("/health/ready", tags=["健康检查"])
async def health_ready():
    ready = runtime_status.ready
    return {"status": "ready" if ready else "not_ready", "ready": ready}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_view.web_main:app",
        host="0.0.0.0",
        port=settings.backend_port,
        reload=False,
    )
