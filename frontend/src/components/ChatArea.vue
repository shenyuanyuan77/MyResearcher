<template>
  <div class="chat-area">
    <!-- 消息列表 -->
    <div class="message-list" ref="messageListRef" @scroll="checkNearBottom" aria-live="polite" aria-atomic="false">
      <WelcomeView
        v-if="displayMessages.length === 0"
        :pending-summary="pendingSummary"
        @pick-quick="$emit('quick-send', $event)"
      />

      <!-- 消息列表（user / assistant / tool 按时间顺序混合展示）-->
      <div v-else class="messages">
        <MessageItem
          v-for="(message, index) in displayMessages"
          :key="message.id || index"
          :message="message"
          :is-streaming="isStreamingForMessage(message)"
        />
      </div>
    </div>
    <!-- 新消息回底提示（用户上滚时有新消息） -->
    <transition name="fade">
      <button
        v-if="hasUnread"
        class="scroll-to-bottom-btn"
        @click="scrollToBottom"
        aria-label="滚动到最新消息"
      >
        ↓ 新消息
      </button>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import MessageItem from './MessageItem.vue'
import WelcomeView from './WelcomeView.vue'

defineEmits(['quick-send'])

/**
 * 对话区域组件
 *
 * 显示消息列表（user / assistant / tool 按时间顺序混合展示）
 * 当 showToolCalls 为 false 时，过滤掉 tool 消息只显示 AI 回复
 */

const props = defineProps({
  messages: {
    type: Array,
    default: () => []
  },
  streaming: {
    type: Boolean,
    default: false
  },
  showToolCalls: {
    type: Boolean,
    default: true
  },
  pendingSummary: {
    type: Object,
    default: null
  }
})

/** 内部管家工具：对用户无信息量，即使开启「显示工具调用」也不展示 */
const HIDDEN_TOOL_NAMES = new Set([
  'write_todos',
  'read_todos',
  'todo_write',
  'todo_read',
  'compact_conversation',
  'emit_research_report',
])

function isHiddenTool(msg) {
  if (msg.role !== 'tool') return false
  const name = String(msg.tool_name || '').toLowerCase()
  return (
    HIDDEN_TOOL_NAMES.has(name) ||
    name.includes('todo') ||
    name.includes('emit_research_report')
  )
}

function isInternalNotice(msg) {
  if (msg.role !== 'assistant') return false
  const text = String(msg.content || '').trim()
  return text.startsWith('[系统通知] 以下技能包已更新')
}

// 根据开关过滤展示的消息
const displayMessages = computed(() => {
  let list = props.messages
  // 始终隐藏待办类内部工具
  list = list.filter((m) => !isHiddenTool(m) && !isInternalNotice(m))
  if (!props.showToolCalls) {
    list = list.filter((m) => m.role !== 'tool')
  }
  return list
})

// 消息列表引用
const messageListRef = ref(null)
// 用户是否在底部附近（用于判断是否自动滚动）
const isNearBottom = ref(true)
// 是否有新消息未读（用户上滚时有新消息时提示）
const hasUnread = ref(false)

/**
 * 判断当前消息是否处于流式输出状态
 * 只有最后一条 assistant 消息在 streaming 时才显示光标
 */
function isStreamingForMessage(msg) {
  if (!props.streaming || msg.role !== 'assistant') return false
  // 找到 messages 中最后一条 assistant 消息（含「思考中」占位）
  const lastAssistant = [...props.messages].reverse().find(m => m.role === 'assistant')
  return lastAssistant === msg
}

/**
 * 检测用户是否在底部附近（距底 < 120px 视为 near）
 */
function checkNearBottom() {
  const el = messageListRef.value
  if (!el) return true
  const threshold = 120
  isNearBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
  // 用户主动滚到底部，清除未读提示
  if (isNearBottom.value) hasUnread.value = false
}

// 监听消息数量变化（新消息加入）
watch(
  () => props.messages.length,
  () => {
    nextTick(() => {
      if (isNearBottom.value) {
        scrollToBottom()
      } else {
        hasUnread.value = true
      }
    })
  }
)

// 深度监听消息内容变化（流式更新时）
watch(
  () => props.messages,
  () => {
    nextTick(() => {
      // 仅当用户在底部附近时自动跟随流式输出滚动
      if (isNearBottom.value) {
        scrollToBottom()
      }
    })
  },
  { deep: true }
)

/**
 * 滚动到底部
 */
function scrollToBottom() {
  if (messageListRef.value) {
    messageListRef.value.scrollTop = props.messages.length
      ? messageListRef.value.scrollHeight
      : 0
    isNearBottom.value = true
    hasUnread.value = false
  }
}

// 历史会话首次挂载时滚动到底部
onMounted(() => nextTick(scrollToBottom))
</script>

<style scoped>
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--c-bg);
}

/* 消息列表 */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 0 126px;
  scroll-padding-bottom: 126px;
}

.message-list::-webkit-scrollbar {
  width: 6px;
}

.message-list::-webkit-scrollbar-track {
  background: transparent;
}

.message-list::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.message-list::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* 消息列表：全宽，由各消息行自己水平居中 */
.messages {
  width: 100%;
  max-width: 100%;
  margin: 0;
  box-sizing: border-box;
}

/* 新消息回底按钮 */
.scroll-to-bottom-btn {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  padding: 6px 16px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-pill, 999px);
  background: var(--c-surface);
  color: var(--c-primary);
  font-size: var(--fz-caption);
  font-weight: 600;
  cursor: pointer;
  box-shadow: var(--sh-md);
  z-index: 10;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast);
}
.scroll-to-bottom-btn:hover {
  transform: translateX(-50%) translateY(-2px);
  box-shadow: var(--sh-lg);
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
