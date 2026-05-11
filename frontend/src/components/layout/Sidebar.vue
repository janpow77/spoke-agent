<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { LayoutDashboard, Server, RefreshCcw, Settings2, FileText, Cable } from 'lucide-vue-next'

const items = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/services', label: 'Services', icon: Server },
  { to: '/update', label: 'Update', icon: RefreshCcw },
  { to: '/config', label: 'Konfiguration', icon: Settings2 },
  { to: '/logs', label: 'Logs', icon: FileText },
]
</script>

<template>
  <aside
    class="hidden md:flex w-[240px] shrink-0 flex-col border-r border-slate-200/70 dark:border-slate-800/70"
    style="background: var(--sidebar-bg)"
  >
    <div class="px-5 pt-5 pb-4 border-b border-slate-200/70 dark:border-slate-800/70">
      <RouterLink to="/" class="flex items-center gap-2.5">
        <div class="grid place-items-center h-9 w-9 rounded-lg bg-indigo-600 text-white shadow-sm">
          <Cable :size="18" />
        </div>
        <div>
          <p class="font-semibold tracking-tight text-slate-900 dark:text-slate-100 leading-none">Spoke-Agent</p>
          <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Host-Admin</p>
        </div>
      </RouterLink>
    </div>

    <nav class="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
      <RouterLink
        v-for="item in items"
        :key="item.to"
        :to="item.to"
        :exact-active-class="item.exact ? 'bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300' : ''"
        active-class="bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300"
        class="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-colors"
      >
        <component :is="item.icon" :size="16" />
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>

    <div class="px-5 py-3 border-t border-slate-200/70 dark:border-slate-800/70 text-xs text-slate-500 dark:text-slate-500">
      <p>v0.1.0</p>
    </div>
  </aside>
</template>
