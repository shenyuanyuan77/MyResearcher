<template>
  <LoginView v-if="!authed" @success="onLoginSuccess" />
  <div v-else class="app-stage">
    <div class="app-window" :class="{ 'aside-collapsed': sidebarCollapsed }">
      <Sidebar
        :sessions="sessions"
        :current-thread-id="currentThreadId"
        :current-user="currentUser"
        :active-view="activeView"
        :drawer-open="sidebarOpen"
        :collapsed="sidebarCollapsed"
        @navigate="navigate"
        @select-session="handleSelectSession"
        @new-chat="handleNewChat"
        @delete-session="handleDeleteSession"
        @logout="handleLogout"
        @close-drawer="sidebarOpen = false"
        @toggle-collapse="toggleSidebarCollapsed"
      />

      <button
        v-if="sidebarOpen"
        class="drawer-scrim"
        aria-label="关闭侧栏"
        @click="sidebarOpen = false"
      ></button>

      <main class="main-content">
        <header class="workspace-header">
          <button
            class="hamburger"
            type="button"
            aria-label="打开侧栏"
            @click="sidebarOpen = true"
          >
            <span></span><span></span><span></span>
          </button>
          <div class="workspace-titles">
            <div class="workspace-title">{{ workspace.name }}</div>
            <div class="workspace-subtitle">{{ workspace.description }}</div>
          </div>
          <div class="workspace-status" :class="{ busy: isStreaming }">
            <span></span>{{ isStreaming ? '正在执行' : '服务在线' }}
          </div>
          <div v-if="currentThreadId && messages.length" class="export-menu">
            <button class="export-btn" @click="exportMenuOpen = !exportMenuOpen" :disabled="exporting">
              {{ exporting ? '导出中…' : '⬇ 导出报告' }}
            </button>
            <div v-if="exportMenuOpen" class="export-dropdown">
              <div class="export-options">
                <label class="export-field">
                  <span>引用格式</span>
                  <select v-model="exportCitationStyle">
                    <option value="gbt7714">GB/T 7714-2015</option>
                    <option value="apa">APA 第7版</option>
                    <option value="ieee">IEEE</option>
                    <option value="chicago">Chicago</option>
                    <option value="vancouver">Vancouver</option>
                    <option value="mla">MLA 第9版</option>
                  </select>
                </label>
                <label class="export-field" v-if="false">
                  <span>PDF 模板</span>
                  <select v-model="exportPdfTemplate">
                    <option value="report">报告（单栏）</option>
                    <option value="academic">学术论文（双栏）</option>
                  </select>
                </label>
              </div>
              <button @click="exportReport('docx')">📄 Word (.docx)</button>
              <button @click="exportReport('pdf')">📑 PDF</button>
              <button @click="exportReport('md')">📝 Markdown</button>
            </div>
          </div>
        </header>

        <section v-if="messages.length === 0" class="workspace-intro">
          <div class="intro-hero">
            <div class="intro-kicker">{{ workspace.role }}</div>
            <h2 class="intro-title">{{ workspace.headline }}</h2>
            <p class="intro-desc">{{ workspace.description }}</p>
            <div class="intro-badges">
              <span class="badge badge-doi">🔗 真实 DOI 溯源</span>
              <span class="badge">CrossRef · OpenAlex · S2</span>
              <span class="badge">零幻觉</span>
            </div>
          </div>
          <div class="quick-grid">
            <button
              v-for="(task, i) in workspace.quickTasks"
              :key="task.label"
              class="quick-task stagger-item"
              :style="{ '--i': i }"
              @click="handleSend(task.message)"
            >
              <span class="qt-icon">{{ task.icon }}</span>
              <div class="qt-body">
                <strong>{{ task.label }}</strong>
                <span>{{ task.description }}</span>
              </div>
            </button>
          </div>
        </section>

        <ChatArea
          v-else
          :messages="messages"
          :streaming="isStreaming || isResuming"
          :show-tool-calls="showToolCalls"
          @quick-send="handleSend"
        />
        <InterruptBanner
          v-if="interruptData"
          :interrupt-data="interruptData"
          :submitting="isResuming"
          @resume="handleResume"
        />
        <InputArea
          v-if="!interruptData"
          :placeholder="workspace.placeholder"
          :streaming="isStreaming"
          :show-tool-calls="showToolCalls"
          @send="handleSend"
          @stop="handleStop"
          @toggle-tool-calls="showToolCalls = $event"
        />
      </main>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import Sidebar from './components/Sidebar.vue'
