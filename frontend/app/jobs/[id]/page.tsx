'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import api from '../../../lib/api'

type Job = Record<string, unknown>
type EvalResult = Record<string, unknown>

export default function JobDetail() {
  const params = useParams()
  const router = useRouter()
  const id = String(params.id)

  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [evaluation, setEvaluation] = useState<EvalResult | null>(null)
  const [evaluating, setEvaluating] = useState(false)
  const [applying, setApplying] = useState(false)
  const [applyResult, setApplyResult] = useState<Record<string, unknown> | null>(null)
  const [cvPath, setCvPath] = useState('cv.md')
  const [mode, setMode] = useState('draft')

  useEffect(() => {
    api.job(id)
      .then(setJob)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  function handleEvaluate() {
    setEvaluating(true)
    api.evaluate({ job_id: id })
      .then(setEvaluation)
      .catch((e: Error) => setError(e.message))
      .finally(() => setEvaluating(false))
  }

  function handleApply() {
    if (!job) return
    setApplying(true)
    api.approve({
      url: String(job.url ?? job.applyUrl ?? ''),
      title: String(job.title ?? job.position ?? ''),
      company: String(job.company ?? ''),
      mode,
      cv_path: cvPath,
    })
      .then(setApplyResult)
      .catch((e: Error) => setError(e.message))
      .finally(() => setApplying(false))
  }

  function handleFeedback(outcome: 'positive' | 'negative') {
    api.feedback({ job_id: id, outcome }).catch(() => null)
  }

  if (loading) return <div className="text-slate-500 text-sm py-12 text-center">Loading…</div>
  if (error && !job) return <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm">{error}</div>
  if (!job) return null

  const title = String(job.title ?? job.position ?? 'Untitled')
  const company = String(job.company ?? '—')
  const score = job.score != null ? Number(job.score) : null
  const description = String(job.description ?? '')

  return (
    <div className="max-w-4xl">
      <button onClick={() => router.back()} className="text-xs text-slate-500 hover:text-slate-300 mb-6 flex items-center gap-1">
        ← Back
      </button>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">{title}</h1>
          <p className="text-slate-400 mt-1 text-sm">
            {company}
            {job.location ? ` · ${String(job.location)}` : ''}
            {job.source ? ` · ${String(job.source)}` : ''}
          </p>
        </div>
        {score != null && (
          <div className={`text-center px-4 py-2 rounded-xl border ${
            score >= 80 ? 'bg-green-950/40 border-green-800 text-green-400' :
            score >= 60 ? 'bg-amber-950/40 border-amber-800 text-amber-400' :
            'bg-slate-900 border-slate-700 text-slate-400'
          }`}>
            <div className="text-2xl font-bold">{score}</div>
            <div className="text-xs opacity-70">score</div>
          </div>
        )}
      </div>

      {Array.isArray(job.matched_skills) && job.matched_skills.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-6">
          {(job.matched_skills as string[]).map(s => (
            <span key={s} className="text-xs bg-blue-950/60 text-blue-400 px-2 py-1 rounded-full border border-blue-900/50">
              {s}
            </span>
          ))}
        </div>
      )}

      {error && (
        <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          {description && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Description</h2>
              <div className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed max-h-80 overflow-y-auto">
                {description.slice(0, 3000)}{description.length > 3000 ? '…' : ''}
              </div>
            </div>
          )}

          {applyResult && (
            <div className={`border rounded-xl p-4 text-sm ${
              applyResult.status === 'submitted' ? 'bg-green-950/30 border-green-800 text-green-300' :
              applyResult.status === 'duplicate_blocked' ? 'bg-amber-950/30 border-amber-800 text-amber-300' :
              'bg-slate-900 border-slate-700 text-slate-300'
            }`}>
              <div className="font-semibold mb-1">
                {applyResult.status === 'submitted' ? 'Application submitted!' :
                 applyResult.status === 'draft_saved' ? 'Draft saved — awaiting review' :
                 applyResult.status === 'duplicate_blocked' ? 'Already applied to this role' :
                 String(applyResult.status)}
              </div>
              {applyResult.session_id && (
                <div className="text-xs opacity-70 mt-1">
                  Session:{' '}
                  <a href={`/sessions/${applyResult.session_id}`} className="underline">
                    {String(applyResult.session_id)}
                  </a>
                </div>
              )}
            </div>
          )}

          {evaluation && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">Evaluation</h2>
              <div className="grid grid-cols-2 gap-3 mb-4">
                {(['archetype', 'global_score', 'confidence', 'recommendation'] as const).map(k => (
                  <div key={k} className="bg-slate-800/60 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">{k.replace(/_/g, ' ')}</div>
                    <div className="text-sm text-white font-medium">{String(evaluation[k] ?? '—')}</div>
                  </div>
                ))}
              </div>
              {evaluation.cv_tailoring && (
                <div>
                  <div className="text-xs text-slate-500 mb-2">CV Tailoring</div>
                  <div className="text-sm text-slate-300 bg-slate-800/60 rounded-lg p-3">
                    {String(evaluation.cv_tailoring)}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="space-y-3">
          {job.url && (
            <a
              href={String(job.url)}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full text-center bg-slate-800 hover:bg-slate-700 border border-slate-700 text-white text-sm font-medium px-4 py-3 rounded-xl transition-colors"
            >
              View Posting ↗
            </a>
          )}

          <button
            onClick={handleEvaluate}
            disabled={evaluating}
            className="w-full bg-slate-800 hover:bg-slate-700 disabled:opacity-50 border border-slate-700 text-white text-sm font-medium px-4 py-3 rounded-xl transition-colors"
          >
            {evaluating ? 'Evaluating…' : 'Evaluate Fit'}
          </button>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
            <div className="text-xs text-slate-500 font-medium uppercase tracking-wider">Apply</div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">CV Path</label>
              <input
                type="text"
                value={cvPath}
                onChange={e => setCvPath(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Mode</label>
              <select
                value={mode}
                onChange={e => setMode(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
              >
                <option value="draft">Draft (review before submit)</option>
                <option value="auto">Auto (submit directly)</option>
              </select>
            </div>
            <button
              onClick={handleApply}
              disabled={applying || !job.url}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-3 rounded-xl transition-colors"
            >
              {applying ? 'Starting…' : 'Apply with Agent'}
            </button>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
            <div className="text-xs text-slate-500 mb-3">Feedback</div>
            <div className="flex gap-2">
              <button
                onClick={() => handleFeedback('positive')}
                className="flex-1 bg-green-950/40 hover:bg-green-900/40 border border-green-900 text-green-400 text-xs font-medium px-3 py-2 rounded-lg transition-colors"
              >
                👍 Good match
              </button>
              <button
                onClick={() => handleFeedback('negative')}
                className="flex-1 bg-red-950/40 hover:bg-red-900/40 border border-red-900 text-red-400 text-xs font-medium px-3 py-2 rounded-lg transition-colors"
              >
                👎 Not a fit
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
