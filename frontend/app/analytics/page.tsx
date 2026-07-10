'use client'

import { useEffect, useState } from 'react'
import api from '../../lib/api'

type Overview = { average_score?: number; total_applications?: number; interview_rate?: number; response_rate?: number; [key: string]: unknown }
type Patterns = {
  conversion_by_score_band?: Record<string, number>
  rejection_by_archetype?: Record<string, number>
  top_companies_by_response?: Array<{ company: string; rate: number }>
  score_vs_outcome_correlation?: { correlation: number | null; data_points: number }
}

function BarChart({ data, label, color = 'bg-blue-600' }: { data: Record<string, number>; label: string; color?: string }) {
  const entries = Object.entries(data).filter(([, v]) => v != null)
  if (!entries.length) return <div className="text-slate-600 text-xs py-4 text-center">No data yet</div>
  const max = Math.max(...entries.map(([, v]) => v), 1)
  return (
    <div>
      <div className="text-xs text-slate-500 font-semibold uppercase tracking-wider mb-3">{label}</div>
      <div className="space-y-2">
        {entries.map(([k, v]) => (
          <div key={k} className="flex items-center gap-3">
            <div className="text-xs text-slate-400 w-24 shrink-0 truncate">{k}</div>
            <div className="flex-1 bg-slate-800 rounded-full h-5 overflow-hidden">
              <div className={`h-5 rounded-full ${color} transition-all duration-700`} style={{ width: `${Math.max((v / max) * 100, 2)}%` }} />
            </div>
            <div className="text-xs text-slate-300 w-10 text-right tabular-nums">{typeof v === 'number' && v < 2 ? `${Math.round(v * 100)}%` : v}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function FunnelChart({ steps }: { steps: Array<{ label: string; value: number; color: string }> }) {
  const max = Math.max(...steps.map(s => s.value), 1)
  return (
    <div>
      <div className="text-xs text-slate-500 font-semibold uppercase tracking-wider mb-4">Application Funnel</div>
      <div className="space-y-2">
        {steps.map((s, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="text-xs text-slate-400 w-24 shrink-0">{s.label}</div>
            <div className="flex-1 bg-slate-800 rounded h-7 overflow-hidden">
              <div className={`h-7 flex items-center px-3 rounded transition-all duration-700 ${s.color}`}
                style={{ width: `${Math.max((s.value / max) * 100, s.value > 0 ? 5 : 2)}%` }}>
                {s.value > 0 && <span className="text-white text-xs font-bold">{s.value}</span>}
              </div>
            </div>
            <div className="text-xs text-slate-300 w-8 text-right">{s.value}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ScoreHistogram({ jobs }: { jobs: Array<{ score?: number }> }) {
  const bands = [
    { range: '90-100', min: 90, max: 101, color: 'bg-green-500' },
    { range: '80-89', min: 80, max: 90, color: 'bg-green-600' },
    { range: '70-79', min: 70, max: 80, color: 'bg-amber-500' },
    { range: '60-69', min: 60, max: 70, color: 'bg-amber-600' },
    { range: '50-59', min: 50, max: 60, color: 'bg-orange-600' },
    { range: '<50', min: 0, max: 50, color: 'bg-red-600' },
  ]
  const counts = bands.map(b => ({
    ...b,
    count: jobs.filter(j => j.score != null && j.score >= b.min && j.score < b.max).length,
  }))
  const max = Math.max(...counts.map(c => c.count), 1)
  return (
    <div>
      <div className="text-xs text-slate-500 font-semibold uppercase tracking-wider mb-3">Score Distribution</div>
      <div className="flex items-end gap-2 h-28">
        {counts.map(c => (
          <div key={c.range} className="flex-1 flex flex-col items-center gap-1">
            <div className="text-xs text-slate-500 tabular-nums">{c.count > 0 ? c.count : ''}</div>
            <div className={`w-full rounded-t transition-all duration-700 ${c.color}`}
              style={{ height: `${Math.max((c.count / max) * 80, c.count > 0 ? 8 : 2)}px` }} />
            <div className="text-xs text-slate-600 text-center leading-tight">{c.range}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Analytics() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [patterns, setPatterns] = useState<Patterns | null>(null)
  const [allJobs, setAllJobs] = useState<Array<{ score?: number }>>([])
  const [apps, setApps] = useState<Array<{ status?: string }>>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      api.analyticsOverview(),
      api.analyticsPatterns(),
      api.jobs({ limit: 500 }),
      api.applications(),
    ]).then(([o, p, j, a]) => {
      if (o.status === 'fulfilled') setOverview(o.value)
      if (p.status === 'fulfilled') setPatterns(p.value)
      if (j.status === 'fulfilled') setAllJobs(j.value.jobs ?? [])
      if (a.status === 'fulfilled') setApps(a.value.applications ?? [])
    }).finally(() => setLoading(false))
  }, [])

  const scoredJobs = allJobs.filter(j => j.score != null)
  const avgScore = scoredJobs.length > 0 ? Math.round(scoredJobs.reduce((s, j) => s + (j.score ?? 0), 0) / scoredJobs.length) : null

  const funnelSteps = [
    { label: 'Total Jobs', value: allJobs.length, color: 'bg-slate-600' },
    { label: 'Scored', value: scoredJobs.length, color: 'bg-blue-600' },
    { label: 'Applied', value: apps.length, color: 'bg-purple-600' },
    { label: 'Submitted', value: apps.filter(a => a.status === 'submitted').length, color: 'bg-green-600' },
    { label: 'Draft', value: apps.filter(a => a.status === 'draft_saved').length, color: 'bg-amber-600' },
  ]

  const statCards = [
    { label: 'Total Jobs', value: allJobs.length, sub: 'in database' },
    { label: 'Avg Score', value: avgScore != null ? `${avgScore}` : '—', sub: 'across scored jobs' },
    { label: 'Applications', value: apps.length, sub: 'total tracked' },
    { label: 'Submission Rate', value: apps.length > 0 ? `${Math.round(apps.filter(a => a.status === 'submitted').length / apps.length * 100)}%` : '—', sub: 'of applications' },
    ...(overview ? Object.entries(overview).filter(([, v]) => typeof v === 'number' && v > 0).slice(0, 2).map(([k, v]) => ({
      label: k.replace(/_/g, ' '),
      value: typeof v === 'number' && v < 1 ? `${Math.round(v * 100)}%` : String(v),
      sub: ''
    })) : []),
  ]

  if (loading) return <div className="text-slate-500 text-sm py-12 text-center">Loading analytics…</div>

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Analytics</h1>
        <p className="text-slate-400 text-sm mt-1">Performance patterns and job search insights</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statCards.slice(0, 4).map(s => (
          <div key={s.label} className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">{s.label}</div>
            <div className="text-3xl font-bold text-white tabular-nums">{s.value}</div>
            {s.sub && <div className="text-xs text-slate-600 mt-1">{s.sub}</div>}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <ScoreHistogram jobs={scoredJobs} />
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <FunnelChart steps={funnelSteps} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {patterns?.conversion_by_score_band && Object.keys(patterns.conversion_by_score_band).length > 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <BarChart data={patterns.conversion_by_score_band} label="Conversion by Score Band" color="bg-green-600" />
          </div>
        )}
        {patterns?.rejection_by_archetype && Object.keys(patterns.rejection_by_archetype).length > 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <BarChart data={patterns.rejection_by_archetype} label="Rejection by Archetype" color="bg-red-600" />
          </div>
        )}
        {patterns?.top_companies_by_response && patterns.top_companies_by_response.length > 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <BarChart
              data={Object.fromEntries(patterns.top_companies_by_response.map(c => [c.company, c.rate]))}
              label="Top Companies by Response Rate"
              color="bg-blue-600"
            />
          </div>
        )}
        {patterns?.score_vs_outcome_correlation && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="text-xs text-slate-500 font-semibold uppercase tracking-wider mb-4">Score vs Outcome Correlation</div>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-800/60 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-white">
                  {patterns.score_vs_outcome_correlation.correlation != null
                    ? patterns.score_vs_outcome_correlation.correlation.toFixed(2)
                    : '—'}
                </div>
                <div className="text-xs text-slate-500 mt-1">Correlation</div>
              </div>
              <div className="bg-slate-800/60 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-white">{patterns.score_vs_outcome_correlation.data_points}</div>
                <div className="text-xs text-slate-500 mt-1">Data Points</div>
              </div>
            </div>
            {patterns.score_vs_outcome_correlation.data_points === 0 && (
              <p className="text-xs text-slate-600 mt-3 text-center">Complete some applications to see correlation data</p>
            )}
          </div>
        )}
      </div>

      {(!patterns || Object.values(patterns).every(v => !v || (Array.isArray(v) && v.length === 0) || (typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length === 0))) && apps.length === 0 && (
        <div className="mt-6 bg-slate-900/50 border border-dashed border-slate-700 rounded-xl p-8 text-center">
          <div className="text-slate-500 text-sm mb-2">No application data yet</div>
          <p className="text-slate-600 text-xs">Apply to jobs to start seeing patterns and conversion analytics</p>
        </div>
      )}
    </div>
  )
}
