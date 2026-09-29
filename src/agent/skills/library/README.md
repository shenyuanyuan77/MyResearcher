# 科研技能库（library/）

共 33 个技能，两个来源：

1. **25 个**封装自本机 ZCode 用户技能（`~/.zcode/skills/` 与
   `~/.agents/skills/`），复制于 2026-09；
2. **8 个**（literature-review / citation-management / hypothesis-generation /
   experimental-design / statistical-power / latex-posters / infographics /
   scientific-schematics）搬运自
   [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills)
   （MIT License），复制于 2026-09。

均只保留方法论与脚本，**排除了** assets/ 示例图、evals/、examples/、tests/
等大体积/非运行必需资源。

## 结构

- 每个技能一个目录，`SKILL.md` 为方法论入口（YAML frontmatter + 正文）；
- `scripts/`、`references/`、`static/`、`templates/` 等为技能自带的工具与规范文件；
- `nature-shared/` 是 nature 系列的公共约束库，被相关技能自动附加。

## 接入方式

- 注册表：`src/agent/skills/registry.py`（frontmatter + 策展中文元数据合并）；
- Agent 工具：`src/agent/tools/research_skills.py` 的 `load_research_skill(skill_id)`；
- 前端目录：`GET /api/skills`（`src/api_view/api/skills.py`）。
- 新增/更新技能：把新 SKILL.md 目录放进来，并在 `registry.py` 的 `CURATED`
  里补一行中文名/分类/触发词/示例即可（不补也会列出，仅少中文说明）。

## 注意

- 技能里的脚本不会在网页端执行；Agent 会给出完整可运行代码或按方法论直接产出文字。
- 文献类技能的事实源仍是学术 MCP 工具（零幻觉铁律不豁免）。
