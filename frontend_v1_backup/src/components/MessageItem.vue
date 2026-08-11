<template>
  <!-- ============================================================ -->
  <!-- 用户消息 - 右侧蓝色气泡 -->
  <!-- ============================================================ -->
  <div v-if="message.role === 'user'" class="message-item message-user">
    <div class="message-content-wrapper">
      <div class="message-content">
        <div class="content-text">{{ message.content }}</div>
      </div>
    </div>
    <div class="message-avatar">
      <div class="avatar user-avatar">👤</div>
    </div>
  </div>

  <!-- ============================================================ -->
  <!-- AI 助手消息 - 左侧，带头部标签栏 -->
  <!-- ============================================================ -->
  <div v-else-if="message.role === 'assistant'" class="message-item message-assistant" :class="{ streaming: isStreaming }">
    <div class="message-avatar">
      <div class="avatar assistant-avatar" :class="getAvatarClass(message.source)">
        {{ getRoleIcon(message.source) }}
      </div>
    </div>
    <div class="message-content-wrapper">
      <!-- 角色标签栏 -->
      <div class="msg-label-bar" :class="getLabelBarClass(message.source)">
        <span class="msg-role-badge">{{ getRoleLabel(message.source) }}</span>
        <span v-if="showSourceBadge(message.source)" class="msg-source-badge">
          {{ getSourceName(message.source) }}
        </span>
      </div>
      <!-- 等待首包：思考中状态 -->
      <div v-if="showThinking" class="thinking-panel">
        <div class="thinking-row">
          <span class="thinking-spinner" aria-hidden="true"></span>
          <span class="thinking-label">{{ thinkingLabel }}</span>
        </div>
        <div class="thinking-hint">研途智探AI 正在处理，请稍候…</div>
      </div>
      <!-- 消息正文 -->
      <div v-else class="message-content">
        <MarkdownRenderer :content="sanitizeAssistantContent(message.content)" />
        <span v-if="isStreaming && message.content" class="typing-cursor">▋</span>
      </div>
    </div>
  </div>

  <!-- ============================================================ -->
  <!-- 工具调用消息 - 左侧，带 Tool 标签栏 -->
  <!-- ============================================================ -->
  <div v-else-if="message.role === 'tool'" class="message-item message-tool-inline">
    <div class="message-avatar">
      <div class="avatar tool-avatar">{{ getToolIcon(message.tool_name) }}</div>
    </div>
    <div class="message-content-wrapper">
      <!-- Tool 标签栏 -->
      <div class="msg-label-bar tool-label-bar">
        <span class="msg-role-badge tool-role-badge">工具</span>
        <span class="msg-tool-name-badge">{{ formatToolName(message.tool_name) }}</span>
        <span v-if="showSourceBadge(message.source)" class="msg-source-badge tool-source-badge">
          {{ getSourceName(message.source) }}
        </span>
        <span v-if="message.tool_status === 'calling'" class="tool-status-badge calling">
          {{ isEmitReportTool ? '生成中' : '执行中' }}
        </span>
        <span v-else-if="hasToolContent" class="tool-status-badge done">完成</span>
      </div>

      <!-- 参数（可折叠）；emit 成稿不展示膨胀 JSON -->
      <div v-if="message.args && !hideToolArgs" class="tool-inline-section">
        <div class="tool-section-header" @click="toggleSection('args')">
          <span class="section-arrow">{{ expandedSections.includes('args') ? '▼' : '▶' }}</span>
          <span class="section-label">参数</span>
        </div>
        <pre v-if="expandedSections.includes('args')" class="tool-inline-code">{{ formatArgs(message.args) }}</pre>
      </div>

      <!-- emit：正文已流式进助手气泡，工具区只显示短状态 -->
      <div v-if="isEmitReportTool && message.tool_status === 'calling'" class="tool-waiting">
        <span class="waiting-dot"></span>
        <span class="waiting-dot"></span>
        <span class="waiting-dot"></span>
        <span class="waiting-text">正在生成完整报告…</span>
      </div>

      <!-- 结果文本（可折叠）；表/报告默认折叠，避免与正文重复刷屏 -->
      <div v-if="message.text && !(isEmitReportTool && message.tool_status === 'calling')" class="tool-inline-section">
        <div class="tool-section-header" @click="toggleSection('result')">
          <span class="section-arrow">{{ expandedSections.includes('result') ? '▼' : '▶' }}</span>
          <span class="section-label">{{ resultSectionLabel }}</span>
        </div>
        <div v-if="expandedSections.includes('result')" class="tool-inline-result">
          <MarkdownRenderer :content="cleanText(message.text)" />
        </div>
      </div>
      <!-- 结果图片：正文已含同 URL 的 markdown 图时不再重复贴图 -->
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
            @click="previewImage(img)"
          />
        </div>
      </div>

      <!-- 等待中动画（非 emit） -->
      <div v-if="message.tool_status === 'calling' && !hasToolContent && !isEmitReportTool" class="tool-waiting">
        <span class="waiting-dot"></span>
        <span class="waiting-dot"></span>
        <span class="waiting-dot"></span>
        <span class="waiting-text">执行中...</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import MarkdownRenderer from './MarkdownRenderer.vue'

