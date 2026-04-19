<script setup>
/**
 * Страница профиля пользователя.
 * 
 * Функции:
 * - Просмотр информации о пользователе
 * - Загрузка/удаление аватара
 * - Смена пароля
 * - Настройки уведомлений (Manager/Admin)
 */
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import Modal from '@/components/Modal.vue'

const authStore = useAuthStore()

const user = ref(null)
const loading = ref(true)
const saving = ref(false)
const message = ref({ type: '', text: '' })
const avatarUploading = ref(false)

// Notification settings
const notifSettings = ref({
  incident_created: { internal: true, email: false },
  assigned_executor: { internal: true, email: true },
  new_comment: { internal: true, email: false },
  status_changed: { internal: true, email: false },
  incident_resolved: { internal: true, email: true },
  overdue: { internal: true, email: true },
  escalation: { internal: true, email: true },
  priority_changed: { internal: true, email: false }
})

// Password change
const showPasswordModal = ref(false)
const passwordForm = ref({
  current_password: '',
  new_password: '',
  confirm_password: ''
})
const passwordError = ref('')
const passwordSaving = ref(false)

const settingLabels = {
  incident_created: 'Новый инцидент',
  assigned_executor: 'Назначение исполнителем',
  new_comment: 'Новый комментарий',
  status_changed: 'Изменение статуса',
  incident_resolved: 'Инцидент решён',
  overdue: 'Просрочка SLA',
  escalation: 'Эскалация',
  priority_changed: 'Изменение приоритета'
}

/**
 * Настройки уведомлений доступны только Manager/Admin.
 */
const canEditNotifications = computed(() => {
  return authStore.isAdmin || authStore.isManager
})

/**
 * Вычисляемые свойства для аватара.
 */
const avatarUrl = computed(() => {
  if (user.value?.avatar) {
    return user.value.avatar
  }
  return null
})

const userInitial = computed(() => {
  return user.value?.full_name?.charAt(0)?.toUpperCase() || 'U'
})

/**
 * Загрузка данных профиля и настроек уведомлений.
 */
onMounted(async () => {
  try {
    const userRes = await axios.get('/api/auth/me')
    user.value = userRes.data
    
    // Load notification settings only for Manager/Admin
    if (canEditNotifications.value) {
      const settingsRes = await axios.get(`/api/notifications/settings/${authStore.user?.id}`)
      if (settingsRes.data) {
        notifSettings.value = {
          incident_created: settingsRes.data.incident_created || { internal: true, email: false },
          assigned_executor: settingsRes.data.assigned_executor || { internal: true, email: true },
          new_comment: settingsRes.data.new_comment || { internal: true, email: false },
          status_changed: settingsRes.data.status_changed || { internal: true, email: false },
          incident_resolved: settingsRes.data.incident_resolved || { internal: true, email: true },
          overdue: settingsRes.data.overdue || { internal: true, email: true },
          escalation: settingsRes.data.escalation || { internal: true, email: true },
          priority_changed: settingsRes.data.priority_changed || { internal: true, email: false }
        }
      }
    }
  } catch (err) {
    console.error('Failed to load data:', err)
  } finally {
    loading.value = false
  }
})

/**
 * Сохранение настроек уведомлений.
 */
async function saveSettings() {
  saving.value = true
  message.value = { type: '', text: '' }
  
  try {
    await axios.put(`/api/notifications/settings/${authStore.user?.id}`, notifSettings.value)
    message.value = { type: 'success', text: 'Настройки сохранены' }
    setTimeout(() => { message.value = { type: '', text: '' } }, 3000)
  } catch (err) {
    message.value = { type: 'error', text: 'Ошибка при сохранении настроек' }
  } finally {
    saving.value = false
  }
}

/**
 * Открытие модального окна смены пароля.
 */
function openPasswordModal() {
  passwordForm.value = {
    current_password: '',
    new_password: '',
    confirm_password: ''
  }
  passwordError.value = ''
  showPasswordModal.value = true
}

/**
 * Смена пароля с валидацией.
 */
