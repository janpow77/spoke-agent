<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { Cpu, Server, Cable, AlertTriangle } from 'lucide-vue-next'
import Card from '../components/shared/Card.vue'
import Badge from '../components/shared/Badge.vue'
import Spinner from '../components/shared/Spinner.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import { useServicesStore } from '../stores/services'
import { usePollStore } from '../stores/poll'
import { formatVram, formatUptime, relativeTime, statusVariant } from '../utils/format'

const svc = useServicesStore()
const poll = usePollStore()

onMounted(() => {
  poll.start('dashboard', () => svc.refresh(), 10_000)
})
onBeforeUnmount(() => poll.stop('dashboard'))

const gpu = computed(() => svc.status?.discovery.gpu)
const host = computed(() => svc.status?.discovery.host_info)
const router = computed(() => svc.status?.router)
const services = computed(() => svc.services)

const healthyCount = computed(() => services.value.filter(s => s.status === 'ok').length)
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <div v-if="svc.loading && !svc.status" class="flex items-center gap-2 text-slate-500"><Spinner /> Lade Status...</div>
    <div v-else-if="svc.error" class="rounded-md border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/30 p-4 text-red-800 dark:text-red-200 text-sm">
      <p class="font-semibold flex items-center gap-2"><AlertTriangle :size="16" /> Fehler</p>
      <p class="mt-1">{{ svc.error }}</p>
      <button class="mt-2 text-xs underline" @click="svc.refresh()">Neu laden</button>
    </div>

    <template v-if="svc.status">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <div class="flex items-start justify-between">
            <div>
              <p class="text-xs font-semibold uppercase tracking-wider text-slate-500">Router-Verbindung</p>
              <p class="mt-2 text-xl font-bold text-slate-900 dark:text-slate-100">
                {{ router?.connected ? 'Online' : 'Offline' }}
              </p>
              <p class="text-xs text-slate-400 mt-1 break-all">{{ router?.url }}</p>
              <p v-if="router?.using_fallback" class="text-xs text-amber-600 mt-1">Fallback aktiv</p>
              <p v-if="router?.last_error" class="text-xs text-red-500 mt-1">{{ router.last_error }}</p>
            </div>
            <div class="grid place-items-center h-9 w-9 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
              <Cable :size="16" />
            </div>
          </div>
        </Card>

        <Card>
          <div class="flex items-start justify-between">
            <div>
              <p class="text-xs font-semibold uppercase tracking-wider text-slate-500">Host</p>
              <p class="mt-2 text-xl font-bold text-slate-900 dark:text-slate-100">{{ svc.status.spoke_name }}</p>
              <p class="text-xs text-slate-400 mt-1">{{ host?.platform }} · {{ host?.arch }}</p>
              <p class="text-xs text-slate-400 mt-0.5">Uptime: {{ formatUptime(svc.status.uptime_s) }}</p>
            </div>
            <div class="grid place-items-center h-9 w-9 rounded-lg bg-green-500/10 text-green-600 dark:text-green-400">
              <Server :size="16" />
            </div>
          </div>
        </Card>

        <Card>
          <div class="flex items-start justify-between">
            <div>
              <p class="text-xs font-semibold uppercase tracking-wider text-slate-500">GPU</p>
              <p v-if="gpu" class="mt-2 text-xl font-bold text-slate-900 dark:text-slate-100 truncate" :title="gpu.device || ''">{{ gpu.device || '—' }}</p>
              <p v-else class="mt-2 text-xl font-bold text-slate-400">CPU-only</p>
              <p v-if="gpu?.vram_total_mb" class="text-xs text-slate-400 mt-1">
                VRAM {{ formatVram(gpu.vram_used_mb) }} / {{ formatVram(gpu.vram_total_mb) }}
                <span v-if="gpu.util_pct !== null && gpu.util_pct !== undefined">· {{ gpu.util_pct }} %</span>
              </p>
            </div>
            <div class="grid place-items-center h-9 w-9 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400">
              <Cpu :size="16" />
            </div>
          </div>
        </Card>
      </div>

      <Card :title="`Services (${healthyCount}/${services.length})`" subtitle="Lokal entdeckt">
        <template #actions>
          <button class="text-xs underline text-slate-500 hover:text-indigo-600" @click="svc.forceDiscovery()">Neu scannen</button>
        </template>
        <div v-if="!services.length" class="py-6">
          <EmptyState title="Keine Services" message="Keine ML-Services auf den Standard-Ports gefunden." />
        </div>
        <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div
            v-for="s in services"
            :key="s.name"
            class="flex items-center justify-between gap-2 px-3 py-2 rounded-md border border-slate-200/70 dark:border-slate-800/70 bg-white/40 dark:bg-slate-900/40"
          >
            <div class="min-w-0">
              <p class="font-medium text-sm text-slate-900 dark:text-slate-100 truncate">{{ s.name }}</p>
              <p class="text-[11px] text-slate-400 truncate">{{ s.base_url }} · {{ s.capabilities.join(', ') || '—' }}</p>
              <p v-if="s.version" class="text-[11px] text-slate-400">v{{ s.version }}</p>
              <p v-if="s.last_check_at" class="text-[11px] text-slate-400">{{ relativeTime(s.last_check_at) }}</p>
            </div>
            <Badge :variant="statusVariant(s.status) as any" dot>{{ s.status }}</Badge>
          </div>
        </div>
      </Card>

      <Card v-if="svc.status.discovery.capabilities.length" title="Capabilities" subtitle="Vom Router angebotene Workloads">
        <div class="flex flex-wrap gap-2">
          <Badge v-for="c in svc.status.discovery.capabilities" :key="c" variant="indigo">{{ c }}</Badge>
        </div>
      </Card>
    </template>
  </div>
</template>
