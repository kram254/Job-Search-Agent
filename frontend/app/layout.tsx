import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import Nav from '../components/Nav'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Job Search Agent',
  description: 'AI-powered job application agent',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-slate-950 text-slate-100`}>
        <div className="flex min-h-screen">
          <Nav />
          <main className="flex-1 ml-56 p-8">{children}</main>
        </div>
      </body>
    </html>
  )
}
