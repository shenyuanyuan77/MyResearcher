# Agent Contracts — 子智能体职责边界与 Evidence Pack 模板

发起 Phase 1 前，按本文为每个子智能体准备最小输入并约定输出格式。目录：

- [1. 角色边界](#1-角色边界)
- [2. GithubExplorer 合同](#2-githubexplorer-合同)
- [3. ResearchScout 合同](#3-researchscout-合同)
- [4. Research Evidence Matrix](#4-research-evidence-matrix)

---

## 1. 角色边界

```text
GithubExplorer       回答：别人代码里做了什么？
ResearchScout        回答：别人论文里做了什么？
ScientificEngineer   回答：我们应该怎么做，并如何证明？
PaperReviewer        回答：这些证据足不足以让同行接受？
```

两个侦察智能体的输入相互独立、输出互不依赖，因此并行发起；它们之间不得互相引用对方未产出的结论。

---

## 2. GithubExplorer 合同

回答的问题：**工程和开源社区里已经有什么？**

### 输入（最小集）

```text
Research Question
Keywords（方法名、数据集名、任务名）
Method Summary（当前方法一段话）
Target Evidence（希望它找什么：Baseline / 官方实现 / Benchmark / Dataset / 评估框架）
```

### 职责

**Repository Search** — 搜索：

- 相关科研代码、官方论文代码
- Baseline、Benchmark、Dataset、Evaluation Framework
- 可复现实验、同类模型实现、相似算法实现

**Source Inspection** — 必须尽可能深入检查仓库内容，不能仅根据 README 判断：

```text
README / configs/ / models/ / datasets/ / scripts/ / tests/
requirements / environment / issues / pull requests / releases
```

### 输出：GitHub Evidence Pack

```text
## GitHub Evidence Pack

### Repository 1
Name:
URL:
Purpose:
Related Method:
Key Source Files:
Dataset:
Experiment Entry:
Metrics:
Reproducibility:
What We Can Reuse:
Risks:
（每个仓库重复此块）

### Existing Implementations
已有实现：

### Existing Baselines
可用 Baseline：

### Existing Benchmarks
可使用 Benchmark：

### Useful Components
值得借鉴的组件：

### Engineering Gap
开源实现仍然没有解决的问题：
```

---

## 3. ResearchScout 合同

回答的问题：**学术界已经研究到什么程度？**

### 输入（最小集）

```text
Research Question
Claimed Contributions（C1、C2、C3…逐条）
Keywords
```

### 职责

**Literature** — 寻找：最相关论文、最新论文、高引用经典论文、最接近当前方法的论文。

**Novelty** — 对每个创新点分别检查，给出四级判定：

```text
Contribution C1 / C2 / C3 …
判定：完全相同 | 高度相似 | 部分相似 | 暂未发现
（附论文证据）
```

**Research Gap** — 必须按真实证据构造链条，而不是为了证明创新强行找 Gap：

```text
Existing Problem
↓
Existing Methods
↓
Remaining Limitation
↓
Research Gap
```

**纪律**：不得把 GitHub Star 数、README 或博客作为主要学术依据。

### 输出：Literature Evidence Pack

```text
## Literature Evidence Pack

Research Problem:

Closest Papers:

Paper 1:
  Method:
  Contribution:
  Dataset:
  Result:
  Limitation:
  Relation to Current Work:
Paper 2: …

Existing Research Paradigm:

Known Limitations:

Potential Research Gap:

Novelty Risks:

Missing Baselines:

Recommended Papers:
```

---

## 4. Research Evidence Matrix

Phase 2 合并两份 Evidence Pack 时建立：

| 科研问题 | 学术界已有方法 | GitHub 是否存在实现 | 当前方法 | 是否仍有 Gap |
| ---- | ------- | ------------- | ---- | -------- |

必须显式标出的两种危险情况：

1. **创新性存疑**：论文没有直接写这个方法，但 GitHub 已存在高度相似实现。
2. **复现陷阱**：论文提出了该方法，但公开代码实际并没有实现论文描述的机制。

矩阵行按 Research Question 拆分，一行一个可验证的子问题；"是否仍有 Gap" 必须引用证据（论文引用或仓库 URL），不允许只写"是/否"。
