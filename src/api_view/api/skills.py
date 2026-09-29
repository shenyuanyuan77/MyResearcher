"""
科研技能中心 API

提供技能库列表查询（供前端技能中心展示与一键发起技能对话）。
技能本体由 Agent 工具 load_research_skill 在对话内按需加载。
"""

from typing import List

from fastapi import APIRouter, Depends

from agent.skills.registry import list_categories, list_skills
from api_view.auth import UserInfo, get_current_user


router = APIRouter()


@router.get("/skills", summary="列出全部科研技能与分类")
async def list_research_skills(current_user: UserInfo = Depends(get_current_user)) -> dict:
    """返回技能库目录（六大分类 + 技能明细：中文名/触发词/示例指令）。"""
    skills: List[dict] = [s.to_api_dict() for s in list_skills()]
    return {
        "ok": True,
        "total": len(skills),
        "categories": list_categories(),
        "skills": skills,
        "user": current_user.username,
    }
