"""环境变量读取（.env 加载）。精简版：只保留研途智探需要的项。"""

import os

from dotenv import load_dotenv

load_dotenv(override=True)

# ---- LLM ----
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
ZHIPU_BASE_URL = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")

# ---- 学术 MCP ----
MCP_ACADEMIC_URL = os.getenv("MCP_ACADEMIC_URL", "http://127.0.0.1:7001/mcp")
MCP_API_KEY = os.getenv("MCP_API_KEY")
