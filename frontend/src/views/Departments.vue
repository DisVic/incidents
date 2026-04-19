<script setup>
/**
 * Страница отделов: список с информацией о руководителях, сотрудниках, инцидентах.
 */
import { ref, onMounted } from 'vue'
import axios from 'axios'

const departments = ref([])
const loading = ref(true)

/**
 * Загрузка списка отделов.
 */
onMounted(async () => {
  try {
    const response = await axios.get('/api/departments', { params: { limit: 100 } })
    departments.value = response.data.data
  } catch (err) {
    console.error('Failed to load departments:', err)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-slate-800 mb-6">Отделы</h1>
    
    <!-- Загрузка -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
    </div>
    
    <!-- Карточки отделов -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="dept in departments"
        :key="dept.id"
        class="bg-white rounded-xl shadow-sm p-6 border border-slate-200"
      >
        <h3 class="text-lg font-semibold text-slate-800 mb-2">{{ dept.name }}</h3>
        <p v-if="dept.description" class="text-sm text-slate-500 mb-4">{{ dept.description }}</p>
        
        <!-- Статистика: сотрудники и инциденты -->
        <div class="flex items-center gap-4 text-sm text-slate-600">
          <div>
            <span class="font-medium">{{ dept.users_count }}</span> сотрудников
          </div>
          <div>
            <span class="font-medium">{{ dept.incidents_count }}</span> инцидентов
          </div>
        </div>
        
        <!-- Руководитель -->
        <div v-if="dept.manager_name" class="mt-4 pt-4 border-t border-slate-200 text-sm">
          <span class="text-slate-500">Руководитель:</span>
          <span class="ml-2 text-slate-700">{{ dept.manager_name }}</span>
        </div>
      </div>
      
      <div v-if="!departments.length" class="col-span-full py-12 text-center text-slate-500">
        Отделы не найдены
      </div>
    </div>
  </div>
</template>
