import axios, { type AxiosError, type AxiosInstance } from 'axios'

const STORAGE_KEY = 'spoke_agent_token'

export const TOKEN_KEY = STORAGE_KEY
export const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export const client: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(STORAGE_KEY)
  if (token) {
    config.headers = config.headers || {}
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(STORAGE_KEY)
      if (!window.location.pathname.endsWith('/login')) {
        window.location.href = '/admin/login'
      }
    }
    return Promise.reject(error)
  }
)

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(STORAGE_KEY, token)
  else localStorage.removeItem(STORAGE_KEY)
}

export function getToken(): string | null {
  return localStorage.getItem(STORAGE_KEY)
}

export function extractError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as any)?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length) return detail[0].msg || JSON.stringify(detail[0])
    return err.message
  }
  if (err instanceof Error) return err.message
  return String(err)
}
