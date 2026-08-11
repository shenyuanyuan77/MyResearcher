/**
 * Markdown 渲染辅助（通用、领域无关）。
 *
 * 历史版本是采购/ERP 报告专用的 1000+ 行正则重整套（markdownTables.js /
 * rebuildPipeTables.js / reportLayout.js / dashboardLayout.js / monthlyTrendChart.js /
 * imageHosts.js），已被移除。本文件提供 MarkdownRenderer 仍需要的通用能力：
 *  - 图片托管 host 识别（学术/通用图床）
 *  - normalizeMarkdown / reportTablesHealthy：passthrough（后端已做通用 normalize）
 *  - injectMonthlyTrendLineChart：passthrough（学术场景无月度采购趋势图）
 */

// 学术/通用图片托管 host（与后端 chat._IMAGE_CDN_HOSTS 对齐）
const IMAGE_HOSTS = [
  'img.shields.io',
  'raw.githubusercontent.com',
  'user-images.githubusercontent.com',
  'objects.githubusercontent.com',
  'avatars.githubusercontent.com',
  'upload.wikimedia.org',
  'ars.els-cdn.com',
  'media.springernature.com',
  'ieeexplore.ieee.org',
  'cdn.pixabay.com',
  'images.unsplash.com',
]

const IMAGE_EXT_RE = /\.(png|jpe?g|gif|webp|svg|bmp|avif)(\?.*)?$/i
const BARE_URL_RE = /(?:^|[\s"'(])(https?:\/\/[^\s"'<>)]+)(?=$|[\s"')])/gm

export function isKnownImageHost(src) {
  if (!src) return false
  return IMAGE_HOSTS.some((h) => String(src).includes(h))
}

export function findKnownImageUrls(text) {
  if (!text) return []
  const urls = []
  for (const m of String(text).matchAll(BARE_URL_RE)) {
    const url = m[1].replace(/[.,;，。；]+$/, '')
    if (isKnownImageHost(url) || IMAGE_EXT_RE.test(url)) {
      if (!urls.includes(url)) urls.push(url)
    }
  }
  return urls
}

/**
 * Markdown normalize（通用）。
 * 后端 normalize_assistant_markdown 已做通用结构修复，
 * 前端此处仅做保守 passthrough，避免引入采购专用正则误伤学术内容。
 */
export function normalizeMarkdown(text) {
  return text || ''
}

/**
 * 报告表格健康检查（通用）。
 * 后端 render_gfm_table 已保证表格结构正确，前端保守返回 true 跳过重整。
 */
export function reportTablesHealthy() {
  return true
}

/**
 * 月度趋势折线图注入（passthrough）。
 * 学术场景无「月度采购趋势」表，原采购专用 SVG 注入已移除。
 */
export function injectMonthlyTrendLineChart(html) {
  return html || ''
}
