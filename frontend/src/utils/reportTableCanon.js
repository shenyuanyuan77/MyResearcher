/**
 * 报告表格唯一出口 + 健康检查（与 Python report_table_canon.py 对齐）
 *
 * 根因对策：关键区块不信任模型手写管道表；一律经 renderGfmTable 产出。
 * 健康正文前端跳过 normalize，避免二次「创意」重整。
 */

export function cellSafe(c) {
  return String(c ?? '')
    .replace(/\|/g, '｜')
    .replace(/\n/g, ' ')
    .replace(/\uFFFD/g, '')
    .replace(/[\uD800-\uDFFF]/g, '')
    .trim()
}

/** 唯一合法的 GFM 表生成器 */
export function renderGfmTable(headers, rows) {
  const hdrs = headers.map(cellSafe)
  if (hdrs.length < 2) throw new Error('table needs ≥2 columns')
  const n = hdrs.length
  const lines = [
    `| ${hdrs.join(' | ')} |`,
    `| ${hdrs.map((h) => '-'.repeat(Math.max(6, h.length))).join(' | ')} |`,
  ]
  for (const row of rows) {
    let cells = [...row].map(cellSafe)
    if (cells.length < n) cells = [...cells, ...Array(n - cells.length).fill('-')]
    else if (cells.length > n) cells = [...cells.slice(0, n - 1), cells.slice(n - 1).join(' ')]
    lines.push(`| ${cells.join(' | ')} |`)
  }
  return lines.join('\n')
}

function colCount(line) {
  const t = line.trim()
  if (!t.startsWith('|')) return 0
  return t.replace(/^\||\|$/g, '').split('|').length
}

function isSepLine(line) {
  return /^\|(?:[ \t]*:?-{1,}:?[ \t]*\|)+\s*$/.test(line.trim())
}

function* iterTableBlocks(text) {
  const lines = String(text || '').split('\n')
  let i = 0
  while (i < lines.length) {
    if (!lines[i].trim().startsWith('|')) {
      i++
      continue
    }
    const start = i
    const block = []
    while (i < lines.length && lines[i].trim().startsWith('|')) {
      block.push(lines[i])
      i++
    }
    yield { start, end: i, block }
  }
}

