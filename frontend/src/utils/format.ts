export function formatBytes(b: number | null | undefined): string {
  if (b === null || b === undefined) return '—'
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`
  return `${(b / 1024 / 1024 / 1024).toFixed(1)} GB`
}

export function formatVram(mb: number | null | undefined): string {
  if (mb === null || mb === undefined) return '—'
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
  return `${mb} MB`
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('de-DE', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  } catch { return iso }
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const t = new Date(iso).getTime()
  const diffS = Math.floor((Date.now() - t) / 1000)
  if (diffS < 5) return 'gerade eben'
  if (diffS < 60) return `vor ${diffS}s`
  if (diffS < 3600) return `vor ${Math.floor(diffS / 60)} min`
  if (diffS < 86400) return `vor ${Math.floor(diffS / 3600)} h`
  return `vor ${Math.floor(diffS / 86400)} d`
}

export function formatUptime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ${Math.floor((seconds % 3600) / 60)} min`
  return `${Math.floor(seconds / 86400)} d ${Math.floor((seconds % 86400) / 3600)} h`
}

export function statusVariant(s: string | null | undefined): string {
  switch (s) {
    case 'ok':
    case 'online':
    case 'healthy':
    case 'running':
      return 'green'
    case 'down':
    case 'failed':
    case 'offline':
    case 'error':
      return 'red'
    case 'degraded':
    case 'unreachable':
      return 'amber'
    case 'unknown':
    default:
      return 'slate'
  }
}
