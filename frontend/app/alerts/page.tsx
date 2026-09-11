'use client'

// JobRight-parity UI addition: notifications center for high-match job alerts.
// Additive page — complements the dashboard banner with full list management.

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import api from '../../lib/api'

type Alert = {
  id: string
  title?: string
  company?: string
  url?: string
  score?: number
  location?: string
  created_at?: string
  read?: boolean
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showRead, setShowRead] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    api.alerts({ limit: 100 })
      .then(d => { setAlerts(d.alerts ?? []); setUnread(d.unread_count ?? 0) })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  function markRead(id: string) {
    api.markAlertRead(id).then(load).catch((e: Error) => setError(e.message))
  }

  function markAll() {
    api.markAllAlertsRead().then(load).catch((e: Error) => setError(e.message))
  }

  const visible = showRead ? alerts : alerts.filter(a => !a.read)

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">🔔 Alerts</h1>
          <p className="text-slate-400 text-sm mt-1">
            High-match jobs (score 75+) found by your scans — apply early while they&apos;re fresh.
          </p>
        </div>
        {unread > 0 && (
          <button onClick={markAll}
            className="text-xs bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-3 py-2 rounded-lg transition-colors">
            Mark all read ({unread})
          </button>
        )}
      </div>

      {error && <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm mb-6">{error}</div>}

      <div className="flex gap-2 mb-4">
        <button onClick={() => setShowRead(true)}
          className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${showRead ? 'bg-blue-950/60 border-blue-800 text-blue-300' : 'border-slate-800 text-slate-500 hover:text-slate-300'}`}>
          All ({alerts.length})
        </button>
        <button onClick={() => setShowRead(false)}
          className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${!showRead ? 'bg-blue-950/60 border-blue-800 text-blue-300' : 'border-slate-800 text-slate-500 hover:text-slate-300'}`}>
          Unread ({unread})
        </button>
      </div>

      {loading ? (
        <div className="text-slate-500 text-sm py-12 text-center">Loading alerts…</div>
      ) : visible.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl py-16 text-center">
          <div className="text-3xl mb-3">🔭</div>
          <div className="text-slate-500 text-sm">{showRead ? 'No alerts yet' : 'All caught up — no unread alerts'}</div>
          <div className="text-slate-600 text-xs mt-1 mb-4">
            Run a scan or discover new jobs — anything scoring 75+ lands here automatically.
          </div>
          <Link href="/" className="text-xs text-blue-400 hover:text-blue-300">Run Discover from the dashboard →</Link>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="divide-y divide-slate-800/50">
            {visible.map(a => (
              <div key={a.id} className={`px-5 py-4 flex items-start justify-between gap-4 ${!a.read ? 'bg-amber-950/10' : ''}`}>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    {!a.read && <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />}
                    <span className="text-sm text-white font-medium">{a.title ?? 'Untitled role'}</span>
                    {typeof a.score === 'number' && (
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${
                        a.score >= 85 ? 'bg-green-900/50 text-green-400 border-green-800' : 'bg-amber-900/50 text-amber-400 border-amber-800'
                      }`}>{a.score}</span>
                    )}
                  </div>
                  <div className="text-xs text-slate-500 mt-1 flex flex-wrap gap-3">
                    <span>{a.company ?? '—'}</span>
                    {a.location && <span>{a.location}</span>}
                    {a.created_at && <span>{new Date(a.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>}
                  </div>
                </div>
                <div className="shrink-0 flex items-center gap-2">
                  {a.url && (
                    <a href={a.url} target="_blank" rel="noopener noreferrer"
                      className="text-xs bg-blue-600 hover:bg-blue-500 text-white rounded-lg px-3 py-1.5 transition-colors">
                      View posting ↗
                    </a>
                  )}
                  <Link href="/jobs"
                    className="text-xs border border-slate-700 text-slate-400 hover:text-white hover:border-slate-600 rounded-lg px-3 py-1.5 transition-colors">
                    In feed
                  </Link>
                  {!a.read && (
                    <button onClick={() => markRead(a.id)} title="Mark as read"
                      className="text-xs text-slate-500 hover:text-slate-300 px-1 transition-colors">
                      ✓
                    </button>
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
