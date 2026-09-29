"""
MyResearcher · 主 Agent 入口。

使用 DeepAgents `create_deep_agent` 将五大引擎工具 + 2 个子 Agent 串联为
可运行的「科研导师」。采用 async graph factory 模式。

与采购助手的关键差异：去 opensandbox（无需代码执行）、去 MongoDB（SQLite checkpoint）。
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Optional

from deepagents import create_deep_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)
from langchain_core.runnables import RunnableConfig

from agent.config import (
    AGENTS_MD_FILENAME,
    CHECKPOINTER,
    DOWNLOAD_DIR,
    LOCAL_AGENTS_MD,
    SKILLS_STORE_NAMESPACE,
    STORE,
    SUMMARY_MODEL,
    MAIN_MODEL,
    ensure_checkpointer,
)
from agent.memory.prompts import system_prompt
from agent.middlewares.context_injection import ContextInjectionMiddleware
from agent.middlewares.ensure_tool_call_pairs import EnsureToolCallPairsMiddleware
from agent.middlewares.memory_update import MemoryUpdateMiddleware
from agent.middlewares.tools_summarization import build_summarization_middleware
from agent.schema import ResearchContext
from agent.subagents.loader import load_subagent_configs, resolve_subagent_tools
from agent.tools.emit_research_report import emit_research_report
from agent.tools.research_skills import load_research_skill
from agent.tools.system_date import get_system_date
from agent.tools.mcp_client import load_mcp_tools
from agent.tools.save_report_locally import create_save_report_tool
from agent.tools.web_search import web_search
from agent.tools.write_markdown_table import write_markdown_table


def _setup_logging() -> None:
    env = os.environ.get("APP_ENV", "development")
    if env == "production":
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            filename="logs/yanjiu_agent.log",
            filemode="a",
        )
    else:
        logging.basicConfig(
            level=logging.ERROR,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stdout,
        )


_setup_logging()
logger = logging.getLogger(__name__)


async def create_main_agent(config: Optional[RunnableConfig] = None):
    """创建MyResearcher科研导师 Agent。"""
    logger.info("=== 开始创建MyResearcher 科研导师 ===")

    from agent.settings import settings
    from api_view.runtime_status import runtime_status

    runtime_status.warnings.clear()

    # ---- Phase 1: 加载学术 MCP 工具 ----
    logger.info("Phase 1: 加载学术 MCP 工具...")
    try:
        all_mcp_tools, academic_tools = await load_mcp_tools()
        runtime_status.mcp_academic_ok = len(academic_tools) > 0
        if not runtime_status.mcp_academic_ok:
            runtime_status.degraded = True
            runtime_status.warnings.append("学术 MCP 工具未加载（将无法检索文献）")
    except Exception:
        logger.exception("学术 MCP 工具加载失败")
        if settings.require_mcp and not settings.allow_degraded_start:
            raise
        all_mcp_tools, academic_tools = [], []
        runtime_status.degraded = True
        runtime_status.warnings.append("MCP 全部不可用，以降级模式启动")
        runtime_status.mcp_academic_ok = False

    # ---- Phase 2: 本地工具 ----
    logger.info("Phase 2: 构建本地工具池...")
    save_report_locally = create_save_report_tool(DOWNLOAD_DIR)
    available_tools = (
        list(academic_tools)
        + [web_search, get_system_date]
        + [write_markdown_table, emit_research_report, save_report_locally]
        + [load_research_skill]
    )
    logger.info("  工具池: %d 个工具", len(available_tools))

    # ---- Phase 3: 子 Agent YAML 加载与解析 ----
    logger.info("Phase 3: 加载子 Agent 配置...")
    raw_configs = load_subagent_configs()
    subagents = resolve_subagent_tools(raw_configs, available_tools)
    logger.info("  已解析 %d 个子 Agent", len(subagents))

    # ---- Phase 4: 中间件栈 ----
    logger.info("Phase 4: 构建中间件栈...")
    # 摘要中间件：backend=None 时仅做内存级历史压缩。
    # 完整对话状态由 SQLite checkpointer 持久化；用户偏好/伴随式成长由
    # MemoryUpdateMiddleware + STORE(SqliteStore) 持久化，与此独立。
    try:
        summarization_mw = build_summarization_middleware(None, SUMMARY_MODEL)
    except Exception:
        summarization_mw = None

    main_middleware = [
        ContextInjectionMiddleware(),
        MemoryUpdateMiddleware(model=SUMMARY_MODEL),
        ModelCallLimitMiddleware(run_limit=50),
        ToolCallLimitMiddleware(run_limit=200),
        EnsureToolCallPairsMiddleware(),
    ]
    if summarization_mw is not None:
        # 摘要放靠前，ensure_tool_call_pairs 在其后补齐
        main_middleware.insert(1, summarization_mw)

    # ---- Phase 5: checkpointer ----
    logger.info("Phase 5: 初始化 checkpointer...")
    checkpointer = await ensure_checkpointer()

    # ---- Phase 6: create_deep_agent ----
    logger.info("Phase 6: 创建 Deep Agent...")
    # 主 Agent 快速查询工具：覆盖常用只读学术工具，避免简单检索误委派子 Agent
    quick_query_names = {
        "topic_radar",
        "paper_search",
        "paper_by_doi",
        "paper_distill",
        "author_profile",
        "cross_search",
    }
    quick_query_tools = [
        t for t in available_tools if getattr(t, "name", None) in quick_query_names
    ]
    logger.info(
        "  主 Agent 快速查询工具: %s",
        [getattr(t, "name", "?") for t in quick_query_tools],
    )

    # 构建 memory 列表（AGENTS.md 文件存在时）
    memory_files = []
    if LOCAL_AGENTS_MD.exists():
        memory_files = [AGENTS_MD_FILENAME]

    agent_graph = create_deep_agent(
        model=MAIN_MODEL,
        system_prompt=system_prompt,
        memory=memory_files,
        tools=[
            web_search,
            get_system_date,
            write_markdown_table,
            emit_research_report,
            save_report_locally,
            load_research_skill,
            *quick_query_tools,
        ],
        subagents=subagents,
        middleware=main_middleware,
        store=STORE,
        checkpointer=checkpointer,
        context_schema=ResearchContext,
    )

    logger.info("=== MyResearcher 科研导师创建完成 ===")
    runtime_status.ready = True
    return agent_graph


# ============================================================
# Agent 懒加载代理（兼容同步/异步）
# ============================================================


async def _create_agent():
    return await create_main_agent()


class _AgentProxy:
    """懒加载 Agent 代理类。"""

    def __init__(self):
        self._agent = None

    @property
    def _is_initialized(self):
        return self._agent is not None

    def _ensure_initialized(self):
        if self._agent is not None:
            return self._agent
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                raise RuntimeError(
                    "Agent 尚未初始化且当前在事件循环中，请使用 await get_agent_async()"
                )
        except RuntimeError as e:
            if "Agent 尚未初始化" in str(e):
                raise
        self._agent = asyncio.run(_create_agent())
        return self._agent

    def __getattr__(self, name):
        return getattr(self._ensure_initialized(), name)

    def __repr__(self):
        if self._agent is None:
            return "<AgentProxy (not initialized)>"
        return repr(self._agent)


agent = _AgentProxy()


def get_agent():
    """同步获取 agent（不能在运行中的事件循环内调用）。"""
    global agent
    if isinstance(agent, _AgentProxy):
        if agent._is_initialized:
            return agent._agent
        return agent._ensure_initialized()
    return agent


async def get_agent_async():
    """异步获取 agent（适用于 FastAPI lifespan）。"""
    global agent
    if isinstance(agent, _AgentProxy):
        if agent._is_initialized:
            return agent._agent
        agent._agent = await _create_agent()
        return agent._agent
    return agent
