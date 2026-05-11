import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('../components/layout/AppShell.vue'),
    children: [
      { path: '', name: 'dashboard', component: () => import('../views/DashboardView.vue') },
      { path: 'services', name: 'services', component: () => import('../views/ServicesView.vue') },
      { path: 'update', name: 'update', component: () => import('../views/UpdateView.vue') },
      { path: 'config', name: 'config', component: () => import('../views/ConfigView.vue') },
      { path: 'logs', name: 'logs', component: () => import('../views/LogsView.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory('/admin/'),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  auth.hydrate()
  // Wenn Auth ausgeschaltet ist (Tailscale-only), liefert /api/auth/me logged_in=true
  // ohne Token. In dem Fall: keinen Login-Redirect erzwingen.
  if (!to.meta.public && !auth.isAuthenticated) {
    const trusted = await auth.checkTrusted()
    if (!trusted) {
      return { name: 'login', query: { next: to.fullPath } }
    }
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
})

export default router
