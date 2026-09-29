/**
 * 科研技能中心 API
 * 从后端 /api/skills 拉取技能目录（六大分类 + 技能明细）；失败时回退到内置精简目录。
 */

import { apiFetch } from './http.js'

// 六大分类元数据（与 src/agent/skills/registry.py CATEGORY_META 对齐）
export const CATEGORY_META = {
  文献情报: { icon: '🔍', desc: '找文献 · 读文献 · 管引文' },
  研究设计: { icon: '🧪', desc: '假设 · 实验与统计设计' },
  论文写作: { icon: '✍️', desc: '从大纲到投稿格式' },
  审稿与发表: { icon: '⚖️', desc: '评审意见与修回复原' },
  图表汇报: { icon: '📊', desc: '绘图 · 海报 · 幻灯' },
  全流程与转化: { icon: '🚀', desc: '端到端流水线 · 专利' },
}

// 内置兜底目录（后端不可达时的精简版；与 registry.py 对齐的示例）
export const FALLBACK_SKILLS = [
  { id: 'nature-academic-search', zh: '多源学术检索', category: '文献情报', summary: '多源检索与引文核验', example: '用多源检索流程帮我做系统文献调研，方向是：' },
  { id: 'literature-review', zh: '系统文献综述', category: '文献情报', summary: '系统综述与 Meta 分析全流程', example: '帮我做系统文献综述，主题是：' },
  { id: 'nature-paper-card', zh: '论文精读卡片', category: '文献情报', summary: '16 节证据锚定的深度精读卡', example: '把这篇论文（标题或 DOI）做成精读卡片：' },
  { id: 'nature-reader', zh: '全文对照精读', category: '文献情报', summary: '全文中英对照逐节精读', example: '帮我把这篇论文全文中英对照精读：' },
  { id: 'citation-management', zh: '引文管理', category: '文献情报', summary: 'BibTeX 生成与元数据核验', example: '帮我把这批论文整理成规范 BibTeX：' },
  { id: 'hypothesis-generation', zh: '假设生成', category: '研究设计', summary: '可检验的研究假设与分析计划', example: '基于初步观察帮我生成研究假设：' },
  { id: 'experimental-design', zh: '实验设计', category: '研究设计', summary: '随机化/对照/区组设计', example: '帮我设计带随机化和对照的实验方案：' },
  { id: 'statistical-power', zh: '统计功效分析', category: '研究设计', summary: '样本量估算与先验功效分析', example: '我的实验需要多少样本量？请做功效分析：' },
  { id: 'nature-writing', zh: '论文写作', category: '论文写作', summary: 'Nature 级论文写作全流程', example: '帮我把实验结果写成论文的 Results 部分：' },
  { id: 'nature-proposal-writer', zh: '开题与提案', category: '论文写作', summary: '开题报告/申请书撰写', example: '帮我写开题报告初稿，方向是：' },
  { id: 'nature-reviewer', zh: '模拟审稿', category: '审稿与发表', summary: '审稿人视角结构化评审', example: '投稿前帮我模拟审稿人评这篇论文：' },
  { id: 'nature-response', zh: '审稿回复', category: '审稿与发表', summary: '审稿意见逐条回复', example: '帮我起草审稿意见的点对点回复：' },
  { id: 'nature-figure', zh: '投稿级科研绘图', category: '图表汇报', summary: '投稿级 matplotlib/ggplot 图形', example: '把我的实验数据画成投稿级多面板图：' },
  { id: 'latex-posters', zh: '学术海报', category: '图表汇报', summary: 'LaTeX 学术会议海报', example: '帮我把这篇论文做成学术会议海报：' },
  { id: 'infographics', zh: '图形摘要', category: '图表汇报', summary: 'Graphical Abstract 版式设计', example: '为我的论文设计一张图形摘要：' },
  { id: 'research-core', zh: '科研全流程', category: '全流程与转化', summary: '从 idea 到论文的统一入口', example: '我要把一个 idea 推到论文投稿，帮我全流程规划：' },
]

export async function listSkills() {
  try {
    const resp = await apiFetch('/api/skills')
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    if (!data.ok || !Array.isArray(data.skills) || data.skills.length === 0) {
      throw new Error('empty')
    }
    const categories = Array.isArray(data.categories) && data.categories.length
      ? data.categories
      : Object.keys(CATEGORY_META).map((name) => ({
          name, icon: CATEGORY_META[name].icon, desc: CATEGORY_META[name].desc,
          count: data.skills.filter((s) => s.category === name).length,
        }))
    return { skills: data.skills, categories }
  } catch {
    const categories = Object.keys(CATEGORY_META).map((name) => ({
      name, icon: CATEGORY_META[name].icon, desc: CATEGORY_META[name].desc,
      count: FALLBACK_SKILLS.filter((s) => s.category === name).length,
    }))
    return { skills: FALLBACK_SKILLS, categories }
  }
}
