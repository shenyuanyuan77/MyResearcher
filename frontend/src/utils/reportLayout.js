/**
 * 报告可读性布局 + 终审（与 Python report_layout.py 对齐）
 * 硬性要求：normalize(normalize(x)) === normalize(x)
 * 关键区块表格一律经 reportTableCanon.emit* / renderGfmTable 产出。
 */

import { emitRiskTable, emitSupplyTable, emitOrderIntegrityTable } from './reportTableCanon.js'
import { parseOrderCollectedProse, orderCollectedRegionRegex } from './orderCollectedProse.js'
import { repairDashboardAndMonthlyTrend } from './dashboardLayout.js'

const IMG_IN_CELL = /!\[[^\]]*\]\([^)]+\)/g
const SEP_LINE_RE = /^\|(?:[ \t]*:?-{1,}:?[ \t]*\|)+$/

/**
 * 表格单元格内的 `![…](url)` 剥到表后独立成块，避免图塞进风险/数据行。
 */
export function detachMediaFromPipeTables(text) {
  const lines = String(text || '').split('\n')
  const out = []
  let i = 0
  while (i < lines.length) {
    if (!lines[i].trim().startsWith('|')) {
      out.push(lines[i])
      i += 1
      continue
    }
    const block = []
    while (i < lines.length && lines[i].trim().startsWith('|')) {
      block.push(lines[i])
      i += 1
    }
    const images = []
    const newBlock = []
    for (const line of block) {
      const trimmed = line.trim()
      const found = trimmed.match(/!\[[^\]]*\]\([^)]+\)/g)
      if (!found) {
        newBlock.push(line)
        continue
      }
      images.push(...found)
      if (SEP_LINE_RE.test(trimmed)) {
        newBlock.push(line.replace(IMG_IN_CELL, ''))
        continue
      }
      let cleaned = trimmed.replace(IMG_IN_CELL, '')
      let body = cleaned.startsWith('|') ? cleaned.slice(1) : cleaned
      if (body.endsWith('|')) body = body.slice(0, -1)
      const cells = body.split('|').map((c) => c.trim())
      const nonempty = cells.filter(Boolean)
      if (cells.length >= 2 && /^\d+$/.test(cells[0] || '') && !cells.slice(1).some(Boolean)) {
        continue
      }
      if (!nonempty.length) continue
      newBlock.push('| ' + cells.join(' | ') + ' |')
    }
    out.push(...newBlock)
    if (images.length) {
      if (out.length && out[out.length - 1].trim()) out.push('')
      for (const im of images) out.push(im)
      out.push('')
    }
  }
  return out.join('\n')
}

function looksLikeTable(body) {
  const s = String(body || '')
  if (!s.trim()) return false
  return (
    /\|[^\n]+\|\s*\n\s*\|?\s*[-:| \t]+\|/.test(s) ||
    (/^\s*\|.+\|\s*$/m.test(s) && /^\s*\|?\s*-{2,}/m.test(s))
  )
}

function cellSafe(c) {
  return String(c || '')
    .replace(/\|/g, '｜')
    .replace(/\n/g, ' ')
    .replace(/\uFFFD/g, '')
    .replace(/[\uD800-\uDFFF]/g, '')
    .trim()
}

const SUPPLIER_SHARE_HEADING = /按供应商分布/
const SUPPLIER_SHARE_SKIP_CELL =
  /^(?:供应商|采购金额(?:\s*[（(]?¥[）)]?)?|占比|项目|内容|金额|角色|信用评级|数值|备注)$/
const SUPPLIER_SHARE_PCT = /^\d+(?:\.\d+)?%$/
const SUPPLIER_SHARE_AMT = /^(?:¥|￥)?[\d,]+(?:\.\d+)?$/

function _supplierShareCells(line) {
  const t = String(line || '').trim()
  if (!t.startsWith('|') || SEP_LINE_RE.test(t)) return null
  let body = t.startsWith('|') ? t.slice(1) : t
  if (body.endsWith('|')) body = body.slice(0, -1)
  return body.split('|').map((c) => c.trim())
}

function _looksSupplierShareAmt(c) {
  return SUPPLIER_SHARE_AMT.test(String(c || '').replace(/\s/g, ''))
}

function _looksSupplierSharePct(c) {
  return SUPPLIER_SHARE_PCT.test(String(c || '').replace(/\s/g, ''))
}

function _looksSupplierShareName(c) {
  const s = String(c || '').trim()
  if (!s || s === '—' || s === '-') return false
  if (SUPPLIER_SHARE_SKIP_CELL.test(s.replace(/\s/g, '')) || SUPPLIER_SHARE_SKIP_CELL.test(s)) {
    return false
  }
  if (_looksSupplierShareAmt(s) || _looksSupplierSharePct(s)) return false
  return /[\u4e00-\u9fffA-Za-z]/.test(s)
}

/** 锯齿错位「名|金额 / %|下一名|金额」→ 标准三列：供应商|采购金额|占比 */
function _tripletSupplierShareRows(flat) {
  if (!flat || flat.length < 6 || flat.length % 3 !== 0) return null
  const rows = []
  for (let i = 0; i < flat.length; i += 3) {
    const name = flat[i]
    const amt = flat[i + 1]
    const pct = flat[i + 2]
    if (!_looksSupplierShareName(name) || !_looksSupplierShareAmt(amt) || !_looksSupplierSharePct(pct)) {
      return null
    }
    rows.push([name, amt, pct])
  }
  return rows.length >= 2 ? rows : null
}

/**
 * 修复「按供应商分布（金额）」错位表（含 项目|内容 假表头）。
 * 仅命中该节标题时动手；无法解析则原样保留。
 */
export function repairSupplierAmountShareTables(text) {
  const lines = String(text || '').split('\n')
  const out = []
  let i = 0
  while (i < lines.length) {
    const raw = lines[i]
    const trimmed = raw.trim()
    if (!(trimmed.startsWith('#') && SUPPLIER_SHARE_HEADING.test(trimmed))) {
      out.push(raw)
      i += 1
      continue
    }
    const heading = trimmed.replace(/\|.*$/, '').trim()
    out.push(heading)
    i += 1
    while (i < lines.length && !lines[i].trim()) i += 1

    const blockStart = i
    const flat = []
    while (i < lines.length) {
      const t = lines[i].trim()
      if (!t) {
        let j = i + 1
        while (j < lines.length && !lines[j].trim()) j += 1
        if (j < lines.length && lines[j].trim().startsWith('|')) {
          i = j
          continue
        }
        break
      }
      if (/^---+$/.test(t) || t.startsWith('#')) break
      if (!t.startsWith('|')) break
      const cells = _supplierShareCells(t)
      if (cells) {
        for (const c of cells) {
          if (!c) continue
          const compact = c.replace(/\s/g, '')
          if (SUPPLIER_SHARE_SKIP_CELL.test(compact) || SUPPLIER_SHARE_SKIP_CELL.test(c)) continue
          flat.push(c)
        }
      }
      i += 1
    }

    const rows = _tripletSupplierShareRows(flat)
    if (rows) {
      if (out.length && out[out.length - 1].trim()) out.push('')
      out.push('| 供应商 | 采购金额 (¥) | 占比 |')
      out.push('|--------|---------------|------|')
      for (const [name, amt, pct] of rows) {
        out.push(`| ${cellSafe(name)} | ${cellSafe(amt)} | ${cellSafe(pct)} |`)
      }
      out.push('')
    } else {
      for (let k = blockStart; k < i; k++) out.push(lines[k])
    }
  }
  return out.join('\n')
}

const ORDER_INTEGRITY_FIELDS =
  '物料名称|物料编码|partId|MPN|供应商|数量|单价|创建人|预计交货日期|备注|createdBy|orderNumber|order_id|订单编号|订单ID'

const ORDER_INTEGRITY_FIELD_RE = new RegExp(
  String.raw`\|\s*\*{0,2}(${ORDER_INTEGRITY_FIELDS})\*{0,2}\s*\|\s*([^|]*)\|?\s*([^|\n]*)`,
  'gi'
)

function _normalizeOrderIntegrityStatus(status, value) {
  let st = String(status || '').replace(/\s+/g, ' ').trim()
  let val = String(value || '').replace(/\s+/g, ' ').trim()
  if ((!st || !/[✅⚠️❓❌]/.test(st)) && /[✅⚠️❓❌]/.test(val)) {
    const sm = val.match(/^(.*?)([✅⚠️❓❌].*)$/u)
    if (sm) {
      val = sm[1].trim() || val
      st = sm[2].trim()
    }
  }
  st = st
    .replace(/需要\s*createdBy\s*ID/gi, '需要 createdById')
    .replace(/需要\s*createdById/gi, '需要 createdById')
    .replace(/^⚠️\s*/, '⚠️ ')
    .replace(/^❓\s*/, '❓ ')
  if (/需要\s*createdById/i.test(st) && !st.includes('⚠️')) st = `⚠️ ${st}`
  if (!st) st = '—'
  if (val === '-' || val === '' || val === '—') val = '-'
  return { value: val, status: st }
}

function _parseOrderIntegrityRows(chunk) {
  const rows = []
  let schemaFromCell = ''
  ORDER_INTEGRITY_FIELD_RE.lastIndex = 0
  for (const m of String(chunk || '').matchAll(ORDER_INTEGRITY_FIELD_RE)) {
    const field = m[1]
    let value = String(m[2] || '').trim()
    let status = String(m[3] || '').trim()
    for (const key of ['status', 'value']) {
      const part = key === 'status' ? status : value
      const idx = part.search(/(?:---+[ \t]*)?\*{0,2}Schema\s*校验结果/)
      if (idx >= 0) {
        schemaFromCell = part.slice(idx).replace(/^---+\s*/, '').trim()
        if (key === 'status') status = part.slice(0, idx).trim()
        else value = part.slice(0, idx).trim()
      }
    }
    const norm = _normalizeOrderIntegrityStatus(status, value)
    rows.push([field, norm.value, norm.status])
  }
  return { rows, schemaFromCell }
}

