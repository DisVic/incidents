import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

const API_URL = '/api'

export const useAuthStore = defineStore('auth', () => {
  // Состояние пользователя и токенов
  const user = ref(null) // Данные текущего пользователя
  const token = ref(localStorage.getItem('access_token') || null) // Access токен из localStorage
  const refreshToken = ref(localStorage.getItem('refresh_token') || null) // Refresh токен из localStorage
  const initialized = ref(false) // Флаг инициализации хранилища

  // Проверка авторизации
  const isAuthenticated = computed(() => !!token.value)
  
  // Проверка роли менеджера (Manager или Admin)
  const isManager = computed(() => {
    if (!user.value) return false
    return ['Manager', 'Admin'].includes(user.value.role_name)
  })
  
  // Проверка роли админа
  const isAdmin = computed(() => {
    if (!user.value) return false
    return user.value.role_name === 'Admin'
  })

  // Проверка роли исполнителя (Executor, Manager или Admin)
  const isExecutor = computed(() => {
    if (!user.value) return false
    return ['Executor', 'Manager', 'Admin'].includes(user.value.role_name)
  })

  // Логин пользователя
  // Вход пользователя
async function login(email, password) {
    try {
      const response = await axios.post(`${API_URL}/auth/login`, { email, password })
      token.value = response.data.access_token
      refreshToken.value = response.data.refresh_token
      
      // Сохраняем токены в localStorage
      localStorage.setItem('access_token', token.value)
      localStorage.setItem('refresh_token', refreshToken.value)
      
      // Устанавливаем заголовок авторизации для всех запросов
      axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
      
      await fetchUser()
      return true
    } catch (error) {
      console.error('Login error:', error)
      throw error
    }
  }

  // Получение данных текущего пользователя
  // Получение данных текущего пользователя
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

  // Обновление токенов через refresh endpoint
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

  // Выход из системы — очистка данных и токенов
  function logout() {
    user.value = null
    token.value = null
    refreshToken.value = null
    
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    
    delete axios.defaults.headers.common['Authorization']
  }

  // Инициализация токена при загрузке — устанавливаем заголовок авторизации
  if (token.value) {
    axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
  }

  // Инициализация хранилища — загружаем пользователя если есть токен
  async function init() {
    if (token.value && !user.value) {
      try {
        await fetchUser()
      } catch {
        // Токен невалиден, уже выполнен logout
      }
    }
    initialized.value = true
  }

  // Перехватчик ответов axios для обработки 401 ошибок и авто-обновления токена
  axios.interceptors.response.use(
    response => response,
    async error => {
      const originalRequest = error.config
      
      // Не пытаемся обновить токен для эндпоинтов авторизации
      if (originalRequest.url?.includes('/auth/login') || originalRequest.url?.includes('/auth/refresh')) {
        logout()
        return Promise.reject(error)
      }
      
      // При 401 ошибке пробуем обновить токен (только один раз)
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
