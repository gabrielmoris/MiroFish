import axios from 'axios'
import i18n from '../i18n'
import { authState, clearToken, getToken } from '../utils/auth'

// 登录失效时回到登录页（动态导入 router，避免循环依赖）
const handleAuthRequired = async () => {
  clearToken()
  authState.authenticated = false
  const { default: router } = await import('../router')
  const current = router.currentRoute.value
  if (current.name !== 'Login') {
    router.replace({ name: 'Login', query: { redirect: current.fullPath } })
  }
}

// 创建axios实例
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001',
  timeout: 300000, // 5分钟超时（本体生成可能需要较长时间）
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
service.interceptors.request.use(
  config => {
    config.headers['Accept-Language'] = i18n.global.locale.value
    const token = getToken()
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器（容错重试机制）
service.interceptors.response.use(
  response => {
    const res = response.data
    
    // 如果返回的状态码不是success，则抛出错误
    if (!res.success && res.success !== undefined) {
      console.error('API Error:', res.error || res.message || 'Unknown error')
      return Promise.reject(new Error(res.error || res.message || 'Error'))
    }
    
    return res
  },
  error => {
    console.error('Response error:', error)
    const apiError = error.response?.data?.error || error.response?.data?.message
    
    // 未登录或令牌已过期（错误的用户名/密码不带此 code，由登录页自行显示）
    if (error.response?.status === 401 && error.response?.data?.code === 'auth_required') {
      handleAuthRequired()
    }

    // 处理超时
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      console.error('Request timeout')
    }
    
    // 处理网络错误
    if (error.message === 'Network Error') {
      console.error('Network error - please check your connection')
    }

    // Axios rejects non-2xx responses before the success interceptor can
    // surface the backend's safe, actionable error message.
    if (typeof apiError === 'string' && apiError) {
      error.message = apiError
    }
    
    return Promise.reject(error)
  }
)

export default service
