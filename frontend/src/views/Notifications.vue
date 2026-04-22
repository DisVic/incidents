<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import axios from 'axios'

const router = useRouter()
const authStore = useAuthStore()
const notifications = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const response = await axios.get('/api/notifications', {
      params: { user_id: authStore.user?.id }
    })
    notifications.value = response.data
  } catch (err) {
    console.error('Failed to load notifications:', err)
  } finally {
    loading.value = false
  }
})

const markAsRead = async (id) => {
  try {
    await axios.post(`/api/notifications/${id}/read`)
    const notif = notifications.value.find(n => n.id === id)
    if (notif) notif.is_read = true
  } catch (err) {
    console.error('Failed to mark as read:', err)
  }
}

const handleNotificationClick = async (notif) => {
  // Mark as read
  if (!notif.is_read) {
    await markAsRead(notif.id)
  }
  
  // Navigate to incident if incident_id exists
  if (notif.incident_id) {
    router.push(`/incidents/${notif.incident_id}`)
  }
}

const markAllAsRead = async () => {
  try {
    await axios.post(`/api/notifications/read-all?user_id=${authStore.user?.id}`)
    notifications.value.forEach(n => n.is_read = true)
  } catch (err) {
    console.error('Failed to mark all as read:', err)
  }
}

const formatDate = (date) => {
  return new Date(date).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-slate-800">Уведомления</h1>
      <button
        v-if="notifications.some(n => !n.is_read)"
        @click="markAllAsRead"
        class="px-4 py-2 text-sm bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors"
      >
        Прочитать все
      </button>
    </div>
    
    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
    </div>
    
    <div v-else class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div v-if="!notifications.length" class="py-12 text-center text-slate-500">
        Нет уведомлений
      </div>
      
      <div v-else class="divide-y divide-slate-200">
        <div
          v-for="notif in notifications"
          :key="notif.id"
          @click="handleNotificationClick(notif)"
          :class="['p-4 hover:bg-slate-50 cursor-pointer transition-colors', !notif.is_read && 'bg-blue-50']"
        >
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <div class="flex items-center gap-2">
                <h3 class="font-medium text-slate-800">{{ notif.title }}</h3>
                <span v-if="notif.incident_id" class="text-xs text-primary-600 bg-primary-50 px-2 py-0.5 rounded">
                  Инцидент
                </span>
              </div>
              <p v-if="notif.message" class="text-sm text-slate-600 mt-1">{{ notif.message }}</p>
              <p class="text-xs text-slate-400 mt-2">{{ formatDate(notif.created_at) }}</p>
            </div>
            <div class="flex items-center gap-2 ml-4">
              <span v-if="!notif.is_read" class="w-2 h-2 bg-primary-500 rounded-full"></span>
              <svg v-if="notif.incident_id" class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>