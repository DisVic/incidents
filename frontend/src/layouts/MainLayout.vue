<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import axios from 'axios'

const router = useRouter()
const route = useRoute()
// Хранилище авторизации
const authStore = useAuthStore()

// Состояние бокового меню
const sidebarOpen = ref(true) // Состояние боковой панели (развернута/свернута)
const unreadCount = ref(0) // Количество непрочитанных уведомлений
let pollingInterval = null // Таймер опроса уведомлений

// Воспроизведение звука уведомления через Web Audio API
const playNotificationSound = () => {
  try {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)()
    const oscillator = audioContext.createOscillator()
    const gainNode = audioContext.createGain()
    
    oscillator.connect(gainNode)
    gainNode.connect(audioContext.destination)
    
    oscillator.frequency.value = 800 // Частота звука (Гц)
    oscillator.type = 'sine' // Тип волны
    
    // Плавное затухание звука
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime)
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5)
    
    oscillator.start(audioContext.currentTime)
    oscillator.stop(audioContext.currentTime + 0.5)
  } catch (e) {
    console.log('Could not play sound')
  }
}

// Загрузка количества непрочитанных уведомлений
const fetchUnreadCount = async () => {
  if (!authStore.user?.id) return
  
  try {
    const response = await axios.get('/api/notifications', {
      params: {
        user_id: authStore.user.id,
        unread_only: true
      }
    })
    const newCount = response.data.length
    
    // Звук при появлении новых уведомлений
    if (newCount > unreadCount.value && unreadCount.value >= 0) {
      playNotificationSound()
    }
    
    unreadCount.value = newCount
  } catch (err) {
    console.error('Failed to fetch notifications:', err)
  }
}

onMounted(() => {
  fetchUnreadCount()
  // Опрос каждые 5 секунд для обновления уведомлений
  pollingInterval = setInterval(fetchUnreadCount, 5000)
})

onUnmounted(() => {
  // Очищаем таймер при уничтожении компонента
  if (pollingInterval) {
    clearInterval(pollingInterval)
  }
})

// Формирование меню в зависимости от роли пользователя
const menuItems = computed(() => {
  const items = []
  
  // Дашборд — Manager и Admin
  if (authStore.isManager) {
    items.push({ name: 'Дашборд', path: '/', icon: 'dashboard' })
  }
  
  items.push({ name: 'Инциденты', path: '/incidents', icon: 'incident' })
  items.push({ name: 'Уведомления', path: '/notifications', icon: 'bell' })
  items.push({ name: 'Профиль', path: '/profile', icon: 'user' })
  
  // Пользователи и Настройки — только Admin
  if (authStore.isAdmin) {
    items.push({ name: 'Пользователи', path: '/users', icon: 'users' })
    items.push({ name: 'Настройки', path: '/settings', icon: 'settings' })
  }
  
  return items
})

// Выход из системы
const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen flex bg-gray-100">
    <!-- Боковая панель -->
    <aside 
      :class="[
        'fixed inset-y-0 left-0 z-50 bg-slate-800 text-white transition-all duration-300',
        sidebarOpen ? 'w-64' : 'w-16'
      ]"
    >
      <!-- Логотип -->
      <div class="h-16 flex items-center justify-between px-4 border-b border-slate-700">
        <span v-if="sidebarOpen" class="text-xl font-bold">IMS</span>
        <span v-else class="text-xl font-bold">I</span>
        <button 
          @click="sidebarOpen = !sidebarOpen"
          class="p-2 rounded-lg hover:bg-slate-700"
          title="Свернуть/развернуть меню"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      </div>
      
      <!-- Навигация -->
      <nav class="mt-4 px-2">
        <router-link
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center gap-3 px-4 py-3 rounded-lg text-slate-300 hover:bg-slate-700 hover:text-white transition-colors mb-1"
          exact-active-class="bg-primary-600 text-white"
        >
          <span class="w-5 h-5 flex items-center justify-center relative">
            <!-- Иконка колокольчика с бейджем -->
            <template v-if="item.icon === 'bell'">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              <!-- Бейдж с количеством непрочитанных -->
              <span 
                v-if="unreadCount > 0" 
                class="absolute -top-1 -right-1 min-w-[18px] h-[18px] bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center px-1"
              >
                {{ unreadCount > 99 ? '99+' : unreadCount }}
              </span>
            </template>
            <!-- Dashboard icon -->
            <svg v-else-if="item.icon === 'dashboard'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
            </svg>
            <!-- Incident icon -->
            <svg v-else-if="item.icon === 'incident'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <!-- User icon -->
            <svg v-else-if="item.icon === 'user'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <!-- Chart icon -->
            <svg v-else-if="item.icon === 'chart'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>

            <!-- Users icon -->
            <svg v-else-if="item.icon === 'users'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            <!-- Settings icon -->
            <svg v-else-if="item.icon === 'settings'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </span>
          <span v-if="sidebarOpen">{{ item.name }}</span>
        </router-link>
      </nav>
      
      <!-- Информация о пользователе -->
      <div class="absolute bottom-0 left-0 right-0 p-4 border-t border-slate-700">
        <div class="flex items-center gap-3">
          <!-- Аватар или инициалы -->
          <div class="w-10 h-10 rounded-full bg-primary-500 flex items-center justify-center font-bold overflow-hidden">
            <img 
              v-if="authStore.user?.avatar" 
              :src="authStore.user.avatar" 
              alt="Avatar" 
              class="w-full h-full object-cover">
            <span v-else>{{ authStore.user?.full_name?.charAt(0)?.toUpperCase() || 'U' }}</span>
          </div>
          <div v-if="sidebarOpen" class="flex-1 min-w-0">
            <p class="text-sm font-medium truncate">{{ authStore.user?.full_name }}</p>
            <p class="text-xs text-slate-400 truncate">{{ authStore.user?.role_name }}</p>
          </div>
          <button 
            v-if="sidebarOpen"
            @click="handleLogout"
            class="p-2 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-white"
            title="Выйти"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>
    </aside>
    
    <!-- Основной контент -->
    <main :class="['flex-1 transition-all duration-300', sidebarOpen ? 'ml-64' : 'ml-16']">
      <!-- Шапка -->
      <div class="sticky top-0 z-40 bg-white border-b border-slate-200 px-6 py-3">
        <div class="flex items-center justify-between">
          <h1 class="text-lg font-semibold text-slate-800">
            {{ menuItems.find(item => item.path === route.path)?.name || 'Система управления инцидентами' }}
          </h1>
        </div>
      </div>
      
      <!-- Область просмотра текущей страницы -->
      <div class="p-6">
        <router-view />
      </div>
    </main>
  </div>
</template>
