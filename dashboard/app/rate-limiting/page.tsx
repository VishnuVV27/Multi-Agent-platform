'use client'

import { Wallet, Gauge, Cpu } from 'lucide-react'
import GlassCard from '@/components/GlassCard'

function ProgressBar({ percent, tone }: { percent: number; tone: 'blue' | 'amber' | 'emerald' | 'red' }) {
  const barColor = {
    blue: 'bg-blue-500',
    amber: 'bg-amber-500',
    emerald: 'bg-emerald-500',
    red: 'bg-red-500',
  }[tone]

  return (
    <div className="w-full bg-white/5 rounded-full h-2 overflow-hidden">
      <div className={`h-2 rounded-full ${barColor} transition-all`} style={{ width: `${Math.min(percent, 100)}%` }} />
    </div>
  )
}

export default function RateLimitingPage() {
  const budgetUsed = 4.5
  const budgetLimit = 10.0
  const budgetPercent = (budgetUsed / budgetLimit) * 100

  const requestsUsed = 15
  const requestsLimit = 20
  const requestsPercent = (requestsUsed / requestsLimit) * 100

  const tokensUsed = 62000
  const tokensLimit = 100000
  const tokensPercent = (tokensUsed / tokensLimit) * 100

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <h1 className="text-4xl font-bold text-slate-100">Budget & Rate Limiting</h1>
        <p className="text-slate-400">Free tier — resets monthly</p>
      </div>

      <div className="bento-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
        <GlassCard tone={budgetPercent > 80 ? 'red' : 'blue'} className="p-5">
          <div className="flex items-center gap-2 text-blue-300 mb-3">
            <Wallet className="w-4 h-4" />
            <p className="text-xs font-medium uppercase tracking-wide">Monthly Budget</p>
          </div>
          <p className="text-3xl font-bold text-slate-100 mb-3">${budgetUsed.toFixed(2)}</p>
          <ProgressBar percent={budgetPercent} tone={budgetPercent > 80 ? 'red' : 'blue'} />
          <p className="text-xs text-slate-400 mt-2">${budgetUsed.toFixed(2)} / ${budgetLimit.toFixed(2)} ({budgetPercent.toFixed(0)}%)</p>
        </GlassCard>

        <GlassCard tone={requestsPercent > 80 ? 'amber' : 'emerald'} className="p-5">
          <div className="flex items-center gap-2 text-emerald-300 mb-3">
            <Gauge className="w-4 h-4" />
            <p className="text-xs font-medium uppercase tracking-wide">Requests Per Minute</p>
          </div>
          <p className="text-3xl font-bold text-slate-100 mb-3">{requestsUsed} / {requestsLimit}</p>
          <ProgressBar percent={requestsPercent} tone={requestsPercent > 80 ? 'amber' : 'emerald'} />
          <p className="text-xs text-slate-400 mt-2">{requestsLimit - requestsUsed} remaining this minute</p>
        </GlassCard>

        <GlassCard tone={tokensPercent > 80 ? 'amber' : 'blue'} className="p-5">
          <div className="flex items-center gap-2 text-blue-300 mb-3">
            <Cpu className="w-4 h-4" />
            <p className="text-xs font-medium uppercase tracking-wide">Daily Token Usage</p>
          </div>
          <p className="text-3xl font-bold text-slate-100 mb-3">{(tokensUsed / 1000).toFixed(0)}K / {(tokensLimit / 1000).toFixed(0)}K</p>
          <ProgressBar percent={tokensPercent} tone={tokensPercent > 80 ? 'amber' : 'blue'} />
          <p className="text-xs text-slate-400 mt-2">{((tokensLimit - tokensUsed) / 1000).toFixed(0)}K tokens remaining</p>
        </GlassCard>
      </div>

      <GlassCard tone="slate" className="p-5">
        <h3 className="font-semibold text-slate-100 mb-4">Tier: Free</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-slate-400 text-xs uppercase tracking-wide mb-1">Requests/Min</p>
            <p className="font-mono text-slate-100 text-lg">20</p>
          </div>
          <div>
            <p className="text-slate-400 text-xs uppercase tracking-wide mb-1">Requests/Hour</p>
            <p className="font-mono text-slate-100 text-lg">500</p>
          </div>
          <div>
            <p className="text-slate-400 text-xs uppercase tracking-wide mb-1">Monthly Budget</p>
            <p className="font-mono text-slate-100 text-lg">$10.00</p>
          </div>
          <div>
            <p className="text-slate-400 text-xs uppercase tracking-wide mb-1">Daily Tokens</p>
            <p className="font-mono text-slate-100 text-lg">100,000</p>
          </div>
        </div>
      </GlassCard>
    </div>
  )
}
