'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import api from '../../lib/api'

type Job = {
  id: string
  title?: string
  company?: string
  location?: string
  score?: number
  match_ratio?: number
  matched_skills?: string[]
  url?: string
  source?: string
  salary_range?: string
}

export default function Jobs() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [minScore, setMinScore] = useState(0)
  const [search, setSearch] = useState('')

  useEffect(() => {
    setLoading(true)
    api.jobs({ min_score: minScore, limit: 200 })
      .then(d => { setJobs(d.jobs ?? []); setTotal(d.total ?? 0) })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [minScore])

  const filtered = jobs.filter(j =>
    !search ||
    [j.title, j.company, j.location].some(v =>
      v?.toLowerCase().includes(search.toLowerCase())
    )
  )

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Jobs</h1>
        <p className="text-slate-400 text-sm mt-1">{total.toLocaleString()} total listings</p>
      </div>

      <div className="flex gap-3 mb-6">
        <input
          type="text"
          placeholder="Search title, company, location…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
        />
        <select
          value={minScore}
          onChange={e => setMinScore(Number(e.target.value))}
          className="bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
        >
          <option value={0}>All scores</option>
          <option value={60}>60+ score</option>
          <option value={70}>70+ score</option>
          <option value={80}>80+ score</option>
          <option value={90}>90+ score</option>
        </select>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm mb-6">{error}</div>
      )}

      {loading ? (
        <div className="text-slate-500 text-sm py-12 text-center">Loading jobs…</div>
      ) : filtered.length === 0 ? (
        <div className="text-slate-500 text-sm py-12 text-center">No jobs found</div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="text-xs text-slate-500 px-5 py-3 border-b border-slate-800">
            Showing {filtered.length} job{filtered.length !== 1 ? 's' : ''}
          </div>
          <div className="divide-y divide-slate-800">
            {filtered.map(j => (
              <Link
                key={j.id}
                href={`/jobs/${j.id}`}
                className="flex items-start justify-between px-5 py-4 hover:bg-slate-800/50 transition-colors group"
              >
                <div className="flex-1 min-w-0 mr-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-white font-medium text-sm group-hover:text-blue-300 transition-colors truncate">
                      {j.title ?? 'Untitled'}
                    </span>
                    {j.source && (
                      <span className="shrink-0 text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full border border-slate-700">
                        {j.source}
                      </span>
                    )}
                  </div>
                  <div className="text-slate-400 text-xs">
                    {j.company ?? '—'} · {j.location ?? 'Remote'}
                    {j.salary_range ? ` · ${j.salary_range}` : ''}
                  </div>
                  {j.matched_skills && j.matched_skills.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {j.matched_skills.slice(0, 5).map(s => (
                        <span key={s} className="text-xs bg-blue-950/60 text-blue-400 px-1.5 py-0.5 rounded border border-blue-900/50">
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="shrink-0 text-right">
                  {j.score != null && (
                    <div className={`text-lg font-bold ${
                      j.score >= 80 ? 'text-green-400' :
                      j.score >= 60 ? 'text-amber-400' : 'text-slate-400'
                    }`}>{j.score}</div>
                  )}
                  {j.match_ratio != null && (
                    <div className="text-xs text-slate-500">{Math.round(j.match_ratio * 100)}% match</div>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