export function findTableHealthIssues(text) {
  const issues = []
  const s = String(text || '')
  const lines = s.split('\n')

  // 塌缩表：|| 粘行 / 单行含表头+分隔+数据 —— 前端绝不能跳过 normalize
  if (/\|\|[ \t]*(?:[^|\s\n]|:?-{2,})/.test(s) || /\|\|[ \t]*\|/.test(s)) {
    issues.push('collapsed_double_pipes')
  }
  for (const line of lines) {
    if (
      line.includes('||') &&
      (line.match(/\|/g) || []).length >= 6 &&
      /\|[ \t]*:?-{2,}/.test(line)
    ) {
      issues.push('collapsed_single_line_table')
      break
    }
  }

  if (/^\|\s*(占比|角色|信用|涉及物料)\s*\|?\s*$/m.test(s)) issues.push('vertical_supply_header')
  if (/\*\*供应结构\*\*[：:]*[ \t]*\|/.test(s)) issues.push('glued_supply_header')
  if (/\*\*风险要点\*\*[：:]*[ \t]*\|/.test(s)) issues.push('glued_risk_header')
  if (/(?<!\*)(?:供应结构|风险要点)[：:][ \t]*\|/.test(s)) issues.push('glued_plain_section_header')
  // 仅同行粘连；换行后的 ]\n\n** 是正常排版
  if (/\]\([^)]+\)[ \t]*\*\*/.test(s)) issues.push('image_glued_to_heading')
  if (/^\|[^\n]*!\[[^\]]*\]\([^)]+\)/m.test(s)) issues.push('image_in_table')
  if (/^\|\s*\d+\s*\|[^|\n]*(?:[🔴🟡🟢🟠]|⚠️)[^|\n]*(?:[🔴🟡🟢🟠]|⚠️)/mu.test(s)) {
    issues.push('mashed_risk_emojis')
  }
  if ((s.match(/\*\*风险要点\*\*/g) || []).length >= 2) issues.push('duplicate_risk_sections')
  // 份额伪行：短描述「供应商 ¥金额（占比%）」；勿误伤含涨幅的真价格风险
  for (const line of lines) {
    const rm = line.match(/^\|\s*\d+\s*\|\s*([^|]+?)\s*\|?/)
    if (!rm) continue
    const d = rm[1].trim()
    if (/(库存|安全|替代|单源|涨|交期|效期|到期|预警|断供|缺口|无替代|缺料)/.test(d)) continue
    if (/¥\s*[\d,]+\s*[（(]?\s*\d+\.?\d*\s*%/.test(d) || (d.includes('¥') && d.includes('%') && d.length < 48)) {
      issues.push('fake_risk_amount_row')
      break
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const t = lines[i].trim()
    if (/^\d+[\.、]\s+/.test(t) && !t.startsWith('|')) {
      const prev = i ? lines[i - 1].trim() : ''
      const nxt = i + 1 < lines.length ? lines[i + 1].trim() : ''
      if (prev.startsWith('|') && (nxt.startsWith('|') || nxt.startsWith('**'))) {
        issues.push('intrusion_between_table_rows')
        break
      }
    }
  }

  if (/^\|[\s|:\-]+\|\s*\n\|[\s|:\-]+\|\s*\n\|[\s|:\-]+\|/m.test(s)) {
    issues.push('multi_fake_separators')
  }

  for (const { block } of iterTableBlocks(s)) {
    if (block.length < 2) continue
    const cols = block.filter((ln) => !isSepLine(ln)).map(colCount)
    if (!cols.length) continue
    if (Math.max(...cols) >= 4 && Math.min(...cols) <= 2 && new Set(cols).size >= 3) {
      issues.push('ragged_column_counts')
      break
    }
    if (!block.slice(0, 3).some(isSepLine) && block.length >= 3) {
      issues.push('missing_separator')
      break
    }
  }

  if (/\|\s*\d+\s*\|[^|\n]*\*\*\s*\|/.test(s)) issues.push('broken_bold_in_cell')
  if (/^\d+[\.、]\s*\*\*CCL\s*\|/m.test(s)) issues.push('split_material_code')

  if (/价格趋势\s*FR\s*4|稳步上行：\s*-?\s*最低/.test(s)) issues.push('mashed_price_trend_prose')
  const pt = s.match(
    /#{2,3}\s+[^\n]*价格趋势([\s\S]{0,1200}?)(?=\n#{2,3}\s+|\n##\s|\n---\s*\n|$)/
  )
  if (pt) {
    const block = pt[1]
    const hasBddRow = /^\|\s*[^|\n]*板多多[^|\n]*\|/m.test(block)
    if (
      /\|[^\n]*规格[^\n]*渠道/.test(block) &&
      /1688|高TG|高\s*TG/.test(block) &&
      !hasBddRow
    ) {
      issues.push('incomplete_price_trend_table')
    }
  }

  if (/\|\s*列\s*[12]\s*\|/.test(s)) issues.push('fake_column_headers')
  if (/\|\s*项目\s*\|\s*内容\s*\|/.test(s) && /\|\s*(?:0?\d{1,2}\s*月|20\d{2}-\d{2})\s*\|/.test(s)) {
    issues.push('fake_project_content_headers')
  }
  if (/月度采购趋势[^\n]{0,40}?月份[ \t]+(?:采购额|订单数)/.test(s)) {
    issues.push('glued_monthly_trend_header')
  }
  if (/\|[^\n]*\|\n\*\*?趋势小结/.test(s)) issues.push('trend_summary_glued_to_table')
  if (
    /\|\s*(?:本月订单数|本月采购额|物料总数)[^\n]*\|\n(?:\|[-:| \t]+\|\n)*(?:\|\s*(?:列\s*[12]|项目|内容)[^\n]*\|\n)*\|\s*(?:0?\d{1,2}\s*月|20\d{2}-\d{2})\s*\|/.test(
      s
    )
  ) {
    issues.push('kpi_holds_month_rows')
  }
  if (/风险要点[\s\S]{0,400}月度采购趋势/.test(s)) issues.push('risk_holds_monthly_trend')
  if (/\|\s*\d+\s*\|[^|\n]+\|\s*\|\s*\|/.test(s) && /(?:^|\n)[🔴🟡🟢]/.test(s)) {
    issues.push('incomplete_action_row_spill')
  }
  if (/选型建议速查[^\n]*场景[ \t]+推荐渠道[ \t]+理由/.test(s)) {
    issues.push('mashed_selection_quickcheck')
  }
  // 下单追问粘在表行末：`|6天 |你要下单的是哪一款？…`（渲染时被裁掉）
  if (
    /^\|[^\n]*\|\s*(?:你要|你需要|请问|请选择|请确认|确认后|哪一款)/m.test(s) ||
    /^\|[^\n]*\|[^|\n]*(?:哪一款|哪种铜箔|立刻下单|请确认物料)/m.test(s)
  ) {
    issues.push('glued_order_ask_to_table')
  }
  // 下单已收集数据密文（未成表）
  if (
    /\*{0,2}已收集的(?:订单)?数据\*{0,2}/.test(s) &&
    /物料(?:名称|ID)|partId/i.test(s) &&
    !/\|\s*字段\s*\|\s*值\s*\|/.test(s)
  ) {
    issues.push('mashed_order_collected_prose')
  }
  // 标题塞进首列表头 / 合计塞进末格
  if (/^\|\s*[^|\n]*(?:明细|汇总|一览).{0,12}(?:共\s*\d+|：)[^|\n]*\|/m.test(s)) {
    issues.push('title_in_table_header')
  }
  if (/^\|[^\n]*\|[^|\n]*(?:本月合计|合计[：:]|均无[「"“]?已取消|按供应商|结论[：:])[^|\n]*\|/m.test(s)) {
    issues.push('summary_in_table_cell')
  }
  for (const wm of s.matchAll(/#{2,3}\s*[^\n]*预警[^\n]*\n([\s\S]*?)(?=\n#{1,3}\s|$)/g)) {
    if (/\|\s*(?:20\d{2}-(?:0[1-9]|1[0-2])|0?\d{1,2}\s*月)\s*\|/.test(wm[1])) {
      issues.push('monthly_data_in_warning_section')
      break
    }
  }

  return issues
}

/** True = 前端可跳过 normalize */
export function reportTablesHealthy(text) {
  if (!text || text.length < 20) return true
  return findTableHealthIssues(text).length === 0
}

export function emitSupplyTable(rows) {
  return (
    '**供应结构**\n\n' +
    renderGfmTable(['供应商', '物料', '金额 (¥)', '占比', '角色', '信用'], rows) +
    '\n\n'
  )
}

export function emitRiskTable(items) {
  const rows = items.map((desc, i) => [String(i + 1), cellSafe(desc)])
  return '**风险要点**\n\n' + renderGfmTable(['序号', '风险说明'], rows) + '\n\n'
}

/** 下单完整性校验表（字段 | 值 | 状态） */
export function emitOrderIntegrityTable(rows) {
  return renderGfmTable(['字段', '值', '状态'], rows) + '\n'
}
