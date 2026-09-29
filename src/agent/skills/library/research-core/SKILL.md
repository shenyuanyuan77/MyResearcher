---
name: research-core
description: 科研"实验+论文"阶段统一入口（原 research-pipeline 全面升级）：从已有 idea/方法到完成论文。用于方法建模、公式推导与检查、实验设计与消融、找 Baseline 与开源实现、复现方法、论文大纲与写作、模拟同行评审与定向回退。协调四个子智能体：GithubExplorer（代码/仓库/Benchmark 证据）、ResearchScout（论文/相关工作/创新核查）、ScientificEngineer（方法建模/公式/实验设计）、PaperReviewer（模拟审稿/弱点攻击），按任务阶段选择性调度。要从零产生研究 idea 用 research-pre；论文定稿后做海报/视频/博客用 research-post。
---

# Research Core（做实验完成论文）

实验与论文阶段的唯一入口，承接 research-pre 的移交（idea card + research-state.md），也可直接从"已有方法/已有草稿"切入。本 Skill 是调度层，不直接完成科研工作。

核心架构：

```text
              research-core（调度器）
                          │
            ┌─────────────┴─────────────┐
            ↓                           ↓
   GithubExplorer              ResearchScout      ← 可并行
   代码/项目/Benchmark          论文/Gap/创新核查
            │                           │
            └─────────────┬─────────────┘
                          ↓
                  Evidence Merge（闸门）
                          ↓
                 ScientificEngineer     ← 串行
                 方法/公式/实验/实现
                          ↓
                    PaperReviewer       ← 串行
                  数据/论文/模拟审稿
                          │
                    ┌─────┴─────┐
                 通过           不通过
                  ↓               ↓
             论文写作交付    定向回退对应 Agent
```

两条铁律：

1. **并行与串行**：`GithubExplorer` 与 `ResearchScout` 互相独立，必须在同一条消息中同时发起；`ScientificEngineer` → `PaperReviewer` 必须串行，Evidence Merge 未完成不许进入设计阶段。
2. **按需调用**：先做 Phase 0 路由，只调用当前任务实际需要的智能体，不默认全调用。

角色隔离：

| 子智能体 | 只回答 |
| ---- | ---- |
| GithubExplorer | 别人代码里做了什么？ |
| ResearchScout | 别人论文里做了什么？ |
| ScientificEngineer | 我们应该怎么做，并如何证明？ |
| PaperReviewer | 这些证据足不足以让同行接受？ |

## 2. Phase 0 — 任务解析与路由

### 2.1 单阶段请求：直接放行

| 用户请求类型 | 直接调用 |
| ---- | ---- |
| 单纯搜索 GitHub 项目 / 找可复现仓库 | `GithubExplorer` |
| 查找论文 / 相关工作（单独） | `ResearchScout` |
| 检查公式 / 设计实验（单独） | `ScientificEngineer` |
| 审稿 / 论文弱点分析（单独） | `PaperReviewer` |

产生新 idea / 查新类请求 → 转交 research-pre。

### 2.2 多阶段请求：按模式路由

| 模式 | 用户已有 | 调用链 |
| ---- | ---- | ---- |
| A. Idea Mode | research-pre 移交的 idea card | `GithubExplorer` ∥ `ResearchScout` → Merge → `ScientificEngineer` → `PaperReviewer` → 定向回退 |
| B. Method Mode | 研究问题 + 现有方法 | 同 A（重点在方法改进与实验设计） |
| C. Experiment Mode | 成熟方法，需补实验 | `GithubExplorer`（找 Baseline/实现）→ `ScientificEngineer` → `PaperReviewer`；`ResearchScout` 仅查 Baseline 与相关工作遗漏 |
| D. Paper Mode | 完整论文/草稿 | `GithubExplorer` ∥ `ResearchScout` → `PaperReviewer` 先找问题 → 视问题类型回退 `ScientificEngineer` 补方法或补实验 |

路由结果需向用户简要说明（调用哪些智能体、跳过哪些、为什么）。

## 3. 统一 Research State

承接 research-pre 的 `research-state.md`；若无则按同格式新建。所有子智能体基于同一状态工作，禁止重新从零理解全部问题。发给子智能体时只传其所需字段（见第 8 节）。

