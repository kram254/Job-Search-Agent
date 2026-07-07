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

type Stats = { total?: number; due_count?: number; overdue_count?: number }

export default function FollowUps() {
  const [due, setDue] = useState<FollowUp[]>([])
  const [active, setActive] = useState<FollowUp[]>([])
  const [stats, setStats] = useState<Stats>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ job_id: '', company: '', title: '' })
  const [tracking, setTracking] = useState(false)

  const load = () => {
    setLoading(true)
    api.followups()
      .then(d => { setDue(d.due ?? []); setActive(d.active ?? []); setStats(d.stats ?? {}) })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  function handleTrack() {
    if (!form.job_id) return
    setTracking(true)
    api.trackFollowup(form)
      .then(() => { setShowForm(false); setForm({ job_id: '', company: '', title: '' }); load() })
      .catch((e: Error) => setError(e.message))
      .finally(() => setTracking(false))
  }

  const allItems = [...due, ...active.filter(a =>
    !due.some(d => d.record_id === a.record_id)
  )]

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Follow-ups</h1>
          <p className="text-slate-400 text-sm mt-1">
            {stats.total ?? 0} tracked · {stats.due_count ?? 0} due · {stats.overdue_count ?? 0} overdue
          </p>
        </div>
        <button
          onClick={() => setShowForm(v => !v)}
          className="text-sm bg-blue-600 hover:bg-blue-500 text-white font-medium px-4 py-2 rounded-xl transition-colors"
        >
          + Track
        </button>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm mb-6">{error}</div>
      )}

      {showForm && (
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 mb-6 space-y-3">
          <div className="text-sm font-semibold text-white">Track Follow-up</div>
          {[
            { key: 'job_id', label: 'Job ID', placeholder: 'e.g. 12345' },
            { key: 'company', label: 'Company', placeholder: 'Company name' },
            { key: 'title', label: 'Role Title', placeholder: 'e.g. Senior AI Engineer' },
          ].map(f => (
            <div key={f.key}>
              <label className="text-xs text-slate-400 block mb-1">{f.label}</label>
              <input
                type="text"
                value={form[f.key as keyof typeof form]}
                onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                placeholder={f.placeholder}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          ))}
          <div className="flex gap-2 pt-1">
            <button
              onClick={handleTrack}
              disabled={tracking || !form.job_id}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
            >
              {tracking ? 'Saving…' : 'Save'}
            </button>
            <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-white text-sm px-4 py-2">
              Cancel
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-slate-500 text-sm py-12 text-center">Loading…</div>
      ) : allItems.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl py-16 text-center">
          <div className="text-slate-500 text-sm">No follow-ups yet</div>
          <div className="text-slate-600 text-xs mt-1">Track applications to get follow-up reminders</div>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="divide-y divide-slate-800">
            {allItems.map((f, i) => {
              const isDue = due.some(d => d.record_id === f.record_id)
              return (
                <div key={f.record_id ?? i} className="flex items-center justify-between px-5 py-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white text-sm font-medium">{f.title ?? '—'}</span>
                      {isDue && (
                        <span className="text-xs bg-amber-900/60 text-amber-400 px-2 py-0.5 rounded-full">Due</span>
                      )}
                    </div>
                    <div className="text-slate-400 text-xs mt-0.5">{f.company ?? '—'}</div>
                  </div>
                  <div className="text-right">
                    {f.next_followup && (
                      <div className="text-xs text-slate-400">{new Date(f.next_followup).toLocaleDateString()}</div>
                    )}
                    {f.archetype && (
                      <div className="text-xs text-slate-600 mt-0.5">{f.archetype}</div>
                    )}
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
