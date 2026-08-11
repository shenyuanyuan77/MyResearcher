<template>
  <div class="welcome">
    <div class="hero card card-pad-lg">
      <div class="hero-icon"><span class="hero-emoji">🎓</span></div>
      <div class="hero-text">
        <h1 class="hero-title">开始你的科研探索</h1>
        <p class="hero-sub">
          研途智探AI —— 一个对话完成方向构建、文献检索精读、学者透视、跨界推演与 AI 审稿，全部文献锚定真实 DOI。
        </p>
      </div>
      <div class="hero-meta">
        <div class="hero-meta-item">
          <span class="meta-label">服务</span>
          <span class="meta-value">{{ serviceStatus }}</span>
        </div>
        <div class="hero-meta-item">
          <span class="meta-label">数据源</span>
          <span class="meta-value">CrossRef · S2</span>
        </div>
      </div>
    </div>

    <div class="welcome-grid">
      <div class="card card-pad">
        <div class="card-section-title">
          <span>快捷任务</span>
          <span class="meta">点击下方任一项即可发送给 Agent</span>
        </div>
        <div class="quick-grid">
          <button
            v-for="(t, i) in quickTasks"
            :key="t.key"
            class="quick-card stagger-item"
            :style="{ '--i': i }"
            @click="$emit('pick-quick', t.message)"
          >
            <span class="quick-glyph" :class="`glyph-${t.key}`" aria-hidden="true">
              <AppIcon :name="t.icon" :size="18" />
            </span>
            <div class="quick-text">
              <div class="quick-title">{{ t.label }}</div>
              <div class="quick-desc">{{ t.desc }}</div>
            </div>
            <AppIcon name="chevronRight" :size="14" class="quick-arrow" />
          </button>
        </div>
      </div>

      <div class="card card-pad">
        <div class="card-section-title">
          <span>科研待办</span>
          <span class="meta">本工作台概览</span>
        </div>
        <div class="pending-grid">
          <button
            v-for="(p, i) in pendingItems"
            :key="p.key"
            class="pending-card stagger-item"
            :class="`pending-${p.tone}`"
            :style="{ '--i': i }"
            @click="$emit('open-pending', p.key)"
          >
            <div class="pending-head">
              <span class="pending-glyph" aria-hidden="true">
                <AppIcon :name="p.icon" :size="14" color="#ffffff" />
              </span>
              <span class="pending-count">{{ p.count }}</span>
            </div>
            <div class="pending-label">{{ p.label }}</div>
            <div class="pending-action">查看</div>
          </button>
        </div>
      </div>
    </div>

    <div class="hint-bar">
      <span class="hint-icon" aria-hidden="true">
        <AppIcon name="info" :size="11" color="#ffffff" />
      </span>
      <span class="hint-text">
        所有报告与表格均锚定真实 DOI，引用可溯源、可核验；AI 审稿建议仅供参考，最终判断由你决定。
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  pendingSummary: {
    type: Object,
    default: null,
  },
})

defineEmits(['pick-quick', 'open-pending'])

const serviceStatus = ref('空闲')

onMounted(() => {
  if (navigator.onLine) serviceStatus.value = '在线'
})

const quickTasks = [
  { key: 'search',    icon: 'search',   label: '检索最新综述', desc: 'RAG 领域高引文献召回',     message: '帮我检索 RAG 最新综述' },
  { key: 'scholar',   icon: 'user',     label: '学者画像',     desc: 'h 指数、代表作与研究布局', message: '查 Yann LeCun 的学者画像' },
  { key: 'cross',     icon: 'layers',   label: '跨界推演',     desc: '两领域融合可行性评估',     message: '推演大模型×量子计算的融合可行性' },
  { key: 'direction', icon: 'bubble',   label: '研究方向',     desc: '思维链与机器人控制',       message: '研究方向：思维链与机器人控制' },
  { key: 'review',    icon: 'scale',    label: 'AI 审稿',     desc: '规范性检查与引用核对',     message: '审稿：帮我检查这段论文摘要' },
]

const pendingItems = computed(() => {
  const s = props.pendingSummary || {}
  return [
    { key: 'reading', label: '待精读文献', icon: 'clipboard', tone: 'warning', count: s.pendingReading ?? 0 },
    { key: 'review',  label: '待审阅草稿', icon: 'scale',     tone: 'warning', count: s.pendingReview ?? 0 },
    { key: 'cited',   label: '高被引关注', icon: 'flame',     tone: 'danger',  count: s.hotCited ?? 0 },
    { key: 'doi',     label: '待溯源 DOI', icon: 'clock',     tone: 'warning', count: s.pendingDoi ?? 0 },
  ]
})
</script>

<style scoped>
.welcome {
  flex: 1;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 1280px;
  margin: 0 auto;
  width: 100%;
}

