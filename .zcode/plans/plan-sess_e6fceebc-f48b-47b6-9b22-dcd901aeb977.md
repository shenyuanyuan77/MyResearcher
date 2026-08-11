# 研途智探AI · 生产级输出体验升级计划

> 借鉴 GitHub 成熟项目（**STORM 行内引用综述 + RAGFlow 引用溯源 + LobeChat 消息渲染**），聚焦你最看重的 **4 项输出能力**，在当前架构上做"输出体验"专项升级。不重构、不换栈，最大化复用现有 SSE/MCP/Agent 管线。

---

## 一、升级目标（对应你的 4 个选择）

| 你的诉求 | 借鉴对象 | 落地能力 |
|---|---|---|
| ① **学术引用格式** | STORM `[n]` 行内引用 + citation-js/CSL | 论文按 **GB/T 7714 / APA / IEEE** 格式输出；正文 `[n]` 角标 + 文末编号参考文献列表 |
| ② **对话内富卡片** | RAGFlow 引用气泡 + LobeChat 富渲染 | 文献富卡片（标题/作者/期刊/被引/DOI按钮）；DOI 链接高亮；`[n]` hover 弹引用气泡 |
| ③ **图表可视化** | mermaid + 内嵌趋势图 | 领域热度趋势折线图、主题分布柱状图、跨界关系图（LLM 产 spec → 前端渲染） |
| ④ **报告导出 PDF/Word** | docx + xhtml2pdf | 一键导出综述/审稿报告为 **PDF / Word(.docx) / Markdown**，含参考文献 |

---

## 二、技术方案（7 个改造点）

### 改造 1：后端 `Paper` 字段补全（引用格式化的前提）
**文件**：`src/mcp_server/tools/unified.py` + `crossref_tools.py` + `openalex_tools.py`
- `Paper` dataclass 增字段：`pub_type`（article/conference/preprint）、`volume`、`issue`、`page`、`publisher`、`raw_authors`（list of `{family, given}`，GB/T 7714 需要姓/名拆分）。
- CrossRef `_parse_crossref_item` 的 `select` 加 `volume,issue,page,type,publisher`；解析 `author` 时保留 family/given。
- OpenAlex `_WORK_SELECT` 加 `biblio,type`；解析 `authorships.author.display_name` 之外补 `raw_author_name`。
- 不破坏现有字段（增量）。

### 改造 2：后端引用格式化器 `citations.py`（核心新增）
**新文件**：`src/mcp_server/tools/citations.py`
- `format_paper_gbt7714(paper) -> str`：国标格式（`[1] 作者. 标题[J]. 期刊, 年, 卷(期): 页. DOI:10.xxx`）。文献类型标识 `[J]/[C]/[M]/[EB/OL]` 按 pub_type 推断。
- `format_paper_apa(paper)` / `format_paper_ieee(paper)`：同构。
- `papers_to_references(papers, style="gbt7714") -> str`：生成编号参考文献列表 markdown（`## 参考文献\n[1] ...\n[2] ...`），每条带可点 DOI。
- `papers_to_markdown` 增加每条 `[n]` 前缀（行内锚点）。
- **纯 Python 自实现**（Paper 字段够用，避免 CSL 引擎复杂度）；GB/T 7714 规则固定、可测试。

### 改造 3：Agent 提示词强制引用规范（STORM 范式）
**文件**：`src/agent/memory/prompts.py` + `literature_analyst.yaml` + `review_expert.yaml` + `AGENTS.md`
- 在「零幻觉铁律」后注入新段落 **「## 引用格式铁律」**：
  - 文献类回答：正文引用处用 `[n]` 角标；文末出 `## 参考文献` 编号列表（调用 `papers_to_references` 返回值原样照贴）。
  - 默认格式 **GB/T 7714**（可应要求切 APA/IEEE）。
  - 综述/审稿报告必须含参考文献章节（`emit_research_report` 校验补充）。
- 5 引擎 quickTask message 追加引用格式诉求（App.vue 同步）。

### 改造 4：SSE 通道 + 前端富卡片（RAGFlow 范式）
**文件**：`src/api_view/api/chat.py`（后端 tool_result 注入 references）+ `frontend/src/api/chat.js`（读取）+ `MessageItem.vue`（渲染）+ `MarkdownRenderer.vue`（DOI 高亮 + `[n]` 气泡）
- **后端**：`paper_search`/`paper_by_doi`/`author_profile`/`cross_search` 的 tool_result 序列化时，把 `papers` 结构化数组塞进 SSE 的 `tool_result` 事件（新字段 `references`）。
- **前端 chat.js**：`_processStream` 的 `tool_result` 分支增读 `data.references`，写入 `finished.references`。
- **MessageItem.vue**：tool 卡片新增 `<div class="ref-card-grid">`，把 `message.references` 渲染成文献富卡片（标题/作者/期刊/年份/被引/DOI 按钮→新窗打开）。`formatToolName` 补全 paper_search→文献检索、paper_by_doi→DOI溯源 等映射。
- **MarkdownRenderer.vue**：
  - `link_open` 规则：`href.includes('doi.org')` → 加 class `doi-link` + 🔗 图标徽章 + 主色高亮。
  - 渲染后 DOM 增强（复用现有 `enhancePriorityCellsDOM` 模式）：扫描正文 `[n]` 文本节点 → 包成 `<sup class="cite-ref" data-idx="n">`，hover/click 弹引用气泡（气泡内容来自 message.references 第 n 条）。
  - 新增 `prop: citations` 接收结构化引用，供气泡查询。

