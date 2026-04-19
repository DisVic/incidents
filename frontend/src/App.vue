<script setup>
/**
 * Корневой компонент приложения.
 * 
 * - Рендерит router-view (текущий маршрут)
 * - Подключает глобальный Modal компонент
 * - Проверяет токен при монтировании
 */
import { useAuthStore } from '@/stores/auth'
import { onMounted } from 'vue'
import Modal from '@/components/Modal.vue'

const authStore = useAuthStore()

// При монтировании проверяем валидность токена
onMounted(async () => {
  if (authStore.token && !authStore.user) {
    try {
      await authStore.fetchUser()
    } catch {
      // Токен невалиден — редирект на login (через router guard)
    }
  }
})
</script>

<template>
  <!-- Router-view рендерит компонент текущего маршрута -->
  <router-view />
  <!-- Глобальное модальное окно (alert/confirm/prompt) -->
  <Modal />
</template>
