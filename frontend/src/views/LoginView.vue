<template>
  <div class="login-page">
    <nav class="navbar">
      <div class="nav-brand">MIROFISH</div>
      <LanguageSwitcher />
    </nav>

    <main class="login-main">
      <form class="login-card" @submit.prevent="submit" novalidate>
        <h1 class="login-title">{{ $t('auth.title') }}</h1>
        <p class="login-subtitle">{{ $t('auth.subtitle') }}</p>

        <label class="field">
          <span class="field-label">{{ $t('auth.username') }}</span>
          <input
            v-model="username"
            class="field-input"
            name="username"
            autocomplete="username"
            autocapitalize="off"
            spellcheck="false"
            autofocus
          />
        </label>

        <label class="field">
          <span class="field-label">{{ $t('auth.password') }}</span>
          <input
            v-model="password"
            class="field-input"
            name="password"
            type="password"
            autocomplete="current-password"
          />
        </label>

        <p v-if="error" class="login-error" role="alert">{{ error }}</p>

        <button class="login-button" type="submit" :disabled="submitting">
          {{ submitting ? $t('auth.submitting') : $t('auth.submit') }}
          <span v-if="!submitting" class="arrow">→</span>
        </button>
      </form>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { login } from '../api/auth'
import { authState, safeRedirect, setToken } from '../utils/auth'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const username = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

const submit = async () => {
  if (submitting.value) return
  error.value = ''
  if (!username.value.trim() || !password.value) {
    error.value = t('auth.required')
    return
  }

  submitting.value = true
  try {
    const res = await login({ username: username.value.trim(), password: password.value })
    if (res.data?.token) {
      setToken(res.data.token)
    }
    authState.authenticated = true
    password.value = ''
    router.replace(safeRedirect(route.query.redirect))
  } catch (err) {
    error.value = err.message || t('common.error')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.login-page {
  --black: #000000;
  --white: #FFFFFF;
  --orange: #FF4500;
  --gray-border: #E5E5E5;
  --gray-text: #666666;
  min-height: 100vh;
  background: var(--white);
  color: var(--black);
  display: flex;
  flex-direction: column;
}

.navbar {
  height: 60px;
  background: var(--black);
  color: var(--white);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
}

.nav-brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  letter-spacing: 1px;
  font-size: 1.2rem;
}

.navbar :deep(.switcher-trigger) {
  color: var(--white);
  border-color: rgba(255, 255, 255, 0.4);
}

.login-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}

.login-card {
  width: 100%;
  max-width: 400px;
  border: 1px solid var(--gray-border);
  padding: 40px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.login-title {
  font-size: 1.6rem;
  font-weight: 600;
  margin: 0;
}

.login-subtitle {
  margin: -8px 0 0;
  color: var(--gray-text);
  font-size: 0.9rem;
  line-height: 1.5;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--gray-text);
}

.field-input {
  border: 1px solid var(--gray-border);
  padding: 12px 14px;
  font-size: 1rem;
  font-family: inherit;
  outline: none;
  transition: border-color 0.2s;
}

.field-input:focus {
  border-color: var(--black);
}

.login-error {
  margin: 0;
  color: #D32F2F;
  font-size: 0.9rem;
}

.login-button {
  background: var(--black);
  color: var(--white);
  border: none;
  padding: 14px 20px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 0.95rem;
  letter-spacing: 1px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background 0.2s;
}

.login-button:hover:not(:disabled) {
  background: var(--orange);
}

.login-button:disabled {
  opacity: 0.6;
  cursor: default;
}

@media (max-width: 600px) {
  .navbar {
    padding: 0 20px;
  }

  .login-card {
    padding: 28px 20px;
  }
}
</style>
