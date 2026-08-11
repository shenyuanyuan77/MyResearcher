import {
  fixDenseReportProse,
  splitHeadingTables,
  rebuildPipeTables,
} from './rebuildPipeTables.js'
import { formatReportLayout, mergeOrphanTableNameRows, detachMediaFromPipeTables, repairSupplierAmountShareTables, repairOrderIntegrityTables } from './reportLayout.js'
import { ensureBlankLineAfterTables } from './dashboardLayout.js'
import { reportTablesHealthy } from './reportTableCanon.js'

/**
 * 采购报告 / 助手 Markdown 全面重整。
 */

const PROSE_START =
  /^(?:>+\s*)?(需要进一步|需要查看|全部来自|全部|供应商统一|以上|综上|所有|备注|如果你|若需|覆盖|均符合|关键发现|期内)/

const NAME_LIKE =
  /^(?:[0-9一二三四五六七八九十]+层|铝基|铜基|FR4|FR-?4|PCB|沉金|HDI|CCL|高TG|半固化)/i

const MPN_LIKE = /^(?:PCB|ALPCB|CCL|IC|R|C|L|FR4|LOT)[-_A-Z0-9]/i

/** 对外主入口：渲染前 / 保存前调用。健康终态直接返回，避免越修越坏。 */
export function normalizeMarkdown(text) {
  if (!text) return text
  const raw = String(text).replace(/\u00a0/g, ' ')
  if (reportTablesHealthy(raw) && raw.includes('**供应结构**') && raw.includes('| 供应商 |')) {
    return raw.replace(/\n{3,}/g, '\n\n').trim()
  }
  let s = raw
  s = explodeDoublePipes(s)
  s = fixHeadingsAndStructure(s)
  s = fixMetaAndLists(s)
  s = s.replace(/^(#{1,6})([^\s#\n])/gm, '$1 $2')
  s = separateMediaAndBlocks(s)
  s = detachMediaFromPipeTables(s)
  s = splitHeadingTables(s)
  s = ensureTableStartsOnOwnLine(s)
  s = fixGluedTableHeaders(s)
  // 先修「挤成一行」的经典塌缩表
  s = fixMarkdownTables(s)
  s = fixDenseReportProse(s)
  // 先剥表尾粘连，再合并残行、再重建 —— 避免「供应结构」还在第三列时被建成假 3 列表
  s = peelGluedTableRowProse(s)
  s = peelTableCaptionAndFooter(s)
  s = mergeOrphanTableNameRows(s)
  // 供应商金额分布锯齿表：须在 rebuild 发明「项目|内容」之前纠正
  s = repairSupplierAmountShareTables(s)
  s = repairOrderIntegrityTables(s)
  s = rebuildPipeTables(s)
  s = repairSupplierAmountShareTables(s)
  s = repairOrderIntegrityTables(s)
  s = fixSpaceSeparatedTables(s)
  s = peelGluedTableRowProse(s)
  s = peelTableCaptionAndFooter(s)
  s = breakTablesOnSectionIntrusions(s)
  s = collapseOrderDumpTables(s)
  s = formatReportLayout(s)
  s = detachMediaFromPipeTables(s)
  s = peelInlineNotes(s)
  s = dedupeRepeatedSections(s)
  s = trimAfterDownloadCta(s)
  s = ensureBlankLineAfterTables(s)
  s = s.replace(/^#{1,6}\s*$/gm, '')
  return s.replace(/\n{3,}/g, '\n\n').trim()
}

/**
 * 图、表、标题必须分块：禁止 `对比![图](url)|表头|` 挤在同一行（否则图和表头并排难读）。
 */
export function separateMediaAndBlocks(text) {
  let s = String(text || '')
  // 正文粘图片：对比![图](
  s = s.replace(/([^\n\s!])(!\[[^\]]*\]\()/g, '$1\n\n$2')
  // 图片后直接跟表头：](url)|物料|
  s = s.replace(/(\]\([^)\n]+\))\s*(\|(?=[^|\n]*\|))/g, '$1\n\n$2')
  // 图片后列表 / 分隔 / 标题
  s = s.replace(/(\]\([^)\n]+\))\s*(-\s+)/g, '$1\n\n$2')
  s = s.replace(/(\]\([^)\n]+\))\s*(---)/g, '$1\n\n$2')
  s = s.replace(/(\]\([^)\n]+\))\s*(#{1,3}\s)/g, '$1\n\n$2')
  // 标题粘图片：### 5.2 小结![图]
  s = s.replace(/^(#{1,6}[^\n!]+?)(!\[[^\]]*\]\()/gm, '$1\n\n$2')
  return s
}

/**
 * 表行里塞进下一节标题（如 `|###月度价格…|订单日期|`）→ 拆表并恢复标题。
 */
export function breakTablesOnSectionIntrusions(text) {
  const lines = String(text || '').split('\n')
  const out = []
  let inTable = false

  const flushIntrusion = (cells) => {
    const first = String(cells[0] || '').trim()
    if (
      !/^#{1,3}/.test(first) &&
      !/(?:月度价格走势|成交价趋势)/.test(first) &&
      !first.includes('###')
    ) {
      return false
    }
    const cleaned = first.replace(/^#+\s*/, '').replace(/\*\*/g, '').trim()
    const title = cleaned.split(/：|:/)[0].trim() || '补充说明'
    const afterColon = cleaned.split(/：|:/).slice(1).join('：').trim()
    out.push('')
    out.push('### ' + title)
    const maybeHeader = cells.slice(1).filter((c) => c && !/^-+$/.test(c))
    if (
      maybeHeader.length >= 2 &&
      maybeHeader.every((c) => c.length < 20) &&
      /日期|数量|单价|金额|订单/.test(maybeHeader.join(''))
    ) {
      out.push('')
      out.push('|' + maybeHeader.join('|') + '|')
    } else if (afterColon) {
      out.push('')
      out.push(afterColon)
    } else if (maybeHeader.length) {
      out.push('')
      out.push(maybeHeader.join(' '))
    }
    out.push('')
    return true
  }

  for (const line of lines) {
    const trimmed = line.trim()
    const isSep = /^\|(?:[ \t]*:?-{1,}:?[ \t]*\|)+$/.test(trimmed)
    const isPipe = /^\|/.test(trimmed) && (trimmed.match(/\|/g) || []).length >= 2

    if (isSep) {
      inTable = true
      out.push(line)
      continue
    }
    if (inTable && isPipe) {
      let body = trimmed
      if (body.startsWith('|')) body = body.slice(1)
      if (body.endsWith('|')) body = body.slice(0, -1)
      const cells = body.split('|').map((c) => c.trim())
      const first = cells[0] || ''
      const intrusionAt = cells.findIndex(
        (c) =>
          /^#{1,3}/.test(c) ||
          /(?:月度价格走势|成交价趋势)/.test(c) ||
          (c.includes('###') && c.length > 8) ||
          /\*\*[^*]*成交价趋势\*\*/.test(c)
      )
      if (intrusionAt >= 0) {
        inTable = false
        // 入侵前的半截行若含价格，可丢弃或并入说明
        flushIntrusion(cells.slice(intrusionAt))
        continue
      }
      out.push(line)
      continue
    }
    if (inTable && trimmed && !isPipe) {
      inTable = false
    }
    out.push(line)
  }
  return out.join('\n')
}

/**
 * 塌缩的 Order# 流水表改为大白话区间；若后文已有「趋势研判」则直接删掉密表。
 */
export function collapseOrderDumpTables(text) {
  const lines = String(text || '').split('\n')
  const out = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    const looksHeader =
      /^\|/.test(line.trim()) && /订单日期|成交单价|数量\s*\(/.test(line)
    const looksOrder = /Order#\s*\d+/i.test(line)
    if (looksHeader || looksOrder) {
      const start = i
      // 向上吞掉空的残缺表头
      let j = i
      const block = []
      while (j < lines.length) {
        const L = lines[j]
        const t = L.trim()
        if (
          /Order#\s*\d+/i.test(L) ||
          (t.startsWith('|') &&
            (/订单日期|成交单价|数量\s*\(/.test(t) ||
              /^\|[-:\s|]+\|$/.test(t) ||
              (/\d+\.\d{2}/.test(t) && block.length > 0)))
        ) {
          block.push(L)
          j++
          continue
        }
        // 半截粘连行：|92.69|Order#...
        if (t.startsWith('|') && /Order#|\d+\.\d{2}/.test(t) && block.length >= 2) {
          block.push(L)
          j++
          continue
        }
        break
      }
      const orderHits = block.filter((b) => /Order#/i.test(b)).length
      if (orderHits >= 2 || (looksHeader && orderHits >= 1 && block.length >= 3)) {
        const prices = []
        for (const b of block) {
          for (const m of b.matchAll(/(?<![\d.])(\d{2,3}\.\d{2})(?![\d.])/g)) {
            const v = Number(m[1])
            if (v >= 20 && v <= 500) prices.push(v)
          }
        }
        const ahead = lines.slice(j, j + 6).join('\n')
        const hasJudgement = /趋势研判|从\s*~?¥|涨至|升到/.test(ahead)
        if (!hasJudgement && prices.length >= 2) {
          const lo = Math.min(...prices)
          const hi = Math.max(...prices)
          out.push(
            `用大白话概括：这段成交价大约从 ¥${lo.toFixed(2)} 到 ¥${hi.toFixed(2)}，逐笔订单不再展开。`
          )
          out.push('')
        }
        // 若上一行是空表头残留「|订单日期|...|」已在 block 里删掉
        // 清理 out 末尾刚写入的残缺表头（仅订单日期三列表头且无分隔）
        while (out.length) {
          const last = out[out.length - 1].trim()
          if (!last) {
            out.pop()
            continue
          }
          if (/^\|订单日期\|/.test(last) || /^\|[-:\s|]+\|$/.test(last)) {
            out.pop()
            continue
          }
          break
        }
        i = j
        continue
      }
      // 不够密，原样输出
      void start
    }
    out.push(line)
    i++
  }
  return out.join('\n')
}

/** |a|b||---|---| 或 |a||CCL-  → 强制换行 */
function explodeDoublePipes(text) {
  let s = String(text || '')
  // 表头紧贴分隔行
  s = s.replace(/\|[ \t]*\|(?=[ \t]*:?-{2,})/g, '|\n|')
  // 分隔行/数据行之间的 ||
  s = s.replace(/(\|:?-{2,}:?\|)[ \t]*\|+/g, '$1\n|')
  s = s.replace(/\|{2,}(?=[ \t]*:?-{2,})/g, '|\n|')
  // 状态列后下一行物料
  s = s.replace(/([✅❌])\|[ \t]*\|+(?=[ \t]*[A-Za-z0-9\u4e00-\u9fff])/g, '$1|\n|')
  s = s.replace(/\|{2,}(?=[ \t]*(?:CCL|PCB|ALPCB|SUP|板|阿|合|FR|高TG|维度|供应商))/g, '|\n|')
  // 通用：|| 后跟非空单元格
  s = s.replace(/\|{2,}(?=[ \t]*[^|\s\n])/g, '|\n|')
  return s
}

/** @deprecated 兼容旧 import；请用 normalizeMarkdown */
export function fixMarkdownTables(text) {
  if (!text || !String(text).includes('|')) return text

  let s = String(text).replace(/[—–﹣－]/g, '-')
  s = peelProseRowsFromMultilineTable(s)

  if (hasHealthyMultilineTable(s) && !hasCollapsedPipeTable(s)) {
    return s
  }

  const sepRe = /\|(?:[ \t]*:?-{1,}:?[ \t]*\|){2,}/g
  let match
  const pieces = []
  let last = 0
  const src = s

  while ((match = sepRe.exec(src)) !== null) {
    if (match.index < last) continue
    const sepStart = match.index
    const sepEnd = sepStart + match[0].length
    const before = src.slice(last, sepStart)
    const rest = src.slice(sepEnd)
    const bodyEnd = findPipeTableBodyEnd(rest)
    const after = rest.slice(0, bodyEnd)
    const headerStart = findHeaderStart(before)
    const prefix = before.slice(0, headerStart).replace(/\s+$/, '')
    const headerRaw = before.slice(headerStart)

    if (
      /\n\|/.test(headerRaw + '\n|' + after.slice(0, 80)) &&
      !isCollapsedSegment(headerRaw, after)
    ) {
      pieces.push(src.slice(last, sepEnd + bodyEnd))
      last = sepEnd + bodyEnd
      sepRe.lastIndex = last
      continue
    }

    const header = normalizePipeRow(headerRaw)
    const colCount = countColumns(header)
    if (colCount < 2) {
      pieces.push(src.slice(last, sepEnd + bodyEnd))
      last = sepEnd + bodyEnd
      sepRe.lastIndex = last
      continue
    }

    let body = after.replace(
      /([✅❌])\s*(需要进一步|需要查看|全部来自|全部|供应商统一|以上|综上|所有|4层板有|备注|如果你|若需|🔴|⚠️)/g,
      '$1|$2'
    )
    const cells = extractCells(body)
    const { rows, trailing } = buildRows(cells, colCount)
    if (!rows.length) {
      pieces.push(src.slice(last, sepEnd + bodyEnd))
      last = sepEnd + bodyEnd
      sepRe.lastIndex = last
      continue
    }

    const sep = '|' + Array(colCount).fill('---').join('|') + '|'
    let block = ''
    if (prefix) block += prefix + '\n\n'
    block += [header, sep, ...rows].join('\n')
    if (trailing) block += '\n\n' + trailing
    // 禁止把 body 之后全文拼进本段：last 已指向其后，后续循环/末尾 slice 会处理；
    // 否则每修一张塌缩表就会把后半篇报告再复制一遍（六/七重复、文末摘要错位）。
    pieces.push(block)
    last = sepEnd + bodyEnd
    sepRe.lastIndex = last
  }

  if (!pieces.length) return s
  pieces.push(src.slice(last))
  return pieces.join('').replace(/\n{3,}/g, '\n\n').trim()
}

function hasHealthyMultilineTable(s) {
  return /^\|.*\|\s*\n\|[-:\s|]+\|\s*\n\|/m.test(s)
}

function hasCollapsedPipeTable(s) {
  if (/\|(?:[ \t]*:?-{1,}:?[ \t]*\|){2,}[^\n]*\|/.test(s)) return true
  if (/\|(?:[ \t]*:?-{1,}:?[ \t]*\|){2,}\s*\|/.test(s)) return true
  return !s.includes('\n') && s.includes('|---')
}

function isCollapsedSegment(headerRaw, after) {
  const chunk = headerRaw + after
  if (!chunk.includes('\n')) return true
  if (/\|(?:[ \t]*:?-{1,}:?[ \t]*\|){2,}[^\n|]/.test(chunk)) return true
  return (chunk.match(/\n/g) || []).length < 2 && chunk.split('|').length > 12
}

function findPipeTableBodyEnd(rest) {
  if (!rest) return 0
  if (!rest.includes('\n') || /^[^\n]{0,20}\|/.test(rest)) {
    const m = rest.search(
      /(?:#{1,3}[ \t]|[—-]{1,}#{1,3}|[一二三四五六七八九十]+##|>\s*[⚠️🔴]|🔴\s*风险|关键发现|###\d)/
    )
    if (m > 0) return m
    return rest.length
  }

  const lines = rest.split('\n')
  let i = 0
  if (lines[0] && lines[0].includes('|')) i = 1
  for (; i < lines.length; i++) {
    const L = lines[i].trim()
    if (!L) {
      const next = (lines[i + 1] || '').trim()
      if (next && !/^\|/.test(next)) {
        return lines.slice(0, i).join('\n').length
      }
      continue
    }
    if (/^#{1,6}(\s|$)/.test(L) || /^#{1,6}[一二三四五\d]/.test(L)) {
      return lines.slice(0, i).join('\n').length
    }
    if (/^>/.test(L) && !/^\|/.test(L)) {
      return lines.slice(0, i).join('\n').length
    }
    if (/^[-—]{3,}$/.test(L) || /^!\[/.test(L)) {
      return lines.slice(0, i).join('\n').length
    }
    if (!/^\|/.test(L) && L.length > 8 && !/^[:\-|]+$/.test(L)) {
      return lines.slice(0, i).join('\n').length
    }
  }
  return rest.length
}

/* ---------------- 标题 / 结构 ---------------- */

export function fixHeadingsAndStructure(text) {
  let s = String(text || '')

  // —#标题 / —##章节（破折号粘标题）
  s = s.replace(/[—–﹣－]+(#{1,6})(?=[^\n#])/g, '\n\n$1')
  s = s.replace(/(#{1,6})[—–﹣－]+/g, '$1\n\n')

  // #标题>分析对象：... / #标题>报告日期：...
  s = s.replace(
    /(#{1,3}[ \t]*[^\n#>]+?)>([ \t]*(?:分析对象|统计周期|报告时间|生成时间|公司|报告日期|分析区间|编制对象|编制人|币种|货币)[^\n#]*)/g,
    '$1\n\n> $2'
  )

  // 一##二、章节（禁止 \s 跨行）
  s = s.replace(
    /([一二三四五六七八九十]+)、?[ \t]*(#{1,3})[ \t]*([一二三四五六七八九十]+、[^\n]*)/g,
    '\n\n$2 $3'
  )
  s = s.replace(/([^\n#])(#{1,3})[ \t]*([一二三四五六七八九十]+、)/g, '$1\n\n$2 $3')

  // ###2.1 / ##二、
  s = s.replace(/([^\n])(#{2,3})(\d+\.\d+)/g, '$1\n\n$2 $3')
  s = s.replace(/(#{2,3})(\d+\.\d+)/g, '$1 $2')
  s = s.replace(/(#{1,3})([一二三四五六七八九十]+、)/g, '$1 $2')

  // 句末粘标题
  s = s.replace(/([。：；）\])])(#{1,3}[ \t])/g, '$1\n\n$2')

  // # 后补空格（#标题 → # 标题）
  s = s.replace(/^(#{1,6})([^\s#\n])/gm, '$1 $2')

  // 「一、供应商概览正文粘连」拆开
  s = s.replace(
    /^(#{1,3}[ \t]+)?([一二三四五六七八九十]+、)(供应商概览|物料清单|替代料分析|采购趋势|库存分析|比价分析|风险|结论|摘要|仪表盘|行动建议)([^\n]*)$/gm,
    (m, hash, num, title, rest) => {
      const h = hash || '## '
      const body = (rest || '').replace(/^[：:\s]+/, '')
      if (!body) return `${h}${num}${title}`
      // 正文以「由/覆铜板/共/期内」等开头
      if (/^(由|覆铜板|共|期内|主要|本|该)/.test(body) || body.length > 4) {
        return `${h}${num}${title}\n\n${body}`
      }
      return `${h}${num}${title}${rest}`
    }
  )

  // ### 2.1标题正文粘连
  s = s.replace(
    /^(#{2,3}[ \t]+\d+\.\d+)([\u4e00-\u9fff][^\n]*)$/gm,
    (m, h, rest) => {
      // ### 2.1核心物料明细xxx → 标题与后文
      const mm = rest.match(
        /^([\u4e00-\u9fffA-Za-z0-9（）()_-]{2,16}?)((?:物料编码|规格|供应商|期内|主|其|本|FR|CCL|板).+)$/
      )
      if (mm) return `${h} ${mm[1]}\n\n${mm[2]}`
      return `${h} ${rest}`
    }
  )

  return s
}

/**
 * 元信息拆行、编号列表换行、下载询问与正文分离
 */
export function fixMetaAndLists(text) {
  let s = String(text || '')

  // 进度废话与标题分离（# 后可能无空格）
  s = s.replace(/(可视化图表已生成[^\n#]*)(#{1,3})/g, '$1\n\n$2')
  s = s.replace(/([。．])(#{1,3})([^\s#\n])/g, '$1\n\n$2 $3')

  // >报告日期: x >分析区间: y >编制对象: z  → 每字段一行
  s = s.replace(
    /\s*>\s*(?=(?:\*{0,2})(?:报告日期|分析区间|编制对象|编制人|币种|货币|分析对象|统计周期|报告时间|生成时间|公司)[：:*])/g,
    '\n> '
  )
  // 行内「报告日期: a 分析区间: b」无 > 时也拆开
  s = s.replace(
    /([^\n])[ \t]+(?=(?:报告日期|分析区间|编制对象|编制人|币种|货币)[：:])/g,
    '$1\n> '
  )
  // 去掉空的 >
  s = s.replace(/\n>\s*\n/g, '\n')

  // 编号行动建议与粘连编号：绝不改表行（| 开头），否则会把风险表单元格拆烂
  s = s
    .split('\n')
    .map((line) => {
      if (line.trim().startsWith('|')) return line
      let t = line.replace(/([。；!！])\s*(?=[2-9]\d?\.\s+)/g, '$1\n')
      t = t.replace(/[ \t]+(?=[2-9]\d?\.\s+\*\*)/g, '\n')
      t = t.replace(
        /([。；）%）\u4e00-\u9fff])\s+([2-9]\d?)\s+(\*\*[^*\n]{2,80}\*\*)/g,
        '$1\n$2. $3'
      )
      t = t.replace(/([。；）%）\u4e00-\u9fff])\s+([2-9]\d?)\s+(?=[\u4e00-\u9fffA-Za-z*])/g, '$1\n$2. ')
      t = t.replace(/([^\n])([2-9]\d?\.\s+(?:\*\*[^*]{2,40}\*\*|[\u4e00-\u9fff]{2,20}[（(]))/g, '$1\n$2')
      return t
    })
    .join('\n')

  // 下载询问必须独立成段；已有独立 --- 则不动（幂等）
  s = s.replace(/报告下载下载/g, '')
  if (!/(?:^|\n)---\s*\n+\s*是否需要将此报告下载/.test(s)) {
    s = s.replace(/([^\n])\s*(是否需要将此报告下载)/g, '$1\n\n---\n\n$2')
  }
  // 表行紧贴 --- 时补空行
  s = s.replace(/(^\|[^\n]*\|)\n(---\s*$)/gm, '$1\n\n$2')

  return s
}

/**
 * 关键因：中文说明后同一行紧跟 |表头| → GFM 不认表
 * 例：近效期批次情况：|物料 |批号 |...
 */
export function ensureTableStartsOnOwnLine(text) {
  // 中文说明后紧跟表头时拆行；已在表内的行（以 | 开头）绝不拆 —— 否则「板多多（…）| 金额」会被拆烂
  return String(text || '')
    .split('\n')
    .map((line) => {
      if (line.trim().startsWith('|')) return line
      let s = line.replace(/([：:。；）】\]])\s*(\|(?:[^|\n]+\|){2,})/g, '$1\n\n$2')
      s = s.replace(/(#{1,6}[^\n|]+[）)\u4e00-\u9fff])\s*(\|(?:[^|\n]+\|){2,})/g, '$1\n\n$2')
      return s
    })
    .join('\n')
}

/**
 * 关键因：表头行不以 | 开头 → markdown-it 不渲染成表格，用户看到原始 |---
 * 例：板供应商对比|供应商 |角色 |\n|-------|
 * 例：板 FR41.6mm|方案 |物料编码 |\n|------|
 * 例：板物料编码 |物料名称 |MPN |\n|---------|
 */
export function fixGluedTableHeaders(text) {
  const lines = String(text || '').split('\n')
  const out = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const next = lines[i + 1] || ''
    const nextIsSep =
      /^\s*\|(?:[ \t]*:?-{1,}:?[ \t]*\|)+\s*$/.test(next) ||
      /^\s*\|?-{3,}.*\|.*-{3,}/.test(next)
    const pipeCount = (line.match(/\|/g) || []).length

    if (
      nextIsSep &&
      pipeCount >= 2 &&
      !/^\s*\|/.test(line) &&
      !/^\s*#{1,6}\s/.test(line) &&
      !/^\s*>/.test(line)
    ) {
      const idx = line.indexOf('|')
      if (idx > 0) {
        const label = line.slice(0, idx).trim()
        let header = line.slice(idx).trim()
        if (!header.startsWith('|')) header = '|' + header
        if (!header.endsWith('|')) header += '|'

        if (
          label &&
          (/(?:对比|方案|清单|概览|分析|明细)$/.test(label) ||
            /^(?:板\s*)?FR-?4|^板\s*FR|^覆铜板?/.test(label))
        ) {
          out.push(label)
          out.push('')
          out.push(header)
        } else if (label) {
          // 当作缺失的首列：板物料编码|名称| → |板物料编码|名称|
          out.push('|' + label + header)
        } else {
          out.push(header)
        }
        continue
      }
    }

    // 分隔行本身缺行首 | ：-------|------| → |-------|------|
    if (
      pipeCount >= 2 &&
      !/^\s*\|/.test(line) &&
      /^[ \t]*:?-{2,}/.test(line.trim()) &&
      /\|/.test(line)
    ) {
      out.push('|' + line.trim())
      continue
    }

    out.push(line)
  }
  return out.join('\n')
}

function peelInlineNotes(text) {
  let s = String(text || '')
  s = s.replace(/(\S)(>\s*[⚠️🔴🟠])/g, '$1\n\n$2')
  s = s.replace(/(\S)(🔴\s*风险提示)/g, '$1\n\n$2')
  s = s.replace(/([✅❌])\s*(>\s*)/g, '$1\n\n$2')
  s = s.replace(/([^\n|])(>\s*⚠️)/g, '$1\n\n$2')
  // 引用行尾误粘的「一|」「##」
  s = s.replace(/(>[^\n]*?)\s*[一二三四五六七八九十]+\|\s*$/gm, '$1')
  return s
}

const TITLE_IN_HEADER =
  /(?:明细|汇总|一览|清单).{0,12}(?:共\s*\d+|：|:)|本月.{0,16}(?:采购|订单).{0,12}(?:明细|共)|共\s*\d+\s*单/
const SUMMARY_IN_CELL =
  /(?:本月合计|合计[：:]|均无[「"“]?已取消|共\s*\d+\s*单|按供应商|结论[：:]|请原样采用)/
const DATE_THEN_PROSE = /^(\d{1,2}\s*\/\s*\d{1,2}|\d{4}-\d{2}-\d{2})\s*(.+)$/
const MONEY_THEN_PROSE = /^([¥￥]\s*[\d,]+(?:\.\d+)?)\s+(.+)$/

export function looksLikeTitleHeader(cell) {
  const s = String(cell || '').trim()
  if (s.length < 10) return false
  if (TITLE_IN_HEADER.test(s)) return true
  return s.length >= 16 && (s.includes('：') || s.includes('共'))
}

function normalizeDateToken(raw) {
  return String(raw || '')
    .trim()
    .replace(/\s+/g, '')
}

export function peelSummaryCell(last) {
  const s = String(last || '').trim()
  if (!s || !SUMMARY_IN_CELL.test(s)) return { cell: s, prose: null }
  const mm = s.match(MONEY_THEN_PROSE)
  if (mm && SUMMARY_IN_CELL.test(mm[2])) {
    return { cell: mm[1].replace(/\s+/g, ''), prose: mm[2].trim() }
  }
  const m = s.match(DATE_THEN_PROSE)
  if (m) {
    const date = normalizeDateToken(m[1])
    const rest = m[2].trim()
    if (rest && SUMMARY_IN_CELL.test(rest)) return { cell: date, prose: rest }
    if (rest) return { cell: date, prose: rest }
  }
  if (s.length >= 10) return { cell: '-', prose: s }
  return { cell: s, prose: null }
}

function looksLikeDateCell(v) {
  const t = String(v || '').trim()
  return /^\d{1,2}\/\d{1,2}\b/.test(t) || /^\d{4}-\d{2}-\d{2}\b/.test(t)
}

function looksLikeMoneyCell(v) {
  const t = String(v || '').trim()
  return t.includes('¥') || t.includes('￥') || /^\d{1,3}(?:,\d{3})*(?:\.\d+)?$/.test(t)
}

export function inferTrailingHeader(dataRows, existingHeaders) {
  if (!dataRows.length) return '备注'
  const lasts = dataRows.map((r) => String(r[r.length - 1] || '').trim())
  if (lasts.length && lasts.every(looksLikeDateCell)) return '日期'
  if (lasts.some(looksLikeMoneyCell)) {
    const joined = existingHeaders.join(' ')
    if (joined.includes('单价') && !joined.includes('金额')) return '金额'
    if (joined.includes('金额') && !joined.includes('单价')) return '单价'
    if (joined.includes('数量')) return '单价'
    return '金额'
  }
  return '备注'
}

function dropRedundantRowIndexColumn(hdrCells, dataRows) {
  if (hdrCells.length < 3 || !dataRows.length) return { hdrCells, dataRows }
  if (!['行号', '#', 'No', 'NO', 'no'].includes(String(hdrCells[0]).trim())) {
    return { hdrCells, dataRows }
  }
  const vals = dataRows.map((r) => String(r[0] ?? '').trim())
  if (!vals.length || !vals.every((v) => /^\d+$/.test(v))) return { hdrCells, dataRows }
  const nums = vals.map(Number)
  const start = nums[0]
  if (!nums.every((n, i) => n === start + i)) return { hdrCells, dataRows }
  return {
    hdrCells: hdrCells.slice(1),
    dataRows: dataRows.map((r) => r.slice(1)),
  }
}

/**
 * 表头误塞标题 → 表前 **caption**，表头左移并补末列；去掉假「行号」列；末格合计出表。
 */
export function peelTableCaptionAndFooter(text) {
  const lines = String(text || '').split('\n')
  const out = []
  let i = 0
  while (i < lines.length) {
    if (!/^\|/.test(lines[i].trim())) {
      out.push(lines[i])
      i += 1
      continue
    }
    const block = []
    while (i < lines.length && /^\|/.test(lines[i].trim())) {
      block.push(lines[i])
      i += 1
    }
    if (block.length < 2) {
      out.push(...block)
      continue
    }
    const splitCells = (line) => {
      let body = line.trim()
      if (body.startsWith('|')) body = body.slice(1)
      if (body.endsWith('|')) body = body.slice(0, -1)
      return body.split('|').map((c) => c.trim())
    }
    const isSep = (line) => /^\|(?:[ \t]*:?-{1,}:?[ \t]*\|)+\s*$/.test(line.trim())
    let hdrIdx = 0
    let sepIdx = -1
    if (block.length >= 2 && isSep(block[1])) {
      sepIdx = 1
      hdrIdx = 0
    } else if (block.length >= 3 && isSep(block[2])) {
      hdrIdx = 1
      sepIdx = 2
    }
    let hdrCells = splitCells(block[hdrIdx])
    const dataStart = sepIdx >= 0 ? sepIdx + 1 : 1
    let dataRows = []
    for (let r = dataStart; r < block.length; r++) {
      if (isSep(block[r])) continue
      dataRows.push(splitCells(block[r]))
    }
    const footers = []
    let caption = null
    let mutated = false
    if (hdrCells.length >= 2 && looksLikeTitleHeader(hdrCells[0])) {
      caption = hdrCells[0]
      const n = hdrCells.length
      let rest = hdrCells.slice(1)
      if (dataRows.length && dataRows[0].length === n && rest.length === n - 1) {
        rest = rest.concat([inferTrailingHeader(dataRows, rest)])
      }
      hdrCells = rest
      mutated = true
    }
    const beforeDrop = hdrCells.length
    ;({ hdrCells, dataRows } = dropRedundantRowIndexColumn(hdrCells, dataRows))
    if (hdrCells.length !== beforeDrop) mutated = true
    for (let r = 0; r < dataRows.length; r++) {
      const cells = dataRows[r]
      if (cells.length < 2) continue
      const peeled = peelSummaryCell(cells[cells.length - 1])
      if (peeled.prose) {
        cells[cells.length - 1] = peeled.cell
        footers.push(peeled.prose)
        mutated = true
      }
    }
    // 表外误带「7/22 本月合计…」且末格为 -：把日期填回末格
    for (let fi = 0; fi < footers.length; fi++) {
      const fm = String(footers[fi]).match(
        /^(\d{1,2}\/\d{1,2}|\d{4}-\d{2}-\d{2})\s+((?:本月合计|合计[：:]).+)$/
      )
      if (!fm || !dataRows.length) continue
      const lastRow = dataRows[dataRows.length - 1]
      const lastCell = String(lastRow[lastRow.length - 1] || '').trim()
      if (lastCell === '-' || lastCell === '') {
        lastRow[lastRow.length - 1] = fm[1]
        footers[fi] = fm[2].trim()
        mutated = true
      }
    }
    if (!mutated) {
      // 合计已在表外下一行，末格为 -：仍要把日期填回
      let j = i
      while (j < lines.length && !lines[j].trim()) j += 1
      const nxt = j < lines.length ? lines[j].trim() : ''
      const fm = nxt.match(
        /^(\d{1,2}\/\d{1,2}|\d{4}-\d{2}-\d{2})\s+((?:本月合计|合计[：:]).+)$/
      )
      if (fm && dataRows.length) {
        const lastRow = dataRows[dataRows.length - 1]
        const lastCell = String(lastRow[lastRow.length - 1] || '').trim()
        if (lastCell === '-' || lastCell === '') {
          lastRow[lastRow.length - 1] = fm[1]
          mutated = true
          footers.push(fm[2].trim())
          i = j + 1 // skip the consumed prose line
        }
      }
      if (!mutated) {
        out.push(...block)
        continue
      }
      // fall through to rebuild with date filled
    } else {
      // already mutated from in-cell peel; also consume following duplicate summary line
      let j = i
      while (j < lines.length && !lines[j].trim()) j += 1
      const nxt = j < lines.length ? lines[j].trim() : ''
      if (/^(?:\d{1,2}\/\d{1,2}|\d{4}-\d{2}-\d{2}\s+)?(?:本月合计|合计[：:])/.test(nxt)) {
        i = j + 1
      }
    }
    const sepCols = Math.max(hdrCells.length, 2)
    const sep = '| ' + Array(sepCols).fill('---').join(' | ') + ' |'
    if (caption) {
      out.push(`**${caption}**`)
      out.push('')
    }
    out.push('| ' + hdrCells.join(' | ') + ' |')
    out.push(sep)
    for (const cells of dataRows) {
      const row = cells.slice()
      while (row.length < hdrCells.length) row.push('-')
      if (row.length > hdrCells.length) {
        const head = row.slice(0, hdrCells.length - 1)
        const tail = row.slice(hdrCells.length - 1).join(' ')
        out.push('| ' + head.concat([tail]).join(' | ') + ' |')
      } else {
        out.push('| ' + row.join(' | ') + ' |')
      }
    }
    for (const f of footers) {
      out.push('')
      out.push(f)
    }
  }
  return out.join('\n')
}

/**
 * 表行末粘连说明：`| … | 🟢安全 |>所有…` / `| … |17.3% |**供应商画像**：…`
 */
export function peelGluedTableRowProse(text) {
  const proseStart =
    /^(?:>\s*)?(所有|分析|供应商画像|需要|以上|综上|备注|\*\*供应商|\*\*分析|\*\*风险|\*\*供应结构|\*\*风险要点|供应结构|风险要点)/
  const out = []
  for (const line of String(text || '').split('\n')) {
    const trimmed = line.trim()
    if (!/^\|/.test(trimmed) || (trimmed.match(/\|/g) || []).length < 2) {
      out.push(line)
      continue
    }
    if (/^\|(?:[ \t]*:?-{1,}:?[ \t]*\|)+$/.test(trimmed)) {
      out.push(line)
      continue
    }
    // |cells|>prose 或 |cells| >prose
    const glued = trimmed.match(/^((?:\|[^|\n]*)+\|)\s*>(.+)$/)
    if (glued) {
      out.push(glued[1])
      out.push('')
      out.push(glued[2].trim())
      continue
    }
    // |cells|后面直接跟问句/邀请（表外追问必须剥出）
    const trailProse = trimmed.match(
      /^((?:\|[^|\n]*)+\|)\s*((?:你要|你需要|请问|请选择|请确认|确认后|需要我|是否需要|请告诉|若需|如果你|哪一款)[\s\S]{2,})$/
    )
    if (trailProse) {
      out.push(trailProse[1])
      out.push('')
      out.push(trailProse[2].trim())
      continue
    }
    // |cells|- **说明… 粘在表外
    const dashNote = trimmed.match(/^((?:\|[^|\n]*)+\|)\s*(-\s+\*\*.+)$/)
    if (dashNote) {
      out.push(dashNote[1])
      out.push('')
      out.push(dashNote[2].replace(/^-\s*/, '').trim())
      continue
    }
    // 最后一格是长说明 / 供应结构块 / 下单追问 / 合计说明（多出的第 N 列）
    let body = trimmed
    if (body.startsWith('|')) body = body.slice(1)
    if (body.endsWith('|')) body = body.slice(0, -1)
    const cells = body.split('|').map((c) => c.trim())
    if (cells.length >= 2) {
      const last = cells[cells.length - 1] || ''
      const orderAsk =
        /^(?:你要|你需要|请问|请选择|请确认|确认后|是否需要|需要我|哪一款)/.test(last) ||
        (/[？?]$/.test(last) &&
          last.length >= 6 &&
          /(?:你要|你需要|哪种|哪一款|确认后|立刻下单|下单|选哪|请确认)/.test(last)) ||
        (/[？?]/.test(last) &&
          last.length >= 8 &&
          /(?:下单|物料名称|哪一款|哪种)/.test(last))
      const summaryPeel = peelSummaryCell(last)
      if (
        orderAsk ||
        (last.length > 24 && proseStart.test(last)) ||
        /^\*\*(?:供应商画像|分析|风险|供应结构|风险要点)/.test(last) ||
        /^供应结构/.test(last) ||
        /^风险要点/.test(last) ||
        summaryPeel.prose
      ) {
        if (summaryPeel.prose) {
          cells[cells.length - 1] = summaryPeel.cell
          out.push('|' + cells.join('|') + '|')
          out.push('')
          out.push(summaryPeel.prose)
        } else {
          cells.pop()
          out.push('|' + cells.join('|') + '|')
          out.push('')
          out.push(last.replace(/^>\s*/, ''))
        }
        continue
      }
    }
    out.push(line)
  }
  return out.join('\n')
}

/**
 * 模型常把「六、七」整段再输出一遍；只保留每个章节号首次出现。
 */
export function dedupeRepeatedSections(text) {
  const lines = String(text || '').split('\n')
  const out = []
  const seen = new Set()
  let skipping = false
  const re = /^(#{1,3})\s+([一二三四五六七八九十]+)、/
  for (const line of lines) {
    const m = line.match(re)
    if (m) {
      const num = m[2]
      if (seen.has(num)) {
        skipping = true
        continue
      }
      seen.add(num)
      skipping = false
    }
    if (skipping) continue
    out.push(line)
  }
  return out.join('\n')
}

/**
 * 下载询问之后的仪表盘残片（总库存/供应结构等）一律丢弃。
 */
export function trimAfterDownloadCta(text) {
  const s = String(text || '')
  const m = s.match(/是否需要将此报告下载[^\n]*/)
  if (!m || m.index == null) return s
  const cleaned = m[0].replace(/[。．]?\s*保存\s*$/, '')
  return (s.slice(0, m.index) + cleaned).replace(/\s+$/, '')
}

/* ---------------- 空格虚线表 ---------------- */

export function fixSpaceSeparatedTables(text) {
  let s = String(text || '')

  s = s.replace(
    /([^\n|#][^\n|]{4,}?)\s+((?:-{3,}[ \t]+){2,}-{3,})\s+([^\n]+)/g,
    (full, header, sep, body) => {
      // 选型速查 / 行动优先级溢出密文：交给专用修复，禁止建成超宽假表
      if (
        full.includes('选型建议') ||
        full.includes('###') ||
        /[🔴🟡🟢🟠]/.test(full) ||
        /\d+\.\s+\S.+\s+[🔴🟡🟢]/.test(full)
      ) {
        return full
      }
      // 避免误伤已是正文的长句
      if (header.includes('。') && header.length > 60) return full
      const cols = sep.trim().split(/\s+/).filter((x) => /^-{3,}$/.test(x))
      if (cols.length < 2) return full
      const headers = splitHeaderCells(header.trim(), cols.length)
      if (headers.length < 2) return full
      const { rows, trailing } = splitSpaceDataRows(body.trim(), cols.length)
      if (!rows.length) return full
      return formatGfm(headers, rows) + (trailing ? '\n\n' + trailing : '')
    }
  )

  const lines = s.split('\n')
  const out = []
  for (let i = 0; i < lines.length; i++) {
    const header = lines[i]
    const sep = lines[i + 1] || ''
    if (
      !header.includes('|') &&
      header.trim().length > 4 &&
      /^(?:-{3,}[ \t]+){2,}-{3,}$/.test(sep.trim())
    ) {
      const colCount = sep.trim().split(/\s+/).filter((x) => /^-{3,}$/.test(x)).length
      const headers = splitHeaderCells(header.trim(), colCount)
      const dataLines = []
      let j = i + 2
      for (; j < lines.length; j++) {
        const L = lines[j].trim()
        if (!L) break
        if (/^#{1,6}(\s|$)/.test(L) || /^>/.test(L) || L.includes('|')) break
        if (/^(?:-{3,}[ \t]+){2,}-{3,}$/.test(L)) break
        dataLines.push(L)
      }
      if (headers.length >= 2 && dataLines.length) {
        const rows = dataLines.map((l) => splitSpaceRow(l, colCount))
        out.push(formatGfm(headers, rows).trim())
        i = j - 1
        continue
      }
    }
    out.push(header)
  }
  return out.join('\n')
}

function splitHeaderCells(header, colCount) {
  if (/\s{2,}/.test(header)) {
    const parts = header.split(/\s{2,}/).map((x) => x.trim()).filter(Boolean)
    if (parts.length === colCount) return parts
  }
  const known =
    '物料编码|名称|MPN|制造商|规格|采购单价|建议零售价|MOQ|交期\\(天\\)|效期\\(天\\)|RoHS|无卤|供应商|角色|覆铜板采购额|覆铜板物料数|状态|板多多单价|1688单价|价差|降幅|风险等级|主供|替代料|库存|效期|预警'
  const re = new RegExp(`(${known})`, 'g')
  const parts = header.match(re)
  if (parts && parts.length >= 2) return parts
  const ws = header.split(/\s+/).filter(Boolean)
  if (ws.length === colCount) return ws
  return ws.length >= 2 ? ws : []
}

function splitSpaceDataRows(body, colCount) {
  let b = body
  b = b.replace(/([✅❌])[ \t]*([✅❌])[ \t]*(?=[A-Z0-9\u4e00-\u9fff])/g, '$1 $2\n')
  b = b.replace(/(无替代|⚠️注意|⚠️[^\s]*)[ \t]+(?=FR|高TG|CCL|PCB|铝)/g, '$1\n')
  b = b.replace(/[ \t]+(?=(?:CCL|PCB|ALPCB|FR4|LOT)-[A-Z0-9])/g, '\n')
  b = b.replace(/[ \t]+(?=FR4?\d)/g, '\n')
  b = b.replace(/[ \t]+(?=高TG)/g, '\n')
  // 结语
  b = b.replace(/([^\n])(>\s*⚠️)/g, '$1\n$2')

  const lines = b.split('\n').map((l) => l.trim()).filter(Boolean)
  const rows = []
  const trailing = []
  for (const line of lines) {
    if (isProseCell(line) || /^[>🔴]/.test(line) || /^⚠️\s*1688/.test(line)) {
      trailing.push(line)
      continue
    }
    rows.push(splitSpaceRow(line, colCount))
  }
  return { rows, trailing: trailing.join('\n') }
}

function splitSpaceRow(line, colCount) {
  // 不拆 mm/μm、小数
  const tokens =
    line.match(
      /¥-?[\d,.]+|-?\d+\.\d+%?|-?\d+%|✅|❌|⚠️[^\s]*|N\/A|无替代|-|[A-Za-z0-9\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff._/\-μ%]*/g
    ) || []
  if (tokens.length === colCount) return tokens
  if (tokens.length > colCount) {
    // 名称/规格常占多 token：保留首列与末尾数值列，中间合并
    const tailN = Math.min(6, colCount - 1)
    const headN = colCount - tailN
    const head = tokens.slice(0, headN)
    const mid = tokens.slice(headN, tokens.length - tailN + headN > headN ? tokens.length - (colCount - headN) : headN)
    // 更稳：首 1~2 列 + 合并中段 + 末尾固定列
    const first = tokens.slice(0, Math.min(2, colCount - 1))
    const last = tokens.slice(-(colCount - first.length))
    const middle = tokens.slice(first.length, tokens.length - last.length).join(' ')
    if (first.length + 1 + last.length === colCount) {
      return middle ? first.concat([middle], last) : first.concat(last)
    }
    const head2 = tokens.slice(0, colCount - 1)
    return head2.concat([tokens.slice(colCount - 1).join(' ')])
  }
  while (tokens.length < colCount) tokens.push('')
  return tokens
}

function formatGfm(headers, rows) {
  const col = headers.length
  const sep = '|' + Array(col).fill('---').join('|') + '|'
  const h = '|' + headers.join('|') + '|'
  const body = rows.map((r) => {
    const cells = [...r]
    while (cells.length < col) cells.push('')
    return '|' + cells.slice(0, col).join('|') + '|'
  })
  return '\n\n' + [h, sep, ...body].join('\n') + '\n\n'
}

/* ---------------- GFM 表工具 ---------------- */

function peelProseRowsFromMultilineTable(text) {
  const lines = String(text).split('\n')
  if (lines.length < 3) return text

  const out = []
  let peeled = []
  let inTable = false
  let sawSep = false

  const flushPeeled = () => {
    if (!peeled.length) return
    out.push('')
    for (const t of [...new Set(peeled.map((x) => x.trim()).filter(Boolean))]) {
      out.push(t)
    }
    peeled = []
  }

  for (const line of lines) {
    const trimmed = line.trim()
    const isPipeRow = /^\|.*\|/.test(trimmed)
    const isSep = /^\|(?:[ \t]*:?-{1,}:?[ \t]*\|)+$/.test(trimmed)

    if (isSep) {
      inTable = true
      sawSep = true
      out.push(line)
      continue
    }

    if (inTable && sawSep && isPipeRow) {
      const cells = splitRowCells(trimmed)
      if (isProseRow(cells)) {
        peeled.push(cells.filter(Boolean).join(' '))
        continue
      }
      out.push(line)
      continue
    }

    if (inTable && sawSep && !isPipeRow) {
      flushPeeled()
      inTable = false
      sawSep = false
    }
    out.push(line)
  }
  flushPeeled()

  return out.join('\n').replace(/\n{3,}/g, '\n\n')
}

function splitRowCells(row) {
  let r = String(row || '').trim()
  if (r.startsWith('|')) r = r.slice(1)
  if (r.endsWith('|')) r = r.slice(0, -1)
  return r.split('|').map((c) => c.trim())
}

function isProseCell(cell) {
  const c = String(cell || '').trim()
  if (!c) return false
  const bare = c.replace(/^>+\s*/, '')
  if (/^>/.test(c)) return true
  if (PROSE_START.test(c) || PROSE_START.test(bare)) return true
  if (/需要查看|可告诉我|均符合\s*RoHS|效期|MSL\s*为|风险提示|持续验证|比板多多便宜/.test(c)) {
    return true
  }
  if (c.length > 28 && /[，。；]/.test(c) && !NAME_LIKE.test(bare) && !MPN_LIKE.test(bare)) {
    return true
  }
  return false
}

function isProseRow(cells) {
  if (!cells || !cells.length) return false
  const nonempty = cells.filter((c) => String(c || '').trim() !== '')
  if (!nonempty.length) return false
  // 风险/行动等「序号 | 说明」数据行：绝不能当散文剥出（长文含 效期/MSL 易误伤）
  if (nonempty.length >= 2 && /^\d{1,3}$/.test(String(nonempty[0]).trim())) {
    return false
  }
  if (
    /^(对比项|角色|金额占比|覆盖物料|交期|信用|优势与风险|序号|事项|字段|值|状态|物料名称|partId|MPN|供应商|数量|单价|创建人|预计交货日期|备注)$/.test(
      String(nonempty[0]).trim().replace(/\*+/g, '')
    )
  ) {
    return false
  }
  if (isProseCell(nonempty[0])) return true
  const joined = nonempty.join(' ')
  if (/需要查看|可告诉我|均符合\s*RoHS|效期180|MSL|风险提示|比板多多便宜/.test(joined)) {
    const hasMpn = nonempty.some((c) => MPN_LIKE.test(c))
    const hasName = nonempty.some((c) => NAME_LIKE.test(String(c).replace(/^>+\s*/, '')))
    if (!hasMpn && !hasName) return true
  }
  return false
}

function findHeaderStart(before) {
  const yi = Math.max(before.lastIndexOf('：'), before.lastIndexOf(':'))
  if (yi >= 0) {
    const p = before.indexOf('|', yi)
    if (p >= 0) return p
  }
  const lines = before.split('\n')
  for (let i = lines.length - 1; i >= 0; i--) {
    if (/\|/.test(lines[i]) && !/^\|[-:\s|]+\|$/.test(lines[i].trim())) {
      const prefixLen = lines.slice(0, i).join('\n').length
      return prefixLen + (i > 0 ? 1 : 0)
    }
  }
  const p = before.indexOf('|')
  return p >= 0 ? p : 0
}

function normalizePipeRow(row) {
  let r = String(row || '')
    .replace(/\s*\n\s*/g, ' ')
    .replace(/[ \t]+/g, ' ')
    .trim()
  r = r.replace(/\|{2,}/g, '|')
  if (!r.startsWith('|')) {
    const p = r.indexOf('|')
    if (p > 0) r = r.slice(p)
  }
  if (!r.startsWith('|')) r = '|' + r
  if (!r.endsWith('|')) r += '|'
  return r
}

function countColumns(headerRow) {
  return Math.max(0, headerRow.split('|').length - 2)
}

function extractCells(after) {
  let s = String(after || '').replace(/\n+/g, '|')
  s = s.replace(/^\|+/, '')
  const parts = s.split('|').map((c) => c.trim())
  while (parts.length && parts[parts.length - 1] === '') parts.pop()
  return parts
}

function isIndexStart(cell, next) {
  if (!/^\d+$/.test(String(cell || '').trim())) return false
  return NAME_LIKE.test(String(next || '').trim())
}

function findIndexStarts(cells) {
  const starts = []
  for (let i = 0; i < cells.length - 1; i++) {
    if (isIndexStart(cells[i], cells[i + 1])) starts.push(i)
  }
  return starts
}

function alignToColCount(raw, colCount) {
  let cells = raw.map((c) => String(c || '').trim()).filter((c) => c !== '')
  let trailing = ''
  while (cells.length && isProseCell(cells[cells.length - 1])) {
    trailing = (cells.pop() + (trailing ? ' ' + trailing : '')).trim()
  }
  if (cells.length && isProseCell(cells[0])) {
    trailing = (cells.join(' ') + (trailing ? ' ' + trailing : '')).trim()
    return { cells: [], trailing }
  }
  if (cells.length) {
    const last = cells[cells.length - 1]
    const m = last.match(
      /^([✅❌]*)\s*(需要进一步|需要查看|全部来自|全部|供应商统一|以上|综上|所有|4层板有|备注|如果你|若需|🔴|⚠️)(.*)$/
    )
    if (m && m[2]) {
      cells[cells.length - 1] = m[1] || ''
      if (!cells[cells.length - 1]) cells.pop()
      trailing = (m[2] + (m[3] || '') + (trailing ? ' ' + trailing : '')).trim()
    }
  }
  if (cells.length > colCount) {
    const head = cells.slice(0, colCount - 2)
    const tail = cells.slice(-2)
    cells = head.concat(tail)
  }
  while (cells.length < colCount) cells.push('')
  return { cells: cells.slice(0, colCount), trailing }
}

function buildRows(cells, colCount) {
  const rows = []
  const trailingParts = []
  const indexStarts = findIndexStarts(cells)

  if (indexStarts.length >= 2) {
    for (let s = 0; s < indexStarts.length; s++) {
      const from = indexStarts[s]
      let to = s + 1 < indexStarts.length ? indexStarts[s + 1] : cells.length
      while (to > from && cells[to - 1] === '') to--
      const { cells: rowCells, trailing } = alignToColCount(cells.slice(from, to), colCount)
      if (rowCells.length && !isProseRow(rowCells) && rowCells.some((c) => c !== '')) {
        rows.push('|' + rowCells.join('|') + '|')
      } else if (trailing || isProseRow(rowCells)) {
        const t = trailing || rowCells.filter(Boolean).join(' ')
        if (t) trailingParts.push(t)
      }
      if (trailing) trailingParts.push(trailing)
    }
    const lastStart = indexStarts[indexStarts.length - 1]
    let i = lastStart
    let taken = 0
    while (i < cells.length && taken < colCount) {
      if (cells[i] !== '') taken++
      i++
    }
    while (i < cells.length && cells[i] === '') i++
    if (i < cells.length) {
      const rest = cells.slice(i).filter(Boolean).join(' ').replace(/^[✅❌|]+/, '').trim()
      if (rest) trailingParts.push(rest)
    }
  } else {
    let i = 0
    while (i < cells.length) {
      while (i < cells.length && cells[i] === '') i++
      if (i >= cells.length) break
      if (isProseCell(cells[i])) {
        trailingParts.push(cells.slice(i).filter(Boolean).join(' ').trim())
        break
      }
      const raw = []
      while (raw.length < colCount && i < cells.length) {
        if (raw.length > 0 && isProseCell(cells[i])) break
        raw.push(cells[i])
        i++
      }
      const { cells: rowCells, trailing } = alignToColCount(raw, colCount)
      if (rowCells.some((c) => c !== '') && !isProseRow(rowCells)) {
        rows.push('|' + rowCells.join('|') + '|')
      } else if (isProseRow(rowCells)) {
        trailingParts.push(rowCells.filter(Boolean).join(' '))
      }
      if (trailing) trailingParts.push(trailing)
    }
    if (i < cells.length) {
      const rest = cells.slice(i).filter(Boolean).join(' ').trim()
      if (rest) trailingParts.push(rest)
    }
  }

  const trailing = [...new Set(trailingParts.map((t) => t.trim()).filter(Boolean))].join('\n')
  return { rows, trailing }
}
