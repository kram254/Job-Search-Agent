'use client'

import { useEffect, useState } from 'react'
import api from '../../lib/api'

type FollowUp = {
  record_id?: string
  job_id?: string
  company?: string
  title?: string
  applied_at?: string
  next_followup?: string
  archetype?: string
  status?: string
}

export default function FollowUps() {
  const [due, setDue] = useState<FollowUp[]>([])
  const [active, setActive] = useState<FollowUp[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ job_id: '', company: '', title: '', applied_at: '' })
  const [tracking, setTracking] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    api.followups()
      .then(d => { setDue(d.due ?? []); setActive(d.active ?? []) })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  function handleTrack() {
    if (!form.job_id) return
    setTracking(true)
    api.trackFollowup({
      job_id: form.job_id,
      company: form.company,
      title: form.title,
      applied_at: form.applied_at || undefined,
    })
      .then(() => { setShowForm(false); setForm({ job_id: '', company: '', title: '', applied_at: '' }); load() })
      .catch((e: Error) => setError(e.message))
      .finally(() => setTracking(false))
  }

  const allItems = [
    ...due,
    ...active.filter(a => !due.some(d => d.record_id === a.record_id)),
  ]

  const dueCount = due.length
  const total = allItems.length
  const today = new Date()
  const overdueCount = due.filter(f => f.next_followup && new Date(f.next_followup) < today).length

  function copyDraftEmail(f: FollowUp) {
    const text = `Subject: Following up — ${f.title ?? 'Role'} at ${f.company ?? 'Company'}

Hi ${f.company ?? ''} team,

I wanted to follow up on my application for the ${f.title ?? 'role'} position. I remain genuinely interested and would love to know if you have any updates on the next steps.

I'm happy to provide any additional information you might need.

Best regards,
Emmanuel Ndaliro`
    navigator.clipboard.writeText(text).then(() => {
      setCopied(f.record_id ?? null)
      setTimeout(() => setCopied(null), 2000)
    })
  }

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Follow-ups</h1>
          <p className="text-slate-400 text-sm mt-1">
            <span className="text-white font-medium">{total}</span> tracked ·{' '}
            <span className={dueCount > 0 ? 'text-amber-400 font-medium' : ''}>{dueCount} due</span>
            {overdueCount > 0 && <span className="text-red-400 font-medium ml-1">· {overdueCount} overdue</span>}
          </p>
        </div>
        <button onClick={() => setShowForm(v => !v)}
          className="text-sm bg-blue-600 hover:bg-blue-500 text-white font-medium px-4 py-2 rounded-xl transition-colors">
          + Track
        </button>
      </div>

      {error && <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm mb-6">{error}</div>}

      {showForm && (
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 mb-6 space-y-3">
          <div className="text-sm font-semibold text-white">Track a Follow-up</div>
          <div className="grid grid-cols-2 gap-3">
            {[
              { key: 'job_id', label: 'Job ID *', placeholder: 'e.g. 4378806447' },
              { key: 'company', label: 'Company', placeholder: 'Company name' },
              { key: 'title', label: 'Role Title', placeholder: 'e.g. Senior AI Engineer' },
              { key: 'applied_at', label: 'Applied Date', placeholder: 'YYYY-MM-DD' },
            ].map(f => (
              <div key={f.key}>
                <label className="text-xs text-slate-400 block mb-1">{f.label}</label>
                <input type="text" value={form[f.key as keyof typeof form]}
                  onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                  placeholder={f.placeholder}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500" />
              </div>
            ))}
          </div>
          <div className="flex gap-2 pt-1">
            <button onClick={handleTrack} disabled={tracking || !form.job_id}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
              {tracking ? 'Saving…' : 'Save'}
            </button>
            <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-white text-sm px-4 py-2 transition-colors">Cancel</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-slate-500 text-sm py-12 text-center">Loading…</div>
      ) : allItems.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl py-16 text-center">
          <div className="text-slate-500 text-sm">No follow-ups tracked yet</div>
          <div className="text-slate-600 text-xs mt-1">Add applications here to get follow-up reminders</div>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="text-xs text-slate-600 px-5 py-3 border-b border-slate-800">{allItems.length} tracked applications</div>
          <div className="divide-y divide-slate-800/50">
            {allItems.map((f, i) => {
              const isDue = due.some(d => d.record_id === f.record_id)
              const isOverdue = isDue && f.next_followup && new Date(f.next_followup) < today
              return (
                <div key={f.record_id ?? i} className={`px-5 py-4 ${isOverdue ? 'bg-red-950/10' : isDue ? 'bg-amber-950/10' : ''}`}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0 mr-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm text-white font-medium">{f.title ?? '—'}</span>
                        {isOverdue && <span className="text-xs bg-red-900/60 text-red-400 px-2 py-0.5 rounded-full border border-red-800">Overdue</span>}
                        {isDue && !isOverdue && <span className="text-xs bg-amber-900/60 text-amber-400 px-2 py-0.5 rounded-full border border-amber-800">Due</span>}
                        {f.archetype && <span className="text-xs text-slate-500">{f.archetype}</span>}
                      </div>
                      <div className="text-xs text-slate-500 mt-1 flex flex-wrap gap-3">
                        <span>{f.company ?? '—'}</span>
                        {f.applied_at && <span>Applied {new Date(f.applied_at).toLocaleDateString()}</span>}
                        {f.next_followup && (
                          <span className={isOverdue ? 'text-red-400' : isDue ? 'text-amber-400' : ''}>
                            Follow up {new Date(f.next_followup).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="shrink-0 flex gap-2">
                      <button onClick={() => copyDraftEmail(f)}
                        className={`text-xs px-2.5 py-1.5 rounded-lg border transition-colors ${
                          copied === (f.record_id ?? null)
                            ? 'border-green-700 bg-green-900/40 text-green-400'
                            : 'border-slate-700 text-slate-400 hover:border-slate-600 hover:text-white'
                        }`}>
                        {copied === (f.record_id ?? null) ? '✓ Copied' : '✉ Draft'}
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
