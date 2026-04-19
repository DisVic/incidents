<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const router = useRouter()

// Флаг загрузки данных
const loading = ref(true)
const userData = ref(null)
const error = ref('')

const period = ref('month')
const periods = [
  { value: 'month', label: 'Месяц' },
  { value: 'quarter', label: 'Квартал' },
  { value: 'year', label: 'Год' },
  { value: 'specific_month', label: 'Конкретный месяц' },
  { value: 'custom', label: 'Свой период' }
]

// Specific month selector
const specificMonth = ref('')
const monthOptions = computed(() => {
  const options = []
  const now = new Date()
  // Generate last 12 months
  for (let i = 0; i < 12; i++) {
    const date = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const value = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
    const label = date.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
    options.push({ value, label: label.charAt(0).toUpperCase() + label.slice(1) })
  }
  return options
})

// Custom date range
const customDateFrom = ref('')
const customDateTo = ref('')

// Compute date range
const dateRange = computed(() => {
  if (period.value === 'specific_month' && specificMonth.value) {
    const [year, month] = specificMonth.value.split('-').map(Number)
    const from = new Date(year, month - 1, 1)
    const to = new Date(year, month, 0)
    return {
      date_from: from.toISOString().split('T')[0],
      date_to: to.toISOString().split('T')[0]
    }
  }
  if (period.value === 'custom' && customDateFrom.value && customDateTo.value) {
    return {
      date_from: customDateFrom.value,
      date_to: customDateTo.value
    }
  }
  return null
})

onMounted(() => {
  // Set default specific month to current month
  const now = new Date()
  specificMonth.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  loadStats()
})

// Отслеживание изменений
watch([period, specificMonth, customDateFrom, customDateTo], () => {
  if (period.value === 'custom' && (!customDateFrom.value || !customDateTo.value)) {
    return // Don't reload until both dates are set
  }
  loadStats()
})

async function loadStats() {
  loading.value = true
  error.value = ''
  try {
    const params = {}
    
    if (dateRange.value) {
      params.date_from = dateRange.value.date_from
      params.date_to = dateRange.value.date_to
    } else {
      params.period = period.value
    }
    
    const res = await axios.get(`/api/reports/user/${route.params.id}`, { params })
    userData.value = res.data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Ошибка загрузки данных'
  } finally {
    loading.value = false
  }
}

