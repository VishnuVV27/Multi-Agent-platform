import type { Metadata } from 'next'
import './globals.css'
import AnimatedBackground from '@/components/AnimatedBackground'

export const metadata: Metadata = {
  title: 'SupervisorFlow — Multi-Agent AI Orchestration',
  description: 'One prompt, a team of AI agents: LLM-planned DAGs, Temporal orchestration, human approvals, RAG memory, and full cost observability',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 min-h-screen">
        <AnimatedBackground />

        <nav className="sticky top-0 z-20 backdrop-blur-xl bg-slate-950/70 border-b border-white/10">
          <div className="max-w-7xl mx-auto flex items-center justify-between px-4 py-4">
            <a href="/" className="text-xl font-semibold tracking-tight hover:text-blue-300 transition-colors">
              🤖 SupervisorFlow
            </a>
            <div className="flex items-center gap-2 text-sm">
              <a href="/workflows" className="px-3 py-1.5 rounded-lg text-slate-300 hover:text-blue-300 hover:bg-blue-500/10 transition-colors">
                Workflows
              </a>
              <a href="/memory" className="px-3 py-1.5 rounded-lg text-slate-300 hover:text-blue-300 hover:bg-blue-500/10 transition-colors">
                Memory
              </a>
              <a href="/metrics" className="px-3 py-1.5 rounded-lg text-slate-300 hover:text-blue-300 hover:bg-blue-500/10 transition-colors">
                Metrics
              </a>
              <a href="/approvals" className="px-3 py-1.5 rounded-lg font-medium text-emerald-300 bg-emerald-500/10 border border-emerald-500/30 hover:bg-emerald-500/20 transition-colors">
                Approvals
              </a>
              <a href="/rate-limiting" className="px-3 py-1.5 rounded-lg text-slate-300 hover:text-blue-300 hover:bg-blue-500/10 transition-colors">
                Budget
              </a>
            </div>
          </div>
        </nav>

        <main className="relative z-10 max-w-7xl mx-auto p-4 md:p-6">
          {children}
        </main>
      </body>
    </html>
  )
}