import ChatArea from './components/ChatArea.vue'
import InputArea from './components/InputArea.vue'
import InterruptBanner from './components/InterruptBanner.vue'
import LoginView from './components/LoginView.vue'
import { streamChat, resumeChat } from './api/chat.js'
import { deleteSession, getMessages, getSessions } from './api/history.js'
import { fetchMe, getStoredUser, isLoggedIn, logout } from './api/auth.js'

const workspace = {
  name: '研途智探AI',
  role: '全周期数字科研导师',
  headline: '让每一次科研探索都有迹可循',
  description: '一个对话完成方向构建、文献检索精读、学者透视、跨界推演与 AI 审稿，全部文献锚定真实 DOI。',
  placeholder: '输入研究方向、检索词、学者姓名，或直接描述你的科研问题…',
  quickTasks: [
    { icon: '🧭', label: '方向构建', description: '选题规划、领域热度、检索策略', message: '我想研究「大模型思维链与机器人控制结合」这个方向，请帮我做方向构建：拆解子方向、给出核心关键词、推荐检索式，并结合领域热度给出进阶研究节点建议。' },
    { icon: '🔍', label: '情报提纯', description: '检索真实文献、精读、综述', message: '请检索 retrieval augmented generation（RAG）领域的最新高引文献，召回 8 篇带真实 DOI 的论文并出表，然后精读其中被引最高的 2 篇，给出创新点、方法与可引用句。' },
    { icon: '👤', label: '资产透视', description: '学者画像、h 指数、代表作', message: '请帮我做学者资产透视：查 Yann LeCun 这位学者的研究布局，给出 h 指数、代表作 Top、研究主题分布和跟进建议。' },
    { icon: '🧬', label: '跨界启发', description: '两领域融合可行性推演', message: '请推演「大语言模型」与「量子计算」的融合可行性：先检索已有的交叉工作（带 DOI 作佐证），再给出融合路径、可行性评估、技术路线与风险盲区。' },
    { icon: '📝', label: 'AI 审稿', description: '规范性检查、引用核对、评分', message: '请帮我审稿（AI 审稿引擎）：我会粘贴一段论文草稿/摘要，请做规范性检查、引用真实性核对（用 paper_search/paper_by_doi 核验）、逻辑漏洞与改进建议，最后给出评分表。我先贴内容：' },
    { icon: '📖', label: 'DOI 溯源', description: '核验单篇引用真实性', message: '请帮我核验这篇引用是否真实存在：10.1038/nature14539，给出标题、作者、年份、期刊和被引数。' },
  ],
}

const activeView = ref('assistant')
const sessions = ref([])
const currentThreadId = ref(null)
const messages = ref([])
const isStreaming = ref(false)
const isResuming = ref(false)
const showToolCalls = ref(true)
const interruptData = ref(null)
const authed = ref(isLoggedIn())
const currentUser = ref(getStoredUser())
const sidebarOpen = ref(false)
const sidebarCollapsed = ref(false)
const exportMenuOpen = ref(false)
const exporting = ref(false)
const exportCitationStyle = ref('gbt7714')
const exportPdfTemplate = ref('report')
let abortController = null

const HIDDEN_TOOL_NAMES = new Set([
  'write_todos', 'read_todos', 'todo_write', 'todo_read',
  'compact_conversation', 'emit_research_report',
])

