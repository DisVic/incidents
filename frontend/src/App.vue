<script setup>
import { useAuthStore } from '@/stores/auth'
import { onMounted } from 'vue'
import Modal from '@/components/Modal.vue'

const authStore = useAuthStore()

onMounted(async () => {
  if (authStore.token && !authStore.user) {
    try {
      await authStore.fetchUser()
    } catch {
      // Token invalid, will redirect to login
    }
  }
})
</script>

<template>
  <router-view />
  <Modal />
</template>