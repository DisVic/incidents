import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

const API_URL = '/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('access_token') || null)
  const refreshToken = ref(localStorage.getItem('refresh_token') || null)
  const initialized = ref(false)

  const isAuthenticated = computed(() => !!token.value)
  
  const isManager = computed(() => {
    if (!user.value) return false
    return ['Manager', 'Admin'].includes(user.value.role_name)
  })
  
  const isAdmin = computed(() => {
    if (!user.value) return false
    return user.value.role_name === 'Admin'
  })

  const isExecutor = computed(() => {
    if (!user.value) return false
    return ['Executor', 'Manager', 'Admin'].includes(user.value.role_name)
  })

  async function login(email, password) {
    try {
      const response = await axios.post(`${API_URL}/auth/login`, { email, password })
      token.value = response.data.access_token
      refreshToken.value = response.data.refresh_token
      
      localStorage.setItem('access_token', token.value)
      localStorage.setItem('refresh_token', refreshToken.value)
      
      axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
      
      await fetchUser()
      return true
    } catch (error) {
      console.error('Login error:', error)
      throw error
    }
  }

  async function fetchUser() {
    try {
      const response = await axios.get(`${API_URL}/auth/me`)
      user.value = response.data
      return response.data
    } catch (error) {
      console.error('Fetch user error:', error)
      logout()
      throw error
    }
  }

  async function refresh() {
    try {
      const response = await axios.post(`${API_URL}/auth/refresh`, null, {
        params: { refresh_token: refreshToken.value }
      })
      token.value = response.data.access_token
      refreshToken.value = response.data.refresh_token
      
      localStorage.setItem('access_token', token.value)
      localStorage.setItem('refresh_token', refreshToken.value)
      
      axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
      return true
    } catch (error) {
      console.error('Refresh token error:', error)
      logout()
      throw error
    }
  }

  function logout() {
    user.value = null
    token.value = null
    refreshToken.value = null
    
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    
    delete axios.defaults.headers.common['Authorization']
  }

  // Initialize axios with token if exists
  if (token.value) {
    axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
  }

  async function init() {
    if (token.value && !user.value) {
      try {
        await fetchUser()
      } catch {
        // Token invalid, already logged out in fetchUser
        // Don't redirect here - let router handle it
      }
    }
    initialized.value = true
  }

  // Axios interceptors
  axios.interceptors.response.use(
    response => response,
    async error => {
      const originalRequest = error.config
      
      // Don't retry for login/refresh endpoints
      if (originalRequest.url?.includes('/auth/login') || originalRequest.url?.includes('/auth/refresh')) {
        logout()
        return Promise.reject(error)
      }
      
      if (error.response?.status === 401 && refreshToken.value && !originalRequest._retry) {
        originalRequest._retry = true
        try {
          await refresh()
          return axios.request(originalRequest)
        } catch {
          logout()
          window.location.href = '/login'
        }
      } else if (error.response?.status === 401) {
        logout()
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }
  )

  return {
    user,
    token,
    initialized,
    isAuthenticated,
    isManager,
    isAdmin,
    isExecutor,
    login,
    fetchUser,
    refresh,
    logout,
    init
  }
})
