'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import api from '../../lib/api'

type DemandSkill = { skill: string; demand_count: number; demand_ratio: number; in_profile?: boolean }
type Insights = {
  profile?: { top_skills?: string[]; years_experience_estimate?: number | null; positioning?: string }
  market?: {
    feed_size?: number
    score_stats?: { avg?: number; max?: number; count?: number; high_match_count?: number }
    seniority_mix?: Record<string, number>
    top_demand_skills?: DemandSkill[]
  }
  alignment?: { coverage_ratio?: number; skills_to_consider?: string[]; demand?: DemandSkill[] }
  application_funnel?: { total_applications?: number; by_status?: Record<string, number> }
  recommendations?: string[]
}

export default function InsightsPage() {
  const [data, setData] = useState<Insights | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.insights()
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <main className="pl-56 pt-10 px-8 text-slate-400">Loading insights…</main>
  if (error) return <main className="pl-56 pt-10 px-8 text-red-400">{error}</main>
  if (!data) return null

  const market = data.market ?? {}
  const scores = market.score_stats ?? {}
  const alignment = data.alignment ?? {}
  const coverage = Math.round((alignment.coverage_ratio ?? 0) * 100)
  const seniority = market.seniority_mix ?? {}
  const demand: DemandSkill[] = alignment.demand ?? []
  const funnel = data.application_funnel ?? {}

  return (
    <main className="pl-56 min-h-screen bg-slate-950 text-slate-200">
      <div className="max-w-6xl mx-auto px-8 py-10">
        <h1 className="text-2xl font-bold text-white mb-1">Insights</h1>
        <p className="text-sm text-slate-500 mb-8">
          How your profile aligns with the current market — skills demand, seniority mix, and funnel health.
        </p>

        {/* Profile snapshot */}
        {data.profile?.positioning && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 mb-6">
            <div className="text-xs text-slate-500 uppercase tracking-widest mb-2">Your positioning</div>
            <p className="text-slate-300">{data.profile.positioning}</p>
            {data.profile.years_experience_estimate != null && (
              <p className="text-xs text-slate-500 mt-2">Estimated experience: ~{data.profile.years_experience_estimate} yr</p>
            )}
          </div>
        )}

        {/* Score stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <Stat label="Feed size" value={market.feed_size ?? 0} />
          <Stat label="Avg score" value={scores.avg ?? 0} />
          <Stat label="Top score" value={scores.max ?? 0} />
          <Stat label="High matches (75+)" value={scores.high_match_count ?? 0} color="text-green-400" />
        </div>

        {/* Skill coverage */}
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="text-xs text-slate-500 uppercase tracking-widest">Market skill demand</div>
              <div className="text-sm font-bold text-blue-400">{coverage}% covered</div>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-2 mb-4">
              <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${coverage}%` }} />
            </div>
            <div className="space-y-2">
              {demand.slice(0, 10).map(d => (
                <div key={d.skill} className="flex items-center gap-3">
                  <div className="w-36 shrink-0 text-sm truncate flex items-center gap-1.5">
                    {d.in_profile
                      ? <span className="w-1.5 h-1.5 rounded-full bg-green-400 shrink-0" />
                      : <span className="w-1.5 h-1.5 rounded-full bg-slate-600 shrink-0" />}
                    {d.skill}
                  </div>
                  <div className="flex-1 bg-slate-800 rounded-full h-1.5">
                    <div
                      className={`h-1.5 rounded-full ${d.in_profile ? 'bg-green-500' : 'bg-slate-600'}`}
                      style={{ width: `${Math.round((d.demand_ratio ?? 0) * 100)}%` }}
                    />
                  </div>
                  <div className="w-10 text-right text-xs text-slate-500 tabular-nums">{d.demand_count}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <div className="text-xs text-slate-500 uppercase tracking-widest mb-4">Seniority mix in feed</div>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(seniority).map(([k, v]) => (
                  <div key={k} className="flex justify-between text-sm bg-slate-950/60 rounded-lg px-3 py-2">
                    <span className="text-slate-400 capitalize">{k}</span>
                    <span className="font-bold tabular-nums">{v}</span>
                  </div>
                ))}
                {Object.keys(seniority).length === 0 && <div className="text-sm text-slate-600">Run a scan first.</div>}
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <div className="text-xs text-slate-500 uppercase tracking-widest mb-3">Application funnel</div>
              <div className="text-3xl font-bold text-white mb-3">{funnel.total_applications ?? 0}</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(funnel.by_status ?? {}).map(([k, v]) => (
                  <span key={k} className="text-xs bg-slate-950/60 border border-slate-800 rounded-full px-2.5 py-1">
                    {k}: <span className="font-bold">{v}</span>
                  </span>
                ))}
                {Object.keys(funnel.by_status ?? {}).length === 0 && (
                  <span className="text-sm text-slate-600">No applications tracked yet.</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Skills to consider */}
        {(alignment.skills_to_consider ?? []).length > 0 && (
          <div className="bg-amber-950/20 border border-amber-900/50 rounded-xl p-5 mb-8">
            <div className="text-xs text-amber-500 uppercase tracking-widest mb-3">Skills the market wants that aren&apos;t in your profile</div>
            <div className="flex flex-wrap gap-2">
              {alignment.skills_to_consider!.map(s => (
                <span key={s} className="text-sm bg-amber-950/40 border border-amber-900/60 text-amber-300 rounded-full px-3 py-1">{s}</span>
              ))}
            </div>
          </div>
        )}

        {/* Recommendations */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="text-xs text-slate-500 uppercase tracking-widest mb-3">Recommended next steps</div>
          <ul className="space-y-2">
            {(data.recommendations ?? []).map((r, i) => (
              <li key={i} className="text-sm text-slate-300 flex gap-2"><span className="text-blue-400">→</span>{r}</li>
            ))}
          </ul>
        </div>
      </div>
    </main>
  )
}

function Stat({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <div className="text-xs text-slate-500 uppercase tracking-widest mb-1">{label}</div>
      <div className={`text-2xl font-bold tabular-nums ${color ?? 'text-white'}`}>{value}</div>
    </div>
  )
}
