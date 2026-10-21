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
  // async-apply fix: /approve returns { apply_job_id }; poll for the result
  applyStatus: (id: string) => req(`/apply-status/${id}`),
  pollApply: async (id: string, onStatus?: (s: string) => void, maxMs = 600000): Promise<any> => {
    const start = Date.now()
    while (Date.now() - start < maxMs) {
      await new Promise(r => setTimeout(r, 4000))
      const s = await req(`/apply-status/${id}`)
      onStatus?.(s.status)
      if (s.status === 'done') return s.result ?? s
      if (s.status === 'failed') throw new Error(s.error || 'Application workflow failed')
    }
    throw new Error('Application workflow timed out (10 min)')
  },

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

  // ---- JobRight-parity additions (Phases 1-5) ----
  matchExplanation: (id: string) => req(`/jobs/${id}/match-explanation`),
  insights: () => req('/insights'),
  copilotChat: (d: object) =>
    req('/copilot/chat', { method: 'POST', body: JSON.stringify(d) }),
  copilotHistory: (conversationId?: string) =>
    req(`/copilot/history?conversation_id=${conversationId ?? 'default'}`),
  alerts: (p?: { unread_only?: boolean; limit?: number }) => {
    const q = new URLSearchParams()
    if (p?.unread_only) q.set('unread_only', 'true')
    if (p?.limit) q.set('limit', String(p.limit))
    return req(`/alerts?${q}`)
  },
  markAlertRead: (id: string) => req(`/alerts/${id}/read`, { method: 'POST' }),
  markAllAlertsRead: () => req('/alerts/read-all', { method: 'POST' }),
  profileImport: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return fetch(`${BASE}/profile/import`, { method: 'POST', body: fd }).then(async res => {
      const body = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error((body as { error?: string }).error || res.statusText)
      return body
    })
  },
  profileImportConfirm: (d: object) =>
    req('/profile/import/confirm', { method: 'POST', body: JSON.stringify(d) }),
  interviews: (p?: { upcoming_only?: boolean }) =>
    req(`/interviews${p?.upcoming_only ? '?upcoming_only=true' : ''}`),
  addInterview: (d: object) => req('/interviews', { method: 'POST', body: JSON.stringify(d) }),
  updateInterviewStatus: (id: string, status: string) =>
    req(`/interviews/${id}/status`, { method: 'POST', body: JSON.stringify({ status }) }),
  insiders: (p: { company?: string; domain?: string }) => {
    const q = new URLSearchParams()
    if (p.company) q.set('company', p.company)
    if (p.domain) q.set('domain', p.domain)
    return req(`/insiders?${q}`)
  },
}

export default api

// Bulk-apply fix: job URLs live under different keys depending on the source
// (LinkedIn scrapes use 'link'/'applyUrl', RemoteOK 'url', some empty strings).
// Empty string is falsy but ?? doesn't skip it — coerce explicitly.
export function resolveJobUrl(job: Record<string, unknown>): string {
  for (const key of ['url', 'applyUrl', 'apply_url', 'link']) {
    const v = job?.[key]
    if (typeof v === 'string' && v.trim().startsWith('http')) return v.trim()
  }
  return ''
}
