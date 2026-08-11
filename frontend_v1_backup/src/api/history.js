/**
 * 历史记录 API 模块
 *
 * 提供会话列表查询、会话消息获取和会话删除接口
 */

import { apiFetch } from './http.js'

const API_BASE = '/api/history'

/**
 * 获取会话列表
 */
export async function getSessions(page = 1, limit = 20, workspace = null) {
  const params = new URLSearchParams({ page, limit })
  if (workspace) params.set('workspace', workspace)
  const response = await apiFetch(`${API_BASE}?${params}`)

  if (!response.ok) {
    throw new Error('获取会话列表失败')
  }

  return response.json()
}

/**
 * 获取会话消息历史
 */
export async function getMessages(threadId) {
  const response = await apiFetch(`${API_BASE}/${threadId}/messages`)

  if (!response.ok) {
    throw new Error('获取会话消息失败')
  }

  return response.json()
}

/**
 * 删除会话
 */
export async function deleteSession(threadId) {
  const response = await apiFetch(`${API_BASE}/${threadId}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new Error('删除会话失败')
  }

  return response.json()
}

/**
 * 更新会话标题
 */
export async function updateSessionTitle(threadId, title) {
  const response = await apiFetch(`${API_BASE}/${threadId}/title`, {
    method: 'PUT',
    body: JSON.stringify({ title }),
  })

  if (!response.ok) {
    throw new Error('更新会话标题失败')
  }

  return response.json()
}
