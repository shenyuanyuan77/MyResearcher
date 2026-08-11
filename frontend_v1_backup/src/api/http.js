/**
 * 统一 HTTP 辅助：鉴权 Token 注入
 */

const TOKEN_KEY = 'erp_openclaw_token'
const USER_KEY = 'erp_openclaw_user'

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
