'use client'

import { useEffect, useState } from 'react'
import { Wallet, Gauge, Clock } from 'lucide-react'
import GlassCard from '@/components/GlassCard'
import { apiFetch, ApiError, DEFAULT_USER_ID } from '@/lib/api'

interface BudgetStatus {
  tier: string
  monthly_budget: number | null
  used: number
  remaining: number | null
  percentage_used: number
  is_unlimited: boolean
}

interface RateLimitCheck {
  remaining: { requests_per_minute: number; requests_per_hour: number }
  status: string
}

interface UserPolicy {
  requests_per_minute: number
  requests_per_hour: number
  monthly_budget: number | null
  max_tokens_per_day: number | null
}

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
  const [budget, setBudget] = useState<BudgetStatus | null>(null)
  const [rateLimit, setRateLimit] = useState<RateLimitCheck | null>(null)
  const [policy, setPolicy] = useState<UserPolicy | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        setError(null)
        const [budgetData, rateLimitData, policyData] = await Promise.all([
          apiFetch<BudgetStatus>(`/api/rate-limiting/budget/${DEFAULT_USER_ID}`),
          apiFetch<RateLimitCheck>(`/api/rate-limiting/check/${DEFAULT_USER_ID}`),
          apiFetch<{ policy: UserPolicy }>('/api/rate-limiting/policies/users/free'),
        ])
        setBudget(budgetData)
        setRateLimit(rateLimitData)
        setPolicy(policyData.policy)
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Could not reach the API')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) {
    return <div className="text-slate-400 text-center py-16">Loading budget status...</div>
  }

  if (error) {
    return (
      <GlassCard tone="red" className="p-6 text-sm text-red-200">
        Couldn't load rate limiting data: {error}
      </GlassCard>
    )
  }

  const budgetLimit = budget?.monthly_budget ?? null
  const budgetUsed = budget?.used ?? 0
  const budgetPercent = budget?.percentage_used ?? 0

  const rpmLimit = policy?.requests_per_minute ?? 0
  const rpmRemaining = rateLimit?.remaining.requests_per_minute ?? 0
  const rpmUsed = Math.max(0, rpmLimit - rpmRemaining)
  const rpmPercent = rpmLimit > 0 ? (rpmUsed / rpmLimit) * 100 : 0

  const rphLimit = policy?.requests_per_hour ?? 0
  const rphRemaining = rateLimit?.remaining.requests_per_hour ?? 0
  const rphUsed = Math.max(0, rphLimit - rphRemaining)
  const rphPercent = rphLimit > 0 ? (rphUsed / rphLimit) * 100 : 0

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <h1 className="text-4xl font-bold text-slate-100">Budget & Rate Limiting</h1>
        <p className="text-slate-400">
          Tier: {budget?.tier ?? 'free'} {budget?.is_unlimited ? '(unlimited)' : '— resets monthly'}
        </p>
      </div>

      <div className="bento-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
        <GlassCard tone={budgetPercent > 80 ? 'red' : 'blue'} className="p-5">
          <div className="flex items-center gap-2 text-blue-300 mb-3">
            <Wallet className="w-4 h-4" />
            <p className="text-xs font-medium uppercase tracking-wide">Monthly Budget</p>
          </div>
          <p className="text-3xl font-bold text-slate-100 mb-3">${budgetUsed < 0.01 && budgetUsed > 0 ? budgetUsed.toFixed(4) : budgetUsed.toFixed(2)}</p>
          {budgetLimit != null ? (
            <>
              <ProgressBar percent={budgetPercent} tone={budgetPercent > 80 ? 'red' : 'blue'} />
              <p className="text-xs text-slate-400 mt-2">
                ${budgetUsed < 0.01 && budgetUsed > 0 ? budgetUsed.toFixed(4) : budgetUsed.toFixed(2)} / ${budgetLimit.toFixed(2)} ({budgetPercent.toFixed(2)}%)
              </p>
            </>
          ) : (
            <p className="text-xs text-slate-400 mt-2">Unlimited budget</p>
          )}
        </GlassCard>

        <GlassCard tone={rpmPercent > 80 ? 'amber' : 'emerald'} className="p-5">
          <div className="flex items-center gap-2 text-emerald-300 mb-3">
            <Gauge className="w-4 h-4" />
            <p className="text-xs font-medium uppercase tracking-wide">Requests Per Minute</p>
          </div>
          <p className="text-3xl font-bold text-slate-100 mb-3">{rpmUsed} / {rpmLimit}</p>
          <ProgressBar percent={rpmPercent} tone={rpmPercent > 80 ? 'amber' : 'emerald'} />
          <p className="text-xs text-slate-400 mt-2">{rpmRemaining} remaining this minute</p>
        </GlassCard>

        <GlassCard tone={rphPercent > 80 ? 'amber' : 'blue'} className="p-5">
          <div className="flex items-center gap-2 text-blue-300 mb-3">
            <Clock className="w-4 h-4" />
            <p className="text-xs font-medium uppercase tracking-wide">Requests Per Hour</p>
          </div>
          <p className="text-3xl font-bold text-slate-100 mb-3">{rphUsed} / {rphLimit}</p>
          <ProgressBar percent={rphPercent} tone={rphPercent > 80 ? 'amber' : 'blue'} />
          <p className="text-xs text-slate-400 mt-2">{rphRemaining} remaining this hour</p>
        </GlassCard>
      </div>

      <GlassCard tone="slate" className="p-5">
        <h3 className="font-semibold text-slate-100 mb-4">Tier: {budget?.tier ?? 'free'}</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-slate-400 text-xs uppercase tracking-wide mb-1">Requests/Min</p>
            <p className="font-mono text-slate-100 text-lg">{policy?.requests_per_minute ?? '—'}</p>
          </div>
          <div>
            <p className="text-slate-400 text-xs uppercase tracking-wide mb-1">Requests/Hour</p>
            <p className="font-mono text-slate-100 text-lg">{policy?.requests_per_hour ?? '—'}</p>
          </div>
          <div>
            <p className="text-slate-400 text-xs uppercase tracking-wide mb-1">Monthly Budget</p>
            <p className="font-mono text-slate-100 text-lg">
              {policy?.monthly_budget != null ? `$${policy.monthly_budget.toFixed(2)}` : 'Unlimited'}
            </p>
          </div>
          <div>
            <p className="text-slate-400 text-xs uppercase tracking-wide mb-1">Daily Token Limit</p>
            <p className="font-mono text-slate-100 text-lg">
              {policy?.max_tokens_per_day != null ? policy.max_tokens_per_day.toLocaleString() : 'Unlimited'}
            </p>
          </div>
        </div>
      </GlassCard>
    </div>
  )
}
