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
      const detail = err.detail
      throw new Error(
        typeof detail === 'string' ? detail : (detail?.msg || '登录失败')
      )
    }
    const data = await response.json()
    setAuth(data.access_token, data.user)
    return data
  } catch (e) {
    if (e.name === 'AbortError') {
      throw new Error('登录超时：后端未响应，请确认 API 已启动（8091）')
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