async function changePassword() {
  passwordError.value = ''
  
  if (!passwordForm.value.current_password || !passwordForm.value.new_password) {
    passwordError.value = 'Заполните все поля'
    return
  }
  
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
    passwordError.value = 'Пароли не совпадают'
    return
  }
  
  if (passwordForm.value.new_password.length < 8) {
    passwordError.value = 'Пароль должен быть не менее 8 символов'
    return
  }
  
  passwordSaving.value = true
  
  try {
    await axios.put('/api/auth/password', {
      current_password: passwordForm.value.current_password,
      new_password: passwordForm.value.new_password
    })
    showPasswordModal.value = false
    message.value = { type: 'success', text: 'Пароль изменён. Выполняется выход из системы...' }
    
    // Logout after password change - user needs to login again
    setTimeout(() => {
      authStore.logout()
    }, 2000)
  } catch (err) {
    passwordError.value = err.response?.data?.detail || 'Ошибка при смене пароля'
  } finally {
    passwordSaving.value = false
  }
}

/**
 * Загрузка аватара (валидация типа и размера).
 */
function triggerAvatarUpload() {
  document.getElementById('avatar-input')?.click()
}

async function uploadAvatar(event) {
  const file = event.target.files?.[0]
  if (!file) return
  
  // Validate file type
  if (!file.type.startsWith('image/')) {
    message.value = { type: 'error', text: 'Можно загрузить только изображение' }
    return
  }
  
  // Validate file size (max 500KB)
  if (file.size > 500 * 1024) {
    message.value = { type: 'error', text: 'Изображение должно быть меньше 500KB' }
    return
  }
  
  avatarUploading.value = true
  
  try {
    // Convert to base64
    const reader = new FileReader()
    reader.onload = async (e) => {
      try {
        const base64 = e.target?.result
        
        await axios.post(`/api/users/${authStore.user?.id}/avatar`, {
          avatar: base64
        })
        
        // Update local user data
        user.value.avatar = base64
        
        // Update auth store
        if (authStore.user) {
          authStore.user.avatar = base64
        }
        
        message.value = { type: 'success', text: 'Аватар обновлён' }
        setTimeout(() => { message.value = { type: '', text: '' } }, 3000)
      } catch (err) {
        message.value = { type: 'error', text: err.response?.data?.detail || 'Ошибка при загрузке аватара' }
      } finally {
        avatarUploading.value = false
      }
    }
    reader.readAsDataURL(file)
  } catch (err) {
    message.value = { type: 'error', text: 'Ошибка при чтении файла' }
    avatarUploading.value = false
  }
  
  // Clear input
  event.target.value = ''
}

/**
 * Удаление аватара.
 */
async function removeAvatar() {
  try {
    await axios.post(`/api/users/${authStore.user?.id}/avatar`, {
      avatar: ""  // Empty string to remove
    })
    
    user.value.avatar = null
    if (authStore.user) {
      authStore.user.avatar = null
    }
    
    message.value = { type: 'success', text: 'Аватар удалён' }
    setTimeout(() => { message.value = { type: '', text: '' } }, 3000)
  } catch (err) {
    message.value = { type: 'error', text: 'Ошибка при удалении аватара' }
  }
}
</script>

