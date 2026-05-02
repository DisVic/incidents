<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import { useModal } from '@/composables/useModal'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { alert: showAlert, confirm: showConfirm, prompt: showPrompt } = useModal()

const incident = ref(null)
const comments = ref([])
const attachments = ref([])
const history = ref([])
const loading = ref(true)
const newComment = ref('')
const commentLoading = ref(false)
const fileInput = ref(null)
const uploadLoading = ref(false)

// Actions
const showAssignModal = ref(false)
const showStatusModal = ref(false)
const showPriorityModal = ref(false)
const showDeadlineModal = ref(false)
const selectedExecutor = ref(null)
const selectedStatus = ref(null)
const selectedPriority = ref(null)
const newDeadline = ref('')
const deadlineReason = ref('')
const slaViolationConfirmed = ref(false)
const actionComment = ref('')
const users = ref([])

// Фильтрованный список для назначения исполнителя
// - Только Executor, Manager, Admin (без User)
// - Только из отдела инцидента (кроме Admin - они глобальные)
// - Только активные
const assignableUsers = computed(() => {
  if (!users.value.length || !incident.value) return []
  
  const incidentDeptId = incident.value.department_id
  
  return users.value.filter(user => {
    // Только активные
    if (!user.is_active) return false
    
    // Без роли User
    if (user.role_name === 'User') return false
    
    // Admin - глобальные, доступны всегда
    if (user.role_name === 'Admin') return true
    
    // Manager и Executor - только из отдела инцидента
    return user.department_id === incidentDeptId
  })
})
const statuses = ref([])
const priorities = ref([])

const canEdit = computed(() => {
  if (!incident.value || !authStore.user) return false
  return authStore.isExecutor
})

// Инициатор может редактировать свои инциденты
const canEditAsInitiator = computed(() => {
  if (!incident.value || !authStore.user) return false
  // Инициатор может редактировать только если статус "Новый" и нет исполнителя
  return incident.value.initiator_id === authStore.user.id &&
         incident.value.status_name === 'Новый' &&
         !incident.value.executor_id
})

const showEditModal = ref(false)
const editForm = ref({
  title: '',
  description: '',
  category_id: null,
  priority_id: null,
  department_id: null
})
const editLoading = ref(false)
const categories = ref([])
const departments = ref([])

const openEditModal = () => {
  editForm.value = {
    title: incident.value.title,
    description: incident.value.description,
    category_id: incident.value.category_id,
    priority_id: incident.value.priority_id,
    department_id: incident.value.department_id
  }
  showEditModal.value = true
  // Load categories and departments if needed
  if (!categories.value.length) {
    axios.get('/api/categories').then(res => {
      categories.value = res.data
    })
  }
  // Load departments for Admin/Manager OR for initiator (to change department)
  if (!departments.value.length && (authStore.user?.role_name === 'Admin' || authStore.user?.role_name === 'Manager' || canEditAsInitiator.value)) {
    axios.get('/api/departments', { params: { limit: 100 } }).then(res => {
      departments.value = res.data.data || res.data
    })
  }
}

const saveEdit = async () => {
  editLoading.value = true
  try {
    const payload = {}
    const isManagerOrAdmin = authStore.user?.role_name === 'Admin' || authStore.user?.role_name === 'Manager'
    
    // Manager/Admin отправляют ТОЛЬКО отдел
    if (isManagerOrAdmin) {
      if (editForm.value.department_id !== incident.value.department_id) {
        payload.department_id = editForm.value.department_id
      }
    } else {
      // Инициатор отправляет все поля
      if (editForm.value.title !== incident.value.title) payload.title = editForm.value.title
      if (editForm.value.description !== incident.value.description) payload.description = editForm.value.description
      if (editForm.value.category_id !== incident.value.category_id) payload.category_id = editForm.value.category_id
      if (editForm.value.priority_id !== incident.value.priority_id) payload.priority_id = editForm.value.priority_id
      if (editForm.value.department_id !== incident.value.department_id) payload.department_id = editForm.value.department_id
    }
    
    // Определяем роль для backend
    const userRole = authStore.user?.role_name || 'User'
    
    await axios.put(`/api/incidents/${route.params.id}`, payload, {
      params: {
        user_id: authStore.user.id,
        user_role: userRole
      }
    })
    showEditModal.value = false
    await loadData()
    await showAlert('Инцидент обновлён')
  } catch (err) {
    console.error('Edit error:', err.response?.data)
    await showAlert(getErrorMessage(err))
  } finally {
    editLoading.value = false
  }
}

const canAssign = computed(() => {
  // Admin и Manager могут назначать и переназначать исполнителя
  if (!incident.value || !authStore.user) return false
  if (!authStore.isManager && !authStore.isAdmin) return false
  
  // Нельзя назначать на закрытый/решённый инцидент
  if (incident.value.status_name === 'Закрыт' || incident.value.status_name === 'Решён') return false
  
  return true
})

const canTake = computed(() => {
  if (!incident.value || !authStore.user) return false
  return (
    authStore.isExecutor &&
    !incident.value.executor_id &&
    incident.value.department_id === authStore.user.department_id
  )
})

const canResolve = computed(() => {
  if (!incident.value || !authStore.user) return false
  return incident.value.executor_id === authStore.user.id
})

