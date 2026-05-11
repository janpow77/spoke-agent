<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Play, Square, RotateCcw, Settings2, FileText } from 'lucide-vue-next'
import Card from '../components/shared/Card.vue'
import Badge from '../components/shared/Badge.vue'
import Spinner from '../components/shared/Spinner.vue'
import Modal from '../components/shared/Modal.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import { useServicesStore } from '../stores/services'
import { useToastStore } from '../stores/toast'
import { usePollStore } from '../stores/poll'
import {
  restartService,
  startService,
  stopService,
  getLogs,
  getServiceConfig,
  setServiceConfig,
} from '../api/agent'
import type { ServiceConfigResponse, ServiceInfo } from '../api/types'
import { statusVariant, relativeTime } from '../utils/format'

const svc = useServicesStore()
const toasts = useToastStore()
const poll = usePollStore()

onMounted(() => poll.start('services', () => svc.refresh(), 10_000))
onBeforeUnmount(() => poll.stop('services'))

const busy = ref<string | null>(null)
const logsOpen = ref(false)
const logsService = ref('')
const logLines = ref<string[]>([])
const configOpen = ref(false)
const configService = ref('')
const configData = ref<ServiceConfigResponse | null>(null)
const configEdits = ref<Record<string, string>>({})

async function doAction(name: string, action: 'restart' | 'stop' | 'start') {
  busy.value = `${name}:${action}`
  try {
    if (action === 'restart') await restartService(name)
    if (action === 'stop') await stopService(name)
    if (action === 'start') await startService(name)
    toasts.success(`${action} ok: ${name}`)
    await svc.refresh()
  } catch (err: any) {
    toasts.error(err?.response?.data?.detail || err?.message || 'Fehler')
  } finally {
    busy.value = null
  }
}

async function openLogs(s: ServiceInfo) {
  logsService.value = s.name
  logsOpen.value = true
  try {
    const r = await getLogs(s.name, 200)
    logLines.value = r.lines
  } catch (err: any) {
    logLines.value = [`<error: ${err?.message || err}>`]
  }
}

async function openConfig(s: ServiceInfo) {
  configService.value = s.name
  configOpen.value = true
  configData.value = null
  try {
    const r = await getServiceConfig(s.name)
    configData.value = r
    configEdits.value = { ...r.env }
    for (const k of r.editable_keys) {
      if (!(k in configEdits.value)) configEdits.value[k] = ''
    }
  } catch (err: any) {
    toasts.error(err?.message || 'config load failed')
  }
}

async function saveConfig() {
  if (!configData.value) return
  busy.value = `${configService.value}:config`
  try {
    await setServiceConfig(configService.value, configEdits.value)
    toasts.success(`Config gespeichert: ${configService.value}`)
    configOpen.value = false
    await svc.refresh()
  } catch (err: any) {
    toasts.error(err?.response?.data?.detail || err?.message || 'config save failed')
  } finally {
    busy.value = null
  }
}
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <Card title="Services" subtitle="Lokal entdeckte ML-Services">
      <template #actions>
        <button class="text-xs underline text-slate-500 hover:text-indigo-600" @click="svc.forceDiscovery()">
          Neu scannen
        </button>
      </template>

      <div v-if="svc.loading && !svc.services.length" class="flex items-center gap-2 text-slate-500"><Spinner /> Lade...</div>
      <EmptyState v-else-if="!svc.services.length" title="Keine Services" message="Es laufen keine bekannten Services." />

      <div v-else class="overflow-x-auto -mx-5 px-5">
        <table class="w-full text-sm border-separate border-spacing-y-1">
          <thead>
            <tr class="text-left text-xs uppercase tracking-wider text-slate-500">
              <th class="px-3 py-2">Service</th>
              <th class="px-3 py-2">Status</th>
              <th class="px-3 py-2">Caps</th>
              <th class="px-3 py-2">Version</th>
              <th class="px-3 py-2">Last Check</th>
              <th class="px-3 py-2 text-right">Aktionen</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in svc.services" :key="s.name" class="bg-white/60 dark:bg-slate-900/40">
              <td class="px-3 py-2">
                <p class="font-medium text-slate-900 dark:text-slate-100">{{ s.name }}</p>
                <p class="text-xs text-slate-400">{{ s.base_url }}</p>
              </td>
              <td class="px-3 py-2"><Badge :variant="statusVariant(s.status) as any" dot>{{ s.status }}</Badge></td>
              <td class="px-3 py-2 text-xs text-slate-500">{{ s.capabilities.join(', ') || '—' }}</td>
              <td class="px-3 py-2 text-xs text-slate-500">{{ s.version || '—' }}</td>
              <td class="px-3 py-2 text-xs text-slate-500">{{ relativeTime(s.last_check_at) }}</td>
              <td class="px-3 py-2">
                <div class="flex items-center gap-1 justify-end">
                  <button class="p-1.5 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800" :disabled="!!busy" title="Start" @click="doAction(s.name, 'start')"><Play :size="14" /></button>
                  <button class="p-1.5 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800" :disabled="!!busy" title="Stop" @click="doAction(s.name, 'stop')"><Square :size="14" /></button>
                  <button class="p-1.5 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800" :disabled="!!busy" title="Restart" @click="doAction(s.name, 'restart')"><RotateCcw :size="14" /></button>
                  <button class="p-1.5 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800" title="Logs" @click="openLogs(s)"><FileText :size="14" /></button>
                  <button class="p-1.5 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800" title="Konfig" @click="openConfig(s)"><Settings2 :size="14" /></button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>

    <Modal :open="logsOpen" :title="`Logs · ${logsService}`" width="48rem" @close="logsOpen = false">
      <pre class="text-xs font-mono whitespace-pre-wrap bg-slate-950 text-slate-200 p-3 rounded-md max-h-96 overflow-auto">{{ logLines.join('\n') }}</pre>
    </Modal>

    <Modal :open="configOpen" :title="`Konfig · ${configService}`" width="36rem" @close="configOpen = false">
      <div v-if="!configData"><Spinner /></div>
      <div v-else class="space-y-3">
        <div v-if="!configData.editable_keys.length" class="text-sm text-slate-500">Keine editierbaren ENVs fuer diesen Service.</div>
        <div v-for="k in configData.editable_keys" :key="k" class="block">
          <label class="text-xs font-medium text-slate-600 dark:text-slate-400">{{ k }}</label>
          <input
            v-model="configEdits[k]"
            class="mt-1 w-full px-3 py-1.5 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <p class="text-xs text-slate-500">Beim Speichern wird der Service automatisch neu gestartet (compose up -d).</p>
      </div>
      <template #footer>
        <button class="text-sm px-3 py-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800" @click="configOpen = false">Abbrechen</button>
        <button
          class="text-sm px-3 py-1.5 rounded-md bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
          :disabled="!configData || !!busy"
          @click="saveConfig"
        >
          Speichern
        </button>
      </template>
    </Modal>
  </div>
</template>