.hero {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 24px;
  animation: riseIn var(--dur-slow) var(--ease-spring) both;
}
.hero-icon {
  width: 56px; height: 56px;
  border-radius: 14px;
  background: var(--c-primary-soft);
  display: flex; align-items: center; justify-content: center;
  box-shadow: var(--sh-sm);
}
.hero-icon .hero-emoji { font-size: 28px; line-height: 1; }
.hero-text { flex: 1; }
.hero-title {
  font-size: var(--fz-h1);
  font-weight: 700;
  color: var(--c-text);
  letter-spacing: var(--tracking-tight);
  margin-bottom: 6px;
  line-height: 1.2;
  font-family: var(--font-display);
}
.hero-sub {
  font-size: var(--fz-body);
  color: var(--c-text-secondary);
  line-height: 1.6;
  max-width: 640px;
}
.hero-meta { display: flex; gap: 24px; flex-shrink: 0; }
.hero-meta-item { display: flex; flex-direction: column; gap: 4px; }
.meta-label {
  font-size: var(--fz-mini);
  color: var(--c-text-tertiary);
  letter-spacing: var(--tracking-caps);
  font-weight: 600;
  text-transform: uppercase;
}
.meta-value {
  font-size: var(--fz-body);
  color: var(--c-text);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.welcome-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 16px;
}
@media (max-width: 1024px) { .welcome-grid { grid-template-columns: 1fr; } }

.quick-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
@media (max-width: 900px) { .quick-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 600px) { .quick-grid { grid-template-columns: 1fr; } }

.quick-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  border-radius: var(--r-md);
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  text-align: left;
  cursor: pointer;
  transition: transform var(--transition-fast), box-shadow var(--transition), background var(--transition-fast), border-color var(--transition-fast);
}
.quick-card:hover {
  border-color: var(--c-primary);
  box-shadow: var(--sh-md);
  background: var(--c-primary-soft);
}
.quick-card:active { transform: scale(0.99); }
.quick-card:focus-visible { outline: 2px solid var(--c-primary); outline-offset: 2px; }

.quick-glyph {
  width: 34px; height: 34px;
  flex-shrink: 0;
  border-radius: var(--r-sm);
  background: var(--c-primary-soft);
  color: var(--c-primary);
  display: inline-flex; align-items: center; justify-content: center;
}
.glyph-review     { background: var(--c-danger-soft);  color: var(--c-danger); }
.glyph-search     { background: var(--c-primary-soft); color: var(--c-primary); }
.glyph-direction  { background: var(--c-warning-soft); color: var(--c-warning); }
.glyph-cross      { background: var(--c-accent-soft);  color: var(--c-accent); }
.glyph-scholar    { background: var(--c-warning-soft); color: var(--c-warning); }

.quick-text { flex: 1; min-width: 0; }
.quick-title {
  font-size: var(--fz-body);
  font-weight: 600;
  color: var(--c-text);
  line-height: 1.4;
  letter-spacing: var(--tracking-body);
}
.quick-desc {
  font-size: var(--fz-caption);
  color: var(--c-text-secondary);
  margin-top: 4px;
  line-height: 1.55;
}
.quick-arrow {
  color: var(--c-text-tertiary);
  align-self: center;
  transition: transform var(--transition-fast), color var(--transition-fast);
}
.quick-card:hover .quick-arrow {
  transform: translateX(2px);
  color: var(--c-primary);
}

.pending-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
@media (max-width: 600px) { .pending-grid { grid-template-columns: 1fr; } }

.pending-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border-radius: var(--r-md);
  background: var(--c-surface-alt);
  border: 1px solid var(--c-border);
  text-align: left;
  cursor: pointer;
  transition: transform var(--transition-fast), box-shadow var(--transition), background var(--transition-fast), border-color var(--transition-fast);
}
.pending-card:hover {
  background: var(--c-surface);
  border-color: var(--c-primary);
  box-shadow: var(--sh-sm);
}
.pending-card:focus-visible { outline: 2px solid var(--c-primary); outline-offset: 2px; }
.pending-card.pending-warning { border-left: 3px solid var(--c-warning); }
.pending-card.pending-danger  { border-left: 3px solid var(--c-danger); }

.pending-head { display: flex; align-items: center; justify-content: space-between; }
.pending-glyph {
  width: 26px; height: 26px;
  border-radius: var(--r-sm);
  display: inline-flex; align-items: center; justify-content: center;
}
.pending-warning .pending-glyph { background: var(--c-warning); color: var(--c-text-on-primary); }
.pending-danger  .pending-glyph { background: var(--c-danger);  color: var(--c-text-on-primary); }

.pending-count {
  font-size: var(--fz-h3);
  font-weight: 700;
  color: var(--c-text);
  background: var(--c-surface);
  padding: 2px 10px;
  border-radius: var(--r-sm);
  border: 1px solid var(--c-border);
  min-width: 32px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.pending-label {
  font-size: var(--fz-body);
  font-weight: 600;
  color: var(--c-text);
  line-height: 1.4;
}
.pending-action {
  font-size: var(--fz-caption);
  color: var(--c-primary);
  font-weight: 500;
}

.hint-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: var(--r-md);
  background: var(--c-primary-soft);
  color: var(--c-text-secondary);
  font-size: var(--fz-caption);
  line-height: 1.6;
}
.hint-icon {
  width: 18px; height: 18px;
  border-radius: 50%;
  background: var(--c-primary);
  color: var(--c-text-on-primary);
  display: inline-flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
</style>
