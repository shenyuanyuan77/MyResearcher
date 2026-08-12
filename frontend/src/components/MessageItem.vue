<template>
  <!-- 用户消息：左头像 + 浅蓝气泡 -->
  <div v-if="message.role === 'user'" class="message-item message-user">
    <div class="message-avatar">
      <div class="avatar user-avatar" aria-hidden="true">
        <AppIcon name="user" :size="18" filled color="#ffffff" />
      </div>
    </div>
    <div class="message-content-wrapper">
      <div class="message-content">
        <div class="content-text">{{ message.content }}</div>
      </div>
      <div class="message-time">{{ formatMessageTime(message) }}</div>
    </div>
  </div>

  <!-- AI 助手消息 -->
  <div
    v-else-if="message.role === 'assistant'"
    class="message-item message-assistant"
    :class="{ streaming: isStreaming }"
  >
    <div class="message-avatar">
      <div class="avatar assistant-avatar" aria-hidden="true">
        <AppIcon name="sparkles" :size="18" color="#ffffff" />
      </div>
    </div>
    <div class="message-content-wrapper">
      <div v-if="showThinking" class="thinking-panel">
        <div class="thinking-row">
          <span class="thinking-spinner" aria-hidden="true"></span>
          <span class="thinking-label">{{ thinkingLabel }}</span>
        </div>
        <div class="thinking-hint">模型正在处理，请稍候…</div>
      </div>
      <div v-else class="message-content">
        <MarkdownRenderer :content="sanitizeAssistantContent(message.content)" />
        <span v-if="isStreaming && message.content" class="typing-cursor" aria-hidden="true"></span>
      </div>
      <!-- 助手消息操作栏（复制 / 引用回复；仅非流式时显示） -->
      <div v-if="!showThinking && !isStreaming && message.content" class="message-actions">
        <button class="msg-action-btn" @click="copyContent" :title="copied ? '已复制' : '复制'">
          <AppIcon :name="copied ? 'check' : 'copy'" :size="13" />
          <span>{{ copied ? '已复制' : '复制' }}</span>
        </button>
        <button class="msg-action-btn" @click="$emit('quote-reply', message)" title="引用回复">
          <AppIcon name="reply" :size="13" />
          <span>引用</span>
        </button>
      </div>
      <div v-if="!showThinking" class="message-time">{{ formatMessageTime(message) }}</div>
    </div>
  </div>

  <!-- 工具调用消息 -->
  <div v-else-if="message.role === 'tool'" class="message-item message-tool-inline">
    <div class="message-avatar">
      <div class="avatar tool-avatar" aria-hidden="true">
        <AppIcon name="sparkles" :size="18" color="#ffffff" />
      </div>
    </div>
    <div class="message-content-wrapper tool-card">
      <div class="tool-card-header">
        <div class="tool-tags">
          <span class="tag tool-tag">工具</span>
          <span class="tag name-tag">{{ formatToolName(message.tool_name) }}</span>
        </div>
        <div class="tool-aside">
          <span v-if="message.tool_status === 'calling'" class="status-badge calling">
            {{ isEmitReportTool ? '生成中' : '执行中' }}
          </span>
          <span v-else-if="hasToolContent" class="status-badge done">完成</span>
          <span class="message-time inline">{{ formatMessageTime(message) }}</span>
        </div>
      </div>

      <div v-if="message.args && !hideToolArgs" class="tool-block">
        <div class="tool-label">参数</div>
        <div class="tool-value mono">{{ formatArgs(message.args) }}</div>
      </div>

      <div v-if="message.text && !(isEmitReportTool && message.tool_status === 'calling')" class="tool-block">
        <div class="tool-label">结果</div>
        <div class="tool-result-box">
          <span class="code-chip" aria-hidden="true">{ }</span>
          <div class="tool-result-text">
            <MarkdownRenderer :content="cleanText(message.text)" :citations="message.references" />
          </div>
        </div>
      </div>

      <!-- 学术文献富卡片（结构化引用，来自学术工具 references） -->
      <div v-if="refCards.length > 0" class="tool-block">
        <div class="tool-label">文献（{{ refCards.length }} 篇，带真实 DOI 可溯源）</div>
        <div class="ref-card-grid">
          <div v-for="r in refCards" :key="r.doi || r.title || r.idx" class="ref-card">
            <div class="ref-card-head">
              <span class="ref-idx">[{{ r.idx || 1 }}]</span>
              <a v-if="r.doi_url" :href="r.doi_url" target="_blank" rel="noopener noreferrer" class="ref-doi-btn">🔗 DOI</a>
              <a v-if="r.oa_url" :href="r.oa_url" target="_blank" rel="noopener noreferrer" class="ref-oa-btn">PDF</a>
            </div>
            <div class="ref-title">{{ r.title || '（无标题）' }}</div>
            <div class="ref-authors">{{ formatAuthors(r.authors) }}<span v-if="r.year"> · {{ r.year }}</span><span v-if="r.venue"> · {{ r.venue }}</span></div>
            <div class="ref-meta">
              <span v-if="r.cited_by_count !== null && r.cited_by_count !== undefined" class="ref-cite">被引 {{ r.cited_by_count }}</span>
              <span v-if="r.source" class="ref-source">{{ refSourceLabel(r.source) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="displayToolImages.length > 0" class="tool-inline-images">
        <div
          v-for="(img, imgIdx) in displayToolImages"
          :key="imgIdx"
          class="tool-image-wrapper"
        >
          <img
            :src="img"
            :alt="`图表 ${imgIdx + 1}`"
            class="tool-result-image"
            loading="lazy"
            referrerpolicy="no-referrer"
            decoding="async"
            @click="previewImage(img)"
          />
        </div>
      </div>

      <div v-if="message.tool_status === 'calling' && !hasToolContent && !isEmitReportTool" class="tool-waiting">
        <span class="waiting-dot"></span>
        <span class="waiting-dot"></span>
        <span class="waiting-dot"></span>
        <span class="waiting-text">执行中…</span>
      </div>
    </div>
  </div>

  <!-- 图片 lightbox 预览（替代 window.open，支持 a11y dialog） -->
  <transition name="fade">
    <div
      v-if="lightboxSrc"
      class="lightbox-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="图片预览"
      @click="closeLightbox"
      @keydown.esc="closeLightbox"
      tabindex="-1"
      ref="lightboxOverlay"
    >
      <img :src="lightboxSrc" :alt="lightboxAlt" class="lightbox-img" @click.stop />
      <button class="lightbox-close" @click="closeLightbox" aria-label="关闭">×</button>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  message: { type: Object, required: true },
  isStreaming: { type: Boolean, default: false },
})

