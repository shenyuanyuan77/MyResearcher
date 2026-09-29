"""科研技能加载工具：按需把 SKILL.md 方法论注入上下文（渐进式披露）。

技能库来自本机 ZCode 科研 skills 的封装（src/agent/skills/library/），
注册表见 agent.skills.registry。工具只读本地文件，不触网。
"""

from __future__ import annotations

from langchain_core.tools import tool

from agent.skills.registry import list_skills, read_skill_body


def _catalog_line() -> str:
    """生成工具描述里的技能目录（一行一个：id — 中文名）。"""
    return "\n".join(
        f"- {s.id}（{s.zh}，{s.category}）" for s in list_skills()
    )


@tool
def load_research_skill(skill_id: str) -> str:
    """加载一个科研专业技能的完整方法论（SKILL.md 全文），并严格照其流程执行。

    触发场景（用户提到对应需求时**必须先调用本工具**再回答）：
    论文精读卡片 / 全文中英对照精读 / 文献日推流水线 / 全文下载 /
    参考文献逐条核验 / CNS 级引文 / 论文写作与 LaTeX / 润色去 AI 腔 /
    开题报告 / 审稿意见回复 / 模拟审稿 / 统计审计 / 数据可用性声明 /
    科研绘图与 AI 绘图提示词 / 论文转 PPT / 图片转 PPT / 实验日志 /
    论文转专利 / 进化式 AutoML / 科研全流程与自动化流水线。

    可用技能：
{catalog}

    Args:
        skill_id: 技能唯一标识（上表括号前的英文 id），
                  例："nature-paper-card"。一次只加载一个；任务跨越多个
                  技能时依次分别加载。

    Returns:
        该技能的完整方法论文本；id 无效时返回可用技能清单。
    """
    return read_skill_body(skill_id)


# 用真实目录覆盖 docstring 占位符，保证技能清单始终与 library/ 同步
load_research_skill.__doc__ = load_research_skill.__doc__.replace(
    "{catalog}", _catalog_line()
)

# 供展示/诊断用
SKILL_CATALOG = _catalog_line()
