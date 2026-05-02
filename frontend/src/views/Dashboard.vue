<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const loading = ref(true)

// Filters
const departmentId = ref('')
const departments = ref([])

// Period filter
const period = ref('current_month')
const periods = [
  { value: 'current_month', label: 'Текущий месяц' },
  { value: 'last_month', label: 'Прошлый месяц' },
  { value: 'quarter', label: 'Квартал' },
  { value: 'year', label: 'Год' },
  { value: 'all', label: 'Весь период' },
  { value: 'custom', label: 'Свой период' }
]
const customDateFrom = ref('')
const customDateTo = ref('')

// Can filter by department (only Admin)
const canFilterByDepartment = computed(() => authStore.isAdmin)

// Format date using local timezone (avoids UTC day-shift bug with toISOString)
function formatDateLocal(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

// Compute date range from period
const dateRange = computed(() => {
  const now = new Date()
  let from, to
  
  switch (period.value) {
    case 'current_month':
      from = new Date(now.getFullYear(), now.getMonth(), 1)
      to = new Date(now.getFullYear(), now.getMonth() + 1, 0)
      break
    case 'last_month':
      from = new Date(now.getFullYear(), now.getMonth() - 1, 1)
      to = new Date(now.getFullYear(), now.getMonth(), 0)
      break
    case 'quarter':
      from = new Date(now.getFullYear(), now.getMonth() - 3, now.getDate())
      to = now
      break
    case 'year':
      from = new Date(now.getFullYear() - 1, now.getMonth(), now.getDate())
      to = now
      break
    case 'all':
      return { date_from: null, date_to: null }
    case 'custom':
      if (customDateFrom.value && customDateTo.value) {
        from = new Date(customDateFrom.value)
        to = new Date(customDateTo.value)
      } else {
        // Fallback to current month
        from = new Date(now.getFullYear(), now.getMonth(), 1)
        to = new Date(now.getFullYear(), now.getMonth() + 1, 0)
      }
      break
    default:
      from = new Date(now.getFullYear(), now.getMonth(), 1)
      to = new Date(now.getFullYear(), now.getMonth() + 1, 0)
  }
  
  return {
    date_from: formatDateLocal(from),
    date_to: formatDateLocal(to)
  }
})

// Accordion states
const showExecutors = ref(false)
const showDepartments = ref(false)
const showSLA = ref(false)
const showOverdueHistory = ref(false)

// Data
const stats = ref(null)
const recentIncidents = ref([])
const slaStats = ref({ on_time: 0, overdue: 0, near_deadline: 0 })
const statusStats = ref([])
const activityData = ref([])
const topExecutors = ref([])

// Detailed data for accordions
const executorsData = ref([])
const departmentsData = ref([])
const slaData = ref({})

// Overdue incidents data
const overdueIncidents = ref([])

// Effective department ID for filtering
const effectiveDeptId = computed(() => {
  if (authStore.isAdmin) {
    return departmentId.value
  }
  return authStore.user?.department_id || null
})

onMounted(async () => {
  // Load saved period from localStorage
  const savedPeriod = localStorage.getItem('dashboard_period')
  if (savedPeriod) {
    period.value = savedPeriod
  }
  const savedCustomFrom = localStorage.getItem('dashboard_custom_from')
  const savedCustomTo = localStorage.getItem('dashboard_custom_to')
  if (savedCustomFrom) customDateFrom.value = savedCustomFrom
  if (savedCustomTo) customDateTo.value = savedCustomTo
  
  // Load departments for filter
  if (authStore.isAdmin) {
    try {
      const deptRes = await axios.get('/api/departments')
      departments.value = deptRes.data.data || deptRes.data || []
    } catch (err) {
      console.error('Failed to load departments:', err)
    }
  }
  
  await loadDashboard()
})

// Save period to localStorage when changed
watch(period, (newVal) => {
  localStorage.setItem('dashboard_period', newVal)
  loadDashboard()
  resetAccordions()
})

watch([customDateFrom, customDateTo], () => {
  if (period.value === 'custom') {
    localStorage.setItem('dashboard_custom_from', customDateFrom.value)
    localStorage.setItem('dashboard_custom_to', customDateTo.value)
    if (customDateFrom.value && customDateTo.value) {
      loadDashboard()
      resetAccordions()
    }
  }
})

watch(departmentId, () => {
  loadDashboard()
  resetAccordions()
})

function resetAccordions() {
  showExecutors.value = false
  showDepartments.value = false
  showSLA.value = false
  showOverdueHistory.value = false
  executorsData.value = []
  departmentsData.value = []
  slaData.value = {}
  overdueIncidents.value = []
}

async function loadDashboard() {
  loading.value = true
  try {
    const params = {}
    if (dateRange.value.date_from && dateRange.value.date_to) {
      params.date_from = dateRange.value.date_from
      params.date_to = dateRange.value.date_to
    }
    if (effectiveDeptId.value) {
      params.department_id = effectiveDeptId.value
    }
    
    const incidentParams = { limit: 5 }
    if (effectiveDeptId.value) {
      incidentParams.user_department_id = effectiveDeptId.value
    }
    
    const [dashboardRes, incidentsRes, slaRes, statusRes, activityRes, executorsRes] = await Promise.all([
      axios.get('/api/reports/dashboard', { params }),
      axios.get('/api/incidents', { params: incidentParams }),
      axios.get('/api/reports/sla-stats', { params }),
      axios.get('/api/reports/status-stats', { params }),
      axios.get('/api/reports/activity', { params: { ...params, days: 14 } }),
      axios.get('/api/reports/executors', { params: { ...params, limit: 5, days: 30 } })
    ])
    stats.value = dashboardRes.data
    recentIncidents.value = incidentsRes.data.data || []
    slaStats.value = slaRes.data || { on_time: 0, overdue: 0, near_deadline: 0 }
    statusStats.value = statusRes.data || []
    activityData.value = activityRes.data || []
    topExecutors.value = executorsRes.data || []
  } catch (error) {
    console.error('Failed to load dashboard:', error)
  } finally {
    loading.value = false
  }
}

// Load detailed data for accordion
async function loadExecutorsData() {
  if (executorsData.value.length > 0) return
  try {
    const params = {}
    if (dateRange.value.date_from && dateRange.value.date_to) {
      params.date_from = dateRange.value.date_from
      params.date_to = dateRange.value.date_to
    }
    if (effectiveDeptId.value) params.department_id = effectiveDeptId.value
    // Manager sees own department executors + all Admins
    if (authStore.user?.role_name === 'Manager' && effectiveDeptId.value) {
      params.manager_view = true
    }
    const res = await axios.get('/api/reports/executors-detailed', { params })
    executorsData.value = res.data || []
  } catch (err) {
    console.error('Failed to load executors:', err)
  }
}

async function loadDepartmentsData() {
  if (departmentsData.value.length > 0) return
  try {
    const params = {}
    if (dateRange.value.date_from && dateRange.value.date_to) {
      params.date_from = dateRange.value.date_from
      params.date_to = dateRange.value.date_to
    }
    if (effectiveDeptId.value) params.department_id = effectiveDeptId.value
    const res = await axios.get('/api/reports/departments', { params })
    departmentsData.value = res.data || []
  } catch (err) {
    console.error('Failed to load departments:', err)
  }
}

async function loadSLAData() {
  if (slaData.value.total_incidents) return
  try {
    const params = {}
    if (dateRange.value.date_from && dateRange.value.date_to) {
      params.date_from = dateRange.value.date_from
      params.date_to = dateRange.value.date_to
    }
    if (effectiveDeptId.value) params.department_id = effectiveDeptId.value
    const res = await axios.get('/api/reports/sla-analytics', { params })
    slaData.value = res.data || {}
  } catch (err) {
    console.error('Failed to load SLA:', err)
  }
}

async function loadOverdueIncidents() {
  if (overdueIncidents.value.length > 0) return
  try {
    const params = { limit: 20 }
    if (dateRange.value.date_from && dateRange.value.date_to) {
      params.date_from = dateRange.value.date_from
      params.date_to = dateRange.value.date_to
    }
    if (effectiveDeptId.value) params.department_id = effectiveDeptId.value
    const res = await axios.get('/api/reports/overdue-incidents', { params })
    overdueIncidents.value = res.data.incidents || []
  } catch (err) {
    console.error('Failed to load overdue incidents:', err)
  }
}

function toggleExecutors() {
  showExecutors.value = !showExecutors.value
  if (showExecutors.value) {
    loadExecutorsData()
    showDepartments.value = false
    showSLA.value = false
  }
}

function toggleDepartments() {
  showDepartments.value = !showDepartments.value
  if (showDepartments.value) {
    loadDepartmentsData()
    showExecutors.value = false
    showSLA.value = false
  }
}

function toggleSLA() {
  showSLA.value = !showSLA.value
  if (showSLA.value) {
    loadSLAData()
    showExecutors.value = false
    showDepartments.value = false
  }
}

const statCards = [
  { key: 'total_incidents', label: 'Всего инцидентов', color: 'blue', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2' },
  { key: 'new_incidents', label: 'Новые', color: 'indigo', icon: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z' },
  { key: 'in_progress_incidents', label: 'В работе', color: 'yellow', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
  { key: 'resolved_incidents', label: 'Решённые', color: 'green', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
  { key: 'overdue_incidents', label: 'Просроченные', color: 'red', icon: 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
]

const colorBgLight = {
  blue: 'bg-blue-50',
  indigo: 'bg-indigo-50',
  yellow: 'bg-yellow-50',
  green: 'bg-green-50',
  red: 'bg-red-50',
}

const colorText = {
  blue: 'text-blue-600',
  indigo: 'text-indigo-600',
  yellow: 'text-yellow-600',
  green: 'text-green-600',
  red: 'text-red-600',
}

// SLA percentage calculations
const slaTotal = computed(() => slaStats.value.on_time + slaStats.value.overdue + slaStats.value.near_deadline)
const slaOnTimePercent = computed(() => slaTotal.value ? Math.round((slaStats.value.on_time / slaTotal.value) * 100) : 0)
const slaOverduePercent = computed(() => slaTotal.value ? Math.round((slaStats.value.overdue / slaTotal.value) * 100) : 0)
const slaNearPercent = computed(() => slaTotal.value ? Math.round((slaStats.value.near_deadline / slaTotal.value) * 100) : 0)

// Activity chart max
const activityMax = computed(() => Math.max(...activityData.value.map(d => d.count), 1))

// Top executor max for chart
const topExecutorMax = computed(() => Math.max(...topExecutors.value.map(e => e.resolved_count), 1))

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
}

function formatDateTime(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function formatHours(hours) {
  if (!hours) return '—'
  if (hours < 24) return `${hours.toFixed(1)} ч`
  const days = Math.floor(hours / 24)
  const h = (hours % 24).toFixed(0)
  return `${days} д ${h} ч`
}

function getStatusBadgeClass(statusName) {
  const statusColors = {
    'Новый': 'bg-blue-100 text-blue-800',
    'Назначен': 'bg-purple-100 text-purple-800',
    'В работе': 'bg-yellow-100 text-yellow-800',
    'Решён': 'bg-green-100 text-green-800',
    'Закрыт': 'bg-slate-100 text-slate-800',
  }
  return statusColors[statusName] || 'bg-slate-100 text-slate-800'
}
</script>

<template>
  <div>
    <!-- Header with filters -->
    <div class="bg-white rounded-xl shadow-sm p-4 mb-6 border border-slate-200">
      <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <h1 class="text-2xl font-bold text-slate-800">Дашборд</h1>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 flex-1">
          <!-- Period filter -->
          <div>
            <label class="block text-xs text-slate-500 mb-1">Период</label>
            <select v-model="period"
                    class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500">
              <option v-for="p in periods" :key="p.value" :value="p.value">{{ p.label }}</option>
            </select>
          </div>
          <!-- Custom date inputs -->
          <div v-if="period === 'custom'" class="sm:col-span-2 lg:col-span-2">
            <label class="block text-xs text-slate-500 mb-1">Период (с — по)</label>
            <div class="flex items-center gap-2">
              <input type="date" v-model="customDateFrom"
                     class="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500">
              <span class="text-slate-400">—</span>
              <input type="date" v-model="customDateTo"
                     class="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500">
            </div>
          </div>
          <!-- Department filter (admin only) -->
          <div v-if="canFilterByDepartment" :class="period === 'custom' ? '' : 'sm:col-span-2 lg:col-span-2'">
            <label class="block text-xs text-slate-500 mb-1">Отдел</label>
            <select v-model="departmentId"
                    class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500">
              <option value="">Все отделы</option>
              <option v-for="dept in departments" :key="dept.id" :value="dept.id">
                {{ dept.name }}
              </option>
            </select>
          </div>
        </div>
      </div>
    </div>
      
    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
    </div>
    
    <template v-else-if="stats">
      <!-- Main stats cards -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <div
          v-for="card in statCards"
          :key="card.key"
          class="bg-white rounded-xl shadow-sm p-5 border border-slate-200 hover:shadow-md transition-shadow"
        >
          <div class="flex items-center gap-4">
            <div :class="[colorBgLight[card.color], 'p-3 rounded-lg']">
              <svg class="w-6 h-6" :class="colorText[card.color]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="card.icon" />
              </svg>
            </div>
            <div>
              <p class="text-sm text-slate-500">{{ card.label }}</p>
              <p class="text-2xl font-bold text-slate-800">{{ stats[card.key] }}</p>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Charts row -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <!-- SLA Statistics -->
        <div class="bg-white rounded-xl shadow-sm p-6 border border-slate-200">
          <h2 class="text-lg font-semibold text-slate-800 mb-4">SLA-статистика</h2>
          
          <!-- Progress bars -->
          <div class="space-y-4">
            <div>
              <div class="flex justify-between text-sm mb-1">
                <span class="text-slate-600">Соблюдён</span>
                <span class="font-medium text-green-600">{{ slaStats.on_time }} ({{ slaOnTimePercent }}%)</span>
              </div>
              <div class="h-3 bg-slate-100 rounded-full overflow-hidden">
                <div class="h-full bg-green-500 rounded-full transition-all duration-500" :style="{ width: slaOnTimePercent + '%' }"></div>
              </div>
            </div>
            
            <div>
              <div class="flex justify-between text-sm mb-1">
                <span class="text-slate-600">Близко к дедлайну</span>
                <span class="font-medium text-yellow-600">{{ slaStats.near_deadline }} ({{ slaNearPercent }}%)</span>
              </div>
              <div class="h-3 bg-slate-100 rounded-full overflow-hidden">
                <div class="h-full bg-yellow-500 rounded-full transition-all duration-500" :style="{ width: slaNearPercent + '%' }"></div>
              </div>
            </div>
            
            <div>
              <div class="flex justify-between text-sm mb-1">
                <span class="text-slate-600">Просрочен</span>
                <span class="font-medium text-red-600">{{ slaStats.overdue }} ({{ slaOverduePercent }}%)</span>
              </div>
              <div class="h-3 bg-slate-100 rounded-full overflow-hidden">
                <div class="h-full bg-red-500 rounded-full transition-all duration-500" :style="{ width: slaOverduePercent + '%' }"></div>
              </div>
            </div>
          </div>
          
          <!-- Donut chart visualization -->
          <div class="mt-6 flex justify-center">
            <div class="relative w-32 h-32">
              <svg class="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                <circle cx="18" cy="18" r="15.9" fill="none" stroke="#f1f5f9" stroke-width="3"></circle>
                <circle cx="18" cy="18" r="15.9" fill="none" stroke="#ef4444" stroke-width="3"
                        :stroke-dasharray="`${slaOverduePercent} ${100 - slaOverduePercent}`"
                        :stroke-dashoffset="0"></circle>
                <circle cx="18" cy="18" r="15.9" fill="none" stroke="#eab308" stroke-width="3"
                        :stroke-dasharray="`${slaNearPercent} ${100 - slaNearPercent}`"
                        :stroke-dashoffset="-slaOverduePercent"></circle>
                <circle cx="18" cy="18" r="15.9" fill="none" stroke="#22c55e" stroke-width="3"
                        :stroke-dasharray="`${slaOnTimePercent} ${100 - slaOnTimePercent}`"
                        :stroke-dashoffset="-(slaOverduePercent + slaNearPercent)"></circle>
              </svg>
              <div class="absolute inset-0 flex items-center justify-center">
                <div class="text-center">
                  <span class="text-2xl font-bold text-slate-800">{{ slaOnTimePercent }}%</span>
                  <p class="text-xs text-slate-500">SLA</p>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Status distribution -->
        <div class="bg-white rounded-xl shadow-sm p-6 border border-slate-200">
          <h2 class="text-lg font-semibold text-slate-800 mb-4">По статусам</h2>
          
          <div v-if="statusStats.length > 0" class="space-y-3">
            <div v-for="status in statusStats" :key="status.name" class="flex items-center gap-3">
              <div class="flex-1">
                <div class="flex justify-between text-sm mb-1">
                  <span class="text-slate-600">{{ status.name }}</span>
                  <span class="font-medium text-slate-800">{{ status.count }}</span>
                </div>
                <div class="h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div 
                    class="h-full rounded-full transition-all duration-500"
                    :class="{
                      'bg-blue-500': status.name === 'Новый',
                      'bg-purple-500': status.name === 'Назначен',
                      'bg-yellow-500': status.name === 'В работе',
                      'bg-green-500': status.name === 'Решён',
                      'bg-slate-500': status.name === 'Закрыт',
                    }"
                    :style="{ width: (status.count / stats.total_incidents * 100) + '%' }"
                  ></div>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="text-center text-slate-500 py-8">
            Нет данных
          </div>
        </div>
        
        <!-- Incident statistics -->
        <div class="bg-white rounded-xl shadow-sm p-6 border border-slate-200">
          <h2 class="text-lg font-semibold text-slate-800 mb-4">Статистика инцидентов</h2>
          
          <div class="space-y-4">
            <div class="p-4 bg-slate-50 rounded-lg">
              <p class="text-sm text-slate-500">Среднее время решения</p>
              <p class="text-sm text-slate-400 mb-2">От создания до закрытия</p>
              <p class="text-2xl font-bold text-slate-800">
                {{ stats.avg_resolution_time_hours ? `${stats.avg_resolution_time_hours} ч` : '—' }}
              </p>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div class="p-3 bg-blue-50 rounded-lg">
                <p class="text-xs text-blue-600">Создано сегодня</p>
                <p class="text-xl font-bold text-blue-700">{{ stats.incidents_today }}</p>
              </div>
              <div class="p-3 bg-indigo-50 rounded-lg">
                <p class="text-xs text-indigo-600">Создано за месяц</p>
                <p class="text-xl font-bold text-indigo-700">{{ stats.incidents_this_month }}</p>
              </div>
            </div>
            <div class="p-3 bg-green-50 rounded-lg">
              <p class="text-xs text-green-600">Решено за неделю</p>
              <p class="text-sm text-slate-400 mb-1">Перешли в статус "Решён"</p>
              <p class="text-xl font-bold text-green-700">{{ stats.resolved_this_week || 0 }}</p>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Activity chart and top executors -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- Activity chart -->
        <div class="bg-white rounded-xl shadow-sm p-6 border border-slate-200">
          <h2 class="text-lg font-semibold text-slate-800 mb-4">Созданные инциденты (14 дней)</h2>
          
          <div v-if="activityData.length > 0" class="h-48 flex">
            <div class="w-8 flex flex-col justify-between text-xs text-slate-400 pr-2 text-right">
              <span>{{ activityMax }}</span>
              <span>{{ Math.round(activityMax / 2) }}</span>
              <span>0</span>
            </div>
            <div class="flex-1 flex items-end gap-1 border-l border-b border-slate-200 pl-2 pb-6 relative">
              <div class="absolute inset-0 flex flex-col justify-between pointer-events-none pb-6">
                <div class="border-t border-slate-100 w-full"></div>
                <div class="border-t border-slate-100 w-full"></div>
                <div class="border-t border-slate-100 w-full"></div>
              </div>
              <div v-for="(day, index) in activityData" :key="index" class="flex-1 flex flex-col items-center relative">
                <div 
                  class="w-full bg-primary-500 rounded-t transition-all duration-300 hover:bg-primary-600 relative z-10"
                  :style="{ height: (day.count / activityMax * 120) + 'px', minHeight: day.count > 0 ? '4px' : '0' }"
                  :title="`${formatDate(day.date)}: ${day.count} инцидентов`"
                ></div>
                <span class="absolute -bottom-5 text-xs text-slate-400 truncate w-full text-center">{{ formatDate(day.date).split('.')[0] }}</span>
              </div>
            </div>
          </div>
          <div v-else class="h-48 flex items-center justify-center text-slate-500">
            Нет данных за период
          </div>
        </div>
        
        <!-- Top Executors -->
        <div class="bg-white rounded-xl shadow-sm p-6 border border-slate-200">
          <h2 class="text-lg font-semibold text-slate-800 mb-4">Топ исполнителей (30 дней)</h2>
          
          <div v-if="topExecutors.length > 0" class="space-y-3">
            <div v-for="(executor, index) in topExecutors" :key="executor.id" class="flex items-center gap-3">
              <div 
                class="w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-sm"
                :class="{
                  'bg-yellow-500': index === 0,
                  'bg-slate-400': index === 1,
                  'bg-amber-600': index === 2,
                  'bg-slate-300': index > 2
                }"
              >
                {{ index + 1 }}
              </div>
              <div class="flex-1">
                <p class="text-sm font-medium text-slate-700">{{ executor.full_name }}</p>
                <div class="h-2 bg-slate-100 rounded-full overflow-hidden mt-1">
                  <div 
                    class="h-full bg-green-500 rounded-full transition-all duration-300"
                    :style="{ width: (executor.resolved_count / topExecutorMax * 100) + '%' }"
                  ></div>
                </div>
              </div>
              <div class="text-right">
                <span class="text-lg font-bold text-slate-800">{{ executor.resolved_count }}</span>
                <p class="text-xs text-slate-500">решено</p>
              </div>
            </div>
          </div>
          <div v-else class="text-center text-slate-500 py-8">
            Нет данных за период
          </div>
        </div>
      </div>
      
      <!-- Recent incidents -->
      <div class="grid grid-cols-1 gap-6 mb-6">
        <div class="bg-white rounded-xl shadow-sm p-6 border border-slate-200">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-slate-800">Последние инциденты</h2>
            <router-link to="/incidents" class="text-sm text-primary-600 hover:text-primary-700">
              Все →
            </router-link>
          </div>
          
          <div v-if="recentIncidents.length > 0" class="space-y-3">
            <router-link 
              v-for="incident in recentIncidents" 
              :key="incident.id" 
              :to="`/incidents/${incident.id}`"
              class="block p-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium text-slate-800 truncate">{{ incident.title }}</p>
                  <p class="text-xs text-slate-500 mt-1">{{ formatDateTime(incident.created_at) }}</p>
                </div>
                <div class="flex gap-1">
                  <span :class="[getStatusBadgeClass(incident.status_name), 'px-2 py-1 text-xs rounded-full']">
                    {{ incident.status_name }}
                  </span>
                </div>
              </div>
            </router-link>
          </div>
          <div v-else class="text-center text-slate-500 py-8">
            Нет инцидентов
          </div>
        </div>
      </div>
      
      <!-- Detail accordions -->
      <div class="space-y-3">
        <!-- Executors accordion -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <button 
            @click="toggleExecutors"
            class="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
          >
            <span class="text-lg font-semibold text-slate-800">Детализация по исполнителям</span>
            <svg 
              class="w-5 h-5 text-slate-400 transition-transform duration-200"
              :class="{ 'rotate-180': showExecutors }"
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          <div v-if="showExecutors" class="border-t border-slate-200 p-4">
            <div v-if="executorsData.length > 0" class="overflow-x-auto">
              <table class="w-full">
                <thead class="bg-slate-50">
                  <tr>
                    <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Исполнитель</th>
                    <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Отдел</th>
                    <th class="px-4 py-3 text-right text-sm font-medium text-slate-600">Назначено</th>
                    <th class="px-4 py-3 text-right text-sm font-medium text-slate-600">Решено</th>
                    <th class="px-4 py-3 text-right text-sm font-medium text-slate-600">Среднее время</th>
                    <th class="px-4 py-3 text-right text-sm font-medium text-slate-600">Просрочено</th>
                    <th class="px-4 py-3 text-right text-sm font-medium text-slate-600">% SLA</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-200">
                  <tr v-for="stat in executorsData" :key="stat.executor_id" class="hover:bg-slate-50">
                    <td class="px-4 py-3">
                      <router-link :to="`/users/${stat.executor_id}/stats`" class="block font-medium text-slate-800 hover:text-blue-600 transition-colors cursor-pointer">
                        {{ stat.executor_name }}
                      </router-link>
                    </td>
                    <td class="px-4 py-3 text-slate-600">{{ stat.department_name || '—' }}</td>
                    <td class="px-4 py-3 text-right text-slate-600">{{ stat.total_assigned }}</td>
                    <td class="px-4 py-3 text-right text-slate-600">{{ stat.total_resolved }}</td>
                    <td class="px-4 py-3 text-right text-slate-600">{{ formatHours(stat.avg_resolution_time_hours) }}</td>
                    <td class="px-4 py-3 text-right">
                      <span :class="stat.overdue_count > 0 ? 'text-red-600 font-medium' : 'text-slate-600'">
                        {{ stat.overdue_count }}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-right">
                      <span :class="stat.sla_compliance >= 90 ? 'text-green-600' : stat.sla_compliance >= 70 ? 'text-yellow-600' : 'text-red-600'">
                        {{ stat.sla_compliance }}%
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="py-8 text-center text-slate-500">Нет данных</div>
          </div>
        </div>
        
        <!-- Departments accordion - Admin only -->
        <div v-if="authStore.isAdmin && !departmentId" class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <button 
            @click="toggleDepartments"
            class="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
          >
            <span class="text-lg font-semibold text-slate-800">Детализация по отделам</span>
            <svg 
              class="w-5 h-5 text-slate-400 transition-transform duration-200"
              :class="{ 'rotate-180': showDepartments }"
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          <div v-if="showDepartments" class="border-t border-slate-200 p-4">
            <div v-if="departmentsData.length > 0" class="overflow-x-auto">
              <table class="w-full">
                <thead class="bg-slate-50">
                  <tr>
                    <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Отдел</th>
                    <th class="px-4 py-3 text-right text-sm font-medium text-slate-600">Всего</th>
                    <th class="px-4 py-3 text-right text-sm font-medium text-slate-600">Новых</th>
                    <th class="px-4 py-3 text-right text-sm font-medium text-slate-600">В работе</th>
                    <th class="px-4 py-3 text-right text-sm font-medium text-slate-600">Решено</th>
                    <th class="px-4 py-3 text-right text-sm font-medium text-slate-600">Просрочено</th>
                    <th class="px-4 py-3 text-right text-sm font-medium text-slate-600">Ср. время</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-200">
                  <tr v-for="stat in departmentsData" :key="stat.department_id" class="hover:bg-slate-50">
                    <td class="px-4 py-3 font-medium text-slate-800">{{ stat.department_name }}</td>
                    <td class="px-4 py-3 text-right text-slate-600">{{ stat.total_incidents }}</td>
                    <td class="px-4 py-3 text-right text-slate-600">{{ stat.new_count }}</td>
                    <td class="px-4 py-3 text-right text-slate-600">{{ stat.in_progress_count }}</td>
                    <td class="px-4 py-3 text-right text-slate-600">{{ stat.resolved_count }}</td>
                    <td class="px-4 py-3 text-right">
                      <span :class="stat.overdue_count > 0 ? 'text-red-600 font-medium' : 'text-slate-600'">
                        {{ stat.overdue_count }}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-right text-slate-600">{{ formatHours(stat.avg_resolution_time_hours) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="py-8 text-center text-slate-500">Нет данных</div>
          </div>
        </div>
        
        <!-- SLA Analytics accordion -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <button 
            @click="toggleSLA"
            class="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
          >
            <span class="text-lg font-semibold text-slate-800">SLA-аналитика</span>
            <svg 
              class="w-5 h-5 text-slate-400 transition-transform duration-200"
              :class="{ 'rotate-180': showSLA }"
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          <div v-if="showSLA" class="border-t border-slate-200 p-4">
            <!-- Summary cards -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <div class="bg-slate-50 rounded-lg p-4">
                <p class="text-sm text-slate-500">Всего инцидентов</p>
                <p class="text-2xl font-bold text-slate-800 mt-1">{{ slaData.total_incidents }}</p>
              </div>
              <div class="bg-green-50 rounded-lg p-4">
                <p class="text-sm text-slate-500">Соблюдено SLA</p>
                <p class="text-2xl font-bold text-green-600 mt-1">{{ slaData.on_time_count }}</p>
                <p class="text-sm text-green-600">{{ slaData.on_time_percent }}%</p>
              </div>
              <div class="bg-red-50 rounded-lg p-4">
                <p class="text-sm text-slate-500">Просрочено</p>
                <p class="text-2xl font-bold text-red-600 mt-1">{{ slaData.overdue_count }}</p>
                <p class="text-sm text-red-600">{{ slaData.overdue_percent }}%</p>
              </div>
              <div class="bg-slate-50 rounded-lg p-4">
                <p class="text-sm text-slate-500">Среднее время решения</p>
                <p class="text-2xl font-bold text-slate-800 mt-1">{{ formatHours(slaData.avg_resolution_time_hours) }}</p>
              </div>
            </div>
            
            <!-- Problem zones -->
            <div class="bg-slate-50 rounded-lg p-4">
              <h4 class="text-sm font-semibold text-slate-700 mb-3">Проблемные зоны</h4>
              <div v-if="slaData.problem_zones && slaData.problem_zones.length > 0" class="space-y-2">
                <div v-for="zone in slaData.problem_zones" :key="zone.name" 
                     class="flex items-center justify-between p-3 bg-red-50 rounded-lg">
                  <span class="text-slate-700">{{ zone.name }}</span>
                  <span class="text-red-600 font-medium">{{ zone.overdue_count }} просрочек ({{ zone.overdue_percent }}%)</span>
                </div>
              </div>
              <div v-else class="text-center text-slate-500 py-4">
                Нет проблемных зон за выбранный период
              </div>
            </div>
          </div>
        </div>
        
        <!-- Overdue Incidents History accordion -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <button 
            @click="showOverdueHistory = !showOverdueHistory; if (showOverdueHistory) loadOverdueIncidents()"
            class="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
          >
            <span class="text-lg font-semibold text-slate-800">История просрочек</span>
            <svg 
              class="w-5 h-5 text-slate-400 transition-transform duration-200"
              :class="{ 'rotate-180': showOverdueHistory }"
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          <div v-if="showOverdueHistory" class="border-t border-slate-200 p-4">
            <div v-if="overdueIncidents.length > 0" class="overflow-x-auto">
              <table class="w-full">
                <thead class="bg-slate-50">
                  <tr>
                    <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Инцидент</th>
                    <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Исполнитель</th>
                    <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Отдел</th>
                    <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Статус</th>
                    <th class="px-4 py-3 text-left text-sm font-medium text-slate-600">Дедлайн</th>
                    <th class="px-4 py-3 text-right text-sm font-medium text-slate-600">Просрочка</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-200">
                  <tr v-for="inc in overdueIncidents" :key="inc.id" class="hover:bg-slate-50">
                    <td class="px-4 py-3">
                      <router-link :to="`/incidents/${inc.id}`" class="text-blue-600 hover:text-blue-800 font-medium">
                        {{ inc.title }}
                      </router-link>
                    </td>
                    <td class="px-4 py-3 text-slate-600">{{ inc.executor_name || 'Не назначен' }}</td>
                    <td class="px-4 py-3 text-slate-600">{{ inc.department || '-' }}</td>
                    <td class="px-4 py-3">
                      <span :class="inc.is_active ? 'text-yellow-600' : 'text-slate-600'">
                        {{ inc.status }}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-slate-600">{{ formatDate(inc.sla_deadline) }}</td>
                    <td class="px-4 py-3 text-right">
                      <span class="text-red-600 font-medium">{{ inc.overdue_hours }} ч.</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="py-8 text-center text-slate-500">
              Нет просроченных инцидентов
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>