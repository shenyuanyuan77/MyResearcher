/**
 * 图片 CDN 域名白名单（前后端共享事实源）
 * 任何"识别裸 URL / 自动内联图片"逻辑都应引用本文件，避免散落硬编码。
 */

export const IMAGE_HOSTS = Object.freeze([
  'mdn.alipayobjects.com',
  'img.alicdn.com',
  'gw.alipayobjects.com',
  'zos.alipayobjects.com',
])

/** 判断 URL 主机是否命中白名单。失败时返回 false（不抛错）。 */
export function isKnownImageHost(url) {
  if (!url) return false
  try {
    const hostname = new URL(url, 'https://_').hostname
    if (!hostname || hostname === '_') return false
    return IMAGE_HOSTS.some((h) => hostname === h || hostname.endsWith(`.${h}`))
  } catch {
    return false
  }
}

/** 匹配正文里的裸图片 URL（仅命中白名单）。 */
export function findKnownImageUrls(text) {
  if (!text) return []
  const out = []
  for (const host of IMAGE_HOSTS) {
    const re = new RegExp(`https?://[^\\s'"<>]*${host.replace(/\./g, '\\.')}[^\\s'"<>]*`, 'gi')
    const matches = text.match(re) || []
    for (const m of matches) out.push(m)
  }
  return Array.from(new Set(out))
}
