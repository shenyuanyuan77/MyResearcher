"""
研途智探AI · 数据结构定义。
包含运行时上下文、用户偏好、对话/会话/SSE 模型。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


@dataclass
class ResearchContext:
    """
    运行时上下文，由调用方在 invoke 时传入。
    传递当前用户身份、认知等级（千人千面）、研究方向。
    """
    user_id: str
    username: str
    thread_id: Optional[str] = None
    roles: List[str] = None
    # 千人千面：认知等级（novice 新手 / advanced 高阶），影响输出晦涩度
    cognitive_level: Optional[str] = None
    research_direction: Optional[str] = None  # 用户研究方向（伴随式成长）
    workspace: Optional[str] = None


@dataclass
class UserPreferences:
    """用户偏好，存于长期记忆文件 /memories/{user_id}/preferences.md。"""
    cognitive_level: Optional[str] = None  # novice / advanced
    research_direction: Optional[str] = None
    preferred_language: Optional[str] = None  # zh / en
    recent_queries: list[str] = None

    def __post_init__(self):
        if self.recent_queries is None:
            self.recent_queries = []


# ============================================================
# 对话相关模型
# ============================================================

class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")
    thread_id: Optional[str] = Field(None, description="会话 ID，为空则新建")
    workspace: Optional[str] = Field(None, description="工作台")


class Message(BaseModel):
    id: str
    role: str
    content: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    source: Optional[str] = None
    tool_name: Optional[str] = None
    tool_status: Optional[str] = None
    text: Optional[str] = None
    images: Optional[List[str]] = None
    args: Optional[str] = None


class ChatResponse(BaseModel):
    thread_id: str
    messages: List[Message] = Field(default_factory=list)


# ============================================================
# 历史记录
# ============================================================

class Session(BaseModel):
    thread_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    workspace: Optional[str] = None


class SessionListResponse(BaseModel):
    sessions: List[Session] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 20


class SessionMessagesResponse(BaseModel):
    thread_id: str
    messages: List[Message] = Field(default_factory=list)


class DeleteSessionResponse(BaseModel):
    success: bool = True
    message: str = "会话已删除"
