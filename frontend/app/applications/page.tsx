'use client'

import { useEffect, useState } from 'react'
import api from '../../lib/api'

type Application = {
  title?: string
  company?: string
  status?: string
  applied_at?: string
  archetype?: string
}

export default function Applications() {
  const [applications, setApplications] = useState<Application[]>([])
  const [stats, setStats] = useState<Record<string, unknown>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.applications()
      .then(d => { setApplications(d.applications ?? []); setStats(d.stats ?? {}) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-slate-500 text-sm py-12 text-center">Loading…</div>

  const statEntries = Object.entries(stats).filter(([, v]) => typeof v !== 'object').slice(0, 4)

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Applications</h1>
        <p className="text-slate-400 text-sm mt-1">{applications.length} total applications tracked</p>
      </div>

      {statEntries.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
          {statEntries.map(([k, v]) => (
            <div key={k} className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">{k.replace(/_/g, ' ')}</div>
              <div className="text-xl font-bold text-white">{String(v)}</div>
            </div>
          ))}
        </div>
      )}

      {applications.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl py-16 text-center">
          <div className="text-slate-500 text-sm">No applications yet</div>
          <div className="text-slate-600 text-xs mt-1">Apply to jobs to track them here</div>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800">
                <th className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">Role</th>
                <th className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">Company</th>
                <th className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">Status</th>
                <th className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">Archetype</th>
                <th className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">Date</th>
              </tr>
            </thead>
            <tbody>
              {applications.map((a, i) => (
                <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                  <td className="px-5 py-3 text-white">{a.title ?? '—'}</td>
                  <td className="px-5 py-3 text-slate-300">{a.company ?? '—'}</td>
                  <td className="px-5 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      a.status === 'submitted' ? 'bg-green-900/60 text-green-400' :
                      a.status === 'draft_saved' ? 'bg-blue-900/60 text-blue-400' :
                      'bg-slate-800 text-slate-400'
                    }`}>{a.status ?? '—'}</span>
                  </td>
                  <td className="px-5 py-3 text-slate-400 text-xs">{a.archetype ?? '—'}</td>
                  <td className="px-5 py-3 text-slate-500 text-xs">
                    {a.applied_at ? new Date(a.applied_at).toLocaleDateString() : '—'}
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
