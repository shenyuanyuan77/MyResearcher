/**
 * 主题管理：light / dark / auto（跟随系统），持久化到 localStorage。
 * <html data-theme="light|dark"> 由 design-tokens.css 消费；
 * index.html 内联脚本在首帧前做同样解析，避免深色用户闪白。
 */

const KEY = 'yantu-theme'

export function getStoredTheme() {
  try { return localStorage.getItem(KEY) || 'auto' } catch { return 'auto' }
}

export function resolvedTheme(stored = getStoredTheme()) {
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyTheme(stored = getStoredTheme()) {
  document.documentElement.setAttribute('data-theme', resolvedTheme(stored))
}

export function setTheme(stored) {
  try { localStorage.setItem(KEY, stored) } catch { /* ignore */ }
  applyTheme(stored)
}

/** 循环切换：auto → light → dark → auto，返回新值供 UI 提示。 */
export function cycleTheme() {
  const order = ['auto', 'light', 'dark']
  const next = order[(order.indexOf(getStoredTheme()) + 1) % order.length]
  setTheme(next)
  return next
}

// 跟随系统时，系统切换主题实时生效
if (window.matchMedia) {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', () => {
    if (getStoredTheme() === 'auto') applyTheme('auto')
  })
}
