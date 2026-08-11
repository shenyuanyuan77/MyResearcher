<template>
  <div v-if="interruptData" class="interrupt-banner banner-unknown">
    <div class="banner-head">
      <span class="banner-icon">⏸</span>
      <span class="banner-title">需要你的输入</span>
    </div>
    <p class="banner-desc">
      {{ interruptData.message || (interruptData.missing_fields && interruptData.missing_fields.length
        ? '请补充以下信息：' + interruptData.missing_fields.join('、')
        : '系统需要更多信息才能继续，请在下方回复。') }}
    </p>
    <div class="banner-actions">
      <input
        v-model="inputText"
        class="banner-input"
        :placeholder="inputPlaceholder"
        @keyup.enter="submit"
      />
      <button class="banner-submit" :disabled="submitting" @click="submit">
        {{ submitting ? '提交中...' : '提交' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  interruptData: { type: Object, default: null },
  submitting: { type: Boolean, default: false },
})
const emit = defineEmits(['resume'])

const inputText = ref('')
const inputPlaceholder = computed(() => '请输入补充信息...')

function submit() {
  const val = inputText.value.trim()
  if (!val) return
  emit('resume', { type: 'text', value: val })
  inputText.value = ''
}
</script>

<style scoped>
.interrupt-banner {
  margin: 12px 22px; padding: 14px 18px; border-radius: 12px;
  border: 1px solid var(--c-warning); background: var(--c-warning-soft);
}
.banner-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.banner-icon { font-size: 18px; }
.banner-title { font-weight: 700; color: var(--c-warning); font-size: 14px; }
.banner-desc { margin: 0 0 10px; font-size: 13px; color: var(--c-text-secondary); }
.banner-actions { display: flex; gap: 8px; }
.banner-input {
  flex: 1; border: 1px solid var(--c-border); border-radius: 8px;
  padding: 9px 12px; font-size: 13px; background: #fff;
}
.banner-submit {
  border: none; background: var(--c-primary); color: #fff;
  border-radius: 8px; padding: 9px 18px; font-size: 13px; font-weight: 600; cursor: pointer;
}
.banner-submit:disabled { opacity: .7; cursor: not-allowed; }
</style>
