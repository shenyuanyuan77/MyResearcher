/**
 * 下单「已收集的数据」密文 → 结构化行（前后端可共用思路；JS 侧实现）。
 */

const FIELD_ALIASES = [
  { keys: ['物料名称', '名称'], label: '物料名称' },
  { keys: ['物料ID', '物料 Id', 'partId', 'part_id'], label: 'partId' },
  { keys: ['MPN', 'mpn'], label: 'MPN' },
  { keys: ['规格', 'partCode', '物料编码'], label: '规格' },
  { keys: ['数量'], label: '数量' },
  { keys: ['单价'], label: '单价' },
  { keys: ['供应商'], label: '供应商' },
  { keys: ['预计交货日期', '预计交货', '预计交期', '交期'], label: '预计交货' },
  { keys: ['创建人', '用户', '采购人'], label: '创建人' },
  { keys: ['备注'], label: '备注' },
]

const ALL_KEYS = FIELD_ALIASES.flatMap((f) => f.keys)

function canonicalLabel(rawKey) {
  const k = String(rawKey || '').trim()
  for (const f of FIELD_ALIASES) {
    if (f.keys.some((x) => x.toLowerCase() === k.toLowerCase())) return f.label
  }
  return k
}

/** 从「物料ID：38（partCode: FOIL-ED35，MPN: ED-35UM，电解铜箔35um）」拆出多行 */
function expandMaterialIdValue(val) {
  const rows = []
  const s = String(val || '').trim()
  const idm = s.match(/^(\d+)\s*[（(]/) || s.match(/^(\d+)\s*$/)
  if (idm) rows.push(['partId', idm[1]])
  const code = s.match(/partCode\s*[：:=]\s*([A-Za-z0-9_-]+)/i)
  if (code) rows.push(['规格', code[1]])
  const mpn = s.match(/MPN\s*[：:=]\s*([A-Za-z0-9_-]+)/i)
  if (mpn) rows.push(['MPN', mpn[1]])
  const name =
    s.match(/名称\s*[：:=]\s*([^）)]+)/) ||
    s.match(/[，,]\s*([^，,）)]*铜箔[^，,）)]*)/) ||
    s.match(/[，,]\s*([一-龥A-Za-z0-9][^，,）)]{1,40})\s*[）)]\s*$/)
  if (name) {
    const n = name[1].replace(/^名称\s*[：:=]\s*/, '').trim()
    if (n && !/^(partCode|MPN|FOIL)/i.test(n)) rows.push(['物料名称', n])
  }
  if (!rows.length && s) rows.push(['partId', s])
  return rows
}

function cleanDeliveryValue(val) {
  let v = String(val || '').trim()
  const days = v.match(/(\d+)\s*天/)
  // 含「假设今天/基于当前日期」的臆测日期一律丢掉，只保留交期天数
  if (days && /基于当前日期|假设今天约|大约\s*20\d{2}/.test(v)) {
    return `${days[1]} 天`
  }
  v = v.replace(/[，,]?\s*基于当前日期大约[^）)]*[）)]?/g, '')
  v = v.replace(/[，,]?\s*假设今天约[^）)]*[）)]?/g, '')
  v = v.replace(/约为?/g, '').replace(/[（(]\s*[）)]/g, '')
  return v.replace(/\s+/g, ' ').trim() || (days ? `${days[1]} 天` : '')
}

/**
 * @returns {null | Array<[string, string]>}
 */
export function parseOrderCollectedProse(chunk) {
  const text = String(chunk || '')
  if (!text.trim()) return null

  const keyAlt = ALL_KEYS.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')
  const splitRe = new RegExp(
    String.raw`(?:^|[\s\-－—｜|])\s*\*?(${keyAlt})\*?\s*[：:]\s*`,
    'gi'
  )
  const matches = [...text.matchAll(splitRe)]
  if (matches.length < 2) return null

  const pairs = []
  for (let i = 0; i < matches.length; i++) {
    const key = matches[i][1]
    const start = matches[i].index + matches[i][0].length
    const end = i + 1 < matches.length ? matches[i + 1].index : text.length
    let val = text.slice(start, end).trim()
    val = val.replace(/^[-－—]\s*/, '').replace(/\s*[-－—]\s*$/, '').trim()
    val = val.replace(/\*+/g, '').replace(/[。；;]+$/, '').trim()
    if (!val) continue
    const label = canonicalLabel(key)
    if (label === 'partId' || /物料ID/i.test(key)) {
      pairs.push(...expandMaterialIdValue(val))
      continue
    }
    if (label === '预计交货') {
      pairs.push([label, cleanDeliveryValue(val)])
      continue
    }
    // 供应商值不要吞掉后续「预计…」
    if (label === '供应商') {
      val = val.split(/-\s*预计/)[0].trim()
    }
    if (label === '创建人') {
      val = val.replace(/数据看起来[\s\S]*$/, '').trim()
    }
    pairs.push([label, val])
  }

  // 去重：同 label 保留首次
  const seen = new Set()
  const rows = []
  for (const [k, v] of pairs) {
    if (seen.has(k)) continue
    seen.add(k)
    rows.push([k, v])
  }
  return rows.length >= 3 ? rows : null
}

export function orderCollectedRegionRegex() {
  return /(\*{0,2}已收集的(?:订单)?数据\*{0,2}[：:]?)([\s\S]*?)(?=数据看起来|让我先进行|让我直接|不过按照|Schema\s*校验|必填字段|现在可以创建|我还需要确认|请问 |\n#{1,3}\s|$)/
}
