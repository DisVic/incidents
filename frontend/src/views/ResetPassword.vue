<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const route = useRoute()

// Токен из URL и поля формы
const token = ref('')
// Новый пароль
const newPassword = ref('')
// Подтверждение пароля
const confirmPassword = ref('')
// Сообщение об ошибке
const error = ref('')
const success = ref(false)
const loading = ref(false)

// Получение токена из query-параметров при загрузке
onMounted(() => {
  token.value = route.query.token || ''
  if (!token.value) {
    error.value = 'Неверная ссылка для сброса пароля'
  }
})

// Валидация и отправка нового пароля
const handleSubmit = async () => {
  error.value = ''
  
  if (newPassword.value.length < 8) {
    error.value = 'Пароль должен содержать минимум 8 символов'
    return
  }
  
  if (newPassword.value !== confirmPassword.value) {
    error.value = 'Пароли не совпадают'
    return
  }
  
  loading.value = true
  
  try {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    await axios.post(`${apiUrl}/api/auth/reset-password`, {
      token: token.value,
      new_password: newPassword.value
    })
    success.value = true
  } catch (err) {
    error.value = err.response?.data?.detail || 'Ошибка сброса пароля'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
    <div class="max-w-md w-full mx-4">
      <!-- Logo -->
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-white mb-2">IMS</h1>
        <p class="text-slate-400">Система управления инцидентами</p>
      </div>
      
      <!-- Form -->
      <div class="bg-white rounded-2xl shadow-2xl p-8">
        <h2 class="text-2xl font-bold text-slate-800 mb-6">Новый пароль</h2>
        
        <!-- Success message -->
        <div v-if="success" class="text-center">
          <div class="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700">
            <svg class="w-12 h-12 mx-auto mb-2 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p class="font-medium">Пароль изменён!</p>
            <p class="text-sm mt-1">Теперь вы можете войти с новым паролем.</p>
          </div>
          <router-link to="/login" class="text-primary-600 hover:text-primary-700">
            Войти в систему
          </router-link>
        </div>
        
        <!-- Form -->
        <form v-else @submit.prevent="handleSubmit">
          <!-- Error message -->
          <div v-if="error" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
            {{ error }}
          </div>
          
          <!-- New Password -->
          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-700 mb-2">Новый пароль</label>
            <input
              v-model="newPassword"
              type="password"
              required
              class="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
              placeholder="Минимум 8 символов"
            />
          </div>
          
          <!-- Confirm Password -->
          <div class="mb-6">
            <label class="block text-sm font-medium text-slate-700 mb-2">Подтверждение пароля</label>
            <input
              v-model="confirmPassword"
              type="password"
              required
              class="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
              placeholder="Повторите пароль"
            />
          </div>
          
          <!-- Submit -->
          <button
            type="submit"
            :disabled="loading"
            class="w-full py-3 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span v-if="loading">Сохранение...</span>
            <span v-else>Сохранить пароль</span>
          </button>
        </form>
      </div>
    </div>
  </div>
</template>
