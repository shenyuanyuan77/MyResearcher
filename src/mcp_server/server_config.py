"""MCP 服务配置（端口/路径从环境变量读取）。"""

from __future__ import annotations

import os

MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "7001"))
MCP_PATH = os.getenv("MCP_PATH", "/mcp")
