"""
MyResearcher · Agent 配置中心。

精简自采购助手：
  - 去掉 opensandbox（研途场景无需代码执行）
  - 去掉 MongoDB（默认 SQLite checkpoint，进程重启可保留会话）
"""

from __future__ import annotations

from pathlib import Path

from langchain_openai import ChatOpenAI
from langgraph.store.memory import InMemoryStore

from agent.env_utils import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    ZHIPU_API_KEY,
    ZHIPU_BASE_URL,
)
from agent.settings import settings
# ---------- 路径常量 ----------
EXAMPLE_DIR = Path(__file__).parent.parent
DOWNLOAD_DIR = EXAMPLE_DIR / "download"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_SUBAGENT_CONFIG_DIR = EXAMPLE_DIR / "agent/subagents"
LOCAL_AGENTS_MD = EXAMPLE_DIR / "agent/memory/AGENTS.md"

AGENTS_MD_FILENAME = "/AGENTS.md"
USER_PREFERENCES_FILENAME = "preferences.md"

PERSISTED_SKILLS_ROOT = "/persisted-skills"
SKILLS_STORE_NAMESPACE = ("skills",)
SCOPE_MAP = {
    "main": "main",
    "literature-analyst": "literature",
    "review-expert": "review",
}

# ---------- 模型配置 ----------
_common_kwargs = dict(
    openai_api_key=DEEPSEEK_API_KEY or settings.deepseek_api_key,
    openai_api_base=DEEPSEEK_BASE_URL or settings.deepseek_base_url,
    max_tokens=8192,
)

MAIN_MODEL = ChatOpenAI(model=settings.main_model, temperature=0.7, **_common_kwargs)
SUMMARY_MODEL = ChatOpenAI(model=settings.summary_model, temperature=0.2, **_common_kwargs)

# 智谱 fallback（仅当 DeepSeek 失败时由上层显式切换；这里不强制）
FALLBACK_BASE_URL = ZHIPU_BASE_URL or settings.zhipu_base_url
FALLBACK_API_KEY = ZHIPU_API_KEY or settings.zhipu_api_key

# ---------- Store（用户偏好 / 记忆 / 伴随式成长）----------
# 持久化：默认同步 SqliteStore（data/memory.sqlite），env MEMORY_BACKEND=memory 可回退内存。
# 同步 Store 可靠稳定；memory_update.py / load_research_context 通过 asyncio.to_thread 包装异步调用。
import os as _os

_MEMORY_BACKEND = _os.getenv("MEMORY_BACKEND", "sqlite").strip().lower()
_MEMORY_SQLITE_PATH = Path(__file__).resolve().parents[2] / "data" / "memory.sqlite"

if _MEMORY_BACKEND == "memory":
    STORE = InMemoryStore()
    _STORE_BACKEND = "memory"
else:
    try:
        from langgraph.store.sqlite import SqliteStore
        _MEMORY_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3 as _sqlite3
        _store_conn = _sqlite3.connect(str(_MEMORY_SQLITE_PATH), check_same_thread=False)
        STORE = SqliteStore(conn=_store_conn)
        try:
            STORE.setup()
        except Exception:
            pass  # 表可能已存在
        _STORE_BACKEND = "sqlite"
    except Exception as _store_err:
        print(f"[WARNING] SqliteStore 初始化失败，降级内存 Store：{_store_err}")
        STORE = InMemoryStore()
        _STORE_BACKEND = "memory"


async def ensure_store():
    """Store 已在模块加载时同步初始化。此函数为兼容 lifespan 启动钩子保留，
    返回当前 STORE 实例并更新 runtime_status。"""
    try:
        from api_view.runtime_status import runtime_status
        runtime_status.store_backend = _STORE_BACKEND
    except Exception:
        pass
    return STORE


async def store_aget(namespace: tuple, key: str):
    """异步包装同步 Store.get（避免 AsyncSqliteStore 的事务陷阱）。"""
    import asyncio
    return await asyncio.to_thread(STORE.get, namespace, key)


async def store_aput(namespace: tuple, key: str, value) -> None:
    """异步包装同步 Store.put。"""
    import asyncio
    await asyncio.to_thread(STORE.put, namespace, key, value)


async def store_adelete(namespace: tuple, key: str) -> None:
    """异步包装同步 Store.delete。"""
    import asyncio
    await asyncio.to_thread(STORE.delete, namespace, key)

# ---------- Checkpointer（SQLite，异步初始化）----------
_CHECKPOINT_SQLITE_PATH = Path(__file__).resolve().parents[2] / "data" / "checkpoints.sqlite"
_sqlite_conn = None  # aiosqlite 连接，保持存活
CHECKPOINTER = None


async def ensure_checkpointer():
    """异步初始化 AsyncSqliteSaver；失败降级到内存。"""
    global CHECKPOINTER, _sqlite_conn

    if CHECKPOINTER is not None:
        return CHECKPOINTER

    try:
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        _CHECKPOINT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _sqlite_conn = await aiosqlite.connect(str(_CHECKPOINT_SQLITE_PATH))
        CHECKPOINTER = AsyncSqliteSaver(_sqlite_conn)
        await CHECKPOINTER.setup()
        print(f"[INFO] SQLite checkpointer 就绪: {_CHECKPOINT_SQLITE_PATH}")
        try:
            from api_view.runtime_status import runtime_status

            runtime_status.checkpoint_backend = "sqlite"
        except Exception:
            pass
        return CHECKPOINTER
    except Exception as sqlite_err:
        from langgraph.checkpoint.memory import InMemorySaver

        print(f"[WARNING] SQLite checkpoint 失败，降级为内存模式: {sqlite_err}")
        CHECKPOINTER = InMemorySaver()
        try:
            from api_view.runtime_status import runtime_status

            runtime_status.checkpoint_backend = "memory"
            runtime_status.degraded = True
            runtime_status.warnings.append(
                "checkpoint 使用内存模式：进程重启后会话状态会丢失"
            )
        except Exception:
            pass
        return CHECKPOINTER
