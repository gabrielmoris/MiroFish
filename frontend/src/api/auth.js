import service from './index'

/**
 * Whether login is required and whether the stored token is still valid
 * @returns {Promise} { data: { enabled, authenticated } }
 */
export const getAuthStatus = () => {
  return service.get('/api/auth/status')
}

/**
 * Exchange the username and password for a token
 * @param {Object} data - { username, password }
 * @returns {Promise} { data: { token, expires_in } }
 */
export const login = (data) => {
  return service.post('/api/auth/login', data)
}