function _formatOrderSchemaBlock(raw) {
  let t = String(raw || '')
    .replace(/^\*{0,2}Schema\s*校验结果\*{0,2}[：:]?\s*/i, '')
    .replace(/\|/g, '')
    .trim()
  if (!t) return ''
  t = t.replace(/\s*-\s+\*\*/g, '\n- **')
  const lines = t
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l && l !== '-' && l !== '- **' && l !== '**')
    .map((l) => (l.startsWith('-') ? l : `- ${l}`))
  if (!lines.length) return ''
  return `**Schema 校验结果：**\n\n${lines.join('\n')}\n`
}

function _rewriteOrderIntegrityRegion(full, index, region) {
  const { rows, schemaFromCell } = _parseOrderIntegrityRows(region)
  if (rows.length < 3) return full

  let schemaRaw = schemaFromCell
  const schemaInRegion = region.match(/\*{0,2}Schema\s*校验结果[\s\S]*/i)
  if (schemaInRegion) schemaRaw = schemaInRegion[0]

  let out =
    '好的，让我进行数据完整性校验。\n\n**已收集到的订单数据：**\n\n' +
    emitOrderIntegrityTable(rows)
  const schemaBlock = _formatOrderSchemaBlock(schemaRaw)
  if (schemaBlock) out += `\n---\n\n${schemaBlock}`

  return full.slice(0, index) + out + full.slice(index + region.length)
}

/**
 * 下单「已收集订单数据」完整性表 → 标准三列（字段|值|状态）。
 * 仅命中该场景；解析不足 3 行则原样保留。
 */
export function repairOrderIntegrityTables(text) {
  let s = String(text || '')
  s = repairOrderCollectedDataProse(s)
  // 已是标准三列表则不再套「完整性校验」开场，避免丢字段、重复标题
  if (
    /\|\s*字段\s*\|\s*值\s*\|\s*状态\s*\|/.test(s) &&
    (/\| ?partId\s*\|/.test(s) || /\| ?物料名称\s*\|/.test(s))
  ) {
    return s
  }
  if (!/已收集到的订单数据|已收集的订单数据|数据完整性校验/.test(s)) return s

  const regionRe =
    /(?:\|[^\n]*)?(?:好的[，,]?)?(?:让我)?进行数据完整性校验[\s\S]*?已收集到的订单数据[\s\S]*?(?=\n请问 |\n子 Agent|$)/
  const m = s.match(regionRe)
  if (!m) {
    const alt = s.match(
      /\*{0,2}已收集到?的订单数据\*{0,2}[：:]?[\s\S]*?(?=\n请问 |\n子 Agent|数据看起来|让我直接|$)/
    )
    if (!alt) return s
    return _rewriteOrderIntegrityRegion(s, alt.index, alt[0])
  }
  return _rewriteOrderIntegrityRegion(s, m.index, m[0])
}

/**
 * 密文「**已收集的数据：**-物料ID：…-数量：…」→ 字段|值|状态 表。
 */
export function repairOrderCollectedDataProse(text) {
  const s = String(text || '')
  if (!/已收集的数据|已收集到的订单数据/.test(s)) return s
  if (/\|\s*字段\s*\|\s*值\s*\|/.test(s) && (/\| ?partId\s*\|/.test(s) || /\| ?物料名称\s*\|/.test(s))) {
    return s
  }

  const re = orderCollectedRegionRegex()
  const m = s.match(re)
  if (!m || m.index == null) return s
  const rows = parseOrderCollectedProse(m[2] || '')
  if (!rows || rows.length < 3) return s

  const table =
    '**已收集的订单数据：**\n\n' +
    emitOrderIntegrityTable(rows.map(([f, v]) => [f, v, '✅']))
  // 表后正文里的破折号统一，避免二次 normalize 才改成 - 破坏幂等
  const tail = s.slice(m.index + m[0].length).replace(/[—–﹣－―]/g, '-')
  return s.slice(0, m.index) + table + '\n' + tail
}

export function mergeOrphanTableNameRows(text) {
  const lines = String(text || '').split('\n')
  const out = []
  const nameRe = /板多多|1688|阿里|供应商|SUP-|CCL-|PCB-|FR-?4|高TG|半固化|PP-/
  const dataRe = /主供|备选|合作|对比|替代|优先级|已建立|[A-D]\s*\| |\d+\.\d+%/
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i]
    const line = raw.trim()
    const next = (lines[i + 1] || '').trim()
    const next2 = (lines[i + 2] || '').trim()
    const pipeCount = (line.match(/\|/g) || []).length
    const nameOnly =
      /^\|/.test(line) &&
      pipeCount <= 2 &&
      !/^\|(?:[ \t]*:?-{1,}:?[ \t]*\|)+$/.test(line) &&
      nameRe.test(line)

    let dataLine = ''
    let skip = 0
    if (nameOnly) {
      if (/^\|/.test(next) && (next.match(/\|/g) || []).length >= 3 && !/^[\s|:\-]+$/.test(next)) {
        dataLine = next
        skip = 1
      } else if (!next && /^\|/.test(next2) && (next2.match(/\|/g) || []).length >= 3) {
        dataLine = next2
        skip = 2
      }
    }
    if (nameOnly && dataLine && dataRe.test(dataLine)) {
      const firstData = dataLine.replace(/^\|/, '').split('|')[0].trim()
      // 仅拦截「名 / 3个核心料|金额…」假合并；替代料下一行首格常为 CCL- 编码
      if (/^\d+\s*个/.test(firstData) || /核心料|金额|占比/.test(firstData)) {
        out.push(raw)
        continue
      }
      const name = line.replace(/^\|/, '').replace(/\|$/, '').trim()
      let body = dataLine.replace(/^\|/, '')
      let prose = ''
      const bm = body.match(/(?:\|\s*)?(-\s+\*\*[^*].*)$/)
      if (bm) {
        prose = bm[1].trim()
        body = body.slice(0, bm.index).replace(/\s+$/, '')
        if (!body.endsWith('|')) body += '|'
      }
      out.push('|' + name + '|' + body)
      if (prose) {
        out.push('')
        out.push(prose.replace(/^-\s*/, '').trim())
      }
      i += skip
      continue
    }
    out.push(raw)
  }
  return out.join('\n')
}

function splitDashItems(body) {
  let s = String(body || '').trim().replace(/^[：:\s]+/, '')
  if (!s || looksLikeTable(s)) return []
  if (s.includes('\n') && (/^\s*[-•]/m.test(s) || /\n\s*[-•]/.test(s))) {
    return s
      .split('\n')
      .map((l) => l.replace(/^\s*[-•*]\s*/, '').trim())
      .filter((l) => l && !l.startsWith('|'))
  }
  s = s.replace(/^[-•]\s*/, '')
  if (/(?:板多多|1688|阿里巴巴).{0,120}(?:板多多|1688|阿里巴巴)/.test(s)) {
    const parts = s
      .split(/\s*-\s*(?=板多多|阿里巴巴|1688工业品)/)
      .map((x) => x.replace(/^\*\*/, '').replace(/\*\*$/, '').trim())
      .filter((p) => p && !p.startsWith('|'))
    if (parts.length >= 2) return parts
  }
  let parts = s
    .split(/(?<=[。；）%）])\s*-\s*(?=[\u4e00-\u9fffA-Za-z*])/)
    .map((x) => x.trim())
    .filter((p) => p && !p.startsWith('|'))
  if (parts.length >= 2) return parts
  // 两侧必须有空白，避免切开 CCL-FR4 / PP-7628
  parts = s
    .split(/\s+-\s+(?=(?:覆铜板|高\s*TG|FR\d|半固化|PP-|CCL-|库存))/)
    .map((x) => x.trim())
    .filter((p) => p && !p.startsWith('|'))
  if (parts.length >= 2) return parts
  return s
    .split(/(?<=[\s。；）%）])-\s+(?=[\u4e00-\u9fffA-Za-z*])/)
    .map((x) => x.trim())
    .filter((p) => p && !p.startsWith('|'))
}

