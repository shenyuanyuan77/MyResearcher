/**
 * 采购仪表盘 / 月度趋势终审（与 Python dashboard_layout.py 对齐）
 */

import { renderGfmTable } from './reportTableCanon.js'

const FAKE_HEADER =
  /\|\s*(?:列\s*[12]|项目|内容|字段\s*\d+)\s*\|\s*(?:列\s*[12]|项目|内容|字段\s*\d+)?\s*\|/
const GLUED_TREND = /#{0,3}\s*[^\n]*月度采购趋势[^\n]{0,40}?月份[ \t]+(?:采购额|订单数)/

function fmtAmount(v) {
  let s = String(v || '')
    .trim()
    .replace(/,/g, '')
  if (!s) return '-'
  if (s.startsWith('¥')) return s
  const n = Number(s)
  if (!Number.isFinite(n)) return String(v).includes('¥') ? String(v) : `¥${v}`
  return Number.isInteger(n)
    ? `¥${n.toLocaleString('en-US')}`
    : `¥${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function inferYear(text) {
  const m = String(text || '').match(/月度采购趋势[^\n]{0,30}?(20\d{2})/)
  if (m) return Number(m[1])
  const years = [...String(text || '').matchAll(/(20\d{2})/g)].map((x) => Number(x[1]))
  if (years.length) return Math.max(...years)
  return new Date().getFullYear()
}

function toYm(token, year) {
  const t = String(token || '').trim()
  let m = t.match(/^(20\d{2})-(0[1-9]|1[0-2])$/)
  if (m) return `${m[1]}-${m[2]}`
  m = t.match(/^0?(\d{1,2})\s*月$/)
  if (m) {
    const mon = Number(m[1])
    if (mon >= 1 && mon <= 12) return `${year}-${String(mon).padStart(2, '0')}`
  }
  return null
}

function extractMonthlyAmountRows(text, year) {
  const y = year || inferYear(text)
  const rows = []
  const seen = new Set()
  const add = (ym, amt) => {
    amt = String(amt).replace(/,/g, '')
    if (seen.has(ym)) return
    const n = Number(amt)
    if (!Number.isFinite(n) || n < 100) return
    seen.add(ym)
    rows.push([ym, amt])
  }
  const s = String(text || '')
  for (const m of s.matchAll(
    /\|\s*((?:20\d{2})-(?:0[1-9]|1[0-2]))\s*\|\s*¥?\s*([\d,]+(?:\.\d+)?)\s*\|/g
  )) {
    add(m[1], m[2])
  }
  for (const m of s.matchAll(/\|\s*(0?\d{1,2}\s*月)\s*\|\s*¥?\s*([\d,]+(?:\.\d+)?)\s*\|/g)) {
    const ym = toYm(m[1], y)
    if (ym) add(ym, m[2])
  }
  for (const m of s.matchAll(
    /(?:^|\n)\s*(0?\d{1,2}\s*月|(?:20\d{2})-(?:0[1-9]|1[0-2]))\s+¥?\s*([\d,]+(?:\.\d+)?)\s+(\d{1,4})\b/g
  )) {
    const ym = toYm(m[1], y)
    if (ym) add(ym, m[2])
  }
  rows.sort((a, b) => a[0].localeCompare(b[0]))
  return rows
}

function extractMonthlyOrderCounts(text, year) {
  const y = year || inferYear(text)
  const out = {}
  const lines = String(text || '').split('\n')
  for (let i = 0; i < lines.length; i++) {
    const raw = String(lines[i] || '').trim()
    let m3 = raw.match(
      /^\|\s*((?:20\d{2})-(?:0[1-9]|1[0-2])|0?\d{1,2}\s*月)\s*\|\s*¥?[\d,.]+\s*\|\s*(\d{1,4})\s*\|/
    )
    if (m3) {
      const ym = toYm(m3[1], y)
      if (ym) out[ym] = m3[2]
      continue
    }
    const m2 = raw.match(
      /^\|\s*((?:20\d{2})-(?:0[1-9]|1[0-2])|0?\d{1,2}\s*月)\s*\|\s*¥?\s*([\d,]+(?:\.\d+)?)\s*\|?\s*$/
    )
    if (!m2) continue
    const ym = toYm(m2[1], y)
    if (!ym) continue
    const amt = m2[2].replace(/,/g, '')
    if (Number(amt) < 100 && !amt.includes('.')) {
      out[ym] = amt
      continue
    }
    if (i + 1 < lines.length) {
      const nxt = String(lines[i + 1] || '').trim()
      const mOc = nxt.match(/^\|\s*(\d{1,4})\s*\|+\s*$/)
      if (mOc && Number(mOc[1]) <= 5000) out[ym] = mOc[1]
    }
  }
  const s = String(text || '')
  for (const m of s.matchAll(
    /(?:^|\n)\s*(0?\d{1,2}\s*月|(?:20\d{2})-(?:0[1-9]|1[0-2]))\s+¥?\s*[\d,]+(?:\.\d+)?\s+(\d{1,4})\b/g
  )) {
    const ym = toYm(m[1], y)
    if (ym) out[ym] = m[2]
  }
  return out
}

function extractWarningCounts(text) {
  const s = String(text || '')
  let expiry = null
  let msl = null
  for (const pat of [
    /近效期(?:预警)?(?:批次)?\s*[：:]?\s*(\d+)/,
    /近效期预警批次\s*(\d+)/,
    /\|\s*近效期[^|]*\|\s*(\d+)\s*\|/,
  ]) {
    const m = s.match(pat)
    if (m) {
      expiry = m[1]
      break
    }
  }
  for (const pat of [
    /MSL(?:开封超时|预警)?(?:批次)?\s*[：:]?\s*(\d+)/,
    /MSL预警批次\s*(\d+)/,
    /\|\s*MSL[^|]*\|\s*(\d+)\s*\|/,
  ]) {
    const m = s.match(pat)
    if (m) {
      msl = m[1]
      break
    }
  }
  return [expiry, msl]
}

function extractKpiRows(text) {
  const wanted = ['物料总数', '供应商数', '客户数', '本月采购额', '本月订单数', '已完成订单']
  const found = {}
  const s = String(text || '')
  for (const name of wanted) {
    const m = s.match(new RegExp(`\\|\\s*${name}\\s*\\|\\s*([^|]+?)\\s*\\|`))
    if (m) found[name] = m[1].trim()
  }
  if (found['本月订单数'] && !found['已完成订单']) {
    const m = found['本月订单数'].match(/(\d+)\s*笔.*?完成\s*(\d+)/)
    if (m) {
      found['本月订单数'] = m[1]
      found['已完成订单'] = m[2]
    }
  }
  return wanted.filter((k) => found[k] != null).map((k) => [k, found[k]])
}

function looksLikeDashboard(text) {
  const s = String(text || '')
  return (
    /采购仪表盘|月度采购趋势|本月采购额/.test(s) ||
    (FAKE_HEADER.test(s) && /\d{1,2}\s*月|20\d{2}-/.test(s)) ||
    (/物料总数/.test(s) && /(?:\d{1,2}\s*月|20\d{2}-\d{2}).{0,20}[\d,]{4,}/.test(s))
  )
}

function needsFullRebuild(text, monthly) {
  const s = String(text || '')
  if (FAKE_HEADER.test(s)) return true
  if (GLUED_TREND.test(s)) return true
  if (/\|[^\n]*\|\n\*\*?趋势小结/.test(s)) return true
  if (/\|\s*(?:0?\d{1,2}\s*月|(?:20\d{2})-(?:0[1-9]|1[0-2]))\s*\|\s*¥?[\d,]{3,}/.test(s)) {
    if (/\|\s*\d{1,4}\s*\|+\s*\n\|\s*(?:0?\d{1,2}\s*月|20\d{2}-)/.test(s)) return true
    if (!/\|\s*月份\s*\|\s*采购额/.test(s)) return true
    if (
      /\|\s*(?:指标|数值|本月订单数|本月采购额)[^\n]*\|\n(?:\|[-:| \t]+\|\n)*(?:\|\s*(?:列\s*[12]|项目|内容)[^\n]*\|\n)*\|\s*(?:0?\d{1,2}\s*月|20\d{2}-)/.test(
        s
      )
    ) {
      return true
    }
  }
  if (/风险要点[\s\S]{0,400}月度采购趋势/.test(s)) return true
  if (monthly.length && !/\|\s*月份\s*\|\s*采购额/.test(s)) return true
  return false
}

function fixMonthKpiHeader(text) {
  const emit = (full, head, body) => {
    const rows = [...body.matchAll(/\|\s*(本月采购额|本月订单数|已完成订单)\s*\|\s*([^|]+?)\s*\|/g)]
    if (rows.length < 1) return full
    return (
      head +
      '\n\n' +
      renderGfmTable(
        ['指标', '数值'],
        rows.map((r) => [r[1], r[2].trim()])
      ) +
      '\n'
    )
  }
  let s = String(text || '').replace(
    /(###\s*[^\n]*本月[^\n]*)\n+(?:指标\s*\n+)?\|?\s*数值\s*(?:\|\s*(?:列\s*\d+|字段\s*\d+|项目|内容)?\s*)*\|?\s*\n+(?:\|[-:| \t]+\|\n+)*((?:\|[^\n]+\n*)+)/g,
    emit
  )
  s = s.replace(
    /(###\s*[^\n]*本月[^\n]*)\n+\|?\s*(?:指标|数值)\s*\|\s*(?:列\s*\d+|字段\s*\d+|数值|项目|内容)?\s*\|\n+(?:\|[-:| \t]+\|\n+)*((?:\|[^\n]+\n*)+)/g,
    emit
  )
  s = s.replace(
    /(###\s*[^\n]*本月[^\n]*)\n+((?:\|?\s*(?:本月采购额|本月订单数|已完成订单)\s*\|[^\n]*\n+)+)/g,
    emit
  )
  return s
}

/** 表行后紧贴非表行时补空行 */
export function ensureBlankLineAfterTables(text) {
  const lines = String(text || '').split('\n')
  const out = []
  for (let i = 0; i < lines.length; i++) {
    out.push(lines[i])
    const nxt = i + 1 < lines.length ? lines[i + 1] : null
    if (nxt == null) continue
    const cur = String(lines[i] || '').trim()
    const nxtS = String(nxt || '').trim()
    if (!cur.startsWith('|') || !cur.endsWith('|')) continue
    if (/^\|?\s*[-:| \t]+\|?$/.test(cur)) continue
    if (!nxtS || nxtS.startsWith('|') || nxtS.startsWith('```')) continue
    out.push('')
  }
  return out.join('\n')
}

