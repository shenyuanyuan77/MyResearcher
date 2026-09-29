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
        <div class="brand-title">MyResearcher</div>
        <div class="brand-sub">科研探索助手</div>
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
        :class="{ active: session.thread_id === currentThreadId, renaming: renamingId === session.thread_id }"
        role="button"
        tabindex="0"
        :title="session.title"
        @click="$emit('select-session', session.thread_id)"
        @keydown.enter="$emit('select-session', session.thread_id)"
        @dblclick="startRename(session)"
      >
        <span v-if="renamingId !== session.thread_id" class="session-title">{{ session.title }}</span>
        <input
          v-else
          v-model="renamingTitle"
          class="rename-input"
          @click.stop
          @keydown.enter="confirmRename(session)"
          @keydown.esc="cancelRename"
          @blur="confirmRename(session)"
          ref="renameInputRef"
        />
        <button
          v-if="renamingId !== session.thread_id"
          class="session-delete-btn"
          title="删除会话"
          aria-label="删除会话"
          @click.stop="onDelete(session.thread_id)"
        >
          <AppIcon name="trash" :size="12" />
        </button>
      </div>
      <div v-if="sessions.length === 0" class="empty-state">
        <p>暂无会话记录</p>
      </div>
      <div v-else-if="filteredSessions.length === 0" class="empty-state">
        <p>未找到匹配「{{ searchKeyword }}」的会话</p>
      </div>
    </div>

    <div class="sidebar-footer" v-if="!collapsed">
      <button class="user-chip" type="button" aria-label="用户菜单" @click="userMenuOpen = !userMenuOpen">
        <span class="user-avatar">{{ avatarLetter }}</span>
        <span class="user-name">{{ currentUser?.username || currentUser?.user_id || 'yanjiu' }}</span>
        <AppIcon name="chevronDown" :size="12" />
      </button>
      <button
        class="settings-btn"
        type="button"
        :aria-label="themeLabel"
        :title="themeLabel"
        @click="onCycleTheme"
      >
        <AppIcon :name="themeResolved === 'dark' ? 'moon' : 'sun'" :size="15" />
      </button>
      <button class="settings-btn" type="button" aria-label="设置" @click="$emit('open-settings')">
        <AppIcon name="cog" :size="15" />
      </button>
      <button class="logout-btn" type="button" aria-label="退出登录" @click="$emit('logout')" title="退出登录">
        <AppIcon name="logout" :size="15" />
      </button>
      <!-- 用户菜单下拉 -->
      <transition name="fade">
        <div v-if="userMenuOpen" class="user-menu" @click="userMenuOpen = false">
          <button class="user-menu-item" @click="$emit('open-settings')">偏好设置</button>
          <button class="user-menu-item danger" @click="$emit('logout')">退出登录</button>
        </div>
      </transition>
    </div>
    <div class="sidebar-footer-collapsed" v-else>
      <button class="user-avatar-btn" type="button" aria-label="退出登录" @click="$emit('logout')">
        {{ avatarLetter }}
      </button>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import WorkspaceNav from './WorkspaceNav.vue'
import AppIcon from './AppIcon.vue'
import { getStoredTheme, resolvedTheme, cycleTheme } from '../theme.js'

const props = defineProps({
  sessions: { type: Array, default: () => [] },
  currentThreadId: { type: String, default: null },
  currentUser: { type: Object, default: null },
  activeView: { type: String, default: 'assistant' },
  drawerOpen: { type: Boolean, default: false },
  collapsed: { type: Boolean, default: false },
})

const emit = defineEmits([
  'select-session', 'new-chat', 'delete-session', 'logout', 'rename-session',
  'navigate', 'close-drawer', 'toggle-collapse', 'open-settings',
])

const searchKeyword = ref('')
const navItems = [
  { id: 'assistant', name: '科研工作台', icon: 'bubble' },
]

// 会话重命名状态
const renamingId = ref(null)
const renamingTitle = ref('')
const renameInputRef = ref(null)
// 用户菜单
const userMenuOpen = ref(false)

function startRename(session) {
  renamingId.value = session.thread_id
  renamingTitle.value = session.title || ''
  nextTick(() => {
    const el = Array.isArray(renameInputRef.value) ? renameInputRef.value[0] : renameInputRef.value
    if (el) { el.focus(); el.select() }
  })
}

