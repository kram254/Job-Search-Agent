'use client'

import { useState } from 'react'
import Link from 'next/link'
import api from '../../lib/api'

type DiscoveredJob = {
  id?: string
  title?: string
  company?: string
  score?: number
  match_ratio?: number
  matched_skills?: string[]
  url?: string
  salary_range?: string
}

type DiscoverResult = {
  remoteok_count: number
  linkedin_count: number
  top_jobs: DiscoveredJob[]
  saved_to: string
}

export default function Discover() {
  const [keywords, setKeywords] = useState('AI engineer LLM machine learning agentic')
  const [topN, setTopN] = useState(5)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<DiscoverResult | null>(null)

  function handleDiscover() {
    setLoading(true)
    setError('')
    setResult(null)
    api.discover({ keywords, top_n: topN })
      .then(setResult)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  return (
    <div className="max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Discover</h1>
        <p className="text-slate-400 text-sm mt-1">Scrape fresh AI/ML leads from RemoteOK and LinkedIn</p>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 mb-6">
        <div className="space-y-4">
          <div>
            <label className="text-xs text-slate-400 font-medium uppercase tracking-wider block mb-2">Keywords</label>
            <input
              type="text"
              value={keywords}
              onChange={e => setKeywords(e.target.value)}
              disabled={loading}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 font-medium uppercase tracking-wider block mb-2">Top N results</label>
            <select
              value={topN}
              onChange={e => setTopN(Number(e.target.value))}
              disabled={loading}
              className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500 disabled:opacity-50"
            >
              {[3, 5, 10, 15, 20].map(n => (
                <option key={n} value={n}>{n} results</option>
              ))}
            </select>
          </div>
          <button
            onClick={handleDiscover}
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold px-6 py-3 rounded-xl text-sm transition-colors flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin inline-block" />
                Scraping… (~30s)
              </>
            ) : 'Run Discovery'}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm mb-6">{error}</div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'RemoteOK', value: result.remoteok_count },
              { label: 'LinkedIn', value: result.linkedin_count },
              { label: 'Top leads', value: result.top_jobs.length },
            ].map(s => (
              <div key={s.label} className="bg-slate-900 border border-slate-800 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-white">{s.value}</div>
                <div className="text-xs text-slate-500 mt-1">{s.label}</div>
              </div>
            ))}
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-800 text-xs text-slate-500">
              Top {result.top_jobs.length} leads
            </div>
            {result.top_jobs.map((j, i) => (
              <div key={i} className="flex items-start justify-between px-5 py-4 border-b border-slate-800/50 last:border-0">
                <div className="flex-1 min-w-0 mr-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-bold text-slate-500 text-xs">#{i + 1}</span>
                    <span className="text-white text-sm font-medium">{j.title ?? 'Untitled'}</span>
                  </div>
                  <div className="text-slate-400 text-xs mb-1.5">
                    {j.company ?? '—'}{j.salary_range ? ` · ${j.salary_range}` : ''}
                  </div>
                  {j.matched_skills && j.matched_skills.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {j.matched_skills.slice(0, 4).map(s => (
                        <span key={s} className="text-xs bg-blue-950/60 text-blue-400 px-1.5 py-0.5 rounded border border-blue-900/50">{s}</span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="shrink-0 flex flex-col items-end gap-2">
                  {j.score != null && (
                    <span className={`text-base font-bold ${j.score >= 80 ? 'text-green-400' : j.score >= 60 ? 'text-amber-400' : 'text-slate-400'}`}>
                      {j.score}
                    </span>
                  )}
                  {j.id && (
                    <Link href={`/jobs/${j.id}`} className="text-xs text-blue-400 hover:text-blue-300">Details →</Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
