<script setup lang="ts">
import { onMounted, ref } from 'vue'
import Card from '../components/shared/Card.vue'
import Badge from '../components/shared/Badge.vue'
import Spinner from '../components/shared/Spinner.vue'
import { useServicesStore } from '../stores/services'
import { useToastStore } from '../stores/toast'
import { runUpdate } from '../api/agent'
import { Download, AlertTriangle } from 'lucide-vue-next'

const svc = useServicesStore()
const toasts = useToastStore()
const busy = ref<string | null>(null)
const lastLog = ref<string>('')

onMounted(() => { if (!svc.status) svc.refresh() })

async function update(service = 'all') {
  busy.value = service
  lastLog.value = ''
  try {
    const r: any = await runUpdate(service)
    lastLog.value = r?.log || 'ok'
    toasts.success(`Update fertig: ${service}`)
    await svc.refresh()
  } catch (err: any) {
    toasts.error(err?.response?.data?.detail || err?.message || 'Update fehlgeschlagen')
  } finally {
    busy.value = null
  }
}
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <Card title="One-Click-Update" subtitle="docker compose pull && up -d">
      <div class="rounded-md bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 p-3 text-xs text-amber-800 dark:text-amber-200 mb-4 flex items-start gap-2">
        <AlertTriangle :size="14" class="shrink-0 mt-0.5" />
        <p>Achtung: Updates ziehen neue Images vom GHCR. Bei breaking changes kann der Service danach offline sein.</p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div
          v-for="s in svc.services"
          :key="s.name"
          class="flex items-center justify-between gap-2 px-3 py-2 rounded-md border border-slate-200/70 dark:border-slate-800/70 bg-white/40 dark:bg-slate-900/40"
        >
          <div class="min-w-0">
            <p class="font-medium text-sm text-slate-900 dark:text-slate-100 truncate">{{ s.name }}</p>
            <p class="text-[11px] text-slate-400">v{{ s.version || '—' }} · digest {{ s.image_digest || '—' }}</p>
            <Badge :variant="s.status === 'ok' ? 'green' : 'red'" dot class="mt-1">{{ s.status }}</Badge>
          </div>
          <button
            class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
            :disabled="busy === s.name || busy === 'all'"
            @click="update(s.compose_service || s.name)"
          >
            <Spinner v-if="busy === (s.compose_service || s.name)" :size="14" />
            <Download v-else :size="14" />
            Update
          </button>
        </div>
      </div>

      <div class="mt-4 pt-4 border-t border-slate-200/70 dark:border-slate-800/70">
        <button
          class="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-slate-700 text-white text-sm font-semibold hover:bg-slate-800 disabled:opacity-50"
          :disabled="!!busy"
          @click="update('all')"
        >
          <Spinner v-if="busy === 'all'" :size="14" />
          <Download v-else :size="14" />
          Alle Services aktualisieren
        </button>
      </div>
    </Card>

    <Card v-if="lastLog" title="Letzte Update-Ausgabe">
      <pre class="text-xs font-mono whitespace-pre-wrap bg-slate-950 text-slate-200 p-3 rounded-md max-h-72 overflow-auto">{{ lastLog }}</pre>
    </Card>
  </div>
</template>