const canClose = computed(() => {
  if (!incident.value || !authStore.user) return false
  return (
    incident.value.status_name === 'Решён' &&
    (incident.value.initiator_id === authStore.user.id || authStore.isManager)
  )
})

const canUpdateDeadline = computed(() => {
  // Admin и Manager могут изменять дедлайн
  if (!incident.value || !authStore.user) return false
  if (!authStore.isManager && !authStore.isAdmin) return false
  
  // Нельзя менять дедлайн для закрытого/решённого инцидента
  if (incident.value.status_name === 'Закрыт' || incident.value.status_name === 'Решён') return false
  
  // Manager только для своего отдела
  if (authStore.isManager && authStore.user?.department_id !== incident.value.department_id) return false
  
  return true
})

const canDelete = computed(() => {
  if (!incident.value || !authStore.user) return false
  
  // Admin can delete any incident
  if (authStore.isAdmin) return true
  
  // Manager can delete incidents from their department
  if (authStore.isManager) {
    return authStore.user?.department_id === incident.value.department_id
  }
  
  // User can delete only incidents they created AND only if status is "Новый"
  if (authStore.user?.role_name === 'User') {
    return incident.value.initiator_id === authStore.user?.id && incident.value.status_name === 'Новый'
  }
  
  // Executor cannot delete
  return false
})

const showDeleteModal = ref(false)
const deleteLoading = ref(false)

// Comment edit modal
const showEditCommentModal = ref(false)
const editCommentContent = ref('')
const editCommentLoading = ref(false)
const editingCommentId = ref(null)

const isClosed = computed(() => {
  return incident.value?.status_name === 'Закрыт'
})

const formatDate = (date) => {
  if (!date) return '—'
  return new Date(date).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' Б'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' КБ'
  return (bytes / (1024 * 1024)).toFixed(1) + ' МБ'
}

// SLA progress bar helpers
const slaProgressWidth = computed(() => {
  if (!incident.value) return 0
  const pct = incident.value.sla_percentage || 0
  return Math.min(pct, 100)
})

const slaProgressBarClass = computed(() => {
  if (!incident.value) return 'bg-green-500'
  const color = incident.value.sla_status_color
  switch (color) {
    case 'red': return 'bg-red-500'
    case 'orange': return 'bg-orange-500'
    case 'yellow': return 'bg-yellow-500'
    default: return 'bg-green-500'
  }
})

const slaContainerClass = computed(() => {
  if (!incident.value) return 'bg-slate-200'
  const isActive = !['Решён', 'Закрыт'].includes(incident.value.status_name)
  if (!isActive) return 'bg-slate-100 border-slate-300'  // Для закрытых инцидентов
  if (incident.value.overdue && isActive) return 'bg-red-100 border-red-300'
  if (incident.value.sla_percentage >= 80 && !incident.value.overdue && isActive) return 'bg-yellow-50 border-yellow-300'
  return 'bg-slate-100'
})

const slaTextClass = computed(() => {
  if (!incident.value) return 'text-slate-600'
  const isActive = !['Решён', 'Закрыт'].includes(incident.value.status_name)
  if (incident.value.overdue && isActive) return 'text-red-600'
  if (incident.value.sla_percentage >= 80 && !incident.value.overdue && isActive) return 'text-yellow-600'
  // Для закрытых/решённых — показываем финальный процент зелёным
  if (!isActive) return 'text-green-600'
  return 'text-slate-600'
})

const slaPercentageDisplay = computed(() => {
  if (!incident.value) return 0
  return incident.value.sla_percentage || 0
})

