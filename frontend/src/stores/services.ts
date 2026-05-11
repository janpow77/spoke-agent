import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '../api/agent'
import type { AgentStatus, ServiceInfo } from '../api/types'

export const useServicesStore = defineStore('services', () => {
  const status = ref<AgentStatus | null>(null)
  const services = ref<ServiceInfo[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastRefresh = ref<number>(0)

  async function refresh() {
    try {
      loading.value = true
      const s = await api.getStatus()
      status.value = s
      services.value = s.discovery.services
      lastRefresh.value = Date.now()
      error.value = null
    } catch (err: any) {
      error.value = err?.message || String(err)
    } finally {
      loading.value = false
    }
  }

  async function forceDiscovery() {
    await api.refreshServices()
    await refresh()
  }

  return { status, services, loading, error, lastRefresh, refresh, forceDiscovery }
})
