---
name: evo-automl
description: 文献证据驱动、领域知识约束的进化式深度学习自动优化框架（科研级 AutoML）。当用户要求"进化搜索网络、仿生算法优化模型、NAS、参数与结构协同优化、自动设计网络、雷达/信号处理 AutoML"，或要在新数据集上复用 μEvoNAS 方法论时使用。覆盖：研究资格评估→证据库→优化目标设计→搜索空间编译→三层冒烟→多臂进化搜索→代理可靠性审计→统计裁决→论文资产生成全流程。
---

# evo-automl：文献证据驱动的进化式深度学习自动优化框架

英文定位：**Evidence-guided, Domain-aware Evolutionary AutoML Framework**。
本 skill 不是"自动调参工具"，而是面向科研人员的深度学习模型自动设计助手：
机器负责搜索与统计，人负责定义问题与科学裁决。

```
Literature Evidence + Domain Knowledge + Experimental Protocol
        ↓  (五个供给点，全部由人提供)
Search Space Compiler（证据 → 可搜索空间）
        ↓
Evolutionary Optimization（GA/PSO/DE/Bayesian/Random 可替换）
        ↓
Proxy Reliability Audit（代理可靠性分级，联动终审策略）
        ↓
Statistical Validation（冻结划分 × 多种子 × bootstrap）
        ↓
Scientific Model + 论文资产（方法节/消融计划/审稿风险清单）
```

## 三环节概念骨架（与九阶段的映射）

一切仿生优化 = **编码 → 适应度评价 → 搜索更新** 三环节的多轮迭代
（目标 X* = argmax F(X)，逐步逼近而非一次计算）。本流程的九阶段是这三环节的操作层展开：

| 概念环节 | 定义 | 对应Phase |
|---|---|---|
| 问题编码 | 把实际方案转为算法可处理的数字表示（向量/图/树）；编码决定可搜索范围 | Phase 3 编译 |
| 适应度评价 | 用目标函数 F(X) 判优劣；高适应度→更高概率被保留或扩展 | Phase 2 定标 + Phase 5 代理 + Phase 6 审计 + Phase 7 终审 |
| 搜索更新 | 按评价结果产生新候选：GA=选择/交叉/变异；PSO=个体经验+群体经验；DE=个体间差异；ACO=信息素累积 | Phase 5 进化引擎 |

## 零预设原则（本框架的第一设计律）

**算法不预设答案。** 本 skill 不内置任何"默认模块清单"——
候选池 100% 由用户提供的证据（同模态文献 + 自有历史实验）经登记准入产生；
CNN、Transformer、Mamba 只是可能的表示族实例化，不是默认选项。
skill 提供的是四样与任务无关的东西：证据登记规范、准入规则、
可插拔的表示族引擎、进化与统计协议。

唯一工程边界：基因必须可解码为可执行网络，因此需先选定**表示族**
（chain-CNN / cell-DAG / tree-GP / token-Transformer / hybrid）。
表示族由用户文献的主流结构证据决定（判定规则见 phase-details.md Phase 3 步骤0），
每个表示族内"哪些模块、哪些维度、什么范围"仍全部来自用户证据。
本项目自证可行：CNN链式族（adlib/enas.py）与 ViT token族（adlib/vitbase.py，
前几轮手工搜索用）在同一代码库共存，进化壳层对两者通用。

## 五个供给点（人在流程中提供的全部内容）

| # | 供给点 | 内容 | 我们的DIAT实例 |
|---|--------|------|----------------|
| 1 | 任务与数据 | 数据集、预处理链、防泄漏划分、指标 | DIAT-μSAT、锁定STFT协议、采集块级3879/484/486、macro-F1 |
| 2 | **用户文献驱动的候选池** | 从用户给的文献+自有实验中登记的模块，每条带出处与作用 | 残差块(RadSATNet文献)、深度可分离(MobileNet系文献)、膨胀DS(自有AnyDwell) |
| 3 | 搜索空间 | 表示族 + 可变维度与范围（由证据推断，非内置） | 链式CNN族：级数/块数/算子/连续宽度 |
| 4 | **优化目标与预算**（最先设计） | fitness形式：max什么/min什么/硬约束多少 | max macro-F1，硬预算 Params≤600K，记录(精度,参数量)供帕累托 |
| 5 | 实验协议与裁决规则 | 训练配方、种子、显著性标准、提升门槛 | 60ep×3种子、bootstrap×2000 CI不含零、0.5pp门槛 |

**规则：供给点4（优化目标）在进入搜索空间编译之前必须先落盘。**
没有目标定义就不准开始设计空间——否则算法会朝着错误方向进化
（例如无约束时产出100M参数的"最优"模型）。多目标形式化参照 EvoXBench：
max F1 同时 min Params/FLOPs/Latency，预算可做硬约束（超限直接不合格）
或软约束（进fitness罚项）。

## 九阶段流程

