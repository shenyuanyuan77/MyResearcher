/**
 * 报告 Markdown 表整段重建：不依赖模型是否写对，脚本对齐列数后再输出标准 GFM。
 */

/** 仅整格匹配的「假首列标题」，禁止前缀误伤「对比维度」 */
const TITLE_CELL =
  /^(?:板)?(?:单价走势|供应商对比|双渠道比价|渠道对比|比价|走势|方案|清单|概览)$/

const SECTION_LABELS = [
  'MSL预警',
  '供应结构',
  '关键风险',
  '渠道分析',
  '供应商集中度风险',
  '关键发现',
  '行动建议',
]

/** 密集摘要/风险列表换行 */
export function fixDenseReportProse(text) {
  let s = String(text || '')
  for (const lab of SECTION_LABELS) {
    const re = new RegExp(`(?<![\\u4e00-\\u9fff*#])(${lab})(?![\\u4e00-\\u9fff])`, 'g')
    s = s.replace(re, '\n\n**$1**\n')
  }
  // 列表项：行首或正文中的「 -板多多」，绝不切开 CCL-FR4
  s = s.replace(/(^|\n)[ \t]*-[ \t]*(?=板多多|1688|覆铜板|半固化|阿里巴巴)/gm, '$1- ')
  s = s.replace(
    /([^\n|\-A-Za-z0-9])[ \t]+-[ \t]*(?=板多多|1688|覆铜板|半固化|阿里巴巴)/g,
    '$1\n- '
  )
  s = s.replace(/([：:])\s*-\s*(?=\*\*)/g, '$1\n- ')
  s = s.replace(/([\u4e00-\u9fff])\s*-\s*(?=\*\*)/g, '$1\n- ')
  // 月度采购密文：…规律：-最高月：…-最低月：…-近期…
  s = s.replace(/(?<!\n)-\s*(?=最高月|最低月|近期[（(])/g, '\n- ')
  s = s.replace(/([^\n!\]])\s*(!\[[^\]]*\]\([^)]+\))/g, '$1\n\n$2')
  s = s.replace(/(\)\s*)---(?=\s*(?:\n|#|是否))/g, '$1\n\n---')
  s = s.replace(/([。！？])---(?=\s*(?:\n|#|是否))/g, '$1\n\n---')
  s = s.replace(/---(?=#{1,3})/g, '---\n\n')
  s = s.replace(
    /\*\*(供应结构|关键风险|渠道分析|MSL预警|供应商画像)\*\*[ \t]*[：:]?\s*/g,
    '**$1**\n\n'
  )
  return s
}

/**
 * 标题行里粘了表头：### 5.1 xxx比价|对比维度 |板多多|
 */
export function splitHeadingTables(text) {
  return String(text || '')
    .split('\n')
    .map((line) => {
      const m = line.match(/^(#{1,6}\s+)([^|#\n][^|\n]*?)(\|[^|\n]+(?:\|[^|\n]*)+\|?\s*)$/)
      if (!m) return line
      const [, hashes, title, tablePart] = m
      let header = tablePart.trim()
      if (!header.startsWith('|')) header = '|' + header
      if (!header.endsWith('|')) header += '|'
      return `${hashes}${title.trim()}\n\n${header}`
    })
    .join('\n')
}

/**
 * 扫描全文，把每一段 pipe 表重建为列数一致的标准 GFM
 */
export function rebuildPipeTables(text) {
  const lines = String(text || '').split('\n')
  const out = []
  let i = 0

  while (i < lines.length) {
    const block = findTableBlock(lines, i)
    if (!block) {
      out.push(lines[i])
      i++
      continue
    }

    const slice = lines.slice(block.start, block.end)
    if (!blockNeedsRebuild(slice)) {
      for (let k = block.start; k < block.end; k++) out.push(lines[k])
      i = block.end
      continue
    }

    const { title, header, rows, trailing } = normalizeTableBlock(slice)

    if (title) {
      out.push(title)
      out.push('')
    }
    if (header && header.length && rows.length) {
      const col = header.length
      out.push('|' + header.map(cleanCell).join('|') + '|')
      out.push('|' + Array(col).fill('---').join('|') + '|')
      for (const row of rows) {
        const cells = row.slice(0, col).map(cleanCell)
        while (cells.length < col) cells.push('')
        out.push('|' + cells.join('|') + '|')
      }
      out.push('')
    } else {
      for (let k = block.start; k < block.end; k++) out.push(lines[k])
    }
    for (const t of trailing) {
      if (t) out.push(t)
    }
    i = block.end
  }

  return out.join('\n').replace(/\n{3,}/g, '\n\n')
}

function cleanCell(c) {
  return String(c || '').replace(/\s+/g, ' ').trim()
}

function blockNeedsRebuild(blockLines) {
  const sepIdx = blockLines.findIndex(isSepLine)
  if (sepIdx < 0) return blockLines.length >= 2
  if (sepIdx >= 2) return true
  const headLine = sepIdx > 0 ? String(blockLines[sepIdx - 1] || '') : ''
  if (headLine.includes('|') && !headLine.trim().startsWith('|')) return true
  const header = sepIdx > 0 ? parseFlexibleRow(headLine, true).cells : []
  if (header[0] && TITLE_CELL.test(String(header[0]).replace(/\s/g, ''))) return true
  const sepCols = countSepColumns(blockLines[sepIdx])
  // 只用管道计数判断列数，避免 parse 时把长单元格当正文剥掉导致误重建
  const dataRows = blockLines
    .slice(sepIdx + 1)
    .map((l) => String(l || '').trim())
    .filter((l) => l.startsWith('|') && !isSepLine(l))
  const dataColCounts = dataRows.map(countPipeCols).filter((n) => n >= 2)
  if (!dataColCounts.length) return false
  const dataCols = mostCommon(dataColCounts)
  if (dataCols && sepCols && dataCols !== sepCols) return true
  if (dataCols && header.length && header.length !== dataCols) return true
  // 列数一致的健康表：原样保留
  if (
    dataCols >= 2 &&
    sepCols === dataCols &&
    (!header.length || header.length === dataCols) &&
    headLine.trim().startsWith('|')
  ) {
    return false
  }
  if (dataRows.some((l) => parseFlexibleRow(l, false).cells.some(isNarrativeCell))) return true
  return false
}

function countPipeCols(line) {
  let s = String(line || '').trim()
  if (!s.includes('|')) return 0
  if (s.startsWith('|')) s = s.slice(1)
  if (s.endsWith('|')) s = s.slice(0, -1)
  return s.split('|').length
}

function findTableBlock(lines, from) {
  if (!lines[from] || !String(lines[from]).trim()) return null

  let sepAt = -1
  for (let j = from; j < Math.min(lines.length, from + 10); j++) {
    if (!isSepLine(lines[j])) continue
    const prev = j > 0 ? String(lines[j - 1] || '') : ''
    const next = String(lines[j + 1] || '')
    if ((prev.includes('|') && !isSepLine(prev)) || next.includes('|')) {
      sepAt = j
      break
    }
  }

  if (sepAt >= 0) {
    let start = sepAt
    while (
      start > from &&
      String(lines[start - 1] || '').trim() &&
      String(lines[start - 1]).includes('|') &&
      !isSepLine(lines[start - 1])
    ) {
      start--
    }
    if (start !== from) return null

    let end = sepAt + 1
    while (end < lines.length) {
      const L = String(lines[end] || '')
      if (!L.trim()) break
      if (isSepLine(L)) break
      if (!L.includes('|')) break
      end++
    }
    if (end - start < 2) return null
    if (end === sepAt + 1 && start === sepAt) return null
    return { start, end, sepAt }
  }

  // 无分隔行：连续 ≥2 行管道数据 → 合成表
  if (!String(lines[from]).includes('|') || isSepLine(lines[from])) return null
  let end = from
  const colCounts = []
  while (end < lines.length) {
    const L = String(lines[end] || '')
    if (!L.trim() || !L.includes('|') || isSepLine(L)) break
    const cells = parseFlexibleRow(L, end === from).cells
    if (cells.length < 2) break
    colCounts.push(cells.length)
    end++
    if (end - from >= 15) break
  }
  if (end - from < 2) return null
  const cols = mostCommon(colCounts)
  if (cols < 2) return null
  return { start: from, end, sepAt: -1 }
}

function normalizeTableBlock(blockLines) {
  let sepIdx = blockLines.findIndex(isSepLine)
  const trailing = []
  let title = ''
  let header = []

  if (sepIdx < 0) {
    // 合成：第一行当表头（若像表头），否则用默认表头
    const all = blockLines.map((l, idx) => parseFlexibleRow(l, idx === 0))
    for (const p of all) {
      if (p.prefix) title = title || p.prefix
      if (p.prose) trailing.push(p.prose)
    }
    const rowsCells = all.map((p) => p.cells).filter((c) => c.length >= 2)
    const colCount = mostCommon(rowsCells.map((r) => r.length)) || rowsCells[0].length
    const first = rowsCells[0] || []
    const firstIsHeader =
      first.length === colCount &&
      first.every((c) => !/^[\d¥~.+\-]+%?$/.test(c) && !/^CCL-|^PCB-/i.test(c))

    if (firstIsHeader) {
      header = [...first]
      while (header.length && TITLE_CELL.test(header[0].replace(/\s/g, ''))) {
        title = title || header.shift()
      }
      return finish(header, rowsCells.slice(1), colCount, title, trailing)
    }
    header = defaultHeaders(colCount)
    return finish(header, rowsCells, colCount, title, trailing)
  }

  for (let h = 0; h < sepIdx; h++) {
    const parsed = parseFlexibleRow(blockLines[h], true)
    if (parsed.prefix) title = title || parsed.prefix
    header.push(...parsed.cells)
  }

  const rows = []
  for (let r = sepIdx + 1; r < blockLines.length; r++) {
    const parsed = parseFlexibleRow(blockLines[r], false)
    if (parsed.prose) trailing.push(parsed.prose)
    if (parsed.cells.length >= 2) rows.push(parsed.cells)
    else if (parsed.cells.length === 1 && parsed.cells[0].length > 20) {
      trailing.push(parsed.cells[0])
    }
  }

  const dataCols =
    mostCommon(rows.map((r) => r.length).filter((n) => n >= 2)) ||
    Math.max(0, ...rows.map((r) => r.length), 0)
  let colCount = dataCols || header.length || countSepColumns(blockLines[sepIdx])
  if (!colCount) {
    return { title, header: null, rows: [], trailing }
  }

  while (header.length && TITLE_CELL.test(String(header[0]).replace(/\s/g, ''))) {
    title = title || header[0]
    header = header.slice(1)
  }

  return finish(header, rows, colCount, title, trailing)
}

function finish(header, rows, colCount, title, trailing) {
  let h = [...(header || [])]
  if (h.length > colCount) h = h.slice(0, colCount)
  while (h.length < colCount) {
    const defs = defaultHeaders(colCount)
    h.push(defs[h.length] || '')
  }
  if (h.every((c) => !String(c).trim())) h = defaultHeaders(colCount)
  if (colCount === 2) {
    const inferred = inferPairHeaders(h.slice(0, 2))
    if (inferred) h = inferred
  }
  h = h.map((c) => (/^列\s*\d+$/.test(String(c || '').trim()) ? '' : c))
  if (colCount === 2 && (!String(h[0] || '').trim() || !String(h[1] || '').trim())) {
    const inferred = inferPairHeaders([h[0] || '', h[1] || ''])
    if (inferred) h = inferred
    else if (h.every((c) => !String(c).trim())) h = defaultHeaders(2)
    else {
      const defs = defaultHeaders(colCount)
      h = h.slice(0, colCount).map((c, i) => String(c || '').trim() || defs[i])
    }
  }

  const cleanRows = []
  const moreTrail = [...trailing]
  for (const r of rows) {
    let cells = [...r]
    if (cells.length) {
      const sp = splitTrailingProse(cells[cells.length - 1])
      if (sp.prose) {
        cells[cells.length - 1] = sp.cell
        moreTrail.push(sp.prose)
      }
    }
    if (cells.length > colCount) {
      const head = cells.slice(0, colCount - 1)
      const rest = cells.slice(colCount - 1).join(' ')
      const sp = splitTrailingProse(rest)
      cells = head.concat([sp.cell || rest])
      if (sp.prose) moreTrail.push(sp.prose)
    }
    while (cells.length < colCount) cells.push('')
    cleanRows.push(cells.slice(0, colCount))
  }

  return {
    title,
    header: h,
    rows: cleanRows,
    trailing: [...new Set(moreTrail.map((t) => t.trim()).filter(Boolean))],
  }
}

function parseFlexibleRow(line, isHeader) {
  let s = String(line || '').trim()
  let prefix = ''
  let prose = ''

  if (!s.includes('|')) return { prefix: '', cells: [], prose: s }

  if (!s.startsWith('|')) {
    const idx = s.indexOf('|')
    prefix = s.slice(0, idx).trim()
    s = s.slice(idx)
  }
  if (!s.endsWith('|')) s += '|'

  let cells = s
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((c) => c.trim())

  if (
    prefix &&
    (TITLE_CELL.test(prefix.replace(/\s/g, '')) || /对比$|比价$|走势$|方案$/.test(prefix))
  ) {
    // title prefix
  } else if (prefix) {
    cells = [prefix, ...cells]
    prefix = ''
  }

  const LABEL_ROW =
    /^(对比项|角色|金额占比|覆盖物料|交期|信用|优势与风险|优势\s*\/\s*风险|供应商|物料|序号|事项|优先级|建议)$/
  if (!isHeader && cells[0] && LABEL_ROW.test(cells[0])) {
    return { prefix, cells, prose: '' }
  }

  if (!isHeader) {
    for (let i = 0; i < cells.length; i++) {
      if (isNarrativeCell(cells[i])) {
        prose = cells.slice(i).join(' ').trim()
        cells = cells.slice(0, i)
        break
      }
    }
  }

  return { prefix, cells, prose }
}

function isNarrativeCell(c) {
  const t = String(c || '')
  if (t.length < 36) return false
  if (/渠道分析|集中度风险|供应核心|独家供应|不能完全依赖|板多多供应/.test(t)) return true
  if ((t.match(/[。；]/g) || []).length >= 2) return true
  return false
}

function splitTrailingProse(cell) {
  const t = String(cell || '')
  const m = t.match(/^(.*?)((?:板多多供应|渠道分析|供应商集中度|阿里巴巴1688).+)$/)
  if (m && m[2].length > 15) {
    return { cell: m[1].trim(), prose: m[2].trim() }
  }
  if (isNarrativeCell(t)) return { cell: '', prose: t }
  return { cell: t, prose: '' }
}

function isSepLine(line) {
  const s = String(line || '').trim()
  if (!s.includes('-')) return false
  return /^[\s|:\-]+$/.test(s) && /-{2,}/.test(s) && (s.match(/\|/g) || []).length >= 1
}

function countSepColumns(line) {
  const s = String(line || '').trim()
  const parts = s.replace(/^\|/, '').replace(/\|$/, '').split('|')
  return parts.filter((p) => /-{2,}/.test(p)).length || parts.length
}

function mostCommon(arr) {
  if (!arr.length) return 0
  const map = new Map()
  for (const n of arr) map.set(n, (map.get(n) || 0) + 1)
  let best = arr[0]
  let bestC = 0
  for (const [n, c] of map) {
    if (c > bestC || (c === bestC && n > best)) {
      best = n
      bestC = c
    }
  }
  return best
}

function defaultHeaders(n) {
  if (n === 2) return ['项目', '内容']
  if (n === 3) return ['项目', '数值', '备注']
  if (n === 4) return ['对比维度', '主供', '备选', '差异']
  if (n === 5) return ['供应商', '角色', '金额', '占比', '状态']
  if (n === 6) return ['物料', '最低价', '最高价', '均价', '基准价', '偏离']
  if (n === 7) return ['供应商', '角色', '评级', '金额', '占比', '交期', '状态']
  return Array.from({ length: n }, (_, i) => `字段${i + 1}`)
}

function inferPairHeaders(cells) {
  if (!cells || cells.length !== 2) return null
  let a = String(cells[0] || '').trim()
  let b = String(cells[1] || '').trim()
  if (/^(?:列|字段)\s*\d+$/.test(a)) a = ''
  if (/^(?:列|字段)\s*\d+$/.test(b)) b = ''
  const known = new Set([a, b].filter(Boolean))
  if (known.has('数值') || known.has('指标')) return ['指标', '数值']
  if (known.has('数量') || known.has('类型')) return ['类型', '数量']
  return null
}
