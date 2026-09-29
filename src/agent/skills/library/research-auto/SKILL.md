---
name: research-auto
description: Codex 决策 + Zcode 执行的双脑科研自动化流水线，覆盖 SOTA 学习→baseline 复现→模块剖析→创新选题→单点改造实验→论文写作→双脑互审全流程。当用户要求"启动科研流水线/科研自动化"、"用 codex 规划 Zcode 执行"、"复现 baseline 并改进模型/挖创新点"、"双脑互审写论文"时使用；单点文献检索、找仓库或纯写作辅助任务不启用本 skill，直接走 research-core。
---

# research-auto：双脑科研流水线

**架构一句话**：codex（gpt-5.6-sol-high）是规划与终审的大脑，Zcode 是执行与状态管理的大脑，项目 `research/` 目录下的状态文件是唯一事实源，人类保留选题、算力预算、终稿三个否决点。

## 与 research-core 的路由（共存）

- 用户要**全流程科研自动化 / codex 双脑模式** → 本 skill。
- 用户只要**单点任务**（一次文献检索、找一个仓库、改一段论文）→ 直接用 research-core 及其子智能体，不启 codex。
- 本 skill 运行中复用子智能体：ResearchScout（文献证据）、GithubExplorer（仓库/开源实现验证）、PaperReviewer（codex 终审前的廉价预筛）。ScientificEngineer 只保留实现职责，规划权归 codex。

## 权力边界（四条铁律）

1. **方法层决策归 codex**：改什么模块、实验怎么设计、论文怎么改。
2. **实现层执行归 Zcode**：写代码、跑训练、解析指标、画图、排版。实现层问题（同功能开源实现互换、CUDA/依赖兼容、环境修复）Zcode 自主解决并记入 `decisions.md`，不打扰任何人；方法层变更（换一种结构/变体/训练策略）必须打回 codex 重规划。
3. **codex 拥有 workspace-write 权限**：直接读写 `research/` 状态文件；论文的 minor/major 级问题由 codex 直接修改并留痕，重构级修改由 codex 出指令、Zcode 执行。
4. **人类否决点不可跳过**：P3 创新选题、算力预算、终稿。Zcode 与 codex 冲突时先调 ARBITER，仍冲突记 `objections.md` 并服从 codex，用户可随时终裁（终裁也记入 decisions.md）。

## 状态文件（唯一事实源）

项目根目录 `research/`，模板见 [references/templates.md](references/templates.md)：

| 文件 | 写入者 | 作用 |
|---|---|---|
| `env.md` | Zcode（每次会话询问用户后更新） | 训练环境：本机/WSL2/SSH、GPU、conda、数据集路径 |
| `state.md` | 双方 | 当前阶段、gate 状态、任务队列、待人类决策项 |
| `plan.md` | codex | 当前阶段计划（任务列表+验收标准+风险） |
| `decisions.md` | 双方 | 方法决策日志 + Zcode 实现层偏差记录（追加式） |
| `results.json` | 解析脚本（禁止 LLM 手写） | 结构化指标：params/FLOPs/种子/数据比例/指标/delta |
| `objections.md` | Zcode | Zcode 与 codex 的分歧记录（记后服从） |
| `papers/` | Zcode | baseline 与候选模块的结构化阅读笔记 |
| `logs/` | 训练脚本 | 原始日志；codex 不读，由脚本解析进 results.json |

**上下文契约**：codex 每次调用只读状态包（state.md / decisions.md / results.json / env.md + 阶段相关文件），永不见原始训练日志。gate 验收时 codex 有权点名要求附上任意文件原文。

## 会话启动（每次必做）

1. **询问训练环境**（用户定案：每次询问）：本机 Windows / WSL2 / SSH 服务器；GPU 型号与显存；Python 环境管理器；数据集路径。写入 `research/env.md`。同一会话内缓存，启动训练前口头复述一次。
2. **探测 codex CLI**：版本、登录状态、旗标、**模型别名**（用户简称 ≠ 真实别名，以 `~/.codex/models_cache.json` 为准）。任一步失败 → 停止流水线并报告用户，禁止静默降级为 Zcode 独立决策。校验步骤与档位建议见 [references/codex-protocol.md](references/codex-protocol.md)。

