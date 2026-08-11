/**
 * 从「月度采购趋势」表解析数据并生成 SVG 折线图（无外部依赖）。
 * 仅当正文含服务端标记 `<!-- pcb-auto-line-chart -->` 时注入——禁止内容启发式。
 */

export const AUTO_LINE_CHART_MARKER = '<!-- pcb-auto-line-chart -->'

function parseAmount(cell) {
  const s = String(cell || '')
    .replace(/[¥,\s]/g, '')
    .replace(/[^\d.-]/g, '')
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}

/**
 * @param {string} markdown
 * @returns {{ labels: string[], values: number[] } | null}
 */
export function extractMonthlyTrendSeries(markdown) {
  const s = String(markdown || '')
  const m = s.match(
    /#{2,3}\s*[^\n]*月度采购趋势[^\n]*\n+([\s\S]*?)(?=\n#{1,3}\s|\n\*\*趋势小结|\n---\s*\n|$)/
  )
  if (!m) return null
  const block = m[1]
  const labels = []
  const values = []
  for (const line of block.split('\n')) {
    const t = line.trim()
    if (!t.startsWith('|') || /^\|?\s*[-:| \t]+\|?$/.test(t) || /月份/.test(t)) continue
    const cells = t
      .replace(/^\|/, '')
      .replace(/\|$/, '')
      .split('|')
      .map((c) => c.trim())
    if (cells.length < 2) continue
    const month = cells[0]
    if (!/^(?:20\d{2})-(?:0[1-9]|1[0-2])$/.test(month) && !/^\d{1,2}\s*月$/.test(month)) {
      continue
    }
    const amt = parseAmount(cells[1])
    if (amt == null) continue
    labels.push(month)
    values.push(amt)
  }
  if (labels.length < 2) return null
  return { labels, values }
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * @param {{ labels: string[], values: number[] }} series
 * @param {{ title?: string }} [opts]
 */
export function buildLineChartSvg(series, opts = {}) {
  const labels = series.labels || []
  const values = series.values || []
  if (labels.length < 2) return ''

  // 偏高画布，在固定输出列宽内更易读
  const w = 680
  const h = 380
  const padL = 58
  const padR = 24
  const padT = 36
  const padB = 48
  const plotW = w - padL - padR
  const plotH = h - padT - padB
  const minV = Math.min(...values)
  const maxV = Math.max(...values)
  const span = maxV - minV || 1
  const yMin = minV - span * 0.08
  const yMax = maxV + span * 0.12
  const ySpan = yMax - yMin || 1

  const pts = values.map((v, i) => {
    const x = padL + (labels.length === 1 ? plotW / 2 : (i / (labels.length - 1)) * plotW)
    const y = padT + plotH - ((v - yMin) / ySpan) * plotH
    return [x, y]
  })
  const polyline = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const area =
    `${padL},${(padT + plotH).toFixed(1)} ` +
    polyline +
    ` ${(padL + plotW).toFixed(1)},${(padT + plotH).toFixed(1)}`

  const yTicks = 4
  let grid = ''
  for (let i = 0; i <= yTicks; i++) {
    const t = i / yTicks
    const val = yMax - t * ySpan
    const y = padT + t * plotH
    grid += `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${padL + plotW}" y2="${y.toFixed(1)}" stroke="rgba(125,125,135,0.18)" stroke-width="1"/>`
    const label =
      Math.abs(val) >= 1000 ? `¥${(val / 1000).toFixed(0)}k` : `¥${Math.round(val)}`
    grid += `<text x="${padL - 8}" y="${(y + 4).toFixed(1)}" text-anchor="end" fill="currentColor" font-size="12" font-family="-apple-system,SF Pro Text,sans-serif" opacity="0.55">${esc(label)}</text>`
  }

  let xLabels = ''
  let dots = ''
  labels.forEach((lab, i) => {
    const [x, y] = pts[i]
    const short = String(lab).replace(/^20\d{2}-/, '')
    xLabels += `<text x="${x.toFixed(1)}" y="${h - 16}" text-anchor="middle" fill="currentColor" font-size="12" font-family="-apple-system,SF Pro Text,sans-serif" opacity="0.55">${esc(short)}</text>`
    dots += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4.5" fill="#007AFF" stroke="#fff" stroke-width="2"/>`
  })

  const title = opts.title || '月度采购额趋势'
  return (
    `<div class="md-line-chart" role="img" aria-label="${esc(title)}">` +
    `<svg viewBox="0 0 ${w} ${h}" width="100%" height="auto" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">` +
    `<rect width="${w}" height="${h}" rx="12" fill="transparent"/>` +
    `<text x="${padL}" y="22" fill="currentColor" font-size="14" font-weight="600" font-family="-apple-system,SF Pro Display,sans-serif">${esc(title)}</text>` +
    grid +
    `<polygon points="${area}" fill="rgba(0,122,255,0.12)"/>` +
    `<polyline points="${polyline}" fill="none" stroke="#007AFF" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>` +
    dots +
    xLabels +
    `</svg></div>`
  )
}

/**
 * 仅当服务端显式插入标记时才 SVG 兜底（与业务问句无关）。
 */
export function shouldInjectDashboardTrendChart(markdown) {
  const s = String(markdown || '')
  if (!s.includes(AUTO_LINE_CHART_MARKER)) return false
  // 正文已有真图则不再画兜底
  if (/!\[[^\]]*\]\(\s*https?:\/\//i.test(s)) return false
  return true
}

/**
 * 在已渲染 HTML 中，为带标记的「月度采购趋势」表补折线图。
 */
export function injectMonthlyTrendLineChart(html, markdownSource) {
  if (!shouldInjectDashboardTrendChart(markdownSource)) return String(html || '')
  let out = String(html || '')
  if (/月度采购趋势[\s\S]{0,800}?(?:md-figure|markdown-image|md-line-chart)/.test(out)) {
    return out
  }
  const series = extractMonthlyTrendSeries(markdownSource)
  if (!series) return out
  const svg = buildLineChartSvg(series)
  if (!svg) return out

  out = out.replace(
    /(<h[23][^>]*>[^<]*月度采购趋势[^<]*<\/h[23]>\s*)(<div class="md-table-wrap">|<table)/i,
    `$1${svg}$2`
  )
  return out
}
