# codex 调用协议

## 目录

1. [首次运行校验](#首次运行校验)
2. [通用调用模板](#通用调用模板)
3. [四类调用与 JSON Schema](#四类调用与-json-schema)
4. [失败兜底（逐级）](#失败兜底逐级)
5. [Token 纪律](#token-纪律)

## 首次运行校验

每个项目的第一次会话执行（之后本会话缓存结果）：

```bash
codex --version
codex login status        # 或 codex auth status，以实际版本为准
codex exec --help         # 确认 -m / -c / -s / -C / -o / --output-schema / --skip-git-repo-check 旗标存在
```

任一步失败 → 停止流水线，报告用户。**禁止**在 codex 不可用时静默改为 Zcode 独立决策（除非用户明示降级）。

**模型别名校验**（冒烟测试教训）：用户口中的简称可能与真实别名不同（如"gptluna"实为 `gpt-5.6-luna`）。别名以模型目录为准：

```bash
grep -i "<简称>" ~/.codex/models_cache.json
```

若调用报 `The '<x>' model is not supported when using Codex with a ChatGPT account`，即别名不对，先查目录再重试。常见可用档（2026-09 实测）：`gpt-5.6-sol`（主力工作模型）、`gpt-5.6-luna`（快速便宜档）、`gpt-5.6-terra`、`gpt-5.5`。确认后的别名写入 `research/env.md`。

**档位建议**（实测依据，会话启动时与用户确认）：PLANNER / REVIEWER 用主力模型 + high effort（质量优先）；CHECK / ARBITER 调用频次高，可用快速档（如 luna）降本，reasoning effort 仍 high。

**schema 初始化**：把本 skill 的 `assets/schemas/*.json`（4 个角色 schema）复制到项目 `research/state/schemas/`。

## 通用调用模板

以下模板经冒烟测试验证（codex-cli 0.151.0，Windows / Git Bash）：

```bash
codex exec \
  -m "<已确认的模型别名>" \
  -c model_reasoning_effort=high \
  -s <sandbox> \
  -C "<项目根目录>" \
  --skip-git-repo-check \
  --output-schema "research/state/schemas/<role>_schema.json" \
  -o "research/state/codex_last.md" \
  "$(cat research/state/prompts/<role>_prompt.md)"
```

- **sandbox 按角色**：PLANNER 用 `workspace-write`（要写 plan.md）；CHECK / REVIEWER / ARBITER 用 `read-only`（只需读文件，更安全）。已在 config 设 `approval_policy=never` 时无需额外审批旗标。
- **`--output-schema` 是 JSON 契约的原生强制**（实测 3/3 次调用返回 schema 合法 JSON），prompt 里的"仅输出 JSON"指令保留作双保险。`codex_last.md` 即纯 JSON，直接 `json.load` 解析。
- **非 git 目录必须带 `--skip-git-repo-check`**（git 仓库内带上也无害）。
- **实测延迟**：单次调用 3-4 分钟、24-38K tokens（luna + high）。因此：
  - 短调用（CHECK）：前台执行，Bash timeout 600000ms（上限）；
  - 长调用（PLANNER / REVIEWER）：`run_in_background: true` 后台执行，轮询 `codex_last.md`；后台 15 分钟无产出按超时处理。
- **prompt 文件**由 Zcode 每次调用前生成到 `research/state/prompts/<role>_prompt.md`（可覆盖），内容 = 角色指令 + codex 需自行读取的文件路径清单。**prompt 里引用的路径必须逐字与状态文件表一致**（冒烟测试发现：prompt 写什么路径 codex 就写哪，错路径不会被纠正）。不要把文件内容粘贴进 prompt，codex 有工作区读权限。

## 四类调用与 JSON Schema

### 1. PLANNER（规划）

- 触发：进入新阶段、P4 每个新实验、回退重规划。
- codex 必读：state.md、decisions.md、results.json、env.md + 阶段相关文件。
- codex 动作：直接覆写 `research/plan.md`（**此路径写死在 prompt 里，不留给 codex 自选**），last message 返回：

```json
{
  "role": "PLANNER",
  "phase": "P4",
  "decision": "一句话决策",
  "tasks": [
    {"id": "T1", "type": "implementation|experiment|analysis|writing",
     "action": "具体做什么", "targets": ["将改动的文件"],
     "acceptance": "可验证的完成标准", "invariants": [1]}
  ],
  "risks": ["..."],
  "open_questions": ["需要人类回答的问题，可为空数组"]
}
```

### 2. CHECK（任务级审核，每个任务完成即调）

- 输入：task_id + Zcode 完成摘要（≤200 字）+ 触碰文件清单 + results.json 增量。

```json
{"role": "CHECK", "task_id": "T1",
 "verdict": "pass|revise|fail",
 "required_fixes": ["verdict != pass 时必填"],
 "notes": "..."}
```

- pass → 标记完成，继续下一任务。
- revise → Zcode 修复后重新 CHECK；同一任务最多 2 轮，超过升级 ARBITER。
- fail → 任务作废，回 PLANNER。

### 3. REVIEWER（gate 验收 / 论文审稿）

mode=gate 验收当前阶段；mode=paper 审稿。

```json
{"role": "REVIEWER", "mode": "paper",
 "findings": [
   {"target": "章节/文件/实验编号", "severity": "blocking|major|minor",
    "comment": "问题", "fix_hint": "修法建议", "who_fixes": "codex|zcode"}
 ],
 "blocking_count": 0}
```

- minor/major 且 who_fixes=codex → codex 直接改文件，改动记入 decisions.md。
- 重构级修改 → codex 出指令，Zcode 执行。
- gate 验收时 codex 有权点名要求 Zcode 附任意文件原文（防状态摘要有偏）。

### 4. ARBITER（冲突裁决）

- 输入：冲突双方陈述（各 ≤150 字）+ 相关 decisions.md 条目。

```json
{"role": "ARBITER",
 "ruling": "codex|zcode|escalate_user",
 "rationale": "..."}
```

- ruling=zcode → Zcode 按己见执行并记 decisions.md。
- ruling=codex → Zcode 服从，异议记 objections.md。
- escalate_user → 停下问用户。
- 选题、算力预算类冲突不经 ARBITER，直接找用户。

## 失败兜底（逐级）

1. **codex 命令不存在 / 未登录** → 报告用户，流水线暂停。禁止静默降级。
2. **超时**（前台 300s / 后台 15 分钟无产出）→ kill 后改 `run_in_background` 重试一次；再超时 → 保存现场（prompt 文件 + 状态包快照），询问用户。
3. **输出非 JSON / 解析失败** → 追加一次修复调用："上一次输出无法解析为 JSON，仅输出符合 schema 的 JSON，不要任何其他文字"。再失败 → 降级为文本人工解析，decisions.md 记 `format_degraded`。
4. **计划违反不变量** → 自动打回 PLANNER，附违反的不变量编号；不打扰用户、不静默修改。同一计划同一不变量打回 2 次仍违反 → 升级用户。
5. **codex 改了 `research/` 之外的文件** → CHECK 时发现即回滚该改动（git 或备份），记 objections.md。

## Token 纪律

- "每个任务完成即 CHECK"是用户定的节奏，不削减频次；但 CHECK 输入摘要必须 ≤200 字 + 增量数据，禁止粘贴整份日志。
- 原始训练日志永不进 prompt；进 results.json 的只有脚本解析后的数字。