const props = defineProps({
  message: { type: Object, required: true },
  isStreaming: { type: Boolean, default: false }
})

const THINKING_STEPS = [
  '正在检索权威学术数据库…',
  '正在多源归并文献并锚定 DOI…',
  '正在精读文献并提炼创新点…',
  '正在推演跨界融合路径…'
]

const thinkingStep = ref(0)
let thinkingTimer = null
let thinkingStartedAt = 0

const showThinking = computed(() => {
  if (props.message.role !== 'assistant') return false
  if (props.message.content) return false
  return !!(props.message.thinking || props.isStreaming)
})

const thinkingLabel = computed(() => THINKING_STEPS[thinkingStep.value] || THINKING_STEPS[0])

function startThinkingTimer() {
  stopThinkingTimer()
  thinkingStartedAt = Date.now()
  thinkingStep.value = 0
  thinkingTimer = setInterval(() => {
    const elapsed = (Date.now() - thinkingStartedAt) / 1000
    if (elapsed >= 20) thinkingStep.value = 3
    else if (elapsed >= 10) thinkingStep.value = 2
    else if (elapsed >= 4) thinkingStep.value = 1
    else thinkingStep.value = 0
  }, 800)
}

function stopThinkingTimer() {
  if (thinkingTimer) {
    clearInterval(thinkingTimer)
    thinkingTimer = null
  }
}

watch(
  showThinking,
  (on) => {
    if (on) startThinkingTimer()
    else stopThinkingTimer()
  },
  { immediate: true }
)

onUnmounted(() => stopThinkingTimer())

// ============================================================
// 工具分类（折叠 / 隐藏参数）
// ============================================================

/** 发布报告：完整报告会流式进入助手气泡，工具区不展示膨胀参数 */
const isEmitReportTool = computed(() =>
  String(props.message?.tool_name || '').includes('emit_research_report')
)

/** 表格 / 报告 / 子代理委派：结果默认折叠，避免与正文重复刷屏 */
const shouldCollapseResult = computed(() => {
  const n = String(props.message?.tool_name || '').toLowerCase()
  return (
    n === 'task' ||
    n.includes('emit_research_report') ||
    n.includes('write_markdown_table') ||
    n.includes('save_report_locally')
  )
})

const hideToolArgs = computed(() =>
  !!(props.message?.hide_args || isEmitReportTool.value)
)

const resultSectionLabel = computed(() => {
  const n = String(props.message?.tool_name || '').toLowerCase()
  if (n.includes('write_markdown_table')) return '结果（表格已生成，点击展开）'
  if (n.includes('emit_research_report')) return '结果（报告已生成，点击展开）'
  if (n.includes('save_report_locally')) return '结果（报告已保存，点击展开）'
  return '结果'
})

/** 正文 markdown 已含的图不再走 images 通道，防止同图双显 */
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

const expandedSections = ref(shouldCollapseResult.value ? [] : ['result'])

const hasToolContent = computed(() => {
  return !!(
    props.message.text ||
    (displayToolImages.value && displayToolImages.value.length > 0)
  )
})

function toggleSection(name) {
  const idx = expandedSections.value.indexOf(name)
  if (idx === -1) { expandedSections.value.push(name) }
  else { expandedSections.value.splice(idx, 1) }
}

function previewImage(src) { window.open(src, '_blank') }

// ============================================================
// AI 消息标签
// ============================================================

/** AI 消息的角色标签文字 */
function getRoleLabel(source) {
  return '研途智探AI'
}

/** AI 消息头像 */
function getRoleIcon(source) {
  return '🎓'
}

/** AI 消息标签栏的 CSS class */
function getLabelBarClass(source) {
  return 'label-bar-main'
}

/** AI 消息头像的 CSS class */
function getAvatarClass(source) {
  return 'avatar-main'
}

/** 非主助手消息展示来源徽章 */
function showSourceBadge(source) {
  return false
}

// ============================================================
// 工具相关
// ============================================================

/** 未知工具名清洗：下划线转空格、首字母大写 */
function cleanRawToolName(name) {
  return String(name)
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim()
}

function formatToolName(name) {
  if (!name) return '未知工具'
  const nameMap = {
    'topic_radar': '方向构建',
    'paper_search': '文献检索',
    'paper_by_doi': 'DOI溯源',
    'paper_distill': '文献精读',
    'author_profile': '学者透视',
    'cross_search': '跨界检索',
    'web_search': '网络搜索',
    'write_markdown_table': '生成表格',
    'emit_research_report': '发布报告',
    'save_report_locally': '保存报告',
    'get_system_date': '系统日期',
    'task': '委派子Agent'
  }
  return nameMap[name] || cleanRawToolName(name)
}

