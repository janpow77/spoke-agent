<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import Card from '../components/shared/Card.vue'
import { useServicesStore } from '../stores/services'
import { getToken } from '../api/client'

const services = useServicesStore()
const lines = ref<{ service: string; line: string }[]>([])
const ws = ref<WebSocket | null>(null)
const filter = ref<string>('')
const wsState = ref<'connecting' | 'open' | 'closed' | 'error'>('connecting')

onMounted(async () => {
  if (!services.status) await services.refresh()
  connect()
})

onBeforeUnmount(() => {
  try { ws.value?.close() } catch { /* ignore */ }
})

function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const token = getToken()
  let url = `${proto}://${location.host}/api/logs/stream`
  if (token) url += `?token=${encodeURIComponent(token)}`
  if (filter.value) url += `${token ? '&' : '?'}service=${encodeURIComponent(filter.value)}`

  wsState.value = 'connecting'
  const sock = new WebSocket(url)
  sock.onopen = () => { wsState.value = 'open' }
  sock.onclose = () => { wsState.value = 'closed' }
  sock.onerror = () => { wsState.value = 'error' }
  sock.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data)
      lines.value.push(msg)
      if (lines.value.length > 2000) lines.value.splice(0, lines.value.length - 2000)
    } catch { /* ignore */ }
  }
  ws.value = sock
}

function reconnect() {
  try { ws.value?.close() } catch { /* ignore */ }
  lines.value = []
  connect()
}

const serviceClass: Record<string, string> = {}
function colorFor(name: string): string {
  if (!serviceClass[name]) {
    const palette = ['text-indigo-400', 'text-green-400', 'text-amber-400', 'text-cyan-400', 'text-rose-400']
    serviceClass[name] = palette[Object.keys(serviceClass).length % palette.length]
  }
  return serviceClass[name]
}
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <Card title="Live-Logs" :subtitle="`WebSocket-Stream (${wsState})`">
      <template #actions>
        <select v-model="filter" class="text-xs px-2 py-1 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900" @change="reconnect">
          <option value="">Alle Services</option>
          <option v-for="s in services.services" :key="s.name" :value="s.compose_service || s.name">
            {{ s.name }}
          </option>
        </select>
        <button class="text-xs underline text-slate-500 hover:text-indigo-600" @click="reconnect">Reconnect</button>
      </template>

      <pre class="text-xs font-mono bg-slate-950 text-slate-200 p-3 rounded-md max-h-[60vh] overflow-auto leading-relaxed">
<template v-for="(l, idx) in lines" :key="idx"><span :class="colorFor(l.service)">[{{ l.service }}]</span> {{ l.line }}
</template>
      </pre>
    </Card>
  </div>
</template>
