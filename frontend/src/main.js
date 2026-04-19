import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import './assets/main.css'

// Создание экземпляра приложения Vue
const app = createApp(App)
const pinia = createPinia()

app.use(pinia) // Подключаем хранилище состояний Pinia
// Подключение роутера
app.use(router) // Подключаем роутер

// Инициализируем авторизацию до монтирования приложения, чтобы проверить токен
const authStore = useAuthStore()
authStore.init().finally(() => {
  // Монтирование приложения в DOM
app.mount('#app')
})
