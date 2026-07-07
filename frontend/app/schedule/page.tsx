'use client'

import { useEffect, useState } from 'react'
import api from '../../lib/api'

type Schedule = {
  id: string
  label?: string
  cv_path?: string
  interval_days?: number
  role_keywords?: string[]
  last_ran?: string
}

export default function Schedule() {
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [dueCount, setDueCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [running, setRunning] = useState<string | null>(null)
  const [form, setForm] = useState({ label: '', cv_path: 'cv.md', interval_days: '2', role_keywords: '' })
  const [creating, setCreating] = useState(false)
  const [showForm, setShowForm] = useState(false)

  const load = () => {
    setLoading(true)
    api.schedule()
      .then(d => { setSchedules(d.schedules ?? []); setDueCount(d.due_count ?? 0) })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  function handleCreate() {
    setCreating(true)
    api.createSchedule({
      label: form.label,
      cv_path: form.cv_path,
      interval_days: Number(form.interval_days),
      role_keywords: form.role_keywords.split(',').map(s => s.trim()).filter(Boolean),
    })
      .then(() => { setShowForm(false); load() })
      .catch((e: Error) => setError(e.message))
      .finally(() => setCreating(false))
  }

  function handleRun(id: string) {
    setRunning(id)
    api.runSchedule(id)
      .then(() => load())
      .catch((e: Error) => setError(e.message))
      .finally(() => setRunning(null))
  }

  function handleDelete(id: string) {
    api.deleteSchedule(id)
      .then(() => load())
      .catch((e: Error) => setError(e.message))
  }

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Schedule</h1>
          <p className="text-slate-400 text-sm mt-1">
            Automated scan schedules · {dueCount} due now
          </p>
        </div>
        <button
          onClick={() => setShowForm(v => !v)}
          className="text-sm bg-blue-600 hover:bg-blue-500 text-white font-medium px-4 py-2 rounded-xl transition-colors"
        >
          + New Schedule
        </button>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm mb-6">{error}</div>
      )}

      {showForm && (
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 mb-6 space-y-4">
          <div className="text-sm font-semibold text-white mb-2">New Schedule</div>
          {[
            { key: 'label', label: 'Label', placeholder: 'e.g. AI Engineer scan' },
            { key: 'cv_path', label: 'CV Path', placeholder: 'cv.md' },
            { key: 'interval_days', label: 'Interval (days)', placeholder: '2' },
            { key: 'role_keywords', label: 'Role Keywords (comma-separated)', placeholder: 'AI engineer, LLM, backend' },
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
          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              disabled={creating}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
            >
              {creating ? 'Creating…' : 'Create'}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="text-slate-400 hover:text-white text-sm px-4 py-2"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-slate-500 text-sm py-12 text-center">Loading…</div>
      ) : schedules.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl py-16 text-center">
          <div className="text-slate-500 text-sm">No schedules yet</div>
          <div className="text-slate-600 text-xs mt-1">Create one to automate periodic job scans</div>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="divide-y divide-slate-800">
            {schedules.map(s => (
              <div key={s.id} className="flex items-start justify-between px-5 py-4">
                <div>
                  <div className="text-white text-sm font-medium">{s.label || s.id.slice(0, 20)}</div>
                  <div className="text-slate-400 text-xs mt-1">
                    Every {s.interval_days}d · CV: {s.cv_path}
                    {s.role_keywords && s.role_keywords.length > 0 && ` · ${s.role_keywords.join(', ')}`}
                  </div>
                  {s.last_ran && (
                    <div className="text-slate-600 text-xs mt-0.5">
                      Last ran: {new Date(s.last_ran).toLocaleDateString()}
                    </div>
                  )}
                </div>
                <div className="flex gap-2 shrink-0 ml-4">
                  <button
                    onClick={() => handleRun(s.id)}
                    disabled={running === s.id}
                    className="text-xs bg-blue-900/50 hover:bg-blue-800/60 border border-blue-800/50 text-blue-400 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {running === s.id ? 'Running…' : 'Run now'}
                  </button>
                  <button
                    onClick={() => handleDelete(s.id)}
                    className="text-xs bg-red-900/30 hover:bg-red-800/40 border border-red-900/50 text-red-400 px-3 py-1.5 rounded-lg transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