export function repairDashboardAndMonthlyTrend(text) {
  let s = String(text || '')
  if (!looksLikeDashboard(s)) return ensureBlankLineAfterTables(s)

  s = s.replace(
    /(#{1,3}\s*[^\n]*月度采购趋势[^\n]{0,40}?)[ \t]+月份[ \t]+采购额[^\n]*订单数\s*/g,
    '$1\n\n'
  )
  s = s.replace(
    /(#{1,3}\s*[^\n]*月度采购趋势[^\n]{0,40}?)[ \t]+月份[ \t]+订单数[^\n]*采购额\s*/g,
    '$1\n\n'
  )
  // 无 # 前缀的粘连标题
  s = s.replace(
    /(^|\n)([^\n#]*月度采购趋势[^\n]{0,40}?)[ \t]+月份[ \t]+(?:采购额|订单数)[^\n]*/g,
    '$1### 📈月度采购趋势\n\n'
  )

  const year = inferYear(s)
  const monthly = extractMonthlyAmountRows(s, year)
  const orders = extractMonthlyOrderCounts(s, year)
  const [expiry, msl] = extractWarningCounts(s)
  const kpi = extractKpiRows(s)

  if (!needsFullRebuild(s, monthly)) {
    return ensureBlankLineAfterTables(fixMonthKpiHeader(s)).replace(/\n{3,}/g, '\n\n')
  }

  let trendSummary = ''
  let mSum = s.match(/(\*\*?趋势小[结结简析][^*\n]*\*?\*?[：:][^\n]+)/)
  if (!mSum) mSum = s.match(/(📉[^\n]+(?:峰值|回落)[^\n]+)/)
  if (mSum) {
    trendSummary = mSum[1].trim()
    if (!trendSummary.startsWith('**')) {
      trendSummary = `**趋势小结：**${trendSummary.replace(/^📉/, '').trim()}`
    }
  }

  const warnRows = []
  if (expiry != null) warnRows.push(['近效期批次', expiry])
  if (msl != null) warnRows.push(['MSL开封超时', msl])
  if (!warnRows.length) warnRows.push(['近效期批次', '-'], ['MSL开封超时', '-'])

  const trendRows = monthly.map(([month, amt]) => {
    let oc = orders[month] || '-'
    if (oc === '-') {
      const mon = Number(month.split('-')[1])
      if (mon) oc = orders[`${mon}月`] || '-'
    }
    return [month, fmtAmount(amt), oc]
  })

  const parts = ['## 📊采购仪表盘', '']
  if (kpi.length) {
    const overview = kpi.filter(([k]) => ['物料总数', '供应商数', '客户数'].includes(k))
    const monthKpi = kpi.filter(([k]) =>
      ['本月采购额', '本月订单数', '已完成订单'].includes(k)
    )
    if (overview.length) {
      parts.push(renderGfmTable(['指标', '数值'], overview), '')
    }
    if (monthKpi.length) {
      parts.push('### 本月', '', renderGfmTable(['指标', '数值'], monthKpi), '')
    }
  }
  parts.push('### ⚠️预警', '', renderGfmTable(['类型', '数量'], warnRows), '')
  if (trendRows.length) {
    parts.push(
      '### 📈月度采购趋势',
      '',
      '<!-- pcb-auto-line-chart -->',
      renderGfmTable(['月份', '采购额 (¥)', '订单数'], trendRows),
      ''
    )
  }
  if (trendSummary) parts.push(trendSummary, '')

  return ensureBlankLineAfterTables(parts.join('\n')).replace(/\n{3,}/g, '\n\n').trim() + '\n'
}
