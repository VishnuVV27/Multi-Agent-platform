'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { ArrowLeft, Activity } from 'lucide-react'
import Link from 'next/link'

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
    const fetchWorkflow = async () => {
      try {
        setWorkflow({
          workflow_id,
          user_request: 'Research AI trends and write report',
          status: 'completed',
          agents: [
            {
              id: 'research_agent',
              name: 'Research Agent',
              status: 'completed',
              duration_ms: 8000,
              cost: 0.08,
              tokens: 3200
            },
            {
              id: 'writer_agent',
              name: 'Writer Agent',
              status: 'completed',
              duration_ms: 4500,
              cost: 0.04,
              tokens: 1800
            }
          ],
          total_duration_ms: 12500,
          total_cost: 0.12,
          total_tokens: 5000,
          created_at: new Date().toISOString(),
          completed_at: new Date().toISOString()
        })
      } finally {
        setLoading(false)
      }
    }

    fetchWorkflow()
  }, [workflow_id])

  if (loading) {
    return (
      <div className="text-center py-12">
        <Activity className="w-8 h-8 animate-spin mx-auto mb-4" />
        <p>Loading...</p>
      </div>
    )
  }

  if (!workflow) return <div>Workflow not found</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/"><ArrowLeft className="w-5 h-5" /></Link>
        <h2 className="text-3xl font-bold">{workflow.workflow_id}</h2>
      </div>

      <div className="metric-card">
        <h3 className="font-bold mb-2">Request</h3>
        <p className="text-slate-300">{workflow.user_request}</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <div className="metric-card">
          <p className="text-sm text-slate-400">Status</p>
          <p className="text-2xl font-bold">{workflow.status}</p>
        </div>
        <div className="metric-card">
          <p className="text-sm text-slate-400">Duration</p>
          <p className="text-2xl font-bold">{((workflow.total_duration_ms ?? 0) / 1000).toFixed(1)}s</p>
        </div>
        <div className="metric-card">
          <p className="text-sm text-slate-400">Cost</p>
          <p className="text-2xl font-bold">${workflow.total_cost?.toFixed(4) ?? '0.0000'}</p>
        </div>
        <div className="metric-card">
          <p className="text-sm text-slate-400">Tokens</p>
          <p className="text-2xl font-bold">{workflow.total_tokens ?? 0}</p>
        </div>
      </div>

      <div className="metric-card">
        <h3 className="font-bold mb-4">Agent Timeline</h3>
        <div className="space-y-4">
          {workflow.agents.map((agent) => (
            <div key={agent.id} className="flex items-center gap-4 pb-4 border-b border-slate-700">
              <div className="w-32">
                <p className="font-mono text-sm">{agent.name}</p>
              </div>
              <div className="flex-1">
                <div className="w-full bg-slate-700 rounded-full h-2">
                  <div className="h-2 rounded-full bg-green-500" style={{ width: '100%' }} />
                </div>
              </div>
              <div className="flex gap-4 text-right text-sm">
                <div>
                  <p className="text-slate-400">Duration</p>
                  <p>{(agent.duration_ms ?? 0 / 1000).toFixed(1)}s</p>
                </div>
                <div>
                  <p className="text-slate-400">Cost</p>
                  <p>${agent.cost?.toFixed(4)}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
