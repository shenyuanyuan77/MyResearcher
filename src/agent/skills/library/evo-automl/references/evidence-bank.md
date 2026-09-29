# Evidence Bank：证据库规范与文献映射

## 一、证据类型 schema（evidence.yaml 的填写规范）

```yaml
data_source:
  dataset: DIAT-uSAT
  paper: "DIAT-SAT_Small_Aerial_Targets_Micro-Doppler_Signatures_and_Their_Classification_Using_CNN"
  records: 4849
  classes: 6
  preprocessing: "重采样10kHz→去直流→6阶Butterworth低通2kHz→STFT(hamming256/ov200/nfft1024)→±2kHz→50dB相对dB→[0,1]→128×532"
  split: "冻结采集块级 3879/484/486（防近亲泄漏）"

baselines:
  - {name: RadSATNet-40L, source: "DIAT-RadSATNet 2022 论文忠实复现†", test_mv: 0.957, params: 409926}
  - {name: MobileNetV3-S, source: torchvision, test_mv: 0.931}
  # ... 同数据集文献方法逐条登记（指标、划分口径必须一致才可比）

parts:   # 零件准入表 —— 每行必须有出处与作用，否则不准入
  - {part: residual_block,  source: "RadSATNet(同数据集SOTA)", role: "稳定深层训练", admit: true}
  - {part: ds_conv_block,   source: "MobileNet系+本数据集MBv3S基线0.931", role: "参数量降一个量级", admit: true}
  - {part: dilated_ds_block, source: "自有实验 AnyDwell(DIAT-G-260908)", role: "扩大时频感受野匹配谐波间隔", admit: true}

mechanisms:   # 机制证据：方法学设计决策 → 文献出处
  - {decision: 连续宽度编码, evidence: "SLE-NAS TNNLS 2024 (#04)"}
  - {decision: 参数-结构协同进化, evidence: "TPEvo-CNN (#13) + MetaNAS (#01)"}
  - {decision: 低保真代理+可靠性审计, evidence: "Fast Memetic(#11)单epoch思想 + 自有ρ=0.355实测"}
```

## 二、零件准入判断口诀

> **零件只看用户提供的证据：同模态文献 + 用户自有历史实验；机制看方法学顶刊。**

零预设原则：本 skill 不内置任何默认模块清单；候选池 100% 由用户证据登记产生。
若用户文献以 Transformer/Mamba 为主，候选池就应是注意力/状态空间组件族，
而不是 CNN 块——表示族本身也由文献证据选择（见 phase-details.md Phase 3 步骤0）。

- 零件准入三问：这个模块在**用户给的文献**或用户历史实验中被验证过吗？
  作用讲得清吗（为什么允许它存在——如雷达上Transformer=长程周期依赖、
  CNN=局部微多普勒纹理）？显存/预算装得下吗？
- 无同模态证据的新模块：先做单点验证实验，再准入空间；不直接进搜索。
- 机制（编码/评价/多目标）不需要同模态验证，看方法学顶刊即可。

## 三、14篇 ENAS 文献 → 设计决策映射表（引用骨架）

| 设计决策 | 文献 | 期刊/年 | 在流程中的位置 |
|---|---|---|---|
| 连续宽度分层编码（整数=层配置/小数=宽度） | SLE-NAS | TNNLS 2024 | Phase 3 编码规范 |
| 精英权重继承（在线权重池） | SLE-NAS | TNNLS 2024 | Phase 5 评价加速 |
| 参数+结构分阶段协同 | TPEvo-CNN | IEEE Access 2023 | Phase 3 基因设计 |
| 元学习LR影响评价公平 | MetaNAS | TCSVT 2025 | Phase 3 训练参数段依据 |
| 进化×梯度混合（超网） | GENAS | TNNLS 2025 | 扩展路线（显存充足时） |
| 脑启发搜索空间（领域先验进空间） | MSE-NAS | TEVC 2025 | 扩展路线（Radar-AutoML） |
| 树编码进化拓扑 | NASGP-Net | TEVC 2024 | 扩展编码（连接方式维度） |
| 单epoch低保真评价 | Fast Memetic | TNNLS 2023 | Phase 3 代理设计 |
| 比较器式代理（排序→分类） | Pareto-Wise Ranking | TEVC 2024 | 扩展代理（学习型） |
| 模糊搜索空间抗标注噪声 | Fuzzy NAS | TFS 2024 | 扩展（噪声数据任务） |
| NAS=多目标优化形式化+免GPU基准 | EvoXBench | TEVC 2024 | Phase 2 目标设计 |
| 精度+时间双目标 | MOEA-PS | TEVC 2023 | Phase 2 目标设计 |
| 资源硬约束（罚函数+修复，动机点名UAV） | Auto-CNN Constraints | TNNLS 2023 | Phase 2 预算约束 |
| 公平比较协议（统一环境/种子） | BenchENAS | TEVC 2022 | Phase 7 统计规范 |
| 全景综述（编码/算子/评价三段框架） | ENAS Survey | TNNLS 2023 | 引言+方法论框架 |

文献PDF位置：`C:\Users\Trashmak1r\Desktop\智能仿生算法NAS文献_2022-2025\`（含README清单）。

## 四、DIAT 案例校准数据（预算与预期参照）

- 搜索成本：GA主臂130评价×13s ≈ 30min（RTX 3050 4GB 笔记本）
- 终训成本：8min/种子（12.9万参数网络，60ep全量）
- 代理保真度：ρ=0.355（Low级）→ 触发R3的top-K终审而非top-1
- 群体效应：GA种群均值0.9347 vs 随机0.8412（+9.4pp），最优个体+0.59pp不显著
- 终局：top-1 test 0.9778(mv)，vs文献SOTA +2.11pp显著；协同超参贡献+1.78pp显著
- 负结果：权重继承墙钟1.02×中性；离散宽度代理过拟合（0.994→0.930）
