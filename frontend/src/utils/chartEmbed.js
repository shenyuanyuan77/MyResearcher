/**
 * 通用：把本轮可视化工具产出的图补进助手正文（与业务场景无关）。
 * 与 Python api_view/chart_embed.py 对齐。
 */

import { IMAGE_HOSTS } from './imageHosts.js'

const VIZ_TOOL_RE = /visualiz|generate_.*chart|chart_generator|_chart$|^generate_visualization$/i

export function isVisualizationTool(name) {
  return VIZ_TOOL_RE.test(String(name || ''))
}

export function extractImageUrlsFromText(text) {
  const s = String(text || '')
  const out = []
  const add = (u) => {
    const url = String(u || '')
      .trim()
      .replace(/[.,;，。；]+$/, '')
    if (url && !out.includes(url)) out.push(url)
  }
  for (const m of s.matchAll(/!\[[^\]]*\]\(([^)]+)\)/g)) add(m[1])
  for (const m of s.matchAll(/data:image\/[^;]+;base64,[A-Za-z0-9+/=]+/g)) add(m[0])
  for (const m of s.matchAll(/(?:^|[\s"'(])(https?:\/\/[^\s"'<>)]+)(?=$|[\s"')])/gm)) {
    const url = m[1]
    if (IMAGE_HOSTS.some((h) => url.includes(h)) || /\.(png|jpe?g|gif|webp|svg)(\?|$)/i.test(url)) {
      add(url)
    }
  }
  return out
}

export function collectToolChartImages(messages) {
  const urls = []
  const seen = new Set()
  const push = (u) => {
    if (u && !seen.has(u)) {
      seen.add(u)
      urls.push(u)
    }
  }
  for (const m of messages || []) {
    if (m.role !== 'tool') continue
    const viz = isVisualizationTool(m.tool_name || m.name)
    for (const img of m.images || []) {
      if (typeof img === 'string' && (viz || IMAGE_HOSTS.some((h) => img.includes(h)))) push(img)
    }
    if (viz) {
      for (const u of extractImageUrlsFromText(m.text || m.content || '')) push(u)
    }
  }
  return urls
}

export function embedOrphanChartImages(text, imageUrls, sectionTitle = '本轮分析图表') {
  let body = String(text || '')
  const orphans = (imageUrls || []).filter((u) => u && !body.includes(u) && !body.includes(String(u).split('?')[0]))
  if (!orphans.length) return body
  const lines = [body.replace(/\s+$/, ''), '']
  if (!body.includes(`### ${sectionTitle}`) && !body.includes(`## ${sectionTitle}`)) {
    lines.push(`### ${sectionTitle}`, '')
  }
  orphans.forEach((url, i) => {
    lines.push(url.startsWith('![') ? url : `![图表${i + 1}](${url})`, '')
  })
  return lines.join('\n').replace(/\s+$/, '') + '\n'
}

/** 同一图片 URL 在正文中只保留首次（与后端 dedupe_markdown_images 对齐） */
export function dedupeMarkdownImages(text) {
  const src = String(text || '')
  if (!src.includes('![')) return src
  const seen = new Set()
  const imgLine = /^\s*(!\[[^\]]*\]\([^)]+\))\s*$/
  const imgInline = /!\[[^\]]*\]\(([^)]+)\)/g
  const lines = src.split(/(\n)/)
  const out = []
  for (const line of lines) {
    if (line === '\n') {
      out.push(line)
      continue
    }
    if (imgLine.test(line)) {
      const m = /!\[[^\]]*\]\(([^)]+)\)/.exec(line)
      const url = (m && m[1] ? m[1] : '').trim()
      const key = url.split('?')[0]
      if (key && seen.has(key)) continue
      if (key) seen.add(key)
      out.push(line)
      continue
    }
    out.push(
      line.replace(imgInline, (full, url) => {
        const key = String(url || '')
          .trim()
          .split('?')[0]
        if (key && seen.has(key)) return ''
        if (key) seen.add(key)
        return full
      })
    )
  }
  return out.join('').replace(/\n{3,}/g, '\n\n')
}

/** 流结束后：把孤儿工具图补进最合适的助手气泡 */
export function attachOrphanChartsToMessages(messages) {
  const list = messages || []
  for (const m of list) {
    if (m.role === 'assistant' && typeof m.content === 'string' && m.content.includes('![')) {
      m.content = dedupeMarkdownImages(m.content)
    }
  }
  const charts = collectToolChartImages(list)
  if (!charts.length) return
  const candidates = list.filter(
    (m) =>
      m.role === 'assistant' &&
      typeof m.content === 'string' &&
      (m.content.trim().length >= 80 || /^#{1,3}\s/m.test(m.content))
  )
  let target = null
  for (let i = candidates.length - 1; i >= 0; i--) {
    const c = candidates[i].content
    if (/^#{1,3}\s/m.test(c) || c.includes('|') || c.includes('![')) {
      target = candidates[i]
      break
    }
  }
  if (!target && candidates.length) target = candidates[candidates.length - 1]
  if (target) {
    target.content = dedupeMarkdownImages(embedOrphanChartImages(target.content, charts))
  }
}
