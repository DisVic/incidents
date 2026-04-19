import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Маршруты приложения
// Маршруты приложения
const routes = [
  // Публичные маршруты (доступны без авторизации)
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { guest: true } // Только для неавторизованных
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
  // Основной layout с проверкой авторизации
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true }, // Требует авторизации для всех вложенных маршрутов
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { requiresManager: true } // Только для менеджеров
      },
      {
        path: 'incidents',
        name: 'Incidents',
        component: () => import('@/views/Incidents.vue')
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
        meta: { requiresAdmin: true } // Только для админов
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/Settings.vue'),
        meta: { requiresAdmin: true }
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
  // Страница 404 — ловит все неизвестные маршруты
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue')
  }
]

// Создание роутера
const router = createRouter({
  history: createWebHistory(), // HTML5 History API для чистых URL
  routes
})

// Глобальный guard для проверки прав доступа перед переходом
// Глобальная защита маршрутов
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  
  // Ждём инициализации авторизации перед проверкой прав
  if (!authStore.initialized) {
    await authStore.init()
  }
  
  // Перенаправляем на логин, если требуется авторизация
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (to.meta.guest && authStore.isAuthenticated) {
    // Авторизованных пользователей не пускаем на страницы логина
    next({ name: 'Incidents' })
  } else if (to.meta.requiresAdmin && !authStore.isAdmin) {
    // Ограничиваем доступ к админским страницам
    next({ name: 'Incidents' })
  } else if (to.meta.requiresManager && !authStore.isManager) {
    // Ограничиваем доступ к страницам менеджеров
    next({ name: 'Incidents' })
  } else {
    next()
  }
})

export default router
