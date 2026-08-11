<template>
  <aside class="sidebar" :class="{ 'is-drawer-open': drawerOpen, 'is-collapsed': collapsed }">
    <div class="traffic-lights" aria-hidden="true">
      <span class="dot red"></span>
      <span class="dot yellow"></span>
      <span class="dot green"></span>
    </div>

    <div class="brand-block" v-if="!collapsed">
      <div class="brand-logo">🎓</div>
      <div class="brand-copy">
        <div class="brand-title">研途智探AI</div>
        <div class="brand-sub">全周期数字科研导师</div>
      </div>
    </div>
    <button
      v-else
      class="expand-btn"
      type="button"
      aria-label="展开侧栏"
      @click="$emit('toggle-collapse')"
    >
      <AppIcon name="chevronRight" :size="14" />
    </button>

    <div class="action-stack">
      <button class="new-chat-btn" @click="onNewChat" :aria-label="collapsed ? '新建对话' : undefined">
        <AppIcon name="bubble" :size="15" color="#ffffff" />
        <span v-if="!collapsed">新建对话</span>
      </button>
    </div>

    <div class="nav-wrap" v-if="!collapsed">
      <WorkspaceNav :active-view="activeView" @navigate="onNavigate" />
    </div>
    <div class="nav-collapsed" v-else>
      <button
        v-for="item in navItems"
        :key="item.id"
        class="nav-dot-btn"
        :class="{ active: activeView === item.id }"
        :aria-label="item.name"
        @click="onNavigate(item.id)"
      >
        <AppIcon :name="item.icon" :size="18" />
      </button>
    </div>

    <div class="search-box" v-if="!collapsed">
      <AppIcon name="search" :size="14" class="search-glyph" />
      <input
        type="text"
        v-model="searchKeyword"
        placeholder="搜索会话..."
        aria-label="搜索会话"
        class="search-input"
      />
    </div>

    <div class="session-list" role="list" aria-label="历史会话" v-if="!collapsed">
      <div
        v-for="session in filteredSessions"
        :key="session.thread_id"
        class="session-item"
        :class="{ active: session.thread_id === currentThreadId }"
        role="button"
        tabindex="0"
        @click="$emit('select-session', session.thread_id)"
        @keydown.enter="$emit('select-session', session.thread_id)"
      >
        <span class="session-title">{{ session.title }}</span>
      </div>
      <div v-if="sessions.length === 0" class="empty-state">
        <p>暂无会话记录</p>
      </div>
    </div>

    <div class="sidebar-footer" v-if="!collapsed">
      <button class="user-chip" type="button" aria-label="用户菜单">
        <span class="user-avatar">{{ avatarLetter }}</span>
        <span class="user-name">{{ currentUser?.username || currentUser?.user_id || 'yanjiu' }}</span>
        <AppIcon name="chevronDown" :size="12" />
      </button>
      <button class="settings-btn" type="button" aria-label="设置" @click="$emit('logout')">
        <AppIcon name="cog" :size="15" />
      </button>
    </div>
    <div class="sidebar-footer-collapsed" v-else>
      <button class="user-avatar-btn" type="button" aria-label="退出登录" @click="$emit('logout')">
        {{ avatarLetter }}
      </button>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import WorkspaceNav from './WorkspaceNav.vue'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  sessions: { type: Array, default: () => [] },
  currentThreadId: { type: String, default: null },
  currentUser: { type: Object, default: null },
  activeView: { type: String, default: 'assistant' },
  drawerOpen: { type: Boolean, default: false },
  collapsed: { type: Boolean, default: false },
})

const emit = defineEmits([
  'select-session', 'new-chat', 'delete-session', 'logout',
  'navigate', 'close-drawer', 'toggle-collapse',
])

const searchKeyword = ref('')
const navItems = [
  { id: 'assistant', name: '科研工作台', icon: 'bubble' },
]

const filteredSessions = computed(() => {
  if (!searchKeyword.value) return props.sessions
  return props.sessions.filter((s) =>
    s.title.toLowerCase().includes(searchKeyword.value.toLowerCase())
  )
})

const avatarLetter = computed(() =>
  String(props.currentUser?.username || props.currentUser?.user_id || 'Y').slice(0, 1).toUpperCase()
)

function onNewChat() { emit('new-chat'); emit('close-drawer') }
function onNavigate(v) { emit('navigate', v); emit('close-drawer') }
function onKeydown(e) { if (e.key === 'Escape') emit('close-drawer') }
onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.sidebar {
  width: var(--aside-w);
  height: 100%;
  background: var(--c-surface-alt);
  color: var(--c-text);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  border-right: 1px solid var(--c-border-light);
  position: relative;
  z-index: 30;
  transition: width var(--transition);
}
.sidebar.is-collapsed { width: var(--aside-collapsed-w); }

