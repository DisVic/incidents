<script setup>
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useModal } from '@/composables/useModal'

const router = useRouter()
const authStore = useAuthStore()
const { alert, confirm } = useModal()

const users = ref([])
const roles = ref([])
const departments = ref([])
const loading = ref(true)
const showModal = ref(false)
const modalMode = ref('create')
const editingUserId = ref(null)

const form = ref({
  email: '',
  full_name: '',
  role_id: '',
  department_id: '',
  password: ''
})

const formErrors = ref({})
const saving = ref(false)

// Фильтры и сортировка
const departmentFilter = ref('')
const roleFilter = ref('')
const sortField = ref('full_name') // full_name, created_at
const sortOrder = ref('asc') // asc, desc

const filteredUsers = computed(() => {
  let result = [...users.value]
  
  // Фильтр по отделу
  if (departmentFilter.value) {
    result = result.filter(u => u.department_id === departmentFilter.value)
  }
  
  // Фильтр по роли
  if (roleFilter.value) {
    result = result.filter(u => u.role_id === roleFilter.value)
  }
  
  // Сортировка
  result.sort((a, b) => {
    let aVal, bVal
    
    if (sortField.value === 'full_name') {
      aVal = (a.full_name || '').toLowerCase()
      bVal = (b.full_name || '').toLowerCase()
    } else if (sortField.value === 'created_at') {
      aVal = new Date(a.created_at || 0).getTime()
      bVal = new Date(b.created_at || 0).getTime()
    }
    
    if (sortOrder.value === 'asc') {
      return aVal < bVal ? -1 : aVal > bVal ? 1 : 0
    } else {
      return aVal > bVal ? -1 : aVal < bVal ? 1 : 0
    }
  })
  
  return result
})

function clearFilters() {
  departmentFilter.value = ''
  roleFilter.value = ''
  sortField.value = 'full_name'
  sortOrder.value = 'asc'
}

const modalTitle = computed(() => modalMode.value === 'create' ? 'Новый пользователь' : 'Редактировать пользователя')

onMounted(async () => {
  await Promise.all([
    loadUsers(),
    loadRoles(),
    loadDepartments()
  ])
  loading.value = false
})

async function loadUsers() {
  try {
    const res = await axios.get('/api/users')
    users.value = res.data.data || res.data || []
  } catch (err) {
    console.error('Failed to load users:', err)
  }
}

async function loadRoles() {
  try {
    const res = await axios.get('/api/roles')
    roles.value = res.data.data || res.data || []
  } catch (err) {
    console.error('Failed to load roles:', err)
  }
}

async function loadDepartments() {
  try {
    const res = await axios.get('/api/departments')
    departments.value = res.data.data || res.data || []
  } catch (err) {
    console.error('Failed to load departments:', err)
  }
}

function openCreateModal() {
  modalMode.value = 'create'
  editingUserId.value = null
  form.value = {
    email: '',
    full_name: '',
    role_id: '',
    department_id: '',
    password: ''
  }
  formErrors.value = {}
  showModal.value = true
}

function openEditModal(user) {
  modalMode.value = 'edit'
  editingUserId.value = user.id
  form.value = {
    email: user.email,
    full_name: user.full_name,
    role_id: user.role_id,
    department_id: user.department_id || '',
    password: ''
  }
  formErrors.value = {}
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  formErrors.value = {}
}

async function saveUser() {
  formErrors.value = {}
  
  if (!form.value.email) {
    formErrors.value.email = 'Email обязателен'
  }
  if (!form.value.full_name) {
    formErrors.value.full_name = 'ФИО обязательно'
  }
  if (!form.value.role_id) {
    formErrors.value.role_id = 'Роль обязательна'
  }
  if (modalMode.value === 'create' && !form.value.password) {
    formErrors.value.password = 'Пароль обязателен'
  }
  
  if (Object.keys(formErrors.value).length > 0) {
    return
  }
  
  saving.value = true
  try {
    const payload = {
      email: form.value.email,
      full_name: form.value.full_name,
      role_id: form.value.role_id,
      department_id: form.value.department_id || null
    }
    
    if (modalMode.value === 'create') {
      payload.password = form.value.password
      await axios.post('/api/users', payload)
    } else {
      await axios.put(`/api/users/${editingUserId.value}`, payload)
    }
    
    await loadUsers()
    closeModal()
  } catch (err) {
    const detail = err.response?.data?.detail
    
    if (Array.isArray(detail) && detail[0]?.field) {
      detail.forEach(e => {
        formErrors.value[e.field] = e.message
      })
    } else if (Array.isArray(detail)) {
      const messages = detail.map(e => {
        const field = e.loc?.[e.loc.length - 1]
        return `${field}: ${e.msg}`
      })
      await alert(messages.join('\n'))
    } else if (typeof detail === 'string') {
      await alert(detail)
    } else {
      await alert('Ошибка сохранения')
    }
  } finally {
    saving.value = false
  }
}

