<script setup>
/**
 * Список инцидентов с фильтрацией, сортировкой и пагинацией.
 * 
 * Функции:
 * - Фильтры: статус, приоритет, отдел (Admin), SLA-статус
 * - Сортировка: по дате, дедлайну, приоритету, заголовку
 * - Поиск по заголовку
 * - Удаление инцидентов (с проверкой прав)
 * 
 * Права доступа:
 * - Admin: видит все, фильтрует по отделу
 * - Manager: видит инциденты своего отдела
 * - Executor: видит инциденты своего отдела
 * - User: видит свои инциденты
 */
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const incidents = ref([])
const loading = ref(true)
const total = ref(0)
const page = ref(1)
const limit = ref(20)
const search = ref('')

// Сортировка
const sortField = ref('created_at')
const sortOrder = ref('desc') // 'asc' или 'desc'

const sortableFields = [
  { value: 'created_at', label: 'Дате создания' },
  { value: 'sla_deadline', label: 'Дедлайну SLA' },
  { value: 'priority', label: 'Приоритету' },
  { value: 'title', label: 'Заголовку' }
]

// Фильтры
const filters = ref({
  status_id: null,
  priority_id: null,
  department_id: null,
  overdue: null
})

// Справочники
const statuses = ref([])
const priorities = ref([])
const departments = ref([])

const pages = computed(() => Math.ceil(total.value / limit.value))

// Admin может фильтровать по отделу, остальные — нет
const canFilterByDepartment = computed(() => {
  return authStore.isAdmin
})

/**
 * Загрузка данных: инциденты + справочники.
 * Учитывает права доступа (отдел для non-Admin).
 */
const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: page.value,
      limit: limit.value,
      search: search.value || undefined,
      sort_field: sortField.value,
      sort_order: sortOrder.value,
      ...Object.fromEntries(
        Object.entries(filters.value).filter(([_, v]) => v !== null && v !== '')
      )
    }
    
    // Executor и Manager видят только инциденты своего отдела (Admin видит все)
    if (authStore.user?.department_id && !authStore.isAdmin) {
      params.user_department_id = authStore.user.department_id
    }
    
    // Add sla_status filter
    if (slaStatus.value) {
      params.sla_status = slaStatus.value
    }
    
    const [incidentsRes, statusesRes, prioritiesRes, departmentsRes] = await Promise.all([
      axios.get('/api/incidents', { params }),
      axios.get('/api/statuses'),
      axios.get('/api/priorities'),
      axios.get('/api/departments', { params: { limit: 100 } })
    ])
    
    incidents.value = incidentsRes.data.data
    total.value = incidentsRes.data.total
    
    if (!statuses.value.length) {
      statuses.value = statusesRes.data
      priorities.value = prioritiesRes.data
      departments.value = departmentsRes.data.data
    }
  } catch (error) {
    console.error('Failed to load incidents:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  // Handle query parameters for quick actions
  if (route.query.sla === 'overdue') {
    slaStatus.value = 'overdue'
  } else if (route.query.sla === 'near') {
    slaStatus.value = 'near'
  }
  
  loadData()
})

/**
 * Применение фильтров (сброс на страницу 1).
 */
const applyFilters = () => {
  page.value = 1
  loadData()
}

/**
 * Сброс всех фильтров и сортировки.
 */
const clearFilters = () => {
  filters.value = {
    status_id: null,
    priority_id: null,
    department_id: null,
    overdue: null
  }
  slaStatus.value = null
  search.value = ''
  sortField.value = 'created_at'
  sortOrder.value = 'desc'
  page.value = 1
  loadData()
}

/**
 * Изменение сортировки (toggle asc/desc).
 * @param {string} field - Поле для сортировки
 */
const toggleSort = (field) => {
  if (sortField.value === field) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortOrder.value = 'desc'
  }
  page.value = 1
  loadData()
}

/**
 * Иконка сортировки для заголовка столбца.
 * @param {string} field - Поле для проверки
 * @returns {string} ↕, ↑ или ↓
 */
const getSortIcon = (field) => {
  if (sortField.value !== field) return '↕'
  return sortOrder.value === 'asc' ? '↑' : '↓'
}

/**
 * Форматирование даты (DD.MM.YYYY HH:MM).
 * @param {string|Date} date
 * @returns {string}
 */