// Форматирование даты
function formatDate(dateStr) {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function formatHours(hours) {
  if (!hours) return '—'
  if (hours < 24) return `${Math.round(hours)} ч`
  const days = Math.floor(hours / 24)
  const remainingHours = Math.round(hours % 24)
  return `${days} д ${remainingHours} ч`
}

// Возврат назад
function goBack() {
  router.back()
}

function getStatusClass(status) {
  const classes = {
    'Новый': 'bg-blue-100 text-blue-800',
    'Назначен': 'bg-purple-100 text-purple-800',
    'В работе': 'bg-yellow-100 text-yellow-800',
    'Решён': 'bg-green-100 text-green-800',
    'Закрыт': 'bg-gray-100 text-gray-800'
  }
  return classes[status] || 'bg-gray-100 text-gray-800'
}

function getPriorityClass(priority) {
  const classes = {
    'Критический': 'bg-red-100 text-red-800',
    'Высокий': 'bg-orange-100 text-orange-800',
    'Средний': 'bg-blue-100 text-blue-800',
    'Низкий': 'bg-gray-100 text-gray-800'
  }
  return classes[priority] || 'bg-gray-100 text-gray-800'
}
</script>

<template>
  <div class="min-h-screen bg-slate-50">
    <!-- Header -->
    <div class="bg-white shadow-sm border-b border-slate-200">
      <div class="max-w-7xl mx-auto px-4 py-4">
        <div class="flex items-center justify-between flex-wrap gap-4">
          <div class="flex items-center gap-4">
            <button @click="goBack" class="p-2 hover:bg-slate-100 rounded-lg transition-colors">
              <svg class="w-5 h-5 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div>
              <h1 class="text-xl font-semibold text-slate-800">Статистика сотрудника</h1>
              <p v-if="userData" class="text-sm text-slate-500">{{ userData.user_name }}</p>
            </div>
          </div>
          
          <div class="flex items-center gap-3 flex-wrap">
            <select v-model="period" class="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500">
              <option v-for="p in periods" :key="p.value" :value="p.value">{{ p.label }}</option>
            </select>
            
            <!-- Specific month selector -->
            <select v-if="period === 'specific_month'" v-model="specificMonth"
                    class="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500">
              <option v-for="m in monthOptions" :key="m.value" :value="m.value">{{ m.label }}</option>
            </select>
            
            <!-- Custom date inputs -->
            <template v-if="period === 'custom'">
              <input type="date" v-model="customDateFrom"
                     class="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500">
              <span class="text-slate-400">—</span>
              <input type="date" v-model="customDateTo"
                     class="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500">
            </template>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
    </div>
    
    <!-- Error -->
    <div v-else-if="error" class="max-w-7xl mx-auto px-4 py-8">
      <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        {{ error }}
      </div>
    </div>
    
    <!-- Content -->
    <template v-else-if="userData">
      <div class="max-w-7xl mx-auto px-4 py-6">
        <!-- User info -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
          <div class="flex items-center gap-6">
            <div 
              v-if="userData.avatar" 
              class="w-16 h-16 rounded-full bg-cover bg-center"
              :style="{ backgroundImage: `url(${userData.avatar})` }"
            ></div>
            <div v-else class="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center text-white text-2xl font-bold">
              {{ userData.user_name?.charAt(0) || '?' }}
            </div>
            <div>
              <h2 class="text-xl font-semibold text-slate-800">{{ userData.user_name }}</h2>
              <p class="text-slate-500">{{ userData.email }}</p>
              <p v-if="userData.department" class="text-sm text-slate-400">{{ userData.department }}</p>
            </div>
          </div>
        </div>
        
        <!-- Stats cards -->
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
          <div class="bg-white rounded-xl shadow-sm p-4 border border-slate-200">
            <p class="text-sm text-slate-500">Назначено</p>
            <p class="text-2xl font-bold text-slate-800 mt-1">{{ userData.stats.total_assigned }}</p>
          </div>
          
          <div class="bg-white rounded-xl shadow-sm p-4 border border-slate-200">
            <p class="text-sm text-slate-500">Решено</p>
            <p class="text-2xl font-bold text-green-600 mt-1">{{ userData.stats.total_resolved }}</p>
          </div>
          
          <div class="bg-white rounded-xl shadow-sm p-4 border border-slate-200">
            <p class="text-sm text-slate-500">В работе</p>
            <p class="text-2xl font-bold text-yellow-600 mt-1">{{ userData.stats.in_progress }}</p>
          </div>
          
          <div class="bg-white rounded-xl shadow-sm p-4 border border-slate-200">
            <p class="text-sm text-slate-500">Просрочено</p>
            <p class="text-2xl font-bold text-red-600 mt-1">{{ userData.stats.overdue_count }}</p>
          </div>
          
          <div class="bg-white rounded-xl shadow-sm p-4 border border-slate-200">
            <p class="text-sm text-slate-500">Среднее время</p>
            <p class="text-2xl font-bold text-slate-800 mt-1">{{ formatHours(userData.stats.avg_resolution_time_hours) }}</p>
          </div>
          
          <div class="bg-white rounded-xl shadow-sm p-4 border border-slate-200">
            <p class="text-sm text-slate-500">% SLA</p>
            <p :class="['text-2xl font-bold mt-1', userData.stats.sla_compliance >= 90 ? 'text-green-600' : userData.stats.sla_compliance >= 70 ? 'text-yellow-600' : 'text-red-600']">
              {{ userData.stats.sla_compliance }}%
            </p>
          </div>
        </div>
        
        <!-- Incidents table -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div class="px-6 py-4 border-b border-slate-200">
            <h3 class="text-lg font-semibold text-slate-800">Инциденты</h3>
          </div>
          
          <div v-if="userData.incidents.length > 0" class="overflow-x-auto">
            <table class="w-full">
              <thead class="bg-slate-50">
                <tr>
                  <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Заголовок</th>
                  <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Статус</th>
                  <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Приоритет</th>
                  <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Дедлайн</th>
                  <th class="px-4 py-3 text-right text-sm font-medium text-slate-600">Время решения</th>
                  <th class="px-4 py-3 text-center text-sm font-medium text-slate-600">SLA</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-200">
                <tr v-for="inc in userData.incidents" :key="inc.id" class="hover:bg-slate-50">
                  <td class="px-4 py-3">
                    <router-link :to="`/incidents/${inc.id}`" class="text-blue-600 hover:text-blue-800">
                      {{ inc.title }}
                    </router-link>
                  </td>
                  <td class="px-4 py-3">
                    <span :class="getStatusClass(inc.status)" class="px-2 py-1 rounded-full text-xs font-medium">
                      {{ inc.status }}
                    </span>
                  </td>
                  <td class="px-4 py-3">
                    <span :class="getPriorityClass(inc.priority)" class="px-2 py-1 rounded-full text-xs font-medium">
                      {{ inc.priority }}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-sm text-slate-600">
                    <span :class="{ 'text-red-600 font-medium': inc.overdue }">
                      {{ formatDate(inc.sla_deadline) }}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-sm text-slate-600 text-right">
                    {{ formatHours(inc.resolution_time_hours) }}
                  </td>
                  <td class="px-4 py-3 text-center">
                    <span v-if="inc.overdue" class="text-red-600 text-sm font-medium">Просрочен</span>
                    <span v-else class="text-green-600 text-sm">OK</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="py-12 text-center text-slate-500">
            Нет инцидентов за выбранный период
          </div>
        </div>
      </div>
    </template>
  </div>
</template>