defineEmits(['quote-reply'])

// 复制状态
const copied = ref(false)
async function copyContent() {
  try {
    const text = props.message.content || ''
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // fallback
    const ta = document.createElement('textarea')
    ta.value = props.message.content || ''
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy') } catch {}
    document.body.removeChild(ta)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }
}

// 思考文案：根据当前工具调用动态匹配，不命中走通用阶段
const TOOL_THINKING_MAP = {
  topic_radar: ['正在检索领域热度趋势…', '正在分析关键词与检索式…'],
  paper_search: ['正在检索权威学术数据库…', '正在多源归并文献并锚定 DOI…'],
  paper_search_cn: ['正在检索中文学术文献…', '正在归并中文与英文结果…'],
  paper_by_doi: ['正在 CrossRef 校验 DOI…', '正在补全摘要与引用…'],
  paper_by_dois: ['正在批量核验 DOI…', '正在归并结果…'],
  paper_distill: ['正在精读文献…', '正在提炼创新点与方法…'],
  paper_cited_by: ['正在检索施引文献…'],
  paper_references: ['正在检索参考文献…'],
  related_papers: ['正在检索相关文献…'],
  author_profile: ['正在构建学者画像…', '正在统计 h 指数与代表作…'],
  cross_search: ['正在检索交叉工作…', '正在推演跨界融合路径…'],
  web_search: ['正在搜索网络资源…'],
}
const THINKING_STEPS_GENERIC = [
  '正在检索权威学术数据库…',
  '正在多源归并文献并锚定 DOI…',
  '正在精读文献并提炼创新点…',
  '正在推演跨界融合路径…',
]

const thinkingStep = ref(0)
let thinkingTimer = null
let thinkingStartedAt = 0

const showThinking = computed(() => {
  if (props.message.role !== 'assistant') return false
  if (props.message.content) return false
  return !!(props.message.thinking || props.isStreaming)
})