function confirmRename(session) {
  if (renamingId.value !== session.thread_id) return
  const newTitle = renamingTitle.value.trim()
  if (newTitle && newTitle !== session.title) {
    emit('rename-session', { threadId: session.thread_id, title: newTitle })
  }
  renamingId.value = null
}

function cancelRename() {
  renamingId.value = null
}

function onDelete(threadId) {
  if (confirm('确定删除此会话？删除后不可恢复。')) {
    emit('delete-session', threadId)
  }
}

const filteredSessions = computed(() => {
  if (!searchKeyword.value) return props.sessions
  return props.sessions.filter((s) =>
    s.title.toLowerCase().includes(searchKeyword.value.toLowerCase())
  )
})

const avatarLetter = computed(() =>
  String(props.currentUser?.username || props.currentUser?.user_id || 'Y').slice(0, 1).toUpperCase()
)

// ===== 主题切换（浅色 → 深色 → 跟随系统 循环） =====
const THEME_LABEL = { auto: '跟随系统', light: '浅色模式', dark: '深色模式' }
const themeMode = ref(getStoredTheme())
const themeResolved = ref(resolvedTheme())
const themeLabel = computed(() => `主题：${THEME_LABEL[themeMode.value]}（点击切换）`)
function onCycleTheme() {
  themeMode.value = cycleTheme()
  themeResolved.value = resolvedTheme(themeMode.value)
}

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
  background: var(--brand-grad-soft, var(--c-primary-soft));
  border: 1px solid var(--c-primary-soft-strong);
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
  background: var(--brand-grad, var(--c-primary));
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(122, 90, 248, .28);
  transition: transform var(--transition-fast), filter var(--transition-fast);
}
.is-collapsed .new-chat-btn { width: 40px; padding: 0; }
.new-chat-btn:hover { filter: brightness(1.08); transform: translateY(-1px); }

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
  background: var(--c-surface-alt, rgba(255, 255, 255, .72));
  color: var(--c-text);
  font-size: 13px;
  outline: none;
}
.search-input:focus {
  border-color: var(--c-primary-soft-strong);
  background: var(--c-surface, #fff);
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
.session-item:hover {
  background: var(--c-surface-alt, rgba(255, 255, 255, .72));
}
.session-item.active {
  background: var(--c-primary-soft);
  box-shadow: inset 2px 0 0 var(--c-primary);
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
.user-chip:hover { background: var(--c-surface-hover, rgba(255, 255, 255, .55)); }
.user-avatar,
.user-avatar-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--brand-grad, linear-gradient(135deg, #7a5af8, #b166ff));
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
  background: var(--c-surface-hover, rgba(255, 255, 255, .7));
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

/* 会话删除按钮 */
.session-item { position: relative; }
.session-delete-btn {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  display: none;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--c-text-tertiary);
  cursor: pointer;
  opacity: 0.6;
}
.session-item:hover .session-delete-btn { display: flex; }
.session-delete-btn:hover {
  background: var(--c-danger-soft);
  color: var(--c-danger);
  opacity: 1;
}

/* 会话重命名输入框 */
.rename-input {
  flex: 1;
  min-width: 0;
  padding: 2px 6px;
  border: 1px solid var(--c-primary);
  border-radius: var(--r-sm);
  background: var(--c-surface);
  color: var(--c-text);
  font-size: 13px;
  outline: none;
}
.session-item.renaming {
  background: var(--c-primary-soft);
}

/* 登出按钮 */
.logout-btn {
  width: 32px;
  height: 32px;
  border: 1px solid transparent;
  border-radius: var(--r-md);
  background: transparent;
  color: var(--c-text-tertiary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
}
.logout-btn:hover {
  background: var(--c-danger-soft);
  color: var(--c-danger);
}

/* 用户菜单下拉 */
.user-menu {
  position: absolute;
  bottom: calc(100% + 4px);
  right: 0;
  min-width: 140px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  box-shadow: var(--sh-lg);
  padding: 4px;
  z-index: 100;
}
.user-menu-item {
  display: block;
  width: 100%;
  padding: 8px 12px;
  border: none;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--c-text);
  font-size: var(--fz-caption);
  text-align: left;
  cursor: pointer;
}
.user-menu-item:hover { background: var(--c-primary-soft); }
.user-menu-item.danger:hover { background: var(--c-danger-soft); color: var(--c-danger); }

/* 空状态/无结果 */
.empty-state p {
  color: var(--c-text-tertiary);
  font-size: var(--fz-caption);
  padding: 12px;
  text-align: center;
}
</style>
