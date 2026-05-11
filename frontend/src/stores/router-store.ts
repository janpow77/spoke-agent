import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '../api/agent'
import type { RouterStatus } from '../api/types'

export const useRouterStore = defineStore('routerStore', () => {
  const status = ref<RouterStatus | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function refresh() {
    try {
      loading.value = true
      status.value = await api.getRouter()
      error.value = null
    } catch (err: any) {
      error.value = err?.message || String(err)
    } finally {
      loading.value = false
    }
  }

  async function save(payload: Parameters<typeof api.setRouter>[0]) {
    status.value = await api.setRouter(payload)
  }

  return { status, loading, error, refresh, save }
})
