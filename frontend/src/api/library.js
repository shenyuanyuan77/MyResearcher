/**
 * 个人文献库 API client。
 * 跨会话知识沉淀：收藏/标记已读/加笔记。
 */
import { apiFetch, authHeaders, extractApiError } from './http.js'

const BASE = '/api/library'

/**
 * 列出当前用户的文献库。
 * @param {string|null} status - 可选状态筛选：unread/reading/read
 * @param {string|null} tag - 可选标签筛选
 */
export async function listLibrary(status = null, tag = null) {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (tag) params.set('tag', tag)
  const q = params.toString() ? `?${params}` : ''
  const resp = await apiFetch(`${BASE}${q}`)
  if (!resp.ok) throw new Error(extractApiError(await resp.json().catch(() => ({})), '获取文献库失败'))
  return resp.json()
}

/**
 * 收藏一篇论文。
 * @param {Object} paper - 论文对象（含 doi/title/authors/...）
 * @param {string[]} tags - 可选标签
 */
export async function savePaper(paper, tags = []) {
  const resp = await apiFetch(`${BASE}`, {
    method: 'POST',
    body: JSON.stringify({
      doi: paper.doi,
      title: paper.title || '',
      authors: paper.authors || [],
      year: paper.year,
      venue: paper.venue || '',
      cited_by_count: paper.cited_by_count,
      doi_url: paper.doi_url || '',
      abstract: paper.abstract || '',
      pub_type: paper.pub_type || '',
      tags,
    }),
  })
  if (!resp.ok) throw new Error(extractApiError(await resp.json().catch(() => ({})), '收藏失败'))
  return resp.json()
}

/**
 * 更新阅读状态/标签/笔记。
 */
export async function updatePaper(doi, { status, tags, notes } = {}) {
  const body = {}
  if (status) body.status = status
  if (tags) body.tags = tags
  if (notes !== undefined) body.notes = notes
  const resp = await apiFetch(`${BASE}/${encodeURIComponent(doi)}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
  if (!resp.ok) throw new Error(extractApiError(await resp.json().catch(() => ({})), '更新失败'))
  return resp.json()
}

/**
 * 取消收藏。
 */
export async function deletePaper(doi) {
  const resp = await apiFetch(`${BASE}/${encodeURIComponent(doi)}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(extractApiError(await resp.json().catch(() => ({})), '取消收藏失败'))
  return resp.json()
}

/**
 * 检查某 DOI 是否已收藏（前端展示用，调 listLibrary 后本地判断）。
 */
export async function isSaved(doi) {
  const data = await listLibrary()
  return (data.papers || []).some(p => p.doi === doi || p.doi_url === doi)
}
