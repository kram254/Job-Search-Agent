const BASE = (() => {
  const raw = process.env.NEXT_PUBLIC_API_URL ?? 'https://job-search-agent-tfd1.onrender.com'
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
  submitSession: (sid: string) => req(`/sessions/${sid}/submit`, { method: 'POST' }),
  gateResponse: (sid: string, d: object) =>
    req(`/gate-response/${sid}`, { method: 'POST', body: JSON.stringify(d) }),

  applications: () => req('/applications'),

  schedule: () => req('/schedule'),
  createSchedule: (d: object) => req('/schedule', { method: 'POST', body: JSON.stringify(d) }),
  deleteSchedule: (id: string) => req(`/schedule/${id}`, { method: 'DELETE' }),
  runSchedule: (id: string) => req(`/schedule/${id}/run`, { method: 'POST' }),

  pipeline: () => req('/pipeline'),
  addToPipeline: (d: object) => req('/pipeline', { method: 'POST', body: JSON.stringify(d) }),
  processPipeline: (d?: object) =>
    req('/pipeline/process', { method: 'POST', body: JSON.stringify(d ?? { limit: 10 }) }),

  followups: () => req('/follow-ups'),
  trackFollowup: (d: object) => req('/follow-ups', { method: 'POST', body: JSON.stringify(d) }),

  storyBank: (p?: { archetype?: string; limit?: number }) => {
    const q = new URLSearchParams()
    if (p?.archetype) q.set('archetype', p.archetype)
    if (p?.limit) q.set('limit', String(p.limit))
    return req(`/story-bank?${q}`)
  },
  addStory: (d: object) => req('/story-bank', { method: 'POST', body: JSON.stringify(d) }),

  providers: () => req('/providers'),
  models: (source?: string) => req(`/models${source ? `?source=${source}` : ''}`),

  scan: (d?: object) => req('/scan', { method: 'POST', body: JSON.stringify(d ?? {}) }),
  liveness: (url: string) => req('/liveness', { method: 'POST', body: JSON.stringify({ url }) }),

  evaluate: (d: object) => req('/evaluate', { method: 'POST', body: JSON.stringify(d) }),
  generateCv: (d: object) => req('/generate-cv', { method: 'POST', body: JSON.stringify(d) }),
  calibrateStyle: (d: object) => req('/calibrate-style', { method: 'POST', body: JSON.stringify(d) }),

  applyFromUrl: (d: object) =>
    req('/apply-from-url', { method: 'POST', body: JSON.stringify(d) }),
  approve: (d: object) => req('/approve', { method: 'POST', body: JSON.stringify(d) }),

  outreach: (d: object) => req('/outreach', { method: 'POST', body: JSON.stringify(d) }),
  deepResearch: (d: object) =>
    req('/deep-research', { method: 'POST', body: JSON.stringify(d) }),

  feedback: (d: object) => req('/feedback', { method: 'POST', body: JSON.stringify(d) }),

  analyticsOverview: () => req('/analytics/overview'),
  analyticsPatterns: () => req('/analytics/patterns'),

  discover: (d?: object) =>
    req('/discover', { method: 'POST', body: JSON.stringify(d ?? {}) }),

  llmComplete: (d: object) =>
    req('/llm/complete', { method: 'POST', body: JSON.stringify(d) }),

  composioConnect: (app: string) =>
    req('/composio/connect', { method: 'POST', body: JSON.stringify({ app }) }),
  composioConnections: () => req('/composio/connections'),
  composioSend: (d: object) =>
    req('/composio/send', { method: 'POST', body: JSON.stringify(d) }),
}

export default api
