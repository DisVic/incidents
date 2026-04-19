/**
 * Точка входа приложения IMS.
 * 
 * Инициализация:
 * 1. Создаётся Pinia store
 * 2. Подключается Vue Router
 * 3. Инициализируется auth store (проверка токена)
 * 4. Монтируется приложение после загрузки auth
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import './assets/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// Инициализируем auth store перед монтированием (проверка токена)
const authStore = useAuthStore()
authStore.init().finally(() => {
  app.mount('#app')
})