const loadData = async () => {
  loading.value = true
  try {
    // Add timestamp to prevent browser caching
    const timestamp = new Date().getTime()
    const [incRes, comRes, attRes] = await Promise.all([
      axios.get(`/api/incidents/${route.params.id}?t=${timestamp}`),
      axios.get(`/api/incidents/${route.params.id}/comments?t=${timestamp}`),
      axios.get(`/api/incidents/${route.params.id}/attachments?t=${timestamp}`)
    ])
    incident.value = incRes.data
    comments.value = comRes.data
    attachments.value = attRes.data
    
    // Load history for executors and managers
    if (authStore.isExecutor) {
      const histRes = await axios.get(`/api/incidents/${route.params.id}/history`)
      history.value = histRes.data
    }
    
    // Load reference data for actions
    if (canAssign.value || canEdit.value || canEditAsInitiator.value) {
      const [usersRes, statusesRes, prioritiesRes] = await Promise.all([
        axios.get('/api/users', { params: { limit: 100 } }),
        axios.get('/api/statuses'),
        axios.get('/api/priorities')
      ])
      users.value = usersRes.data.data
      statuses.value = statusesRes.data
      priorities.value = prioritiesRes.data
    }
    
    // Load departments for Admin/Manager or initiator edit
    if (authStore.user?.role_name === 'Admin' || authStore.user?.role_name === 'Manager' || canEditAsInitiator.value) {
      axios.get('/api/departments', { params: { limit: 100 } }).then(res => {
        departments.value = res.data.data || res.data
      })
    }
  } catch (err) {
    console.error('Failed to load incident:', err)
    router.push('/incidents')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)

const addComment = async () => {
  if (!newComment.value.trim()) return
  commentLoading.value = true
  
  try {
    const response = await axios.post(`/api/incidents/${route.params.id}/comments`, {
      content: newComment.value
    })
    comments.value.push(response.data)
    newComment.value = ''
  } catch (err) {
    console.error('Failed to add comment:', err)
    await showAlert(err.response?.data?.detail || 'Ошибка добавления комментария')
  } finally {
    commentLoading.value = false
  }
}

const getErrorMessage = (err) => {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(e => e.msg).join(', ')
  if (detail?.message) return detail.message
  if (detail?.msg) return detail.msg
  return 'Произошла ошибка'
}

const takeIncident = async () => {
  const confirmed = await showConfirm('Взять инцидент в работу?')
  if (!confirmed) return
  
  try {
    await axios.post(`/api/incidents/${route.params.id}/take`, {
      user_id: authStore.user?.id
    })
    await loadData()
  } catch (err) {
    await showAlert(getErrorMessage(err))
  }
}

const resolveIncident = async () => {
  const comment = await showPrompt('Комментарий к решению:', '', 'Решение инцидента')
  if (comment === null) return
  
  try {
    await axios.post(`/api/incidents/${route.params.id}/resolve`, null, {
      params: {
        executor_id: authStore.user?.id,
        comment: comment || ''
      }
    })
    await loadData()
  } catch (err) {
    await showAlert(getErrorMessage(err))
  }
}

const closeIncident = async () => {
  const confirmed = await showConfirm('Закрыть инцидент? Это действие нельзя отменить.', 'Закрытие инцидента')
  if (!confirmed) return
  
  try {
    await axios.post(`/api/incidents/${route.params.id}/close`, {
      user_id: authStore.user?.id
    })
    await loadData()
  } catch (err) {
    await showAlert(getErrorMessage(err))
  }
}

const deleteIncident = async () => {
  deleteLoading.value = true
  try {
    await axios.delete(`/api/incidents/${route.params.id}`, {
      params: {
        user_id: authStore.user?.id,
        user_role: authStore.user?.role_name,
        user_department_id: authStore.user?.department_id
      }
    })
    router.push('/incidents')
  } catch (err) {
    await showAlert(getErrorMessage(err))
  } finally {
    deleteLoading.value = false
    showDeleteModal.value = false
  }
}

const assignExecutor = async () => {
  if (!selectedExecutor.value) return
  
  try {
    await axios.post(`/api/incidents/${route.params.id}/assign`, {
      executor_id: selectedExecutor.value,
      assigned_by_id: authStore.user?.id
    })
    showAssignModal.value = false
    selectedExecutor.value = null
    await loadData()
  } catch (err) {
    await showAlert(getErrorMessage(err))
  }
}

const changeStatus = async () => {
  if (!selectedStatus.value) return
  
  try {
    await axios.post(`/api/incidents/${route.params.id}/status`, {
      status_id: selectedStatus.value,
      user_id: authStore.user?.id,
      comment: actionComment.value || undefined
    })
    showStatusModal.value = false
    selectedStatus.value = null
    actionComment.value = ''
    await loadData()
  } catch (err) {
    await showAlert(getErrorMessage(err))
  }
}

const changePriority = async () => {
  if (!selectedPriority.value) return
  
  try {
    const response = await axios.post(`/api/incidents/${route.params.id}/priority?priority_id=${selectedPriority.value}&user_id=${authStore.user?.id}`)
    showPriorityModal.value = false
    selectedPriority.value = null
    await loadData()
    
    // Show result message
    if (response.data.deadline_recalculated) {
      await showAlert(`Приоритет изменён. Дедлайн пересчитан: ${response.data.new_deadline ? new Date(response.data.new_deadline).toLocaleString('ru-RU') : 'N/A'}`)
    }
  } catch (err) {
    await showAlert(getErrorMessage(err))
  }
}

const updateDeadline = async () => {
  if (!newDeadline.value) return

  try {
    const response = await axios.put(`/api/incidents/${route.params.id}/deadline`, {
      new_deadline: new Date(newDeadline.value).toISOString(),
      user_id: authStore.user?.id,
      reason: deadlineReason.value || undefined,
      sla_violation_confirmed: slaViolationConfirmed.value
    })
    showDeadlineModal.value = false
    newDeadline.value = ''
    deadlineReason.value = ''
    slaViolationConfirmed.value = false
    await loadData()

    // Show result message
    await showAlert(`Дедлайн изменён: ${new Date(response.data.new_deadline).toLocaleString('ru-RU')}`)
  } catch (err) {
    await showAlert(getErrorMessage(err))
  }
}
// File upload
const triggerFileUpload = () => {
  fileInput.value?.click()
}

const handleFileUpload = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return
  
  // Check file size (max 10MB)
  if (file.size > 10 * 1024 * 1024) {
    await showAlert('Файл слишком большой. Максимальный размер: 10 МБ')
    return
  }
  
  uploadLoading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('uploader_id', authStore.user?.id || '40000000-0000-0000-0000-000000000001')
    
    const response = await axios.post(`/api/incidents/${route.params.id}/attachments`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    attachments.value.unshift(response.data)
  } catch (err) {
    await showAlert(err.response?.data?.detail || 'Ошибка загрузки файла')
  } finally {
    uploadLoading.value = false
    event.target.value = ''
  }
}

