'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import api from '../../../lib/api'

type Job = Record<string, unknown>
type EvalResult = Record<string, unknown>
type ResearchResult = Record<string, unknown>
type OutreachResult = { subject?: string; body?: string; contact?: Record<string, unknown>; matched_skills?: string[] }
type CvResult = { pdf_path?: string; page_count?: number; file_size_kb?: number; keywords_injected?: string[]; coverage_percentage?: number; format_used?: string }
type ApplyResult = Record<string, unknown>

const TABS = ['Overview', 'Apply', 'Outreach', 'Cover Letter', 'Research'] as const
type Tab = typeof TABS[number]

const CV_VARIANTS = [
  { id: 'ai_engineer', label: 'AI Engineer', path: 'CVs/My CVc.md', archetypes: ['agentic_automation', 'ai_platform_llmops'] },
  { id: 'software_dev', label: 'Software Developer', path: 'CVs/Soft Dev CV.md', archetypes: ['ai_forward_deployed'] },
  { id: 'fullstack', label: 'Full-Stack', path: 'CVs/SoftwareDevCV.md', archetypes: ['ai_transformation'] },
]

function ScoreBadge({ score, size = 'sm' }: { score: number; size?: 'sm' | 'lg' }) {
  const color = score >= 80 ? 'bg-green-900/50 text-green-400 border-green-800' :
    score >= 65 ? 'bg-amber-900/50 text-amber-400 border-amber-800' :
    'bg-red-900/40 text-red-400 border-red-800'
  const cls = size === 'lg' ? 'text-2xl font-bold px-4 py-2' : 'text-xs font-bold px-2 py-0.5'
  return <span className={`${cls} rounded-full border ${color}`}>{score}{size === 'lg' ? '/100' : ''}</span>
}

function BlockScores({ scores }: { scores: Record<string, { score: number; reasoning: string }> }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {Object.entries(scores).map(([k, v]) => (
        <div key={k} title={v.reasoning}
          className={`text-xs px-2 py-1 rounded-lg border cursor-help ${
            v.score >= 4 ? 'bg-green-950/40 border-green-900 text-green-400' :
            v.score >= 3 ? 'bg-amber-950/40 border-amber-900 text-amber-400' :
            'bg-red-950/30 border-red-900 text-red-400'
          }`}>
          {k}: {v.score}/5
        </div>
      ))}
    </div>
  )
}

