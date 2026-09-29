# MyResearcher · 网页版

> 面向研究生的科研探索助手 · 网页版
> 一个对话完成方向构建、文献检索精读、学者透视、跨界推演与 AI 审稿，**全部文献锚定真实 DOI，可溯源可核验**。

基于 LangGraph + DeepSeek + FastAPI + MCP + Vue3 构建，用 **CrossRef / OpenAlex / Semantic Scholar 等公开学术 API 的真实 DOI** 兑现「文献溯源零幻觉」——所有召回文献带真实 DOI 可点击核验。注：DOI 锚定保证文献真实存在，LLM 对摘要的提炼/改写仍建议对照原文。

📖 **完整产品需求**见 [MyResearcherPRD.md](MyResearcherPRD.md)

---

## ✨ 核心能力（五大引擎 + 生产级输出）

| 引擎 | 功能 | 工具 |
|---|---|---|
| 🧭 **方向构建** | 选题规划、领域热度趋势、检索式建议 | `topic_radar` |
| 🔍 **情报提纯** | 多源文献检索（带真实 DOI）、精读、综述 | `paper_search` / `paper_by_doi` / `paper_distill` |
| 👤 **资产透视** | 学者画像、h 指数、代表作、研究主题 | `author_profile` |
| 🧬 **跨界启发** | 两领域融合可行性推演、交叉工作佐证 | `cross_search` |
| 📝 **AI 审稿** | 规范性检查、引用核对、改进建议、评分 | `review-expert` 子 Agent |

### 🎓 生产级输出（v2 升级）
- **学术引用格式**：GB/T 7714-2015（默认）/ APA 第7版 / IEEE，正文 `[n]` 角标 + 文末编号参考文献列表。
- **文献富卡片**：每篇文献以卡片展示（标题/作者/期刊/被引/DOI按钮/PDF链接），DOI 链接高亮，`[n]` hover 弹引用气泡。
- **图表可视化**：Mermaid 思维导图/流程图（跨界推演、方向构建）；领域热度趋势表。
- **报告导出**：一键导出综述/审稿报告为 **Word(.docx) / PDF / Markdown**，含参考文献。
- **Apple 设计语言**：窗口化布局、毛玻璃、弹簧动效、深色模式、SF Pro 字体。

**文献溯源三层保障**：(1) 工具结果是唯一事实源；(2) 每条文献强制带可点 DOI 可核验；(3) 系统提示词硬约束 + 撤稿过滤。注：保证文献真实存在，对摘要的改写请对照原文。

---

## 🚀 快速启动

### 环境要求
- Python 3.10+
- Node.js 18+（含 npm）
- DeepSeek API Key（[申请](https://platform.deepseek.com/)）

### 一键启动（Windows）
```bat
1. 复制 .env.example 为 .env，填入 DEEPSEEK_API_KEY
2. 双击 start.bat
3. 浏览器访问 http://localhost:3001
```

### 命令行启动
```bash
# 1. 安装依赖
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 2. 启动全部服务（MCP + 后端 + 前端）
python start_all.py

# 或仅后端（不起前端）
python start_all.py --no-frontend
```

### 默认账号
`yanjiu / yanjiu123`（可在 `.env` 的 `AUTH_USERS` 修改）

---

## 🌐 服务地址

| 服务 | 地址 |
|---|---|
| 前端 | http://localhost:3001 |
| 后端 API 文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |
| 学术 MCP | http://127.0.0.1:7001/mcp |

---

## 🏗️ 技术架构

```
Vue3 SPA (:3001)  ──SSE──►  FastAPI (:8000)  ──►  DeepAgent (DeepSeek)
                                │
                          AsyncSqliteSaver (会话记忆)
                                │
                          学术 MCP (:7001)
                                │
                   CrossRef + OpenAlex + Semantic Scholar
```

- **Agent 运行时**：LangGraph 1.x + deepagents，DeepSeek-V4-Pro（主）/ V4-Flash（摘要）。
- **数据源**：CrossRef（权威 DOI）+ OpenAlex（富数据/作者/h指数）+ Semantic Scholar（摘要兜底），均免费无 Key。
- **会话记忆**：SQLite checkpoint（进程重启可保留）+ 用户偏好 Store（认知等级/研究方向，千人千面）。
- **安全**：JWT 登录 + RBAC + 限流 + 安全头 + 审计日志。

详见 [docs/架构说明.md](docs/架构说明.md)。

---

## 📂 目录结构

```
MyResearcherdemo/
├─ MyResearcherPRD.md            产品需求文档
├─ start.bat / stop.bat      Windows 启停
├─ start_all.py              Python 一键启动器
├─ .env.example              环境变量模板
├─ requirements.txt          Python 依赖
├─ frontend/                 Vue3 前端
├─ src/
│  ├─ agent/                 主 Agent、子 Agent、工具、中间件、提示词
│  ├─ api_view/              FastAPI、SSE、认证、会话
│  └─ mcp_server/            学术数据 MCP 服务（三源归一）
├─ data/                     SQLite checkpoint + 会话存储
├─ logs/                     运行日志
└─ scripts/dev/              冒烟测试脚本
```

---

## 🧪 测试

```bash
# 学术工具冒烟测试（直接调引擎层，验证三源连通）
PYTHONPATH=src python scripts/dev/smoke_academic.py

# 端到端引擎冒烟测试（登录→SSE→Agent→真实 DOI）
python scripts/dev/smoke_engines.py
```

---

## 📚 文档
- [MyResearcherPRD.md](MyResearcherPRD.md) — 产品需求文档
- [docs/运行与演示指南.md](docs/运行与演示指南.md) — 详细启动与演示脚本
- [docs/架构说明.md](docs/架构说明.md) — 技术架构与设计决策

---

## 📝 设计决策
1. **模型**：用 `deepseek-v4-pro`/`deepseek-v4-flash`（当前可用，已验证）；旧别名 `deepseek-chat`/`deepseek-reasoner` 可作 `.env` 覆盖。
2. **数据源**：CrossRef 为主 DOI 源（全球 DOI 注册机构，最权威），OpenAlex 补富数据/作者，S2 做纯文本摘要兜底。免费、合法、无需授权。
3. **去沙箱/去 Mongo**：研途场景无需代码执行；SQLite checkpoint 足以支撑多会话记忆，更轻更稳。
4. **零幻觉**：工具唯一事实源 + DOI 强制 + 提示词硬约束 + 报告校验。
5. **千人千面**：用户偏好 Store 存「认知等级」+「研究方向」，提示词据此调节晦涩度。

> 「我们不仅在消除 AI 的幻觉，更在打破中国基础科研创新的信息壁垒。」