// 根据当前消息关联的工具调用动态选择思考文案
const activeThinkingSteps = computed(() => {
  const toolCalls = props.message.tool_calls || []
  for (const tc of toolCalls) {
    const name = tc.name || (tc.tool_name) || ''
    if (TOOL_THINKING_MAP[name]) return TOOL_THINKING_MAP[name]
  }
  return THINKING_STEPS_GENERIC
})

const thinkingLabel = computed(() => activeThinkingSteps.value[thinkingStep.value] || activeThinkingSteps.value[0] || '思考中…')

function startThinkingTimer() {
  stopThinkingTimer()
  thinkingStartedAt = Date.now()
  thinkingStep.value = 0
  thinkingTimer = setInterval(() => {
    const elapsed = (Date.now() - thinkingStartedAt) / 1000
    const steps = activeThinkingSteps.value
    // 按经过时间推进步骤（不超过该工具的文案数）
    const stepCount = steps.length
    if (stepCount <= 1) {
      thinkingStep.value = 0
    } else {
      const perStep = Math.max(4, 20 / stepCount)
      thinkingStep.value = Math.min(Math.floor(elapsed / perStep), stepCount - 1)
    }
  }, 800)
}

function stopThinkingTimer() {
  if (thinkingTimer) {
    clearInterval(thinkingTimer)
    thinkingTimer = null
  }
}

watch(showThinking, (on) => {
  if (on) startThinkingTimer()
  else stopThinkingTimer()
}, { immediate: true })

onUnmounted(() => stopThinkingTimer())

const isEmitReportTool = computed(() =>
  String(props.message?.tool_name || '').includes('emit_research_report')
)

const hideToolArgs = computed(() =>
  !!(props.message?.hide_args || isEmitReportTool.value)
)

const displayToolImages = computed(() => {
  const images = props.message?.images || []
  if (!images.length) return []
  const text = String(props.message?.text || '')
  if (!text.includes('![')) return images
  return images.filter((img) => {
    const u = String(img || '')
    if (!u) return false
    if (text.includes(u)) return false
    const base = u.split('?')[0]
    return !(base && text.includes(base))
  })
})

// 学术文献富卡片：从 message.references 提取（限制最多 12 张避免过长）
const refCards = computed(() => {
  const refs = props.message?.references
  if (!Array.isArray(refs) || !refs.length) return []
  return refs.slice(0, 12).map((r, i) => ({
    idx: r.idx || i + 1,
    title: r.title || '',
    authors: r.authors || [],
    year: r.year,
    venue: r.venue || '',
    cited_by_count: r.cited_by_count,
    doi: r.doi || '',
    doi_url: r.doi_url || (r.doi ? `https://doi.org/${r.doi}` : ''),
    oa_url: r.oa_url || '',
    source: r.source || '',
  }))
})

function formatAuthors(authors) {
  if (!Array.isArray(authors) || !authors.length) return '佚名'
  const visible = authors.slice(0, 2).join(', ')
  return authors.length > 2 ? `${visible} 等` : visible
}

function refSourceLabel(src) {
  const m = { crossref: 'CrossRef', openalex: 'OpenAlex', s2: 'Semantic Scholar' }
  return m[src] || src
}

const hasToolContent = computed(() => {
  return !!(
    props.message.text ||
    (displayToolImages.value && displayToolImages.value.length > 0)
  )
})

// 图片预览：lightbox modal（替代 window.open，支持 a11y dialog）
const lightboxSrc = ref('')
const lightboxAlt = ref('')
function previewImage(src) {
  lightboxSrc.value = src
  lightboxAlt.value = '图片预览'
}
function closeLightbox() {
  lightboxSrc.value = ''
}

function formatMessageTime(m) {
  const ts = m?.created_at || m?.timestamp || m?.time
  const d = ts ? new Date(ts) : new Date()
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatToolName(name) {
  if (!name) return '未知工具'
  const map = {
    topic_radar: '方向构建',
    paper_search: '文献检索',
    paper_by_doi: 'DOI溯源',
    paper_distill: '文献精读',
    author_profile: '学者透视',
    cross_search: '跨界检索',
    web_search: '网络搜索',
    write_markdown_table: '生成表格',
    emit_research_report: '发布报告',
    save_report_locally: '保存报告',
    get_system_date: '系统日期',
    task: '委派子Agent',
  }
  if (map[name]) return map[name]
  // 未知工具：清理原始名称作为兜底
  return String(name).replace(/[_-]+/g, ' ').trim() || String(name)
}

function formatArgs(args) {
  if (!args) return '—'
  try {
    const parsed = typeof args === 'string' ? JSON.parse(args) : args
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return Object.entries(parsed)
        .map(([k, v]) => `${k} = ${typeof v === 'string' ? v : JSON.stringify(v)}`)
        .join('\n')
    }
    return JSON.stringify(parsed, null, 2)
  } catch {
    return String(args)
  }
}

