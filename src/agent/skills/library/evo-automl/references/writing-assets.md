# 论文资产生成模板（Phase 8 交付）

## 一、方法节骨架（问题驱动叙事，禁止"我们搜索了一个网络"式写法）

```
1. 通用形式化（开篇）：优化目标 X* = argmax F(X)，X=候选方案（结构+超参基因），
   F=适应度；强调多轮迭代逐步逼近而非一次计算；再特化为双层优化
   min_a F(a, w*_a)  s.t.  w*_a = argmin_w L(a,w)（权重仍由梯度训练，
   仿生算法不替代梯度优化，只作用于设计阶段——终模型按普通流程训练测试部署）。
2. 领域问题：现有<X任务>网络（列举文献方法）的结构与超参依赖人工试错，
   从未被系统优化；且<数据特点：实测数据稀缺/类不均衡/…>使标准NAS的
   全量训练评价既昂贵又不可靠。
3. 方法：分层混合基因（离散结构+连续宽度+训练参数）联合进化
   （编码引SLE-NAS，协同引TPEvo-CNN/MetaNAS）+ <低保真代理描述>
   + 预算硬约束 + 代理可靠性审计（自有贡献，ρ实测）。
4. 统计协议：冻结<块级>划分×3种子×bootstrap×2000（引BenchENAS公平比较思想）。
```

## 二、搜索空间准入表（Search Space Justification Table，LaTeX）

```latex
\begin{table}[t]
\caption{Search space justification: every component admits documented evidence}
\centering
\begin{tabular}{lllc}
\toprule
Component & Source & Role & Searched \\
\midrule
Residual block   & RadSATNet (dataset SOTA) & stable deep training & \checkmark \\
Depthwise-sep.   & MobileNet family + in-domain baseline & $\sim$10$\times$ fewer params & \checkmark \\
Dilated DW (d=2) & own prior experiments & wider TF receptive field & \checkmark \\
\bottomrule
\end{tabular}
\end{table}
```

基因表：维度 | 类型 | 范围 | 依据（每行一条文献或自有实验出处）。

## 三、消融计划表

| 消融 | 配置 | 回答 | DIAT实测预期量级 |
|---|---|---|---|
| no co-optimized HP | 同结构×默认超参 | 参数优化贡献 | +1.78pp(显著) |
| random search | 等预算随机臂 | 进化归属 | 最优差不显著,种群均值+9.4pp |
| discrete width | {32,64,96}档位 | 连续编码价值 | 代理过拟合反例 |
| no weight inheritance | 继承关闭 | 评价加速价值 | 墙钟中性(如实报) |

## 四、审稿风险问答清单（Reviewer Risk Checklist）

| 审稿人可能问 | 预置回答（数据来自本流程产出） |
|---|---|
| 为什么不是随机搜索就够？ | 我们跑了等预算随机对照臂：种群均值+9.4pp说明进化系统性改善群体；最优个体差距如实报告(不显著则如实写)，主张落在"稳定产出高质量候选+可解释收敛模式" |
| 代理评价可信吗？ | 强制审计给出Spearman ρ与分级策略(Low级→top-10全量终审)；并报告代理分数跨度压缩比与过拟合个案 |
| 为什么允许这些模块进搜索空间？ | 准入表逐条给出同模态文献/自有实验证据 |
| 会不会搜索过拟合验证集？ | 划分冻结在采集块级；终审在独立test；3种子±std；显著性bootstrap |
| 换数据集还成立吗？ | 框架与协议可迁移；零件库按Evidence Bank规则重准入 |
| 提升幅度多大算数？ | CI95不含零且>0.5pp门槛 |

## 五、诚实负结果段落模板

```
Two negative findings are reported for the community:
(1) the low-fidelity proxy correlates weakly with full training
    (Spearman ρ=<val>), confirming that on small radar datasets proxies
    can only coarse-rank; our protocol therefore mandates <K>-candidate
    full retraining (Rule R3);
(2) <机制> showed no wall-clock benefit (<数值>) at this model scale —
    retained in the framework as optional, reported for honesty.
```

## 六、实验记录规范

- 每轮一个日志：`实验日志/<体系>/<体系>-G-YYMMDD-NNN.md`，含设计→执行→结果三段
- 结果编号：E0复杂度 / E1搜索动态 / E2代理审计 / E3主表+显著性 / E4消融
- 每run目录：ckpt_best.pt + result.json + probs_test.npz（供bootstrap复算）
- 索引表：`实验日志/实验索引.md` 追加一行（日期/体系/类型/状态/关键结果/日志链接）
