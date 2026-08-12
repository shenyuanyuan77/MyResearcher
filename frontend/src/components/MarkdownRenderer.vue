<template>
  <div class="markdown-renderer" ref="rootRef" v-html="renderedContent"></div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import { normalizeMarkdown, reportTablesHealthy, injectMonthlyTrendLineChart, isKnownImageHost, findKnownImageUrls } from '../utils/markdown.js'

/**
 * Markdown 渲染组件
 *
 * 设计原则：
 *  - XSS：默认关闭 html，图片/链接属性强制转义
 *  - 视觉：颜色、字号、圆角、间距、动效全部走 design-token
 *  - 优先级徽章：DOM 操作（避免对渲染产物的脆弱正则）
 */

const props = defineProps({
  content: { type: String, default: '' },
  citations: { type: Array, default: null },  // 结构化引用 [{idx,title,authors,doi,doi_url,...}]，供 [n] 角标气泡
})

const renderedContent = ref('')
const rootRef = ref(null)
let md = null

// 内联 style：保证在任何容器都能正确缩放
const IMG_STYLE =
  'max-width:100%;max-height:420px;width:100%;height:auto;object-fit:contain;' +
  'display:block;border-radius:var(--r-md);margin:0;box-shadow:var(--sh-sm);box-sizing:border-box;'

function escapeAttr(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function isImageExt(src) {
  return /\.(png|jpe?g|gif|webp|svg|bmp|avif)(\?.*)?$/i.test(src) || /^data:image\//i.test(src)
}

function shouldRenderAsImage(src) {
  return isImageExt(src) || isKnownImageHost(src)
}

function buildImgTag(src, alt) {
  const safeSrc = escapeAttr(src)
  const safeAlt = escapeAttr(alt || '图片')
  return (
    `<figure class="md-figure">` +
    `<img src="${safeSrc}" alt="${safeAlt}" class="markdown-image" ` +
    `loading="lazy" decoding="async" referrerpolicy="no-referrer" ` +
    `style="${IMG_STYLE}" />` +
    `</figure>`
  )
}

function buildImageLink(src, alt) {
  const safeSrc = escapeAttr(src)
  const safeAlt = escapeAttr(alt || src || '图片')
  return (
    `<a href="${safeSrc}" target="_blank" rel="noopener noreferrer" ` +
    `class="image-link md-link"><span class="md-image-glyph" aria-hidden="true">` +
    `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/></svg>` +
    `</span>${safeAlt}</a>`
  )
}

onMounted(() => {
  md = new MarkdownIt({
    html: false,          // 安全：默认拒绝原始 HTML
    xhtmlOut: true,
    breaks: true,         // 软换行 <br>
    linkify: true,
    typographer: true,
    highlight(str, lang) {
      // mermaid 图表：输出占位容器，由 enhanceMermaid() 异步渲染
      if (lang === 'mermaid') {
        return `<div class="mermaid">${escapeHtml(str)}</div>`
      }
      if (lang && hljs.getLanguage(lang)) {
        try {
          return `<pre class="hljs"><code class="hljs language-${escapeAttr(lang)}">${hljs.highlight(str, { language: lang }).value}</code></pre>`
        } catch (_) {}
      }
      return `<pre class="hljs"><code class="hljs">${escapeHtml(str)}</code></pre>`
    },
  })
  md.enable(['table'])

  // 宽表横向滚动容器
  const defOpen = md.renderer.rules.table_open || ((t, i, o, e, s) => s.renderToken(t, i, o))
  md.renderer.rules.table_open = (t, i, o, e, s) => '<div class="md-table-wrap">' + defOpen(t, i, o, e, s)
  const defClose = md.renderer.rules.table_close || ((t, i, o, e, s) => s.renderToken(t, i, o))
  md.renderer.rules.table_close = (t, i, o, e, s) => defClose(t, i, o, e, s) + '</div>'

  // 图片规则
  md.renderer.rules.image = (tokens, idx) => {
    const token = tokens[idx]
    const srcIdx = token.attrIndex('src')
    const src = srcIdx >= 0 ? token.attrs[srcIdx][1] : ''
    const alt = token.content || ''
    return shouldRenderAsImage(src) ? buildImgTag(src, alt) : buildImageLink(src, alt)
  }

  // 文本规则：捕获 base64 / CDN 裸链接
  const defText = md.renderer.rules.text || ((tokens, idx) => md.utils.escapeHtml(tokens[idx].content))
  md.renderer.rules.text = (tokens, idx, options, env, self) => {
    const content = tokens[idx].content
    const dataImg = content.match(/(data:image\/[a-zA-Z0-9+]+;base64,[A-Za-z0-9+/=]+)/)
    if (dataImg) return buildImgTag(dataImg[1], '图片')
    const urls = findKnownImageUrls(content)
    if (urls.length) return urls.map((u) => buildImgTag(u, '图片')).join('')
    return defText(tokens, idx, options, env, self)
  }

  // 链接强制安全
  const defLinkOpen = md.renderer.rules.link_open || ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options))
  md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
    const token = tokens[idx]
    const hrefIdx = token.attrIndex('href')
    const href = hrefIdx >= 0 ? token.attrs[hrefIdx][1] : ''
    const tIdx = token.attrIndex('target')
    if (tIdx < 0) {
      token.attrSet('target', '_blank')
      token.attrSet('rel', 'noopener noreferrer')
    } else {
      if (/^https?:\/\//i.test(href)) token.attrSet('rel', 'noopener noreferrer')
    }
    if (href.includes('doi.org')) token.attrSet('class', 'doi-link')
    return defLinkOpen(tokens, idx, options, env, self)
  }

  renderContent()
})

