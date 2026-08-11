/**
 * 统一 HTTP 辅助：鉴权 Token 注入
 *
 * 存储 key 历史遗留 erp_openclaw_*（采购项目残留），已迁移为 yzzt_*（研途智探）。
 * 首次读取时若新 key 不存在但旧 key 存在，自动迁移，避免用户被登出。
 */

const TOKEN_KEY = 'yzzt_token'
const USER_KEY = 'yzzt_user'
const LEGACY_TOKEN_KEY = 'erp_openclaw_token'
const LEGACY_USER_KEY = 'erp_openclaw_user'

/** 一次性迁移历史遗留 key → 新 key */
function _migrateLegacyKeys() {
  try {
    const legacyToken = localStorage.getItem(LEGACY_TOKEN_KEY)
    if (legacyToken && !localStorage.getItem(TOKEN_KEY)) {
      localStorage.setItem(TOKEN_KEY, legacyToken)
      localStorage.setItem(USER_KEY, localStorage.getItem(LEGACY_USER_KEY) || '{}')
      localStorage.removeItem(LEGACY_TOKEN_KEY)
      localStorage.removeItem(LEGACY_USER_KEY)
    }
  } catch {
    /* localStorage 不可用时静默忽略 */
  }
}

_migrateLegacyKeys()

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user || {}))
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

export function authHeaders(extra = {}) {
  const headers = { ...extra }
  const token = getToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  return headers
}

/**
 * 统一 fetch 封装：自动注入鉴权头 + 401 全局登出。
 *
 * 返回的 Response body 中若包含 {code, message, detail} 结构化错误契约，
 * 调用方可通过 response.json() 解析 code 做业务化文案路由。
 */
export async function apiFetch(url, options = {}) {
  const opts = { ...options }
  opts.headers = authHeaders({
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  })
  const response = await fetch(url, opts)
  if (response.status === 401) {
    clearAuth()
    window.dispatchEvent(new CustomEvent('auth:required'))
  }
  return response
}
