'use client'

import { useEffect, useState } from 'react'
import api from '../../lib/api'

type Overview = Record<string, unknown>
type Patterns = Record<string, unknown>

export default function Analytics() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [patterns, setPatterns] = useState<Patterns | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([api.analyticsOverview(), api.analyticsPatterns()])
      .then(([o, p]) => {
        if (o.status === 'fulfilled') setOverview(o.value)
        if (p.status === 'fulfilled') setPatterns(p.value)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-slate-500 text-sm py-12 text-center">Loading analytics…</div>

  const scalars = Object.entries(overview ?? {}).filter(([, v]) => typeof v !== 'object')
  const hasData = scalars.length > 0

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Analytics</h1>
        <p className="text-slate-400 text-sm mt-1">Application performance and pattern analysis</p>
      </div>

      {!hasData ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl py-16 text-center">
          <div className="text-slate-500 text-sm">No analytics data yet</div>
          <div className="text-slate-600 text-xs mt-1">Complete applications to see patterns here</div>
        </div>
      ) : (
        <div className="space-y-8">
          <section>
            <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">Overview</h2>
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
              {scalars.map(([k, v]) => (
                <div key={k} className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                  <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">{k.replace(/_/g, ' ')}</div>
                  <div className="text-xl font-bold text-white">{String(v)}</div>
                </div>
              ))}
            </div>
          </section>

          {patterns && Object.keys(patterns).length > 0 && (
            <section>
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">Patterns</h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {Object.entries(patterns).map(([k, v]) => (
                  <div key={k} className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                    <h3 className="text-xs text-slate-400 uppercase tracking-wider mb-3">{k.replace(/_/g, ' ')}</h3>
                    <pre className="text-xs text-slate-300 overflow-auto max-h-40 font-mono">
                      {JSON.stringify(v, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  )
}