function renderContent() {
  if (!md || !props.content) {
    renderedContent.value = escapeHtml(props.content || '')
    return
  }
  try {
    const looksDash =
      /科研仪表盘|文献检索趋势|本月文献量/.test(props.content) ||
      (/\|\s*(?:列\s*[12]|项目)\s*\|/.test(props.content) &&
        /(?:\d{1,2}\s*月|20\d{2}-\d{2})/.test(props.content))
    const fixed =
      looksDash || !reportTablesHealthy(props.content)
        ? normalizeMarkdown(props.content)
        : props.content
    const html = md.render(fixed)
    renderedContent.value = injectMonthlyTrendLineChart(html, fixed)
    nextTick(() => {
      enhancePriorityCellsDOM()
      enhanceCitations()
      enhanceMermaid()
    })
  } catch (error) {
    console.warn('[MarkdownRenderer] 渲染失败：', error)
    renderedContent.value = escapeHtml(props.content)
  }
}

/**
 * 把正文中的 [n] 文本转成可悬停的引用角标（title 气泡显示该篇文献信息）。
 * citations 来自学术工具的结构化 references；无 citations 时仅美化 [n] 不弹气泡。
 */
function enhanceCitations() {
  const root = rootRef.value
  if (!root) return
  // 仅处理段落、列表、引用块内的文本（不动表格/代码块）
  const targets = root.querySelectorAll('p, li, blockquote, h1, h2, h3, h4, h5, h6, td')
  const citeMap = {}
  if (Array.isArray(props.citations)) {
    for (const c of props.citations) {
      const i = c.idx || 0
      if (i) citeMap[i] = c
    }
  }
  targets.forEach((el) => {
    if (el.dataset && el.dataset.citeEnhanced) return
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null)
    const nodes = []
    let n
    while ((n = walker.nextNode())) nodes.push(n)
    for (const node of nodes) {
      const txt = node.nodeValue || ''
      if (!/\[\d{1,4}\]/.test(txt)) continue
      const frag = document.createDocumentFragment()
      let last = 0
      const re = /\[(\d{1,4})\]/g
      let m
      while ((m = re.exec(txt))) {
        const num = parseInt(m[1], 10)
        // 仅当 num 在 citeMap 中才转为可点击角标；否则保留原文（避免非引用 [123] 误转）
        const c = citeMap[num]
        if (!c) continue
        if (m.index > last) frag.appendChild(document.createTextNode(txt.slice(last, m.index)))
        const sup = document.createElement('sup')
        sup.className = 'cite-ref'
        sup.textContent = `[${num}]`
        const auth = Array.isArray(c.authors) && c.authors.length
          ? (c.authors.slice(0, 2).join(', ') + (c.authors.length > 2 ? ' 等' : ''))
          : '佚名'
        sup.title = `${c.title || '（无标题）'}\n${auth}${c.year ? ' (' + c.year + ')' : ''}${c.venue ? ', ' + c.venue : ''}${c.doi_url ? '\n' + c.doi_url : ''}`
        sup.dataset.idx = String(num)
        if (c.doi_url) {
          sup.style.cursor = 'pointer'
          sup.addEventListener('click', () => window.open(c.doi_url, '_blank', 'noopener'))
        }
        frag.appendChild(sup)
        last = m.index + m[0].length
      }
      if (last === 0) continue  // 无匹配，跳过替换
      if (last < txt.length) frag.appendChild(document.createTextNode(txt.slice(last)))
      node.parentNode.replaceChild(frag, node)
    }
    el.dataset.citeEnhanced = '1'
  })
}

