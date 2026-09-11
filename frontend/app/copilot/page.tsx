'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import api from '../../lib/api'

type Action = { action_key: string; label: string }
type Message = { role: 'user' | 'assistant'; content: string; actions?: Action[]; at?: string }

const SUGGESTIONS = [
  'What jobs should I apply to today and why?',
  'Which of my applications need a follow-up?',
  'How does my profile stack up against the current market?',
  'Help me prepare for interviews with my top-match company.',
]

const ACTION_ROUTES: Record<string, string> = {
  scan: '/',
  follow_ups: '/follow-ups',
  insights: '/insights',
}

export default function CopilotPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [error, setError] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.copilotHistory()
      .then(r => setMessages(r.messages ?? []))
      .catch(() => {})
      .finally(() => setLoadingHistory(false))
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function send(text?: string) {
    const message = (text ?? input).trim()
    if (!message || sending) return
    setInput('')
    setError('')
    setSending(true)
    setMessages(m => [...m, { role: 'user', content: message }])

    api.copilotChat({ message })
      .then(r => {
        setMessages(m => [...m, { role: 'assistant', content: r.reply, actions: r.actions ?? [] }])
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setSending(false))
  }

  function runAction(action: Action) {
    const key = action.action_key
    if (key === 'evaluate_job' || key === 'generate_cv' || key === 'outreach') {
      // these are per-job actions — send the user to the job browser to pick one
      router.push('/jobs')
      return
    }
    const route = ACTION_ROUTES[key]
    if (route) router.push(route)
  }

  return (
    <main className="pl-56 h-screen bg-slate-950 text-slate-200 flex flex-col">
      <div className="px-8 pt-8 pb-4 border-b border-slate-800 bg-slate-950/90">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">🤖 AI Copilot</h1>
        <p className="text-sm text-slate-500">Your 24/7 career copilot — grounded in your live feed, applications and pipeline.</p>
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="max-w-3xl mx-auto space-y-4">
          {loadingHistory && <div className="text-slate-600 text-sm">Loading conversation…</div>}

          {!loadingHistory && messages.length === 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <div className="text-white font-semibold mb-2">Hi — I&apos;m Orion, your job-search copilot.</div>
              <p className="text-sm text-slate-400 mb-4">
                I can see your live job feed, match scores, applications and follow-ups. Ask me anything, or start with:
              </p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map(s => (
                  <button key={s} onClick={() => send(s)}
                    className="text-left text-xs bg-slate-950/70 hover:bg-slate-800 border border-slate-800 hover:border-blue-800 rounded-full px-3 py-2 text-slate-300 transition-colors">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap ${
                m.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-sm'
                  : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-sm'
              }`}>
                {m.content}
                {!!m.actions?.length && (
                  <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-slate-800">
                    {m.actions.map((a, j) => (
                      <button key={j} onClick={() => runAction(a)}
                        className="text-xs bg-blue-950/60 hover:bg-blue-900 border border-blue-900 text-blue-300 rounded-lg px-3 py-1.5 transition-colors">
                        {a.label} →
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {sending && (
            <div className="flex justify-start">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl rounded-bl-sm px-4 py-3">
                <div className="flex gap-1.5">
                  <span className="w-2 h-2 bg-slate-600 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-slate-600 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-slate-600 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
          {error && <div className="text-red-400 text-sm">{error}</div>}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="border-t border-slate-800 px-8 py-4">
        <div className="max-w-3xl mx-auto flex gap-3">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            placeholder="Ask about your search, matches, applications…"
            className="flex-1 bg-slate-900 border border-slate-800 focus:border-blue-700 outline-none rounded-xl px-4 py-3 text-sm placeholder:text-slate-600"
          />
          <button
            onClick={() => send()}
            disabled={sending || !input.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:hover:bg-blue-600 text-white rounded-xl px-6 py-3 text-sm font-semibold transition-colors">
            Send
          </button>
        </div>
      </div>
    </main>
  )
}
