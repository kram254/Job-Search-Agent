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
  location?: string
  source?: string
}

type RunHistory = {
  ts: string
  remoteok: number
  linkedin: number
  top: DiscoveredJob[]
}

export default function Discover() {
  const [keywords, setKeywords] = useState('AI engineer LLM machine learning agentic')
  const [topN, setTopN] = useState(5)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [latest, setLatest] = useState<RunHistory | null>(null)
  const [history, setHistory] = useState<RunHistory[]>([])
  const [log, setLog] = useState<string[]>([])

  function addLog(msg: string) {
    setLog(prev => [...prev, `${new Date().toLocaleTimeString()} — ${msg}`])
  }

  function handleDiscover() {
    setLoading(true)
    setError('')
    setLog([])
    addLog('Starting discovery run…')
    addLog('Fetching RemoteOK listings…')

    api.discover({ keywords, top_n: topN })
      .then(r => {
        addLog(`RemoteOK: ${r.remoteok_count} listings scored`)
        addLog(`LinkedIn: ${r.linkedin_count} listings scored`)
        addLog(`Top ${r.top_jobs?.length ?? 0} leads saved to output/${r.saved_to?.split('/').pop() ?? ''}`)
        const run: RunHistory = {
          ts: new Date().toLocaleString(),
          remoteok: r.remoteok_count ?? 0,
          linkedin: r.linkedin_count ?? 0,
          top: r.top_jobs ?? [],
        }
        setLatest(run)
        setHistory(prev => [run, ...prev.slice(0, 4)])
      })
      .catch((e: Error) => { setError(e.message); addLog(`Error: ${e.message}`) })
      .finally(() => setLoading(false))
  }

  return (
    <div className="max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Discover</h1>
        <p className="text-slate-400 text-sm mt-1">Scrape fresh AI/ML leads from RemoteOK and LinkedIn in real-time</p>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 mb-6">
        <div className="space-y-4">
          <div>
            <label className="text-xs text-slate-400 font-medium uppercase tracking-wider block mb-2">Search Keywords</label>
            <input type="text" value={keywords} onChange={e => setKeywords(e.target.value)} disabled={loading}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-60" />
          </div>
          <div className="flex items-center gap-4">
            <div>
              <label className="text-xs text-slate-400 font-medium uppercase tracking-wider block mb-2">Top N</label>
              <select value={topN} onChange={e => setTopN(Number(e.target.value))} disabled={loading}
                className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500 disabled:opacity-60">
                {[3, 5, 10, 15, 20].map(n => <option key={n} value={n}>{n} results</option>)}
              </select>
            </div>
            <div className="flex-1 flex items-end pb-0.5">
              <button onClick={handleDiscover} disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white font-semibold px-6 py-2.5 rounded-xl text-sm transition-colors flex items-center justify-center gap-2 mt-6">
                {loading ? (
                  <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin inline-block" />Scraping (30–60s)…</>
                ) : '✦ Run Discovery'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {log.length > 0 && (
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 mb-6 font-mono text-xs text-slate-400 space-y-1 max-h-32 overflow-y-auto">
          {log.map((l, i) => <div key={i}>{l}</div>)}
          {loading && <div className="text-blue-400 animate-pulse">● Running…</div>}
        </div>
      )}

      {error && <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm mb-6">{error}</div>}

      {latest && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Latest Run — {latest.ts}</h2>
              <div className="text-xs text-slate-500 mt-0.5">
                {latest.remoteok} from RemoteOK · {latest.linkedin} from LinkedIn
              </div>
            </div>
            <Link href="/jobs" className="text-xs text-blue-400 hover:text-blue-300 transition-colors">All Jobs →</Link>
          </div>

          <div className="grid grid-cols-3 gap-3 mb-4">
            {[
              { label: 'RemoteOK', value: latest.remoteok, color: 'text-orange-400' },
              { label: 'LinkedIn', value: latest.linkedin, color: 'text-blue-400' },
              { label: 'Top Leads', value: latest.top.length, color: 'text-green-400' },
            ].map(s => (
              <div key={s.label} className="bg-slate-900 border border-slate-800 rounded-xl p-4 text-center">
                <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
                <div className="text-xs text-slate-500 mt-1">{s.label}</div>
              </div>
            ))}
          </div>

          {latest.top.length > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
              <div className="text-xs text-slate-500 px-5 py-3 border-b border-slate-800">
                Top {latest.top.length} scored leads
              </div>
              {latest.top.map((j, i) => (
                <div key={i} className="flex items-start justify-between px-5 py-4 border-b border-slate-800/50 last:border-0">
                  <div className="flex-1 min-w-0 mr-4">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs text-slate-600 font-mono">#{i + 1}</span>
                      <span className="text-sm text-white font-medium">{j.title ?? 'Untitled'}</span>
                      {j.source && <span className="text-xs text-slate-600 capitalize">{j.source}</span>}
                    </div>
                    <div className="text-xs text-slate-400">{j.company ?? '—'}{j.salary_range ? ` · ${j.salary_range}` : ''}</div>
                    {j.matched_skills && j.matched_skills.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {j.matched_skills.slice(0, 4).map(s => (
                          <span key={s} className="text-xs bg-blue-950/60 text-blue-400 px-1.5 py-0.5 rounded border border-blue-900/40">{s}</span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="shrink-0 flex flex-col items-end gap-2">
                    {j.score != null && (
                      <span className={`text-sm font-bold ${j.score >= 80 ? 'text-green-400' : j.score >= 60 ? 'text-amber-400' : 'text-slate-400'}`}>
                        {j.score}
                      </span>
                    )}
                    {j.id && (
                      <Link href={`/jobs/${j.id}`} className="text-xs text-blue-400 hover:text-blue-300 transition-colors">
                        Details →
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {history.length > 1 && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="text-xs text-slate-500 px-5 py-3 border-b border-slate-800">Run History (this session)</div>
          <div className="divide-y divide-slate-800/50">
            {history.slice(1).map((h, i) => (
              <div key={i} className="flex items-center justify-between px-5 py-3 text-xs">
                <span className="text-slate-500">{h.ts}</span>
                <span className="text-slate-400">{h.remoteok} RemoteOK · {h.linkedin} LinkedIn</span>
                <span className="text-green-400">{h.top.length} leads</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!latest && !loading && (
        <div className="bg-slate-900/50 border border-dashed border-slate-700 rounded-xl p-8 text-center">
          <div className="text-slate-500 text-sm">No discovery runs yet this session</div>
          <div className="text-slate-600 text-xs mt-1">Click Run Discovery to fetch fresh AI/ML job leads</div>
        </div>
      )}
    </div>
  )
}
