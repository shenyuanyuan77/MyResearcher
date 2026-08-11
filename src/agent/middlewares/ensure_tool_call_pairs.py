"""在每次模型调用前修补悬空 tool_calls。

DeepAgents 自带的 PatchToolCallsMiddleware 只在 before_agent 跑一次。
本项目在其后又挂了 SummarizationToolMiddleware，压缩上下文时可能删掉
ToolMessage，导致下一轮 LLM 报：
  An assistant message with 'tool_calls' must be followed by tool messages...

本中间件在 before_model / abefore_model 每次调用模型前补齐缺失的 ToolMessage。
"""

from __future__ import annotations

from typing import Any, Iterable

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import AIMessage, AnyMessage, RemoveMessage, ToolMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime


def _as_tool_call_dict(tool_call: Any) -> dict[str, Any] | None:
    if isinstance(tool_call, dict):
        return tool_call
    tc_id = getattr(tool_call, "id", None) or getattr(tool_call, "tool_call_id", None)
    name = getattr(tool_call, "name", None)
    if not tc_id:
        return None
    return {
        "id": tc_id,
        "name": name or "unknown",
        "type": getattr(tool_call, "type", None),
        "args": getattr(tool_call, "args", {}) or {},
    }


def _iter_tool_calls(msg: AIMessage) -> Iterable[dict[str, Any]]:
    for raw in list(msg.tool_calls or []):
        parsed = _as_tool_call_dict(raw)
        if parsed:
            yield parsed
    for raw in list(getattr(msg, "invalid_tool_calls", None) or []):
        parsed = _as_tool_call_dict(raw)
        if parsed:
            # 统一标记，便于补丁文案
            if "type" not in parsed or not parsed["type"]:
                parsed["type"] = "invalid_tool_call"
            yield parsed


def _patch_dangling_tool_calls(messages: list[AnyMessage]) -> list[AnyMessage] | None:
    if not messages:
        return None

    answered_ids = {
        msg.tool_call_id
        for msg in messages
        if getattr(msg, "type", None) == "tool" and getattr(msg, "tool_call_id", None)
    }

    needs_patch = False
    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue
        for tool_call in _iter_tool_calls(msg):
            tc_id = tool_call.get("id")
            if tc_id and tc_id not in answered_ids:
                needs_patch = True
                break
        if needs_patch:
            break

    if not needs_patch:
        return None

    patched: list[AnyMessage] = []
    for msg in messages:
        patched.append(msg)
        if not isinstance(msg, AIMessage):
            continue
        for tool_call in _iter_tool_calls(msg):
            tc_id = tool_call.get("id")
            if not tc_id or tc_id in answered_ids:
                continue
            name = tool_call.get("name") or "unknown"
            if tool_call.get("type") == "invalid_tool_call":
                content = (
                    f"Tool call {name} with id {tc_id} could not be executed - "
                    "arguments were malformed or truncated."
                )
            else:
                content = (
                    f"Tool call {name} with id {tc_id} was cancelled - "
                    "context was compacted or another message arrived before completion."
                )
            patched.append(ToolMessage(content=content, name=name, tool_call_id=tc_id))
            answered_ids.add(tc_id)
    return patched


class EnsureToolCallPairsMiddleware(AgentMiddleware):
    """每次模型调用前补齐悬空 tool_call 对应的 ToolMessage。"""

    def before_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        patched = _patch_dangling_tool_calls(list(state.get("messages") or []))
        if patched is None:
            return None
        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *patched]}

    async def abefore_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        return self.before_model(state, runtime)
