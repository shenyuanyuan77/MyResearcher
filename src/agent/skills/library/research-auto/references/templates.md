# 状态文件模板

首次在用户项目中初始化 `research/` 目录时按以下模板创建；之后只更新内容不重建结构。

## 目录

- [research/env.md](#researchenvmd)
- [research/state.md](#researchstatemd)
- [research/decisions.md](#researchdecisionsmd)
- [research/results.json](#researchresultsjson)
- [research/objections.md](#researchobjectionsmd)
- [research/state/prompts/](#researchstateprompts)

## research/env.md

```markdown
# 训练环境（每次会话开始向用户确认后更新）
- 更新时间: YYYY-MM-DD
- 执行位置: 本机 Windows / WSL2 / SSH(user@host)
- GPU: 型号 / 显存
- Python: conda env 名或 venv 路径
- 数据集: 路径 + 划分文件路径
- codex: 模型别名 / 校验通过日期
- 备注: 代理、CUDA 版本等
```

## research/state.md

```markdown
# 流水线状态
- 当前阶段: P4
- Gate 历史: P0 ✔ P1 ✔ P2 ✔ P3 ✔（用户 YYYY-MM-DD 批准）
- 验证集划分文件: research/splits/val_split.json
- 基准指标: {"metric": "mAP", "value": 0.0, "seed": 42}
- 任务队列:
  - [x] T1 xxx
  - [ ] T2 xxx（进行中，CHECK 第 1 轮通过）
- 待人类决策: 无
```

## research/decisions.md（追加式日志，禁改历史条目）

```markdown
## D007 | YYYY-MM-DD | PLANNER | P4
- 决策: Neck 的 C2f 替换为 DEConv
- 理由: ...
- 涉及不变量: 1, 2

## D008 | YYYY-MM-DD | ZCODE-DEV | 实现层偏差
- 原计划实现: github.com/x/y 的 Mamba
- 实际实现: 同功能 z/w（CUDA 12.1 兼容）
- 等价性: 接口一致，单测对齐

## D009 | YYYY-MM-DD | USER | 终裁
- 事项: P6 OBJ003
- 裁决: 恢复梯度累积描述
```

## research/results.json

**只由解析脚本生成，禁止 LLM 手写。** 解析脚本每次训练结束后从 `logs/` 提取。

```json
{
  "baseline": {"run_id": "p1-base", "seeds": [42], "metrics": {"mAP": 0.0}},
  "runs": [
    {"run_id": "P4-T3-r1", "decision": "D007", "data_frac": 0.1, "epochs": 30,
     "params_M": 0.0, "flops_G": 0.0, "seeds": [0, 1, 2],
     "metrics": {"mAP_mean": 0.0, "mAP_std": 0.0},
     "delta_vs_baseline": 0.0,
     "verdict": "screening|accepted|rejected"}
  ]
}
```

## research/objections.md

```markdown
## OBJ003 | YYYY-MM-DD | P6
- codex 意见: 删除 3.2 节的梯度累积描述
- Zcode 异议: 实验确实用了累积 4 步，应当披露
- 处理: 服从 codex 已删除，留待用户终裁
```

## research/state/prompts/ 与 research/state/schemas/

- `prompts/`：`planner_prompt.md` / `check_prompt.md` / `reviewer_prompt.md` / `arbiter_prompt.md`。Zcode 每次调用 codex 前生成，可覆盖；超时排查时作为现场快照保留。
- `schemas/`：4 个角色 JSON Schema，从本 skill 的 `assets/schemas/` 复制，传给 `codex exec --output-schema`（原生强制 JSON 契约）。
- `codex_last.md`（及 `codex_last_check.md` 等）：每次调用的最终 JSON 回复，即解析目标；轮询到该文件出现即代表调用完成。
- `plan.md` 的规范路径是 `research/plan.md`（状态文件表定义），PLANNER prompt 中必须写死该路径。
