<template>
  <div class="chat-area">
    <!-- 消息列表 -->
    <div class="message-list" ref="messageListRef">
      <WelcomeView
        v-if="displayMessages.length === 0"
        :pending-summary="pendingSummary"
        @pick-quick="$emit('quick-send', $event)"
        @open-pending="$emit('open-pending', $event)"
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
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import MessageItem from './MessageItem.vue'
import WelcomeView from './WelcomeView.vue'

defineEmits(['quick-send', 'open-pending'])

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
    default: () => ({ pendingApprovals: 0, overdueOrders: 0, shortageAlerts: 0, mslAlerts: 0 })
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

// 监听消息变化，自动滚动到底部
watch(
  () => props.messages.length,
  () => {
    nextTick(() => {
      scrollToBottom()
    })
  }
)

// 深度监听消息内容变化（流式更新时也会触发滚动）
watch(
  () => props.messages,
  () => {
    nextTick(() => {
      scrollToBottom()
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
  }
}

// 历史会话首次挂载时 props 已经包含完整消息，watch 不一定会再次触发。
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
</style>
