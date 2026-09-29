# Scientific Design — 方法设计、数学检查与实验矩阵

发起 Phase 3（ScientificEngineer）前必读。ScientificEngineer 消费 Research State + 两份 Evidence Pack + Evidence Matrix，禁止重新进行大规模文献检索。目录：

- [1. 科学问题链](#1-科学问题链)
- [2. 模块设计链](#2-模块设计链)
- [3. 数学检查清单](#3-数学检查清单)
- [4. GitHub 复用分级](#4-github-复用分级)
- [5. 实验设计](#5-实验设计)
- [6. 实验记录](#6-实验记录)
- [7. Scientific Design Pack 模板](#7-scientific-design-pack-模板)

---

## 1. 科学问题链

设计任何方法前，必须先建立完整链路；无法建立完整链路时，不允许直接设计复杂网络：

```text
Scientific Problem
↓
Physical / Mathematical Mechanism
↓
Existing Limitation
↓
Proposed Mechanism
↓
Proposed Method
↓
Expected Observable Effect
```

## 2. 模块设计链

对每一个模块建立：

```text
Problem
↓
Mechanism
↓
Operation
↓
Feature Effect
↓
Expected Performance Effect
```

反例（禁止）：`增加注意力机制可以提高性能`。

必须回答：

```text
什么问题需要 Attention？
Attention 对什么变量加权？
为什么这个变量具有可靠性差异？
这种加权如何影响特征？
最终如何影响任务结果？
```

## 3. 数学检查清单

所有公式逐项检查：

- 变量定义、输入输出
- tensor dimension
- 单位
- 概率定义
- 假设条件、等式成立条件、approximation 条件
- loss function 逻辑
- 推导连续性

遇到以下情况必须显式标记，禁止全部包装为理论推导：

```text
Strong Assumption
Approximation
Empirical Design
Heuristic
Engineering Choice
```

## 4. GitHub 复用分级

根据 GithubExplorer 的结果，把代码分为三级，最终明确 `Existing Code + Modified Code + Novel Code` 三部分清单，防止把已有开源模块错误包装为创新：

| 级别 | 含义 | 典型对象 |
| ---- | ---- | ---- |
| A. Direct Reuse | 直接使用 | dataset loader、evaluation metric、baseline implementation、training framework |
| B. Adaptation | 需要修改 | backbone、loss、augmentation、feature extraction |
| C. New Implementation | 属于当前研究的新模块 | 论文声称的核心创新对应代码 |

## 5. 实验设计

每个 Claim 必须映射到具体实验：

```text
Claim C1 → Experiment E1
Claim C2 → Experiment E2
Claim C3 → Experiment E3
```

至少考虑：

| 实验类型 | 目的 |
| ---- | ---- |
| Main Experiment | 证明整体性能 |
| Baseline | 与最相关方法比较；来源同时考虑 ResearchScout + GithubExplorer |
| Ablation | 验证各核心模块 |
| Robustness | 噪声、参数变化、环境变化、数据扰动 |
| Generalization | 跨 Dataset / Subject / Device / Environment / Condition（按研究问题确定） |
| Parameter Sensitivity | 验证重要参数 |
| Failure Case | 主动寻找方法失败情况 |

## 6. 实验记录

所有实验尽量保留以下字段；实验失败同样属于科研结果，不能删除：

```text
Experiment ID
Git Commit
Dataset Version
Train/Val/Test Split
Seed
Configuration
Environment
Checkpoint
Raw Metrics
Logs
Runtime
```

## 7. Scientific Design Pack 模板

```text
## Scientific Design Pack

Scientific Problem:

Hypothesis:

Method Overview:

Key Contributions:

Mathematical Model:

Algorithm Pipeline:

Existing Components:        （复用分级 A/B）

New Components:             （复用分级 C）

Experiment Matrix:          （Claim → Experiment 映射）

Baseline:

Ablation:

Robustness:

Generalization:

Metrics:

Expected Evidence:

Known Risks:

Implementation Plan:
```
