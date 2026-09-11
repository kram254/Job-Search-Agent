'use client'

// JobRight-parity UI addition: interview scheduling and management.
// Additive page — the dashboard shows upcoming interviews; this one creates,
// completes and cancels them.

import { useEffect, useState, useCallback } from 'react'
import api from '../../lib/api'

type Interview = {
  id: string
  job_id?: string
  title?: string
  company?: string
  scheduled_at?: string
  interview_type?: string
  contact_name?: string
  notes?: string
  status?: string
}

const INTERVIEW_TYPES = ['screening', 'technical', 'system_design', 'behavioral', 'final', 'other']

const TYPE_COLORS: Record<string, string> = {
  screening: 'bg-blue-900/60 text-blue-400',
  technical: 'bg-purple-900/60 text-purple-300',
  system_design: 'bg-pink-900/60 text-pink-300',
  behavioral: 'bg-teal-900/60 text-teal-300',
  final: 'bg-red-900/60 text-red-300',
  other: 'bg-slate-800 text-slate-400',
}

export default function InterviewsPage() {
  const [interviews, setInterviews] = useState<Interview[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    job_id: '', company: '', title: '',
    scheduled_at: '', interview_type: 'screening',
    contact_name: '', notes: '',
  })

  const load = useCallback(() => {
    setLoading(true)
    api.interviews()
      .then(d => setInterviews(d.interviews ?? []))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  function handleAdd() {
    if (!form.job_id || !form.scheduled_at) return
    setSaving(true)
    api.addInterview({
      ...form,
      scheduled_at: new Date(form.scheduled_at).toISOString(),
    })
      .then(() => { setShowForm(false); setForm({ job_id: '', company: '', title: '', scheduled_at: '', interview_type: 'screening', contact_name: '', notes: '' }); load() })
      .catch((e: Error) => setError(e.message))
      .finally(() => setSaving(false))
  }

  function setStatus(id: string, status: string) {
    api.updateInterviewStatus(id, status).then(load).catch((e: Error) => setError(e.message))
  }

  const upcoming = interviews.filter(i => i.status === 'scheduled')
  const past = interviews.filter(i => i.status !== 'scheduled').reverse()

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Interviews</h1>
          <p className="text-slate-400 text-sm mt-1">
            <span className="text-white font-medium">{upcoming.length}</span> scheduled
          </p>
        </div>
        <button onClick={() => setShowForm(v => !v)}
          className="text-sm bg-blue-600 hover:bg-blue-500 text-white font-medium px-4 py-2 rounded-xl transition-colors">
          + Schedule
        </button>
      </div>

      {error && <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm mb-6">{error}</div>}

      {showForm && (
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 mb-6 space-y-3">
          <div className="text-sm font-semibold text-white">Schedule an Interview</div>
          <div className="grid grid-cols-2 gap-3">
            {[
              { key: 'job_id', label: 'Job ID *', placeholder: 'e.g. 4380364969' },
              { key: 'company', label: 'Company', placeholder: 'Company name' },
              { key: 'title', label: 'Role Title', placeholder: 'e.g. Senior AI Engineer' },
              { key: 'contact_name', label: 'Contact', placeholder: 'Interviewer name (optional)' },
            ].map(f => (
              <div key={f.key}>
                <label className="text-xs text-slate-400 block mb-1">{f.label}</label>
                <input type="text" value={form[f.key as keyof typeof form]}
                  onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                  placeholder={f.placeholder}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500" />
              </div>
            ))}
            <div>
              <label className="text-xs text-slate-400 block mb-1">When *</label>
              <input type="datetime-local" value={form.scheduled_at}
                onChange={e => setForm(p => ({ ...p, scheduled_at: e.target.value }))}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Type</label>
              <select value={form.interview_type}
                onChange={e => setForm(p => ({ ...p, interview_type: e.target.value }))}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500">
                {INTERVIEW_TYPES.map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1">Notes</label>
            <textarea value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))}
              rows={2} placeholder="Prep notes, format, links…"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500" />
          </div>
          <div className="flex gap-2 pt-1">
            <button onClick={handleAdd} disabled={saving || !form.job_id || !form.scheduled_at}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-white text-sm px-4 py-2 transition-colors">Cancel</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-slate-500 text-sm py-12 text-center">Loading…</div>
      ) : interviews.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl py-16 text-center">
          <div className="text-3xl mb-3">📅</div>
          <div className="text-slate-500 text-sm">No interviews scheduled yet</div>
          <div className="text-slate-600 text-xs mt-1">When a recruiter responds, schedule it here to keep your pipeline organized.</div>
        </div>
      ) : (
        <div className="space-y-6">
          {upcoming.length > 0 && (
            <div>
              <div className="text-xs text-slate-500 uppercase tracking-widest mb-3">Upcoming</div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
                <div className="divide-y divide-slate-800/50">
                  {upcoming.map(iv => (
                    <div key={iv.id} className="px-5 py-4">
                      <div className="flex items-start justify-between">
                        <div className="min-w-0 flex-1 mr-3">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm text-white font-medium">{iv.title ?? '—'}</span>
                            <span className={`text-xs px-2 py-0.5 rounded-full ${TYPE_COLORS[iv.interview_type ?? 'other'] ?? TYPE_COLORS.other}`}>
                              {(iv.interview_type ?? 'interview').replace('_', ' ')}
                            </span>
                          </div>
                          <div className="text-xs text-slate-500 mt-1 flex flex-wrap gap-3">
                            <span>{iv.company ?? '—'}</span>
                            {iv.contact_name && <span>with {iv.contact_name}</span>}
                            {iv.scheduled_at && (
                              <span className="text-blue-400">
                                {new Date(iv.scheduled_at).toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                              </span>
                            )}
                          </div>
                          {iv.notes && <div className="text-xs text-slate-600 mt-2">{iv.notes}</div>}
                        </div>
                        <div className="shrink-0 flex gap-2">
                          <button onClick={() => setStatus(iv.id, 'completed')}
                            className="text-xs bg-green-900/40 border border-green-800 text-green-400 hover:bg-green-900/60 rounded-lg px-2.5 py-1.5 transition-colors">
                            ✓ Done
                          </button>
                          <button onClick={() => setStatus(iv.id, 'cancelled')}
                            className="text-xs border border-slate-700 text-slate-400 hover:text-white rounded-lg px-2.5 py-1.5 transition-colors">
                            Cancel
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {past.length > 0 && (
            <div>
              <div className="text-xs text-slate-500 uppercase tracking-widest mb-3">Past</div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden opacity-75">
                <div className="divide-y divide-slate-800/50">
                  {past.map(iv => (
                    <div key={iv.id} className="px-5 py-3 flex items-center justify-between">
                      <div className="min-w-0 mr-3">
                        <div className="text-sm text-slate-300">{iv.title ?? '—'}</div>
                        <div className="text-xs text-slate-600">
                          {iv.company ?? '—'} · {iv.scheduled_at ? new Date(iv.scheduled_at).toLocaleDateString() : '—'}
                        </div>
                      </div>
                      <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${
                        iv.status === 'completed' ? 'bg-green-900/40 text-green-400' : 'bg-slate-800 text-slate-500'
                      }`}>{iv.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