const formatDate = (date) => {
  return new Date(date).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// SLA status filter options
const slaStatusOptions = [
  { value: null, label: 'Все по SLA' },
  { value: 'overdue', label: 'Просроченные' },
  { value: 'near', label: 'Близко к дедлайну' },
  { value: 'ok', label: 'В срок' }
]
const slaStatus = ref(null)

/**
 * Применение фильтра по SLA-статусу.
 */
const applySlaFilter = () => {
  applyFilters()
}

// Опции размера страницы
const pageSizeOptions = [20, 50, 100]

/**
 * Изменение размера страницы (сброс на страницу 1).
 */
const changePageSize = () => {
  page.value = 1
  loadData()
}

// Delete incident functionality
const showDeleteModal = ref(false)
const incidentToDelete = ref(null)
const deleteLoading = ref(false)

/**
 * Проверка прав на удаление инцидента.
 * 
 * Правила:
 * - Admin: может удалить любой
 * - Manager: только инциденты своего отдела
 * - User: только свои и только в статусе "Новый"
 * - Executor: не может удалять
 * 
 * @param {Object} incident - Данные инцидента
 * @returns {boolean}
 */
const canDeleteIncident = (incident) => {

const canDeleteIncident = (incident) => {
  // Admin: любой инцидент
  if (authStore.isAdmin) return true
  
  // Manager: инциденты своего отдела
  if (authStore.isManager) {
    return authStore.user?.department_id === incident.department_id
  }
  
  // User: только свои и статус "Новый"
  if (authStore.user?.role_name === 'User') {
    return incident.initiator_id === authStore.user?.id && incident.status_name === 'Новый'
  }
  
  // Executor: нельзя
  return false
}

/**
 * Подтверждение удаления (открытие модального окна).
 * @param {Object} incident
 * @param {Event} event
 */
const confirmDelete = (incident, event) => {
  event.stopPropagation()
  incidentToDelete.value = incident
  showDeleteModal.value = true
}

/**
 * Удаление инцидента через API.
 */
const deleteIncident = async () => {
  if (!incidentToDelete.value) return
  
  deleteLoading.value = true
  try {
    await axios.delete(`/api/incidents/${incidentToDelete.value.id}`, {
      params: {
        user_id: authStore.user?.id,
        user_role: authStore.user?.role_name,
        user_department_id: authStore.user?.department_id
      }
    })
    showDeleteModal.value = false
    incidentToDelete.value = null
    loadData()
  } catch (error) {
    console.error('Failed to delete incident:', error)
    alert(error.response?.data?.detail || 'Ошибка при удалении инцидента')
  } finally {
    deleteLoading.value = false
  }
}
</script>

<template>
  <div>
    <!-- Заголовок + кнопка создания -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-slate-800">Инциденты</h1>
      <router-link
        to="/incidents/create"
        class="px-4 py-2 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors"
      >
        + Создать
      </router-link>
    </div>
    
    <!-- Фильтры -->
    <div class="bg-white rounded-xl shadow-sm p-4 mb-6 border border-slate-200">
      <!-- Строка 1: Основные фильтры -->
      <div class="grid grid-cols-1 md:grid-cols-6 gap-4 mb-4">
        <!-- Поиск -->
        <div class="md:col-span-2">
          <input
            v-model="search"
            type="text"
            placeholder="Поиск по заголовку..."
            class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            @keyup.enter="applyFilters"
          />
        </div>
        
        <!-- Статус -->
        <select
          v-model="filters.status_id"
          class="px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          @change="applyFilters"
        >
          <option :value="null">Все статусы</option>
          <option v-for="s in statuses" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        
        <!-- Приоритет -->
        <select
          v-model="filters.priority_id"
          class="px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          @change="applyFilters"
        >
          <option :value="null">Все приоритеты</option>
          <option v-for="p in priorities" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        
        <!-- Отдел (только Admin) -->
        <select
          v-if="canFilterByDepartment"
          v-model="filters.department_id"
          class="px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          @change="applyFilters"
        >
          <option :value="null">Все отделы</option>
          <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
        </select>
        
        <!-- SLA-статус -->
        <select
          v-model="slaStatus"
          class="px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          @change="applySlaFilter"
        >
          <option v-for="opt in slaStatusOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
      
      <!-- Строка 2: Действия -->
      <div class="flex flex-wrap items-end gap-4">
        <!-- Размер страницы -->
        <div>
          <label class="block text-xs text-slate-500 mb-1">На странице</label>
          <select
            v-model="limit"
            class="px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            @change="changePageSize"
          >
            <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}</option>
          </select>
        </div>
        
        <!-- Сброс фильтров -->
        <button
          @click="clearFilters"
          class="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors"
        >
          Сбросить фильтры
        </button>
      </div>
    </div>
    
    <!-- Индикатор загрузки -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
    </div>
    
    <!-- Пустое состояние -->
    <div v-else-if="!incidents.length" class="bg-white rounded-xl shadow-sm border border-slate-200 p-12 text-center">
      <svg class="mx-auto h-12 w-12 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
      </svg>
      <h3 class="mt-2 text-sm font-medium text-slate-800">Инциденты не найдены</h3>
      <p class="mt-1 text-sm text-slate-500">Попробуйте изменить параметры фильтрации или создайте новый инцидент</p>
      <div class="mt-6">
        <router-link
          to="/incidents/create"
          class="px-4 py-2 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors"
        >
          Создать инцидент
        </router-link>
      </div>
    </div>
    
    <!-- Таблица инцидентов -->
    <div v-else class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <table class="w-full">
        <thead class="bg-slate-50 border-b border-slate-200">
          <tr>
            <!-- Сортируемые заголовки -->
            <th 
              class="px-4 py-3 text-left text-sm font-medium text-slate-600 cursor-pointer hover:bg-slate-100 select-none"
              @click="toggleSort('title')"
            >
              Заголовок <span class="text-slate-400">{{ getSortIcon('title') }}</span>
            </th>
            <th 
              class="px-4 py-3 text-left text-sm font-medium text-slate-600 cursor-pointer hover:bg-slate-100 select-none"
              @click="toggleSort('priority')"
            >
              Приоритет <span class="text-slate-400">{{ getSortIcon('priority') }}</span>
            </th>
            <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Статус</th>
            <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Отдел</th>
            <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Исполнитель</th>
            <th 
              class="px-4 py-3 text-left text-sm font-medium text-slate-600 cursor-pointer hover:bg-slate-100 select-none"
              @click="toggleSort('sla_deadline')"
            >
              Дедлайн <span class="text-slate-400">{{ getSortIcon('sla_deadline') }}</span>
            </th>
            <th 
              class="px-4 py-3 text-left text-sm font-medium text-slate-600 cursor-pointer hover:bg-slate-100 select-none"
              @click="toggleSort('created_at')"
            >
              Создан <span class="text-slate-400">{{ getSortIcon('created_at') }}</span>
            </th>
            <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Действия</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-200">
          <!-- Строка инцидента (клик = переход к деталям) -->
          <tr
            v-for="incident in incidents"
            :key="incident.id"
            class="hover:bg-slate-50 cursor-pointer transition-colors"
            @click="router.push(`/incidents/${incident.id}`)"
          >
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <!-- Индикатор просрочки (красный) или близкого дедлайна (жёлтый) -->
                <span
                  v-if="incident.overdue && !['Решён', 'Закрыт'].includes(incident.status_name)"
                  class="w-2 h-2 rounded-full bg-red-500 flex-shrink-0"
                  title="Просрочен"
                ></span>
                <span
                  v-else-if="incident.sla_percentage >= 80 && !['Решён', 'Закрыт'].includes(incident.status_name)"
                  class="w-2 h-2 rounded-full bg-yellow-500 flex-shrink-0"
                  title="Близко к дедлайну"
                ></span>
                <span class="font-medium text-slate-800 truncate max-w-[200px]">{{ incident.title }}</span>
              </div>
            </td>
            <td class="px-4 py-3">
              <!-- Бейдж приоритета (цвет из БД) -->
              <span
                class="px-2 py-1 rounded text-xs font-medium text-white"
                :style="{ backgroundColor: incident.priority_color }"
              >
                {{ incident.priority_name }}
              </span>
            </td>
            <td class="px-4 py-3">
              <!-- Бейдж статуса (цвет из БД) -->
              <span
                class="px-2 py-1 rounded text-xs font-medium"
                :style="{ backgroundColor: incident.status_color, color: '#fff' }"
              >
                {{ incident.status_name }}
              </span>
            </td>
            <td class="px-4 py-3 text-slate-600 text-sm">{{ incident.department_name }}</td>
            <td class="px-4 py-3">
              <!-- Аватар исполнителя или инициалы -->
              <div v-if="incident.executor_name" class="flex items-center gap-2">
                <div 
                  v-if="incident.executor_avatar"
                  class="w-6 h-6 rounded-full bg-cover bg-center flex-shrink-0"
                  :style="{ backgroundImage: `url(${incident.executor_avatar})` }"
                ></div>
                <div 
                  v-else
                  class="w-6 h-6 rounded-full bg-primary-500 flex items-center justify-center text-white text-xs font-medium flex-shrink-0"
                >
                  {{ incident.executor_name?.charAt(0)?.toUpperCase() || '?' }}
                </div>
                <span class="text-slate-600 text-sm">{{ incident.executor_name }}</span>
              </div>
              <span v-else class="text-slate-400 text-sm">—</span>
            </td>
            <td class="px-4 py-3">
              <!-- Дедлайн с индикатором просрочки -->
              <div class="flex items-center gap-1">
                <span 
                  :class="[
                    'text-sm',
                    incident.overdue && !['Решён', 'Закрыт'].includes(incident.status_name) ? 'text-red-600 font-medium' : 
                    incident.sla_percentage >= 80 && !['Решён', 'Закрыт'].includes(incident.status_name) ? 'text-yellow-600 font-medium' : 'text-slate-600'
                  ]"
                >
                  {{ formatDate(incident.sla_deadline) }}
                </span>
                <span 
                  v-if="incident.overdue && !['Решён', 'Закрыт'].includes(incident.status_name)" 
                  class="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded"
                >
                  просрочен
                </span>
                <span 
                  v-else-if="incident.sla_percentage >= 80 && !['Решён', 'Закрыт'].includes(incident.status_name)" 
                  class="text-xs bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded"
                >
                  скоро
                </span>
              </div>
            </td>
            <td class="px-4 py-3 text-slate-600 text-sm">{{ formatDate(incident.created_at) }}</td>
            <td class="px-4 py-3">
              <!-- Кнопка удаления (только с правами) -->
              <button
                v-if="canDeleteIncident(incident)"
                @click="confirmDelete(incident, $event)"
                class="p-1.5 text-red-500 hover:text-red-700 hover:bg-red-50 rounded transition-colors"
                title="Удалить инцидент"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      
      <!-- Пагинация -->
      <div class="px-4 py-3 border-t border-slate-200 flex items-center justify-between flex-wrap gap-4">
        <span class="text-sm text-slate-600">
          Показано {{ incidents.length }} из {{ total }}
        </span>
        <div class="flex items-center gap-2">
          <!-- Кнопка "Назад" -->
          <button
            :disabled="page === 1"
            @click="page--; loadData()"
            class="px-3 py-1.5 rounded border border-slate-300 text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50 transition-colors"
          >
            ← Назад
          </button>
          
          <!-- Номера страниц -->
          <div class="flex gap-1">
            <button
              v-for="p in Math.min(pages, 5)"
              :key="p"
              @click="page = p; loadData()"
              :class="[
                'px-3 py-1.5 rounded text-sm transition-colors',
                page === p 
                  ? 'bg-primary-600 text-white' 
                  : 'border border-slate-300 hover:bg-slate-50'
              ]"
            >
              {{ p }}
            </button>
            <span v-if="pages > 5" class="px-2 py-1.5 text-slate-400">...</span>
            <button
              v-if="pages > 5"
              @click="page = pages; loadData()"
              :class="[
                'px-3 py-1.5 rounded text-sm transition-colors',
                page === pages 
                  ? 'bg-primary-600 text-white' 
                  : 'border border-slate-300 hover:bg-slate-50'
              ]"
            >
              {{ pages }}
            </button>
          </div>
          
          <!-- Кнопка "Вперёд" -->
          <button
            :disabled="page === pages"
            @click="page++; loadData()"
            class="px-3 py-1.5 rounded border border-slate-300 text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50 transition-colors"
          >
            Вперёд →
          </button>
        </div>
      </div>
    </div>
    
    <!-- Модальное окно подтверждения удаления -->
    <div v-if="showDeleteModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
        <h3 class="text-lg font-semibold text-slate-800 mb-4">Подтверждение удаления</h3>
        <p class="text-slate-600 mb-6">
          Вы уверены, что хотите удалить инцидент "<strong>{{ incidentToDelete?.title }}</strong>"?
          Это действие нельзя отменить.
        </p>
        <div class="flex justify-end gap-3">
          <button
            @click="showDeleteModal = false"
            class="px-4 py-2 text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
          >
            Отмена
          </button>
          <button
            @click="deleteIncident"
            :disabled="deleteLoading"
            class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
          >
            <span v-if="deleteLoading">Удаление...</span>
            <span v-else>Удалить</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
