<template>
  <button
    v-if="authState.enabled && authState.authenticated"
    class="logout-button"
    type="button"
    @click="logout"
  >
    {{ $t('auth.logout') }}
  </button>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { authState, clearToken } from '../utils/auth'

const router = useRouter()

// Tokens are stateless, so signing out means forgetting this browser's token
const logout = () => {
  clearToken()
  authState.authenticated = false
  router.replace({ name: 'Login' })
}
</script>

<style scoped>
/* Inherits the header's text colour so it works on light and dark headers */
.logout-button {
  background: transparent;
  color: inherit;
  border: 1px solid currentColor;
  opacity: 0.7;
  padding: 4px 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  cursor: pointer;
  transition: opacity 0.2s;
  white-space: nowrap;
}

.logout-button:hover {
  opacity: 1;
}
</style>