## 七阶段流程

| 阶段 | 内容 | Gate（不达标不许前进） |
|---|---|---|
| P0 SOTA 学习 | ResearchScout 读同数据集近年顶会论文 | ≥3 篇结构化笔记 + 可迁移模块清单 |
| P1 复现 | 固定种子复现 baseline | 指标对齐 + 基准表入 results.json + 验证集划分文件存档 |
| P2 模块剖析 | 逐模块文档化 | 每模块：shape/参数量/FLOPs/功能/可替换性评级 |
| P3 选题 | codex 排序创新点 → **人类拍板** | 用户批准主候选+备选 + 故事线文档 |
| P4 单点改造实验 | codex 设计 → Zcode 校验不变量 → 执行 | 3 种子均值±std，提升 ≥0.5 点；不达标回 P3 下一候选 |
| P5 写作 | codex 大纲 → Zcode 逐节起草 | 全文初稿 + 图表可复现脚本齐 |
| P6 互审 | PaperReviewer 预筛 → codex 分级终审 → 修订循环 | blocking=0 → **人类终稿** |

详细 gate 判定规则、回退边、不变量校验表：[references/gates.md](references/gates.md)。

## codex 调用节奏（用户定案：每个任务状态即审）

- **CHECK**：codex 计划中的每个 task 完成（写完一个模块、跑完一轮训练、写完一节）后，立即发起一次任务级审核，通过才标记完成，不等 gate。同一任务 CHECK 最多 2 轮，超过升级 ARBITER。
- **gate 验收**：每阶段结束一次完整验收（REVIEWER mode=gate 全量读状态包）。
- 角色定义、命令模板、JSON schema、超时与非 JSON 兜底：[references/codex-protocol.md](references/codex-protocol.md)。

## 纪律校验器（用户定案：codex 设计，Zcode 校验）

实验纪律细节由 codex 每次自行设计，但以下 8 条不变量是用户的硬规则。Zcode 在执行任何 codex 计划前逐条校验，违反则自动打回 PLANNER（附违反条目编号），不静默修改、不打扰用户；同一计划同一不变量打回 2 次仍违反 → 升级用户。

1. 一次只改一处结构；优先 Neck/Head；动 Backbone 需 codex 显式声明理由与风险。
2. 每次改结构后必须先报 params 与 FLOPs，再开训。
3. 固定随机种子；验证集划分文件存档一次、全程复用。
4. 筛选用 10% 训练集 + 1/3 epochs 看趋势；正式对比才跑全量。
5. 正式结论 ≥3 随机种子，报均值±标准差；提升 <0.5 点不认可。
6. 默认 BF16；loss NaN 先排查除零/对数取零；OOM 用梯度累积 4 步 + BN→GN。
7. BS 翻倍 LR 同步翻倍；warmup 500-1000 迭代；cosine 衰减；WD 在 {0.01, 0.05} 内选。
8. 复现对不上优先排查数据预处理（Resize 方式、归一化参数），再查种子与版本。

## 长训练与失败兜底

- ZCode 单次命令有 10 分钟硬超时：训练一律后台任务 + 轮询 results.json/logs；等待期间并行推进不依赖实验结果的章节（related work、方法描述框架）。
- codex 调用失败（未登录/超时/输出非 JSON/codex 越权改文件）逐级兜底规则见 [references/codex-protocol.md](references/codex-protocol.md)。

## 论文写作与互审（P5-P6）

- 故事线强制"领域针对性适配 + 机制分析"叙事，参照 baseline 论文的章节逻辑与问题引入方式；明确与"简单替换"的区分点。不做掩饰式改写——这既是底线也是接收率策略。
- 分级修订权：minor/major 由 codex 直接改文件并记 decisions.md；重构级由 codex 出指令、Zcode 执行。
- Zcode 不同意 codex 时：记 `objections.md`，服从执行，留待用户终裁。
- 可组合既有 skill：nature-writing（起草）、nature-figure（出图）、happy-figure-skill（绘图提示词）、nature-response（返修信）。