async function toggleActive(user) {
  const action = user.is_active ? 'заблокировать' : 'активировать'
  const confirmed = await confirm(`Вы уверены, что хотите ${action} пользователя "${user.full_name}"?`)
  
  if (!confirmed) return
  
  try {
    await axios.patch(`/api/users/${user.id}/active`, { is_active: !user.is_active })
    await loadUsers()
  } catch (err) {
    const detail = err.response?.data?.detail
    await alert(typeof detail === 'string' ? detail : 'Ошибка')
  }
}

async function confirmDelete(user) {
  const confirmed = await confirm(
    `Вы уверены, что хотите УДАЛИТЬ пользователя "${user.full_name}"?\n\nЭто действие нельзя отменить.`,
    'Удаление пользователя'
  )
  
  if (!confirmed) return
  
  try {
    await axios.delete(`/api/users/${user.id}`)
    await loadUsers()
  } catch (err) {
    const detail = err.response?.data?.detail
    await alert(typeof detail === 'string' ? detail : 'Ошибка удаления')
  }
}

function getRoleColor(role) {
  const colors = {
    'Admin': 'bg-red-100 text-red-700',
    'Manager': 'bg-purple-100 text-purple-700',
    'Executor': 'bg-blue-100 text-blue-700',
    'User': 'bg-gray-100 text-gray-700'
  }
  return colors[role] || 'bg-gray-100 text-gray-700'
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  })
}

