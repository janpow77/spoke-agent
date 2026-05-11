import { client } from './client'
import type {
  AgentStatus,
  LoginResponse,
  MeResponse,
  RouterStatus,
  ServiceConfigResponse,
  ServiceInfo,
  ServiceLogResponse,
} from './types'

export async function getHealth(): Promise<{ status: string; version: string; spoke_name: string; uptime_s: number; router_connected: boolean }> {
  // /health liegt NICHT unter /api — gesondert routen
  const r = await fetch('/health', { headers: { 'Accept': 'application/json' } })
  return r.json()
}

export async function getStatus(): Promise<AgentStatus> {
  const r = await client.get<AgentStatus>('/status')
  return r.data
}

export async function listServices(): Promise<ServiceInfo[]> {
  const r = await client.get<ServiceInfo[]>('/services')
  return r.data
}

export async function refreshServices(): Promise<unknown> {
  const r = await client.post('/services/refresh')
  return r.data
}

export async function restartService(name: string): Promise<unknown> {
  const r = await client.post(`/services/${name}/restart`)
  return r.data
}
export async function stopService(name: string): Promise<unknown> {
  const r = await client.post(`/services/${name}/stop`)
  return r.data
}
export async function startService(name: string): Promise<unknown> {
  const r = await client.post(`/services/${name}/start`)
  return r.data
}

export async function getLogs(name: string, tail = 200): Promise<ServiceLogResponse> {
  const r = await client.get<ServiceLogResponse>(`/services/${name}/logs`, { params: { tail } })
  return r.data
}

export async function getServiceConfig(name: string): Promise<ServiceConfigResponse> {
  const r = await client.get<ServiceConfigResponse>(`/services/${name}/config`)
  return r.data
}

export async function setServiceConfig(name: string, env: Record<string, string>): Promise<ServiceConfigResponse> {
  const r = await client.put<ServiceConfigResponse>(`/services/${name}/config`, { env })
  return r.data
}

export async function getRouter(): Promise<RouterStatus> {
  const r = await client.get<RouterStatus>('/router')
  return r.data
}

export async function setRouter(payload: {
  url?: string
  fallback_url?: string
  api_key?: string
  registration_token?: string
  spoke_tags?: string[]
}): Promise<RouterStatus> {
  const r = await client.put<RouterStatus>('/router', payload)
  return r.data
}

export async function runUpdate(service = 'all'): Promise<unknown> {
  const r = await client.post('/update', { service })
  return r.data
}

export async function login(password: string): Promise<LoginResponse> {
  const r = await client.post<LoginResponse>('/auth/login', { password })
  return r.data
}

export async function logout(): Promise<void> {
  await client.post('/auth/logout')
}

export async function me(): Promise<MeResponse> {
  const r = await client.get<MeResponse>('/auth/me')
  return r.data
}