@media (max-width: 1024px) {
  .sidebar {
    position: fixed;
    top: 0; left: 0;
    height: 100vh;
    width: var(--aside-w);
    box-shadow: var(--sh-xl);
    transform: translateX(-100%);
    transition: transform var(--transition);
  }
  .sidebar.is-drawer-open { transform: translateX(0); }
  .sidebar.is-collapsed { width: var(--aside-w); }
}

.traffic-lights {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 16px 18px 8px;
}
.dot {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  display: inline-block;
}
.dot.red { background: #ff5f57; }
.dot.yellow { background: #febc2e; }
.dot.green { background: #28c840; }

.brand-block {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 18px 16px;
}
.brand-logo {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  background: var(--c-surface);
  border: 1px solid var(--c-border-light);
  box-shadow: var(--sh-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}
.brand-logo {
  font-size: 26px;
  line-height: 1;
}
.brand-title {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: var(--tracking-display);
  color: var(--c-text);
}
.brand-sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--c-text-tertiary);
}

.expand-btn {
  width: 36px;
  height: 36px;
  margin: 8px auto 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  background: var(--c-surface);
  color: var(--c-text-secondary);
  cursor: pointer;
}

.action-stack {
  padding: 0 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.is-collapsed .action-stack { align-items: center; padding: 0 8px 12px; }

.new-chat-btn {
  width: 100%;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: none;
  border-radius: 14px;
  background: var(--c-primary);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(0, 122, 255, .22);
  transition: transform var(--transition-fast), background var(--transition-fast);
}
.is-collapsed .new-chat-btn { width: 40px; padding: 0; }
.new-chat-btn:hover { background: var(--c-primary-hover); transform: translateY(-1px); }

.nav-wrap { padding: 4px 10px 8px; }
.nav-collapsed {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 4px 0 10px;
}
.nav-dot-btn {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: var(--c-text-secondary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.nav-dot-btn.active,
.nav-dot-btn:hover {
  background: var(--c-primary-soft);
  color: var(--c-primary);
}

.search-box {
  position: relative;
  padding: 4px 16px 12px;
}
.search-glyph {
  position: absolute;
  left: 28px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--c-text-tertiary);
  pointer-events: none;
}
.search-input {
  width: 100%;
  height: 38px;
  padding: 0 14px 0 36px;
  border: 1px solid transparent;
  border-radius: 14px;
  background: rgba(255, 255, 255, .72);
  color: var(--c-text);
  font-size: 13px;
  outline: none;
}
.search-input:focus {
  border-color: var(--c-primary-soft-strong);
  background: #fff;
  box-shadow: 0 0 0 4px var(--c-primary-soft);
}
.search-input::placeholder { color: var(--c-text-tertiary); }

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px 12px;
}
.session-item {
  padding: 10px 12px;
  border-radius: 12px;
  cursor: pointer;
  margin-bottom: 2px;
}
.session-item:hover,
.session-item.active {
  background: rgba(255, 255, 255, .72);
}
.session-title {
  display: block;
  font-size: 13px;
  color: var(--c-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.session-item.active .session-title {
  color: var(--c-text);
  font-weight: 600;
}
.empty-state {
  padding: 28px 12px;
  text-align: center;
  color: var(--c-text-tertiary);
  font-size: 13px;
}

.sidebar-footer {
  margin-top: auto;
  padding: 12px 14px 16px;
  border-top: 1px solid var(--c-border-light);
  display: flex;
  align-items: center;
  gap: 8px;
}
.user-chip {
  flex: 1;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: transparent;
  color: var(--c-text);
  cursor: pointer;
  padding: 4px 2px;
  border-radius: 12px;
}
.user-chip:hover { background: rgba(255, 255, 255, .55); }
.user-avatar,
.user-avatar-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #7c8cff, #5ac8fa);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}
.user-name {
  flex: 1;
  text-align: left;
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.settings-btn {
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--c-text-tertiary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.settings-btn:hover {
  background: rgba(255, 255, 255, .7);
  color: var(--c-text);
}
.sidebar-footer-collapsed {
  margin-top: auto;
  padding: 14px 0;
  display: flex;
  justify-content: center;
  border-top: 1px solid var(--c-border-light);
}
.user-avatar-btn {
  border: none;
  cursor: pointer;
}
</style>