function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

/**
 * 用 DOM 操作把"优先级"列的单元格替换为徽章。
 * 不再依赖对 markdown-it 输出 HTML 的脆弱正则。
 */
function enhancePriorityCellsDOM() {
  const root = rootRef.value
  if (!root) return
  const tables = root.querySelectorAll('table')
  for (const table of tables) {
    const ths = table.querySelectorAll('thead th')
    let priIdx = -1
    ths.forEach((th, i) => {
      const t = (th.textContent || '').replace(/\s+/g, '').trim()
      if (t === '优先级' || t.includes('优先级')) priIdx = i
    })
    if (priIdx < 0) continue
    table.querySelectorAll('tbody tr').forEach((tr) => {
      const tds = tr.querySelectorAll('td')
      const td = tds[priIdx]
      if (!td || td.classList.contains('md-priority')) return
      const raw = td.textContent || ''
      const level = priorityLevel(raw)
      if (!level) return
      td.classList.add('md-priority', `md-priority-${level}`)
      const label = priorityLabel(raw, level)
      td.innerHTML =
        `<span class="md-priority-badge"><span class="md-priority-dot" aria-hidden="true"></span>${escapeHtml(label)}</span>`
    })
  }
}

/**
 * 异步渲染 mermaid 图表（思维导图/流程图/时序图，用于跨界推演、方向构建）。
 * 动态 import 避免撑大首屏 bundle；跟随系统暗色。
 */
let _mermaidReady = null
async function ensureMermaid() {
  if (_mermaidReady) return _mermaidReady
  _mermaidReady = import('mermaid').then((mod) => {
    const mermaid = mod.default || mod
    const dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
    mermaid.initialize({
      startOnLoad: false,
      theme: dark ? 'dark' : 'default',
      securityLevel: 'loose',
      fontFamily: 'inherit',
    })
    return mermaid
  })
  return _mermaidReady
}

async function enhanceMermaid() {
  const root = rootRef.value
  if (!root) return
  const nodes = root.querySelectorAll('.mermaid')
  if (!nodes.length) return
  try {
    const mermaid = await ensureMermaid()
    // 清理已渲染标记，重新跑
    for (const n of nodes) {
      if (n.dataset.rendered) continue
      n.removeAttribute('data-processed')
      const code = n.textContent || ''
      n.setAttribute('data-code', code)
    }
    await mermaid.run({ nodes: Array.from(nodes).filter((n) => !n.dataset.rendered) })
    for (const n of nodes) n.dataset.rendered = '1'
  } catch (e) {
    console.warn('[MarkdownRenderer] mermaid 渲染失败：', e)
  }
}

function priorityLevel(raw) {
  const t = raw.replace(/\s+/g, '').trim()
  if (t.includes('紧急')) return 'urgent'
  if (t.includes('高')) return 'high'
  if (t.includes('中')) return 'mid'
  if (t.includes('低')) return 'low'
  return ''
}

function priorityLabel(raw, level) {
  const cleaned = raw
    .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, '')
    .replace(/\uFFFD/g, '')
    .trim()
  const map = { urgent: '紧急', high: '高', mid: '中', low: '低' }
  return map[level] || cleaned || raw
}

watch(() => props.content, () => renderContent())
watch(() => props.citations, () => { nextTick(() => enhanceCitations()) })
</script>

<!-- scoped 块：作用于根容器 -->
<style scoped>
.markdown-renderer {
  font-family: var(--font-body);
  font-size: var(--fz-body);
  line-height: var(--lh-loose);
  color: var(--c-text);
  letter-spacing: var(--tracking-body);
  word-break: break-word;
  overflow-wrap: break-word;
  overflow: hidden;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}
</style>

<!-- 非 scoped：作用于 v-html 注入的内容 -->
<style>
.markdown-renderer :is(h1, h2, h3, h4, h5, h6) {
  font-family: var(--font-display);
  color: var(--c-text);
  letter-spacing: var(--tracking-display);
  font-weight: 600;
  line-height: var(--lh-tight);
}
.markdown-renderer h1 {
  font-size: var(--fz-h1);
  margin: 28px 0 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--c-border);
}
.markdown-renderer h2 {
  font-size: var(--fz-h2);
  margin: 22px 0 12px;
}
.markdown-renderer h3 { font-size: var(--fz-h3); margin: 18px 0 10px; }
.markdown-renderer h4 { font-size: 16px; margin: 16px 0 8px; color: var(--c-text-secondary); }
.markdown-renderer h5, .markdown-renderer h6 { font-size: 14px; margin: 14px 0 6px; color: var(--c-text-secondary); }