## 4. Phase 1 — 双路侦察（并行）

同一条消息并行发起：`GithubExplorer` 输出 GitHub Evidence Pack；`ResearchScout` 输出 Literature Evidence Pack。仓库证据归 GithubExplorer，学术证据归 ResearchScout；ResearchScout 不得把 Star 数、README 或博客作为主要学术依据。职责细节与 Evidence Pack 模板见 [references/agent-contracts.md](references/agent-contracts.md)。

## 5. Phase 2 — Evidence Merge（闸门）

合并两份 Evidence Pack，建立 Research Evidence Matrix，重点检查：① 论文没写但 GitHub 已有高度相似实现（创新存疑）；② 论文写了但公开代码未实现该机制（复现陷阱）。结论写回 Research State。

## 6. Phase 3 — ScientificEngineer（串行）

完成 Merge 后进入；**不允许重新大规模文献检索**。核心要求（完整规范见 [references/scientific-design.md](references/scientific-design.md)）：

- 科学问题链（Problem → Mechanism → Limitation → Proposed Method → Expected Effect）不完整不许直接设计复杂网络
- 每个模块建立 Problem → Mechanism → Operation → Feature Effect → Performance Effect 链条，禁止"加注意力就能涨点"式表述
- 所有公式过数学检查清单；强假设/近似/经验设计显式标记，不许包装为理论推导
- 基于 GithubExplorer 结果做复用分级（Direct Reuse / Adaptation / New Implementation）
- 每个 Claim 映射到具体实验（Main / Baseline / Ablation / Robustness / Generalization / Sensitivity / Failure Case）

输出 Scientific Design Pack。

## 7. Phase 4/5/6 — 评审、定向回退、二次评审

`PaperReviewer` 尽最大可能找出足以导致拒稿的问题（检查清单与报告模板见 [references/reviewer-guide.md](references/reviewer-guide.md)）。收到 Reviewer Report 后按问题类型**只回退对应智能体**：

| 问题类型 | 回退目标 |
| ---- | ---- |
| 文献/创新问题 | `ResearchScout`（必要时加 `GithubExplorer`）；全新 ideation 需求转 research-pre |
| GitHub/复现问题 | `GithubExplorer` + `ScientificEngineer` |
| 方法/实验问题 | `ScientificEngineer` |
| 单纯表达问题 | `PaperReviewer` 直接修正 |

回退携带：原始 Issue + 相关证据 + 该智能体上次输出。修改后二次评审只检查 Major Concern 是否解决、是否引入新问题（Issue Resolution Matrix）。

停止条件（全部满足即停，不为"完美论文"无限迭代）：无致命技术错误、无虚假创新、无关键实验缺失、核心 Claim 均有证据。允许保留：语言问题、非关键补充实验、轻微图表问题、未来工作。

## 8. Token 与效率控制

| 子智能体 | 只传 |
| ---- | ---- |
| GithubExplorer | Research Question、Keywords、Method Summary、Target Evidence |
| ResearchScout | Research Question、Claimed Contributions、Keywords |
| ScientificEngineer | Research State、Evidence Matrix、相关证据摘要 |
| PaperReviewer | 当前 Research State、Scientific Design Pack、实验结果、论文草稿 |

禁止把整篇论文或全部搜索原文发给任何子智能体。

## 9. 论文写作交付（本阶段出口）

实验闭环通过后进入写作，交付物按序产出：

```text
Core-Paper Package
├── 01 Research State（最终版）
├── 02 Literature / GitHub Evidence Pack
├── 03 Research Evidence Matrix
├── 04 Scientific Design Pack
├── 05 Experiment Matrix + Experimental Results
├── 06 Reviewer Report + Issue Resolution Matrix
├── 07 Paper Outline（贡献-方法-实验对齐表）
├── 08 Figure Plan（每图承载的 Claim）
├── 09 Table Plan（主表/消融表/鲁棒性表）
└── 10 Final Draft
```

未调用的智能体对应产物标记"Not applicable (route: X Mode)"，不留空壳。

定稿（或预印本发布）后，告知用户可进入 research-post 生成海报/视频/博客等传播物。
