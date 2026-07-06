const BASE = (() => {
  const raw = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:5000'
  if (raw.startsWith('http')) return raw.replace(/\/$/, '')
  return `https://${raw}`
})()

async function req(path: string, opts?: RequestInit) {
  const res = await fetch(`${BASE}${path}`, {
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
    ...opts,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error((body as { error?: string }).error || res.statusText)
  }
  return res.json()
}

const api = {
  health: () => req('/health'),
  jobs: (p?: { min_score?: number; limit?: number }) => {
    const q = new URLSearchParams()
    if (p?.min_score != null) q.set('min_score', String(p.min_score))
    if (p?.limit != null) q.set('limit', String(p.limit))
    return req(`/jobs?${q}`)
  },
  job: (id: string) => req(`/jobs/${id}`),
  sessions: () => req('/sessions'),
  session: (id: string) => req(`/sessions/${id}`),
  applications: () => req('/applications'),
  analyticsOverview: () => req('/analytics/overview'),
  analyticsPatterns: () => req('/analytics/patterns'),
  evaluate: (d: object) => req('/evaluate', { method: 'POST', body: JSON.stringify(d) }),
  applyFromUrl: (d: object) => req('/apply-from-url', { method: 'POST', body: JSON.stringify(d) }),
  approve: (d: object) => req('/approve', { method: 'POST', body: JSON.stringify(d) }),
  gateResponse: (sid: string, d: object) =>
    req(`/gate-response/${sid}`, { method: 'POST', body: JSON.stringify(d) }),
  discover: (d?: object) => req('/discover', { method: 'POST', body: JSON.stringify(d ?? {}) }),
  outreach: (d: object) => req('/outreach', { method: 'POST', body: JSON.stringify(d) }),
  deepResearch: (d: object) => req('/deep-research', { method: 'POST', body: JSON.stringify(d) }),
  feedback: (d: object) => req('/feedback', { method: 'POST', body: JSON.stringify(d) }),
  generateCv: (d: object) => req('/generate-cv', { method: 'POST', body: JSON.stringify(d) }),
  submitSession: (sid: string) => req(`/sessions/${sid}/submit`, { method: 'POST' }),
}

export default api