function goToUserStats(user) {
  if (['Executor', 'Manager', 'Admin'].includes(user.role_name)) {
    router.push(`/users/${user.id}/stats`)
  }
}
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-slate-800">Пользователи</h1>
      <button
        @click="openCreateModal"
        class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        Добавить пользователя
      </button>
    </div>
    
    <!-- Filters -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-4">
      <div class="flex flex-wrap items-center gap-4">
        <!-- Department filter -->
        <div class="flex items-center gap-2">
          <label class="text-sm text-slate-600">Отдел:</label>
          <select
            v-model="departmentFilter"
            class="px-3 py-1.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">Все отделы</option>
            <option v-for="dept in departments" :key="dept.id" :value="dept.id">{{ dept.name }}</option>
          </select>
        </div>
        
        <!-- Role filter -->
        <div class="flex items-center gap-2">
          <label class="text-sm text-slate-600">Роль:</label>
          <select
            v-model="roleFilter"
            class="px-3 py-1.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">Все роли</option>
            <option v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }}</option>
          </select>
        </div>
        
        <!-- Sort field -->
        <div class="flex items-center gap-2">
          <label class="text-sm text-slate-600">Сортировка:</label>
          <select
            v-model="sortField"
            class="px-3 py-1.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="full_name">По имени</option>
            <option value="created_at">По дате создания</option>
          </select>
          <button
            @click="sortOrder = sortOrder === 'asc' ? 'desc' : 'asc'"
            class="px-2 py-1.5 border border-slate-300 rounded-lg text-sm hover:bg-slate-50 transition-colors flex items-center gap-1"
            :title="sortOrder === 'asc' ? 'По возрастанию' : 'По убыванию'"
          >
            <svg v-if="sortOrder === 'asc'" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
            </svg>
            <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h9m5-4v12m0 0l-4-4m4 4l4-4" />
            </svg>
            {{ sortOrder === 'asc' ? 'А-Я' : 'Я-А' }}
          </button>
        </div>
        
        <!-- Clear filters -->
        <button
          v-if="departmentFilter || roleFilter || sortField !== 'full_name' || sortOrder !== 'asc'"
          @click="clearFilters"
          class="px-3 py-1.5 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
        >
          Сбросить
        </button>
        
        <!-- Count -->
        <div class="ml-auto text-sm text-slate-500">
          Найдено: {{ filteredUsers.length }} из {{ users.length }}
        </div>
      </div>
    </div>
    
    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
    </div>
    
    <!-- Users table -->
    <div v-else-if="filteredUsers.length > 0" class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <table class="w-full">
        <thead class="bg-slate-50 border-b border-slate-200">
          <tr>
            <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Пользователь</th>
            <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Email</th>
            <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Роль</th>
            <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Отдел</th>
            <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Статус</th>
            <th class="px-4 py-3 text-right text-sm font-medium text-slate-600">Действия</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-200">
          <tr 
            v-for="user in filteredUsers" 
            :key="user.id" 
            class="hover:bg-slate-50"
            :class="{ 'cursor-pointer': ['Executor', 'Manager', 'Admin'].includes(user.role_name) }"
            @click="goToUserStats(user)"
          >
            <td class="px-4 py-3">
              <div class="flex items-center gap-3">
                <div
                  v-if="user.avatar"
                  class="w-8 h-8 rounded-full bg-cover bg-center"
                  :style="{ backgroundImage: `url(${user.avatar})` }"
                ></div>
                <div
                  v-else
                  class="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-bold"
                >
                  {{ user.full_name?.charAt(0) || 'U' }}
                </div>
                <div>
                  <span class="font-medium text-slate-800">{{ user.full_name }}</span>
                  <div class="text-xs text-slate-400">{{ formatDate(user.created_at) }}</div>
                </div>
              </div>
            </td>
            <td class="px-4 py-3 text-slate-600">{{ user.email }}</td>
            <td class="px-4 py-3">
              <span :class="['px-2 py-1 rounded text-xs font-medium', getRoleColor(user.role_name)]">
                {{ user.role_name }}
              </span>
            </td>
            <td class="px-4 py-3 text-slate-600">{{ user.department_name || '—' }}</td>
            <td class="px-4 py-3">
              <span :class="['px-2 py-1 rounded text-xs font-medium', user.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700']">
                {{ user.is_active ? 'Активен' : 'Заблокирован' }}
              </span>
            </td>
            <td class="px-4 py-3" @click.stop>
              <div class="flex items-center justify-end gap-2">
                <button
                  @click="openEditModal(user)"
                  class="p-2 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                  title="Редактировать"
                >
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
                <button
                  v-if="authStore.isAdmin"
                  @click="toggleActive(user)"
                  class="p-2 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                  :title="user.is_active ? 'Заблокировать' : 'Активировать'"
                >
                  <svg v-if="user.is_active" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                  <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z" />
                  </svg>
                </button>
                <button
                  v-if="authStore.isAdmin"
                  @click="confirmDelete(user)"
                  class="p-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  title="Удалить"
                >
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="text-center text-slate-500 py-12">
      Нет пользователей
    </div>
    
    <!-- Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" @click.self="closeModal">
      <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div class="p-6 border-b border-slate-200">
          <h2 class="text-xl font-semibold text-slate-800">{{ modalTitle }}</h2>
        </div>
        
        <form @submit.prevent="saveUser" class="p-6 space-y-4">
          <!-- Email -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Email *</label>
            <input
              v-model="form.email"
              type="email"
              class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              :class="formErrors.email ? 'border-red-500' : 'border-slate-300'"
            />
            <p v-if="formErrors.email" class="text-red-500 text-sm mt-1">{{ formErrors.email }}</p>
          </div>
          
          <!-- Full Name -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">ФИО *</label>
            <input
              v-model="form.full_name"
              type="text"
              class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              :class="formErrors.full_name ? 'border-red-500' : 'border-slate-300'"
            />
            <p v-if="formErrors.full_name" class="text-red-500 text-sm mt-1">{{ formErrors.full_name }}</p>
          </div>
          
          <!-- Role -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Роль *</label>
            <select
              v-model="form.role_id"
              class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              :class="formErrors.role_id ? 'border-red-500' : 'border-slate-300'"
            >
              <option value="">Выберите роль</option>
              <option v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }}</option>
            </select>
            <p v-if="formErrors.role_id" class="text-red-500 text-sm mt-1">{{ formErrors.role_id }}</p>
          </div>
          
          <!-- Department -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Отдел</label>
            <select
              v-model="form.department_id"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Без отдела</option>
              <option v-for="dept in departments" :key="dept.id" :value="dept.id">{{ dept.name }}</option>
            </select>
          </div>
          
          <!-- Password (create only) -->
          <div v-if="modalMode === 'create'">
            <label class="block text-sm font-medium text-slate-700 mb-1">Пароль *</label>
            <input
              v-model="form.password"
              type="password"
              class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              :class="formErrors.password ? 'border-red-500' : 'border-slate-300'"
            />
            <p v-if="formErrors.password" class="text-red-500 text-sm mt-1">{{ formErrors.password }}</p>
          </div>
          
          <!-- Actions -->
          <div class="flex justify-end gap-3 pt-4">
            <button
              type="button"
              @click="closeModal"
              class="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
            >
              Отмена
            </button>
            <button
              type="submit"
              :disabled="saving"
              class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {{ saving ? 'Сохранение...' : 'Сохранить' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>