.markdown-renderer p { margin: 10px 0; }

.markdown-renderer ul, .markdown-renderer ol { margin: 10px 0; padding-left: 28px; }
.markdown-renderer li { margin: 6px 0; }
.markdown-renderer ul li { list-style-type: disc; }
.markdown-renderer ol li { list-style-type: decimal; }
.markdown-renderer li::marker { color: var(--c-text-tertiary); }

/* ============ 行内 code ============ */
.markdown-renderer code {
  font-family: var(--font-mono);
  font-size: 0.92em;
  padding: 2px 6px;
  background: var(--c-surface-alt);
  border: 1px solid var(--c-border-light);
  border-radius: var(--r-xs);
  color: var(--c-text);
}

/* ============ 代码块 ============ */
.markdown-renderer pre {
  margin: 14px 0;
  padding: 16px 18px;
  background: #0d0d10;
  border-radius: var(--r-md);
  overflow-x: auto;
  box-shadow: var(--sh-sm);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.65;
  color: #e5e5ea;
}
.markdown-renderer pre code {
  padding: 0; background: none; border: none; color: inherit; font-size: inherit;
}
.markdown-renderer .hljs { background: transparent; color: #e5e5ea; }
.markdown-renderer .hljs-keyword,
.markdown-renderer .hljs-selector-tag,
.markdown-renderer .hljs-built_in,
.markdown-renderer .hljs-name,
.markdown-renderer .hljs-tag { color: #ff7b72; }
.markdown-renderer .hljs-string,
.markdown-renderer .hljs-title,
.markdown-renderer .hljs-section,
.markdown-renderer .hljs-attribute,
.markdown-renderer .hljs-literal,
.markdown-renderer .hljs-template-tag,
.markdown-renderer .hljs-template-variable,
.markdown-renderer .hljs-type { color: #a5d6ff; }
.markdown-renderer .hljs-comment,
.markdown-renderer .hljs-quote,
.markdown-renderer .hljs-deletion,
.markdown-renderer .hljs-meta { color: #8b8b94; font-style: italic; }
.markdown-renderer .hljs-number,
.markdown-renderer .hljs-regexp,
.markdown-renderer .hljs-variable { color: #d2a8ff; }
.markdown-renderer .hljs-function .hljs-title { color: #79c0ff; }

/* ============ 链接 ============ */
.markdown-renderer a,
.markdown-renderer .md-link {
  color: var(--c-primary);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: color var(--transition-fast), border-color var(--transition-fast);
}
.markdown-renderer a:hover { border-bottom-color: var(--c-primary); }

/* ============ DOI 链接（学术溯源，视觉区分） ============ */
.markdown-renderer a.doi-link,
.markdown-renderer a[href*="doi.org"] {
  color: var(--c-primary);
  font-weight: 600;
  border-bottom: none;
}
.markdown-renderer a.doi-link::before,
.markdown-renderer a[href*="doi.org"]::before {
  content: '🔗 ';
}

/* ============ 引用角标 [n]（学术引用） ============ */
.markdown-renderer .cite-ref {
  color: var(--c-primary);
  font-size: 0.72em;
  font-weight: 700;
  padding: 0 2px;
  cursor: default;
  white-space: nowrap;
  transition: background var(--transition-fast);
  border-radius: 3px;
}
.markdown-renderer .cite-ref:hover {
  background: var(--c-primary-soft);
  text-decoration: underline;
}
.markdown-renderer .cite-ref[title] {
  cursor: help;
}
.markdown-renderer .cite-ref[data-idx] {
  cursor: pointer;
}

/* ============ 图片 ============ */
.markdown-renderer .md-figure {
  display: block;
  width: 100%;
  max-width: 100%;
  clear: both;
  margin: 16px 0;
  box-sizing: border-box;
}
.markdown-renderer img.markdown-image {
  max-width: 100% !important;
  max-height: 420px;
  width: 100%;
  height: auto;
  object-fit: contain;
  border-radius: var(--r-md);
  margin: 0;
  display: block;
  box-shadow: var(--sh-sm);
  box-sizing: border-box;
}
.markdown-renderer a.image-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: var(--c-surface-alt);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  margin: 10px 0;
  color: var(--c-primary);
  font-size: 13px;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}
.markdown-renderer a.image-link:hover {
  background: var(--c-primary-soft);
  border-color: var(--c-primary);
}
.markdown-renderer .md-image-glyph {
  display: inline-flex;
  align-items: center;
  color: var(--c-text-tertiary);
}

/* ============ 表格 ============ */
.markdown-renderer .md-table-wrap {
  display: block;
  width: 100%;
  max-width: 100%;
  clear: both;
  overflow-x: auto;
  margin: 16px 0;
  border-radius: var(--r-lg);
  border: 1px solid var(--c-border);
  background: var(--c-surface);
  box-shadow: var(--sh-xs);
}
.markdown-renderer table {
  width: 100%;
  border-collapse: collapse;
  margin: 0;
  font-size: var(--fz-caption);
  table-layout: auto;
  font-variant-numeric: tabular-nums;
}
.markdown-renderer th, .markdown-renderer td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--c-border-light);
  text-align: left;
  white-space: nowrap;
  word-break: keep-all;
  overflow-wrap: normal;
  color: var(--c-text);
}
.markdown-renderer th {
  background: var(--c-surface-alt);
  font-weight: 600;
  font-size: var(--fz-caption);
  color: var(--c-text-secondary);
  position: sticky;
  top: 0;
  border-bottom: 1px solid var(--c-border);
}
.markdown-renderer tbody tr:nth-child(even) td { background: rgba(0, 0, 0, .02); }
@media (prefers-color-scheme: dark) {
  .markdown-renderer tbody tr:nth-child(even) td { background: rgba(255, 255, 255, .03); }
}
.markdown-renderer tbody tr:hover td { background: var(--c-primary-soft); }
.markdown-renderer tbody tr:last-child td { border-bottom: none; }

/* ============ 优先级徽章（DOM 注入后样式生效） ============ */
.markdown-renderer td.md-priority {
  text-align: center;
  vertical-align: middle;
  white-space: nowrap;
}
.markdown-renderer .md-priority-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fz-caption);
  font-weight: 500;
}
.markdown-renderer .md-priority-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  display: inline-block;
}
.markdown-renderer .md-priority-urgent .md-priority-dot { background: var(--c-accent); }
.markdown-renderer .md-priority-high .md-priority-dot { background: var(--c-danger); }
.markdown-renderer .md-priority-mid .md-priority-dot { background: var(--c-warning); }
.markdown-renderer .md-priority-low .md-priority-dot { background: var(--c-success); }

