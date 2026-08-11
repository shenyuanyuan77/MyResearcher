"""
运行时上下文注入中间件。

从 runtime.context（ProcurementContext）中提取 user_id / username，
并注入**本轮硬分流裁定**（单一真相源：agent.intent_router）。
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage

from agent.intent_router import latest_user_text, routing_notice

logger = logging.getLogger(__name__)


def _today_iso() -> str:
    return date.today().isoformat()


class ContextInjectionMiddleware(AgentMiddleware):
    """将 runtime.context 中的 user_id/username + 本轮分流裁定注入对话。"""

    def before_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        ctx = getattr(runtime, "context", None)
        if ctx is None:
            logger.warning("ContextInjectionMiddleware: runtime.context 为 None，跳过上下文注入")
            return None
        user_id = getattr(ctx, "user_id", None)
        if not user_id:
            logger.warning("ContextInjectionMiddleware: runtime.context 中没有 user_id，跳过上下文注入")
            return None
        username = getattr(ctx, "username", None) or user_id
        workspace = getattr(ctx, "workspace", None)

        user_text = latest_user_text(state.get("messages") if isinstance(state, dict) else None)
        verdict = routing_notice(user_text)
        logger.info(
            "ContextInjectionMiddleware: user_id=%s username=%s user_preview=%r",
            user_id,
            username,
            (user_text or "")[:60],
        )

        workspace_notice = {
            "assistant": "当前用户在研途智探主工作台，可自由使用五大引擎（方向构建/情报提纯/资产透视/跨界启发/审稿）。",
        }.get(workspace, "")
        notice = (
            f"【系统上下文·勿向用户复述】\n"
            f"user_id={user_id}; username={username}; "
            f"today={_today_iso()}; "
            f"偏好路径=/memories/{user_id}/preferences.md\n"
            f"{workspace_notice}\n\n"
            f"{verdict}"
        )
        return {"messages": [SystemMessage(content=notice)]}

    async def abefore_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        return self.before_agent(state, runtime)
