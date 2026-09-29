# Reviewer Guide — 审稿检查清单与报告模板

发起 Phase 4 / Phase 6（PaperReviewer）前必读。PaperReviewer 不负责证明方案正确，其任务是**尽最大可能找到足以导致论文被拒的问题**。目录：

- [1. 检查清单](#1-检查清单)
- [2. Reviewer Report 模板](#2-reviewer-report-模板)
- [3. Issue Resolution Matrix](#3-issue-resolution-matrix)

---

## 1. 检查清单

### Novelty

```text
创新点是否已经存在？
是否只是已有模块组合？
是否只有工程改进？
```

### Scientific Logic

检查 `Problem → Mechanism → Method → Experiment → Conclusion` 是否闭环。

### Technical Correctness

检查：数学、算法、信号处理、网络设计、物理解释。

### Experimental Fairness

检查 Dataset、Split、Baseline、Hyperparameters、Training Budget、Evaluation Metric 是否公平。

### Evidence

每个主要 Claim 必须有对应来源：

```text
Theory  or  Experiment  or  Citation
```

三者皆无 → 标记 `Unsupported Claim`。

### Reproducibility

检查论文描述能否支持第三方复现。

### Overclaim

特别审查以下措辞是否有充分数据支持：

```text
显著提升 / 有效解决 / 证明 / 鲁棒 / 泛化 / 实时 / 低复杂度
```

---

## 2. Reviewer Report 模板

```text
## Reviewer Report

Overall Recommendation:
Accept | Weak Accept | Borderline | Weak Reject | Reject

### Major Concerns

M1:
M2:
M3:

### Minor Concerns

m1:
m2:

### Novelty Risks

### Technical Risks

### Experimental Risks

### Reproducibility Risks

### Unsupported Claims

### Missing Experiments

### Missing Literature

### Potential Reviewer Questions

Q1:
Q2:
Q3:

### Required Actions
```

---

## 3. Issue Resolution Matrix

第二轮评审（Phase 6）只检查两件事：每个 Major Concern 是否解决、新增修改是否引入新问题。不重新审查全文所有细节。

```text
| Issue | Previous Status | Action | Evidence | Current Status |
| ----- | --------------- | ------ | -------- | -------------- |
```

状态取值：

```text
Resolved
Partially Resolved
Unresolved
```

Unresolved 的问题必须给出理由：要么继续回退对应智能体，要么说明其属于停止条件中"允许保留"的类别。
