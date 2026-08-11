"""
研途智探AI · Agent 配置中心。

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

# ---------- Store（用户偏好 / 记忆）----------
STORE = InMemoryStore()

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
