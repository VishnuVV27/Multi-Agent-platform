'use client'

import { useEffect, useState } from 'react'
import { AreaChart, Area, PieChart, Pie, Cell, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { DollarSign, ListChecks, CheckCircle2, Clock } from 'lucide-react'
import GlassCard from '@/components/GlassCard'

interface CostPoint {
  day: string
  cost: number
}

interface AgentCost {
  name: string
  value: number
}

const AGENT_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#f97316']

export default function MetricsPage() {
  const [costHistory, setCostHistory] = useState<CostPoint[]>([])
  const [costByAgent, setCostByAgent] = useState<AgentCost[]>([])

  useEffect(() => {
    // Sample data until /api/observability/metrics/costs is wired to real history
    setCostHistory([
      { day: 'Mon', cost: 0.42 },
      { day: 'Tue', cost: 0.58 },
      { day: 'Wed', cost: 0.51 },
      { day: 'Thu', cost: 0.73 },
      { day: 'Fri', cost: 0.68 },
      { day: 'Sat', cost: 0.35 },
      { day: 'Sun', cost: 0.4 },
    ])
    setCostByAgent([
      { name: 'research_agent', value: 1.8 },
      { name: 'analysis_agent', value: 1.1 },
      { name: 'writer_agent', value: 0.9 },
      { name: 'supervisor_agent', value: 0.3 },
    ])
  }, [])

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <h1 className="text-4xl font-bold text-slate-100">Metrics & Analytics</h1>
        <p className="text-slate-400">Cost, throughput, and reliability across all workflows</p>
      </div>

      <div className="bento-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
        <GlassCard tone="emerald" className="p-4">
          <div className="flex items-center gap-2 text-emerald-300 mb-1">
            <DollarSign className="w-4 h-4" />
            <p className="text-xs font-medium">Total Cost (Today)</p>
          </div>
          <p className="text-3xl font-bold text-slate-100">$4.10</p>
        </GlassCard>
        <GlassCard tone="blue" className="p-4">
          <div className="flex items-center gap-2 text-blue-300 mb-1">
            <ListChecks className="w-4 h-4" />
            <p className="text-xs font-medium">Workflows (Today)</p>
          </div>
          <p className="text-3xl font-bold text-slate-100">18</p>
        </GlassCard>
        <GlassCard tone="emerald" className="p-4">
          <div className="flex items-center gap-2 text-emerald-300 mb-1">
            <CheckCircle2 className="w-4 h-4" />
            <p className="text-xs font-medium">Success Rate</p>
          </div>
          <p className="text-3xl font-bold text-slate-100">95%</p>
        </GlassCard>
        <GlassCard tone="amber" className="p-4">
          <div className="flex items-center gap-2 text-amber-300 mb-1">
            <Clock className="w-4 h-4" />
            <p className="text-xs font-medium">Avg Latency</p>
          </div>
          <p className="text-3xl font-bold text-slate-100">5.4s</p>
        </GlassCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GlassCard tone="slate" className="p-5 lg:col-span-2">
          <h3 className="font-semibold text-slate-100 mb-4">Cost Over Time (7 days)</h3>
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
                <XAxis dataKey="day" stroke="rgba(226,232,240,0.5)" fontSize={12} />
                <YAxis stroke="rgba(226,232,240,0.5)" fontSize={12} tickFormatter={(v) => `$${v}`} />
                <Tooltip
                  contentStyle={{ background: 'rgba(15,23,42,0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12 }}
                  labelStyle={{ color: '#e2e8f0' }}
                  formatter={(value: number) => [`$${value.toFixed(2)}`, 'Cost']}
                />
                <Area type="monotone" dataKey="cost" stroke="#3b82f6" fill="url(#costGradient)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        <GlassCard tone="slate" className="p-5">
          <h3 className="font-semibold text-slate-100 mb-4">Cost by Agent</h3>
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
                  formatter={(value: number) => `$${value.toFixed(2)}`}
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
                <span className="text-slate-400 font-mono">${agent.value.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
    </div>
  )
}
