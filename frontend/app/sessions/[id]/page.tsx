'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import api from '../../../lib/api'

type Checkpoint = Record<string, unknown>
type Gate = { gate_id: string; response: unknown }

export default function SessionDetail() {
  const params = useParams()
  const router = useRouter()
  const id = String(params.id)

  const [data, setData] = useState<{ checkpoints: Checkpoint[]; gates: Gate[] } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [gateInputs, setGateInputs] = useState<Record<string, string>>({})
  const [gateStatus, setGateStatus] = useState<Record<string, string>>({})

  const load = () => {
    api.session(id)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [id])

  function handleGateResponse(gateId: string, approve: boolean) {
    const value = gateInputs[gateId] ?? ''
    api.gateResponse(id, {
      gate_id: gateId,
      response: approve ? { approved: true, value } : { approved: false },
    })
      .then(() => setGateStatus(prev => ({ ...prev, [gateId]: approve ? 'approved' : 'rejected' })))
      .catch((e: Error) => setError(e.message))
  }

  function handleSubmit() {
    setSubmitting(true)
    api.submitSession(id)
      .then(() => load())
      .catch((e: Error) => setError(e.message))
      .finally(() => setSubmitting(false))
  }

  if (loading) return <div className="text-slate-500 text-sm py-12 text-center">Loading session…</div>
  if (error && !data) return <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm">{error}</div>
  if (!data) return null

  const latest = data.checkpoints[data.checkpoints.length - 1] ?? {}
  const pendingGates = data.gates.filter(g => !gateStatus[g.gate_id])

  return (
    <div className="max-w-3xl">
      <button onClick={() => router.back()} className="text-xs text-slate-500 hover:text-slate-300 mb-6 flex items-center gap-1">
        ← Sessions
      </button>

      <div className="mb-6">
        <h1 className="text-xl font-bold text-white font-mono break-all">{id}</h1>
        <p className="text-slate-400 text-sm mt-1">
          {data.checkpoints.length} checkpoints · {data.gates.length} gate responses
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-8">
        {(['status', 'step', 'platform'] as const).map(k => (
          <div key={k} className="bg-slate-900 border border-slate-800 rounded-xl p-4">
            <div className="text-xs text-slate-500 mb-1 uppercase tracking-wider">{k}</div>
            <div className="text-sm text-white font-medium">{String(latest[k] ?? '—')}</div>
          </div>
        ))}
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm mb-6">{error}</div>
      )}

      {pendingGates.length > 0 && (
        <section className="mb-8">
          <h2 className="text-sm font-semibold text-amber-400 uppercase tracking-wider mb-4">
            ⚠ HITL Gates Awaiting Response ({pendingGates.length})
          </h2>
          <div className="space-y-4">
            {pendingGates.map(g => (
              <div key={g.gate_id} className="bg-amber-950/20 border border-amber-800/50 rounded-xl p-5">
                <div className="text-sm font-semibold text-white mb-1">{g.gate_id}</div>
                <pre className="text-xs text-amber-400/80 mb-4 overflow-auto max-h-24 font-mono">
                  {JSON.stringify(g.response, null, 2).slice(0, 400)}
                </pre>
                <div className="flex gap-2 items-center">
                  <input
                    type="text"
                    placeholder="Override value (optional)"
                    value={gateInputs[g.gate_id] ?? ''}
                    onChange={e => setGateInputs(prev => ({ ...prev, [g.gate_id]: e.target.value }))}
                    className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-amber-500"
                  />
                  <button
                    onClick={() => handleGateResponse(g.gate_id, true)}
                    className="bg-green-700 hover:bg-green-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => handleGateResponse(g.gate_id, false)}
                    className="bg-red-800/60 hover:bg-red-700/60 text-red-300 text-sm font-medium px-4 py-2 rounded-lg border border-red-700/50 transition-colors"
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {String(latest.status) === 'draft_saved' && (
        <div className="mb-8">
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold px-6 py-3 rounded-xl text-sm transition-colors"
          >
            {submitting ? 'Submitting…' : 'Submit Application'}
          </button>
        </div>
      )}

      {data.checkpoints.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">
            Checkpoints ({data.checkpoints.length})
          </h2>
          <div className="space-y-2">
            {[...data.checkpoints].reverse().map((cp, i) => (
              <div key={i} className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-slate-600 font-mono">#{data.checkpoints.length - i}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    String(cp.status) === 'submitted' ? 'bg-green-900/60 text-green-400' :
                    String(cp.status) === 'hitl_pause' ? 'bg-amber-900/60 text-amber-400' :
                    'bg-slate-800 text-slate-400'
                  }`}>{String(cp.status ?? '—')}</span>
                </div>
                <pre className="text-xs text-slate-400 overflow-auto max-h-24 font-mono">
                  {JSON.stringify(cp, null, 2).slice(0, 600)}
                </pre>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
