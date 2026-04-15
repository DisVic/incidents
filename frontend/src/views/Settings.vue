<script setup>
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import { useModal } from '@/composables/useModal'

const { alert: showAlert, confirm: showConfirm } = useModal()

const activeTab = ref('statuses')
const loading = ref(false)

// Data
const statuses = ref([])
const categories = ref([])
const slaPolicies = ref([])
const priorities = ref([])

// Modals
const showStatusModal = ref(false)
const showCategoryModal = ref(false)
const showSLAModal = ref(false)

// Forms
const statusForm = ref({ id: null, name: '', color: '#6B7280' })
const categoryForm = ref({ id: null, name: '', description: '' })
const slaForm = ref({ id: null, priority_id: null, resolution_hours: 4, description: '' })

const loadData = async () => {
  loading.value = true
  try {
    const [statusRes, catRes, slaRes, priRes] = await Promise.all([
      axios.get('/api/statuses'),
      axios.get('/api/categories'),
      axios.get('/api/sla/policies'),
      axios.get('/api/priorities')
    ])
    statuses.value = statusRes.data
    categories.value = catRes.data
    slaPolicies.value = slaRes.data
    priorities.value = priRes.data
  } catch (err) {
    console.error('Failed to load settings:', err)
  } finally {
    loading.value = false
  }
}

onMounted(loadData)

// === STATUSES ===
const editStatus = (status = null) => {
  if (status) {
    statusForm.value = { id: status.id, name: status.name, color: status.color || '#6B7280' }
  } else {
    statusForm.value = { id: null, name: '', color: '#6B7280' }
  }
  showStatusModal.value = true
}

const saveStatus = async () => {
  try {
    if (statusForm.value.id) {
      await axios.put(`/api/statuses/${statusForm.value.id}`, {
        name: statusForm.value.name,
        color: statusForm.value.color
      })
    } else {
      await axios.post('/api/statuses', {
        name: statusForm.value.name,
        color: statusForm.value.color
      })
    }
    showStatusModal.value = false
    await loadData()
  } catch (err) {
    await showAlert(err.response?.data?.detail || 'Ошибка сохранения статуса')
  }
}

const deleteStatus = async (status) => {
  const confirmed = await showConfirm(`Удалить статус "${status.name}"?`, 'Удаление статуса')
  if (!confirmed) return
  
  try {
    await axios.delete(`/api/statuses/${status.id}`)
    await loadData()
  } catch (err) {
    await showAlert(err.response?.data?.detail || 'Ошибка удаления статуса')
  }
}

// === CATEGORIES ===
const editCategory = (category = null) => {
  if (category) {
    categoryForm.value = { id: category.id, name: category.name, description: category.description || '' }
  } else {
    categoryForm.value = { id: null, name: '', description: '' }
  }
  showCategoryModal.value = true
}

const saveCategory = async () => {
  try {
    if (categoryForm.value.id) {
      await axios.put(`/api/categories/${categoryForm.value.id}`, {
        name: categoryForm.value.name,
        description: categoryForm.value.description
      })
    } else {
      await axios.post('/api/categories', {
        name: categoryForm.value.name,
        description: categoryForm.value.description
      })
    }
    showCategoryModal.value = false
    await loadData()
  } catch (err) {
    await showAlert(err.response?.data?.detail || 'Ошибка сохранения категории')
  }
}

const deleteCategory = async (category) => {
  const confirmed = await showConfirm(`Удалить категорию "${category.name}"?`, 'Удаление категории')
  if (!confirmed) return
  
  try {
    await axios.delete(`/api/categories/${category.id}`)
    await loadData()
  } catch (err) {
    await showAlert(err.response?.data?.detail || 'Ошибка удаления категории')
  }
}

// === SLA ===
const editSLA = (policy) => {
  slaForm.value = { 
    id: policy.id, 
    priority_id: policy.priority_id, 
    priority_name: policy.priority_name,
    resolution_hours: policy.resolution_hours, 
    description: policy.description || '' 
  }
  showSLAModal.value = true
}

