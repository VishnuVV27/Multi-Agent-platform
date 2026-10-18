'use client'

import { useEffect, useState } from 'react'
import { AreaChart, Area, PieChart, Pie, Cell, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { DollarSign, ListChecks, CheckCircle2, Clock } from 'lucide-react'
import GlassCard from '@/components/GlassCard'
import { apiFetch, ApiError } from '@/lib/api'

interface CostPoint {
  date: string
  cost: number
}

interface AgentCost {
  name: string
  value: number
}

interface CostMetrics {
  total_cost: number
  total_tokens: number
  request_count: number
  cost_by_agent: Record<string, number>
}

interface LatencyByAgent {
  [agentId: string]: { avg_latency_ms: number; sample_count: number }
}

interface SuccessRate {
  total_runs: number
  success_rate: number
}

const AGENT_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#f97316']

export default function MetricsPage() {
  const [costHistory, setCostHistory] = useState<CostPoint[]>([])
  const [costMetrics, setCostMetrics] = useState<CostMetrics | null>(null)
  const [latency, setLatency] = useState<LatencyByAgent>({})
  const [successRate, setSuccessRate] = useState<SuccessRate | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        setError(null)
        const [daily, costs, latencyData, success] = await Promise.all([
          apiFetch<{ series: CostPoint[] }>('/api/observability/metrics/costs/daily?days=7'),
          apiFetch<CostMetrics>('/api/observability/metrics/costs?days=7'),
          apiFetch<{ latency_by_agent: LatencyByAgent }>('/api/observability/metrics/latency'),
          apiFetch<SuccessRate>('/api/observability/metrics/success-rate?days=7'),
        ])
        setCostHistory(daily.series)
        setCostMetrics(costs)
        setLatency(latencyData.latency_by_agent)
        setSuccessRate(success)
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Could not reach the API')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const costByAgent: AgentCost[] = costMetrics
    ? Object.entries(costMetrics.cost_by_agent).map(([name, value]) => ({ name, value }))
    : []

  const latencyEntries = Object.values(latency)
  const avgLatencyMs = latencyEntries.length
    ? latencyEntries.reduce((sum, l) => sum + l.avg_latency_ms * l.sample_count, 0) /
      latencyEntries.reduce((sum, l) => sum + l.sample_count, 0)
    : 0

  if (loading) {
    return <div className="text-slate-400 text-center py-16">Loading metrics...</div>
  }

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <h1 className="text-4xl font-bold text-slate-100">Metrics & Analytics</h1>
        <p className="text-slate-400">Cost, throughput, and reliability across all workflows</p>
      </div>

      {error && (
        <GlassCard tone="red" className="p-4 text-sm text-red-200">
          Couldn't load metrics from the API: {error}
        </GlassCard>
      )}

      <div className="bento-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
        <GlassCard tone="emerald" className="p-4">
          <div className="flex items-center gap-2 text-emerald-300 mb-1">
            <DollarSign className="w-4 h-4" />
            <p className="text-xs font-medium">Total Cost (7d)</p>
          </div>
          <p className="text-3xl font-bold text-slate-100">
            ${(costMetrics?.total_cost ?? 0) < 0.01 ? (costMetrics?.total_cost ?? 0).toFixed(4) : (costMetrics?.total_cost ?? 0).toFixed(2)}
          </p>
        </GlassCard>
        <GlassCard tone="blue" className="p-4">
          <div className="flex items-center gap-2 text-blue-300 mb-1">
            <ListChecks className="w-4 h-4" />
            <p className="text-xs font-medium">Agent Runs (7d)</p>
          </div>
          <p className="text-3xl font-bold text-slate-100">{costMetrics?.request_count ?? 0}</p>
        </GlassCard>
        <GlassCard tone="emerald" className="p-4">
          <div className="flex items-center gap-2 text-emerald-300 mb-1">
            <CheckCircle2 className="w-4 h-4" />
            <p className="text-xs font-medium">Success Rate</p>
          </div>
          <p className="text-3xl font-bold text-slate-100">{((successRate?.success_rate ?? 0) * 100).toFixed(0)}%</p>
        </GlassCard>
        <GlassCard tone="amber" className="p-4">
          <div className="flex items-center gap-2 text-amber-300 mb-1">
            <Clock className="w-4 h-4" />
            <p className="text-xs font-medium">Avg Latency</p>
          </div>
          <p className="text-3xl font-bold text-slate-100">{(avgLatencyMs / 1000).toFixed(1)}s</p>
        </GlassCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GlassCard tone="slate" className="p-5 lg:col-span-2">
          <h3 className="font-semibold text-slate-100 mb-4">Cost Over Time (7 days)</h3>
          {costHistory.length === 0 ? (
            <p className="text-sm text-slate-400 py-16 text-center">No agent runs recorded yet.</p>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={costHistory}>
                  <defs>
                    <linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="date" stroke="rgba(226,232,240,0.5)" fontSize={12} />
                  <YAxis stroke="rgba(226,232,240,0.5)" fontSize={12} tickFormatter={(v) => `$${v}`} />
                  <Tooltip
                    contentStyle={{ background: 'rgba(15,23,42,0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12 }}
                    labelStyle={{ color: '#e2e8f0' }}
                    formatter={(value: number) => [`$${value.toFixed(4)}`, 'Cost']}
                  />
                  <Area type="monotone" dataKey="cost" stroke="#3b82f6" fill="url(#costGradient)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </GlassCard>

        <GlassCard tone="slate" className="p-5">
          <h3 className="font-semibold text-slate-100 mb-4">Cost by Agent</h3>
          {costByAgent.length === 0 ? (
            <p className="text-sm text-slate-400 py-16 text-center">No agent runs recorded yet.</p>
          ) : (
            <>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={costByAgent} dataKey="value" nameKey="name" innerRadius={45} outerRadius={70} paddingAngle={3}>
                      {costByAgent.map((entry, index) => (
                        <Cell key={entry.name} fill={AGENT_COLORS[index % AGENT_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ background: 'rgba(15,23,42,0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12 }}
                      formatter={(value: number) => `$${value.toFixed(4)}`}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-1.5 mt-2">
                {costByAgent.map((agent, index) => (
                  <div key={agent.name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: AGENT_COLORS[index % AGENT_COLORS.length] }} />
                      <span className="text-slate-300">{agent.name.replace('_agent', '')}</span>
                    </div>
                    <span className="text-slate-400 font-mono">${agent.value.toFixed(4)}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </GlassCard>
      </div>
    </div>
  )
}
