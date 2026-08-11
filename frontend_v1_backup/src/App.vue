<template>
  <LoginView v-if="!authed" @success="onLoginSuccess" />
  <div v-else class="app-container">
    <Sidebar
      :sessions="sessions"
      :current-thread-id="currentThreadId"
      :current-user="currentUser"
      @select-session="handleSelectSession"
      @new-chat="handleNewChat"
      @delete-session="handleDeleteSession"
      @logout="handleLogout"
    />
    <main class="main-content">
      <header class="workspace-header">
        <div>
          <div class="workspace-title">{{ workspace.name }}</div>
          <div class="workspace-subtitle">{{ workspace.description }}</div>
        </div>
        <div class="workspace-status">
          <span></span>{{ isStreaming ? '正在执行' : '服务在线' }}
        </div>
      </header>

      <section v-if="messages.length === 0" class="workspace-intro">
        <div>
          <span class="workspace-kicker">{{ workspace.role }}</span>
          <h1>{{ workspace.name }}</h1>
          <p>{{ workspace.description }}</p>
          <div class="badge-row">
            <span class="doi-badge">🔗 真实 DOI 溯源</span>
            <span class="badge"> CrossRef · OpenAlex · S2</span>
            <span class="badge"> 零幻觉</span>
          </div>
        </div>
        <div class="quick-grid">
          <button
            v-for="task in workspace.quickTasks"
            :key="task.label"
            class="quick-task"
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
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import Sidebar from './components/Sidebar.vue'
import ChatArea from './components/ChatArea.vue'
import InputArea from './components/InputArea.vue'
import LoginView from './components/LoginView.vue'
import { streamChat, resumeChat } from './api/chat.js'
import { deleteSession, getMessages, getSessions } from './api/history.js'
import { fetchMe, getStoredUser, isLoggedIn, logout } from './api/auth.js'

const workspace = {
  name: '研途智探AI',
  role: '全周期数字科研导师',
  description: '一个对话完成方向构建、文献检索精读、学者透视、跨界推演与 AI 审稿，全部文献锚定真实 DOI。',
  placeholder: '输入研究方向、检索词、学者姓名，或直接描述你的科研问题...',
  quickTasks: [
    {
      icon: '🧭', label: '方向构建',
      description: '选题规划、领域热度、检索策略',
      message: '我想研究「大模型思维链与机器人控制结合」这个方向，请帮我做方向构建：拆解子方向、给出核心关键词、推荐检索式，并结合领域热度给出进阶研究节点建议。',
    },
    {
      icon: '🔍', label: '情报提纯',
      description: '检索真实文献、精读、综述',
      message: '请检索 retrieval augmented generation（RAG）领域的最新高引文献，召回 8 篇带真实 DOI 的论文并出表，然后精读其中被引最高的 2 篇，给出创新点、方法与可引用句。',
    },
    {
      icon: '👤', label: '资产透视',
      description: '学者画像、h 指数、代表作',
      message: '请帮我做学者资产透视：查 Jason Wei 这位学者的研究布局，给出 h 指数、代表作 Top、研究主题分布和跟进建议。',
    },
    {
      icon: '🧬', label: '跨界启发',
      description: '两领域融合可行性推演',
      message: '请推演「大语言模型」与「量子计算」的融合可行性：先检索已有的交叉工作（带 DOI 作佐证），再给出融合路径、可行性评估、技术路线与风险盲区。',
    },
    {
      icon: '📝', label: 'AI 审稿',
      description: '规范性检查、引用核对、评分',
      message: '请帮我审稿（AI 审稿引擎）：我会粘贴一段论文草稿/摘要，请做规范性检查、引用真实性核对（用 paper_search/paper_by_doi 核验）、逻辑漏洞与改进建议，最后给出评分表。我先贴内容：',
    },
  ],
}

const sessions = ref([])
const currentThreadId = ref(null)
const messages = ref([])
const isStreaming = ref(false)
const isResuming = ref(false)
const showToolCalls = ref(false)
const interruptData = ref(null)
const authed = ref(isLoggedIn())
const currentUser = ref(getStoredUser())
let abortController = null