export default function JobDetail() {
  const params = useParams()
  const router = useRouter()
  const id = String(params.id)

  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<Tab>('Overview')

  const [evaluation, setEvaluation] = useState<EvalResult | null>(null)
  const [evaluating, setEvaluating] = useState(false)

  const [research, setResearch] = useState<ResearchResult | null>(null)
  const [researching, setResearching] = useState(false)

  const [outreach, setOutreach] = useState<OutreachResult | null>(null)
  const [reaching, setReaching] = useState(false)
  const [outreachBody, setOutreachBody] = useState('')
  const [outreachSubject, setOutreachSubject] = useState('')
  const [copied, setCopied] = useState(false)

  const [letter, setLetter] = useState('')
  const [letterLoading, setLetterLoading] = useState(false)

  const [cvResult, setCvResult] = useState<CvResult | null>(null)
  const [generatingCv, setGeneratingCv] = useState(false)
  const [cvVariant, setCvVariant] = useState(CV_VARIANTS[0])
  const [archetype, setArchetype] = useState('general')
  const [mode, setMode] = useState('draft')

  const [applying, setApplying] = useState(false)
  const [applyResult, setApplyResult] = useState<ApplyResult | null>(null)

  useEffect(() => {
    api.job(id)
      .then(setJob)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (evaluation) {
      const arch = String((evaluation as Record<string,unknown>).archetype ?? 'general')
      setArchetype(arch)
      const match = CV_VARIANTS.find(v => v.archetypes.includes(arch))
      if (match) setCvVariant(match)
    }
  }, [evaluation])

  useEffect(() => {
    if (outreach) {
      setOutreachSubject(outreach.subject || '')
      setOutreachBody(outreach.body || '')
    }
  }, [outreach])

  function handleEvaluate() {
    setEvaluating(true)
    api.evaluate({ job_id: id })
      .then(r => { setEvaluation(r); setTab('Overview') })
      .catch((e: Error) => setError(e.message))
      .finally(() => setEvaluating(false))
  }

  function handleResearch() {
    if (!job) return
    setResearching(true)
    api.deepResearch({ job_description: String(job.description ?? ''), company: String(job.company ?? '') })
      .then(r => { setResearch(r); setTab('Research') })
      .catch((e: Error) => setError(e.message))
      .finally(() => setResearching(false))
  }

  function handleOutreach() {
    setReaching(true)
    api.outreach({ job_id: id })
      .then(r => { setOutreach(r); setTab('Outreach') })
      .catch((e: Error) => setError(e.message))
      .finally(() => setReaching(false))
  }

  function handleGenerateCv() {
    setGeneratingCv(true)
    api.generateCv({ job_id: id, cv_path: cvVariant.path, archetype })
      .then(r => { setCvResult(r); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setGeneratingCv(false))
  }

  function handleCoverLetter() {
    if (!job) return
    setLetterLoading(true)
    fetch(`${process.env.NEXT_PUBLIC_API_URL?.startsWith('http') ? process.env.NEXT_PUBLIC_API_URL : `https://${process.env.NEXT_PUBLIC_API_URL}`}/cover-letter`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_description: String(job.description ?? ''),
        company: String(job.company ?? ''),
        title: String(job.title ?? ''),
        archetype,
      }),
    })
      .then(r => r.json())
      .then(d => { setLetter(d.letter || d.error || ''); setTab('Cover Letter') })
      .catch((e: Error) => setLetter(`Error: ${e.message}`))
      .finally(() => setLetterLoading(false))
  }

  function handleApply() {
    if (!job) return
    const url = String(job.url ?? job.applyUrl ?? job.apply_url ?? '')
    setApplying(true)
    api.approve({ url, title: String(job.title ?? ''), company: String(job.company ?? ''), mode, cv_path: cvVariant.path })
      .then(r => { setApplyResult(r); setTab('Apply') })
      .catch((e: Error) => setError(e.message))
      .finally(() => setApplying(false))
  }

  function handleFeedback(outcome: 'positive' | 'negative') {
    api.feedback({ job_id: id, outcome }).catch(() => null)
  }

  function handleCopy(text: string) {
    navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000) })
  }

  function getCvDownloadUrl(path: string): string {
    const base = (process.env.NEXT_PUBLIC_API_URL ?? 'https://job-search-agent-tfd1.onrender.com')
    const baseUrl = base.startsWith('http') ? base : `https://${base}`
    const filename = path.split('/').pop() || path
    return `${baseUrl}/output/cvs/${filename}`
  }

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-500 text-sm">Loading job…</div>
  if (!job && error) return <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-xl px-5 py-4 text-sm">{error}</div>
  if (!job) return null

  const title = String(job.title ?? job.position ?? 'Untitled')
  const company = String(job.company ?? '—')
  const score = job.score != null ? Number(job.score) : null
  const description = String(job.description ?? '')
  const jobUrl = String(job.url ?? job.applyUrl ?? job.apply_url ?? '')
  const hasUrl = jobUrl.length > 5
  const matchedSkills = Array.isArray(job.matched_skills) ? job.matched_skills as string[] : []
  const globalScore = evaluation ? Math.round(Number((evaluation as Record<string,unknown>).global_score ?? 0) * 20) : null

  return (
    <div className="max-w-5xl">
      <button onClick={() => router.back()} className="text-xs text-slate-500 hover:text-slate-300 mb-5 flex items-center gap-1 transition-colors">
        ← Back to Jobs
      </button>

      <div className="flex items-start justify-between mb-5">
        <div className="flex-1 min-w-0 mr-4">
          <h1 className="text-2xl font-bold text-white leading-tight">{title}</h1>
          <div className="flex items-center flex-wrap gap-2 mt-2 text-sm text-slate-400">
            <span>{company}</span>
            {job.location && <><span className="text-slate-700">·</span><span>{String(job.location)}</span></>}
            {job.source && <><span className="text-slate-700">·</span><span className="capitalize">{String(job.source)}</span></>}
            {job.salary_range && <><span className="text-slate-700">·</span><span className="text-green-400">{String(job.salary_range)}</span></>}
          </div>
          {matchedSkills.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {matchedSkills.slice(0, 8).map(s => (
                <span key={s} className="text-xs bg-blue-950/60 text-blue-400 px-2 py-0.5 rounded-full border border-blue-900/50">{s}</span>
              ))}
            </div>
          )}
        </div>
        <div className="shrink-0 flex flex-col items-end gap-2">
          {globalScore != null ? (
            <ScoreBadge score={globalScore} size="lg" />
          ) : score != null ? (
            <div className="text-center">
              <ScoreBadge score={score} size="lg" />
              <div className="text-xs text-slate-600 mt-1">quick score</div>
            </div>
          ) : null}
          {job.match_ratio != null && (
            <div className="text-xs text-slate-500">{Math.round(Number(job.match_ratio) * 100)}% skill match</div>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-5">
        {hasUrl ? (
          <a href={jobUrl} target="_blank" rel="noopener noreferrer"
            className="text-xs bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-3 py-2 rounded-lg transition-colors">
            View Original Posting ↗
          </a>
        ) : (
          <span className="text-xs bg-slate-900 border border-slate-800 text-slate-600 px-3 py-2 rounded-lg">No posting URL available</span>
        )}
        <button onClick={handleEvaluate} disabled={evaluating}
          className="text-xs bg-blue-900/40 hover:bg-blue-800/60 disabled:opacity-50 border border-blue-800/60 text-blue-300 px-3 py-2 rounded-lg transition-colors">
          {evaluating ? 'Evaluating…' : evaluation ? '✓ Evaluated' : '⚡ Evaluate Fit'}
        </button>
        <button onClick={handleOutreach} disabled={reaching}
          className="text-xs bg-purple-900/40 hover:bg-purple-800/60 disabled:opacity-50 border border-purple-800/60 text-purple-300 px-3 py-2 rounded-lg transition-colors">
          {reaching ? 'Generating…' : outreach ? '✓ Outreach Ready' : '✉ Generate Outreach'}
        </button>
        <button onClick={handleCoverLetter} disabled={letterLoading}
          className="text-xs bg-teal-900/40 hover:bg-teal-800/60 disabled:opacity-50 border border-teal-800/60 text-teal-300 px-3 py-2 rounded-lg transition-colors">
          {letterLoading ? 'Writing…' : letter ? '✓ Cover Letter Ready' : '📄 Cover Letter'}
        </button>
        <button onClick={handleResearch} disabled={researching || !description}
          className="text-xs bg-slate-800 hover:bg-slate-700 disabled:opacity-50 border border-slate-700 text-slate-300 px-3 py-2 rounded-lg transition-colors"
          title={!description ? 'No description available for research' : ''}>
          {researching ? 'Researching…' : research ? '✓ Researched' : '🔍 Deep Research'}
        </button>
        <div className="flex gap-1.5 ml-auto">
          <button onClick={() => handleFeedback('positive')}
            className="text-xs bg-green-950/40 hover:bg-green-900/50 border border-green-900 text-green-400 px-2 py-2 rounded-lg transition-colors">👍</button>
          <button onClick={() => handleFeedback('negative')}
            className="text-xs bg-red-950/30 hover:bg-red-900/40 border border-red-900 text-red-400 px-2 py-2 rounded-lg transition-colors">👎</button>
        </div>
      </div>

      {error && <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>}

      <div className="border-b border-slate-800 mb-5">
        <div className="flex gap-1">
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
                tab === t ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-300'
              }`}>
              {t}
              {t === 'Overview' && evaluation && <span className="ml-1.5 text-xs bg-green-900/60 text-green-400 px-1.5 py-0.5 rounded-full">✓</span>}
              {t === 'Outreach' && outreach && <span className="ml-1.5 text-xs bg-purple-900/60 text-purple-400 px-1.5 py-0.5 rounded-full">✓</span>}
              {t === 'Cover Letter' && letter && <span className="ml-1.5 text-xs bg-teal-900/60 text-teal-400 px-1.5 py-0.5 rounded-full">✓</span>}
              {t === 'Apply' && applyResult && <span className="ml-1.5 text-xs bg-blue-900/60 text-blue-400 px-1.5 py-0.5 rounded-full">✓</span>}
            </button>
          ))}
        </div>
      </div>

      {tab === 'Overview' && (
        <div className="space-y-5">
          {!description ? (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-center">
              <div className="text-slate-500 text-sm mb-2">No job description available</div>
              <div className="text-slate-600 text-xs">
                {hasUrl
                  ? <><a href={jobUrl} target="_blank" rel="noopener noreferrer" className="text-blue-400 underline">View the posting ↗</a> for full details</>
                  : 'This listing was scraped without a description. Run Evaluate Fit to score based on title.'}
              </div>
            </div>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Job Description</div>
              <div className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed max-h-72 overflow-y-auto">
                {description}
              </div>
            </div>
          )}

          {evaluation && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">AI Evaluation</div>
                <ScoreBadge score={globalScore ?? 0} size="lg" />
              </div>
              <div className="grid grid-cols-2 gap-3 mb-4">
                {(['archetype', 'confidence', 'recommendation'] as const).map(k => {
                  let val = String((evaluation as Record<string,unknown>)[k] ?? '—')
                  if (k === 'confidence') val = `${Math.round(Number((evaluation as Record<string,unknown>)[k] ?? 0) * 100)}%`
                  return (
                    <div key={k} className="bg-slate-800/60 rounded-lg p-3">
                      <div className="text-xs text-slate-500 mb-1 capitalize">{k}</div>
                      <div className="text-sm text-white font-medium">{val}</div>
                    </div>
                  )
                })}
                {(evaluation as Record<string,unknown>).posting_legitimacy && (
                  <div className="bg-slate-800/60 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">Posting Legitimacy</div>
                    <div className={`text-sm font-medium ${
                      Number((evaluation as Record<string,unknown> & { posting_legitimacy?: { score: number } }).posting_legitimacy?.score ?? 5) >= 4
                        ? 'text-green-400' : Number((evaluation as Record<string,unknown> & { posting_legitimacy?: { score: number } }).posting_legitimacy?.score ?? 5) >= 2.5
                        ? 'text-amber-400' : 'text-red-400'
                    }`}>
                      {Number((evaluation as Record<string,unknown> & { posting_legitimacy?: { score: number } }).posting_legitimacy?.score ?? 5) >= 4
                        ? 'High Confidence' : Number((evaluation as Record<string,unknown> & { posting_legitimacy?: { score: number } }).posting_legitimacy?.score ?? 5) >= 2.5
                        ? 'Proceed with Caution' : 'Suspicious'}
                    </div>
                  </div>
                )}
              </div>
              {(evaluation as Record<string,unknown>).scores && (
                <div className="mb-4">
                  <div className="text-xs text-slate-600 mb-2">Block scores (hover for reasoning)</div>
                  <BlockScores scores={(evaluation as Record<string,unknown>).scores as Record<string, { score: number; reasoning: string }>} />
                </div>
              )}
              {(evaluation as Record<string,unknown>).cv_tailoring && typeof (evaluation as Record<string,unknown>).cv_tailoring === 'object' && (
                <div>
                  <div className="text-xs text-slate-600 mb-2">CV Tailoring Plan</div>
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {(((evaluation as Record<string,unknown>).cv_tailoring as Record<string,unknown>).inject_keywords as string[] ?? []).slice(0,8).map((k: string) => (
                      <span key={k} className="text-xs bg-blue-950/60 text-blue-400 px-1.5 py-0.5 rounded border border-blue-900/40">{k}</span>
                    ))}
                  </div>
                  <div className="text-xs text-slate-500">
                    Archetype: {String(((evaluation as Record<string,unknown>).cv_tailoring as Record<string,unknown>).archetype ?? '—')}
                    {((evaluation as Record<string,unknown>).cv_tailoring as Record<string,unknown>).summary_rewrite ? ' · Rewrite summary' : ''}
                    {((evaluation as Record<string,unknown>).cv_tailoring as Record<string,unknown>).reorder_experience ? ' · Reorder experience' : ''}
                  </div>
                </div>
              )}
            </div>
          )}

          {!evaluation && (
            <div className="bg-slate-900/50 border border-dashed border-slate-700 rounded-xl p-6 text-center">
              <div className="text-slate-500 text-sm mb-3">Evaluate this job to see fit score, archetype, and tailoring plan</div>
              <button onClick={handleEvaluate} disabled={evaluating}
                className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors">
                {evaluating ? 'Evaluating…' : '⚡ Evaluate Fit Now'}
              </button>
            </div>
          )}
        </div>
      )}

      {tab === 'Apply' && (
        <div className="space-y-5">
          {!evaluation && (
            <div className="bg-amber-950/20 border border-amber-800/50 rounded-xl p-4 text-sm text-amber-400">
              ⚡ Tip: Run <button onClick={() => { handleEvaluate(); setTab('Overview') }} className="underline">Evaluate Fit</button> first to get the best CV archetype match.
            </div>
          )}

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">Select CV Variant</div>
            <div className="grid grid-cols-3 gap-3 mb-5">
              {CV_VARIANTS.map(v => (
                <button key={v.id} onClick={() => setCvVariant(v)}
                  className={`p-3 rounded-xl border text-sm text-left transition-all ${
                    cvVariant.id === v.id ? 'border-blue-600 bg-blue-900/30 text-blue-300' : 'border-slate-700 bg-slate-800/50 text-slate-400 hover:border-slate-600'
                  }`}>
                  <div className="font-medium mb-1">{v.label}</div>
                  <div className="text-xs opacity-70 truncate">{v.path}</div>
                </button>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-3 mb-5">
              <div>
                <label className="text-xs text-slate-400 block mb-1.5">Archetype override</label>
                <input type="text" value={archetype} onChange={e => setArchetype(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500" />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1.5">Application mode</label>
                <select value={mode} onChange={e => setMode(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500">
                  <option value="draft">Draft — I review before submit</option>
                  <option value="auto">Auto — Submit directly</option>
                </select>
              </div>
            </div>

            <div className="flex gap-3">
              <button onClick={handleGenerateCv} disabled={generatingCv}
                className="flex-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white text-sm font-medium px-4 py-3 rounded-xl transition-colors">
                {generatingCv ? 'Generating CV…' : 'Generate Tailored CV'}
              </button>
              <button onClick={handleApply} disabled={applying || !hasUrl}
                title={!hasUrl ? 'No apply URL available for this listing' : ''}
                className="flex-1 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold px-4 py-3 rounded-xl transition-colors">
                {applying ? 'Starting Application…' : 'Apply with Agent →'}
              </button>
            </div>
            {!hasUrl && (
              <div className="mt-2 text-xs text-slate-500">
                Apply is disabled — no apply URL found for this listing. {jobUrl ? '' : 'Open the original posting to apply manually.'}
              </div>
            )}
          </div>

          {cvResult && (
            <div className="bg-slate-900 border border-green-900/50 rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Generated CV</div>
                <a href={getCvDownloadUrl(cvResult.pdf_path ?? '')} target="_blank" rel="noopener noreferrer"
                  className="text-xs bg-green-800/50 hover:bg-green-700/60 border border-green-700/60 text-green-300 px-3 py-1.5 rounded-lg transition-colors">
                  ⬇ Download PDF
                </a>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {[['Pages', cvResult.page_count], ['Size', `${cvResult.file_size_kb} KB`], ['Keywords', cvResult.keywords_injected?.length], ['Coverage', `${cvResult.coverage_percentage}%`]].map(([k, v]) => (
                  <div key={String(k)} className="bg-slate-800/60 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">{String(k)}</div>
                    <div className="text-sm text-white font-medium">{String(v ?? '—')}</div>
                  </div>
                ))}
              </div>
              {cvResult.keywords_injected && cvResult.keywords_injected.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {cvResult.keywords_injected.map(k => (
                    <span key={k} className="text-xs bg-blue-950/60 text-blue-400 px-1.5 py-0.5 rounded">{k}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {applyResult && (
            <div className={`border rounded-xl p-5 ${
              String(applyResult.status) === 'submitted' ? 'bg-green-950/30 border-green-800 text-green-300' :
              String(applyResult.status) === 'draft_saved' ? 'bg-blue-950/30 border-blue-800 text-blue-300' :
              String(applyResult.status) === 'duplicate_blocked' ? 'bg-amber-950/30 border-amber-800 text-amber-300' :
              'bg-slate-900 border-slate-700 text-slate-300'
            }`}>
              <div className="font-semibold mb-2 text-sm">
                {String(applyResult.status) === 'submitted' ? '✅ Application submitted!' :
                 String(applyResult.status) === 'draft_saved' ? '📋 Draft saved — open session to review and submit' :
                 String(applyResult.status) === 'duplicate_blocked' ? '⚠ Already applied to this role' :
                 String(applyResult.status)}
              </div>
              {applyResult.session_id && (
                <Link href={`/sessions/${applyResult.session_id}`}
                  className="text-xs underline opacity-80 hover:opacity-100">
                  Open Session →
                </Link>
              )}
            </div>
          )}
        </div>
      )}

      {tab === 'Outreach' && (
        <div className="space-y-4">
          {!outreach ? (
            <div className="bg-slate-900/50 border border-dashed border-slate-700 rounded-xl p-6 text-center">
              <div className="text-slate-500 text-sm mb-3">Generate a targeted cold outreach email for this role</div>
              <button onClick={handleOutreach} disabled={reaching}
                className="bg-purple-700 hover:bg-purple-600 disabled:opacity-50 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors">
                {reaching ? 'Generating…' : '✉ Generate Outreach Email'}
              </button>
            </div>
          ) : (
            <>
              {outreach.contact && (
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 text-xs text-slate-400">
                  <span className="text-slate-600 mr-2">To:</span>
                  {String((outreach.contact as Record<string,unknown>).name || '—')}
                  {(outreach.contact as Record<string,unknown>).email ? ` · ${String((outreach.contact as Record<string,unknown>).email)}` : ''}
                  {(outreach.contact as Record<string,unknown>).title ? ` · ${String((outreach.contact as Record<string,unknown>).title)}` : ''}
                </div>
              )}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs text-slate-500 font-medium uppercase tracking-wider">Subject</label>
                  <button onClick={() => handleCopy(outreachSubject)} className="text-xs text-slate-500 hover:text-slate-300 transition-colors">Copy</button>
                </div>
                <input type="text" value={outreachSubject} onChange={e => setOutreachSubject(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-purple-500" />
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs text-slate-500 font-medium uppercase tracking-wider">Body ({outreachBody.split(' ').length} words)</label>
                  <div className="flex gap-2">
                    <button onClick={handleOutreach} disabled={reaching} className="text-xs text-purple-400 hover:text-purple-300 transition-colors disabled:opacity-50">
                      {reaching ? 'Regenerating…' : '↺ Regenerate'}
                    </button>
                    <button onClick={() => handleCopy(`Subject: ${outreachSubject}\n\n${outreachBody}`)}
                      className={`text-xs px-3 py-1 rounded-lg border transition-colors ${
                        copied ? 'border-green-700 bg-green-900/40 text-green-400' : 'border-slate-700 text-slate-400 hover:text-white hover:border-slate-600'
                      }`}>
                      {copied ? '✓ Copied' : 'Copy All'}
                    </button>
                  </div>
                </div>
                <textarea value={outreachBody} onChange={e => setOutreachBody(e.target.value)} rows={14}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-purple-500 resize-none leading-relaxed" />
              </div>
              {outreach.matched_skills && outreach.matched_skills.length > 0 && (
                <div className="text-xs text-slate-500">
                  Skills highlighted: {outreach.matched_skills.join(', ')}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {tab === 'Cover Letter' && (
        <div className="space-y-4">
          {!letter ? (
            <div className="bg-slate-900/50 border border-dashed border-slate-700 rounded-xl p-6 text-center">
              <div className="text-slate-500 text-sm mb-3">Generate a concise, targeted cover letter for this role</div>
              <button onClick={handleCoverLetter} disabled={letterLoading}
                className="bg-teal-700 hover:bg-teal-600 disabled:opacity-50 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors">
                {letterLoading ? 'Writing…' : '📄 Generate Cover Letter'}
              </button>
            </div>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Cover Letter</div>
                <div className="flex gap-2">
                  <button onClick={handleCoverLetter} disabled={letterLoading} className="text-xs text-teal-400 hover:text-teal-300 disabled:opacity-50">
                    {letterLoading ? 'Writing…' : '↺ Regenerate'}
                  </button>
                  <button onClick={() => handleCopy(letter)}
                    className={`text-xs px-3 py-1 rounded-lg border transition-colors ${
                      copied ? 'border-green-700 bg-green-900/40 text-green-400' : 'border-slate-700 text-slate-400 hover:text-white'
                    }`}>
                    {copied ? '✓ Copied' : 'Copy'}
                  </button>
                </div>
              </div>
              <textarea value={letter} onChange={e => setLetter(e.target.value)} rows={18}
                className="w-full bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-teal-500 resize-none leading-relaxed" />
            </div>
          )}
        </div>
      )}

      {tab === 'Research' && (
        <div className="space-y-4">
          {!research ? (
            <div className="bg-slate-900/50 border border-dashed border-slate-700 rounded-xl p-6 text-center">
              <div className="text-slate-500 text-sm mb-2">Deep research analyzes the JD against your profile</div>
              <div className="text-slate-600 text-xs mb-4">Requires job description to be available</div>
              <button onClick={handleResearch} disabled={researching || !description}
                className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors">
                {researching ? 'Researching…' : description ? '🔍 Run Deep Research' : 'No description available'}
              </button>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3">
                {(['archetype', 'global_score', 'confidence', 'recommendation'] as const).map(k => {
                  let val = String((research as Record<string,unknown>)[k] ?? '—')
                  if (k === 'global_score') val = `${Math.round(Number((research as Record<string,unknown>)[k] ?? 0) * 20)}/100`
                  if (k === 'confidence') val = `${Math.round(Number((research as Record<string,unknown>)[k] ?? 0) * 100)}%`
                  const pct = k === 'global_score' ? Math.round(Number((research as Record<string,unknown>)[k] ?? 0) * 20) : 0
                  return (
                    <div key={k} className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                      <div className="text-xs text-slate-500 mb-1 capitalize">{k.replace(/_/g, ' ')}</div>
                      <div className={`text-sm font-medium ${
                        k === 'global_score' ? (pct >= 80 ? 'text-green-400' : pct >= 60 ? 'text-amber-400' : 'text-red-400') : 'text-white'
                      }`}>{val}</div>
                    </div>
                  )
                })}
              </div>
              {(research as Record<string,unknown>).application_answer_why && (
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                  <div className="text-xs text-slate-500 mb-2 font-semibold uppercase tracking-wider">Why do you want to work here?</div>
                  <div className="text-sm text-slate-300 leading-relaxed">{String((research as Record<string,unknown>).application_answer_why)}</div>
                </div>
              )}
              {(research as Record<string,unknown>).application_answer_strength && (
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                  <div className="text-xs text-slate-500 mb-2 font-semibold uppercase tracking-wider">What is your greatest strength?</div>
                  <div className="text-sm text-slate-300 leading-relaxed">{String((research as Record<string,unknown>).application_answer_strength)}</div>
                </div>
              )}
              {Array.isArray((research as Record<string,unknown>).interview_stories) && ((research as Record<string,unknown>).interview_stories as unknown[]).length > 0 && (
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                  <div className="text-xs text-slate-500 mb-3 font-semibold uppercase tracking-wider">Interview Stories (STAR)</div>
                  <div className="space-y-3">
                    {((research as Record<string,unknown>).interview_stories as Record<string,string>[]).slice(0,3).map((s, i) => (
                      <div key={i} className="bg-slate-800/60 rounded-lg p-3 text-xs text-slate-300">
                        <div className="font-medium text-white mb-2">{s.situation}</div>
                        <div><span className="text-slate-500">T:</span> {s.task}</div>
                        <div><span className="text-slate-500">A:</span> {s.action}</div>
                        <div><span className="text-slate-500">R:</span> {s.result}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
