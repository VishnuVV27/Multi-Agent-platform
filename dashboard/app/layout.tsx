import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Multi-Agent AI Platform - Dashboard',
  description: 'Monitor and manage AI workflows',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100">
        <nav className="border-b border-slate-800 bg-slate-900 p-4">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <h1 className="text-2xl font-bold">🤖 Multi-Agent Platform</h1>
            <div className="flex gap-4">
              <a href="/" className="hover:text-blue-400">Workflows</a>
              <a href="/metrics" className="hover:text-blue-400">Metrics</a>
              <a href="/rate-limiting" className="hover:text-blue-400">Budget</a>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto p-4">
          {children}
        </main>
      </body>
    </html>
  )
}
