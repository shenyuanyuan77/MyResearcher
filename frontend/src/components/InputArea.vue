<template>
  <div class="input-area">
    <div class="input-container">
      <div class="toolbar-row">
        <label class="toggle-label">
          <input
            type="checkbox"
            role="switch"
            :checked="showToolCalls"
            :aria-checked="showToolCalls"
            aria-label="启用工具调用"
            @change="emit('toggle-tool-calls', $event.target.checked)"
            class="toggle-checkbox"
          />
          <span class="toggle-switch" aria-hidden="true"></span>
          <span class="toggle-text">启用工具调用</span>
        </label>
        <span class="role-pill">
          <AppIcon name="sparkles" :size="12" color="var(--c-primary)" />
          研途智探AI
        </span>
      </div>

      <div class="input-wrapper" :class="{ focused: isFocused, streaming: streaming }">
        <textarea
          ref="textareaRef"
          v-model="inputText"
          :aria-label="placeholder"
          @focus="isFocused = true"
          @blur="isFocused = false"
          @keydown.enter.exact.prevent="handleSend"
          @input="autoResize"
          :placeholder="placeholder"
          rows="1"
          :disabled="streaming"
          class="input-textarea"
        ></textarea>
        <button
          v-if="!streaming"
          class="send-btn"
          :disabled="!inputText.trim()"
          aria-label="发送消息"
          @click="handleSend"
        >
          <span class="send-label">发送</span>
          <AppIcon name="paperPlane" :size="14" color="#ffffff" />
        </button>
        <button v-else class="stop-btn" aria-label="停止生成" @click="handleStop">
          <span>停止</span>
          <AppIcon name="stop" :size="11" color="#ffffff" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  placeholder: { type: String, default: '输入研究方向、检索词、学者姓名，或直接描述你的科研问题…' },
  streaming: { type: Boolean, default: false },
  showToolCalls: { type: Boolean, default: true },
})

const emit = defineEmits(['send', 'stop', 'toggle-tool-calls'])

const inputText = ref('')
const isFocused = ref(false)
const textareaRef = ref(null)

function handleSend() {
  const text = inputText.value.trim()
  if (!text) return
  emit('send', text)
  inputText.value = ''
  nextTick(() => {
    if (textareaRef.value) textareaRef.value.style.height = 'auto'
  })
}

function handleStop() { emit('stop') }

function autoResize() {
  const t = textareaRef.value
  if (!t) return
  t.style.height = 'auto'
  t.style.height = Math.min(t.scrollHeight, 200) + 'px'
}
</script>

<style scoped>
.input-area {
  position: absolute;
  z-index: 20;
  left: 0; right: 0; bottom: 0;
  padding: 16px 18px max(12px, env(safe-area-inset-bottom));
  background: var(--c-bg);
  border-top: 1px solid var(--c-border-light);
  pointer-events: none;
}

.input-container {
  max-width: var(--content-max);
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
  position: relative;
  padding: 10px 10px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-xl);
  box-shadow: var(--sh-md);
  pointer-events: auto;
  transition: box-shadow var(--transition), border-color var(--transition-fast);
}
.input-container:focus-within {
  border-color: var(--c-primary);
  box-shadow: var(--sh-lg), 0 0 0 4px var(--c-primary-soft);
}

.toolbar-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.toggle-label {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
  user-select: none;
  font-size: var(--fz-mini);
  color: var(--c-text-secondary);
}
.toggle-checkbox { position: absolute; opacity: 0; pointer-events: none; }
.toggle-switch {
  position: relative;
  width: 30px; height: 18px;
  background: var(--c-muted-soft);
  border-radius: var(--r-pill);
  transition: background var(--transition);
}
.toggle-switch::after {
  content: '';
  position: absolute;
  top: 2px; left: 2px;
  width: 14px; height: 14px;
  background: #fff;
  border-radius: 50%;
  box-shadow: var(--sh-xs);
  transition: transform var(--transition);
}
.toggle-checkbox:checked + .toggle-switch { background: var(--c-success); }
.toggle-checkbox:checked + .toggle-switch::after { transform: translateX(12px); }
.toggle-checkbox:focus-visible + .toggle-switch {
  outline: 2px solid var(--c-primary);
  outline-offset: 2px;
}
.toggle-text { font-weight: 500; }

.role-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 22px;
  padding: 0 10px;
  border-radius: var(--r-pill);
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: var(--fz-mini);
  font-weight: 500;
}

.input-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 4px 16px;
  background: transparent;
  border-radius: calc(var(--r-xl) - 8px);
  transition: background var(--transition-fast);
}
.input-wrapper.streaming { background: var(--c-danger-soft); }

.input-textarea {
  flex: 1;
  border: none;
  background: transparent;
  font-size: var(--fz-body);
  line-height: 22px;
  padding: 8px 0;
  resize: none;
  outline: none;
  min-height: 38px;
  max-height: 200px;
  color: var(--c-text);
  font-weight: 400;
  letter-spacing: var(--tracking-body);
  font-family: var(--font-body);
  align-self: center;
}
.input-textarea::placeholder { color: var(--c-text-tertiary); }
.input-textarea:disabled { opacity: 0.6; cursor: not-allowed; }

.send-btn {
  flex-shrink: 0;
  align-self: center;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 14px 0 18px;
  background: var(--c-primary);
  color: var(--c-text-on-primary);
  border: none;
  border-radius: calc(var(--r-xl) - 8px);
  font-size: var(--fz-caption);
  font-weight: 600;
  letter-spacing: var(--tracking-body);
  cursor: pointer;
  box-shadow: 0 1px 3px var(--c-primary-soft-strong);
  transition: transform var(--transition-fast), box-shadow var(--transition), background var(--transition-fast);
  will-change: transform;
}
.send-btn:hover:not(:disabled) { background: var(--c-primary-hover); box-shadow: var(--sh-primary); transform: translateY(-1px); }
.send-btn:active:not(:disabled) { transform: scale(0.94); }
.send-btn:disabled { background: var(--c-muted-soft); color: var(--c-text-tertiary); cursor: not-allowed; box-shadow: none; }
.send-btn:focus-visible { outline: 2px solid var(--c-primary); outline-offset: 2px; }

.stop-btn {
  flex-shrink: 0;
  align-self: center;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 14px;
  background: var(--c-danger);
  color: var(--c-text-on-primary);
  border: none;
  border-radius: calc(var(--r-xl) - 8px);
  font-size: var(--fz-caption);
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 2px 8px var(--c-danger-soft);
  animation: stopPulse 2s var(--ease-ios) infinite;
  transition: transform var(--transition-fast), box-shadow var(--transition);
}
.stop-btn:hover { transform: translateY(-1px); }
.stop-btn:active { transform: scale(0.94); }
.stop-btn:focus-visible { outline: 2px solid var(--c-danger); outline-offset: 2px; }

@media (max-width: 760px) {
  .input-area { padding: 12px 14px max(12px, env(safe-area-inset-bottom)); }
  .send-label, .stop-btn span { display: none; }
  .send-btn { width: 38px; padding: 0; }
  .stop-btn { width: 38px; padding: 0; }
}
</style>