function cleanText(text) {
  if (!text) return ''
  let cleaned = text
  cleaned = cleaned.replace(/,?\s*'id':\s*'[^']*'/g, '')
  cleaned = cleaned.replace(/,?\s*"id":\s*"[^"]*"/g, '')
  const name = (props.message?.tool_name || '').toLowerCase()
  if (
    (name === 'task' || name.includes('task')) &&
    cleaned.length > 400 &&
    (cleaned.includes('研究报告') || cleaned.includes('分析报告'))
  ) {
    return '子代理分析已完成。完整报告已在下方对话中展示，此处不再重复。'
  }
  return cleaned
}

function sanitizeAssistantContent(text) {
  if (!text) return ''
  let cleaned = String(text)
  // 通用清理：剥离尾部调试 JSON（thread_id / tool_call_id 等内部字段）
  cleaned = cleaned.replace(
    /\s*\{[^{}]*"(?:thread_id|tool_call_id)"[^{}]{0,400}\}\s*$/g,
    ''
  )
  return cleaned.trimEnd()
}
</script>

<style scoped>
.message-item {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 12px;
  width: 100%;
  max-width: var(--content-max);
  margin: 0 auto;
  padding: 8px 0 14px;
  box-sizing: border-box;
  animation: riseIn var(--dur-slow) var(--ease-spring) both;
}