const HIDDEN_TOOL_NAMES = new Set([
  'write_todos', 'read_todos', 'todo_write', 'todo_read',
  'compact_conversation', 'emit_research_report',
])

function isHiddenToolName(name) {
  const n = String(name || '').toLowerCase()
  return HIDDEN_TOOL_NAMES.has(n) || n.includes('todo')
}

function pushThinking() {
  messages.value.push({ id: `thinking-${Date.now()}`, role: 'assistant', content: '', thinking: true, source: 'main' })
}
function removeEmptyThinking() {
  const last = messages.value.at(-1)
  if (last?.role === 'assistant' && !last.content && last.thinking) messages.value.pop()
}
function markToolsDone() {
  messages.value.forEach(m => { if (m.role === 'tool' && m.tool_status === 'calling') m.tool_status = 'done' })
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
    messages.value.push({ id: `assistant-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, role: 'assistant', content, source: source || 'main' })
  }
}
function addTool(tool) {
  if (isHiddenToolName(tool.name)) return
  removeEmptyThinking()
  messages.value.push({ id: tool.id, role: 'tool', tool_name: tool.name, args: '', text: '', images: [], source: tool.source || 'main', tool_status: 'calling', hide_args: String(tool.name).includes('emit_research_report') })
}
function updateTool(tool) {
  const item = messages.value.find(m => m.role === 'tool' && m.id === tool.id)
  if (item) { item.text = tool.text || item.text; item.images = tool.images || item.images; item.tool_status = 'done' }
}
function streamCallbacks() {
  return {
    onToken: addToken,
    onToolStart: addTool,
    onToolArgs: (args) => {
      const item = [...messages.value].reverse().find(m => m.role === 'tool' && m.tool_status === 'calling' && !m.hide_args)
      if (item) item.args += args
    },
    onToolResult: updateTool,
    onToolEnd: markToolsDone,
    onInterrupt: (data) => { markToolsDone(); removeEmptyThinking(); interruptData.value = data; if (data.thread_id && !currentThreadId.value) { currentThreadId.value = data.thread_id; loadSessions() } },
    onDone: async (data) => {
      markToolsDone(); applyFinal(data)
      messages.value = messages.value.filter(m => m.role !== 'assistant' || m.content || data.aborted)
      if (data.thread_id && !currentThreadId.value) { currentThreadId.value = data.thread_id; await loadSessions() }
      if (data.thread_id && !data.interrupted && !data.aborted) await loadMessages(data.thread_id)
    },
    onError: (error) => {
      const last = messages.value.at(-1)
      const content = `抱歉，发生了错误：${error.message}`
      if (last?.role === 'assistant' && !last.content) last.content = content
      else messages.value.push({ id: `error-${Date.now()}`, role: 'assistant', content, source: 'main' })
    },
  }
}

async function handleSend(message) {
  if (isStreaming.value || !message?.trim()) return
  messages.value.push({ id: `user-${Date.now()}`, role: 'user', content: message })
  interruptData.value = null
  isStreaming.value = true
  pushThinking()
  abortController = new AbortController()
  try {
    await streamChat(message, currentThreadId.value, streamCallbacks(), abortController.signal, 'assistant')
  } catch (error) {
    if (error.name !== 'AbortError') console.error(error)
  } finally {
    removeEmptyThinking(); isStreaming.value = false; abortController = null
  }
}

async function handleResume(resumeData) {
  if (isResuming.value || !currentThreadId.value) return
  isResuming.value = true; isStreaming.value = true
  pushThinking()
  abortController = new AbortController()
  try {
    const result = await resumeChat(currentThreadId.value, resumeData, streamCallbacks(), abortController.signal, 'assistant')
    if (!result.interrupted) interruptData.value = null
  } catch (error) {
    if (error.name !== 'AbortError') console.error(error)
  } finally {
    removeEmptyThinking(); isResuming.value = false; isStreaming.value = false; abortController = null
  }
}

async function loadSessions() {
  try { sessions.value = (await getSessions(1, 100)).sessions || [] }
  catch { sessions.value = [] }
}
async function loadMessages(threadId) {
  try {
    messages.value = ((await getMessages(threadId)).messages || []).filter(
      m => m.role !== 'system' && !(m.role === 'tool' && isHiddenToolName(m.tool_name))
    )
  } catch { messages.value = [] }
}
async function handleSelectSession(threadId) {
  if (threadId === currentThreadId.value) return
  currentThreadId.value = threadId
  interruptData.value = null
  await loadMessages(threadId)
}
function handleNewChat() {
  abortController?.abort()
  isStreaming.value = false; isResuming.value = false
  interruptData.value = null; currentThreadId.value = null; messages.value = []
}
async function handleDeleteSession(threadId) {
  try {
    await deleteSession(threadId)
    if (threadId === currentThreadId.value) handleNewChat()
    await loadSessions()
  } catch (error) { alert(`删除会话失败：${error.message}`) }
}
function handleStop() { abortController?.abort() }
function handleLogout() { logout(); authed.value = false; currentUser.value = null; sessions.value = []; handleNewChat() }
async function onLoginSuccess(user) {
  currentUser.value = user; authed.value = true
  await loadSessions()
}
function onAuthRequired() { authed.value = false; currentUser.value = null }

onMounted(async () => {
  window.addEventListener('auth:required', onAuthRequired)
  if (authed.value) {
    try { currentUser.value = await fetchMe(); await loadSessions() }
    catch { onAuthRequired() }
  }
})
onUnmounted(() => window.removeEventListener('auth:required', onAuthRequired))
</script>

<style scoped>
.app-container { display: flex; height: 100vh; overflow: hidden; background: var(--c-bg); }
.main-content { flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden; position: relative; }
.workspace-header {
  min-height: 56px; padding: 0 22px; display: flex; align-items: center;
  justify-content: space-between; gap: 16px; background: rgba(255, 255, 255, .94);
  border-bottom: 1px solid var(--c-border); backdrop-filter: blur(10px);
}
.workspace-title { font-size: 16px; font-weight: 700; }
.workspace-subtitle { margin-top: 2px; color: var(--c-text-tertiary); font-size: 11px; }
.workspace-status {
  display: inline-flex; align-items: center; gap: 7px; color: var(--c-success);
  font-size: 11px; white-space: nowrap; padding: 5px 9px; border-radius: 999px; background: var(--c-success-soft);
}
.workspace-status span { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.workspace-intro {
  flex: 1; overflow: auto; padding: 38px max(26px, 6vw) 136px;
  background: linear-gradient(180deg, #f8fbff 0%, var(--c-bg) 50%);
}
.workspace-intro > div:first-child { max-width: 760px; }
.workspace-kicker { color: var(--c-primary); font-size: 11px; font-weight: 700; letter-spacing: .5px; }
.workspace-intro h1 { font-size: 30px; margin: 8px 0 6px; color: var(--c-text); }
.workspace-intro p { color: var(--c-text-secondary); font-size: 14px; line-height: 1.6; margin: 0 0 12px; }
.badge-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 24px; }
.doi-badge, .badge {
  font-size: 11px; padding: 4px 10px; border-radius: 999px;
  background: var(--c-primary-soft); color: var(--c-primary); font-weight: 600;
}
.doi-badge { background: var(--c-accent-soft); color: var(--c-accent); }
.badge { background: var(--c-bg); color: var(--c-text-secondary); border: 1px solid var(--c-border); }
.quick-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; max-width: 900px; }
.quick-task {
  text-align: left; border: 1px solid var(--c-border); background: var(--c-surface);
  border-radius: 14px; padding: 16px; cursor: pointer; display: flex; gap: 12px; align-items: flex-start;
  transition: all .15s;
}
.quick-task:hover { border-color: var(--c-primary); box-shadow: var(--sh-md); transform: translateY(-1px); }
.qt-icon { font-size: 24px; line-height: 1; }
.qt-body strong { display: block; font-size: 14px; color: var(--c-text); margin-bottom: 3px; }
.qt-body span { font-size: 12px; color: var(--c-text-tertiary); line-height: 1.4; display: block; }
</style>
