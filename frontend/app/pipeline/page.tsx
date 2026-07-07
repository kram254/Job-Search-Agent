'use client'

import { useEffect, useState } from 'react'
import api from '../../lib/api'

type PipelineEntry = {
  id: string
  url?: string
  title?: string
  status?: string
  created_at?: string
  result?: Record<string, unknown>
}

type Stats = {
  total?: number
  pending?: number
  processing?: number
  done?: number
  failed?: number
}

export default function Pipeline() {
  const [entries, setEntries] = useState<PipelineEntry[]>([])
  const [stats, setStats] = useState<Stats>({})
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [addUrl, setAddUrl] = useState('')
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState('')

  const load = () => {
    setLoading(true)
    api.pipeline()
      .then(d => { setEntries(d.entries ?? []); setStats(d.stats ?? {}) })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  function handleProcess() {
    setProcessing(true)
    api.processPipeline()
      .then(() => load())
      .catch((e: Error) => setError(e.message))
      .finally(() => setProcessing(false))
  }

  function handleAdd() {
    if (!addUrl.trim()) return
    setAdding(true)
    api.addToPipeline({ url: addUrl.trim() })
      .then(() => { setAddUrl(''); load() })
      .catch((e: Error) => setError(e.message))
      .finally(() => setAdding(false))
  }

  const statusColor = (s?: string) => {
    if (s === 'done') return 'bg-green-900/60 text-green-400'
    if (s === 'processing') return 'bg-blue-900/60 text-blue-400'
    if (s === 'failed') return 'bg-red-900/60 text-red-400'
    return 'bg-slate-800 text-slate-400'
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Pipeline</h1>
          <p className="text-slate-400 text-sm mt-1">
            {stats.total ?? 0} total · {stats.pending ?? 0} pending · {stats.done ?? 0} done
          </p>
        </div>
        <button
          onClick={handleProcess}
          disabled={processing || (stats.pending ?? 0) === 0}
          className="text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium px-4 py-2 rounded-xl transition-colors"
        >
          {processing ? 'Processing…' : `Process pending (${stats.pending ?? 0})`}
        </button>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm mb-6">{error}</div>
      )}

      <div className="flex gap-2 mb-6">
        <input
          type="text"
          value={addUrl}
          onChange={e => setAddUrl(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleAdd()}
          placeholder="Paste a job URL to add to the pipeline…"
          className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
        />
        <button
          onClick={handleAdd}
          disabled={adding || !addUrl.trim()}
          className="bg-slate-800 hover:bg-slate-700 disabled:opacity-50 border border-slate-700 text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors"
        >
          {adding ? 'Adding…' : 'Add'}
        </button>
      </div>

      {loading ? (
        <div className="text-slate-500 text-sm py-12 text-center">Loading…</div>
      ) : entries.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl py-16 text-center">
          <div className="text-slate-500 text-sm">Pipeline is empty</div>
          <div className="text-slate-600 text-xs mt-1">Add job URLs above or run a scan to populate it</div>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800">
                <th className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">URL / Title</th>
                <th className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">Status</th>
                <th className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">Score</th>
                <th className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">Added</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(e => (
                <tr key={e.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                  <td className="px-5 py-3">
                    <div className="text-white text-xs font-medium truncate max-w-xs">{e.title || e.url || e.id}</div>
                    {e.url && e.title && <div className="text-slate-500 text-xs truncate max-w-xs">{e.url}</div>}
                  </td>
                  <td className="px-5 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${statusColor(e.status)}`}>
                      {e.status ?? '—'}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-slate-300 text-xs">
                    {e.result ? String((e.result as Record<string, unknown>).global_score ?? '—') : '—'}
                  </td>
                  <td className="px-5 py-3 text-slate-500 text-xs">
                    {e.created_at ? new Date(e.created_at).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