function getSourceName(source) {
  const sourceMap = {
    'main': '研途智探AI',
    'literature-analyst': '文献分析专家',
    'review-expert': '审稿专家'
  }
  if (!source) return '研途智探AI'
  if (sourceMap[source]) return sourceMap[source]
  // UUID / 未知来源：不暴露内部 ID（展示层已用「助手」）
  if (/^[0-9a-fA-F-]{20,}$/.test(source)) return '助手'
  return source
}

function getToolIcon(name) {
  if (!name) return '🔧'
  const lowerName = (name || '').toLowerCase()
  if (lowerName.includes('paper_by_doi') || lowerName.includes('doi')) return '🔗'
  if (lowerName.includes('paper_search') || lowerName.includes('web_search') || lowerName.includes('cross_search')) return '🔍'
  if (lowerName.includes('paper_distill') || lowerName.includes('distill')) return '📖'
  if (lowerName.includes('author_profile') || lowerName.includes('author')) return '👤'
  if (lowerName.includes('topic_radar') || lowerName.includes('radar')) return '🧭'
  if (lowerName.includes('write_markdown_table') || lowerName.includes('table')) return '📋'
  if (lowerName.includes('emit_research_report') || lowerName.includes('report')) return '📝'
  if (lowerName.includes('save_report')) return '💾'
  if (lowerName.includes('get_system_date') || lowerName.includes('date')) return '📅'
  if (lowerName.includes('task')) return '🤝'
  return '🔧'
}

function formatArgs(args) {
  if (!args) return ''
  try { return JSON.stringify(JSON.parse(args), null, 2) }
  catch { return args }
}

/** 清洗工具结果文本：去掉泄漏的内部 id 字段 */
function cleanText(text) {
  if (!text) return ''
  let cleaned = text
  cleaned = cleaned.replace(/,?\s*'id':\s*'[^']*'/g, '')
  cleaned = cleaned.replace(/,?\s*"id":\s*"[^"]*"/g, '')
  return cleaned
}

/** 去掉助手消息尾部泄漏的调试 JSON（内部跟踪字段，用户看不懂） */
function sanitizeAssistantContent(text) {
  if (!text) return ''
  let cleaned = String(text)
  cleaned = cleaned.replace(
    /\s*\{[^{}]*"(?:thread_id|tool_call_id|request_id|trace_id|run_id|session_id|span_id)"[^{}]{0,400}\}\s*$/g,
    ''
  )
  return cleaned.trimEnd()
}
</script>

<style scoped>
/* ============================================================ */
/* 基础布局 */
/* ============================================================ */
.message-item {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  justify-content: center;
}

.message-item.streaming {
  background: linear-gradient(to right, transparent, rgba(14, 165, 233, 0.03), transparent);
}

/* ============================================================ */
/* 角色标签栏（AI 和 Tool 共用） */
/* ============================================================ */
.msg-label-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding: 6px 0;
  flex-wrap: wrap;
}

.msg-role-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.2px;
}

/* 主 Agent AI 标签 */
.label-bar-main .msg-role-badge {
  background: #dbeafe;
  color: #1d4ed8;
}

/* 子 Agent AI 标签 */
.label-bar-sub .msg-role-badge {
  background: #ede9fe;
  color: #7c3aed;
}

/* Tool 标签 */
.tool-label-bar .tool-role-badge {
  background: #fef3c7;
  color: #b45309;
}

.msg-source-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.label-bar-sub .msg-source-badge {
  background: #ddd6fe;
  color: #6d28d9;
}

.tool-source-badge {
  background: #fef9c3;
  color: #a16207;
}

.msg-tool-name-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 700;
  color: #92400e;
  background: #fef9c3;
  font-family: 'Monaco', 'Menlo', 'JetBrains Mono', monospace;
}

.tool-status-badge {
  margin-left: auto;
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 10px;
  font-weight: 600;
}

.tool-status-badge.calling {
  background: #fef3c7;
  color: #b45309;
  animation: pulse 1.5s ease-in-out infinite;
}

.tool-status-badge.done {
  background: #d1fae5;
  color: #065f46;
}

/* ============================================================ */
/* 用户消息（右侧气泡，整列水平居中） */
/* ============================================================ */
.message-user {
  display: grid;
  grid-template-columns: min(800px, calc(100vw - 160px)) 38px;
  justify-content: center;
  align-items: start;
  column-gap: 12px;
  gap: 12px;
}

.message-user .message-content-wrapper {
  width: 100%;
  max-width: 100%;
  display: flex;
  justify-content: flex-end;
  text-align: right;
  box-sizing: border-box;
}

