'use client'

import { useEffect, useState, useRef } from 'react'
import Link from 'next/link'
import api from '../../lib/api'

type Job = { id: string; title?: string; company?: string; score?: number; match_ratio?: number; source?: string; archetype?: string }
type QueueItem = { job: Job; status: 'queued' | 'running' | 'done' | 'failed' | 'skipped'; session_id?: string; error?: string }

const CV_VARIANTS = [
  { id: 'ai_engineer', label: 'AI Engineer CV', path: 'CVs/My CVc.md' },
  { id: 'software_dev', label: 'Software Dev CV', path: 'CVs/Soft Dev CV.md' },
  { id: 'fullstack', label: 'Full-Stack CV', path: 'CVs/SoftwareDevCV.md' },
]

type Step = 1 | 2 | 3

function StatusBadge({ status }: { status: QueueItem['status'] }) {
  const map = {
    queued: 'bg-slate-800 text-slate-400 border-slate-700',
    running: 'bg-blue-900/60 text-blue-400 border-blue-800 animate-pulse',
    done: 'bg-green-900/60 text-green-400 border-green-800',
    failed: 'bg-red-900/50 text-red-400 border-red-800',
    skipped: 'bg-slate-800 text-slate-500 border-slate-700',
  }
  const labels = { queued: '⏳ Queued', running: '⚡ Running', done: '✅ Done', failed: '❌ Failed', skipped: '⏭ Skipped' }
  return <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${map[status]}`}>{labels[status]}</span>
}

export default function BulkApply() {
  const [step, setStep] = useState<Step>(1)
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [minScore, setMinScore] = useState(0)
  const [searchQ, setSearchQ] = useState('')
  const [cvVariant, setCvVariant] = useState(CV_VARIANTS[0])
  const [mode, setMode] = useState('draft')
  const [concurrency, setConcurrency] = useState(1)
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [running, setRunning] = useState(false)
  const [done, setDone] = useState(0)
  const abortRef = useRef(false)

  useEffect(() => {
    api.jobs({ limit: 500 })
      .then(d => setJobs(d.jobs ?? []))
      .finally(() => setLoading(false))
  }, [])

  const filtered = jobs.filter(j => {
    if (minScore > 0 && (j.score ?? 0) < minScore) return false
    if (searchQ) {
      const q = searchQ.toLowerCase()
      return [j.title, j.company, j.source].some(v => v?.toLowerCase().includes(q))
    }
    return true
  })

  function toggleJob(id: string) {
    setSelected(prev => {
      const s = new Set(prev)
      if (s.has(id)) s.delete(id)
      else s.add(id)
      return s
    })
  }

  function selectHighMatch() {
    const ids = jobs.filter(j => (j.score ?? 0) >= 80).map(j => j.id)
    setSelected(new Set(ids))
  }

  function selectVisible() {
    setSelected(new Set(filtered.map(j => j.id)))
  }

  function clearSelection() {
    setSelected(new Set())
  }

  function buildQueue(): QueueItem[] {
    return [...selected].map(id => {
      const job = jobs.find(j => j.id === id)!
      return { job, status: 'queued' as const }
    })
  }

  async function runQueue(items: QueueItem[]) {
    setRunning(true)
    abortRef.current = false
    let doneCount = 0

    for (let i = 0; i < items.length; i++) {
      if (abortRef.current) {
        setQueue(prev => prev.map((q, idx) => idx >= i ? { ...q, status: 'skipped' } : q))
        break
      }

      setQueue(prev => prev.map((q, idx) => idx === i ? { ...q, status: 'running' } : q))

      try {
        const job = items[i].job
        const url = String((job as Record<string,unknown>).url ?? (job as Record<string,unknown>).applyUrl ?? (job as Record<string,unknown>).apply_url ?? '')
        if (!url) {
          setQueue(prev => prev.map((q, idx) => idx === i ? { ...q, status: 'failed', error: 'No apply URL' } : q))
          continue
        }
        const result = await api.approve({
          url,
          title: job.title ?? '',
          company: job.company ?? '',
          mode,
          cv_path: cvVariant.path,
        })
        doneCount++
        setDone(doneCount)
        setQueue(prev => prev.map((q, idx) => idx === i ? {
          ...q,
          status: 'done',
          session_id: String(result.session_id ?? ''),
        } : q))
      } catch (e) {
        setQueue(prev => prev.map((q, idx) => idx === i ? {
          ...q,
          status: 'failed',
          error: e instanceof Error ? e.message : 'Unknown error',
        } : q))
      }

      if (i < items.length - 1 && concurrency === 1) {
        await new Promise(r => setTimeout(r, 500))
      }
    }
    setRunning(false)
  }

  function handleLaunch() {
    const items = buildQueue()
    setQueue(items)
    setDone(0)
    setStep(3)
    runQueue(items)
  }

  const total = queue.length
  const doneItems = queue.filter(q => q.status === 'done').length
  const failedItems = queue.filter(q => q.status === 'failed').length
  const progress = total > 0 ? Math.round((doneItems + failedItems) / total * 100) : 0

  return (
    <div className="max-w-4xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Bulk Apply</h1>
        <p className="text-slate-400 text-sm mt-1">Queue multiple job applications and run them in sequence</p>
      </div>

      <div className="flex gap-3 mb-8">
        {([1, 2, 3] as const).map(s => (
          <div key={s} className={`flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-full transition-all ${
            step === s ? 'bg-blue-600 text-white' : step > s ? 'bg-green-900/50 text-green-400 border border-green-800' : 'text-slate-500 border border-slate-700'
          }`}>
            <span>{step > s ? '✓' : s}</span>
            <span>{['Select Jobs', 'Configure', 'Launch & Monitor'][s - 1]}</span>
          </div>
        ))}
      </div>

      {step === 1 && (
        <div className="space-y-4">
          <div className="flex gap-3">
            <input type="text" value={searchQ} onChange={e => setSearchQ(e.target.value)}
              placeholder="Search jobs…"
              className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500" />
            <select value={minScore} onChange={e => setMinScore(Number(e.target.value))}
              className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500">
              <option value={0}>All scores</option>
              <option value={60}>60+ score</option>
              <option value={70}>70+ score</option>
              <option value={80}>80+ score</option>
            </select>
          </div>

          <div className="flex items-center gap-3 text-xs">
            <span className="text-slate-500">{selected.size} selected</span>
            <button onClick={selectHighMatch} className="text-blue-400 hover:text-blue-300 transition-colors">Select high match (≥80)</button>
            <button onClick={selectVisible} className="text-blue-400 hover:text-blue-300 transition-colors">Select visible ({filtered.length})</button>
            {selected.size > 0 && <button onClick={clearSelection} className="text-slate-500 hover:text-slate-300 transition-colors">Clear</button>}
          </div>

          {loading ? (
            <div className="py-12 text-center text-slate-500 text-sm">Loading jobs…</div>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
              <div className="text-xs text-slate-600 px-5 py-3 border-b border-slate-800">
                {filtered.length} jobs · {selected.size} selected
              </div>
              <div className="divide-y divide-slate-800/50 max-h-[480px] overflow-y-auto">
                {filtered.map(j => (
                  <div key={j.id} onClick={() => toggleJob(j.id)}
                    className={`flex items-center gap-4 px-5 py-3.5 cursor-pointer transition-colors ${
                      selected.has(j.id) ? 'bg-blue-900/20' : 'hover:bg-slate-800/40'
                    }`}>
                    <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-all ${
                      selected.has(j.id) ? 'bg-blue-600 border-blue-600' : 'border-slate-600'
                    }`}>
                      {selected.has(j.id) && <span className="text-white text-xs">✓</span>}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white font-medium truncate">{j.title ?? 'Untitled'}</div>
                      <div className="text-xs text-slate-500">{j.company ?? '—'}{j.source ? ` · ${j.source}` : ''}</div>
                    </div>
                    <div className="shrink-0 flex items-center gap-2">
                      {j.match_ratio != null && (
                        <span className="text-xs text-slate-500">{Math.round(j.match_ratio * 100)}%</span>
                      )}
                      {j.score != null && (
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${
                          j.score >= 80 ? 'bg-green-950/50 text-green-400 border-green-800' :
                          j.score >= 60 ? 'bg-amber-950/50 text-amber-400 border-amber-800' :
                          'bg-slate-800 text-slate-500 border-slate-700'
                        }`}>{j.score}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex justify-end">
            <button onClick={() => setStep(2)} disabled={selected.size === 0}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white font-semibold px-6 py-3 rounded-xl transition-colors">
              Configure {selected.size > 0 ? `${selected.size} applications` : ''} →
            </button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-5">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="text-sm font-semibold text-white mb-4">CV Variant</div>
            <div className="grid grid-cols-3 gap-3">
              {CV_VARIANTS.map(v => (
                <button key={v.id} onClick={() => setCvVariant(v)}
                  className={`p-4 rounded-xl border text-left transition-all ${
                    cvVariant.id === v.id ? 'border-blue-600 bg-blue-900/30 text-blue-300' : 'border-slate-700 bg-slate-800/40 text-slate-400 hover:border-slate-600'
                  }`}>
                  <div className="font-medium text-sm mb-1">{v.label}</div>
                  <div className="text-xs opacity-60 truncate">{v.path}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="text-sm font-semibold text-white mb-4">Application Mode</div>
            <div className="grid grid-cols-2 gap-3">
              <button onClick={() => setMode('draft')}
                className={`p-4 rounded-xl border text-left transition-all ${
                  mode === 'draft' ? 'border-blue-600 bg-blue-900/30' : 'border-slate-700 bg-slate-800/40 hover:border-slate-600'
                }`}>
                <div className="text-sm font-medium text-white mb-1">📋 Draft Mode</div>
                <div className="text-xs text-slate-500">I review each application before it's submitted — recommended</div>
              </button>
              <button onClick={() => setMode('auto')}
                className={`p-4 rounded-xl border text-left transition-all ${
                  mode === 'auto' ? 'border-amber-600 bg-amber-900/20' : 'border-slate-700 bg-slate-800/40 hover:border-slate-600'
                }`}>
                <div className="text-sm font-medium text-white mb-1">⚡ Auto Mode</div>
                <div className="text-xs text-slate-500">Agent submits directly. Use only for roles you've already reviewed.</div>
              </button>
            </div>
          </div>

          <div className="bg-amber-950/20 border border-amber-800/50 rounded-xl p-4 text-xs text-amber-400">
            ⚠ The agent never submits an application without your review unless you select Auto mode. Draft mode saves each application for you to approve in the Sessions page.
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
            <div className="text-sm font-semibold text-white mb-3">Summary</div>
            <div className="grid grid-cols-3 gap-3 text-sm">
              <div><span className="text-slate-500">Applications:</span> <span className="text-white font-semibold">{selected.size}</span></div>
              <div><span className="text-slate-500">CV:</span> <span className="text-white font-semibold">{cvVariant.label}</span></div>
              <div><span className="text-slate-500">Mode:</span> <span className="text-white font-semibold capitalize">{mode}</span></div>
            </div>
          </div>

          <div className="flex gap-3 justify-between">
            <button onClick={() => setStep(1)} className="text-slate-400 hover:text-white text-sm px-4 py-2 transition-colors">← Back</button>
            <button onClick={handleLaunch} className="bg-blue-600 hover:bg-blue-500 text-white font-semibold px-6 py-3 rounded-xl transition-colors">
              🚀 Launch {selected.size} Applications
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-5">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm font-semibold text-white">
                {running ? `Running… ${doneItems + failedItems}/${total}` : `Complete — ${doneItems} done, ${failedItems} failed`}
              </div>
              <div className="text-xs text-slate-500">{progress}%</div>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-2 mb-4">
              <div className="h-2 rounded-full bg-blue-600 transition-all duration-500" style={{ width: `${progress}%` }} />
            </div>
            <div className="grid grid-cols-4 gap-3 text-center text-xs">
              {[
                { label: 'Queued', count: queue.filter(q => q.status === 'queued').length, color: 'text-slate-400' },
                { label: 'Running', count: queue.filter(q => q.status === 'running').length, color: 'text-blue-400' },
                { label: 'Done', count: doneItems, color: 'text-green-400' },
                { label: 'Failed', count: failedItems, color: 'text-red-400' },
              ].map(s => (
                <div key={s.label}>
                  <div className={`text-2xl font-bold ${s.color}`}>{s.count}</div>
                  <div className="text-slate-600 mt-0.5">{s.label}</div>
                </div>
              ))}
            </div>
          </div>

          {running && (
            <button onClick={() => { abortRef.current = true }}
              className="text-xs text-red-400 hover:text-red-300 border border-red-900 px-3 py-2 rounded-lg transition-colors">
              Stop Queue
            </button>
          )}

          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            <div className="text-xs text-slate-500 px-5 py-3 border-b border-slate-800">Application queue</div>
            <div className="divide-y divide-slate-800/50 max-h-[500px] overflow-y-auto">
              {queue.map((q, i) => (
                <div key={i} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex-1 min-w-0 mr-4">
                    <div className="text-sm text-white font-medium truncate">{q.job.title ?? 'Untitled'}</div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      {q.job.company ?? '—'}
                      {q.error && <span className="text-red-400 ml-2">Error: {q.error}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <StatusBadge status={q.status} />
                    {q.session_id && (
                      <Link href={`/sessions/${q.session_id}`} className="text-xs text-blue-400 hover:text-blue-300 transition-colors">
                        Open →
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {!running && doneItems > 0 && (
            <div className="flex gap-3">
              <Link href="/sessions" className="text-sm bg-blue-900/40 hover:bg-blue-800/60 border border-blue-800 text-blue-300 px-4 py-2.5 rounded-xl transition-colors">
                Review Draft Sessions →
              </Link>
              <Link href="/applications" className="text-sm bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-4 py-2.5 rounded-xl transition-colors">
                View Applications →
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
