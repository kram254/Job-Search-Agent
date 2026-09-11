'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import api from '../lib/api'

const groups = [
  {
    label: 'Main',
    links: [
      { href: '/', label: 'Dashboard' },
      { href: '/jobs', label: 'Browse Jobs' },
      { href: '/discover', label: 'Discover' },
      { href: '/insights', label: 'Insights' },
    ],
  },
  {
    label: 'Copilot',
    links: [
      { href: '/copilot', label: '🤖 AI Copilot', highlight: true },
    ],
  },
  {
    label: 'Apply',
    links: [
      { href: '/bulk-apply', label: '⚡ Bulk Apply', highlight: true },
      { href: '/sessions', label: 'Sessions' },
      { href: '/applications', label: 'Applications' },
      { href: '/follow-ups', label: 'Follow-ups' },
      { href: '/pipeline', label: 'Pipeline' },
    ],
  },
  {
    label: 'Organize',
    links: [
      { href: '/alerts', label: '🔔 Alerts', badgeKey: 'alerts' as const },
      { href: '/interviews', label: '📅 Interviews' },
      { href: '/schedule', label: 'Schedule' },
      { href: '/analytics', label: 'Analytics' },
      { href: '/story-bank', label: 'Story Bank' },
      { href: '/providers', label: 'Providers' },
    ],
  },
]

export default function Nav() {
  const path = usePathname()
  // unread alert count for the nav badge (Phase 3); silent on failure —
  // the badge is cosmetic and must never break navigation
  const [unreadAlerts, setUnreadAlerts] = useState(0)

  useEffect(() => {
    let cancelled = false
    api.alerts({ unread_only: true, limit: 1 })
      .then((d: { unread_count?: number }) => { if (!cancelled) setUnreadAlerts(d.unread_count ?? 0) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [path])

  return (
    <aside className="fixed top-0 left-0 h-screen w-56 bg-slate-900 border-r border-slate-800 flex flex-col z-20 overflow-y-auto">
      <div className="px-6 py-5 border-b border-slate-800">
        <div className="text-blue-400 font-bold text-sm tracking-wide">JOB SEARCH AGENT</div>
        <div className="text-slate-600 text-xs mt-0.5">kram254 · Render</div>
      </div>
      <nav className="flex-1 py-3 px-3">
        {groups.map(g => (
          <div key={g.label} className="mb-4">
            <div className="text-xs text-slate-700 uppercase tracking-widest px-3 mb-1">{g.label}</div>
            {g.links.map(l => {
              const badge = 'badgeKey' in l && l.badgeKey === 'alerts' ? unreadAlerts : 0
              return (
                <Link key={l.href} href={l.href}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg mb-0.5 text-sm font-medium transition-all ${
                    path === l.href
                      ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/30'
                      : (l as { highlight?: boolean }).highlight
                      ? 'text-blue-400 hover:text-white hover:bg-blue-900/40 border border-blue-900/40'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800'
                  }`}>
                  <span>{l.label}</span>
                  {badge > 0 && (
                    <span className="text-[10px] font-bold bg-amber-500 text-slate-950 rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1">
                      {badge > 9 ? '9+' : badge}
                    </span>
                  )}
                </Link>
              )
            })}
          </div>
        ))}
      </nav>
      <div className="px-5 py-4 border-t border-slate-800 text-xs text-slate-700">
        v0.3.0 · JobRight parity
      </div>
    </aside>
  )
}
