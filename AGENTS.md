# AGENTS.md — MyResearcher（科研导师网页版）

> 面向 ZCode agent 的项目工作指南。仅记录**不读代码就会踩坑**的项目专属事实。
> 完整背景见 [README.md](README.md) / [MyResearcherPRD.md](MyResearcherPRD.md) / [docs/架构说明.md](docs/架构说明.md)。

## 项目定位
研究生科研探索助手网页版：一次对话完成方向构建、文献检索精读、学者透视、跨界推演、AI 审稿。**所有文献锚定真实 DOI、可溯源**。技术栈：LangGraph + DeepAgents + DeepSeek + FastAPI + fastmcp + Vue3。

## 三服务与端口
| 服务 | 端口 | 入口模块 |
|---|---|---|
| 前端 Vue3 SPA | 3001 | `frontend/`（Vite，proxy `/api` → :8000） |
| 后端 FastAPI | 8000 | `python -m api_view.web_main` |
| 学术数据 MCP | 7001 | `python -m mcp_server.server_main`（streamable_http `/mcp`） |

启动顺序：MCP → 后端（后台惰性初始化 Agent）→ 前端。**登录/健康检查不阻塞 Agent 加载**（`web_main.py` lifespan）。

## 常用命令
```bash
# 一键启停（自动设 PYTHONPATH=src）
python start_all.py                 # 启动全部
python start_all.py --no-frontend   # 仅后端 + MCP
python start_all.py --check         # 仅健康检查
start.bat / stop.bat                # Windows（纯 ASCII，规避 cmd GBK 崩溃）

# 前端
cd frontend && npm install && npm run dev      # 开发（:3001）
cd frontend && npm run build                   # 构建到 frontend/dist
cd frontend && npm run test:md                 # markdown 工具单测

# 后台常驻启动（测试/CI 用，服务脱离启动进程树；stop_bg.py 按端口停）
PYTHONIOENCODING=utf-8 python scripts/dev/start_bg.py   # detached 启动 MCP + 后端
python scripts/dev/stop_bg.py                            # 停止后台服务

# 冒烟测试（均在 scripts/dev/）
PYTHONPATH=src python scripts/dev/smoke_academic.py     # 三源连通 + Paper 归一（离线直接调引擎层）
PYTHONPATH=src python scripts/dev/smoke_security.py     # bcrypt/所有权/限流/RBAC（纯离线）
python scripts/dev/smoke_engines.py                     # 端到端：登录→SSE→真实 DOI（需服务在跑）

# LangGraph 图定义入口（langgraph.json）
#   graphs.agent = ./src/agent/main_agent.py:agent
```
默认账号：`yanjiu / yanjiu123`（`.env` 的 `AUTH_USERS` 可改）。

## 分层边界（改动时务必遵守）
代码按包根在 `src/` 组织，**import 顶层包名**（`from agent...` / `from api_view...` / `from mcp_server...`），所以**任何 Python 运行都需要 `PYTHONPATH=src`**（`start_all.py`、冒烟脚本、`langgraph.json` 已各自处理）。

1. **`src/agent/`** — 主 Agent、子 Agent、工具、中间件、提示词。
   - `main_agent.py`：`create_deep_agent` 组装；工具池 = 学术 MCP 工具 + `web_search` + `write_markdown_table` + `emit_research_report` + `save_report_locally` + `get_system_date` + `load_research_skill`（科研技能库，见 `src/agent/skills/`，33 个技能按六大生命周期分类：文献情报/研究设计/论文写作/审稿与发表/图表汇报/全流程与转化；来源=本机 ZCode skills 25 个 + K-Dense-AI/scientific-agent-skills 8 个（MIT），前端技能中心走 `GET /api/skills`）。
   - 子 Agent：`literature-analyst`、`review-expert`（YAML + `subagents/loader.py`，按工具名子串匹配）。
   - `middlewares/`：ContextInjection / MemoryUpdate / Summarization / EnsureToolCallPairs。
   - `memory/prompts.py`：系统提示词（五大引擎分流 + 零幻觉铁律 + 出表规范）。
2. **`src/api_view/`** — FastAPI、SSE、认证、会话、报告导出。路由在 `api/`（`auth_routes` / `chat` / `history` / `library`）。`agent_loader.py` 持有 Agent 单例 + 会话归属 + 展示消息存取（`local_session_store` JSON）。
3. **`src/mcp_server/`** — 学术数据 MCP。`tools/unified.py` 是**统一 `Paper` 数据类 + HTTP 客户端 + 多源归并**的核心；`academic.py` 是引擎编排层；`crossref_tools` / `openalex_tools` / `semantic_scholar_tools` 是三源适配。

**层级铁律**：后端不直连学术 API（必须经 MCP 或 Agent 工具）；MCP 工具返回的 `Paper` 必须带 `doi_url`。前端只走 `/api/*`。