function parseSupplyItem(item) {
  let s = item.replace(/^\*\*/, '').replace(/\*\*$/, '').trim()
  if (!s || /^风险/.test(s) || s.startsWith('|')) return null
  const nameM = s.match(/^(.+?)[：:]/)
  const name = (nameM ? nameM[1] : s.split(/[，,]/)[0] || '').trim()
  if (!name || name.length > 40) return null
  const sku =
    (s.match(/物料\s*([^；;]+)/) || [])[1] ||
    (s.match(/(\d+\s*个[^，,¥%（(]*)/) || [])[1] ||
    ''
  const amount = (s.match(/金额\s*¥?\s*([\d,.]+)/) || [])[1] || ''
  const pct = (s.match(/占比约?\s*([\d.]+%)/) || [])[1] || ''
  let role = ((s.match(/角色\s*([^；;]+)/) || [])[1] || '').trim()
  let credit = ((s.match(/信用\s*([A-D])/) || [])[1] || '').trim()
  if (!role || !credit) {
    const parens = [...s.matchAll(/（([^）]+)）/g)].map((m) => m[1])
    for (let i = parens.length - 1; i >= 0; i--) {
      const inner = parens[i]
      if (/主供|备选|信用/.test(inner)) {
        if (!role) {
          role =
            (inner.match(/(主供|备选\/比价|备选|合作主供|对比备选)/) || [])[1] ||
            inner.split(/[，,]/)[0] ||
            ''
        }
        if (!credit) credit = (inner.match(/信用(?:评级)?\s*([A-D])/) || [])[1] || ''
        break
      }
    }
  }
  if (!role) role = (s.match(/(主供|备选\/比价|备选|合作主供)/) || [])[1] || ''
  if (!amount && !pct) return null
  return { name, sku: sku.trim() || '-', amount: amount || '-', pct: pct || '-', role: role || '-', credit: credit || '-' }
}

export function expandSupplyAndRiskBlocks(text) {
  let s = String(text || '')
  s = s.replace(
    /\*\*供应结构\*\*[：:]?\s*([\s\S]*?)(?=\*\*风险|\n---\s*\n|\n## |\n### |$)/,
    (full, body) => {
      if (looksLikeTable(body)) return full
      const items = splitDashItems(body)
      const rows = items.map(parseSupplyItem).filter(Boolean)
      if (!rows.length) {
        if (items.length >= 2 && !items.some((it) => it.includes('|'))) {
          return '\n\n**供应结构**\n\n' + items.map((it) => `- ${it}`).join('\n') + '\n\n'
        }
        return full
      }
      return (
        '\n\n' +
        emitSupplyTable(
          rows.map((r) => [r.name, r.sku, r.amount, r.pct, r.role, r.credit])
        )
      )
    }
  )
  s = s.replace(
    /\*\*风险要点?\*\*[：:]?\s*([\s\S]*?)(?=\n---\s*\n|\n## |\n### |\n\*\*(?:供应结构|风险要点|关键数字)\*\*|$)/,
    (full, body) => {
      if (looksLikeTable(body)) return full
      const items = splitDashItems(body).filter(
        (it) => it && !/^风险/.test(it) && !it.includes('|') && !it.includes('序号') && !it.includes('风险说明')
      )
      if (!items.length) return full
      return '\n\n' + emitRiskTable(items)
    }
  )
  return s
}

function parseProfileChunk(title, rest) {
  let name = title
  let role = ''
  let share = ''
  const tm = title.match(/^(.+?[）)])\s*[-—–]\s*(.+)$/) || title.match(/^([^（(]+?)\s*[-—–]\s*(.+)$/)
  if (tm) {
    name = tm[1].trim()
    const tag = tm[2]
    role = (tag.match(/(主供|备选|散剪比价渠道|合作主供|对比备选)/) || [])[1] || tag.split(/[，,]/)[0] || ''
    share = (tag.match(/占比[^\s，,]*/) || [])[0] || (tag.match(/[一二三四五六七八九十\d]+成/) || [])[0] || ''
  }
  const bullets = splitDashItems(rest)
  let coverage = ''
  let lead = ''
  let credit = ''
  let note = ''
  for (const b of bullets) {
    if (b.includes('|')) continue
    if (/涵盖|供应|仅供|核心渠道|物料/.test(b) && !coverage) coverage = b.replace(/^[-•]\s*/, '').slice(0, 40)
    else if (/交期/.test(b) && !lead) lead = b.replace(/^[-•]\s*/, '').slice(0, 36)
    else if (/信用/.test(b) && !credit) {
      credit = (b.match(/[A-D]/) || [])[0] || b.slice(0, 20)
      if (/稳定|波动/.test(b)) note = (note ? note + '；' : '') + b.replace(/^[-•]\s*/, '').slice(0, 30)
    } else if (/劣势|优势|风险|无卤|备选/.test(b)) {
      note = (note ? note + '；' : '') + b.replace(/^[-•]\s*/, '').slice(0, 40)
    }
  }
  if (!share) share = (rest.match(/占比[^\s，,。]*/) || [])[0] || ''
  if (!credit) credit = (rest.match(/信用(?:评级)?\s*([A-D])/) || [])[1] || ''
  return { name, role, share, coverage, lead, credit, note }
}

export function expandSupplierProfile(text) {
  return String(text || '').replace(
    /(#{2,3}\s+[^\n]*供应商画像)([\s\S]*?)(?=\n---\s*\n|\n## |\n### \d|\n### [^\d]|$)/,
    (full, heading, body) => {
      if (
        looksLikeTable(body) &&
        !/对比项\s*\|+\s*对比项|\/\s*信用\s*\/|\/\s*角色\s*\/|\/\s*优势\s*\//.test(body)
      ) {
        return full
      }
      const chunks = []
      const marks = [...body.matchAll(/\*\*([^*]+)\*\*/g)]
      if (marks.length >= 2) {
        for (let i = 0; i < marks.length; i++) {
          const title = marks[i][1].trim()
          if (title.length < 2 || title.startsWith('|')) continue
          const start = marks[i].index + marks[i][0].length
          const end = i + 1 < marks.length ? marks[i + 1].index : body.length
          chunks.push({ name: title, rest: body.slice(start, end).trim() })
        }
      } else {
        const alt = body.split(/(?=(?:\*\*)?(?:板多多|1688工业品|阿里巴巴1688))/).filter((x) => x.trim())
        for (const a of alt) {
          const t = a.replace(/^\*\*/, '').replace(/\*\*/, ' ').trim()
          const name = (t.match(/^(板多多[^\-\n]*|1688工业品[^\-\n]*|阿里巴巴1688[^\-\n]*)/) || [])[1] || t.slice(0, 20)
          chunks.push({ name: name.trim(), rest: t.slice(name.length).replace(/^[-：:\s]+/, '') })
        }
      }
      if (chunks.length < 2) return full
      const parsed = chunks
        .slice(0, 3)
        .map((c) => parseProfileChunk(c.name, c.rest))
        .filter((p) => p.name && p.name.length >= 2)
      if (parsed.length < 2) return full
      const headers = ['对比项', ...parsed.map((p) => p.name)]
      const fields = [
        ['角色', ...parsed.map((p) => p.role || '-')],
        ['金额占比', ...parsed.map((p) => p.share || '-')],
        ['覆盖物料', ...parsed.map((p) => p.coverage || '-')],
        ['交期', ...parsed.map((p) => p.lead || '-')],
        ['信用', ...parsed.map((p) => p.credit || '-')],
        ['优势与风险', ...parsed.map((p) => p.note || '-')],
      ]
      let t = `\n${heading.trim()}\n\n| ${headers.map(cellSafe).join(' | ')} |\n| ${headers.map(() => '---').join(' | ')} |\n`
      for (const row of fields) {
        t += `| ${row.map(cellSafe).join(' | ')} |\n`
      }
      return t + '\n'
    }
  )
}

export function expandConclusionActions(text) {
  let s = String(text || '')
  s = s.replace(/^(#{1,3}\s+[^\n]*结论)\s*\n+与行动建议\s*/gm, '$1与行动建议\n\n')
  s = s.replace(/(结论与行动建议)\s*(?=\d+\.)/g, '$1\n\n')
  s = s.replace(/(#{1,3}\s+[^\n]*行动建议)\s*(?=\d+\.)/g, '$1\n\n')
  s = s.replace(
    /(#{1,3}\s+[^\n]*(?:结论与行动建议|结论|行动建议)[^\n]*\n+)((?:[1-9]\d?\.\s+\*\*[^*\n]+?\*\*[：:][^\n]*(?:\n(?![1-9]\d?\.\s+|#{1,3}\s+|---)[^\n]*)*\n?)+)/,
    (full, head, list) => {
      if (looksLikeTable(list) || /\| ?序号 ?\|/.test(list)) return full
      const items = []
      const itemRe = /([1-9]\d?)\.\s+\*\*([^*]+?)\*\*[：:]\s*([\s\S]*?)(?=(?:[1-9]\d?\.\s+\*\*)|$)/g
      let m
      while ((m = itemRe.exec(list)) !== null) {
        const rawTitle = m[2].trim()
        const body = m[3].replace(/\s+/g, ' ').trim()
        let title = rawTitle
        let priority = ''
        const pm = rawTitle.match(/^(.+?)[（(]([^）)]+)[）)]$/)
        if (pm) {
          title = pm[1].trim()
          priority = pm[2].trim()
        }
        items.push({ n: m[1], title, priority, body })
      }
      if (items.length < 2) return full
      let t =
        head.replace(/\n+$/, '\n\n') + '| 序号 | 事项 | 优先级 | 建议 |\n|------|------|--------|------|\n'
      for (const it of items) {
        t += `| ${it.n} | ${cellSafe(it.title)} | ${cellSafe(normalizeActionPriority(it.priority || '-'))} | ${cellSafe(cleanActionBody(it.body))} |\n`
      }
      // 多留空行，避免表尾与后续 --- 粘连（破坏幂等）
      return t + '\n'
    }
  )
  return s
}

function repairSlashPseudoTables(text) {
  const out = []
  for (const line of String(text || '').split('\n')) {
    const t = line.trim()
    const pipeN = (t.match(/\|/g) || []).length
    // 已是多列表行：绝不按 / 重切（物料名常含 CCL-FR4-1.6 / FR4-0.8）
    if (t.startsWith('|') && pipeN >= 4) {
      if (/序号\s*\/\s*风险说明|\/ 序号 \//.test(t)) continue
      if (/^\|[\s/]*\|?$/.test(t)) continue
      out.push(line)
      continue
    }
    if (t.startsWith('/') && t.endsWith('/') && (t.match(/\//g) || []).length >= 3 && !t.includes('|') && !t.startsWith('//')) {
      const cells = t
        .replace(/^\/+|\/+$/g, '')
        .split('/')
        .map((c) => c.trim())
        .filter(Boolean)
      if (cells.length >= 2) {
        out.push('| ' + cells.map(cellSafe).join(' | ') + ' |')
        continue
      }
    }
    // 混写且几乎不是表：|/ 优势 / 风险 /
    if (
      t.includes('|') &&
      pipeN <= 3 &&
      (t.match(/\//g) || []).length >= 2 &&
      /\/\s*(?:信用|优势|风险|角色|交期|对比)/.test(t)
    ) {
      const core = t.replace(/\|/g, ' ').trim()
      const cells = core
        .replace(/^\/+|\/+$/g, '')
        .split('/')
        .map((c) => c.trim())
        .filter((c) => c && c !== '-')
      if (cells.length >= 2) {
        out.push('| ' + cells.map(cellSafe).join(' | ') + ' |')
        continue
      }
    }
    if (/^\|/.test(t) && /^\|[\s/]*\|?$/.test(t)) continue
    out.push(line)
  }
  return out.join('\n')
}

function riskItemsFromMangledBlock(block) {
  const chunks = []
  for (const line of String(block || '').split('\n')) {
    let t = line.trim()
    if (!t || t.startsWith('**风险要点') || /^\|[\s|:\-]+$/.test(t)) continue
    if (t.startsWith('|')) {
      const cells = t.replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
      if (cells[0] === '序号') continue
      if (cells.length >= 2 && /^\d+$/.test(cells[0])) chunks.push(cells[1])
      else chunks.push(...cells.filter((c) => c && c !== '风险说明' && c !== '序号'))
    } else {
      chunks.push(t.replace(/^\*\*|\*\*$/g, '').trim())
    }
  }
  const glued = []
  for (const c of chunks) {
    if (glued.length && /CCL\s*[|｜]?\s*$/.test(glued[glued.length - 1]) && /^FR\d/.test(c)) {
      glued[glued.length - 1] = glued[glued.length - 1].replace(/\s*[|｜]?\s*$/, '') + '-' + c
    } else if (
      glued.length &&
      glued[glued.length - 1].replace(/[|｜\s]+$/, '').endsWith('CCL') &&
      c.startsWith('FR')
    ) {
      glued[glued.length - 1] = glued[glued.length - 1].replace(/[|｜\s]+$/, '') + '-' + c
    } else {
      glued.push(c)
    }
  }
  let prose = glued
    .join(' ')
    .replace(/\bCCL\s*[|｜]\s*FR/g, 'CCL-FR')
    .replace(/\bCCL\s+FR/g, 'CCL-FR')
    .replace(/\s+/g, ' ')
    .trim()
  if (!prose || prose.length < 8) return []
  let parts = prose
    .split(/(?:(?<=\S)\s+)(?=\d+[\.、]\s*\*?\*?|\d+\s+\*\*)/)
    .map((p) => p.trim())
    .filter(Boolean)
  if (parts.length < 2) {
    parts = prose
      .split(/(?:\s+|\n)+(?=\d+(?:[\.、]\s*|\s+)\*\*)/)
      .map((p) => p.trim())
      .filter(Boolean)
  }
  const clean = []
  for (let p of parts) {
    p = p
      .replace(/^\d+\s+/, '')
      .replace(/^\d+[\.、]\s*/, '')
      .replace(/\*\*([^*]+)\*\*/g, '$1')
      .replace(/\*\*/g, '')
      .replace(/^\d+\s*$/, '')
      .replace(/^[|｜]\s*/, '')
      .replace(/[|｜]\s*$/, '')
      .replace(/\s*---\s*$/, '')
      .trim()
    if (p === '序号' || p === '风险说明') continue
    if (p.length >= 6) clean.push(p)
  }
  return clean
}

function repairNestedRiskTables(text) {
  // 单元格内合法加粗（**日期**）不算损坏；仅表间插入「2. …」散文才走 mangled
  return String(text || '').replace(
    /\*\*风险要点\*\*\s*\n+(?:\|[^\n]*(?:\n|$)|^\d+[\.、][^\n]*(?:\n|$)|^\*\*近效期[^\n]*(?:\n|$))+/gm,
    (block) => {
      const proseIntrusion =
        /^\d+[\.、]\s+/m.test(block) || /^\*\*近效期/m.test(block)
      const rows = []
      for (const line of block.split('\n')) {
        const m = line.match(/^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|?\s*$/)
        if (
          m &&
          !m[2].includes('序号') &&
          !m[2].includes('风险说明') &&
          !/^[\s/]/.test(m[2]) &&
          !/\*\*[A-Za-z]*\s*$/.test(m[2]) &&
          !isFakeRiskDesc(m[2].trim())
        ) {
          rows.push([m[1], m[2].trim()])
        }
      }
      let clean = rows
      if (proseIntrusion || clean.length < 1) {
        let rebuilt = riskItemsFromMangledBlock(block).filter((d) => !isFakeRiskDesc(d))
        if (rebuilt.length) clean = rebuilt.map((d, i) => [String(i + 1), d])
        else if (clean.length < 1) return block
      }
      if (clean.length < 1) return block
      const items = []
      const seen = new Set()
      for (const [, desc] of clean) {
        const raw = String(desc)
          .replace(/\*\*([^*]+)\*\*/g, '$1')
          .replace(/\*\*/g, '')
          .replace(/\bCCL\s+FR/g, 'CCL-FR')
        for (const part of splitMashedRiskDesc(raw)) {
          if (isFakeRiskDesc(part) || part.length < 6) continue
          const key = part.replace(/\s+/g, '').slice(0, 48)
          if (seen.has(key)) continue
          seen.add(key)
          items.push(part)
        }
      }
      if (!items.length) return block
      return emitRiskTable(items)
    }
  )
}

function repairBrokenProfileHeaders(text) {
  const lines = String(text || '').split('\n')
  const out = []
  for (let i = 0; i < lines.length; i++) {
    if (/\|?\s*对比项\s*\|+\s*对比项/.test(lines[i])) {
      if (i + 1 < lines.length && /^[\s|:\-/]+$/.test(lines[i + 1].trim())) i++
      continue
    }
    out.push(lines[i])
  }
  return out.join('\n')
}

function isFakeRiskDesc(desc) {
  const d = String(desc || '').trim()
  if (!d) return true
  if (/!\[[^\]]*\]\([^)]+\)/.test(d) && !d.replace(/!\[[^\]]*\]\([^)]+\)/g, '').trim()) return true
  if (/^MSL\s*=?\s*\d+(?:\s*[-–]\s*\d+)?$/i.test(d)) return true
  if (/(库存|安全|替代|单源|涨|交期|效期|到期|预警|断供|缺口|无替代|缺料|潮敏|双渠道|覆盖|信用|品质|批次)/.test(d)) {
    return false
  }
  if (/¥\s*[\d,]+\s*[（(]?\s*\d+\.?\d*\s*%/.test(d)) return true
  if (/^(?:板多多|阿里|1688|立创|华强).{0,48}\d+\.?\d*\s*%/.test(d)) return true
  if (d.includes('¥') && d.includes('%') && d.length < 48) return true
  return false
}

function splitMashedRiskDesc(desc) {
  let d = String(desc || '')
    .replace(/!\[[^\]]*\]\([^)]+\)/g, '')
    .trim()
    .replace(/^[\s\-–—]+|[\s\-–—]+$/g, '')
  if (!d) return []
  // 粘进下一行序号：`…压力低 2 MSL 1 - 1`
  d = d.replace(/\s+(\d{1,3}\s+(?:MSL\b|[🔴🟡🟢🟠]|⚠️))/gi, '\n$1')
  const emojis = d.match(/[🔴🟡🟢🟠]|⚠️/gu) || []
  if (emojis.length < 2 && !d.includes('\n')) return [d]
  let parts = d
    .split(/(?=(?:[🔴🟡🟢🟠]|⚠️))/u)
    .flatMap((p) => p.split('\n'))
    .map((p) => p.replace(/^[\s\-–—]+|[\s\-–—]+$/g, '').trim())
    .filter((p) => p.length >= 4)
  // 去掉「2 MSL…」这类纯序号残片（已是假风险）
  parts = parts.filter((p) => !isFakeRiskDesc(p))
  return parts.length >= 2 ? parts : [d.replace(/\n/g, ' ').trim()].filter(Boolean)
}

function extractRiskItemsFromBlock(body) {
  const items = []
  const seen = new Set()

  const push = (desc) => {
    for (const part of splitMashedRiskDesc(desc)) {
      if (part === '风险说明' || part === '序号' || isFakeRiskDesc(part)) continue
      if (part.length < 6) continue
      const key = part.replace(/\s+/g, '').slice(0, 48)
      if (seen.has(key)) continue
      seen.add(key)
      items.push(part)
    }
  }

  for (const line of String(body || '').split('\n')) {
    const m = line.match(/^\|\s*\d+\s*\|\s*([^|]+?)\s*\|?\s*$/)
    if (!m) continue
    push(m[1].trim())
  }
  if (!items.length) {
    for (const it of riskItemsFromMangledBlock('**风险要点**\n' + (body || ''))) {
      push(it)
    }
  }
  return items
}

function detachSectionGlues(text) {
  let s = String(text || '')
  s = s.replace(
    /(\]\([^)]+\))\s*(\*\*(?:供应结构|风险要点|关键数字)\*\*)/g,
    '$1\n\n$2'
  )
  s = s.replace(/(\*\*(?:供应结构|风险要点)\*\*)[：:]\s*/g, '$1\n\n')
  s = s.replace(/(\*\*(?:供应结构|风险要点)\*\*)[ \t]*\|/g, '$1\n\n|')
  s = s.replace(/(?<!\*)(供应结构|风险要点)[：:][ \t]*\|/g, '**$1**\n\n|')
  return s
}

function mergeDuplicateRiskSections(text) {
  let s = String(text || '')
  const m = s.match(/\n##\s*[二三四五六七]/)
  const idx = m ? s.indexOf(m[0]) : -1
  const head = idx >= 0 ? s.slice(0, idx) : s
  const tail = idx >= 0 ? s.slice(idx) : ''
  const blockRe =
    /\*\*风险要点\*\*\s*\n+([\s\S]*?)(?=\n\*\*(?:供应结构|风险要点|关键数字)\*\*|\n##\s|\n---\s*\n|$)/g
  const blocks = [...head.matchAll(blockRe)]
  if (blocks.length < 1) return s
  const allItems = []
  const seen = new Set()
  for (const b of blocks) {
    for (const it of extractRiskItemsFromBlock(b[1])) {
      const key = it.replace(/\s+/g, '').slice(0, 40)
      if (seen.has(key)) continue
      seen.add(key)
      allItems.push(it)
    }
  }
  let newHead = head.replace(/\n*\*\*风险要点\*\*\s*\n+(?:\|[^\n]*\n*)+/g, '\n\n')
  if (!allItems.length) return newHead.replace(/\n{3,}/g, '\n\n') + tail
  const riskMd = emitRiskTable(allItems)
  const sm = newHead.match(
    /(\*\*供应结构\*\*\s*\n+(?:\|[^\n]+\n)+)(\n*!\[|\n*---|\n*##|\n*$)/
  )
  let insertAt = null
  if (sm) {
    insertAt = sm.index + sm[1].length
  } else {
    const imgs = [...newHead.matchAll(/!\[[^\]]*\]\([^)]+\)/g)]
    if (imgs.length) insertAt = imgs[imgs.length - 1].index + imgs[imgs.length - 1][0].length
  }
  if (insertAt == null) {
    newHead = newHead.replace(/\s*$/, '') + '\n\n' + riskMd
  } else {
    newHead =
      newHead.slice(0, insertAt).replace(/\s*$/, '') +
      '\n\n' +
      riskMd +
      newHead.slice(insertAt).replace(/^\n+/, '')
  }
  return newHead.replace(/\n{3,}/g, '\n\n') + tail
}

function purgeFakeRiskRows(text) {
  return String(text || '').replace(
    /\*\*风险要点\*\*\s*\n+((?:\|[^\n]*\n*)+)/g,
    (_full, body) => {
      const items = extractRiskItemsFromBlock(body)
      if (!items.length) return '\n\n'
      return '\n\n' + emitRiskTable(items)
    }
  )
}

export function auditAndRepairReport(text) {
  let s = String(text || '')
  s = detachMediaFromPipeTables(s)
  s = fixSplitHeadings(s)
  s = detachSectionGlues(s)
  s = repairFragmentedSupplyAndRiskTables(s)
  s = mergeDuplicateRiskSections(s)
  s = purgeFakeRiskRows(s)
  s = detachMediaFromPipeTables(s)
  s = mergeIncompleteTableRows(s)
  s = repairComparisonAdvantageRows(s)
  s = repairMetricsTableHoldingRisks(s)
  s = ensureSummaryKpiTable(s)
  s = repairSlashPseudoTables(s)
  s = repairNestedRiskTables(s)
  s = repairBrokenProfileHeaders(s)
  s = repairBrokenActionAndQuickcheck(s)
  s = repairOrphanActionRows(s)
  s = mergeOrphanTableNameRows(s)
  s = detachSectionGlues(s)
  return s.replace(/\n{3,}/g, '\n\n')
}

const SUPPLY_HEADER_WORDS = new Set([
  '供应商',
  '涉及物料',
  '物料',
  '金额',
  '金额 (¥)',
  '金额(¥)',
  '占比',
  '角色',
  '信用',
])

function isFragmentedPipeBlock(body) {
  if (!body || !body.includes('|')) return false
  if (/^\|\s*(占比|角色|信用|涉及物料)\s*\|/m.test(body)) return true
  if (/\*\*供应结构\*\*\s*\|?\s*供应商/.test(body)) return true
  if (/^\|\s*供应商\s*\|?\s*$/m.test(body)) return true
  if (/\|供应商\|/.test(body) && /\|(?:涉及)?物料\|/.test(body)) return true
  const sepN = (body.match(/^\|[\s|:\-]+\|$/gm) || []).length
  if (sepN >= 2 && /板多多|1688/.test(body)) return true
  for (const line of body.split('\n')) {
    const t = line.trim()
    if (
      t.startsWith('|') &&
      t.includes('供应商') &&
      (t.includes('金额') || t.includes('占比')) &&
      t.includes('角色') &&
      (t.match(/\|/g) || []).length >= 6
    ) {
      return false
    }
  }
  return false
}

function flattenPipeCells(block) {
  const cells = []
  for (const line of String(block || '').split('\n')) {
    let t = line.trim()
    if (!t.startsWith('|')) continue
    if (/^[\s|:\-]+$/.test(t)) continue
    t = t.replace(/!\[[^\]]*\]\([^)]+\)/g, '')
    for (const p of t.replace(/^\||\|$/g, '').split('|').map((c) => c.trim())) {
      if (!p) continue
      if (SUPPLY_HEADER_WORDS.has(p) || /^金额\s*\(¥\)$/.test(p)) continue
      if (p === '序号' || p === '风险说明') continue
      cells.push(p)
    }
  }
  return cells
}

function looksLikeSupplierName(s) {
  if (/CCL-|PCB-|FR-?\d|PP-|HIGH-?TG|¥|%|^\d|交期|库存/.test(s)) return false
  return /板多多|1688工业|阿里巴巴|立创|华强|得捷|SUP-/.test(s)
}

/** 重建竖切表头的供应结构 / 空壳风险表 */
function repairFragmentedSupplyAndRiskTables(text) {
  let s = String(text || '')
  s = s.replace(/(\*\*供应结构\*\*)\s*\|/g, '$1\n\n|')
  s = s.replace(/(\*\*风险要点\*\*)\s*\|/g, '$1\n\n|')
  s = s.replace(/(\]\([^)]+\))\s*(\*\*风险要点\*\*)/g, '$1\n\n$2')

  s = s.replace(
    /\*\*供应结构\*\*\s*\n+([\s\S]*?)(?=\*\*风险|\n---\s*\n|\n## |\n### |$)/g,
    (full, body) => {
      const imgs = [...body.matchAll(/!\[[^\]]*\]\([^)]+\)/g)].map((m) => m[0])
      const bodyWo = body.replace(/!\[[^\]]*\]\([^)]+\)/g, '')
      if (!isFragmentedPipeBlock(bodyWo) && !isFragmentedPipeBlock('**供应结构**\n' + bodyWo)) {
        return full
      }
      const cells = flattenPipeCells(bodyWo)
      const rows = []
      for (let i = 0; i < cells.length; ) {
        if (!looksLikeSupplierName(cells[i])) {
          i++
          continue
        }
        const name = cells[i++]
        const vals = []
        while (i < cells.length && vals.length < 5) {
          if (looksLikeSupplierName(cells[i])) break
          vals.push(cells[i++])
        }
        while (vals.length < 5) vals.push('-')
        rows.push([name, ...vals.slice(0, 5)])
      }
      if (!rows.length) return full
      let t = emitSupplyTable(rows)
      for (const img of imgs) t += `\n${img}\n`
      return t
    }
  )

  s = s.replace(
    /\*\*风险要点?\*\*\s*\n+([\s\S]*?)(?=\n---\s*\n|\n## |\n### |\n\*\*(?:供应结构|风险要点|关键数字)\*\*|$)/g,
    (full, body) => {
      const mangled =
        /^\d+[\.、]\s+/m.test(body) ||
        /^\d+[\.、]\s*\*\*[^*]*\|/m.test(body) ||
        /\|\s*\d+\s*\|[^|\n]*\*\*\s*$/m.test(body)
      const good = [...body.matchAll(/^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|/gm)]
      if (
        !mangled &&
        good.length &&
        good.every((m) => m[2].trim().length >= 12 && !m[2].includes('序号'))
      ) {
        return full
      }
      const imgs = [...body.matchAll(/!\[[^\]]*\]\([^)]+\)/g)].map((m) => m[0])
      let clean
      if (mangled || (good.length && good.some((m) => m[2].trim().length < 8))) {
        clean = riskItemsFromMangledBlock('**风险要点**\n' + body)
      } else {
        let prose = body.replace(/!\[[^\]]*\]\([^)]+\)/g, '')
        prose = prose.replace(/^\|[^\n]*$/gm, '')
        prose = prose.replace(/\n{2,}/g, '\n').trim()
        prose = prose.replace(/^(序号|风险说明)\s*/, '')
        if (!prose || prose.length < 8) return full

        let parts = prose
          .split(/(?:\s+|\n)+(?=\d+(?:[\.、]\s*|\s+)\*\*)/)
          .map((p) => p.trim())
          .filter(Boolean)
        if (parts.length < 2) parts = splitDashItems(prose)
        if (!parts.length) parts = [prose]

        clean = []
        for (let p of parts) {
          p = p
            .replace(/^\d+\s+/, '')
            .replace(/^\d+[\.、]\s*/, '')
            .replace(/\*\*([^*]+)\*\*/g, '$1')
            .replace(/\*\*/g, '')
            .trim()
          if (p.startsWith('|') || p === '序号' || p === '风险说明') continue
          if (p.length >= 6) clean.push(p)
        }
      }
      if (!clean.length) return full
      let t = emitRiskTable(clean)
      for (const img of imgs) t += `\n${img}\n`
      return t
    }
  )
  return s
}

