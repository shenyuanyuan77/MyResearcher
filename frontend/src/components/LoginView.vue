<template>
  <div class="login-page">
    <form class="login-card" @submit.prevent="onSubmit">
      <div class="brand-logo">🎓</div>
      <h1>研途智探AI</h1>
      <p class="subtitle">伴随青年学者的全周期数字科研导师</p>

      <div class="field" :class="{ 'has-error': !!error }">
        <label for="login-username">用户名</label>
        <input
          id="login-username"
          v-model="username"
          autocomplete="username"
          required
          :aria-invalid="!!error"
          aria-describedby="login-error"
        />
      </div>
      <div class="field" :class="{ 'has-error': !!error }">
        <label for="login-password">密码</label>
        <input
          id="login-password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          :aria-invalid="!!error"
          aria-describedby="login-error"
        />
      </div>

      <p v-if="error" id="login-error" class="error" role="alert">{{ error }}</p>

      <button type="submit" :disabled="loading">
        {{ loading ? '登录中…' : '登录' }}
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
  background: radial-gradient(1000px 600px at 50% -10%, var(--c-primary-soft) 0%, var(--c-bg) 60%);
  padding: 24px;
}
.login-card {
  width: 100%;
  max-width: 400px;
  background: var(--glass-bg-strong);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border: 1px solid var(--c-border);
  border-radius: var(--r-xl);
  padding: 40px 32px 30px;
  box-shadow: var(--sh-xl);
  display: flex;
  flex-direction: column;
  gap: 14px;
  animation: modalPop var(--dur-slow) var(--ease-spring-strong);
}
.brand-logo {
  width: 68px; height: 68px;
  margin: 0 auto 6px;
  border-radius: 18px;
  background: var(--c-primary-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 38px;
  line-height: 1;
  box-shadow: var(--sh-md);
  animation: riseIn var(--dur-slow) var(--ease-spring) both;
}
h1 {
  text-align: center;
  font-size: var(--fz-h1);
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  margin: 0;
  color: var(--c-text);
  font-family: var(--font-display);
}
.subtitle {
  text-align: center;
  color: var(--c-text-tertiary);
  margin: -6px 0 10px;
  font-size: var(--fz-caption);
}

.field label {
  display: block;
  font-size: var(--fz-caption);
  color: var(--c-text-secondary);
  margin-bottom: 6px;
  font-weight: 500;
}
.field input {
  width: 100%;
  height: 40px;
  padding: 0 13px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  background: var(--c-surface);
  font-size: var(--fz-body);
  font-family: var(--font-body);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.field input:focus {
  border-color: var(--c-primary);
  box-shadow: 0 0 0 4px var(--c-primary-soft);
}
.field.has-error input { border-color: var(--c-danger); }
.field.has-error input:focus { box-shadow: 0 0 0 4px var(--c-danger-soft); }

button {
  margin-top: 10px;
  border: none;
  border-radius: var(--r-md);
  padding: 13px;
  background: var(--c-primary);
  color: var(--c-text-on-primary);
  font-weight: 600;
  font-size: var(--fz-body);
  letter-spacing: var(--tracking-body);
  cursor: pointer;
  font-family: var(--font-body);
  box-shadow: 0 1px 3px var(--c-primary-soft-strong);
  transition: transform var(--transition-fast), box-shadow var(--transition), background var(--transition-fast);
  will-change: transform;
}
button:hover:not(:disabled) { background: var(--c-primary-hover); box-shadow: var(--sh-primary); transform: translateY(-1px); }
button:active:not(:disabled) { transform: scale(0.97); }
button:disabled { opacity: 0.7; cursor: not-allowed; }
button:focus-visible { outline: 2px solid var(--c-primary); outline-offset: 2px; }

.error {
  color: var(--c-danger);
  font-size: var(--fz-caption);
  margin: 0;
  animation: popIn var(--dur-normal) var(--ease-spring) both;
}
.hint {
  text-align: center;
  color: var(--c-text-tertiary);
  font-size: var(--fz-mini);
  margin: 6px 0 0;
}
</style>