## 配置中心（改配置只动这里）
- **所有可变配置从环境变量读取**，统一经 `from agent.settings import settings`（`src/agent/settings.py`，dataclass + `lru_cache`）。**不要在业务代码里 `os.getenv` 散读**；新增配置项请加到 `settings` 并同步 `.env.example`。
- `.env` 由 `.env.example` 复制；`.env` **已 gitignore**。
- 模型：`MAIN_MODEL=deepseek-v4-pro`（主）、`SUMMARY_MODEL=deepseek-v4-flash`；旧别名 `deepseek-chat`/`deepseek-reasoner` 可覆盖。生产：`APP_ENV=production` + 强随机 `JWT_SECRET` + bcrypt 哈希 `AUTH_USERS`，建议 `FAIL_ON_INSECURE_CONFIG=true`。

## 零幻觉溯源（核心壁垒，改动须格外谨慎）
1. **工具结果是唯一事实源**，提示词硬约束禁止编造文献/作者/DOI。
2. 每条 `Paper` 强制带可点 `doi_url`，工具返回的 `suggested_markdown` 含 DOI 链接。
3. CrossRef（主 DOI 源）+ OpenAlex（富数据/作者/h 指数）+ Semantic Scholar（摘要兜底）三源去重归并。
4. **工具未召回时如实说「未找到」**，不得反向编造。
5. `emit_research_report` 校验长度/标题，防半截报告。

## SSE 流式事件协议（`api/chat.py`，前后端必须一致）
事件类型：`token` / `tool_start` / `tool_args` / `tool_result` / `tool_end` / `interrupt` / `done` / `error`。
- `emit_research_report` 的 markdown 参数经增量投影为 `token`（报告流式进入助手气泡，避免与工具卡片重复）。
- 前端 `api/chat.js` 的 `_processStream` 与之配对解析；工具名中文映射在 `MessageItem.vue`（如 `paper_search→文献检索`）。

## 前端约定（`frontend/src/`）
- Vue3 + Vite；markdown 渲染 = `markdown-it` + `highlight.js` + Mermaid；DOI 链接高亮样式见 `MarkdownRenderer.vue`（`a[href*="doi.org"]`）。
- API 层在 `src/api/`（`http.js`：fetch + JWT + 401 触发重登录；`chat.js`：SSE 解析）。
- 设计语言：Apple 风（毛玻璃/深色模式/SF Pro），token 在 `design-tokens.js` 与 `styles/design-tokens.css`。
- `frontend/dist/`、`node_modules/` 已 gitignore，别提交。

## 数据与产物（已 gitignore，勿提交）
- `data/checkpoints.sqlite*`（LangGraph checkpoint，~47MB）、`data/memory.sqlite`、`data/local_sessions/`：会话记忆 + 用户偏好 Store，进程重启可保留。
- `src/data/library.sqlite*`（个人文献库 + WAL/SHM，运行时数据）：`.gitignore` 已有规则（`src/data/*.sqlite*`），但**历史上曾被跟踪的文件需 `git rm --cached` 才真正解除跟踪**（ignore 规则对已跟踪文件无效），已执行过一次（2026-09）；若 `git status` 再出现这些文件的改动，先查是否被重新 `git add`。
- `logs/`：各服务运行日志（mcp/backend/frontend.log）。
- `_ref_caigou/`、`_ref_caigou_v2/`：参考工程（采购助手），**只读参考，勿改勿提交**。
- `gui-test-screenshots/`、`frontend_v1_backup/`：历史快照。

## 平台 / Windows 注意
- Windows 上 npm 是 `npm.cmd`，`start_all.py` 已用 `shell=True` 处理；跨平台脚本请同样适配。
- `.bat` 文件保持**纯 ASCII**（注释、echo），避免 cmd.exe GBK/UTF-8 崩溃。
- Python 定位优先 Anaconda（见 `start.bat`），跳过 WindowsApps 占位 python。

## 改动前应读
- 改 Agent/提示词/工具池 → `src/agent/main_agent.py` + `src/agent/memory/prompts.py` + `docs/架构说明.md`。
- 改学术数据/新增源 → `src/mcp_server/tools/unified.py`（`Paper` 归一）+ `academic.py`（编排）。
- 改 SSE/会话 → `src/api_view/api/chat.py` + `frontend/src/api/chat.js`（两端必须同步）。
- 改配置 → `src/agent/settings.py` + `.env.example`。
- 产品方向 / 待办 / 决策 → `docs/PRODUCT_DECISIONS.md`、`docs/DEFERRED.md`。

## 视觉理解
**若任务需要视觉理解（识图、读图、从图像提取信息），自动调用用户配置的视觉理解 MCP 服务**（如 `mcp__recognition__*` 等可用工具），无需逐次询问。