const saveSLA = async () => {
  try {
    await axios.put(`/api/sla/policies/${slaForm.value.id}`, {
      resolution_hours: slaForm.value.resolution_hours,
      description: slaForm.value.description
    })
    showSLAModal.value = false
    await loadData()
  } catch (err) {
    await showAlert(err.response?.data?.detail || 'Ошибка сохранения SLA-политики')
  }
}
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-slate-800 mb-6">Настройки системы</h1>
    
    <!-- Tabs -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 mb-6">
      <div class="flex border-b border-slate-200">
        <button
          @click="activeTab = 'statuses'"
          :class="['px-6 py-4 text-sm font-medium transition-colors', activeTab === 'statuses' ? 'text-primary-600 border-b-2 border-primary-600' : 'text-slate-500 hover:text-slate-700']"
        >
          Статусы
        </button>
        <button
          @click="activeTab = 'categories'"
          :class="['px-6 py-4 text-sm font-medium transition-colors', activeTab === 'categories' ? 'text-primary-600 border-b-2 border-primary-600' : 'text-slate-500 hover:text-slate-700']"
        >
          Категории
        </button>
        <button
          @click="activeTab = 'sla'"
          :class="['px-6 py-4 text-sm font-medium transition-colors', activeTab === 'sla' ? 'text-primary-600 border-b-2 border-primary-600' : 'text-slate-500 hover:text-slate-700']"
        >
          SLA-политики
        </button>
      </div>
      
      <!-- Loading -->
      <div v-if="loading" class="p-8 flex justify-center">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
      
      <!-- Statuses Tab -->
      <div v-else-if="activeTab === 'statuses'" class="p-6">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-lg font-semibold text-slate-800">Статусы инцидентов</h2>
          <button @click="editStatus()" class="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700">
            + Добавить статус
          </button>
        </div>
        
        <div class="space-y-2">
          <div v-for="status in statuses" :key="status.id" class="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
            <div class="flex items-center gap-3">
              <div class="w-4 h-4 rounded-full" :style="{ backgroundColor: status.color }"></div>
              <span class="font-medium text-slate-700">{{ status.name }}</span>
            </div>
            <div class="flex gap-2">
              <button @click="editStatus(status)" class="p-2 text-slate-500 hover:text-primary-600 hover:bg-primary-50 rounded-lg">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </button>
              <button @click="deleteStatus(status)" class="p-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </div>
          
          <div v-if="!statuses.length" class="text-center text-slate-500 py-8">
            Нет статусов
          </div>
        </div>
      </div>
      
      <!-- Categories Tab -->
      <div v-else-if="activeTab === 'categories'" class="p-6">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-lg font-semibold text-slate-800">Категории инцидентов</h2>
          <button @click="editCategory()" class="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700">
            + Добавить категорию
          </button>
        </div>
        
        <div class="space-y-2">
          <div v-for="cat in categories" :key="cat.id" class="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
            <div>
              <span class="font-medium text-slate-700">{{ cat.name }}</span>
              <p v-if="cat.description" class="text-sm text-slate-500">{{ cat.description }}</p>
            </div>
            <div class="flex gap-2">
              <button @click="editCategory(cat)" class="p-2 text-slate-500 hover:text-primary-600 hover:bg-primary-50 rounded-lg">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </button>
              <button @click="deleteCategory(cat)" class="p-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </div>
          
          <div v-if="!categories.length" class="text-center text-slate-500 py-8">
            Нет категорий
          </div>
        </div>
      </div>
      
      <!-- SLA Tab -->
      <div v-else-if="activeTab === 'sla'" class="p-6">
        <div class="mb-4">
          <h2 class="text-lg font-semibold text-slate-800">SLA-политики по приоритетам</h2>
        </div>
        
        <p class="text-sm text-slate-500 mb-4">
          SLA-политики определяют время на решение инцидента в зависимости от приоритета. Рабочие часы: 9:00-18:00, Пн-Пт.
        </p>
        
        <div class="space-y-2">
          <div v-for="policy in slaPolicies" :key="policy.id" class="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
            <div>
              <span class="font-medium text-slate-700">{{ policy.priority_name }}</span>
              <span class="ml-2 text-primary-600 font-semibold">{{ policy.resolution_hours }} ч.</span>
              <p v-if="policy.description" class="text-sm text-slate-500">{{ policy.description }}</p>
            </div>
            <div class="flex gap-2">
              <button @click="editSLA(policy)" class="p-2 text-slate-500 hover:text-primary-600 hover:bg-primary-50 rounded-lg">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </button>
            </div>
          </div>
          
          <div v-if="!slaPolicies.length" class="text-center text-slate-500 py-8">
            Нет SLA-политик
          </div>
        </div>
      </div>
    </div>
    
    <!-- Status Modal -->
    <div v-if="showStatusModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl p-6 w-full max-w-md">
        <h3 class="text-lg font-semibold mb-4">{{ statusForm.id ? 'Редактировать статус' : 'Новый статус' }}</h3>
        
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Название</label>
            <input v-model="statusForm.name" type="text" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500" placeholder="Название статуса" />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Цвет</label>
            <div class="flex items-center gap-3">
              <input v-model="statusForm.color" type="color" class="w-10 h-10 rounded cursor-pointer" />
              <input v-model="statusForm.color" type="text" class="flex-1 px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500" placeholder="#6B7280" />
            </div>
          </div>
        </div>
        
        <div class="flex gap-2 mt-6">
          <button @click="saveStatus" :disabled="!statusForm.name" class="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg disabled:opacity-50">
            Сохранить
          </button>
          <button @click="showStatusModal = false" class="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg">
            Отмена
          </button>
        </div>
      </div>
    </div>
    
    <!-- Category Modal -->
    <div v-if="showCategoryModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl p-6 w-full max-w-md">
        <h3 class="text-lg font-semibold mb-4">{{ categoryForm.id ? 'Редактировать категорию' : 'Новая категория' }}</h3>
        
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Название</label>
            <input v-model="categoryForm.name" type="text" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500" placeholder="Название категории" />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Описание</label>
            <textarea v-model="categoryForm.description" rows="2" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500" placeholder="Описание (опционально)"></textarea>
          </div>
        </div>
        
        <div class="flex gap-2 mt-6">
          <button @click="saveCategory" :disabled="!categoryForm.name" class="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg disabled:opacity-50">
            Сохранить
          </button>
          <button @click="showCategoryModal = false" class="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg">
            Отмена
          </button>
        </div>
      </div>
    </div>
    
    <!-- SLA Modal -->
    <div v-if="showSLAModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl p-6 w-full max-w-md">
        <h3 class="text-lg font-semibold mb-4">Редактировать SLA-политику</h3>
        
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Приоритет</label>
            <div class="px-3 py-2 bg-slate-100 rounded-lg text-slate-700 font-medium">
              {{ slaForm.priority_name }}
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Время на решение (часы)</label>
            <input v-model.number="slaForm.resolution_hours" type="number" min="1" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500" placeholder="4" />
            <p class="text-xs text-slate-500 mt-1">Рабочие часы: 9:00-18:00, Пн-Пт</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Описание</label>
            <textarea v-model="slaForm.description" rows="2" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500" placeholder="Описание (опционально)"></textarea>
          </div>
        </div>
        
        <div class="flex gap-2 mt-6">
          <button @click="saveSLA" :disabled="!slaForm.resolution_hours" class="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg disabled:opacity-50">
            Сохранить
          </button>
          <button @click="showSLAModal = false" class="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg">
            Отмена
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
