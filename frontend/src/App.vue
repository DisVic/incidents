<script setup>
import { useAuthStore } from '@/stores/auth'
import { onMounted } from 'vue'
import Modal from '@/components/Modal.vue'

const authStore = useAuthStore()

// При загрузке приложения проверяем валидность токена и загружаем данные пользователя
onMounted(async () => {
  // Если токен есть, но пользователь ещё не загружен — запрашиваем его данные
  if (authStore.token && !authStore.user) {
    try {
      await authStore.fetchUser()
    } catch {
      // Токен невалиден, роутер перенаправит на логин
    }
  }
})
</script>

<template>
  <!-- Основное окно роутера для отображения страниц -->
  <!-- Точка вывода маршрутов -->
<router-view />
  <!-- Глобальное модальное окно для уведомлений -->
  <Modal />
</template>
