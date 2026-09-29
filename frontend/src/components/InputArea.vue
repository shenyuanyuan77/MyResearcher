<template>
  <div class="input-area">
    <div class="input-container">
      <div class="toolbar-row">
        <div class="toolbar-left">
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
          <!-- 科研技能选择器 -->
          <div ref="pickerWrapRef" class="skill-picker-wrap">
            <button
              type="button"
              class="skill-picker-btn"
              :class="{ open: skillPickerOpen }"
              aria-label="选择科研技能"
              @click="skillPickerOpen = !skillPickerOpen"
            >
              <AppIcon name="sparkles" :size="12" />
              <span>技能</span>
            </button>
            <transition name="picker-fade">
              <div v-if="skillPickerOpen" class="skill-picker-panel">
                <div class="picker-head">科研技能（{{ skills.length }}）</div>
                <div class="picker-list">
                  <div v-for="group in skillGroups" :key="group.name" class="picker-group">
                    <div class="picker-group-label">{{ group.icon }} {{ group.name }}</div>
                    <button
                      v-for="s in group.items"
                      :key="s.id"
                      class="picker-item"
                      :title="s.summary"
                      @click="pickSkill(s)"
                    >
                      <span class="picker-zh">{{ s.zh }}</span>
                      <span class="picker-cat">{{ s.category }}</span>
                    </button>
                  </div>
                </div>
              </div>
            </transition>
          </div>
        </div>
        <span class="role-pill">
          <AppIcon name="sparkles" :size="12" color="var(--c-primary)" />
          MyResearcher
        </span>
      </div>

      <div class="input-wrapper" :class="{ focused: isFocused, streaming: streaming }">
        <!-- 文件上传按钮 -->
        <label class="upload-btn" :class="{ uploading }" :title="streaming ? '生成中不可上传' : '上传 PDF/Word 精读'">
          <AppIcon :name="uploading ? 'attachment' : 'attachment'" :size="16" :class="{ spinning: uploading }" />
          <input
            type="file"
            accept=".pdf,.docx,.doc,.txt,application/pdf"
            class="upload-input"
            :disabled="streaming || uploading"
            @change="handleUpload"
          />
        </label>
        <textarea
          ref="textareaRef"
          v-model="inputText"
          :aria-label="placeholder"
          @focus="isFocused = true"
          @blur="isFocused = false"
          @keydown.enter.exact.prevent="handleSend"
          @keydown.arrow-up.prevent="editLastMessage"
          @keydown.esc="inputText = ''"
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
          <AppIcon name="paperPlane" :size="14" />
        </button>
        <button v-else class="stop-btn" aria-label="停止生成" @click="handleStop">
          <span>停止</span>
          <AppIcon name="stop" :size="11" />
        </button>
      </div>
      <!-- 字数/token 提示 + 快捷键提示 -->
      <div class="input-hint">
        <span class="char-count" :class="{ warn: charCount > 4000 }">
          {{ charCount }} 字 · 约 {{ estimatedTokens }} token
        </span>
        <span class="shortcut-hint">
          <kbd>Enter</kbd> 发送 · <kbd>↑</kbd> 编辑上条 · <kbd>Esc</kbd> 清空
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import AppIcon from './AppIcon.vue'
import { listSkills } from '../api/skills.js'

const props = defineProps({
  placeholder: { type: String, default: '输入研究方向、检索词、学者姓名，或直接描述你的科研问题…' },
  streaming: { type: Boolean, default: false },
  showToolCalls: { type: Boolean, default: true },
  presetText: { type: String, default: '' },  // 外部注入文本（quote/edit 时用）
})

const emit = defineEmits(['send', 'stop', 'toggle-tool-calls', 'edit-last', 'upload-result', 'preset-consumed'])

// 外部 presetText 变化时注入输入框（append 模式，光标聚焦末尾）
watch(() => props.presetText, (val) => {
  if (!val) return
  inputText.value = inputText.value
    ? `${inputText.value}\n\n${val}`
    : val
  emit('preset-consumed')  // 通知父组件已消费
  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.focus()
      autoResize()
    }
  })
})

const inputText = ref('')
const isFocused = ref(false)
const textareaRef = ref(null)
const uploading = ref(false)

// ===== 科研技能选择器 =====
const skills = ref([])
const skillCategories = ref([])
const skillPickerOpen = ref(false)
const pickerWrapRef = ref(null)

// 按分类分组（保持 API 返回的六大生命周期顺序）
const skillGroups = computed(() =>
  skillCategories.value
    .map((c) => ({
      name: c.name,
      icon: c.icon || '📦',
      items: skills.value.filter((s) => s.category === c.name),
    }))
    .filter((g) => g.items.length > 0)
)

async function loadSkillCatalog() {
  const data = await listSkills()
  skills.value = data.skills
  skillCategories.value = data.categories
}

function pickSkill(skill) {
  const text = skill.example || `请用「${skill.zh}」技能帮我处理：`
  inputText.value = inputText.value ? `${inputText.value}\n\n${text}` : text
  skillPickerOpen.value = false
  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.focus()
      autoResize()
    }
  })
}

function onDocClick(e) {
  if (pickerWrapRef.value && !pickerWrapRef.value.contains(e.target)) {
    skillPickerOpen.value = false
  }
}
onMounted(() => {
  loadSkillCatalog()
  document.addEventListener('click', onDocClick)
})
onUnmounted(() => document.removeEventListener('click', onDocClick))

