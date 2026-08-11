<template>
  <div class="welcome-empty">
    <div class="welcome-icon">🎓</div>
    <h2>开始你的科研探索</h2>
    <p>在下方输入你的研究方向、检索词或科研问题，或试试这些：</p>
    <div class="quick-row">
      <button v-for="q in quickPicks" :key="q" class="quick-chip" @click="$emit('pick-quick', q)">{{ q }}</button>
    </div>
  </div>
</template>

<script setup>
defineEmits(['pick-quick', 'open-pending'])
defineProps({ pendingSummary: { type: Object, default: () => ({}) } })

const quickPicks = [
  '帮我检索 RAG 最新综述',
  '查 Jason Wei 的学者画像',
  '推演大模型×量子计算的融合可行性',
  '研究方向：思维链与机器人控制',
]
</script>

<style scoped>
.welcome-empty {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 48px 24px; text-align: center; color: var(--c-text-secondary);
}
.welcome-icon { font-size: 56px; margin-bottom: 12px; }
.welcome-empty h2 { font-size: 20px; color: var(--c-text); margin: 0 0 8px; }
.welcome-empty p { font-size: 14px; margin: 0 0 18px; }
.quick-row { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; max-width: 560px; }
.quick-chip {
  border: 1px solid var(--c-border); background: var(--c-surface); color: var(--c-primary);
  border-radius: 999px; padding: 7px 14px; font-size: 12.5px; cursor: pointer;
}
.quick-chip:hover { background: var(--c-primary-soft); border-color: var(--c-primary); }
</style>
