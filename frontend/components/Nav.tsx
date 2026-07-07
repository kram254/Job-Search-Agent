'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const groups = [
  {
    label: 'Main',
    links: [
      { href: '/', label: 'Dashboard' },
      { href: '/jobs', label: 'Jobs' },
      { href: '/discover', label: 'Discover' },
    ],
  },
  {
    label: 'Applications',
    links: [
      { href: '/sessions', label: 'Sessions' },
      { href: '/applications', label: 'Applications' },
      { href: '/follow-ups', label: 'Follow-ups' },
      { href: '/pipeline', label: 'Pipeline' },
    ],
  },
  {
    label: 'Tools',
    links: [
      { href: '/schedule', label: 'Schedule' },
      { href: '/analytics', label: 'Analytics' },
      { href: '/story-bank', label: 'Story Bank' },
      { href: '/providers', label: 'Providers' },
    ],
  },
]

export default function Nav() {
  const path = usePathname()
  return (
    <aside className="fixed top-0 left-0 h-screen w-56 bg-slate-900 border-r border-slate-800 flex flex-col z-20 overflow-y-auto">
      <div className="px-6 py-5 border-b border-slate-800">
        <div className="text-blue-400 font-bold text-sm tracking-wide">JOB SEARCH AGENT</div>
        <div className="text-slate-600 text-xs mt-0.5">kram254</div>
      </div>
      <nav className="flex-1 py-3 px-3">
        {groups.map(g => (
          <div key={g.label} className="mb-4">
            <div className="text-xs text-slate-600 uppercase tracking-widest px-3 mb-1">{g.label}</div>
            {g.links.map(l => (
              <Link
                key={l.href}
                href={l.href}
                className={`flex items-center px-3 py-2 rounded-lg mb-0.5 text-sm font-medium transition-all ${
                  path === l.href
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800'
                }`}
              >
                {l.label}
              </Link>
            ))}
          </div>
        ))}
      </nav>
      <div className="px-5 py-4 border-t border-slate-800 text-xs text-slate-700">
        Render · v0.1.0
      </div>
    </aside>
  )
}
