<template>
  <div v-if="interruptData" class="interrupt-banner">
    <div class="banner-head">
      <span class="banner-icon">⏸</span>
      <span class="banner-title">{{ titleText }}</span>
    </div>
    <p class="banner-desc">{{ descText }}</p>

    <!-- HITL 审批：显示同意/拒绝按钮 -->
    <div v-if="isApproval" class="banner-actions approval-actions">
      <button class="banner-approve" :disabled="submitting" @click="approve">
        {{ submitting ? '处理中…' : '✓ 同意执行' }}
      </button>
      <button class="banner-reject" :disabled="submitting" @click="reject">
        {{ submitting ? '处理中…' : '✗ 拒绝' }}
      </button>
    </div>

    <!-- 信息补充：文本输入 -->
    <div v-else class="banner-actions">
      <input
        v-model="inputText"
        class="banner-input"
        :placeholder="inputPlaceholder"
        @keyup.enter="submit"
      />
      <button class="banner-submit" :disabled="submitting || !inputText.trim()" @click="submit">
        {{ submitting ? '提交中…' : '提交' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  interruptData: { type: Object, default: null },
  submitting: { type: Boolean, default: false },
})
const emit = defineEmits(['resume'])

const inputText = ref('')

// HITL 审批类型判断（后端 emit hitl_approval / interrupt_type 含 approval）
const isApproval = computed(() => {
  const d = props.interruptData || {}
  return d.interrupt_type === 'hitl_approval' || d.type === 'hitl_approval' || !!d.action_requests
})

const titleText = computed(() => {
  const d = props.interruptData || {}
  if (isApproval.value) return d.title || '需要你的审批'
  return d.title || '需要你的输入'
})
const descText = computed(() => {
  const d = props.interruptData || {}
  if (d.message) return d.message
  if (isApproval.value && Array.isArray(d.action_requests)) {
    const names = d.action_requests.map(a => a.name || a.tool).join(', ')
    return `Agent 请求执行：${names}。请确认是否允许。`
  }
  if (Array.isArray(d.missing_fields) && d.missing_fields.length) {
    return '请补充以下信息：' + d.missing_fields.join('、')
  }
  return '系统需要更多信息才能继续，请在下方回复。'
})
const inputPlaceholder = computed(() => props.interruptData?.placeholder || '请输入补充信息…')

function submit() {
  const val = inputText.value.trim()
  if (!val || props.submitting) return
  emit('resume', { type: 'text', value: val })
  inputText.value = ''
}

function approve() {
  if (props.submitting) return
  emit('resume', { decisions: [{ type: 'approve' }] })
}

function reject() {
  if (props.submitting) return
  emit('resume', { decisions: [{ type: 'reject' }] })
}
</script>

<style scoped>
.interrupt-banner {
  margin: 12px 28px;
  padding: 16px 20px;
  border-radius: var(--r-lg);
  border: 1px solid var(--c-warning);
  background: var(--c-warning-soft);
  animation: slideUp .3s var(--ease-spring);
}
@keyframes slideUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.banner-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.banner-icon { font-size: 18px; }
.banner-title { font-weight: 700; color: var(--c-warning); font-size: var(--fz-body); }
.banner-desc { margin: 0 0 12px; font-size: var(--fz-caption); color: var(--c-text-secondary); line-height: 1.5; }
.banner-actions { display: flex; gap: 8px; }
.banner-input {
  flex: 1; border: 1px solid var(--c-border); border-radius: var(--r-md);
  padding: 10px 14px; font-size: var(--fz-caption); background: var(--c-surface);
}
.banner-input:focus { border-color: var(--c-primary); }
.banner-submit {
  border: none; background: var(--c-primary); color: #fff;
  border-radius: var(--r-md); padding: 10px 20px; font-size: var(--fz-caption); font-weight: 600;
  cursor: pointer; transition: background var(--transition-fast);
}
.banner-submit:hover:not(:disabled) { background: var(--c-primary-hover); }
.banner-submit:disabled { opacity: .6; cursor: not-allowed; }

/* HITL 审批按钮 */
.approval-actions { gap: 10px; }
.banner-approve {
  border: none; background: var(--c-success, #34c759); color: #fff;
  border-radius: var(--r-md); padding: 10px 20px; font-size: var(--fz-caption); font-weight: 600;
  cursor: pointer; transition: background var(--transition-fast);
}
.banner-approve:hover:not(:disabled) { filter: brightness(1.1); }
.banner-reject {
  border: 1px solid var(--c-danger); background: transparent; color: var(--c-danger);
  border-radius: var(--r-md); padding: 10px 20px; font-size: var(--fz-caption); font-weight: 600;
  cursor: pointer; transition: all var(--transition-fast);
}
.banner-reject:hover:not(:disabled) { background: var(--c-danger-soft); }
.banner-approve:disabled, .banner-reject:disabled { opacity: .6; cursor: not-allowed; }
</style>