function isHiddenToolName(name) {
  const n = String(name || '').toLowerCase()
  return HIDDEN_TOOL_NAMES.has(n) || n.includes('todo') || n.includes('emit_research_report')
}
function pushThinking() {
  messages.value.push({ id: `thinking-${Date.now()}`, role: 'assistant', content: '', thinking: true, source: 'main' })
}
function removeEmptyThinking() {
  const last = messages.value.at(-1)
  if (last?.role === 'assistant' && !last.content && last.thinking) messages.value.pop()
}
function markToolsDone() {
  messages.value.forEach((m) => {
    if (m.role === 'tool' && m.tool_status === 'calling') m.tool_status = 'done'
  })
}
function applyFinal(data) {
  const finals = data?.final_assistants
  if (!Array.isArray(finals)) return
  let index = messages.value.length - 1
  for (let i = finals.length - 1; i >= 0; i -= 1) {
    while (index >= 0 && messages.value[index].role !== 'assistant') index -= 1
    if (index < 0) return
    if (typeof finals[i] === 'string' && finals[i].trim()) messages.value[index].content = finals[i]
    index -= 1
  }
}
function addToken(content, source) {
  if (String(content).includes('【系统上下文') || String(content).includes('勿向用户复述')) return
  const last = messages.value.at(-1)
  if (last?.role === 'assistant') {
    last.thinking = false
    last.content += content
    if (source) last.source = source
  } else {
    messages.value.push({
      id: `assistant-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      role: 'assistant',
      content,
      source: source || 'main',
    })
  }
}
function addTool(tool) {
  if (isHiddenToolName(tool.name)) return
  removeEmptyThinking()
  messages.value.push({
    id: tool.id,
    role: 'tool',
    tool_name: tool.name,
    args: '',
    text: '',
    images: [],
    references: null,
    source: tool.source || 'main',
    tool_status: 'calling',
    hide_args: String(tool.name).includes('emit_research_report'),
    created_at: Date.now(),
  })
}
function updateTool(tool) {
  const item = messages.value.find((m) => m.role === 'tool' && m.id === tool.id)
  if (item) {
    item.text = tool.text || item.text
    item.images = tool.images || item.images
    if (tool.references) item.references = tool.references
    item.tool_status = 'done'
  }
}
function streamCallbacks() {
  return {
    onToken: addToken,
    onToolStart: addTool,
    onToolArgs: (args) => {
      const item = [...messages.value].reverse().find(
        (m) => m.role === 'tool' && m.tool_status === 'calling' && !m.hide_args
      )
      if (item) item.args += args
    },
    onToolResult: updateTool,
    onToolEnd: markToolsDone,
    onInterrupt: (data) => {
      markToolsDone()
      removeEmptyThinking()
      interruptData.value = data
      if (data.thread_id && !currentThreadId.value) {
        currentThreadId.value = data.thread_id
        loadSessions()
      }
    },
    onDone: async (data) => {
      markToolsDone()
      applyFinal(data)
      messages.value = messages.value.filter(
        (m) => m.role !== 'assistant' || m.content || data.aborted
      )
      if (data.thread_id && !currentThreadId.value) {
        currentThreadId.value = data.thread_id
        await loadSessions()
      }
      if (data.thread_id && !data.interrupted && !data.aborted) await loadMessages(data.thread_id)
    },
    onError: (error) => {
      const last = messages.value.at(-1)
      const content = `抱歉，发生了错误：${error.message}`
      if (last?.role === 'assistant' && !last.content) last.content = content
      else messages.value.push({
        id: `error-${Date.now()}`,
        role: 'assistant',
        content,
        source: 'main',
      })
    },
  }
}

async function handleSend(message) {
  if (isStreaming.value || !message?.trim()) return
  sidebarOpen.value = false
  messages.value.push({ id: `user-${Date.now()}`, role: 'user', content: message, created_at: Date.now() })
  interruptData.value = null
  isStreaming.value = true
  pushThinking()
  abortController = new AbortController()
  try {
    await streamChat(message, currentThreadId.value, streamCallbacks(), abortController.signal, 'assistant')
  } catch (error) {
    if (error.name !== 'AbortError') console.error(error)
  } finally {
    removeEmptyThinking()
    isStreaming.value = false
    abortController = null
  }
}

async function handleResume(resumeData) {
  if (isResuming.value || !currentThreadId.value) return
  isResuming.value = true
  isStreaming.value = true
  pushThinking()
  abortController = new AbortController()
  try {
    const result = await resumeChat(currentThreadId.value, resumeData, streamCallbacks(), abortController.signal, 'assistant')
    if (!result.interrupted) interruptData.value = null
  } catch (error) {
    if (error.name !== 'AbortError') console.error(error)
  } finally {
    removeEmptyThinking()
    isResuming.value = false
    isStreaming.value = false
    abortController = null
  }
}

async function loadSessions() {
  try { sessions.value = (await getSessions(1, 100)).sessions || [] }
  catch { sessions.value = [] }
}
async function loadMessages(threadId) {
  try {
    messages.value = ((await getMessages(threadId)).messages || []).filter(
      (m) => m.role !== 'system' && !(m.role === 'tool' && isHiddenToolName(m.tool_name))
    )
  } catch { messages.value = [] }
}

async function handleSelectSession(threadId) {
  if (threadId === currentThreadId.value && activeView.value === 'assistant') return
  activeView.value = 'assistant'
  currentThreadId.value = threadId
  interruptData.value = null
  await loadMessages(threadId)
}

function handleNewChat() {
  abortController?.abort()
  isStreaming.value = false
  isResuming.value = false
  interruptData.value = null
  currentThreadId.value = null
  messages.value = []
}

async function handleDeleteSession(threadId) {
  try {
    await deleteSession(threadId)
    if (threadId === currentThreadId.value) handleNewChat()
    await loadSessions()
  } catch (error) {
    alert(`删除会话失败：${error.message}`)
  }
}
function handleStop() { abortController?.abort() }

async function exportReport(format) {
  exportMenuOpen.value = false
  if (!currentThreadId.value) return
  exporting.value = true
  try {
    const { getToken, extractApiError } = await import('./api/http.js')
    const token = getToken()
    const resp = await fetch('/api/report/export', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        thread_id: currentThreadId.value,
        format,
        citation_style: exportCitationStyle.value,
        pdf_template: exportPdfTemplate.value,
      }),
    })
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}))
      throw new Error(extractApiError(body, `导出失败 (${resp.status})`))
    }
    const blob = await resp.blob()
    const cd = resp.headers.get('content-disposition') || ''
    const m = cd.match(/filename="?([^"]+)"?/)
    const filename = m ? m[1] : `研途智探报告.${format}`
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e) {
    alert(`导出失败：${e.message}`)
  } finally {
    exporting.value = false
  }
}
function navigate(view) {
  if (view === activeView.value) return
  activeView.value = view
  if (view === 'assistant') loadSessions()
}
function handleLogout() {
  logout()
  authed.value = false
  currentUser.value = null
  sessions.value = []
  handleNewChat()
}
async function onLoginSuccess(user) {
  currentUser.value = user
  authed.value = true
  await loadSessions()
}
function onAuthRequired() {
  authed.value = false
  currentUser.value = null
}
function onResize() {
  if (window.innerWidth > 1024) sidebarOpen.value = false
}
function toggleSidebarCollapsed() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

onMounted(async () => {
  window.addEventListener('auth:required', onAuthRequired)
  window.addEventListener('resize', onResize)
  if (authed.value) {
    try {
      currentUser.value = await fetchMe()
      await loadSessions()
    } catch {
      onAuthRequired()
    }
  }
})
onUnmounted(() => {
  window.removeEventListener('auth:required', onAuthRequired)
  window.removeEventListener('resize', onResize)
})
</script>

<style scoped>
.app-stage {
  min-height: 100vh;
  padding: var(--window-pad);
  box-sizing: border-box;
  display: flex;
  align-items: stretch;
  justify-content: center;
  background:
    radial-gradient(1200px 700px at 18% 12%, rgba(0, 122, 255, .10), transparent 55%),
    radial-gradient(900px 600px at 88% 78%, rgba(255, 159, 10, .08), transparent 50%),
    var(--c-bg);
}

.app-window {
  width: min(1480px, 100%);
  height: calc(100vh - var(--window-pad) * 2);
  display: flex;
  overflow: hidden;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-window);
  box-shadow: var(--sh-xl);
}

.main-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  background: var(--c-surface);
}

.drawer-scrim {
  position: fixed; inset: 0;
  background: var(--c-overlay);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  z-index: 25;
  animation: fadeIn var(--dur-normal) var(--ease-ios);
  border: none;
  cursor: pointer;
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

.workspace-header {
  min-height: var(--header-h);
  padding: 18px 28px 12px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  background: transparent;
  flex-shrink: 0;
}

.hamburger {
  display: none;
  width: 36px; height: 36px;
  background: transparent;
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  margin-top: 2px;
}
.hamburger:hover { background: var(--c-surface-alt); }
.hamburger span {
  display: block;
  width: 16px; height: 1.5px;
  background: var(--c-text);
  border-radius: 2px;
}

.workspace-titles { flex: 1; min-width: 0; }
.workspace-title {
  font-family: var(--font-display);
  font-size: var(--fz-h1);
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--c-text);
  line-height: 1.2;
}
.workspace-subtitle {
  margin-top: 6px;
  color: var(--c-text-tertiary);
  font-size: var(--fz-caption);
  line-height: 1.5;
}

.workspace-status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--c-success);
  font-size: var(--fz-mini);
  white-space: nowrap;
  padding: 7px 12px;
  border-radius: var(--r-pill);
  background: var(--c-success-soft);
  font-weight: 600;
  margin-top: 2px;
}
.export-menu { position: relative; margin-top: 2px; }
.export-btn {
  font-size: var(--fz-mini); font-weight: 600; white-space: nowrap;
  padding: 7px 13px; border-radius: var(--r-pill);
  background: var(--c-primary); color: #fff; border: none; cursor: pointer;
  box-shadow: var(--sh-primary); transition: all var(--transition-fast);
}
.export-btn:hover:not(:disabled) { background: var(--c-primary-hover); transform: translateY(-1px); }
.export-btn:disabled { opacity: .7; cursor: not-allowed; }
.export-dropdown {
  position: absolute; right: 0; top: calc(100% + 6px);
  background: var(--c-surface); border: 1px solid var(--c-border);
  border-radius: var(--r-md); box-shadow: var(--sh-lg);
  min-width: 168px; padding: 6px; z-index: 30;
  animation: fadeIn .16s var(--ease-ios);
}
.export-dropdown button {
  display: block; width: 100%; text-align: left;
  padding: 9px 12px; border: none; background: transparent;
  font-size: var(--fz-caption); color: var(--c-text); border-radius: var(--r-sm);
  cursor: pointer;
}
.export-dropdown button:hover { background: var(--c-primary-soft); color: var(--c-primary); }
.export-options {
  padding: 6px 4px 8px;
  border-bottom: 1px solid var(--c-border);
  margin-bottom: 4px;
}
.export-field {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: var(--fz-mini);
  color: var(--c-text-secondary);
}
.export-field span { font-weight: 500; }
.export-field select {
  height: 30px;
  padding: 0 6px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  background: var(--c-surface);
  color: var(--c-text);
  font-size: var(--fz-caption);
}
.workspace-status span {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--c-success-bright);
  animation: pulseDot 2.2s var(--ease-ios) infinite;
}
.workspace-status.busy { color: var(--c-primary); background: var(--c-primary-soft); }
.workspace-status.busy span { background: var(--c-primary); animation-duration: 0.9s; }

.workspace-intro {
  flex: 1;
  overflow: auto;
  padding: 8px 28px 140px;
}
.intro-hero { max-width: var(--content-max); margin-bottom: 28px; }
.intro-kicker {
  color: var(--c-primary);
  font-size: var(--fz-caption);
  font-weight: 700;
  letter-spacing: var(--tracking-caps);
  text-transform: uppercase;
}
.intro-title {
  font-family: var(--font-display);
  font-size: var(--fz-hero);
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--c-text);
  margin: 10px 0 10px;
  line-height: 1.15;
}
.intro-desc {
  color: var(--c-text-secondary);
  font-size: var(--fz-body);
  line-height: var(--lh-normal);
  max-width: 640px;
  margin: 0 0 16px;
}
.intro-badges { display: flex; gap: 8px; flex-wrap: wrap; }
.badge {
  font-size: var(--fz-mini);
  padding: 5px 11px;
  border-radius: var(--r-pill);
  background: var(--c-surface-alt);
  color: var(--c-text-secondary);
  border: 1px solid var(--c-border);
  font-weight: 600;
}
.badge-doi { background: var(--c-accent-soft); color: var(--c-accent); border-color: transparent; }

.quick-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  max-width: var(--content-max);
}
.quick-task {
  min-height: 92px;
  padding: 16px 17px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  background: var(--c-surface);
  text-align: left;
  display: flex;
  gap: 12px;
  align-items: flex-start;
  box-shadow: var(--sh-sm);
  cursor: pointer;
  transition: transform var(--transition), box-shadow var(--transition), border-color var(--transition-fast);
}
.quick-task:hover { border-color: var(--c-primary); transform: translateY(-2px); box-shadow: var(--sh-md); }
.qt-icon { font-size: 24px; line-height: 1; }
.qt-body { display: flex; flex-direction: column; gap: 4px; }
.quick-task strong { font-size: var(--fz-body); font-weight: 600; }
.quick-task span { color: var(--c-text-secondary); font-size: var(--fz-caption); line-height: 1.5; }

.stagger-item { animation: staggerIn .5s var(--ease-spring) backwards; animation-delay: calc(var(--i, 0) * 60ms); }
@keyframes staggerIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
@keyframes pulseDot { 0%, 100% { opacity: 1; } 50% { opacity: .35; } }

@media (max-width: 1100px) {
  .quick-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 1024px) {
  .app-stage { padding: 0; }
  .app-window {
    width: 100%;
    height: 100vh;
    border-radius: 0;
    border: none;
    box-shadow: none;
  }
  .hamburger { display: inline-flex; }
  .workspace-header { padding: 14px 16px 10px; }
}
@media (max-width: 760px) {
  .quick-grid { grid-template-columns: 1fr; }
  .workspace-subtitle { display: none; }
  .intro-title { font-size: var(--fz-h1); }
}
</style>