.message-avatar { flex-shrink: 0; padding-top: 2px; }
.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--sh-sm);
}
.user-avatar { background: linear-gradient(180deg, #ffb45c 0%, #ff9f0a 100%); }
.assistant-avatar,
.tool-avatar { background: linear-gradient(180deg, #5b8cff 0%, #007aff 100%); }

.message-content-wrapper {
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.message-user .message-content {
  background: var(--c-user-bubble);
  border-radius: 18px;
  padding: 12px 16px;
  color: var(--c-text);
  box-shadow: none;
  max-width: min(720px, 100%);
}
.message-user .content-text {
  font-size: var(--fz-body);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.message-assistant .message-content {
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 2px 0;
  width: 100%;
  color: var(--c-text);
  font-size: var(--fz-body);
  line-height: 1.7;
}

.message-time {
  font-size: 11px;
  color: var(--c-text-tertiary);
  padding-left: 4px;
}
.message-time.inline {
  padding-left: 0;
}

.thinking-panel {
  background: var(--c-primary-soft);
  border: 1px solid var(--c-primary-soft-strong);
  border-radius: 18px;
  padding: 14px 16px;
  min-width: 220px;
}
.thinking-row { display: flex; align-items: center; gap: 10px; }
.thinking-spinner {
  width: 14px; height: 14px;
  border: 2px solid var(--c-primary-soft-strong);
  border-top-color: var(--c-primary);
  border-radius: 50%;
  animation: thinking-spin .7s linear infinite;
}
.thinking-label { font-size: 14px; font-weight: 500; color: var(--c-primary); }
.thinking-hint { margin-top: 6px; margin-left: 24px; font-size: 12px; color: var(--c-text-tertiary); }
@keyframes thinking-spin { to { transform: rotate(360deg); } }

.tool-card {
  width: 100%;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 18px;
  padding: 14px 16px 16px;
  box-shadow: var(--sh-sm);
}
.tool-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.tool-tags { display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
.tool-tag {
  background: rgba(255, 159, 10, .12);
  color: #c77700;
}
.name-tag {
  background: rgba(255, 159, 10, .10);
  color: #d88900;
}
.tool-aside {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.status-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
.status-badge.done {
  background: var(--c-success-soft);
  color: var(--c-success);
}
.status-badge.calling {
  background: var(--c-warning-soft);
  color: var(--c-warning);
}

.tool-block { margin-top: 10px; }
.tool-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text);
  margin-bottom: 6px;
}
.tool-value {
  font-size: 13px;
  color: var(--c-text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.tool-value.mono { font-family: var(--font-mono); }
.tool-result-box {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--c-surface-alt);
}
.code-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 24px;
  border-radius: 8px;
  background: rgba(0, 0, 0, .04);
  color: var(--c-text-tertiary);
  font-family: var(--font-mono);
  font-size: 12px;
  flex-shrink: 0;
}
.tool-result-text {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--c-text-secondary);
}

.tool-inline-images {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.tool-image-wrapper {
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
  background: var(--c-surface-alt);
}
.tool-result-image {
  width: 100%;
  max-height: 420px;
  object-fit: contain;
  display: block;
  cursor: pointer;
}

/* ===== 学术文献富卡片 ===== */
.ref-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 10px;
  padding-top: 6px;
}
.ref-card {
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  padding: 12px;
  background: var(--c-surface-2);
  display: flex;
  flex-direction: column;
  gap: 5px;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.ref-card:hover { border-color: var(--c-primary); box-shadow: var(--sh-sm); }
.ref-card-head { display: flex; align-items: center; gap: 6px; }
.ref-idx {
  font-size: var(--fz-caption); font-weight: 700; color: var(--c-primary);
  background: var(--c-primary-soft); padding: 2px 7px; border-radius: var(--r-pill);
}
.ref-doi-btn, .ref-oa-btn {
  font-size: var(--fz-mini); padding: 2px 9px; border-radius: var(--r-pill);
  font-weight: 600; text-decoration: none; border: 1px solid var(--c-border);
  transition: all var(--transition-fast);
}
.ref-doi-btn { color: var(--c-primary); border-color: var(--c-primary-soft-strong); }
.ref-doi-btn:hover { background: var(--c-primary); color: #fff; }
.ref-oa-btn { color: var(--c-success); border-color: var(--c-success-soft); }
.ref-oa-btn:hover { background: var(--c-success); color: #fff; }
.ref-title {
  font-size: var(--fz-caption); font-weight: 600; color: var(--c-text);
  line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.ref-authors { font-size: var(--fz-mini); color: var(--c-text-secondary); line-height: 1.4; }
.ref-meta { display: flex; gap: 8px; font-size: var(--fz-mini); color: var(--c-text-tertiary); }
.ref-cite { font-weight: 600; color: var(--c-warning-bright); }
.ref-source { font-style: italic; }

.tool-waiting {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0 0;
}
.waiting-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--c-warning-bright);
  animation: bounce 1.4s infinite var(--ease-ios) both;
}
.waiting-dot:nth-child(1) { animation-delay: -.32s; }
.waiting-dot:nth-child(2) { animation-delay: -.16s; }
.waiting-text { margin-left: 6px; font-size: 12px; color: var(--c-warning); }

.typing-cursor {
  display: inline-block;
  width: 6px;
  height: 15px;
  margin-left: 3px;
  vertical-align: text-bottom;
  background: var(--c-primary);
  border-radius: 2px;
  animation: blink 1.2s var(--ease-ios) infinite;
}

@keyframes blink {
  0%, 60% { opacity: 1; }
  61%, 100% { opacity: 0; }
}
@keyframes bounce {
  0%, 80%, 100% { transform: scale(.4); opacity: .4; }
  40% { transform: scale(1); opacity: 1; }
}

/* 助手消息操作栏（复制 / 引用） */
.message-actions {
  display: flex;
  gap: 4px;
  margin-top: 6px;
  opacity: 0;
  transition: opacity 0.15s;
}
.message-assistant:hover .message-actions { opacity: 1; }
.msg-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 3px 8px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  background: var(--c-surface);
  color: var(--c-text-tertiary);
  font-size: var(--fz-mini);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.msg-action-btn:hover {
  background: var(--c-primary-soft);
  color: var(--c-primary);
  border-color: var(--c-primary);
}

/* 图片 lightbox */
.lightbox-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  cursor: zoom-out;
}
.lightbox-img {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: var(--r-md);
  box-shadow: var(--sh-xl);
  cursor: default;
}
.lightbox-close {
  position: absolute;
  top: 16px;
  right: 24px;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  font-size: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.lightbox-close:hover { background: rgba(255, 255, 255, 0.3); }
</style>
