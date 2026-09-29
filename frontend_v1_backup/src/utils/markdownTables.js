/**
 * MyResearcher · Markdown 表格规范化（轻量版）
 *
 * 只做 GFM 表格的健壮性修正：
 *  - 表格前后补空行（markdown-it 需要）
 *  - 确保分隔行（| --- |）存在且格式合法
 *  - 标题前后补空行
 *
 * 不含采购助手那套重型报告/Dashboard 重整逻辑。
 */

/**
 * 规范化 Markdown，重点修 GFM 表格结构。
 * @param {string} md
 * @returns {string}
 */
export function normalizeMarkdown(md) {
  if (!md || typeof md !== 'string') return md || ''
  let text = md
  text = ensureBlankLinesAroundTables(text)
  text = ensureTableSeparator(text)
  text = ensureBlankLinesAroundHeadings(text)
  return text
}

function isTableRow(line) {
  const t = line.trim()
  return t.includes('|')
}

function isTableSeparator(line) {
  const t = line.trim()
  return /^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?$/.test(t) || /^(\s*:?-+:?\s*\|)+\s*:?-+:?\s*$/.test(t)
}

function ensureBlankLinesAroundTables(text) {
  const lines = text.split('\n')
  const out = []
  let inTable = false
  let prevBlank = true
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const rowLike = isTableRow(line)
    if (rowLike && !inTable) {
      if (!prevBlank) out.push('')
      inTable = true
    } else if (!rowLike && inTable) {
      if (out.length && out[out.length - 1] !== '') out.push('')
      inTable = false
    }
    out.push(line)
    prevBlank = line.trim() === ''
  }
  if (inTable && out.length && out[out.length - 1] !== '') out.push('')
  return out.join('\n')
}

function ensureTableSeparator(text) {
  const lines = text.split('\n')
  const out = []
  let i = 0
  while (i < lines.length) {
    if (isTableRow(lines[i]) && !isTableSeparator(lines[i])) {
      const blockStart = i
      let j = i
      while (j < lines.length && isTableRow(lines[j])) j++
      const block = lines.slice(blockStart, j)
      if (block.length >= 2 && !isTableSeparator(block[1])) {
        const headerCols = countCols(block[0])
        block.splice(1, 0, makeSeparator(headerCols))
      }
      out.push(...block)
      i = j
    } else {
      out.push(lines[i])
      i++
    }
  }
  return out.join('\n')
}

function countCols(line) {
  const t = line.trim().replace(/^\||\|$/g, '')
  return Math.max(1, t.split('|').length)
}

function makeSeparator(cols) {
  return '| ' + Array(cols).fill('---').join(' | ') + ' |'
}

function ensureBlankLinesAroundHeadings(text) {
  return text
    .replace(/([^\n])\n(#{1,6}\s)/g, '$1\n\n$2')
    .replace(/(#{1,6}[^\n]*)\n([^\n#])/g, '$1\n\n$2')
}

/** 兼容旧 import */
export const reportTablesHealthy = () => true
