<template>
  <nav class="workspace-nav" aria-label="工作台导航">
    <div class="nav-group-label">工作台</div>
    <button
      v-for="item in workbenchItems"
      :key="item.id"
      class="nav-item"
      :class="{ active: activeView === item.id }"
      :aria-current="activeView === item.id ? 'page' : undefined"
      type="button"
      @click="$emit('navigate', item.id)"
    >
      <span class="nav-icon">
        <AppIcon :name="item.icon" :size="16" />
      </span>
      <span class="nav-copy">
        <strong>{{ item.name }}</strong>
        <small>{{ item.short }}</small>
      </span>
    </button>
  </nav>
</template>

<script setup>
import AppIcon from './AppIcon.vue'

defineProps({ activeView: { type: String, default: 'assistant' } })
defineEmits(['navigate'])

const workbenchItems = [
  { id: 'assistant', name: '科研工作台', short: '方向·文献·学者·跨界·审稿', icon: 'bubble' },
]
</script>

<style scoped>
.workspace-nav {
  padding: 8px 6px 4px;
}
.nav-group-label {
  padding: 0 10px 8px;
  color: var(--c-text-tertiary);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: .04em;
}
.nav-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 10px;
  border: none;
  border-radius: 14px;
  text-align: left;
  cursor: pointer;
  background: transparent;
  color: inherit;
  transition: background var(--transition-fast);
  font-family: var(--font-body);
}
.nav-item:hover { background: rgba(255, 255, 255, .55); }
.nav-item.active {
  background: rgba(255, 255, 255, .82);
  box-shadow: var(--sh-xs);
}
.nav-item:focus-visible {
  outline: 2px solid var(--c-primary);
  outline-offset: 2px;
}
.nav-icon {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: var(--c-text-tertiary);
  flex: 0 0 auto;
}
.nav-item.active .nav-icon { color: var(--c-primary); }
.nav-copy { display: grid; gap: 1px; min-width: 0; }
.nav-copy strong {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text);
}
.nav-copy small {
  color: var(--c-text-tertiary);
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
