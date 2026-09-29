"""
MyResearcher · Agent 加载器（单例）。

精简自采购助手：去 Mongo，会话归属/标题/展示消息统一走 local_session_store（JSON 文件，
进程重启可保留）；checkpoint 由 main_agent 内部 SQLite checkpointer 管理。
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from agent.settings import settings
from api_view import local_session_store as local_store

# 进程内归属/标题缓存（local_store 持久化的镜像，加速查询）
_memory_owners: Dict[str, str] = {}
_memory_titles: Dict[str, str] = {}


class AgentLoader:
    """Agent 加载器单例。"""

    _instance: Optional["AgentLoader"] = None
    _initialized: bool = False
    _agent = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self):
        """懒加载 Agent（内部 SQLite checkpointer）。"""
        if self._initialized and self._agent is not None:
            return self._agent
        print("[AgentLoader] 开始初始化...")
        try:
            from agent.main_agent import get_agent_async

            self._agent = await get_agent_async()
            self._initialized = True
            print("[AgentLoader] 初始化完成")
        except Exception:
            self._initialized = False
            raise
        return self._agent

    @property
    def agent(self):
        if self._agent is None:
            raise RuntimeError("Agent 未初始化，请先调用 initialize()")
        return self._agent

    def create_config(
        self,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return {
            "configurable": {
                "thread_id": thread_id or str(uuid.uuid4()),
                "user_id": user_id or settings.default_user_id,
                **kwargs,
            }
        }

    # ---------- 归属 / 标题 / 工作区 ----------

    def bind_session_owner(
        self, thread_id: str, user_id: str, workspace: Optional[str] = None
    ) -> None:
        if not thread_id or not user_id:
            return
        if thread_id not in _memory_owners:
            _memory_owners[thread_id] = user_id
        local_store.bind_owner(thread_id, user_id)
        if workspace:
            local_store.set_workspace(thread_id, workspace)

    def get_session_workspace(self, thread_id: str) -> Optional[str]:
        return local_store.get_workspace(thread_id)

    def get_session_owner(self, thread_id: str) -> Optional[str]:
        if thread_id in _memory_owners:
            return _memory_owners[thread_id]
        owner = local_store.get_owner(thread_id)
        if owner:
            _memory_owners[thread_id] = owner
        return owner

    def get_session_title(self, thread_id: str) -> Optional[str]:
        if thread_id in _memory_titles:
            return _memory_titles[thread_id]
        title = local_store.get_title(thread_id)
        if title:
            _memory_titles[thread_id] = title
        return title

    def set_session_title(self, thread_id: str, title: str) -> bool:
        title = (title or "").strip()
        if not thread_id or not title:
            return False
        _memory_titles[thread_id] = title
        local_store.set_title(thread_id, title)
        return True

    def get_thread_ids_for_user(
        self, user_id: str, workspace: Optional[str] = None
    ) -> List[str]:
        mem = [tid for tid, uid in _memory_owners.items() if uid == user_id]
        local_ids = local_store.thread_ids_for_user(user_id)
        merged = list(dict.fromkeys(local_ids + mem))
        if workspace:
            merged = [
                tid
                for tid in merged
                if (local_store.get_workspace(tid) or self.get_session_workspace(tid))
                == workspace
            ]
        # 兜底：本地有消息但无归属记录的会话，对默认用户可见
        if user_id == settings.default_user_id and not workspace:
            for tid in local_store.all_thread_ids():
                if tid not in merged:
                    owner = self.get_session_owner(tid)
                    if owner is None:
                        self.bind_session_owner(tid, user_id)
                        merged.append(tid)
        return merged

    def thread_exists(self, thread_id: str) -> bool:
        if not thread_id:
            return False
        return local_store.thread_exists(thread_id)

    def assert_session_owner(self, thread_id: str, user_id: str) -> bool:
        """校验 user_id 是否为 thread_id 的所有者。

        安全策略（修复越权漏洞）：
        - 已有 owner：直接比对。
        - 无 owner 且 thread 存在：仅 default_user 一次性迁移认领（兼容历史无主会话），
          其他用户一律拒绝。迁移打审计日志。
        - 无 owner 且 thread 不存在：拒绝（不再自动认领新 thread，杜绝抢占）。
        历史版本的"任意用户自动认领未存在 thread"已移除。
        """
        owner = self.get_session_owner(thread_id)
        if owner is not None:
            return owner == user_id
        # 无 owner
        if self.thread_exists(thread_id) and user_id == settings.default_user_id:
            # 仅默认用户对历史无主会话做一次性迁移
            self.bind_session_owner(thread_id, user_id)
            import logging
            logging.getLogger(__name__).info(
                "assert_session_owner: 迁移认领历史无主会话 thread=%s user=%s",
                thread_id, user_id,
            )
            return True
        return False

    # ---------- 状态 / 消息 ----------

    async def get_current_messages(self, thread_id: str) -> List[Any]:
        config = self.create_config(thread_id)
        try:
            state = await self.agent.aget_state(config)
            if state and state.values:
                return state.values.get("messages", [])
        except Exception as e:
            print(f"[AgentLoader] 获取消息失败: {e}")
        return []

    async def get_state_history(self, thread_id: str, limit: int = 100) -> List[Any]:
        """获取会话历史消息（修复 chat.py 调用但未定义的 latent AttributeError）。

        优先从 checkpointer 读取状态历史；失败时回退到 local_session_store 的展示消息。
        """
        config = self.create_config(thread_id)
        try:
            history = []
            async for state in self.agent.aget_state_history(config, limit=limit):
                if state and state.values:
                    msgs = state.values.get("messages", [])
                    if msgs:
                        history.extend(msgs)
            if history:
                # 去重保序（checkpointer 可能返回多个 checkpoint 的快照）
                seen, out = set(), []
                for m in history:
                    key = getattr(m, "id", None) or str(m)
                    if key not in seen:
                        seen.add(key)
                        out.append(m)
                return out
        except Exception as e:
            print(f"[AgentLoader] 获取状态历史失败，回退到 local_store: {e}")
        # 回退：local_session_store 展示消息
        msgs = local_store.load_messages(thread_id)
        return msgs or []

    def get_session_updated_at(self, thread_id: str) -> datetime:
        return local_store.get_updated_at(thread_id)

    async def delete_session(self, thread_id: str) -> bool:
        _memory_owners.pop(thread_id, None)
        _memory_titles.pop(thread_id, None)
        return local_store.delete_session(thread_id)

    # ---------- 展示消息存取 ----------

    _MAX_FIELD_LENGTH = 500_000

    @classmethod
    def _truncate_message_fields(cls, msg: Dict[str, Any]) -> Dict[str, Any]:
        for field in ("text", "content", "args"):
            if (
                field in msg
                and isinstance(msg[field], str)
                and len(msg[field]) > cls._MAX_FIELD_LENGTH
            ):
                msg[field] = msg[field][: cls._MAX_FIELD_LENGTH] + "\n\n...(内容过长已截断)"
        return msg

    async def save_display_messages(
        self, thread_id: str, messages: List[Dict[str, Any]]
    ) -> bool:
        safe = [self._truncate_message_fields(dict(m)) for m in messages]
        ok = local_store.save_messages(thread_id, safe)
        local_store.set_updated_at(thread_id)
        return ok

    async def get_display_messages(
        self, thread_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        return local_store.load_messages(thread_id)


agent_loader = AgentLoader()
