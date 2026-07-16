'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { ArrowLeft, Activity, Clock, DollarSign, Cpu } from 'lucide-react'
import Link from 'next/link'
import GlassCard from '@/components/GlassCard'
import StatusBadge from '@/components/StatusBadge'

interface Agent {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  duration_ms?: number
  cost?: number
  tokens?: number
}

interface WorkflowDetail {
  workflow_id: string
  user_request: string
  status: string
  agents: Agent[]
  total_duration_ms?: number
  total_cost?: number
  total_tokens?: number
  created_at: string
  completed_at?: string
}

export default function WorkflowDetail() {
  const params = useParams()
  const workflow_id = params.id as string
  const [workflow, setWorkflow] = useState<WorkflowDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Sample data until the backend exposes per-workflow persistence (Step 12 MVP)
    const timer = setTimeout(() => {
      setWorkflow({
        workflow_id,
        user_request: 'Research AI trends and write report',
        status: 'completed',
        agents: [
          { id: 'research_agent', name: 'Research Agent', status: 'completed', duration_ms: 8000, cost: 0.08, tokens: 3200 },
          { id: 'writer_agent', name: 'Writer Agent', status: 'completed', duration_ms: 4500, cost: 0.04, tokens: 1800 },
        ],
        total_duration_ms: 12500,
        total_cost: 0.12,
        total_tokens: 5000,
        created_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
      })
      setLoading(false)
    }, 200)
    return () => clearTimeout(timer)
  }, [workflow_id])

  if (loading) {
    return (
      <div className="text-center py-16">
        <Activity className="w-8 h-8 animate-spin mx-auto mb-4 text-blue-400" />
        <p className="text-slate-400">Loading...</p>
      </div>
    )
  }

  if (!workflow) return <div className="text-slate-400">Workflow not found</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/" className="p-2 rounded-lg hover:bg-white/5 transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <h1 className="text-2xl md:text-3xl font-bold font-mono">{workflow.workflow_id}</h1>
        <StatusBadge status={workflow.status} />
      </div>

      <GlassCard tone="slate" className="p-5">
        <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Request</h3>
        <p className="text-slate-200">{workflow.user_request}</p>
      </GlassCard>

      <div className="bento-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))' }}>
        <GlassCard tone="blue" className="p-4">
          <div className="flex items-center gap-2 text-blue-300 mb-1">
            <Clock className="w-4 h-4" />
            <p className="text-xs font-medium">Duration</p>
          </div>
          <p className="text-2xl font-bold text-slate-100">{((workflow.total_duration_ms ?? 0) / 1000).toFixed(1)}s</p>
        </GlassCard>
        <GlassCard tone="emerald" className="p-4">
          <div className="flex items-center gap-2 text-emerald-300 mb-1">
            <DollarSign className="w-4 h-4" />
            <p className="text-xs font-medium">Cost</p>
          </div>
          <p className="text-2xl font-bold text-slate-100">${workflow.total_cost?.toFixed(4) ?? '0.0000'}</p>
        </GlassCard>
        <GlassCard tone="amber" className="p-4">
          <div className="flex items-center gap-2 text-amber-300 mb-1">
            <Cpu className="w-4 h-4" />
            <p className="text-xs font-medium">Tokens</p>
          </div>
          <p className="text-2xl font-bold text-slate-100">{workflow.total_tokens ?? 0}</p>
        </GlassCard>
      </div>

      <GlassCard tone="slate" className="p-5">
        <h3 className="font-semibold text-slate-100 mb-4">Agent Timeline</h3>
        <div className="space-y-3">
          {workflow.agents.map((agent) => (
            <div key={agent.id} className="flex items-center gap-4 p-3 rounded-xl bg-white/5 border border-white/10">
              <div className="w-32 shrink-0">
                <p className="font-mono text-sm text-slate-200">{agent.name}</p>
              </div>
              <div className="flex-1">
                <div className="w-full bg-slate-800 rounded-full h-1.5">
                  <div className="h-1.5 rounded-full bg-emerald-500" style={{ width: '100%' }} />
                </div>
              </div>
              <div className="flex gap-4 text-right text-sm shrink-0">
                <div>
                  <p className="text-xs text-slate-400">Duration</p>
                  <p className="text-slate-200">{((agent.duration_ms ?? 0) / 1000).toFixed(1)}s</p>
                </div>
                <div>
                  <p className="text-xs text-slate-400">Cost</p>
                  <p className="text-slate-200">${agent.cost?.toFixed(4)}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  )
}
