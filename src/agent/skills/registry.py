"""
科研技能库注册表。

library/ 下每个子目录是一个从本机 ZCode skills 封装来的科研技能，
目录名即 skill_id，其 SKILL.md 携带 YAML frontmatter（name/description）。

注册表职责：
1. 扫描 library/ 构建技能索引（frontmatter + 人工策展的中文元数据合并）；
2. 供 Agent 工具 load_research_skill 按需读取完整方法论（渐进式披露）；
3. 供 /api/skills 提供技能中心列表（前端展示）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

LIBRARY_DIR = Path(__file__).parent / "library"

# 单个技能正文读取上限（字符），超出截断——防极端长文撑爆上下文
MAX_BODY_CHARS = 120_000

# 六大功能分类（按科研生命周期排序，前端入口与 API 均按此顺序展示）
CATEGORY_META = {
    "文献情报":   {"icon": "🔍", "desc": "找文献 · 读文献 · 管引文"},
    "研究设计":   {"icon": "🧪", "desc": "假设 · 实验与统计设计"},
    "论文写作":   {"icon": "✍️", "desc": "从大纲到投稿格式"},
    "审稿与发表": {"icon": "⚖️", "desc": "评审意见与修回复原"},
    "图表汇报":   {"icon": "📊", "desc": "绘图 · 海报 · 幻灯"},
    "全流程与转化": {"icon": "🚀", "desc": "端到端流水线 · 专利"},
}
CATEGORY_ORDER = list(CATEGORY_META.keys())

# 人工策展的中文元数据：分类 / 中文名 / 一句话 / 触发词 / 示例指令。
# frontmatter 的 name/description 与此合并展示；新增技能只需放入 library/
# 并在此补一行（缺省也能列出，仅少中文说明）。
CURATED: Dict[str, dict] = {
    # ---------- 文献情报 ----------
    "nature-academic-search": {
        "zh": "多源学术检索", "category": "文献情报",
        "summary": "多源文献检索、引文核验与检索式构建的严格流程",
        "triggers": "文献检索 找论文 检索式 引文核验 系统综述",
        "example": "用多源检索流程给我做「钙钛矿太阳能电池稳定性」的系统文献调研",
    },
    "nature-paper-card": {
        "zh": "论文精读卡片", "category": "文献情报",
        "summary": "把一篇论文做成 16 节证据锚定的深度精读卡（定位/方法/证据边界/可测试 idea）",
        "triggers": "精读 文献卡片 paper card 深度解读 拆论文",
        "example": "把这篇 DOI:10.1038/s41586-024-00000-x 做成精读卡片",
    },
    "nature-reader": {
        "zh": "全文对照精读", "category": "文献情报",
        "summary": "论文全文中英对照精读，图/表/公式感知，逐节翻译与讲解",
        "triggers": "翻译全文 对照阅读 全文精读 逐节翻译 读论文",
        "example": "帮我把 arXiv:2401.00001 全文中英对照精读",
    },
    "nature-literature-pipeline": {
        "zh": "文献日推流水线", "category": "文献情报",
        "summary": "检索→六维评分→精读→成稿交付的自动化文献监控流水线",
        "triggers": "文献推送 日推 跟踪文献 每天文献 监控",
        "example": "帮我搭一个「LLM for Science」方向的每日文献推送方案",
    },
    "nature-downloader": {
        "zh": "全文合法下载", "category": "文献情报",
        "summary": "OA/出版商/CNKI/机构通路的合法全文获取路径",
        "triggers": "下载全文 全文 PDF 获取原文 文献下载",
        "example": "帮我找这篇论文的合法全文下载途径",
    },
    "nature-ref-verifier": {
        "zh": "参考文献核验", "category": "文献情报",
        "summary": "参考文献逐条多源交叉验证，标记卷年冲突/作者异常/页码偏差",
        "triggers": "核验参考文献 查引文 文献校对 references 核对",
        "example": "逐条核验我论文参考文献列表的真实性",
    },
    "nature-citation": {
        "zh": "CNS 级引文", "category": "文献情报",
        "summary": "只引 Nature/Science/Cell 系旗舰刊的严格引文添加流程",
        "triggers": "加引文 CNS 引用 nature 引文 高端引文",
        "example": "给这段论述加上 Nature 子刊级别的引文支撑",
    },
    # ---------- 论文写作 ----------
    "nature-writing": {
        "zh": "论文写作", "category": "论文写作",
        "summary": "Nature 级论文写作：结构/摘要/引言/方法/结果/讨论全流程",
        "triggers": "写论文 论文写作 摘要 introduction 方法部分 投稿",
        "example": "帮我把实验结果写成 Nature 风格的 Results 部分",
    },
    "nature-polishing": {
        "zh": "学术润色", "category": "论文写作",
        "summary": "去 AI 腔的学术语言润色，保持主张强度与准确度",
        "triggers": "润色 polish 改语言 去 AI 味 降重 表达",
        "example": "润色这段摘要，去掉 AI 腔，别弱化主张",
    },
    "nature-proposal-writer": {
        "zh": "开题与提案", "category": "论文写作",
        "summary": "开题报告/研究计划/基金申请书的提案优先写作流水线",
        "triggers": "开题 研究计划 proposal 申请书 基金 标书",
        "example": "帮我写「可解释 AI 医学影像」的开题报告初稿",
    },
    "nature-response": {
        "zh": "审稿回复", "category": "审稿与发表",
        "summary": "逐条审稿意见回复信、Rebuttal 策略与修订稿红标",
        "triggers": "审稿意见 回复信 rebuttal 修回 response letter",
        "example": "帮我起草这三条审稿意见的点对点回复",
    },
    "nature-reviewer": {
        "zh": "模拟审稿", "category": "审稿与发表",
        "summary": "以审稿人视角出结构化评审意见（新颖性/严谨性/过度声明）",
        "triggers": "审我的论文 模拟审稿 review 评审意见 投稿前",
        "example": "投稿前帮我模拟两位审稿人评这篇论文",
    },
    "nature-statistics": {
        "zh": "统计审计", "category": "论文写作",
        "summary": "统计方法审计：样本量/重复/检验/P 值报告规范",
        "triggers": "统计方法 样本量 显著性 P值 统计审查",
        "example": "审计我实验部分的统计报告是否达到期刊标准",
    },
    "nature-data": {
        "zh": "数据可用性", "category": "论文写作",
        "summary": "Data Availability 声明、FAIR 数据计划与仓库选择",
        "triggers": "数据可用性 data availability FAIR 数据共享 仓库",
        "example": "帮我写论文的 Data Availability 声明",
    },
    "latex-paper-en": {
        "zh": "LaTeX 英文论文", "category": "论文写作",
        "summary": "英文 LaTeX 期刊/会议论文：编译修复/模板/引用检查/去 AI 润色",
        "triggers": "latex tex 模板 icml neurips 编译报错 bibliography",
        "example": "我的 LaTeX 编译报错了，帮我修复并检查引用格式",
    },
    # ---------- 图表汇报 ----------
    "nature-figure": {
        "zh": "投稿级科研绘图", "category": "图表汇报",
        "summary": "matplotlib/seaborn/ggplot 投稿级图形：多面板/配色/期刊规范",
        "triggers": "画图 科研绘图 figure 配色 多面板 图形规范",
        "example": "用 matplotlib 把我的消融实验画成投稿级多面板图",
    },
    "happy-figure-skill": {
        "zh": "AI 绘图提示词", "category": "图表汇报",
        "summary": "生成可复制的科研 AI 绘图提示词（机制图/技术路线图/图形摘要）",
        "triggers": "机制图 路线图 graphical abstract 绘图提示词 示意图",
        "example": "给我的方法部分生成一张技术路线图的 AI 绘图提示词",
    },
    "nature-paper2ppt": {
        "zh": "论文转 PPT", "category": "图表汇报",
        "summary": "论文转 Nature 风格中英答辩/组会 PPT（含讲稿）",
        "triggers": "答辩ppt 组会汇报 论文转ppt 讲稿 presentation",
        "example": "把这篇论文做成 15 页的组会汇报 PPT",
    },
    "nature-image2ppt": {
        "zh": "图片转 PPT", "category": "图表汇报",
        "summary": "幻灯片截图/扫描 PDF/图片 PPT 高保真还原为可编辑 PPTX",
        "triggers": "图片转ppt 还原幻灯片 扫描件 pdf转ppt 可编辑",
        "example": "把这份扫描版课件还原成可编辑的 PPT",
    },
    # ---------- 实验与转化 ----------
    "nature-experiment-log": {
        "zh": "实验日志", "category": "研究设计",
        "summary": "图/音/文输入的标准化实验记录（YAML frontmatter 归档）",
        "triggers": "实验记录 实验日志 记录数据 归档 logbook",
        "example": "帮我把今天这组实验结果整理成标准实验日志",
    },
    "nature-paper-to-patent": {
        "zh": "论文转专利", "category": "全流程与转化",
        "summary": "论文/技术报告→证据锚定的中文发明专利草稿与交底书",
        "triggers": "专利 交底书 发明 patent 成果转化",
        "example": "把这篇方法论文转写成发明专利交底书",
    },
    "evo-automl": {
        "zh": "进化式 AutoML", "category": "研究设计",
        "summary": "文献证据驱动的进化式深度学习自动优化（μEvoNAS 方法论）",
        "triggers": "自动优化 nas 进化搜索 automl 仿生算法",
        "example": "用进化搜索自动优化我的网络结构与超参",
    },
    # ---------- 全流程 ----------
    "research-core": {
        "zh": "科研全流程", "category": "全流程与转化",
        "summary": "从 idea 到论文的统一入口：方法建模/实验设计/复现/写作/审稿",
        "triggers": "全流程 从idea到论文 复现baseline 消融 论文大纲",
        "example": "我要从零开始把一个 idea 推到论文投稿，帮我全流程规划",
    },
    "research-auto": {
        "zh": "科研自动化流水线", "category": "全流程与转化",
        "summary": "SOTA 学习→baseline 复现→创新点→实验→写作的双脑流水线",
        "triggers": "自动化流水线 科研流水线 端到端 sota 学习",
        "example": "启动科研自动化流水线，从 SOTA 学习开始推进我的课题",
    },
    "nature-shared": {
        "zh": "Nature 公共规范", "category": "全流程与转化",
        "summary": "nature 系列技能共用的写作与证据约束（自动随技能加载）",
        "triggers": "",
        "example": "",
    },
    # ---------- 第二批：封装自 K-Dense-AI/scientific-agent-skills（MIT） ----------
    "literature-review": {
        "zh": "系统文献综述", "category": "文献情报",
        "summary": "多数据库系统综述与 Meta 分析全流程（检索→筛选→综合）",
        "triggers": "系统综述 meta分析 meta-analysis 综述写作 叙述综述",
        "example": "帮我做「肠道菌群与认知障碍」的系统文献综述",
    },
    "citation-management": {
        "zh": "引文管理", "category": "文献情报",
        "summary": "元数据抓取核验 + 规范 BibTeX 生成与参考文献库管理",
        "triggers": "bibtex 引文管理 文献管理 参考文献 整理引文",
        "example": "帮我把这 10 篇论文整理成规范 BibTeX 并核验元数据",
    },
    "hypothesis-generation": {
        "zh": "假设生成", "category": "研究设计",
        "summary": "证据边界的科学问题、候选假设、判别性预测与预注册分析计划",
        "triggers": "研究假设 科学问题 研究猜想 预注册 判别性预测",
        "example": "基于我的初步观察，帮我生成可检验的研究假设与分析计划",
    },
    "experimental-design": {
        "zh": "实验设计", "category": "研究设计",
        "summary": "随机化、区组、对照与处理组合的设计，保证结果可解释",
        "triggers": "实验设计 随机化 对照试验 组间设计 因子设计",
        "example": "帮我设计带随机化和对照的消融实验方案",
    },
    "statistical-power": {
        "zh": "统计功效分析", "category": "研究设计",
        "summary": "样本量估算、先验功效分析、最小可检测效应与功效曲线",
        "triggers": "样本量 功效分析 power curve 最小可检测效应 需要多少样本",
        "example": "我的对照实验需要多少样本量？请做先验功效分析",
    },
    "latex-posters": {
        "zh": "学术海报", "category": "图表汇报",
        "summary": "beamerposter/tikzposter/baposter 投稿级学术会议海报",
        "triggers": "学术海报 poster 会议展板 A0海报 展报",
        "example": "帮我把这篇论文做成学术会议 A0 海报",
    },
    "infographics": {
        "zh": "图形摘要", "category": "图表汇报",
        "summary": "图形摘要（Graphical Abstract）与信息图的版式设计方法论",
        "triggers": "图形摘要 graphical abstract 信息图 infographics",
        "example": "为我的论文设计一张期刊投稿用的图形摘要",
    },
    "scientific-schematics": {
        "zh": "科研示意图", "category": "图表汇报",
        "summary": "模型架构图、流程示意图的规范化绘制方法与质量自检",
        "triggers": "架构图 示意图 结构图 流程图 模型图",
        "example": "给我的模型画一张论文用的架构示意图",
    },
}


@dataclass(frozen=True)
class SkillInfo:
    """单个技能的展示与路由元数据。"""

    id: str
    name: str            # frontmatter 英文名
    zh: str              # 中文名
    category: str        # 分类（文献情报/论文写作/图表汇报/实验与转化/全流程）
    summary: str         # 中文一句话
    description: str     # frontmatter 原始英文描述（供主 Agent 精确判断适用性）
    triggers: str        # 中文触发词（空格分隔）
    example: str         # 示例指令
    path: Path           # SKILL.md 路径

    def to_api_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "zh": self.zh,
            "category": self.category,
            "summary": self.summary,
            "description": self.description,
            "triggers": self.triggers,
            "example": self.example,
        }


def _parse_frontmatter(text: str) -> tuple[Optional[dict], str]:
    """解析 SKILL.md 的 YAML frontmatter，返回 (元数据, 正文)。"""
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None, text
    if not isinstance(meta, dict):
        meta = None
    return meta, parts[2].lstrip("\n")


@lru_cache(maxsize=1)
def list_skills() -> List[SkillInfo]:
    """扫描 library/ 返回全部技能（含 frontmatter 与策展元数据合并）。"""
    skills: List[SkillInfo] = []
    if not LIBRARY_DIR.exists():
        logger.warning("技能库目录不存在: %s", LIBRARY_DIR)
        return skills
    for skill_dir in sorted(LIBRARY_DIR.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_dir.is_dir() or not skill_md.exists():
            continue
        meta, _ = _parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        curated = CURATED.get(skill_dir.name, {})
        skills.append(
            SkillInfo(
                id=skill_dir.name,
                name=(meta or {}).get("name", skill_dir.name),
                zh=curated.get("zh", skill_dir.name),
                category=curated.get("category", "其他"),
                summary=curated.get("summary", ""),
                description=(meta or {}).get("description", ""),
                triggers=curated.get("triggers", ""),
                example=curated.get("example", ""),
                path=skill_md,
            )
        )
    # 按六大分类的生命周期顺序稳定排序
    skills.sort(
        key=lambda s: (
            CATEGORY_ORDER.index(s.category) if s.category in CATEGORY_META else 99,
            s.id,
        )
    )
    return skills


def list_categories() -> List[dict]:
    """返回有序分类元数据（含技能数），供前端入口与 API 使用。"""
    counts: Dict[str, int] = {}
    for s in list_skills():
        counts[s.category] = counts.get(s.category, 0) + 1
    cats = [
        {
            "name": name,
            "icon": meta["icon"],
            "desc": meta["desc"],
            "count": counts.get(name, 0),
        }
        for name, meta in CATEGORY_META.items()
    ]
    for name, cnt in counts.items():  # 未知分类兜底
        if name not in CATEGORY_META:
            cats.append({"name": name, "icon": "📦", "desc": "", "count": cnt})
    return cats


def get_skill(skill_id: str) -> Optional[SkillInfo]:
    sid = (skill_id or "").strip().strip("/").lower()
    for s in list_skills():
        if s.id == sid:
            return s
    return None


def read_skill_body(skill_id: str) -> str:
    """读取技能完整方法论（frontmatter 剥离 + 依赖技能附加 + 文件清单）。

    技能间依赖（如 nature-* 引用 nature-shared）会自动附加被依赖技能正文，
    保证模型拿到的方法论自洽。
    """
    skill = get_skill(skill_id)
    if skill is None:
        available = ", ".join(s.id for s in list_skills())
        return (
            f"未找到技能「{skill_id}」。可用技能：{available}。"
            "请从中选择后重新调用。"
        )
    _, body = _parse_frontmatter(skill.path.read_text(encoding="utf-8"))

    # 依赖技能自动附加（最多附加 1 个，防级联膨胀）
    if "nature-shared" in body and skill.id != "nature-shared":
        shared = get_skill("nature-shared")
        if shared is not None:
            _, shared_body = _parse_frontmatter(
                shared.path.read_text(encoding="utf-8")
            )
            body += "\n\n---\n\n## 附：nature-shared 公共规范\n\n" + shared_body

    # 随技能列出可用脚本/参考文件（相对路径，用户本地可运行）
    extras = sorted(
        str(p.relative_to(skill.path.parent))
        for p in skill.path.parent.rglob("*")
        if p.is_file() and p.name != "SKILL.md"
    )
    if extras:
        listed = "\n".join(f"- {e}" for e in extras[:40])
        more = f"\n- …（共 {len(extras)} 个文件）" if len(extras) > 40 else ""
        body += (
            "\n\n---\n\n## 本技能附带文件（相对技能目录）\n\n"
            f"{listed}{more}\n\n"
            "注意：脚本需用户本地 Python 环境运行；网页端你应给出完整可运行的"
            "代码块或按方法论直接产出文字结果，不要声称已替用户执行脚本。"
        )

    if len(body) > MAX_BODY_CHARS:
        body = (
            body[:MAX_BODY_CHARS]
            + "\n\n[技能全文过长已截断；请优先遵循上文核心流程与输出契约]"
        )
    return body
