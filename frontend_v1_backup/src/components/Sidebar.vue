<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="logo">
        <span class="logo-icon">🎓</span>
        <span class="logo-text">研途智探AI</span>
      </div>
      <button class="new-chat-btn" @click="$emit('new-chat')">
        <span class="icon">+</span>
        新建对话
      </button>
    </div>

    <!-- 搜索框 -->
    <div class="search-box">
      <input
        type="text"
        v-model="searchKeyword"
        placeholder="搜索会话..."
        class="search-input"
      />
    </div>

    <!-- 会话列表 -->
    <div class="session-list">
      <div class="session-list-header">
        <span>历史记录</span>
      </div>
      <div class="session-items">
        <div
          v-for="session in filteredSessions"
          :key="session.thread_id"
          class="session-item"
          :class="{ active: session.thread_id === currentThreadId }"
          @click="$emit('select-session', session.thread_id)"
        >
          <div class="session-info">
            <span class="session-title">{{ session.title }}</span>
            <div class="session-meta">
              <span class="session-time">{{ formatTime(session.updated_at) }}</span>
            </div>
          </div>
          <button
            class="delete-btn"
            @click.stop="handleDelete(session.thread_id)"
            title="删除会话"
          >×</button>
        </div>
        <div v-if="!filteredSessions.length" class="empty-state">
          暂无历史会话
        </div>
      </div>
    </div>

    <!-- 用户区 -->
    <div class="user-area" v-if="currentUser">
      <div class="user-avatar">{{ (currentUser.username || 'U')[0].toUpperCase() }}</div>
      <div class="user-info">
        <div class="user-name">{{ currentUser.username }}</div>
        <div class="user-role">{{ (currentUser.roles || []).join(', ') || '用户' }}</div>
      </div>
      <button class="logout-btn" @click="$emit('logout')" title="退出登录">退出</button>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  sessions: { type: Array, default: () => [] },
  currentThreadId: { type: String, default: null },
  currentUser: { type: Object, default: null },
})

const emit = defineEmits(['new-chat', 'select-session', 'delete-session', 'logout'])
const searchKeyword = ref('')

const filteredSessions = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  if (!kw) return props.sessions
  return props.sessions.filter(s => (s.title || '').toLowerCase().includes(kw))
})

function formatTime(ts) {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    const now = new Date()
    const diff = (now - d) / 1000
    if (diff < 60) return '刚刚'
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
    if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前`
    return d.toLocaleDateString('zh-CN')
  } catch { return '' }
}

function handleDelete(tid) {
  if (confirm('确定删除该会话？')) emit('delete-session', tid)
}
</script>

<style scoped>
.sidebar {
  width: 264px;
  min-width: 264px;
  height: 100vh;
  background: var(--c-surface);
  border-right: 1px solid var(--c-border);
  display: flex;
  flex-direction: column;
}
.sidebar-header { padding: 16px; border-bottom: 1px solid var(--c-border); }
.logo { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.logo-icon { font-size: 26px; }
.logo-text { font-size: 17px; font-weight: 700; color: var(--c-text); }
.new-chat-btn {
  width: 100%; border: 1px dashed var(--c-primary);
  background: var(--c-primary-soft); color: var(--c-primary);
  border-radius: 10px; padding: 10px; font-size: 13px; font-weight: 600;
  cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px;
}
.new-chat-btn:hover { background: var(--c-primary); color: #fff; }
.new-chat-btn .icon { font-size: 16px; line-height: 1; }
.search-box { padding: 12px 16px; }
.search-input {
  width: 100%; border: 1px solid var(--c-border); border-radius: 8px;
  padding: 8px 12px; font-size: 13px; background: var(--c-bg);
}
.session-list { flex: 1; overflow-y: auto; padding: 0 8px; }
.session-list-header {
  padding: 8px 8px; font-size: 11px; font-weight: 700;
  color: var(--c-text-tertiary); text-transform: uppercase; letter-spacing: .5px;
}
.session-item {
  display: flex; align-items: center; gap: 8px; padding: 10px;
  border-radius: 8px; cursor: pointer; margin-bottom: 2px;
}
.session-item:hover { background: var(--c-bg); }
.session-item.active { background: var(--c-primary-soft); }
.session-info { flex: 1; min-width: 0; }
.session-title {
  font-size: 13px; color: var(--c-text); display: block;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.session-meta { margin-top: 2px; }
.session-time { font-size: 11px; color: var(--c-text-tertiary); }
.delete-btn {
  border: none; background: transparent; color: var(--c-text-tertiary);
  cursor: pointer; font-size: 18px; padding: 2px 6px; border-radius: 6px; opacity: 0;
}
.session-item:hover .delete-btn { opacity: 1; }
.delete-btn:hover { background: var(--c-danger-soft); color: var(--c-danger); }
.empty-state { padding: 24px; text-align: center; color: var(--c-text-tertiary); font-size: 13px; }
.user-area {
  display: flex; align-items: center; gap: 10px; padding: 12px 16px;
  border-top: 1px solid var(--c-border);
}
.user-avatar {
  width: 34px; height: 34px; border-radius: 50%; background: var(--c-primary);
  color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 600;
}
.user-info { flex: 1; min-width: 0; }
.user-name { font-size: 13px; font-weight: 600; color: var(--c-text); }
.user-role { font-size: 11px; color: var(--c-text-tertiary); }
.logout-btn {
  border: 1px solid var(--c-border); background: transparent; color: var(--c-text-secondary);
  border-radius: 6px; padding: 5px 10px; font-size: 12px; cursor: pointer;
}
.logout-btn:hover { background: var(--c-bg); color: var(--c-danger); }
</style>
