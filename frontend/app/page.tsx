'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import api from '../lib/api'

type AppRecord = { title?: string; company?: string; status?: string; applied_at?: string }
type SessionRecord = { session_id: string; checkpoints: number; latest?: { step?: string } }

export default function Dashboard() {
  const [jobs, setJobs] = useState<{ total?: number } | null>(null)
  const [apps, setApps] = useState<{ applications: AppRecord[] } | null>(null)
  const [sessions, setSessions] = useState<{ sessions: SessionRecord[] } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      api.jobs({ limit: 1 }),
      api.applications(),
      api.sessions(),
    ]).then(([j, a, s]) => {
      if (j.status === 'fulfilled') setJobs(j.value)
      if (a.status === 'fulfilled') setApps(a.value)
      if (s.status === 'fulfilled') setSessions(s.value)
      setLoading(false)
    })
  }, [])

  const stats = [
    { label: 'Total Jobs', value: loading ? '—' : String(jobs?.total ?? 0) },
    { label: 'Applications', value: loading ? '—' : String(apps?.applications?.length ?? 0) },
    { label: 'Sessions', value: loading ? '—' : String(sessions?.sessions?.length ?? 0) },
  ]

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-slate-400 text-sm mt-1">AI-powered job application overview</p>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-10">
        {stats.map(s => (
          <div key={s.label} className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="text-slate-500 text-xs uppercase tracking-wider mb-2">{s.label}</div>
            <div className="text-3xl font-bold text-white">{s.value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
            <h2 className="text-sm font-semibold text-white">Recent Applications</h2>
            <Link href="/applications" className="text-xs text-blue-400 hover:text-blue-300">View all →</Link>
          </div>
          {!apps || apps.applications.length === 0 ? (
            <div className="px-5 py-8 text-slate-500 text-sm text-center">No applications yet</div>
          ) : (
            <div className="divide-y divide-slate-800">
              {apps.applications.slice(0, 6).map((a, i) => (
                <div key={i} className="flex items-center justify-between px-5 py-3">
                  <div>
                    <div className="text-sm text-white">{a.title ?? '—'}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{a.company ?? '—'}</div>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    a.status === 'submitted' ? 'bg-green-900/60 text-green-400' :
                    a.status === 'draft_saved' ? 'bg-blue-900/60 text-blue-400' :
                    'bg-slate-800 text-slate-400'
                  }`}>{a.status ?? '—'}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
            <h2 className="text-sm font-semibold text-white">Active Sessions</h2>
            <Link href="/sessions" className="text-xs text-blue-400 hover:text-blue-300">View all →</Link>
          </div>
          {!sessions || sessions.sessions.length === 0 ? (
            <div className="px-5 py-8 text-slate-500 text-sm text-center">No sessions yet</div>
          ) : (
            <div className="divide-y divide-slate-800">
              {sessions.sessions.slice(0, 6).map(s => (
                <div key={s.session_id} className="flex items-center justify-between px-5 py-3">
                  <div>
                    <div className="text-sm text-white font-mono">{s.session_id.slice(0, 24)}…</div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      {s.checkpoints} checkpoint{s.checkpoints !== 1 ? 's' : ''} · {s.latest?.step ?? 'initializing'}
                    </div>
                  </div>
                  <Link href={`/sessions/${s.session_id}`} className="text-xs text-blue-400 hover:text-blue-300">Open →</Link>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