// File delete
const deleteAttachment = async (att) => {
  const confirmed = await showConfirm(`Удалить файл "${att.filename}"?`, 'Удаление файла')
  if (!confirmed) return
  
  try {
    await axios.delete(`/api/attachments/${att.id}`)
    attachments.value = attachments.value.filter(a => a.id !== att.id)
  } catch (err) {
    await showAlert(err.response?.data?.detail || 'Ошибка удаления файла')
  }
}

// Check if user can delete attachment (uploader or admin)
const canDeleteAttachment = (att) => {
  if (!authStore.user) return false
  return att.uploader_id === authStore.user.id || authStore.isAdmin
}

// Check if user can edit comment (only creator)
const canEditComment = (comment) => {
  if (!authStore.user) return false
  return comment.author_id === authStore.user.id
}

// Check if user can delete comment (creator or admin)
const canDeleteComment = (comment) => {
  if (!authStore.user) return false
  return comment.author_id === authStore.user.id || authStore.isAdmin
}

// Edit comment
const editComment = async (comment) => {
  editingCommentId.value = comment.id
  editCommentContent.value = comment.content
  showEditCommentModal.value = true
}

// Save comment edit
const saveCommentEdit = async () => {
  if (!editCommentContent.value.trim() || !editingCommentId.value) return
  
  editCommentLoading.value = true
  
  try {
    const response = await axios.put(`/api/comments/${editingCommentId.value}`, {
      content: editCommentContent.value
    })
    // Update comment in list
    const index = comments.value.findIndex(c => c.id === editingCommentId.value)
    if (index !== -1) {
      comments.value[index] = response.data
    }
    showEditCommentModal.value = false
    editCommentContent.value = ''
    editingCommentId.value = null
  } catch (err) {
    await showAlert(getErrorMessage(err))
  } finally {
    editCommentLoading.value = false
  }
}

// Delete comment
const deleteComment = async (comment) => {
  const confirmed = await showConfirm(`Удалить комментарий?`, 'Удаление комментария')
  if (!confirmed) return
  
  try {
    await axios.delete(`/api/comments/${comment.id}`)
    // Remove comment from list
    comments.value = comments.value.filter(c => c.id !== comment.id)
  } catch (err) {
    await showAlert(getErrorMessage(err))
  }
}
</script>

