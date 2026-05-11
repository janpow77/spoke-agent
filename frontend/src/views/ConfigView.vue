<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import Card from '../components/shared/Card.vue'
import Spinner from '../components/shared/Spinner.vue'
import { useRouterStore } from '../stores/router-store'
import { useServicesStore } from '../stores/services'
import { useToastStore } from '../stores/toast'
import { Save } from 'lucide-vue-next'

const routerStore = useRouterStore()
const services = useServicesStore()
const toasts = useToastStore()

const url = ref('')
const fallback = ref('')
const apiKey = ref('')
const registrationToken = ref('')
const tagsInput = ref('')
const saving = ref(false)

onMounted(async () => {
  await routerStore.refresh()
  if (!services.status) await services.refresh()
  if (routerStore.status) {
    url.value = routerStore.status.url || ''
    fallback.value = routerStore.status.fallback_url || ''
  }
  if (services.status) {
    tagsInput.value = services.status.spoke_tags.join(', ')
  }
})

watch(() => routerStore.status, (s) => {
  if (s) {
    url.value = s.url || ''
    fallback.value = s.fallback_url || ''
  }
})

async function save() {
  saving.value = true
  try {
    const payload: any = {
      url: url.value || undefined,
      fallback_url: fallback.value,
      spoke_tags: tagsInput.value.split(',').map(t => t.trim()).filter(Boolean),
    }
    if (apiKey.value) payload.api_key = apiKey.value
    if (registrationToken.value) payload.registration_token = registrationToken.value
    await routerStore.save(payload)
    toasts.success('Gespeichert. Naechster Heartbeat verwendet neue Konfig.')
    apiKey.value = ''
    registrationToken.value = ''
    await services.refresh()
  } catch (err: any) {
    toasts.error(err?.response?.data?.detail || err?.message || 'Speichern fehlgeschlagen')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <Card title="Router-Verbindung" subtitle="Wohin schickt dieser Spoke seine Heartbeats?">
      <div v-if="routerStore.loading && !routerStore.status"><Spinner /></div>
      <form v-else class="space-y-4" @submit.prevent="save">
        <div>
          <label class="text-xs font-medium text-slate-600 dark:text-slate-400">Router-URL</label>
          <input v-model="url" type="url" class="mt-1 w-full px-3 py-1.5 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
        <div>
          <label class="text-xs font-medium text-slate-600 dark:text-slate-400">Fallback-Router-URL (optional)</label>
          <input v-model="fallback" type="url" class="mt-1 w-full px-3 py-1.5 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
        <div>
          <label class="text-xs font-medium text-slate-600 dark:text-slate-400">API-Key (Bearer fuer Router-Calls)</label>
          <input v-model="apiKey" type="password" placeholder="leer = nicht aendern" class="mt-1 w-full px-3 py-1.5 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          <p class="text-xs text-slate-400 mt-1">Wird im OS-Keychain (falls verfuegbar) oder verschluesselt in /data persistiert.</p>
        </div>
        <div>
          <label class="text-xs font-medium text-slate-600 dark:text-slate-400">Registration-Token (X-Spoke-Token)</label>
          <input v-model="registrationToken" type="password" placeholder="leer = nicht aendern" class="mt-1 w-full px-3 py-1.5 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
        <div>
          <label class="text-xs font-medium text-slate-600 dark:text-slate-400">Spoke-Tags (komma-getrennt)</label>
          <input v-model="tagsInput" class="mt-1 w-full px-3 py-1.5 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="gpu, linux, rtx5070ti" />
        </div>

        <button
          type="submit"
          :disabled="saving"
          class="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50"
        >
          <Spinner v-if="saving" :size="14" />
          <Save v-else :size="14" />
          Speichern
        </button>
      </form>
    </Card>

    <Card v-if="routerStore.status" title="Aktueller Status">
      <dl class="grid grid-cols-2 gap-y-2 gap-x-6 text-sm">
        <dt class="text-slate-500">Verbindung</dt>
        <dd>{{ routerStore.status.connected ? 'Online' : 'Offline' }}</dd>
        <dt class="text-slate-500">Fallback aktiv</dt>
        <dd>{{ routerStore.status.using_fallback ? 'Ja' : 'Nein' }}</dd>
        <dt class="text-slate-500">Failures in Folge</dt>
        <dd>{{ routerStore.status.consecutive_failures }}</dd>
        <dt class="text-slate-500">Letzter Register</dt>
        <dd>{{ routerStore.status.last_register_at || '—' }}</dd>
        <dt class="text-slate-500">Letzter Fehler</dt>
        <dd class="text-red-500 break-all">{{ routerStore.status.last_error || '—' }}</dd>
      </dl>
    </Card>
  </div>
</template>
