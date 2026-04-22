import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
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
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { requiresManager: true }
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
        meta: { requiresAdmin: true }
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

// Navigation guards
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  
  // Wait for auth initialization if not done yet
  if (!authStore.initialized) {
    await authStore.init()
  }
  
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