# 七阶段 gate 判定规则

每阶段统一节奏：入口条件 → 执行 → gate 验收（REVIEWER mode=gate，全量读状态包）→ 通过则在 state.md 推进阶段；失败走回退边。

## 目录

- [P0 SOTA 学习](#p0-sota-学习)
- [P1 复现 baseline](#p1-复现-baseline)
- [P2 模块剖析](#p2-模块剖析)
- [P3 选题（人类否决点）](#p3-选题人类否决点)
- [P4 单点改造实验（主循环）](#p4-单点改造实验主循环)
- [P5 写作](#p5-写作)
- [P6 互审](#p6-互审)
- [不变量校验表](#不变量校验表)

## P0 SOTA 学习

- 入口：用户给定本地数据集 + 同数据集近年论文（或授权联网检索）。
- 动作：ResearchScout 逐篇产出笔记到 `papers/`：baseline、核心框架（MIP/CNN/Transformer/Mamba 等，声明为不动部分）、各模块功能、可迁移模块候选。
- Gate：≥3 篇结构化笔记 + 汇总可迁移模块清单（每项含来源、功能、开源实现线索）。
- 回退：笔记不足 → 继续检索；清单为空 → 换关键词/扩年份。

## P1 复现 baseline

- 动作：GithubExplorer 定位官方/可信开源实现 → PLANNER 出复现计划 → Zcode 按 env.md 搭环境 → 固定种子跑通。
- Gate：结果与论文报告对齐（容差由 codex 在计划中显式给出，默认 ±0.3 点）+ 基准表写入 results.json + **验证集划分文件存档**（路径记入 state.md，全程复用）。
- 回退：对不上 → 先按不变量 8 排查预处理（Resize 方式、归一化参数），再查种子与版本；连续 2 轮修不好 → 升级用户（可能需换 baseline）。

## P2 模块剖析

- 动作：PLANNER 列剖析清单 → Zcode 逐模块产出文档。
- Gate：baseline 每个非骨干模块一份剖析：输入输出 shape、参数量、FLOPs、功能假设、可替换性评级（A=易替换/B=需适配/C=强耦合）。CHECK 通过。

## P3 选题（人类否决点）

- 动作：ResearchScout 拉候选 + GithubExplorer 验证开源可用 → PLANNER 按三维排序：novelty 风险 / 实现成本 / 预期增益 → 输出候选表。
- Gate：**用户明确批准 1 个主候选 + 1-2 个备选** + 故事线文档（领域适配 + 机制分析叙事，写明与"简单替换"的区分点）。
- 铁律：未经用户批准不得进 P4。

## P4 单点改造实验（主循环）

每轮固定节奏：

1. PLANNER 设计单个实验（含消融配置与全量配置两套）。
2. Zcode 过不变量校验表 → 违反自动打回。
3. 实现 + 报告 params/FLOPs。
4. 筛选：10% 数据 + 1/3 epochs → results.json → CHECK。
5. 筛选有效 → 3 种子全量 → results.json → CHECK。
6. REVIEWER mode=gate 判定。

- Gate：相对基准提升 ≥0.5 点（均值±std 口径）→ 进 P5。
- 回退：不达标 → 回 P3 启用下一备选（决策留痕 decisions.md）。这是显式回退边，不是失败。

## P5 写作

- 动作：PLANNER 出大纲（显式参照 baseline 论文的章节逻辑与问题引入方式）→ Zcode 逐节起草 → 每节完成即 CHECK → 可调用 nature-writing / nature-figure / happy-figure-skill。
- Gate：全文初稿齐 + 每张图表有可复现脚本。

## P6 互审

- 动作：PaperReviewer 预筛（廉价第一道）→ REVIEWER mode=paper 分级审 → 修订循环。
- Gate：blocking_count = 0 → **用户终稿**。用户终裁后 state.md 标记 done，流水线结束。
- 分歧处理：Zcode 异议记 objections.md 后服从 codex；用户可终裁改判。

## 不变量校验表

Zcode 在执行任何 codex 计划前逐条过一遍。违反 → 自动打回 PLANNER（附编号）；同一计划同一不变量打回 2 次 → escalate_user。

| # | 校验点 | 违反处理 |
|---|---|---|
| 1 | 单点修改；Neck/Head 优先；动 Backbone 需 codex 显式理由+风险 | 打回 |
| 2 | 改后先报 params/FLOPs 再开训 | 打回 |
| 3 | 固定种子；验证集划分文件存档复用 | 打回 |
| 4 | 筛选 10% 数据 + 1/3 epochs；全量仅用于通过筛选的改动 | 打回 |
| 5 | 正式结论 ≥3 种子、均值±std、提升 <0.5 点不认可 | 打回 |
| 6 | 默认 BF16；NaN 先查除零/对数取零；OOM→梯度累积 4 步+BN→GN | 打回 |
| 7 | BS 翻倍 LR 翻倍；warmup 500-1000；cosine；WD ∈ {0.01, 0.05} | 打回 |
| 8 | 复现失败先查预处理（Resize/归一化） | 打回 |
