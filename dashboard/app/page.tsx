'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Activity, Plus } from 'lucide-react'
import GlassCard from '@/components/GlassCard'
import StatusBadge from '@/components/StatusBadge'

interface Workflow {
  workflow_id: string
  status: string
  created_at: string
  total_cost?: number
  agents?: string[]
}

export default function Dashboard() {
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Backend workflow listing endpoint is not persisted yet (Step 12 MVP),
    // so this shows representative sample data for now.
    const timer = setTimeout(() => {
      setWorkflows([
        {
          workflow_id: 'wf_001',
          status: 'running',
          created_at: new Date().toISOString(),
          total_cost: 0.05,
          agents: ['research_agent', 'writer_agent'],
        },
        {
          workflow_id: 'wf_002',
          status: 'completed',
          created_at: new Date(Date.now() - 3600000).toISOString(),
          total_cost: 0.08,
          agents: ['research_agent', 'analysis_agent', 'writer_agent'],
        },
      ])
      setLoading(false)
    }, 200)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="space-y-8">
      <div className="flex justify-between items-center">
        <div className="space-y-1">
          <h1 className="text-4xl font-bold text-slate-100">Workflows</h1>
          <p className="text-slate-400">{workflows.length} workflows tracked</p>
        </div>
        <button className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm text-blue-300 bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/30 hover:border-blue-500/50 backdrop-blur-sm transition-colors">
          <Plus className="w-4 h-4" />
          New Workflow
        </button>
      </div>

      {loading ? (
        <div className="text-center py-16">
          <Activity className="w-8 h-8 animate-spin mx-auto mb-4 text-blue-400" />
          <p className="text-slate-400">Loading workflows...</p>
        </div>
      ) : workflows.length === 0 ? (
        <GlassCard tone="slate" className="p-12 text-center">
          <p className="text-slate-400">No workflows yet</p>
        </GlassCard>
      ) : (
        <div className="bento-grid">
          {workflows.map((workflow) => (
            <Link key={workflow.workflow_id} href={`/workflows/${workflow.workflow_id}`}>
              <GlassCard tone="slate" hover className="p-5 cursor-pointer h-full">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-mono text-sm text-slate-100">{workflow.workflow_id}</h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {new Date(workflow.created_at).toLocaleString()}
                    </p>
                  </div>
                  <StatusBadge status={workflow.status} />
                </div>

                {workflow.agents && (
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {workflow.agents.map((agent) => (
                      <span key={agent} className="text-xs px-2 py-1 rounded-md bg-white/5 text-slate-300 border border-white/10">
                        {agent.replace('_agent', '')}
                      </span>
                    ))}
                  </div>
                )}

                {workflow.total_cost !== undefined && (
                  <p className="text-sm font-mono text-slate-300">${workflow.total_cost.toFixed(4)}</p>
                )}
              </GlassCard>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
