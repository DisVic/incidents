<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
// Импорт хранилища авторизации
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
// Получение данных пользователя из хранилища
const authStore = useAuthStore()

// Поля формы
// Email пользователя
const email = ref('') // Email пользователя
// Пароль пользователя
const password = ref('') // Пароль
// Сообщение об ошибке
const error = ref('') // Сообщение об ошибке
const loading = ref(false) // Флаг загрузки при авторизации

// Обработка входа в систему
const handleLogin = async () => {
  error.value = ''
  loading.value = true
  
  try {
    await authStore.login(email.value, password.value)
    // Перенаправляем на страницу, с которой пришли, или на главную
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (err) {
    error.value = err.response?.data?.detail || 'Ошибка авторизации'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
    <div class="max-w-md w-full mx-4">
      <!-- Логотип -->
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-white mb-2">IMS</h1>
        <p class="text-slate-400">Система управления инцидентами</p>
      </div>
      
      <!-- Форма входа -->
      <div class="bg-white rounded-2xl shadow-2xl p-8">
        <h2 class="text-2xl font-bold text-slate-800 mb-6">Вход в систему</h2>
        
        <form @submit.prevent="handleLogin">
          <!-- Сообщение об ошибке -->
          <div v-if="error" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
            {{ error }}
          </div>
          
          <!-- Email -->
          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-700 mb-2">Email</label>
            <input
              v-model="email"
              type="email"
              required
              class="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
              placeholder="Введите email"
            />
          </div>
          
          <!-- Пароль -->
          <div class="mb-6">
            <label class="block text-sm font-medium text-slate-700 mb-2">Пароль</label>
            <input
              v-model="password"
              type="password"
              required
              class="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
              placeholder="Введите пароль"
            />
          </div>
          
          <!-- Кнопка входа -->
          <button
            type="submit"
            :disabled="loading"
            class="w-full py-3 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span v-if="loading">Вход...</span>
            <span v-else>Войти</span>
          </button>
          
          <!-- Ссылка на восстановление пароля -->
          <div class="mt-4 text-center">
            <router-link to="/forgot-password" class="text-sm text-primary-600 hover:text-primary-700">
              Забыли пароль?
            </router-link>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
