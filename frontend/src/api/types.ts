// Spiegelt die Pydantic-Schemas in src/spoke_agent/models.py.

export interface GpuInfo {
  device?: string | null
  vram_total_mb?: number | null
  vram_used_mb?: number | null
  util_pct?: number | null
}

export interface HostInfo {
  hostname: string
  platform: string
  arch: string
  kernel?: string | null
  container_runtime?: string | null
}

export interface ServiceInfo {
  name: string
  type: string
  base_url: string
  capabilities: string[]
  status: 'ok' | 'down' | 'unreachable' | 'unknown'
  version?: string | null
  image_digest?: string | null
  container_id?: string | null
  container_state?: string | null
  last_check_at?: string | null
  last_error?: string | null
  config: Record<string, unknown>
  compose_service?: string | null
}

export interface DiscoverySnapshot {
  capabilities: string[]
  gpu?: GpuInfo | null
  host_info: HostInfo
  services: ServiceInfo[]
  refreshed_at?: string | null
}

export interface RouterStatus {
  url: string
  fallback_url?: string | null
  using_fallback: boolean
  connected: boolean
  last_register_at?: string | null
  last_error?: string | null
  consecutive_failures: number
  app_id: string
}

export interface AgentStatus {
  spoke_name: string
  spoke_tags: string[]
  version: string
  uptime_s: number
  discovery: DiscoverySnapshot
  router: RouterStatus
}

export interface ServiceLogResponse {
  service: string
  lines: string[]
  tail: number
}

export interface ServiceConfigResponse {
  service: string
  env: Record<string, string>
  editable_keys: string[]
}

export interface MeResponse {
  logged_in: boolean
  expires_at?: string | null
}

export interface LoginResponse {
  token: string
  expires_at: string
}
