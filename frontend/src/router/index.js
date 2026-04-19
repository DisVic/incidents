/**
 * Vue Router — маршрутизация приложения.
 * 
 * Маршруты разделены на:
 * - Публичные (guest: true) — Login, ForgotPassword, ResetPassword
 * - Защищённые (requiresAuth: true) — все основные страницы
 * - С ограничениями по ролям (requiresAdmin, requiresManager)
 * 
 * Навигационный хук beforeEach проверяет:
 * 1. Инициализацию auth store
 * 2. Авторизацию для защищённых маршрутов
 * 3. Права доступа для админских/менеджерских страниц
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  // === Публичные страницы (без авторизации) ===
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { guest: true }
  },
  {
    path: '/forgot-password',
    name: 'ForgotPassword',
    component: () => import('@/views/ForgotPassword.vue'),
    meta: { guest: true }
  },
  {
    path: '/reset-password',
    name: 'ResetPassword',
    component: () => import('@/views/ResetPassword.vue'),
    meta: { guest: true }
  },
  
  // === Защищённые страницы (требуют авторизацию) ===
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { requiresManager: true }  // Только Manager и Admin (статистика)
      },
      {
        path: 'incidents',
        name: 'Incidents',
        component: () => import('@/views/Incidents.vue')  // Все роли
      },
      {
        path: 'incidents/:id',
        name: 'IncidentDetail',
        component: () => import('@/views/IncidentDetail.vue')
      },
      {
        path: 'incidents/create',
        name: 'IncidentCreate',
        component: () => import('@/views/IncidentForm.vue')
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/Users.vue'),
        meta: { requiresAdmin: true }  // Только Admin
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/Settings.vue'),
        meta: { requiresAdmin: true }  // Только Admin
      },

      {
        path: 'notifications',
        name: 'Notifications',
        component: () => import('@/views/Notifications.vue')
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/Profile.vue')
      },
      {
        path: 'users/:id/stats',
        name: 'UserStats',
        component: () => import('@/views/UserStats.vue'),
        meta: { requiresManager: true }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

/**
 * Навигационный хук — проверка прав доступа перед переходом.
 * 
 * @param {Object} to - Целевой маршрут
 * @param {Object} from - Исходный маршрут
 * @param {Function} next - Функция продолжения навигации
 */
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  
  // Ждём инициализации auth (проверка токена в localStorage)
  if (!authStore.initialized) {
    await authStore.init()
  }
  
  // Редирект на логин если не авторизован
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (to.meta.guest && authStore.isAuthenticated) {
    next({ name: 'Incidents' })
  } else if (to.meta.requiresAdmin && !authStore.isAdmin) {
    next({ name: 'Incidents' })
  } else if (to.meta.requiresManager && !authStore.isManager) {
    next({ name: 'Incidents' })
  } else {
    next()
  }
})

export default router