### 改造 5：图表可视化（mermaid + 趋势图）
**文件**：`frontend/src/components/MarkdownRenderer.vue` + `package.json`（加 `mermaid`）
- markdown-it fence 钩子：`lang === 'mermaid'` → 输出 `<div class="mermaid">{code}</div>` 占位，`nextTick` 调 `mermaid.run({ nodes })` 渲染（思维导图/流程图，用于跨界推演、方向构建）。
- **领域热度趋势图**（已有 `monthlyTrendChart.js` 注入 SVG 折线的范式）：`topic_radar` 返回 `heat_trend` 数据，后端在 `suggested_markdown` 里附带一个 `chart` spec 块（ECharts JSON），前端识别并渲染成柱状/折线图（主题分布、热度趋势）。
- 复用现有 `.md-line-chart` / `.md-figure` 容器样式。

### 改造 6：报告导出 PDF/Word（docx + xhtml2pdf）
**新文件**：`src/api_view/report_export.py` + `src/agent/tools/export_helpers.py`（或扩展 save_report_locally）
- **新端点** `POST /api/report/export`（body: `{thread_id, format: pdf|docx|md, citation_style}`）：
  - 从 `agent_loader.get_display_messages(thread_id)` 取报告 markdown。
  - `format=docx` → `python-docx` 生成 Word（含标题/正文/表格/参考文献）。
  - `format=pdf` → `xhtml2pdf`（纯 Python，无需 GTK，比 weasyprint 轻）把 markdown→HTML→PDF。
  - `format=md` → 直接返回规范化的 .md。
  - 返回 `StreamingResponse`（文件下载）。
- **save_report_locally 工具增 `format` 参数**：Agent 可在对话内触发导出（"下载为 Word"）。
- `requirements.txt` 加 `python-docx`、`xhtml2pdf`、`reportlab`（xhtml2pdf 依赖）。
- 复用 `auth.py` 的 `require_permission("report:export")`（已定义未用）。

### 改造 7：引用格式与导出的一致性校验
**文件**：`src/agent/tools/emit_research_report.py` + `citations.py` 单测
- `emit_research_report` 的 `normalize_report_markdown`：若内容含文献但**无** `## 参考文献` 章节，追加提示（非阻断）。
- `scripts/dev/test_citations.py`：对 GB/T 7714/APA/IEEE 格式化做 golden 用例测试（给定 Paper → 期望字符串）。

---

## 三、依赖增量（最小集）

**Python**（requirements.txt）：`python-docx`、`xhtml2pdf`、`reportlab`（PDF/Word 导出）。引用格式化纯自实现，不加 CSL。
**Node**（package.json）：`mermaid`（图表）。`citation-js` 不加（格式化在后端做，前端只渲染结构化数据）。

---

## 四、分阶段交付（可独立验收）

| 阶段 | 内容 | 验收 |
|---|---|---|
| **P1 引用格式化基石** | 改造1+2：Paper 字段补全 + citations.py 格式化器 + 单测 | `python test_citations.py` 输出正确 GB/T 7714/APA/IEEE 字符串 |
| **P2 引用规范贯通** | 改造3：Prompt 注入 + quickTask 更新 + emit 校验 | 五引擎输出含 `[n]` + 参考文献列表 |
| **P3 富卡片 + DOI 高亮** | 改造4：SSE references + MessageItem 富卡片 + MarkdownRenderer DOI/[n] 气泡 | 文献以卡片展示，DOI 可点，[n] hover 弹气泡 |
| **P4 图表可视化** | 改造5：mermaid 渲染 + 趋势图 spec | 方向构建出趋势图，跨界推演出关系图 |
| **P5 导出 PDF/Word** | 改造6：/api/report/export + save 工具 format 参数 | 报告一键导出 PDF/Word，含参考文献 |
| **P6 校验收尾** | 改造7 + 全链路冒烟 + 文档更新 | 5 引擎端到端 + 导出冒烟通过 |

---

## 五、不做什么（边界）
- ❌ 不做多用户/数据库持久化（你说"当前架构够用"）。
- ❌ 不做 Docker/CI（非本轮重点）。
- ❌ 不换前端栈（Vue3 保持，借鉴 LobeChat 设计而非移植 React 组件）。
- ❌ 不引入 weasyprint（Windows GTK 重），用 xhtml2pdf 纯 Python。
- ❌ 不引入 CSL 引擎（Paper 字段够，自实现更可控可测）。

---

## 验收脚本（升级后）
1. 情报提纯：输出含 `[n]` 行内引用 + 文末 `## 参考文献`（GB/T 7714），文献以富卡片展示，DOI 可点。
2. 方向构建：领域热度以趋势图展示。
3. 跨界启发：关系图以 mermaid 展示。
4. 综述报告：一键导出 Word，打开后含标题/正文/表格/参考文献。
5. `[n]` 角标 hover 弹引用气泡，显示该篇标题/作者/DOI。

批准后我按 P1→P6 顺序实施，每阶段完成更新进度。中途如遇必须由你决策的分叉（如某导出库在 Windows 异常），会用 AskUserQuestion 即时确认。