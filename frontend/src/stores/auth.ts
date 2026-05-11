import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '../api/agent'
import { setToken, getToken, extractError } from '../api/client'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getToken())
  const expiresAt = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  // Wenn der Server Auth ausgeschaltet hat (SPOKE_AGENT_AUTH=off), erlaubt
  // /api/auth/me logged_in:true ohne Token. Wir merken uns das so wir nicht
  // bei jedem Routing-Hop neu fragen muessen.
  const trusted = ref(false)

  const isAuthenticated = computed(() => !!token.value || trusted.value)

  function hydrate() {
    token.value = getToken()
  }

  async function checkTrusted(): Promise<boolean> {
    try {
      const r = await api.me()
      if (r.logged_in && !token.value) {
        trusted.value = true
        return true
      }
      return r.logged_in
    } catch {
      return false
    }
  }

  async function login(password: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      const result = await api.login(password)
      token.value = result.token
      expiresAt.value = result.expires_at
      setToken(result.token)
      return true
    } catch (err) {
      error.value = extractError(err)
      return false
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    try { await api.logout() } catch { /* ignore */ }
    token.value = null
    expiresAt.value = null
    setToken(null)
  }

  return { token, expiresAt, loading, error, trusted, isAuthenticated, hydrate, checkTrusted, login, logout }
})