<template>
  <div class="max-w-3xl mx-auto space-y-6">
    <h1 class="text-2xl font-bold text-slate-800">Профиль</h1>
    
    <!-- Сообщение (успех/ошибка) -->
    <div v-if="message.text" 
         :class="[
           'p-4 rounded-lg',
           message.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'
         ]">
      {{ message.text }}
    </div>
    
    <!-- Загрузка -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
    </div>
    
    <template v-else-if="user">
      <!-- Карточка пользователя -->
      <div class="bg-white rounded-xl shadow-sm p-6 border border-slate-200">
        <div class="flex items-center justify-between mb-6">
          <div class="flex items-center gap-4">
            <!-- Аватар с загрузкой -->
            <div class="relative group">
              <div 
                @click="triggerAvatarUpload"
                class="w-16 h-16 rounded-full bg-primary-500 flex items-center justify-center text-white text-2xl font-bold cursor-pointer overflow-hidden hover:ring-4 hover:ring-primary-200 transition-all">
                <img v-if="avatarUrl" :src="avatarUrl" alt="Avatar" class="w-full h-full object-cover">
                <span v-else>{{ userInitial }}</span>
              </div>
              <!-- Оверлей при наведении -->
              <div 
                class="absolute inset-0 rounded-full bg-black/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                @click="triggerAvatarUpload">
                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
              <input 
                type="file" 
                id="avatar-input" 
                accept="image/*" 
                class="hidden" 
                @change="uploadAvatar">
              <!-- Индикатор загрузки -->
              <div 
                v-if="avatarUploading"
                class="absolute inset-0 rounded-full bg-black/50 flex items-center justify-center">
                <div class="animate-spin rounded-full h-6 w-6 border-2 border-white border-t-transparent"></div>
              </div>
            </div>
            <div>
              <h2 class="text-xl font-semibold text-slate-800">{{ user.full_name }}</h2>
              <p class="text-slate-500">{{ authStore.user?.role_name }}</p>
              <button 
                v-if="user.avatar"
                @click="removeAvatar"
                class="text-xs text-red-500 hover:text-red-700 mt-1">
                Удалить аватар
              </button>
            </div>
          </div>
          <!-- Кнопка смены пароля -->
          <button @click="openPasswordModal" 
                  class="px-4 py-2 text-sm font-medium text-primary-600 hover:text-primary-700 hover:bg-primary-50 rounded-lg transition-colors">
            Сменить пароль
          </button>
        </div>
        
        <!-- Информация о пользователе -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="flex items-center gap-3 text-slate-600">
            <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            <span>{{ user.email }}</span>
          </div>
          
          <div v-if="user.phone" class="flex items-center gap-3 text-slate-600">
            <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
            </svg>
            <span>{{ user.phone }}</span>
          </div>
          
          <div v-if="user.department_name" class="flex items-center gap-3 text-slate-600">
            <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
            <span>{{ user.department_name }}</span>
          </div>
        </div>
      </div>
      
      <!-- Настройки уведомлений (только Manager/Admin) -->
      <div v-if="canEditNotifications" class="bg-white rounded-xl shadow-sm p-6 border border-slate-200">
        <h3 class="text-lg font-semibold text-slate-800 mb-4">Настройки уведомлений</h3>
        
        <!-- Таблица настроек -->
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="border-b border-slate-200">
                <th class="text-left py-3 px-4 text-sm font-medium text-slate-600">Событие</th>
                <th class="text-center py-3 px-4 text-sm font-medium text-slate-600">
                  <div class="flex items-center justify-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                    </svg>
                    В системе
                  </div>
                </th>
                <th class="text-center py-3 px-4 text-sm font-medium text-slate-600">
                  <div class="flex items-center justify-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    Email
                  </div>
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-for="(setting, key) in notifSettings" :key="key" class="hover:bg-slate-50">
                <td class="py-3 px-4 text-sm text-slate-700">{{ settingLabels[key] }}</td>
                <td class="py-3 px-4 text-center">
                  <input type="checkbox" v-model="setting.internal" 
                         class="w-4 h-4 text-primary-600 border-slate-300 rounded focus:ring-primary-500">
                </td>
                <td class="py-3 px-4 text-center">
                  <input type="checkbox" v-model="setting.email" 
                         class="w-4 h-4 text-primary-600 border-slate-300 rounded focus:ring-primary-500">
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        
        <div class="mt-4 flex justify-end">
          <button @click="saveSettings" 
                  :disabled="saving"
                  class="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
            <span v-if="saving">Сохранение...</span>
            <span v-else>Сохранить настройки</span>
          </button>
        </div>
      </div>
    </template>
    
    <!-- Модальное окно смены пароля -->
    <Modal v-if="showPasswordModal" @close="showPasswordModal = false">
      <template #title>Смена пароля</template>
      
      <form @submit.prevent="changePassword" class="space-y-4">
        <div v-if="passwordError" class="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
          {{ passwordError }}
        </div>
        
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">Текущий пароль</label>
          <input type="password" v-model="passwordForm.current_password"
                 class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500">
        </div>
        
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">Новый пароль</label>
          <input type="password" v-model="passwordForm.new_password"
                 class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500">
        </div>
        
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">Подтверждение пароля</label>
          <input type="password" v-model="passwordForm.confirm_password"
                 class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500">
        </div>
        
        <div class="flex justify-end gap-3 pt-4">
          <button type="button" @click="showPasswordModal = false"
                  class="px-4 py-2 text-slate-700 hover:bg-slate-100 rounded-lg transition-colors">
            Отмена
          </button>
          <button type="submit" :disabled="passwordSaving"
                  class="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors">
            <span v-if="passwordSaving">Сохранение...</span>
            <span v-else>Сменить пароль</span>
          </button>
        </div>
      </form>
    </Modal>
  </div>
</template>