.message-user .message-content {
  background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%);
  border-radius: 18px 18px 6px 18px;
  padding: 14px 18px;
  box-shadow: 0 2px 8px rgba(14, 165, 233, 0.2);
}

.message-user .content-text {
  color: #fff;
  font-size: 15px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.message-user .avatar { background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); }

/* ============================================================ */
/* AI 助手消息（左侧） */
/* ============================================================ */
.message-assistant {
  display: grid;
  grid-template-columns: 38px min(800px, calc(100vw - 160px));
  justify-content: center;
  align-items: start;
  column-gap: 12px;
  gap: 12px;
}

.message-assistant .message-content-wrapper {
  width: 100%;
  max-width: 100%;
  overflow: hidden;
  box-sizing: border-box;
  flex-shrink: 0;
}

.message-assistant .message-content {
  background: #ffffff;
  border: 1px solid var(--c-border);
  border-radius: 6px 14px 14px 14px;
  padding: 16px 20px;
  line-height: 1.75;
  font-size: 14.5px;
  color: var(--c-text);
  overflow: hidden;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  box-shadow: var(--sh-sm);
}

.thinking-panel {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 6px 14px 14px 14px;
  padding: 14px 18px;
  min-width: 240px;
}

.thinking-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.thinking-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid #bae6fd;
  border-top-color: #0284c7;
  border-radius: 50%;
  animation: thinking-spin 0.7s linear infinite;
  flex-shrink: 0;
}

.thinking-label {
  font-size: 14px;
  font-weight: 500;
  color: #0369a1;
}

.thinking-hint {
  margin-top: 6px;
  margin-left: 24px;
  font-size: 12px;
  color: #64748b;
}

@keyframes thinking-spin {
  to { transform: rotate(360deg); }
}

.avatar-main { background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%); }
.avatar-sub { background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%); }

/* ============================================================ */
/* 工具调用消息（左侧） */
/* ============================================================ */
.message-tool-inline {
  display: grid;
  grid-template-columns: 38px min(800px, calc(100vw - 160px));
  justify-content: center;
  align-items: start;
  column-gap: 12px;
  gap: 12px;
}

.message-tool-inline .message-content-wrapper {
  width: 100%;
  max-width: 100%;
  background: #fffdf5;
  border: 1px solid #f5e2b0;
  border-radius: 0 14px 14px 14px;
  padding: 14px 18px;
  overflow: hidden;
  box-sizing: border-box;
}

.message-tool-inline .avatar {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  font-size: 22px !important;
}

/* 工具内容区域 */
.tool-inline-section { margin-top: 8px; }

.tool-section-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 6px 0;
  user-select: none;
  color: #78350f;
  font-size: 13px;
  font-weight: 600;
}

.section-arrow { font-size: 10px; width: 14px; text-align: center; }

.section-label {
  letter-spacing: 0.3px;
  font-size: 12px;
}

.tool-inline-code {
  background: #fffbeb;
  border: 1px solid #fde68a;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-family: 'Monaco', 'Menlo', 'JetBrains Mono', monospace;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 4px 0 0 20px;
  color: #78350f;
  line-height: 1.6;
  max-height: 200px;
  overflow-y: auto;
}

.tool-inline-result {
  margin: 4px 0 0 20px;
  padding: 10px 14px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  color: #1e293b;
  line-height: 1.6;
  overflow: hidden;
}

/* 图片展示 */
.tool-inline-images {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
}

.tool-image-wrapper {
  display: block;
  width: 100%;
  max-width: 100%;
  background: #ffffff;
  border-radius: 10px;
  padding: 8px;
  overflow: hidden;
  box-sizing: border-box;
}

.tool-result-image {
  max-width: 100% !important;
  max-height: 420px;
  width: 100%;
  height: auto;
  border-radius: 8px;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  object-fit: contain;
  background: #f8fafc;
  display: block;
  box-sizing: border-box;
}

.tool-result-image:hover {
  transform: scale(1.02);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

/* 等待动画 */
.tool-waiting {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 0;
  margin-top: 4px;
}

.waiting-dot {
  width: 8px;
  height: 8px;
  background: #f59e0b;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.waiting-dot:nth-child(1) { animation-delay: -0.32s; }
.waiting-dot:nth-child(2) { animation-delay: -0.16s; }

.waiting-text { margin-left: 8px; font-size: 13px; color: #a16207; }

/* ============================================================ */
/* 通用样式 */
/* ============================================================ */
.message-avatar { flex-shrink: 0; }

.avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 19px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
}

.typing-cursor {
  display: inline-block;
  animation: blink 1s infinite;
  color: #0ea5e9;
  margin-left: 3px;
  font-weight: bold;
}

/* ============================================================ */
/* 动画 */
/* ============================================================ */
@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.4); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
