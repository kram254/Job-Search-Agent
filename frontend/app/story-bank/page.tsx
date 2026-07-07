'use client'

import { useEffect, useState } from 'react'
import api from '../../lib/api'

type Story = {
  id?: string
  title?: string
  situation?: string
  task?: string
  action?: string
  result?: string
  tags?: string[]
  archetype?: string
}

export default function StoryBank() {
  const [stories, setStories] = useState<Story[]>([])
  const [stats, setStats] = useState<Record<string, unknown>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [archetype, setArchetype] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ title: '', situation: '', task: '', action: '', result: '', archetype: '', tags: '' })
  const [adding, setAdding] = useState(false)

  const load = (arc?: string) => {
    setLoading(true)
    api.storyBank({ archetype: arc || undefined, limit: 50 })
      .then(d => { setStories(d.stories ?? []); setStats(d.stats ?? {}) })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  function handleArchetypeChange(v: string) {
    setArchetype(v)
    load(v || undefined)
  }

  function handleAdd() {
    setAdding(true)
    api.addStory({
      ...form,
      tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
    })
      .then(() => { setShowForm(false); setForm({ title: '', situation: '', task: '', action: '', result: '', archetype: '', tags: '' }); load(archetype || undefined) })
      .catch((e: Error) => setError(e.message))
      .finally(() => setAdding(false))
  }

  const archetypes = stats.by_archetype ? Object.keys(stats.by_archetype as object) : []

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Story Bank</h1>
          <p className="text-slate-400 text-sm mt-1">
            {(stats.total as number) ?? 0} interview stories
          </p>
        </div>
        <button
          onClick={() => setShowForm(v => !v)}
          className="text-sm bg-blue-600 hover:bg-blue-500 text-white font-medium px-4 py-2 rounded-xl transition-colors"
        >
          + Add Story
        </button>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm mb-6">{error}</div>
      )}

      {archetypes.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-5">
          <button
            onClick={() => handleArchetypeChange('')}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              !archetype ? 'bg-blue-600 border-blue-600 text-white' : 'border-slate-700 text-slate-400 hover:border-slate-500'
            }`}
          >
            All
          </button>
          {archetypes.map(a => (
            <button
              key={a}
              onClick={() => handleArchetypeChange(a)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                archetype === a ? 'bg-blue-600 border-blue-600 text-white' : 'border-slate-700 text-slate-400 hover:border-slate-500'
              }`}
            >
              {a}
            </button>
          ))}
        </div>
      )}

      {showForm && (
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 mb-6 space-y-3">
          <div className="text-sm font-semibold text-white">New Story (STAR format)</div>
          {[
            { key: 'title', label: 'Title', placeholder: 'e.g. Led ML pipeline migration' },
            { key: 'archetype', label: 'Archetype', placeholder: 'e.g. agentic_automation' },
            { key: 'situation', label: 'Situation', placeholder: 'Context and background…' },
            { key: 'task', label: 'Task', placeholder: 'Your responsibility…' },
            { key: 'action', label: 'Action', placeholder: 'What you did…' },
            { key: 'result', label: 'Result', placeholder: 'Outcome and impact…' },
            { key: 'tags', label: 'Tags (comma-separated)', placeholder: 'python, ml, leadership' },
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
              onClick={handleAdd}
              disabled={adding || !form.title}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
            >
              {adding ? 'Saving…' : 'Save Story'}
            </button>
            <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-white text-sm px-4 py-2">Cancel</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-slate-500 text-sm py-12 text-center">Loading…</div>
      ) : stories.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl py-16 text-center">
          <div className="text-slate-500 text-sm">No stories yet</div>
          <div className="text-slate-600 text-xs mt-1">Add STAR-format interview stories to use in applications</div>
        </div>
      ) : (
        <div className="space-y-3">
          {stories.map((s, i) => (
            <div key={s.id ?? i} className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <div className="flex items-start justify-between mb-3">
                <div className="text-white font-medium text-sm">{s.title ?? 'Untitled'}</div>
                {s.archetype && (
                  <span className="text-xs bg-blue-950/60 text-blue-400 px-2 py-0.5 rounded-full border border-blue-900/50 ml-2 shrink-0">
                    {s.archetype}
                  </span>
                )}
              </div>
              {s.situation && <div className="text-xs text-slate-400 mb-1"><span className="text-slate-600">S:</span> {s.situation}</div>}
              {s.task && <div className="text-xs text-slate-400 mb-1"><span className="text-slate-600">T:</span> {s.task}</div>}
              {s.action && <div className="text-xs text-slate-400 mb-1"><span className="text-slate-600">A:</span> {s.action}</div>}
              {s.result && <div className="text-xs text-slate-300 mb-2"><span className="text-slate-500">R:</span> {s.result}</div>}
              {s.tags && s.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {s.tags.map(t => (
                    <span key={t} className="text-xs bg-slate-800 text-slate-500 px-1.5 py-0.5 rounded">{t}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
