'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import api from '../lib/api'

type Job = { id: string; title?: string; company?: string; score?: number; match_ratio?: number; source?: string }
type AppRecord = { title?: string; company?: string; status?: string; applied_at?: string }
type Session = { session_id: string; checkpoints: number; latest?: { step?: string; status?: string } }
type ProviderInfo = { available: boolean; model?: string }
type Providers = { anthropic?: ProviderInfo; openrouter?: ProviderInfo; gemini?: ProviderInfo; active_provider?: string }
type FollowupStats = { due_count?: number; total?: number }

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color: string }) {
  return (
    <div className={`bg-slate-900 border rounded-xl p-5 relative overflow-hidden group transition-all hover:scale-[1.02] ${color}`}>
      <div className="text-xs text-slate-500 uppercase tracking-widest mb-2 font-medium">{label}</div>
      <div className="text-4xl font-bold text-white tabular-nums">{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-1">{sub}</div>}
      <div className="absolute -bottom-2 -right-2 w-16 h-16 rounded-full opacity-10 bg-current transition-all group-hover:opacity-20" />
    </div>
  )
}

function ProviderBadge({ providers }: { providers: Providers | null }) {
  if (!providers) return null
  const active = providers.active_provider || 'unknown'
  const hasAI = providers.anthropic?.available || providers.openrouter?.available || providers.gemini?.available
  const model = providers.openrouter?.available
    ? (providers.openrouter.model || 'OpenRouter')
    : providers.anthropic?.available
    ? (providers.anthropic.model || 'Anthropic')
    : providers.gemini?.available
    ? 'Gemini'
    : null

  return (
    <div className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-full border ${
      hasAI ? 'border-green-800/60 bg-green-950/40 text-green-400' : 'border-red-900/60 bg-red-950/30 text-red-400'
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${hasAI ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
      {hasAI ? (model || active) : 'No LLM configured'}
    </div>
  )
}

function ScorePill({ score }: { score?: number }) {
  if (score == null) return null
  const color = score >= 80 ? 'text-green-400 bg-green-950/50 border-green-900/60' :
    score >= 60 ? 'text-amber-400 bg-amber-950/50 border-amber-900/60' :
    'text-slate-400 bg-slate-800 border-slate-700'
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded-full border tabular-nums ${color}`}>{score}</span>
  )
}

export default function Dashboard() {
  const [jobs, setJobs] = useState<{ jobs: Job[]; total: number } | null>(null)
  const [apps, setApps] = useState<{ applications: AppRecord[] } | null>(null)
  const [sessions, setSessions] = useState<{ sessions: Session[] } | null>(null)
  const [providers, setProviders] = useState<Providers | null>(null)
  const [followupStats, setFollowupStats] = useState<FollowupStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [discovering, setDiscovering] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [discoverResult, setDiscoverResult] = useState<{ top_jobs: Job[] } | null>(null)
  const [actionMsg, setActionMsg] = useState('')

  const load = useCallback(() => {
    Promise.allSettled([
      api.jobs({ limit: 200 }),
      api.applications(),
      api.sessions(),
      api.providers(),
      api.followups(),
    ]).then(([j, a, s, p, f]) => {
      if (j.status === 'fulfilled') setJobs(j.value)
      if (a.status === 'fulfilled') setApps(a.value)
      if (s.status === 'fulfilled') setSessions(s.value)
      if (p.status === 'fulfilled') setProviders(p.value)
      if (f.status === 'fulfilled') setFollowupStats(f.value.stats ?? {})
      setLoading(false)
    })
  }, [])

  useEffect(() => { load() }, [load])

  function handleDiscover() {
    setDiscovering(true)
    setActionMsg('Scraping RemoteOK + LinkedIn…')
    api.discover({ top_n: 5 })
      .then(r => { setDiscoverResult(r); setActionMsg(`Found ${r.remoteok_count + r.linkedin_count} leads — top 5 shown below`) })
      .catch((e: Error) => setActionMsg(`Discover failed: ${e.message}`))
      .finally(() => setDiscovering(false))
  }

  function handleProcess() {
    setProcessing(true)
    setActionMsg('Processing pipeline…')
    api.processPipeline()
      .then(r => { setActionMsg(`Processed ${r.processed ?? 0} pipeline items`); load() })
      .catch((e: Error) => setActionMsg(`Pipeline error: ${e.message}`))
      .finally(() => setProcessing(false))
  }

  const topJobs = (jobs?.jobs ?? [])
    .filter(j => j.score != null)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, 8)

  const recentApps = (apps?.applications ?? []).slice(0, 6)
  const activeSessions = (sessions?.sessions ?? []).filter(s => s.latest?.status !== 'submitted')

  return (
    <div className="min-h-screen">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Dashboard</h1>
          <p className="text-slate-500 text-sm mt-1">Job Search Agent · kram254</p>
        </div>
        <div className="flex items-center gap-3">
          <ProviderBadge providers={providers} />
          <button onClick={load} className="text-xs text-slate-500 hover:text-slate-300 transition-colors">
            ↻ Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Total Jobs"
          value={loading ? '—' : (jobs?.total ?? 0).toLocaleString()}
          sub="in database"
          color="border-blue-900/40 text-blue-500"
        />
        <StatCard
          label="Applications"
          value={loading ? '—' : apps?.applications?.length ?? 0}
          sub="sent"
          color="border-green-900/40 text-green-500"
        />
        <StatCard
          label="Sessions"
          value={loading ? '—' : activeSessions.length}
          sub="active"
          color="border-purple-900/40 text-purple-500"
        />
        <StatCard
          label="Follow-ups"
          value={loading ? '—' : followupStats?.due_count ?? 0}
          sub="due now"
          color={followupStats?.due_count ? 'border-amber-900/40 text-amber-500' : 'border-slate-800 text-slate-500'}
        />
      </div>

      <div className="flex flex-wrap gap-3 mb-8">
        <button
          onClick={handleDiscover}
          disabled={discovering}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-all hover:shadow-lg hover:shadow-blue-900/40 active:scale-95"
        >
          {discovering ? (
            <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin inline-block" />Scraping…</>
          ) : '✦ Discover New Jobs'}
        </button>
        <button
          onClick={handleProcess}
          disabled={processing}
          className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-60 border border-slate-700 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-all active:scale-95"
        >
          {processing ? (
            <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin inline-block" />Processing…</>
          ) : '⚡ Process Pipeline'}
        </button>
        <Link
          href="/schedule"
          className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-all"
        >
          ◷ Schedules
        </Link>
        <Link
          href="/analytics"
          className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-sm font-semibold px-5 py-2.5 rounded-xl transition-all"
        >
          ◑ Analytics
        </Link>
      </div>

      {actionMsg && (
        <div className="mb-6 text-xs text-slate-400 bg-slate-900 border border-slate-800 rounded-lg px-4 py-2.5">
          {actionMsg}
        </div>
      )}

      {discoverResult && discoverResult.top_jobs.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white">✦ Latest Discovery — Top Leads</h2>
            <Link href="/jobs" className="text-xs text-blue-400 hover:text-blue-300">See all →</Link>
          </div>
          <div className="bg-slate-900 border border-blue-900/40 rounded-xl overflow-hidden">
            <div className="divide-y divide-slate-800/50">
              {discoverResult.top_jobs.map((j, i) => (
                <Link key={i} href={j.id ? `/jobs/${j.id}` : '/jobs'}
                  className="flex items-center justify-between px-5 py-3.5 hover:bg-slate-800/40 transition-colors group">
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-600 font-mono w-4">#{i + 1}</span>
                    <div>
                      <div className="text-sm text-white group-hover:text-blue-300 transition-colors font-medium">{j.title ?? 'Untitled'}</div>
                      <div className="text-xs text-slate-500">{j.company ?? '—'}</div>
                    </div>
                  </div>
                  <ScorePill score={j.score} />
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-8">
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white">Top Jobs by Score</h2>
            <Link href="/jobs" className="text-xs text-blue-400 hover:text-blue-300">Browse all →</Link>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            {loading ? (
              <div className="py-12 text-center text-slate-600 text-sm">Loading…</div>
            ) : topJobs.length === 0 ? (
              <div className="py-12 text-center">
                <div className="text-slate-500 text-sm">No jobs yet</div>
                <button onClick={handleDiscover} className="mt-3 text-xs text-blue-400 hover:text-blue-300">
                  Run Discover to fetch jobs →
                </button>
              </div>
            ) : (
              <div className="divide-y divide-slate-800/50">
                {topJobs.map(j => (
                  <Link key={j.id} href={`/jobs/${j.id}`}
                    className="flex items-center justify-between px-5 py-3.5 hover:bg-slate-800/40 transition-colors group">
                    <div className="min-w-0 mr-4">
                      <div className="text-sm text-white group-hover:text-blue-300 transition-colors font-medium truncate">
                        {j.title ?? 'Untitled'}
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        {j.company ?? '—'}
                        {j.source ? ` · ${j.source}` : ''}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {j.match_ratio != null && (
                        <span className="text-xs text-slate-500">{Math.round(j.match_ratio * 100)}%</span>
                      )}
                      <ScorePill score={j.score} />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-5">
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-white">Applications</h2>
              <Link href="/applications" className="text-xs text-blue-400 hover:text-blue-300">View all →</Link>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
              {recentApps.length === 0 ? (
                <div className="py-8 text-center text-slate-600 text-xs">No applications yet</div>
              ) : (
                <div className="divide-y divide-slate-800/50">
                  {recentApps.map((a, i) => (
                    <div key={i} className="flex items-center justify-between px-4 py-3">
                      <div className="min-w-0 mr-2">
                        <div className="text-xs text-white font-medium truncate">{a.title ?? '—'}</div>
                        <div className="text-xs text-slate-600 truncate">{a.company ?? '—'}</div>
                      </div>
                      <span className={`text-xs px-1.5 py-0.5 rounded-full shrink-0 ${
                        a.status === 'submitted' ? 'bg-green-900/60 text-green-400' :
                        a.status === 'draft_saved' ? 'bg-blue-900/60 text-blue-400' :
                        'bg-slate-800 text-slate-500'
                      }`}>{a.status ?? '—'}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-white">Active Sessions</h2>
              <Link href="/sessions" className="text-xs text-blue-400 hover:text-blue-300">View all →</Link>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
              {activeSessions.length === 0 ? (
                <div className="py-8 text-center text-slate-600 text-xs">No active sessions</div>
              ) : (
                <div className="divide-y divide-slate-800/50">
                  {activeSessions.slice(0, 4).map(s => (
                    <Link key={s.session_id} href={`/sessions/${s.session_id}`}
                      className="flex items-center justify-between px-4 py-3 hover:bg-slate-800/40 transition-colors group">
                      <div className="min-w-0 mr-2">
                        <div className="text-xs text-white font-mono truncate">{s.session_id.slice(0, 16)}…</div>
                        <div className="text-xs text-slate-600">{s.latest?.step ?? 'initializing'}</div>
                      </div>
                      <span className={`text-xs px-1.5 py-0.5 rounded-full shrink-0 ${
                        s.latest?.status === 'hitl_pause' ? 'bg-amber-900/60 text-amber-400' :
                        s.latest?.status === 'running' ? 'bg-blue-900/60 text-blue-400' :
                        'bg-slate-800 text-slate-500'
                      }`}>{s.latest?.status ?? '—'}</span>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">System Status</h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <div className="text-xs text-slate-600 mb-1">Backend</div>
            <div className="flex items-center gap-1.5 text-xs text-green-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
              Healthy
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-600 mb-1">Active LLM</div>
            <div className="text-xs text-white">
              {providers
                ? providers.openrouter?.available ? 'OpenRouter (llama-3.3-70b)'
                  : providers.anthropic?.available ? 'Anthropic (claude)'
                  : providers.gemini?.available ? 'Gemini'
                  : 'Not configured'
                : '—'}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-600 mb-1">Daily Digest</div>
            <div className="text-xs text-slate-400">Runs 07:00 UTC daily</div>
          </div>
          <div>
            <div className="text-xs text-slate-600 mb-1">Follow-ups due</div>
            <div className={`text-xs font-bold ${(followupStats?.due_count ?? 0) > 0 ? 'text-amber-400' : 'text-slate-400'}`}>
              {followupStats?.due_count ?? 0} of {followupStats?.total ?? 0} total
            </div>
          </div>
        </div>
        <div className="mt-4 pt-4 border-t border-slate-800 flex flex-wrap gap-3">
          <Link href="/providers" className="text-xs text-slate-500 hover:text-blue-400 transition-colors">LLM Providers →</Link>
          <Link href="/follow-ups" className="text-xs text-slate-500 hover:text-blue-400 transition-colors">Follow-ups →</Link>
          <Link href="/story-bank" className="text-xs text-slate-500 hover:text-blue-400 transition-colors">Story Bank →</Link>
          <Link href="/pipeline" className="text-xs text-slate-500 hover:text-blue-400 transition-colors">Pipeline →</Link>
          <a href="https://job-search-agent-tfd1.onrender.com" target="_blank" rel="noopener noreferrer"
            className="text-xs text-slate-500 hover:text-blue-400 transition-colors">
            API ↗
          </a>
        </div>
      </div>
    </div>
  )
}