| Phase | 名称 | 输入 | 输出 | 门禁 |
|---|---|---|---|---|
| 0 | Research Qualification | 任务描述 | 适用性评分0-10+劝退判据 | <6分停止并说明 |
| 1 | Evidence Collection | 文献/历史实验 | Evidence Bank（四类证据） | 每个零件有出处 |
| 2 | Objective Design | 任务需求 | 优化目标+约束+预算文档 | 目标可计算、可复算 |
| 3 | Search Space Compiler | Evidence Bank | 基因编码规范+准入表+4个yaml | 三层冒烟全过 |
| 4 | Search Validation | 空间+评价环境 | 冒烟通过记录 | 随机基因前向30/30、2ep代理、2ep全链路 |
| 5 | Evolutionary Search | 全部配置 | 各臂search_log | 至少2臂：进化主臂+等预算随机对照臂 |
| 6 | Search Audit | top候选 | Spearman ρ分级+终审策略 | ρ分级强制联动（见规则R3） |
| 7 | Final Adjudication | top-K×3种子 | 最终主表+bootstrap | CI不含零才可声明显著 |
| 8 | Ablation & Paper Assets | 全部结果 | 消融矩阵+方法节草稿+审稿风险清单+实验日志 | 日志入库、索引更新 |

各 Phase 的详细模板、问题清单、评分细则见
[references/phase-details.md](references/phase-details.md)。

## 硬规则库（防坑规则，全部来自实测教训，不可绕过）

- **R1 代理只准粗筛**：top-1 不许直接采信；终审至少 top-3 全量×3种子。
  实测依据：DIAT上代理-全量 Spearman ρ=0.355。
- **R2 随机对照臂必做**：等预算随机搜索是归属检验，回答"收益来自进化还是来自预算"。
  DIAT实测：GA种群均值+9.4pp但最优个体差距不显著——这个结论必须有能力说出来。
- **R3 代理可靠性分级联动**（Phase 6 输出直接改 Phase 7 策略）：
  ρ>0.7 High → top-3 终审；0.4~0.7 Medium → top-5 终审；
  ρ<0.4 Low → 禁止依赖代理排序，top-10 全量终审或重新设计代理。
- **R4 宽度默认连续编码**：离散档位（如{32,64,96}）易被代理过拟合
  （DIAT实测：离散臂代理0.994→test仅0.930）。
- **R5 协议先冻结后搜索**：划分文件、种子、指标、目标函数在搜索前落盘，之后不可改。
- **R6 三层冒烟不过不准开搜**：L1随机基因前向(30/30) → L2代理评价2ep → L3全链路2ep。
  实测教训：级间通道变化缺过渡卷积这类错误只有L1能提前暴露。
- **R7 负结果如实入日志**：权重继承墙钟中性、离散宽度反例等照写——可信度资产。
- **R8 消融矩阵最低配置**：①协同超参消融(同结构换默认超参) ②随机搜索对照 ③宽度编码
  ④按需加权重继承。缺①则"参数优化"主张无证据。
- **R9 NaN排查顺序**：除零→log取零→BF16溢出；消融用10%子集+1/3轮数先看趋势，
  但终审结论必须全量（小样本上10%趋势可能反转，DIAT实测三段反转）。
- **R10 优化器可替换**：进化引擎是可插拔接口（GA/PSO/DE/ACO/Bayesian/Random），
  换引擎不换协议；引用时对应文献（GA→综述#12、PSO→SLE-NAS、DE→TPEvo-CNN、
  ACO适合离散组合/路径型空间、Bayesian/Random作对照）。
  多目标fitness时选择机制换 NSGA-II 式非支配排序（引EvoXBench），锦标赛仅用于单目标。

## 配置驱动接口（换任务只换yaml，不动引擎）

```
project/
├── task.yaml          # 任务名、指标、优化目标、约束预算
├── search_space.yaml  # 零件库、维度、范围、编码
├── evaluation.yaml    # 代理协议、终训配方、统计标准
└── evidence.yaml      # 证据库（每零件的出处与作用）
```
模板见 [templates/](templates/)。参考实现（Python/PyTorch）：
`D:\Innodemo\code\adlib\enas.py`（基因组/EvoNet/权重池/GA）、
`run_enas_search.py`、`run_enas_final.py`、`enas_analysis.py`，
及完整案例 `D:\Innodemo\实验日志\DIAT\DIAT-G-260916-001.md`。

## 论文资产生成（Phase 8 交付的一部分）

运行结束后自动产出四件写作资产，模板见
[references/writing-assets.md](references/writing-assets.md)：
方法节骨架（双层优化形式化+证据驱动叙事）、搜索空间准入表（LaTeX）、
消融计划表、审稿风险问答清单（"为什么不是随机搜索？""代理可信吗？"
"为什么允许这个模块存在？"等预置回答）。

## 文献证据映射（Evidence Bank 的方法学层）

零件准入看"同模态论文+自有历史实验"，机制选择看"方法学顶刊"。
14篇ENAS文献到设计决策的完整映射表见
[references/evidence-bank.md](references/evidence-bank.md)。

## 扩展方向

- **Radar-AutoML**：物理先验约束（时频几何、多普勒谐波结构、信噪比条件化）
  作为搜索空间与目标的内建维度，面向雷达信号处理专化。
- 神经进化（权重也进基因）、超网权重共享路线（显存充足时）、
  学习型代理/比较器（替代低保真训练）。
