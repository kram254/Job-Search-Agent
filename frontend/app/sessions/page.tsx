'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import api from '../../lib/api'

type Session = {
  session_id: string
  checkpoints: number
  latest?: { step?: string; status?: string; title?: string }
}

export default function Sessions() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    api.sessions()
      .then(d => setSessions(d.sessions ?? []))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Sessions</h1>
          <p className="text-slate-400 text-sm mt-1">Active application sessions and HITL gates</p>
        </div>
        <button
          onClick={load}
          className="text-xs bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-3 py-2 rounded-lg transition-colors"
        >
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="text-slate-500 text-sm py-12 text-center">Loading sessions…</div>
      ) : sessions.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl py-16 text-center">
          <div className="text-slate-500 text-sm">No sessions yet</div>
          <div className="text-slate-600 text-xs mt-1">Apply to a job to start a session</div>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="divide-y divide-slate-800">
            {sessions.map(s => {
              const latest = s.latest
              return (
                <Link
                  key={s.session_id}
                  href={`/sessions/${s.session_id}`}
                  className="flex items-center justify-between px-5 py-4 hover:bg-slate-800/50 transition-colors group"
                >
                  <div>
                    <div className="text-sm text-white font-mono group-hover:text-blue-300 transition-colors">
                      {s.session_id}
                    </div>
                    <div className="text-xs text-slate-500 mt-1 flex items-center gap-2">
                      <span>{s.checkpoints} checkpoint{s.checkpoints !== 1 ? 's' : ''}</span>
                      {latest?.step && <span>· {latest.step}</span>}
                      {latest?.title && <span>· {latest.title}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {latest?.status && (
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        latest.status === 'submitted' ? 'bg-green-900/60 text-green-400' :
                        latest.status === 'hitl_pause' ? 'bg-amber-900/60 text-amber-400' :
                        latest.status === 'running' ? 'bg-blue-900/60 text-blue-400' :
                        'bg-slate-800 text-slate-400'
                      }`}>
                        {latest.status}
                      </span>
                    )}
                    <span className="text-slate-600 text-sm">→</span>
                  </div>
                </Link>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