/** 「1688价格优势|- 便宜约10%|」→ 数值归到 1688 列 */
function repairComparisonAdvantageRows(text) {
  return String(text || '')
    .split('\n')
    .map((line) => {
      const t = line.trim()
      if (!t.startsWith('|') || /^[\s|:\-]+$/.test(t)) return line
      const cells = t.replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
      if (cells.length < 2) return line
      const label = cells[0]
      // 仅处理「…价格优势」行，勿误伤趋势表里带「便宜」备注的 1688 行
      if (!/价格优势|(?<![/\w])优势$/.test(label)) return line
      if (!/1688|板多多|价格优势/.test(label)) return line
      let val = ''
      for (const v of cells.slice(1)) {
        if (!v || v === '-' || v === '—' || v === '–') continue
        val = v.replace(/^[-—–]\s*/, '').trim() || v
        break
      }
      if (!val) return line
      if (label.includes('1688')) return `| 价格优势 | - | ${cellSafe(val)} |`
      if (label.includes('板多多')) return `| 价格优势 | ${cellSafe(val)} | - |`
      return line
    })
    .join('\n')
}

/** ### 4.1 覆铜\\n\\n板供应商对比 → 合并 */
function fixSplitHeadings(text) {
  return String(text || '')
    .replace(/(#{2,3}\s+\d+(?:\.\d+)?\s*[^\n]*?覆铜)\s*\n+\s*(板[^\n]*)/g, '$1$2')
    .replace(/(#{2,3}\s+\d+(?:\.\d+)?\s*[^\n]*?半固)\s*\n+\s*(化片[^\n]*)/g, '$1$2')
}

/** `|交期（FR4）` + `|3天|2天|` → 同一行；丢掉误插假分隔行 */
function mergeIncompleteTableRows(text) {
  const lines = String(text || '').split('\n')
  const out = []
  for (let i = 0; i < lines.length; ) {
    const raw = lines[i]
    const t = raw.trim()
    if (t.startsWith('|') && !/^[\s|:\-]+$/.test(t)) {
      const cells = t.replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
      const incomplete =
        (cells.length === 1 && cells[0].length >= 2) || (!t.endsWith('|') && cells.length <= 2)
      if (incomplete) {
        let j = i + 1
        while (j < lines.length && !lines[j].trim()) j++
        const nxt = j < lines.length ? lines[j].trim() : ''
        if (nxt.startsWith('|') && !/^[\s|:\-]+$/.test(nxt) && !nxt.includes('对比项')) {
          const vals = nxt
            .replace(/^\||\|$/g, '')
            .split('|')
            .map((c) => c.trim())
            .filter(Boolean)
          if (
            vals.length &&
            vals.every((v) => v.length <= 28) &&
            !/^(供应商|物料|指标|序号)/.test(vals[0])
          ) {
            out.push(`| ${cellSafe(cells[0])} | ${vals.map(cellSafe).join(' | ')} |`)
            let k = j + 1
            while (k < lines.length && !lines[k].trim()) k++
            if (k < lines.length && /^\|[\s|:\-]+\|$/.test(lines[k].trim())) k++
            i = k
            continue
          }
        }
      }
    }
    out.push(raw)
    i++
  }
  return out.join('\n')
}

const METRIC_LABEL = /^(?:SKU|sku|累计|采购|订单|品类|排名|数量|金额|笔数|占比|总额|均价)/
const RISK_HINT = /库存|安全库存|替代|单源|交期|预警|近效期|缺料|涨幅|风险|无卤|集中/

/** 摘要误把风险塞进「指标|数值」→ 拆成指标表 + 风险要点表 */
function repairMetricsTableHoldingRisks(text) {
  let s = String(text || '').replace(
    /\|[ \t]*指标[ \t]*\|[ \t]*数值[ \t]*\|[ \t]*\n\|[-:| \t]+\|[ \t]*\n(?:\|[^\n]+\|\n?)+/g,
    (block) => {
      const rows = [...block.matchAll(/^\|([^\n]+)\|$/gm)].map((m) => m[1])
      if (rows.length < 2) return block
      const data = []
      for (const r of rows.slice(1)) {
        if (/^[\s|:\-]+$/.test(r.replace(/\|/g, ''))) continue
        const parts = r.split('|').map((c) => c.trim())
        if (parts.length < 2) continue
        const [a, b] = parts
        if (/^:?-{2,}:?$/.test(a) || a === '指标' || a === '数值') continue
        data.push([a, b])
      }
      if (!data.length) return block

      const metrics = []
      const risks = []
      for (const [a, b] of data) {
        if (/^\d+$/.test(a) && b.length >= 12) {
          risks.push(b)
          continue
        }
        if (/^\d+$/.test(b) && a.length >= 12) {
          risks.push(a)
          continue
        }
        if ((b === '---' || b === '—' || b === '-' || b === '------') && a.length >= 8) {
          risks.push(a)
          continue
        }
        if (METRIC_LABEL.test(a) && a.length <= 20 && b.length <= 40) {
          metrics.push([a, b])
          continue
        }
        if (RISK_HINT.test(a) || RISK_HINT.test(b)) {
          risks.push(a.length >= b.length ? a : b)
          continue
        }
        if (a.length <= 16 && b.length <= 24 && !RISK_HINT.test(a + b)) metrics.push([a, b])
        else risks.push(a.length >= b.length ? a : b)
      }
      if (risks.length < 1) return block

      const out = []
      if (metrics.length) {
        out.push('| 指标 | 数值 |', '|------|------|')
        for (const [lab, val] of metrics) out.push(`| ${cellSafe(lab)} | ${cellSafe(val)} |`)
        out.push('')
      }
      out.push('**风险要点**', '', '| 序号 | 风险说明 |', '|------|----------|')
      risks.forEach((desc, i) => out.push(`| ${i + 1} | ${cellSafe(desc)} |`))
      out.push('')
      return out.join('\n')
    }
  )

  // 风险表后掉队的涨价/交期说明 → 并入下一序号
  s = s.replace(
    /(\*\*风险要点\*\*\s*\n+(?:\|[^\n]+\n)+)\n+([^\n|#>][^\n]{20,}(?:涨幅|上行|交期|库存|单源)[^\n]*)\n/g,
    (full, block, orphan) => {
      const t = orphan.trim()
      if (t.length < 12 || t.startsWith('|') || t.startsWith('#')) return full
      const nums = [...block.matchAll(/^\|\s*(\d+)\s*\|/gm)].map((m) => Number(m[1]))
      const n = (nums.length ? nums[nums.length - 1] : 0) + 1
      return `${block.replace(/\n+$/, '')}\n| ${n} | ${cellSafe(t)} |\n\n`
    }
  )
  return s
}

/** 摘要有体量数字但缺 KPI 表时，从首段补一张「指标|数值」 */
function ensureSummaryKpiTable(text) {
  return String(text || '').replace(
    /(##\s*一、摘要\s*\n+)([\s\S]*?)(?=\n\*\*风险要点\*\*|\n\*\*供应结构\*\*|\n##\s)/,
    (full, head, body) => {
      if (/\|[ \t]*指标[ \t]*\|/.test(body)) return full
      const prose = body.trim()
      const rows = []
      const sku = prose.match(/(\d+)\s*个\s*SKU|共\s*(\d+)\s*个\s*SKU|覆盖\s*\*\*?(\d+)\s*个/i)
      const orders = prose.match(/累计\s*(\d+)\s*笔|(\d+)\s*笔订单/)
      const amt = prose.match(/金额\s*¥\s*([\d,]+)|¥\s*([\d,]+)/)
      const share = prose.match(/占总采购额\s*([\d.]+%)/)
      const rank = prose.match(/第\s*([一二三四五六七八九十\d]+)\s*大|排名\s*\*\*?第\s*(\d+)/)
      if (sku) rows.push(['SKU 数', sku[1] || sku[2] || sku[3]])
      if (orders) rows.push(['订单笔数', orders[1] || orders[2]])
      if (amt) rows.push(['累计采购金额', `¥${amt[1] || amt[2]}`])
      if (share) rows.push(['占总采购额', share[1]])
      if (rank) rows.push(['品类地位', `第${rank[1] || rank[2]}大采购品类`])
      if (rows.length < 2) return full
      let t = `${head}${prose}\n\n| 指标 | 数值 |\n|------|------|\n`
      for (const [a, b] of rows) t += `| ${cellSafe(a)} | ${cellSafe(b)} |\n`
      t += '\n'
      return t
    }
  )
}

const ACTION_PRI_WORD = '(?:紧急|高|中|低)'
// 必须用 unicode 码点匹配，禁止无 u 标志的代理对字符类（会匹配半个 emoji → �）
const ACTION_EMOJI = '[\\u{1F534}\\u{1F7E1}\\u{1F7E2}\\u{1F7E0}]'
const QUICK_CHANNEL =
  '(?:立创商城|华强电子网|得捷电子(?:\\s*Digi-Key)?|Digi-Key(?:（[^）]+）)?(?:\\+立创)?|板多多|1688(?:工业品)?|暂无渠道(?:（[^）]+）)?)'

function blankish(c) {
  const t = String(c || '').trim()
  return !t || t === '-' || t === '—' || t === '–' || t === '|||' || t === '\uFFFD' || t === '�'
}

/** 行动表优先级只保留文字，禁止 emoji（前端易显示为 �） */
function normalizeActionPriority(pri) {
  const raw = String(pri || '')
  for (const label of ['紧急', '高', '中', '低']) {
    if (raw.includes(label)) return label
  }
  if (/🔴|\u{1F534}/u.test(raw)) return '紧急'
  if (/🟢|\u{1F7E2}/u.test(raw)) return '低'
  if (/🟡|\u{1F7E1}|🟠|\u{1F7E0}/u.test(raw)) return '中'
  return raw
    .replace(/[🔴🟡🟢🟠⚠️\uFFFD]/gu, '')
    .replace(/[\uD800-\uDFFF]/g, '')
    .trim() || '-'
}

function cleanActionBody(body) {
  return String(body || '')
    .replace(/\uFFFD/g, '')
    .replace(/[\uD800-\uDFFF]/g, '')
    .replace(/^[🔴🟡🟢🟠⚠️]+\s*(?:紧急|高|中|低)?\s*/u, '')
    .replace(/^[—\-\s]+|[—\-\s]+$/g, '')
    .trim()
}


function parseActionPipeRows(block) {
  const rows = []
  for (const line of block) {
    const t = line.trim()
    if (!t.startsWith('|') || /^\|[\s|:\-]+\|$/.test(t)) continue
    const cells = t.replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
    if (!cells.length || cells[0] === '序号' || cells[0].includes('事项')) continue
    if (!/^\d+$/.test(cells[0] || '')) continue
    while (cells.length < 4) cells.push('')
    rows.push(cells.slice(0, 4))
  }
  return rows
}

function extractMashedActionItems(prose) {
  let s = String(prose || '').trim()
  if (!s) return []
  s = s.split(/(?=###|\n\s*---\s*$)/)[0].trim()
  s = s.replace(/[|]+/g, ' ').replace(/-{3,}/g, ' ').replace(/\s+/g, ' ')
  const items = []
  const markRe = new RegExp(
    `(?:(?<=\\s)|^)(\\d{1,2})\\.?\\s+(.+?)\\s+(${ACTION_EMOJI})\\s*(${ACTION_PRI_WORD})?`,
    'gu'
  )
  const marks = [...s.matchAll(markRe)]
  const prefix = marks.length ? s.slice(0, marks[0].index).trim() : s
  if (prefix) {
    const lm = prefix.match(new RegExp(`^(${ACTION_EMOJI})\\s*(${ACTION_PRI_WORD})?\\s*(.*)$`, 'u'))
    if (lm) {
      const pri = normalizeActionPriority(lm[2] ? `${lm[1]} ${lm[2]}` : lm[1])
      const body = cleanActionBody(lm[3] || '')
      if (body) items.push(['1', '', pri, body])
    }
  }
  for (let i = 0; i < marks.length; i++) {
    const m = marks[i]
    const end = i + 1 < marks.length ? marks[i + 1].index : s.length
    const body = cleanActionBody(s.slice(m.index + m[0].length, end))
    const pri = normalizeActionPriority(m[4] ? `${m[3]} ${m[4]}` : m[3])
    items.push([m[1], m[2].trim().replace(/\.$/, ''), pri, body])
  }
  return items
}

function mergeActionRowDicts(tableRows, spilled) {
  const byN = {}
  for (const r of tableRows) byN[r[0]] = [...r]
  for (const [n, title, pri, body] of spilled) {
    if (byN[n]) {
      const old = byN[n]
      byN[n] = [
        n,
        blankish(old[1]) ? title : old[1],
        blankish(old[2]) ? pri : old[2],
        blankish(old[3]) ? body : old[3],
      ]
    } else {
      byN[n] = [n, title, pri, body]
    }
  }
  return Object.keys(byN)
    .sort((a, b) => (Number(a) || 999) - (Number(b) || 999))
    .map((k) => {
      const [n, title, pri, body] = byN[k]
      if (blankish(title) && blankish(body)) return null
      return [n, title || '-', pri || '-', body || '-']
    })
    .filter(Boolean)
}

function emitActionTable(rows) {
  let t = '| 序号 | 事项 | 优先级 | 建议 |\n| ------ | ------ | ------ | ------ |\n'
  for (const [n, title, pri, body] of rows) {
    t += `| ${n} | ${cellSafe(title)} | ${cellSafe(normalizeActionPriority(pri))} | ${cellSafe(cleanActionBody(body))} |\n`
  }
  return t
}

function parseQuickcheckRowsFromBody(body) {
  let raw = String(body || '').trim()
  raw = raw.replace(/^场景\s+推荐渠道\s+理由\s+(?:-{2,}[ \t]*)+/, '')
  raw = raw.replace(/[|]+/g, ' ').replace(/-{3,}/g, ' ').replace(/\s+/g, ' ').trim()
  if (!raw) return []
  const marks = [...raw.matchAll(/\*\*([^*]+)\*\*/g)]
  const rows = []
  let i = 0
  while (i < marks.length) {
    const scene = marks[i][1].trim()
    const start = marks[i].index + marks[i][0].length
    if (i + 1 < marks.length && !raw.slice(start, marks[i + 1].index).trim()) {
      const channel = marks[i + 1][1].trim()
      const end = i + 2 < marks.length ? marks[i + 2].index : raw.length
      const reason = raw.slice(marks[i + 1].index + marks[i + 1][0].length, end).trim()
      if (scene && channel) rows.push([scene, channel, reason || '-'])
      i += 2
      continue
    }
    const end = i + 1 < marks.length ? marks[i + 1].index : raw.length
    const rest = raw.slice(start, end).trim()
    const cm = rest.match(new RegExp(`^(${QUICK_CHANNEL})\\s+(.+)$`))
    if (cm) rows.push([scene, cm[1].trim(), cm[2].trim()])
    i += 1
  }
  return rows
}

function repairSelectionQuickcheck(text) {
  let s = String(text || '').replace(/([^\n#])(#{1,3}\s*选型建议速查)/g, '$1\n\n$2')
  s = s.replace(/^(#{1,3})(选型建议速查)/gm, '$1 $2')
  return s.replace(
    /(#{1,3}\s*选型建议速查)\s*([\s\S]*?)(?=\n---\s*\n|\n##\s|\n###\s(?!选型)|\Z)/g,
    (full, heading, body) => {
      const h = heading.replace(/^(#{1,3})\s*/, '$1 ').trim()
      if (/^\|\s*场景\s*\|/m.test(body) && (body.match(/\n/g) || []).length >= 3) return full
      const rows = parseQuickcheckRowsFromBody(body)
      if (rows.length < 2) return full
      let table = '| 场景 | 推荐渠道 | 理由 |\n| ------ | ------ | ------ |\n'
      for (const [a, b, c] of rows) {
        table += `| ${cellSafe(a)} | ${cellSafe(b)} | ${cellSafe(c)} |\n`
      }
      return `${h}\n\n${table}\n`
    }
  )
}

function repairActionTableSpill(text) {
  const lines = String(text || '').split('\n')
  const out = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (line.trim().startsWith('|') && line.includes('序号') && line.includes('事项') && line.includes('优先级')) {
      const block = [line]
      i += 1
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        block.push(lines[i])
        i += 1
      }
      while (i < lines.length && !lines[i].trim()) i += 1
      const spillParts = []
      while (i < lines.length) {
        const raw = lines[i]
        const t = raw.trim()
        if (/^##\s/.test(t) || /^---\s*$/.test(t)) break
        if (t.startsWith('是否需要将此报告下载')) break
        if (/^#{1,3}\s*选型建议速查/.test(t) || (t.includes('选型建议速查') && !t.startsWith('|'))) {
          if (t.startsWith('#')) {
            lines[i] = t.replace(/^(#{1,3})\s*选型建议速查/, '$1 选型建议速查')
          } else {
            const idx = raw.indexOf('选型建议速查')
            const pre = raw.slice(0, idx).replace(/#+$/, '').trimEnd()
            if (pre.trim()) spillParts.push(pre)
            lines[i] = '### 选型建议速查' + raw.slice(idx + '选型建议速查'.length)
          }
          break
        }
        if (t.startsWith('|')) {
          const cells = t.replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
          if (cells.length >= 6 || cells.some((c) => c.includes('选型'))) {
            spillParts.push(cells.filter(Boolean).join(' '))
            i += 1
            while (i < lines.length && lines[i].trim().startsWith('|')) {
              const ct = lines[i].trim()
              if (/^\|[\s|:\-]+\|$/.test(ct)) {
                i += 1
                continue
              }
              const cc = ct.replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
              spillParts.push(cc.filter((c) => c && c !== '-').join(' '))
              i += 1
            }
            continue
          }
          break
        }
        spillParts.push(raw)
        i += 1
      }
      const spill = spillParts.join('\n').trim()
      const rows = parseActionPipeRows(block)
      const incomplete = rows.length ? rows.some((r) => blankish(r[2]) || blankish(r[3])) : true
      const hasMashed =
        new RegExp(`\\d+\\.?\\s+\\S.{0,40}\\s+${ACTION_EMOJI}`, 'u').test(spill) ||
        new RegExp(`^${ACTION_EMOJI}`, 'u').test(spill)
      if (rows.length && (incomplete || rows.length < 2) && hasMashed) {
        const merged = mergeActionRowDicts(rows, extractMashedActionItems(spill))
        if (merged.length >= 2) {
          out.push(emitActionTable(merged).replace(/\n$/, ''))
          out.push('')
          continue
        }
      }
      out.push(...block)
      if (spillParts.length) {
        out.push('')
        out.push(...spillParts)
      }
      continue
    }
    out.push(line)
    i += 1
  }
  return out.join('\n')
}

function scrubActionPriorityCells(text) {
  const lines = String(text || '').split('\n')
  const out = []
  let inAction = false
  for (const line of lines) {
    const t = line.trim()
    if (t.startsWith('|') && t.includes('序号') && t.includes('事项') && t.includes('优先级')) {
      inAction = true
      out.push(line)
      continue
    }
    if (inAction) {
      if (!t.startsWith('|')) {
        inAction = false
        out.push(line)
        continue
      }
      if (/^\|[\s|:\-]+\|$/.test(t)) {
        out.push(line)
        continue
      }
      const m = t.match(/^\|\s*(\d+)\s*\|\s*([^|]*)\|\s*([^|]*)\|\s*([^|]*)\|?\s*$/)
      if (m) {
        const [, n, title, pri, body] = m
        out.push(
          `| ${n} | ${cellSafe(title.trim())} | ${cellSafe(normalizeActionPriority(pri))} | ${cellSafe(cleanActionBody(body))} |`
        )
        continue
      }
    }
    out.push(line)
  }
  return out.join('\n')
}

function repairBrokenActionAndQuickcheck(text) {
  let s = String(text || '')
  s = s.replace(/([^\n#])(#{1,3}\s*选型建议速查)/g, '$1\n\n$2')
  s = s.replace(/^(#{1,6})([^\s#\n])/gm, '$1 $2')
  s = repairActionTableSpill(s)
  s = scrubActionPriorityCells(s)
  s = repairSelectionQuickcheck(s)
  return s
}

/** 结论行动表后漏掉的 `6 事项 🟢中 说明` 拉回表内 */
function repairOrphanActionRows(text) {
  const lines = String(text || '').split('\n')
  const out = []
  for (let i = 0; i < lines.length; i++) {
    out.push(lines[i])
    const line = lines[i].trim()
    if (!/^\|\s*\d+\s*\|/.test(line)) continue
    const orphans = []
    let j = i + 1
    while (j < lines.length) {
      const t = lines[j].trim()
      if (!t) {
        j++
        if (orphans.length) break
        continue
      }
      if (t.startsWith('|') || t.startsWith('#') || t.startsWith('---') || t.startsWith('>')) break
      const m = t.match(/^(\d+)\.?\s+(?:\*\*)?(.+?)(?:\*\*)?\s+(🔴|🟡|🟢)\s*(紧急|高|中|低)?\s*(.*)$/u)
      if (!m) break
      const [, n, title, emoji, pri, body] = m
      const priS = normalizeActionPriority(pri ? `${emoji} ${pri}` : emoji)
      orphans.push(
        `| ${n} | ${cellSafe(title.trim())} | ${cellSafe(priS)} | ${cellSafe(cleanActionBody(body))} |`
      )
      j++
    }
    if (orphans.length) {
      const window = out.slice(-12).join('\n')
      if (window.includes('| 序号 |') && (window.includes('优先级') || window.includes('事项'))) {
        out.push(...orphans)
        i = j - 1
      }
    }
  }
  return out.join('\n')
}

export function formatReportLayout(text) {
  let s = String(text || '')
  s = mergeOrphanTableNameRows(s)
  s = repairSupplierAmountShareTables(s)
  s = repairOrderIntegrityTables(s)
  s = expandSupplyAndRiskBlocks(s)
  s = expandSupplierProfile(s)
  s = expandPriceTrendBlocks(s)
  s = expandConclusionActions(s)
  s = repairDashboardAndMonthlyTrend(s)
  s = auditAndRepairReport(s)
  // 表行与独立 --- 之间必须空行（幂等）
  s = s.replace(/(^\|[^\n]*\|)\n(---\s*$)/gm, '$1\n\n$2')
  return s
}

/** 价格趋势密文 → 渠道对比表 */
function extractDatePrices(segment) {
  const s = String(segment || '')
  let pts = [...s.matchAll(/(\d{4}-\d{2})\s*[：:]\s*¥\s*([\d.]+)/g)].map((m) => [m[1], m[2]])
  if (pts.length < 2) {
    pts = [...s.matchAll(/(\d{4}-\d{2})\s+¥\s*([\d.]+)/g)].map((m) => [m[1], m[2]])
  }
  return pts
}

function emitPriceTrendTable(heading, rows) {
  let t = `${String(heading).trim()}\n\n双渠道价格对比如下：\n\n| 规格 / 渠道 | 起点价 | 终点价 | 涨幅 | 备注 |\n|-------------|--------|--------|------|------|\n`
  for (const r of rows) t += `| ${r.map(cellSafe).join(' | ')} |\n`
  return t + '\n'
}

function parsePriceTrendRows(body) {
  body = String(body || '')
  const bddSeg = body.split(/高\s*TG|1688/)[0]
  let pts = extractDatePrices(bddSeg)
  if (pts.length < 2) pts = extractDatePrices(body)
  let bddPct = body.match(/累计涨幅\s*\*?\*?约?\s*([\d.]+%)/)
  if (!bddPct) {
    bddPct = body.match(/(?:板多多|FR4\s*1\.6mm)[^。\n]{0,80}?涨幅\s*\*?\*?约?\s*([\d.]+%)/)
  }
  const annual = body.match(/年均约?\s*([\d.]+%)/)
  let s1688 = body.match(/1688[^\n]{0,80}?¥\s*([\d.]+)[^\n]{0,40}?¥\s*([\d.]+)/)
  if (!s1688) s1688 = body.match(/1688[^\n]{0,50}?从\s*¥\s*([\d.]+)\s*涨至\s*¥\s*([\d.]+)/)
  const s1688Pct = body.match(/1688[^\n]{0,120}?涨幅\s*\*?\*?约?\s*([\d.]+%)/)
  const cheap = body.match(/便宜\s*约?\s*([\d.\-~～]+%?)/)
  const tg = body.match(/高\s*TG[^。\n]{0,50}?¥\s*([\d.]+)\s*[~～\-至到]\s*¥?\s*([\d.]+)/)

  const rows = []
  if (pts.length >= 2) {
    const [sd, sp] = pts[0]
    const [ed, ep] = pts[pts.length - 1]
    let note = annual ? `年均约${annual[1]}` : ''
    if (pts.length >= 3) note = (note ? note + '；' : '') + `中段 ${pts[1][0]} ¥${pts[1][1]}`
    rows.push([
      'FR4 1.6mm · 板多多',
      `¥${sp}（${sd}）`,
      `¥${ep}（${ed}）`,
      bddPct ? `**${bddPct[1]}**` : '-',
      note || '18个月稳步上行',
    ])
  } else {
    let loose = body.match(
      /(?:板多多|FR4\s*1\.6mm)[^¥\n]{0,40}¥\s*([\d.]+)[^¥\n]{0,40}¥\s*([\d.]+)[^。\n]{0,40}?涨幅\s*\*?\*?约?\s*([\d.]+%)/
    )
    if (!loose) {
      loose = body.match(
        /价格从\s*约?\s*¥\s*([\d.]+)[^¥\n]{0,40}¥\s*([\d.]+)[^。\n]{0,40}?涨幅\s*\*?\*?约?\s*([\d.]+%)/
      )
    }
    if (loose) {
      rows.push([
        'FR4 1.6mm · 板多多',
        `¥${loose[1]}`,
        `¥${loose[2]}`,
        `**${loose[3]}**`,
        annual ? `年均约${annual[1]}` : '18个月稳步上行',
      ])
    }
  }
  if (s1688) {
    rows.push([
      'FR4 1.6mm · 1688',
      `¥${s1688[1]}`,
      `¥${s1688[2]}`,
      s1688Pct ? `**${s1688Pct[1]}**` : '-',
      cheap ? `仍比板多多便宜约 ${cheap[1]}` : '价低于板多多',
    ])
  }
  if (tg) {
    rows.push(['高TG覆铜板', `¥${tg[1]}`, `¥${tg[2]}`, '相对稳定', '-'])
  }
  return rows
}

export function expandPriceTrendBlocks(text) {
  let s = String(text || '').replace(
    /(#{2,3}\s+\d+\.\d+\s+[^\n]{0,40}?(?:价格趋势|价格走势|采购额变化))(?=FR|覆铜板与|板多多|高\s*TG|CCL|[A-Za-z0-9])/g,
    '$1\n\n'
  )
  return s.replace(
    /(#{2,3}\s+[^\n]*(?:价格趋势|价格走势)[^\n]*)\n+([\s\S]*?)(?=\n#{2,3}\s+|\n---\s*\n|$)/g,
    (full, heading, body) => {
      if (!body.includes('¥') && !body.includes('涨幅') && !body.includes('价格')) return full

      const tableRows = looksLikeTable(body)
        ? String(body)
            .split('\n')
            .map((line) => {
              const t = line.trim()
              if (!t.startsWith('|') || /^[\s|:\-]+$/.test(t)) return null
              const cells = t
                .replace(/^\|/, '')
                .replace(/\|$/, '')
                .split('|')
                .map((c) => c.trim())
              if (cells.length < 4 || cells[0].includes('规格')) return null
              if (/^:?-{2,}/.test(cells[0].replace(/\s/g, ''))) return null
              while (cells.length < 5) cells.push('-')
              return [cells[0], cells[1], cells[2], cells[3], cells[4]]
            })
            .filter(Boolean)
        : []
      const hasBdd = tableRows.some((r) => r[0].includes('板多多'))
      if (tableRows.length >= 2 && hasBdd) return full

      let parsed = parsePriceTrendRows(body)
      if (tableRows.length && !hasBdd) parsed = parsePriceTrendRows(s)
      const byKey = {}
      const keyOf = (name) => {
        if (name.includes('板多多')) return 'bdd'
        if (name.includes('1688')) return '1688'
        if (name.replace(/\s/g, '').includes('高TG')) return 'tg'
        return name
      }
      for (const group of [tableRows, parsed]) {
        for (const r of group) {
          const k = keyOf(r[0])
          const prev = byKey[k]
          if (!prev) byKey[k] = r
          else if (!prev[1].includes('（20') && r[1].includes('（20')) byKey[k] = r
        }
      }
      const rows = ['bdd', '1688', 'tg'].filter((k) => byKey[k]).map((k) => byKey[k])
      for (const [k, r] of Object.entries(byKey)) {
        if (!['bdd', '1688', 'tg'].includes(k)) rows.push(r)
      }
      if (!rows.length) return full
      return emitPriceTrendTable(heading, rows)
    }
  )
}
