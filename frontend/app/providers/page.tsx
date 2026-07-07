'use client'

import { useEffect, useState } from 'react'
import api from '../../lib/api'

type ProviderInfo = { available: boolean; model?: string; base_url?: string; routes_to?: string }
type Providers = {
  anthropic?: ProviderInfo
  openrouter?: ProviderInfo
  gemini?: ProviderInfo
  ollama?: ProviderInfo
  hermes?: ProviderInfo
  active_provider?: string
}

export default function Providers() {
  const [providers, setProviders] = useState<Providers | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [prompt, setPrompt] = useState('What is 2+2? Reply in one sentence.')
  const [testResult, setTestResult] = useState('')
  const [testing, setTesting] = useState(false)
  const [testProvider, setTestProvider] = useState('')

  useEffect(() => {
    api.providers()
      .then(setProviders)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  function handleTest() {
    setTesting(true)
    setTestResult('')
    api.llmComplete({ prompt, provider: testProvider || undefined })
      .then((d: { result?: string; provider?: string }) => setTestResult(`[${d.provider ?? '?'}] ${d.result ?? ''}`))
      .catch((e: Error) => setTestResult(`Error: ${e.message}`))
      .finally(() => setTesting(false))
  }

  const providerList = providers
    ? Object.entries(providers).filter(([k]) => k !== 'active_provider')
    : []

  return (
    <div className="max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Providers</h1>
        <p className="text-slate-400 text-sm mt-1">
          LLM provider status and live test
          {providers?.active_provider && (
            <span className="ml-2 text-blue-400">· Active: {providers.active_provider}</span>
          )}
        </p>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm mb-6">{error}</div>
      )}

      {loading ? (
        <div className="text-slate-500 text-sm py-12 text-center">Loading…</div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {providerList.map(([name, info]) => {
              const p = info as ProviderInfo
              return (
                <div key={name} className={`bg-slate-900 border rounded-xl p-5 ${
                  p.available ? 'border-slate-700' : 'border-slate-800 opacity-60'
                }`}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="text-white font-semibold capitalize">{name}</div>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      p.available ? 'bg-green-900/60 text-green-400' : 'bg-slate-800 text-slate-500'
                    }`}>
                      {p.available ? 'Available' : 'Not configured'}
                    </span>
                  </div>
                  {p.model && (
                    <div className="text-xs text-slate-400 font-mono truncate">{p.model}</div>
                  )}
                  {p.routes_to && (
                    <div className="text-xs text-slate-500 mt-1">Routes to: {p.routes_to}</div>
                  )}
                  {p.base_url && (
                    <div className="text-xs text-slate-500 mt-1 font-mono truncate">{p.base_url}</div>
                  )}
                </div>
              )
            })}
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-white mb-4">Live LLM Test</h2>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Provider override (leave blank for auto)</label>
                <select
                  value={testProvider}
                  onChange={e => setTestProvider(e.target.value)}
                  className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                >
                  <option value="">Auto (active provider)</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="openrouter">OpenRouter</option>
                  <option value="gemini">Gemini</option>
                  <option value="hermes">Hermes</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">Prompt</label>
                <input
                  type="text"
                  value={prompt}
                  onChange={e => setPrompt(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>
              <button
                onClick={handleTest}
                disabled={testing}
                className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
              >
                {testing ? 'Calling LLM…' : 'Test'}
              </button>
              {testResult && (
                <div className="bg-slate-800/60 rounded-lg p-3 text-sm text-slate-300 whitespace-pre-wrap">
                  {testResult}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