/* ============ 引用 ============ */
.markdown-renderer blockquote {
  margin: 14px 0;
  padding: 12px 16px;
  background: var(--c-surface-alt);
  border-left: 3px solid var(--c-primary);
  border-radius: 0 var(--r-sm) var(--r-sm) 0;
  color: var(--c-text-secondary);
}

/* ============ 分割线 ============ */
.markdown-renderer hr {
  border: none;
  height: 1px;
  background: var(--c-border);
  margin: 24px 0;
}

/* ============ 任务列表 ============ */
.markdown-renderer input[type="checkbox"] {
  margin-right: 8px;
  vertical-align: middle;
  accent-color: var(--c-primary);
}
.markdown-renderer input[type="checkbox"]:checked + * {
  color: var(--c-text-tertiary);
  text-decoration: line-through;
}

/* ============ 月度趋势图 ============ */
.markdown-renderer .md-line-chart {
  display: block;
  width: 100%;
  max-width: 100%;
  margin: 12px 0 8px;
  border-radius: var(--r-md);
  border: 1px solid var(--c-border);
  overflow: hidden;
  background: var(--c-surface);
  box-shadow: var(--sh-xs);
}
.markdown-renderer .md-line-chart svg {
  display: block;
  width: 100%;
  height: auto;
  min-height: 280px;
}

/* ============ 键盘元素 ============ */
.markdown-renderer kbd {
  font-family: var(--font-mono);
  font-size: 12px;
  padding: 2px 6px;
  border-radius: var(--r-xs);
  border: 1px solid var(--c-border);
  background: var(--c-surface-alt);
  color: var(--c-text-secondary);
  box-shadow: 0 1px 0 var(--c-border-strong);
}

/* ============ 链接图标 ============ */
.markdown-renderer a[href^="http"]::after {
  content: "";
}

/* ============ 行内强调 ============ */
.markdown-renderer strong { font-weight: 600; color: var(--c-text); }
.markdown-renderer em { font-style: italic; }
</style>
