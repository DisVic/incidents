/**
 * Auth Store — управление аутентификацией и правами доступа.
 * 
 * State:
 * - user: данные текущего пользователя
 * - token/refreshToken: JWT токены (хранятся в localStorage)
 * - initialized: флаг завершения инициализации
 * 
 * Computed:
 * - isAuthenticated: есть ли токен
 * - isManager: Manager или Admin (доступ к дашборду)
 * - isAdmin: только Admin (управление пользователями/настройками)
 * - isExecutor: Executor/Manager/Admin (может брать инциденты)
 * 
 * Actions:
 * - login: вход по email/password
 * - fetchUser: загрузка данных пользователя
 * - refresh: обновление access-токена
 * - logout: выход с очисткой localStorage
 * - init: инициализация при загрузке приложения
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

const API_URL = '/api'

export const useAuthStore = defineStore('auth', () => {
  // === State ===
  const user = ref(null)  // Данные пользователя {id, email, full_name, role_name, department_id, ...}
  const token = ref(localStorage.getItem('access_token') || null)
  const refreshToken = ref(localStorage.getItem('refresh_token') || null)
  const initialized = ref(false)  // Флаг инициализации (проверка токена при загрузке)

  // === Computed ===
  const isAuthenticated = computed(() => !!token.value)
  
  // Manager или Admin (доступ к дашборду)
  const isManager = computed(() => {
    if (!user.value) return false
    return ['Manager', 'Admin'].includes(user.value.role_name)
  })
  
  // Только Admin
  const isAdmin = computed(() => {
    if (!user.value) return false
    return user.value.role_name === 'Admin'
  })

  // Может брать инциденты в работу
  const isExecutor = computed(() => {
    if (!user.value) return false
    return ['Executor', 'Manager', 'Admin'].includes(user.value.role_name)
  })

  // === Actions ===
  
  /**
   * Вход по email и паролю.
   * @param {string} email 
   * @param {string} password
   * @returns {Promise<boolean>}
   */
  async function login(email, password) {
    // Вход: получает токены, сохраняет в localStorage, загружает пользователя
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

  /**
   * Загрузка данных текущего пользователя (/auth/me).
   * @returns {Promise<Object>}
   */
  async function fetchUser() {
    // Загружает данные текущего пользователя (/auth/me)
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

  /**
   * Обновление access-токена по refresh-токену.
   * @returns {Promise<boolean>}
   */
  async function refresh() {
    // Обновляет access-токен по refresh-токену
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

  /**
   * Выход: очистка state и localStorage.
   */
  function logout() {
    // Выход: очищает state и localStorage
    user.value = null
    token.value = null
    refreshToken.value = null
    
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    
    delete axios.defaults.headers.common['Authorization']
  }

  // Установка токена при инициализации (если есть в localStorage)
  if (token.value) {
    axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
  }

  /**
   * Инициализация при загрузке приложения.
   * Проверяет токен из localStorage, загружает пользователя.
   */
  async function init() {
    // Инициализация при загрузке приложения: проверяет токен, загружает пользователя
    if (token.value && !user.value) {
      try {
        await fetchUser()
      } catch {
        // Токен невалиден — logout вызывается в fetchUser
      }
    }
    initialized.value = true
  }

  // Axios interceptor: авто-обновление токена при 401
  axios.interceptors.response.use(
    response => response,
    async error => {
      const originalRequest = error.config
      
      // Не повторяем запрос для login/refresh
      if (originalRequest.url?.includes('/auth/login') || originalRequest.url?.includes('/auth/refresh')) {
        logout()
        return Promise.reject(error)
      }
      
      // При 401 пытаемся обновить токен
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