async function handleUpload(e) {
  const file = e.target.files?.[0]
  if (!file) return
  e.target.value = ''  // 清空，允许重复上传同文件
  uploading.value = true
  try {
    const { uploadFile } = await import('../api/upload.js')
    const result = await uploadFile(file)
    // 把精读结果注入输入框（用户可编辑后发送），并 emit 供上层展示
    const summary = [
      `📄 已上传《${result.filename}》（${result.full_text_chars} 字）`,
      result.abstract_hint ? `\n\n**摘要提示**：${result.abstract_hint}` : '',
      result.quotable_sentences?.length
        ? `\n\n**可引用句**：\n${result.quotable_sentences.slice(0, 3).map(s => '- ' + s).join('\n')}`
        : '',
      `\n\n请基于这篇论文帮我：精读提炼 / 综述对比 / 审稿。`,
    ].join('')
    inputText.value = summary
    emit('upload-result', result)
    nextTick(() => autoResize())
  } catch (err) {
    alert(`上传失败：${err.message}`)
  } finally {
    uploading.value = false
  }
}

// 字数与 token 估算（中文≈1.5 token/字，英文≈0.25 token/字，粗估）
const charCount = computed(() => inputText.value.length)
const estimatedTokens = computed(() => {
  const cn = (inputText.value.match(/[\u4e00-\u9fff]/g) || []).length
  const en = inputText.value.length - cn
  return Math.round(cn * 1.5 + en * 0.25)
})

function handleSend() {
  const text = inputText.value.trim()
  if (!text) return
  emit('send', text)
  inputText.value = ''
  nextTick(() => {
    if (textareaRef.value) textareaRef.value.style.height = 'auto'
  })
}

function editLastMessage() {
  // 输入框为空时按 ↑ 编辑上一条消息
  if (inputText.value.trim()) return
  emit('edit-last')
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
  max-width: calc(var(--content-max) + 48px);
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
.toolbar-left { display: inline-flex; align-items: center; gap: 14px; min-width: 0; }

/* ===== 科研技能选择器 ===== */
.skill-picker-wrap { position: relative; }
.skill-picker-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 10px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-pill);
  background: var(--c-surface);
  color: var(--c-text-secondary);
  font-size: var(--fz-mini);
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
}
.skill-picker-btn:hover,
.skill-picker-btn.open {
  border-color: var(--c-primary);
  color: var(--c-primary);
  background: var(--c-primary-soft);
}
.skill-picker-panel {
  position: absolute;
  bottom: calc(100% + 10px);
  left: 0;
  width: min(340px, 78vw);
  max-height: 320px;
  display: flex;
  flex-direction: column;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  box-shadow: var(--sh-lg);
  overflow: hidden;
  z-index: 40;
}
.picker-head {
  padding: 10px 14px 8px;
  font-size: var(--fz-mini);
  font-weight: 700;
  color: var(--c-text-tertiary);
  border-bottom: 1px solid var(--c-border-light);
}
.picker-list { overflow-y: auto; padding: 6px; }
.picker-group { margin-bottom: 4px; }
.picker-group-label {
  padding: 8px 10px 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .04em;
  color: var(--c-text-tertiary);
  border-bottom: 1px dashed var(--c-border-light);
  margin-bottom: 2px;
}
.picker-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border: none;
  border-radius: var(--r-sm);
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background var(--transition-fast);
}
.picker-item:hover { background: var(--c-primary-soft); }
.picker-zh { font-size: var(--fz-caption); font-weight: 600; color: var(--c-text); }
.picker-item:hover .picker-zh { color: var(--c-primary); }
.picker-cat {
  font-size: var(--fz-mini);
  color: var(--c-text-tertiary);
  flex-shrink: 0;
}
.picker-fade-enter-active, .picker-fade-leave-active { transition: opacity .16s, transform .16s; }
.picker-fade-enter-from, .picker-fade-leave-to { opacity: 0; transform: translateY(6px); }

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
  background: var(--brand-grad, var(--c-primary));
  color: var(--c-text-on-primary);
  border: none;
  border-radius: calc(var(--r-xl) - 8px);
  font-size: var(--fz-caption);
  font-weight: 600;
  letter-spacing: var(--tracking-body);
  cursor: pointer;
  box-shadow: 0 1px 3px var(--c-primary-soft-strong);
  transition: transform var(--transition-fast), box-shadow var(--transition), filter var(--transition-fast);
  will-change: transform;
}
.send-btn:hover:not(:disabled) { filter: brightness(1.08); box-shadow: var(--sh-primary); transform: translateY(-1px); }
.send-btn:active:not(:disabled) { transform: scale(0.94); }
.send-btn:disabled {
  background: var(--c-muted-soft); color: var(--c-text-secondary); cursor: not-allowed;
  box-shadow: none; border: 1px dashed var(--c-border-strong);
}
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

/* 字数/token 提示 + 快捷键提示 */
.input-hint {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 4px 0;
  font-size: var(--fz-mini);
  color: var(--c-text-tertiary);
}

/* 上传按钮 */
.upload-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border-radius: var(--r-sm);
  color: var(--c-text-tertiary);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.upload-btn:hover:not(.uploading) {
  background: var(--c-primary-soft);
  color: var(--c-primary);
}
.upload-btn.uploading {
  opacity: 0.6;
  cursor: wait;
}
.upload-btn.uploading :deep(svg),
.upload-btn .spinning {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.8; }
}
.upload-input {
  position: absolute;
  width: 1px; height: 1px;
  opacity: 0;
  overflow: hidden;
}
.char-count.warn { color: var(--c-warning); }
.shortcut-hint kbd {
  display: inline-block;
  padding: 1px 5px;
  border: 1px solid var(--c-border);
  border-radius: 3px;
  background: var(--c-surface);
  font-family: var(--font-mono, monospace);
  font-size: 10px;
  margin: 0 1px;
}
@media (max-width: 600px) {
  .shortcut-hint { display: none; }  /* 移动端隐藏快捷键提示 */
}
</style>