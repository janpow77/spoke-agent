// Polling-Store fuer Auto-Refresh (10 s default).
import { defineStore } from 'pinia'
import { ref } from 'vue'

interface Job {
  intervalId: number
  lastRun: number
}

export const usePollStore = defineStore('poll', () => {
  const jobs = ref<Map<string, Job>>(new Map())

  function start(key: string, fn: () => Promise<void> | void, intervalMs: number) {
    stop(key)
    const wrapped = async () => {
      try { await fn() } catch { /* swallow polling errors */ }
      const j = jobs.value.get(key)
      if (j) j.lastRun = Date.now()
    }
    void wrapped()
    const id = window.setInterval(wrapped, intervalMs)
    jobs.value.set(key, { intervalId: id, lastRun: Date.now() })
  }

  function stop(key: string) {
    const j = jobs.value.get(key)
    if (j) {
      clearInterval(j.intervalId)
      jobs.value.delete(key)
    }
  }

  function stopAll() {
    for (const k of [...jobs.value.keys()]) stop(k)
  }

  return { jobs, start, stop, stopAll }
})
