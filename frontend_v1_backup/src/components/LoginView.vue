<template>
  <div class="login-page">
    <form class="login-card" @submit.prevent="onSubmit">
      <div class="brand-logo">🎓</div>
      <h1>MyResearcher</h1>
      <p class="subtitle">伴随青年学者的全周期数字科研导师</p>

      <label>
        用户名
        <input v-model="username" autocomplete="username" required />
      </label>
      <label>
        密码
        <input v-model="password" type="password" autocomplete="current-password" required />
      </label>

      <p v-if="error" class="error">{{ error }}</p>

      <button type="submit" :disabled="loading">
        {{ loading ? '登录中...' : '登录' }}
      </button>
      <p class="hint">默认账号 yanjiu / yanjiu123（可在 .env 的 AUTH_USERS 修改）</p>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { login } from '../api/auth.js'

const emit = defineEmits(['success'])

const username = ref('yanjiu')
const password = ref('yanjiu123')
const loading = ref(false)
const error = ref('')

async function onSubmit() {
  loading.value = true
  error.value = ''
  try {
    const data = await login(username.value.trim(), password.value)
    emit('success', data.user)
  } catch (e) {
    error.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--c-bg);
  padding: 24px;
}
.login-card {
  width: 100%;
  max-width: 400px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  padding: 36px 28px 28px;
  box-shadow: var(--sh-lg);
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.brand-logo {
  width: 64px;
  height: 64px;
  margin: 0 auto 4px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 38px;
  background: var(--c-primary-soft);
}
h1 {
  text-align: center;
  font-size: 24px;
  margin: 0;
  color: #0f172a;
}
.subtitle {
  text-align: center;
  color: #64748b;
  margin: -6px 0 8px;
  font-size: 14px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #334155;
  font-weight: 600;
}
input {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 14px;
}
button {
  margin-top: 8px;
  border: none;
  border-radius: 10px;
  padding: 12px;
  background: var(--c-primary);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
button:hover:not(:disabled) {
  background: var(--c-primary-hover);
}
.error {
  color: #dc2626;
  font-size: 13px;
  margin: 0;
}
.hint {
  text-align: center;
  color: #94a3b8;
  font-size: 12px;
  margin: 4px 0 0;
}
</style>
