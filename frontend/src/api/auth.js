import { apiFetch, setAuth, clearAuth, getStoredUser, getToken } from './http.js'

export async function login(username, password) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 15000)
  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
      signal: controller.signal,
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      // 解析结构化错误契约 {code, message, detail} 或 FastAPI 默认 {detail: "..."/{msg}}
      const detail = err.detail
      const message =
        typeof detail === 'string' ? detail :
        (detail && typeof detail === 'object' ? (detail.message || detail.msg) : null) ||
        '登录失败'
      throw new Error(message)
    }
    const data = await response.json()
    setAuth(data.access_token, data.user)
    return data
  } catch (e) {
    if (e.name === 'AbortError') {
      throw new Error('服务暂不可用，请确认科研助手服务已启动后重试')
    }
    throw e
  } finally {
    clearTimeout(timer)
  }
}

export async function fetchMe() {
  const response = await apiFetch('/api/auth/me')
  if (!response.ok) {
    throw new Error('未登录')
  }
  return response.json()
}

export function logout() {
  clearAuth()
}

export function isLoggedIn() {
  return !!getToken()
}

export { getStoredUser }