<template>
  <div>
    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
    </div>
    
    <template v-else-if="incident">
      <!-- Header -->
      <div class="flex items-center gap-4 mb-6">
        <button @click="router.push('/incidents')" class="p-2 hover:bg-slate-100 rounded-lg">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h1 class="text-2xl font-bold text-slate-800">{{ incident.title }}</h1>
      </div>
      
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Main info -->
        <div class="lg:col-span-2 space-y-6">
          <!-- Details card -->
          <div class="bg-white rounded-xl shadow-sm p-6 border border-slate-200">
            <div class="flex items-start justify-between mb-4">
              <div class="flex items-center gap-3">
                <span
                  class="px-3 py-1 rounded-lg text-sm font-medium text-white"
                  :style="{ backgroundColor: incident.priority_color }"
                >
                  {{ incident.priority_name }}
                </span>
                <span
                  class="px-3 py-1 rounded-lg text-sm font-medium"
                  :style="{ backgroundColor: incident.status_color, color: '#fff' }"
                >
                  {{ incident.status_name }}
                </span>
                <span
                  v-if="incident.overdue && !['Решён', 'Закрыт'].includes(incident.status_name)"
                  class="px-3 py-1 rounded-lg text-sm font-medium bg-red-100 text-red-700"
                >
                  Просрочен
                </span>
                <span
                  v-else-if="incident.sla_percentage >= 80 && !incident.overdue && !['Решён', 'Закрыт'].includes(incident.status_name)"
                  class="px-3 py-1 rounded-lg text-sm font-medium bg-yellow-100 text-yellow-700"
                >
                  Скоро дедлайн
                </span>
                <span 
                  v-if="incident.status_name === 'Решён'"
                  class="px-3 py-1 rounded-lg text-sm font-medium bg-green-100 text-green-700"
                >
                  Решён за {{ incident.sla_percentage?.toFixed(1) }}% SLA
                </span>
                <span 
                  v-else-if="incident.status_name === 'Закрыт'"
                  class="px-3 py-1 rounded-lg text-sm font-medium bg-green-100 text-green-700"
                >
                  Закрыт за {{ incident.sla_percentage?.toFixed(1) }}% SLA
                </span>
              </div>
            </div>
            
            <p class="text-slate-700 whitespace-pre-wrap">{{ incident.description }}</p>
            
            <!-- SLA Progress Bar -->
            <div v-if="incident.sla_deadline" class="mt-4 p-4 rounded-lg border" :class="slaContainerClass">
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm font-medium text-slate-700">SLA</span>
                <span 
                  class="text-sm font-medium"
                  :class="slaTextClass"
                >
                  {{ slaPercentageDisplay?.toFixed(1) }}%
                </span>
              </div>
              <div class="w-full h-3 bg-slate-200 rounded-full overflow-hidden">
                <div 
                  class="h-full rounded-full transition-all duration-300"
                  :class="slaProgressBarClass"
                  :style="{ width: slaProgressWidth + '%' }"
                ></div>
              </div>
              <div class="flex items-center justify-between mt-2 text-xs">
                <span class="text-slate-500">
                  Дедлайн: {{ formatDate(incident.sla_deadline) }}
                </span>
                <span 
                  v-if="!['Решён', 'Закрыт'].includes(incident.status_name)"
                  class="font-medium"
                  :class="slaTextClass"
                >
                  <template v-if="incident.sla_remaining">
                    {{ incident.sla_remaining.formatted }}
                  </template>
                </span>
                <span 
                  v-else
                  class="font-medium text-green-600"
                >
                  <template v-if="incident.resolved_at">
                    Решён за {{ incident.sla_percentage?.toFixed(1) }}% SLA
                  </template>
                  <template v-else-if="incident.closed_at">
                    Закрыт за {{ incident.sla_percentage?.toFixed(1) }}% SLA
                  </template>
                </span>
              </div>
            </div>
            
            <div class="mt-4 pt-4 border-t border-slate-200 grid grid-cols-2 gap-4 text-sm">
              <div>
                <span class="text-slate-500">Отдел:</span>
                <span class="ml-2 text-slate-700">{{ incident.department_name }}</span>
              </div>
              <div>
                <span class="text-slate-500">Категория:</span>
                <span class="ml-2 text-slate-700">{{ incident.category_name || 'Не указана' }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-slate-500">Инициатор:</span>
                <div class="flex items-center gap-2">
                  <div 
                    v-if="incident.initiator_avatar"
                    class="w-6 h-6 rounded-full bg-cover bg-center"
                    :style="{ backgroundImage: `url(${incident.initiator_avatar})` }"
                  ></div>
                  <div 
                    v-else
                    class="w-6 h-6 rounded-full bg-primary-500 flex items-center justify-center text-white text-xs font-medium"
                  >
                    {{ incident.initiator_name?.charAt(0)?.toUpperCase() || '?' }}
                  </div>
                  <span class="text-slate-700">{{ incident.initiator_name }}</span>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-slate-500">Исполнитель:</span>
                <div v-if="incident.executor_name" class="flex items-center gap-2">
                  <div 
                    v-if="incident.executor_avatar"
                    class="w-6 h-6 rounded-full bg-cover bg-center"
                    :style="{ backgroundImage: `url(${incident.executor_avatar})` }"
                  ></div>
                  <div 
                    v-else
                    class="w-6 h-6 rounded-full bg-primary-500 flex items-center justify-center text-white text-xs font-medium"
                  >
                    {{ incident.executor_name?.charAt(0)?.toUpperCase() || '?' }}
                  </div>
                  <span class="text-slate-700">{{ incident.executor_name }}</span>
                </div>
                <span v-else class="text-slate-400">Не назначен</span>
              </div>
              <div>
                <span class="text-slate-500">Дедлайн SLA:</span>
                <span :class="['ml-2', incident.overdue ? 'text-red-600 font-medium' : 'text-slate-700']">
                  {{ formatDate(incident.sla_deadline) }}
                </span>
              </div>
              <div>
                <span class="text-slate-500">Создан:</span>
                <span class="ml-2 text-slate-700">{{ formatDate(incident.created_at) }}</span>
              </div>
            </div>
          </div>
          
          <!-- Comments -->
          <div class="bg-white rounded-xl shadow-sm p-6 border border-slate-200">
            <h2 class="text-lg font-semibold text-slate-800 mb-4">Комментарии</h2>
            
            <div class="space-y-4 mb-6">
              <div
                v-for="comment in comments"
                :key="comment.id"
                class="p-4 rounded-lg bg-slate-50"
              >
                <div class="flex items-start justify-between mb-2">
                  <div class="flex items-center gap-2">
                    <div 
                      v-if="comment.author_avatar"
                      class="w-6 h-6 rounded-full bg-cover bg-center"
                      :style="{ backgroundImage: `url(${comment.author_avatar})` }"
                    ></div>
                    <div 
                      v-else
                      class="w-6 h-6 rounded-full bg-primary-500 flex items-center justify-center text-white text-xs font-medium"
                    >
                      {{ comment.author_name?.charAt(0)?.toUpperCase() || '?' }}
                    </div>
                    <span class="font-medium text-slate-700">{{ comment.author_name }}</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <span class="text-xs text-slate-500">{{ formatDate(comment.created_at) }}</span>
                    <!-- Edit button - only for creator -->
                    <button
                      v-if="canEditComment(comment)"
                      @click="editComment(comment)"
                      class="p-1 text-slate-500 hover:text-primary-600 rounded transition-colors"
                      title="Редактировать"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    <!-- Delete button - for creator or admin -->
                    <button
                      v-if="canDeleteComment(comment)"
                      @click="deleteComment(comment)"
                      class="p-1 text-slate-500 hover:text-red-600 rounded transition-colors"
                      title="Удалить"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
                <p class="text-slate-600 whitespace-pre-wrap">{{ comment.content }}</p>
              </div>
              
              <div v-if="!comments.length" class="text-center text-slate-500 py-4">
                Нет комментариев
              </div>
            </div>
            
            <!-- Add comment -->
            <div v-if="!isClosed" class="border-t border-slate-200 pt-4">
              <textarea
                v-model="newComment"
                rows="3"
                class="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent mb-2"
                placeholder="Добавить комментарий..."
              ></textarea>
              <div class="flex items-center justify-end">
                <button
                  @click="addComment"
                  :disabled="!newComment.trim() || commentLoading"
                  class="px-4 py-2 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 disabled:opacity-50"
                >
                  Отправить
                </button>
              </div>
            </div>
          </div>
          
          <!-- Attachments -->
          <div class="bg-white rounded-xl shadow-sm p-6 border border-slate-200">
            <div class="flex items-center justify-between mb-4">
              <h2 class="text-lg font-semibold text-slate-800">Вложения</h2>
              <div v-if="!isClosed">
                <input
                  ref="fileInput"
                  type="file"
                  class="hidden"
                  accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.txt,.log,.zip,.rar"
                  @change="handleFileUpload"
                />
                <button
                  @click="triggerFileUpload"
                  :disabled="uploadLoading"
                  class="px-4 py-2 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 disabled:opacity-50 text-sm"
                >
                  {{ uploadLoading ? 'Загрузка...' : '+ Прикрепить файл' }}
                </button>
              </div>
            </div>
            
            <div v-if="attachments.length" class="space-y-2">
              <div
                v-for="att in attachments"
                :key="att.id"
                class="flex items-center justify-between p-3 bg-slate-50 rounded-lg"
              >
                <div class="flex items-center gap-3">
                  <!-- Preview for images -->
                  <div v-if="att.mime_type?.startsWith('image/')" class="w-10 h-10 rounded-lg overflow-hidden bg-slate-200">
                    <img 
                      :src="`/api/attachments/${att.id}/download`" 
                      class="w-full h-full object-cover"
                      @error="$event.target.style.display='none'"
                    />
                  </div>
                  <div v-else class="w-10 h-10 rounded-lg bg-primary-100 flex items-center justify-center">
                    <svg class="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div>
                    <p class="text-sm font-medium text-slate-700">{{ att.filename }}</p>
                    <p class="text-xs text-slate-500">{{ formatFileSize(att.filesize) }}</p>
                  </div>
                </div>
                <div class="flex items-center gap-2">
                  <span class="text-xs text-slate-400 hidden sm:inline">{{ formatDate(att.created_at) }}</span>
                  <a
                    :href="`/api/attachments/${att.id}/download`"
                    :download="att.filename"
                    class="p-2 text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                    title="Скачать"
                  >
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                  </a>
                  <button
                    v-if="!isClosed && canDeleteAttachment(att)"
                    @click="deleteAttachment(att)"
                    class="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="Удалить"
                  >
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
            
            <div v-else class="text-center text-slate-500 py-4">
              Нет прикреплённых файлов
            </div>
          </div>
        </div>
        
        <!-- Sidebar -->
        <div class="space-y-6">
          <!-- Actions -->
          <div class="bg-white rounded-xl shadow-sm p-6 border border-slate-200">
            <h2 class="text-lg font-semibold text-slate-800 mb-4">Действия</h2>
            
            <div class="space-y-2">
              <button
                v-if="canEditAsInitiator"
                @click="openEditModal"
                class="w-full px-4 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700"
              >
                Редактировать инцидент
              </button>
              
              <button
                v-if="(authStore.user?.role_name === 'Admin' || authStore.user?.role_name === 'Manager') && !['Решён', 'Закрыт'].includes(incident?.status_name)"
                @click="openEditModal"
                class="w-full px-4 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700"
              >
                Изменить отдел
              </button>
              
              <button
                v-if="canTake"
                @click="takeIncident"
                class="w-full px-4 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700"
              >
                Взять в работу
              </button>
              
              <button
                v-if="canAssign"
                @click="showAssignModal = true"
                class="w-full px-4 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700"
              >
                {{ incident?.executor_id ? 'Переназначить исполнителя' : 'Назначить исполнителя' }}
              </button>
              
              <button
                v-if="canEdit"
                @click="showStatusModal = true"
                class="w-full px-4 py-3 bg-slate-600 text-white rounded-lg font-medium hover:bg-slate-700"
              >
                Изменить статус
              </button>
              
              <button
                v-if="authStore.isManager || authStore.isAdmin"
                @click="showPriorityModal = true"
                class="w-full px-4 py-3 bg-orange-600 text-white rounded-lg font-medium hover:bg-orange-700"
              >
                Изменить приоритет
              </button>
              
              <button
                v-if="canUpdateDeadline"
                @click="showDeadlineModal = true; newDeadline = incident?.sla_deadline ? new Date(incident.sla_deadline).toISOString().slice(0, 16) : ''"
                class="w-full px-4 py-3 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700"
              >
                Изменить дедлайн
              </button>
              
              <button
                v-if="canResolve"
                @click="resolveIncident"
                class="w-full px-4 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700"
              >
                Отметить решённым
              </button>
              
              <button
                v-if="canClose"
                @click="closeIncident"
                class="w-full px-4 py-3 bg-slate-800 text-white rounded-lg font-medium hover:bg-slate-900"
              >
                Закрыть инцидент
              </button>
              
              <button
                v-if="canDelete"
                @click="showDeleteModal = true"
                class="w-full px-4 py-3 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700"
              >
                Удалить инцидент
              </button>
            </div>
          </div>
          
          <!-- History -->
          <div v-if="authStore.isExecutor && history.length" class="bg-white rounded-xl shadow-sm p-6 border border-slate-200">
            <h2 class="text-lg font-semibold text-slate-800 mb-4">История</h2>
            
            <div class="space-y-3 text-sm">
              <div v-for="entry in history" :key="entry.id" class="border-l-2 border-slate-200 pl-3">
                <div class="text-slate-600">
                  <span v-if="entry.previous_status_name">{{ entry.previous_status_name }} → </span>
                  <span class="font-medium">{{ entry.new_status_name || 'Создан' }}</span>
                </div>
                <div v-if="entry.comment" class="text-slate-500">{{ entry.comment }}</div>
                <div class="text-xs text-slate-400">
                  {{ entry.user_name || 'Система' }} • {{ formatDate(entry.created_at) }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Assign Modal -->
      <div v-if="showAssignModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div class="bg-white rounded-xl p-6 w-full max-w-md">
          <h3 class="text-lg font-semibold mb-4">{{ incident?.executor_id ? 'Переназначить исполнителя' : 'Назначить исполнителя' }}</h3>
          <select v-model="selectedExecutor" class="w-full px-4 py-3 border border-slate-300 rounded-lg mb-4">
            <option :value="null" disabled>Выберите исполнителя</option>
            <option v-for="user in assignableUsers" :key="user.id" :value="user.id">{{ user.full_name }}</option>
          </select>
          <div class="flex gap-2">
            <button @click="assignExecutor" :disabled="!selectedExecutor" class="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg">
              Назначить
            </button>
            <button @click="showAssignModal = false" class="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg">
              Отмена
            </button>
          </div>
        </div>
      </div>
      
      <!-- Status Modal -->
      <div v-if="showStatusModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div class="bg-white rounded-xl p-6 w-full max-w-md">
          <h3 class="text-lg font-semibold mb-4">Изменить статус</h3>
          <select v-model="selectedStatus" class="w-full px-4 py-3 border border-slate-300 rounded-lg mb-4">
            <option :value="null" disabled>Выберите статус</option>
            <option v-for="status in statuses" :key="status.id" :value="status.id">{{ status.name }}</option>
          </select>
          <textarea
            v-model="actionComment"
            rows="2"
            class="w-full px-4 py-3 border border-slate-300 rounded-lg mb-4"
            placeholder="Комментарий (опционально)"
          ></textarea>
          <div class="flex gap-2">
            <button @click="changeStatus" :disabled="!selectedStatus" class="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg">
              Изменить
            </button>
            <button @click="showStatusModal = false" class="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg">
              Отмена
            </button>
          </div>
        </div>
      </div>
      
      <!-- Priority Modal -->
      <div v-if="showPriorityModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div class="bg-white rounded-xl p-6 w-full max-w-md">
          <h3 class="text-lg font-semibold mb-4">Изменить приоритет</h3>
          <p class="text-sm text-slate-500 mb-4">
            Текущий приоритет: <strong>{{ incident?.priority_name }}</strong>
          </p>
          <select v-model="selectedPriority" class="w-full px-4 py-3 border border-slate-300 rounded-lg mb-4">
            <option :value="null" disabled>Выберите приоритет</option>
            <option v-for="priority in priorities" :key="priority.id" :value="priority.id">
              {{ priority.name }}
            </option>
          </select>
          <p class="text-xs text-slate-500 mb-4">
            При изменении приоритета дедлайн SLA будет пересчитан автоматически.
          </p>
          <div class="flex gap-2">
            <button @click="changePriority" :disabled="!selectedPriority" class="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg">
              Изменить
            </button>
            <button @click="showPriorityModal = false" class="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg">
              Отмена
            </button>
          </div>
        </div>
      </div>
      
      <!-- Deadline Modal -->
      <div v-if="showDeadlineModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div class="bg-white rounded-xl p-6 w-full max-w-md">
          <h3 class="text-lg font-semibold mb-4">Изменить дедлайн SLA</h3>
          <p class="text-sm text-slate-500 mb-4">
            Текущий дедлайн: <strong>{{ formatDate(incident?.sla_deadline) }}</strong>
          </p>
          <label class="block text-sm font-medium text-slate-700 mb-2">Новый дедлайн</label>
          <input
            v-model="newDeadline"
            type="datetime-local"
            class="w-full px-4 py-3 border border-slate-300 rounded-lg mb-4"
          />
          <label class="block text-sm font-medium text-slate-700 mb-2">Причина изменения (опционально)</label>
          <input
            v-model="deadlineReason"
            type="text"
            class="w-full px-4 py-3 border border-slate-300 rounded-lg mb-4"
            placeholder="Например: Согласовано с заказчиком"
          />
          <!-- SLA Violation Confirmation -->
          <div class="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
            <label class="flex items-start gap-3 cursor-pointer">
              <input
                v-model="slaViolationConfirmed"
                type="checkbox"
                class="mt-1 w-4 h-4 text-amber-600 rounded border-amber-300"
              />
              <div>
                <span class="text-sm font-medium text-amber-800">Нарушение SLA подтверждено</span>
                <p class="text-xs text-amber-600 mt-1">
                  Отметьте, если просрочка была критичной и должна учитываться в статистике
                </p>
              </div>
            </label>
          </div>
          <div class="flex gap-2">
            <button @click="updateDeadline" :disabled="!newDeadline" class="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg">
              Изменить
            </button>
            <button @click="showDeadlineModal = false" class="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg">
              Отмена
            </button>
          </div>
        </div>
      </div>
      
      <!-- Delete Modal -->
      <div v-if="showDeleteModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div class="bg-white rounded-xl p-6 w-full max-w-md">
          <h3 class="text-lg font-semibold mb-4 text-red-600">Подтверждение удаления</h3>
          <p class="text-slate-600 mb-4">
            Вы уверены, что хотите удалить инцидент "<strong>{{ incident?.title }}</strong>"?
          </p>
          <p class="text-sm text-red-600 mb-6">
            Это действие нельзя отменить. Все комментарии, вложения и история будут удалены.
          </p>
          <div class="flex gap-3">
            <button 
              @click="showDeleteModal = false" 
              class="flex-1 px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200"
            >
              Отмена
            </button>
            <button 
              @click="deleteIncident" 
              :disabled="deleteLoading"
              class="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
            >
              {{ deleteLoading ? 'Удаление...' : 'Удалить' }}
            </button>
          </div>
        </div>
      </div>
      
      <!-- Comment Edit Modal -->
      <div v-if="showEditCommentModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div class="bg-white rounded-xl p-6 w-full max-w-md">
          <h3 class="text-lg font-semibold mb-4">Редактировать комментарий</h3>
          <textarea
            v-model="editCommentContent"
            rows="4"
            class="w-full px-4 py-3 border border-slate-300 rounded-lg mb-4 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            placeholder="Текст комментария..."
          ></textarea>
          <div class="flex gap-2">
            <button 
              @click="saveCommentEdit" 
              :disabled="!editCommentContent.trim() || editCommentLoading"
              class="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {{ editCommentLoading ? 'Сохранение...' : 'Сохранить' }}
            </button>
            <button 
              @click="showEditCommentModal = false" 
              class="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200"
            >
              Отмена
            </button>
          </div>
        </div>
      </div>
      
      <!-- Edit Incident Modal -->
      <div v-if="showEditModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div class="bg-white rounded-xl p-6 w-full max-w-lg">
          <h3 class="text-lg font-semibold mb-4">
            {{ canEditAsInitiator ? 'Редактировать инцидент' : 'Изменить отдел' }}
          </h3>
          
          <div class="space-y-4">
            <!-- Show title/description/category only for initiator editing new incident -->
            <div v-if="canEditAsInitiator">
              <label class="block text-sm font-medium text-slate-700 mb-1">Заголовок</label>
              <input
                v-model="editForm.title"
                type="text"
                class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                placeholder="Заголовок инцидента"
              />
            </div>
            
            <div v-if="canEditAsInitiator">
              <label class="block text-sm font-medium text-slate-700 mb-1">Описание</label>
              <textarea
                v-model="editForm.description"
                rows="4"
                class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                placeholder="Подробное описание проблемы..."
              ></textarea>
            </div>
            
            <div v-if="canEditAsInitiator">
              <label class="block text-sm font-medium text-slate-700 mb-1">Категория</label>
              <select
                v-model="editForm.category_id"
                class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              >
                <option :value="null">Не указана</option>
                <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
              </select>
            </div>
            
            <div v-if="canEditAsInitiator">
              <label class="block text-sm font-medium text-slate-700 mb-1">Приоритет</label>
              <select
                v-model="editForm.priority_id"
                class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              >
                <option v-for="pri in priorities" :key="pri.id" :value="pri.id">
                  {{ pri.name }}
                </option>
              </select>
              <p class="text-xs text-slate-500 mt-1">
                При изменении приоритета дедлайн SLA будет пересчитан автоматически
              </p>
            </div>
            
            <div v-if="canEditAsInitiator || authStore.user?.role_name === 'Admin' || authStore.user?.role_name === 'Manager'">
              <label class="block text-sm font-medium text-slate-700 mb-1">Отдел</label>
              <select
                v-model="editForm.department_id"
                class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              >
                <option v-for="dept in departments" :key="dept.id" :value="dept.id">{{ dept.name }}</option>
              </select>
              <p v-if="canEditAsInitiator" class="text-xs text-amber-600 mt-1">
                ⚠️ При смене отдела исполнитель будет сброшен
              </p>
              <p v-if="authStore.user?.role_name === 'Admin' || authStore.user?.role_name === 'Manager'" class="text-xs text-amber-600 mt-1">
                ⚠️ При смене отдела исполнитель из другого отдела будет сброшен
              </p>
            </div>
          </div>
          
          <div class="flex gap-2 mt-6">
            <button 
              @click="saveEdit" 
              :disabled="editLoading"
              class="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {{ editLoading ? 'Сохранение...' : 'Сохранить' }}
            </button>
            <button 
              @click="showEditModal = false" 
              class="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200"
            >
              Отмена
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>