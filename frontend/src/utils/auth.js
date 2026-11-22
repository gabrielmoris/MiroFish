import { reactive } from 'vue'

const TOKEN_KEY = 'mirofish_auth_token'

// Fallback when localStorage is unavailable (private mode, blocked storage)
let memoryToken = null

export const authState = reactive({
  checked: false,
  enabled: false,
  authenticated: false
})

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || memoryToken
  } catch {
    return memoryToken
  }
}

export function setToken(token) {
  memoryToken = token
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // keep the in-memory copy only
  }
}

export function clearToken() {
  memoryToken = null
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    // nothing stored
  }
}

// Only follow same-app paths after login, never an external URL
export function safeRedirect(target) {
  if (typeof target === 'string' && target.startsWith('/') && !target.startsWith('//')) {
    return target
  }
  return '/'
}
