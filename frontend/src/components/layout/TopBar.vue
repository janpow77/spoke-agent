<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useThemeStore } from '../../stores/theme'
import { useAuthStore } from '../../stores/auth'
import { useRouter } from 'vue-router'
import { useServicesStore } from '../../stores/services'
import { Sun, Moon, LogOut, Activity } from 'lucide-vue-next'
import Badge from '../shared/Badge.vue'

const theme = useThemeStore()
const auth = useAuthStore()
const router = useRouter()
const svc = useServicesStore()

onMounted(async () => {
  if (!svc.status) await svc.refresh()
})

const routerOk = computed(() => svc.status?.router.connected ?? false)
const usingFallback = computed(() => svc.status?.router.using_fallback ?? false)

async function doLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <header
    class="sticky top-0 z-30 flex items-center justify-between gap-4 px-6 py-3 border-b border-slate-200/70 dark:border-slate-800/70 backdrop-blur-md"
    style="background: var(--sidebar-bg)"
  >
    <div class="flex items-center gap-3">
      <div class="md:hidden grid place-items-center h-9 w-9 rounded-lg bg-indigo-600 text-white">
        <Activity :size="16" />
      </div>
      <div>
        <h1 class="text-sm font-semibold text-slate-900 dark:text-slate-100 capitalize">
          {{ String($route.name || 'Spoke-Agent') }}
        </h1>
        <p v-if="svc.status" class="text-xs text-slate-500 dark:text-slate-400 leading-tight">
          {{ svc.status.spoke_name }} · uptime {{ Math.floor((svc.status.uptime_s || 0) / 60) }} min
        </p>
      </div>
    </div>

    <div class="flex items-center gap-2">
      <Badge v-if="usingFallback" variant="amber" dot>Fallback-Router</Badge>
      <Badge :variant="routerOk ? 'green' : 'red'" dot>{{ routerOk ? 'Router OK' : 'Router offline' }}</Badge>

      <button
        class="grid place-items-center h-9 w-9 rounded-md text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
        :title="theme.theme === 'dark' ? 'Light Mode' : 'Dark Mode'"
        @click="theme.toggle"
      >
        <Sun v-if="theme.theme === 'dark'" :size="16" />
        <Moon v-else :size="16" />
      </button>

      <button
        v-if="auth.token"
        class="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
        title="Abmelden"
        @click="doLogout"
      >
        <LogOut :size="14" />
        <span class="hidden sm:inline">Abmelden</span>
      </button>
    </div>
  </header>
</template>
