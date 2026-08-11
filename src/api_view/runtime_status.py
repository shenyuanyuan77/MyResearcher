"""运行时状态（降级标记、MCP 状态等），供 /health 查询。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RuntimeStatus:
    ready: bool = False
    degraded: bool = False
    warnings: List[str] = field(default_factory=list)
    # 学术 MCP 是否就绪
    mcp_academic_ok: bool = False
    # checkpoint 后端：sqlite | memory | unknown
    checkpoint_backend: str = "unknown"
    # 用户偏好 Store 后端：sqlite | memory | unknown（伴随式成长持久化）
    store_backend: str = "unknown"


runtime_status = RuntimeStatus()
