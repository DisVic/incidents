<script setup>
import { ref, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const form = ref({
  title: '',
  description: '',
  category_id: null,
  priority_id: null,
  department_id: null,
  initiator_id: null
})

const categories = ref([])
const priorities = ref([])
const departments = ref([])
const loading = ref(false)
const errors = reactive({
  title: '',
  description: '',
  category_id: '',
  priority_id: '',
  department_id: ''
})

// Перевод ошибок на русский
const translateError = (error) => {
  const translations = {
    'string_too_short': 'Слишком короткое значение',
    'string_too_long': 'Слишком длинное значение',
    'missing': 'Обязательное поле',
    'value_error': 'Некорректное значение',
    'type_error': 'Неверный тип данных'
  }
  
  if (typeof error === 'string') {
    // Общие ошибки
    if (error.includes('at least 10 characters') || error.includes('10 characters')) {
      return 'Минимум 10 символов'
    }
    if (error.includes('required') || error.includes('missing')) {
      return 'Обязательное поле'
    }
    return error
  }
  
  if (error.type) {
    const baseMessage = translations[error.type] || error.msg || 'Ошибка валидации'
    
    // Добавляем детали
    if (error.ctx) {
      if (error.ctx.min_length) {
        return `Минимум ${error.ctx.min_length} символов`
      }
      if (error.ctx.max_length) {
        return `Максимум ${error.ctx.max_length} символов`
      }
    }
    
    return baseMessage
  }
  
  return error.msg || 'Ошибка валидации'
}

// Парсинг ошибок от backend
const parseBackendErrors = (errorData) => {
  // Очищаем предыдущие ошибки
  Object.keys(errors).forEach(key => errors[key] = '')
  
  if (Array.isArray(errorData)) {
    errorData.forEach(err => {
      const field = err.loc?.[1] || err.field
      if (field && errors.hasOwnProperty(field)) {
        errors[field] = translateError(err)
      }
    })
  } else if (typeof errorData === 'object') {
    Object.entries(errorData).forEach(([field, message]) => {
      if (errors.hasOwnProperty(field)) {
        errors[field] = translateError(message)
      }
    })
  }
}

// Клиентская валидация
const validateForm = () => {
  let isValid = true
  Object.keys(errors).forEach(key => errors[key] = '')
  
  if (!form.value.title || form.value.title.trim().length < 3) {
    errors.title = 'Минимум 3 символа'
    isValid = false
  }
  
  if (!form.value.description || form.value.description.trim().length < 10) {
    errors.description = 'Минимум 10 символов'
    isValid = false
  }
  
  if (!form.value.category_id) {
    errors.category_id = 'Выберите категорию'
    isValid = false
  }
  
  if (!form.value.priority_id) {
    errors.priority_id = 'Выберите приоритет'
    isValid = false
  }
  
  if (!form.value.department_id) {
    errors.department_id = 'Выберите отдел'
    isValid = false
  }
  
  return isValid
}

onMounted(async () => {
  // Set initiator_id from current user
  if (authStore.user?.id) {
    form.value.initiator_id = authStore.user.id
  }
  
  try {
    const [catRes, priRes, deptRes] = await Promise.all([
      axios.get('/api/categories'),
      axios.get('/api/priorities'),
      axios.get('/api/departments', { params: { limit: 100 } })
    ])
    categories.value = catRes.data
    priorities.value = priRes.data
    departments.value = deptRes.data.data
  } catch (err) {
    console.error('Failed to load reference data:', err)
  }
})

const handleSubmit = async () => {
  // Клиентская валидация
  if (!validateForm()) {
    return
  }
  
  loading.value = true
  
  try {
    const response = await axios.post('/api/incidents', form.value)
    router.push(`/incidents/${response.data.id}`)
  } catch (err) {
    const errorData = err.response?.data?.detail
    if (errorData) {
      parseBackendErrors(errorData)
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <h1 class="text-2xl font-bold text-slate-800 mb-6">Создать инцидент</h1>
    
    <!-- Form -->
    <form @submit.prevent="handleSubmit" class="bg-white rounded-xl shadow-sm p-6 border border-slate-200">
      <!-- Title -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-slate-700 mb-2">
          Заголовок <span class="text-red-500">*</span>
        </label>
        <input
          v-model="form.title"
          type="text"
          :class="[
            'w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent',
            errors.title ? 'border-red-500 bg-red-50' : 'border-slate-300'
          ]"
          placeholder="Краткое описание проблемы"
        />
        <p v-if="errors.title" class="mt-1 text-sm text-red-600">{{ errors.title }}</p>
      </div>
      
      <!-- Description -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-slate-700 mb-2">
          Описание <span class="text-red-500">*</span>
        </label>
        <textarea
          v-model="form.description"
          rows="5"
          :class="[
            'w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent',
            errors.description ? 'border-red-500 bg-red-50' : 'border-slate-300'
          ]"
          placeholder="Подробное описание проблемы (минимум 10 символов)"
        ></textarea>
        <p v-if="errors.description" class="mt-1 text-sm text-red-600">{{ errors.description }}</p>
      </div>
      
      <!-- Category -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-slate-700 mb-2">
          Категория <span class="text-red-500">*</span>
        </label>
        <select
          v-model="form.category_id"
          :class="[
            'w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent',
            errors.category_id ? 'border-red-500 bg-red-50' : 'border-slate-300'
          ]"
        >
          <option :value="null" disabled>Выберите категорию</option>
          <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
        </select>
        <p v-if="errors.category_id" class="mt-1 text-sm text-red-600">{{ errors.category_id }}</p>
      </div>
      
      <!-- Priority -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-slate-700 mb-2">
          Приоритет <span class="text-red-500">*</span>
        </label>
        <select
          v-model="form.priority_id"
          :class="[
            'w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent',
            errors.priority_id ? 'border-red-500 bg-red-50' : 'border-slate-300'
          ]"
        >
          <option :value="null" disabled>Выберите приоритет</option>
          <option v-for="pri in priorities" :key="pri.id" :value="pri.id">{{ pri.name }}</option>
        </select>
        <p v-if="errors.priority_id" class="mt-1 text-sm text-red-600">{{ errors.priority_id }}</p>
      </div>
      
      <!-- Department -->
      <div class="mb-6">
        <label class="block text-sm font-medium text-slate-700 mb-2">
          Отдел-исполнитель <span class="text-red-500">*</span>
        </label>
        <select
          v-model="form.department_id"
          :class="[
            'w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent',
            errors.department_id ? 'border-red-500 bg-red-50' : 'border-slate-300'
          ]"
        >
          <option :value="null" disabled>Выберите отдел</option>
          <option v-for="dept in departments" :key="dept.id" :value="dept.id">{{ dept.name }}</option>
        </select>
        <p v-if="errors.department_id" class="mt-1 text-sm text-red-600">{{ errors.department_id }}</p>
      </div>
      
      <!-- Actions -->
      <div class="flex gap-4">
        <button
          type="submit"
          :disabled="loading"
          class="px-6 py-3 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors disabled:opacity-50"
        >
          {{ loading ? 'Создание...' : 'Создать инцидент' }}
        </button>
        <button
          type="button"
          @click="router.push('/incidents')"
          class="px-6 py-3 bg-slate-100 text-slate-700 rounded-lg font-medium hover:bg-slate-200 transition-colors"
        >
          Отмена
        </button>
      </div>
    </form>
  </div>
</template>