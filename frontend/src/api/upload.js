/**
 * 文件上传 API client。
 * PDF/Word 上传 → 结构化精读（创新点/方法/可引用句）。
 */
import { getToken, clearAuth, extractApiError } from './http.js'

/**
 * 上传文件并返回结构化精读。
 * @param {File} file - PDF/Word/TXT 文件
 * @returns {Promise<Object>} { ok, filename, file_type, full_text_chars, sections, quotable_sentences, ... }
 */
export async function uploadFile(file) {
  const fd = new FormData()
  fd.append('file', file)
  const token = getToken()
  const resp = await fetch('/api/upload', {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      // 注意：multipart 不要手动设 Content-Type，浏览器自动加 boundary
    },
    body: fd,
  })
  if (resp.status === 401) {
    // 与 http.js 契约一致：token 失效时清凭证并触发全局重登录
    clearAuth()
    window.dispatchEvent(new CustomEvent('auth:required'))
  }
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new Error(extractApiError(body, `上传失败 (${resp.status})`))
  }
  return resp.json()
}
