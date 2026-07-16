'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Activity, Check, X, Clock } from 'lucide-react'

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
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchWorkflows = async () => {
      try {
        setLoading(true)
        // Fetch from backend
        const response = await fetch('http://localhost:8000/api/workflows')
        if (!response.ok) throw new Error('Failed to fetch workflows')
        
        // For now, show mock data
        setWorkflows([
          {
            workflow_id: 'wf_001',
            status: 'running',
            created_at: new Date().toISOString(),
            total_cost: 0.05,
            agents: ['research_agent', 'writer_agent']
          },
          {
            workflow_id: 'wf_002',
            status: 'completed',
            created_at: new Date(Date.now() - 3600000).toISOString(),
            total_cost: 0.08,
            agents: ['research_agent', 'analysis_agent', 'writer_agent']
          },
        ])
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }

    fetchWorkflows()
  }, [])

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <Activity className="w-4 h-4 text-blue-400 animate-spin" />
      case 'completed':
        return <Check className="w-4 h-4 text-green-400" />
      case 'failed':
        return <X className="w-4 h-4 text-red-400" />
      default:
        return <Clock className="w-4 h-4 text-yellow-400" />
    }
  }

  const getStatusClass = (status: string) => {
    return `status-badge status-${status}`
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold">Workflows</h2>
        <button className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg">
          New Workflow
        </button>
      </div>

      {error && (
        <div className="bg-red-500/20 border border-red-500 text-red-300 p-4 rounded-lg">
          Error: {error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-12">
          <Activity className="w-8 h-8 animate-spin mx-auto mb-4" />
          <p>Loading workflows...</p>
        </div>
      ) : workflows.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-slate-400">No workflows yet</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {workflows.map((workflow) => (
            <Link key={workflow.workflow_id} href={`/workflows/${workflow.workflow_id}`}>
              <div className="workflow-card cursor-pointer">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4 flex-1">
                    {getStatusIcon(workflow.status)}
                    <div>
                      <h3 className="font-mono text-sm">{workflow.workflow_id}</h3>
                      <p className="text-xs text-slate-400">
                        {new Date(workflow.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    {workflow.agents && (
                      <div className="flex gap-2">
                        {workflow.agents.map((agent) => (
                          <span key={agent} className="text-xs bg-slate-700 px-2 py-1 rounded">
                            {agent.replace('_agent', '')}
                          </span>
                        ))}
                      </div>
                    )}

                    {workflow.total_cost !== undefined && (
                      <div className="text-right">
                        <p className="text-sm font-mono">${workflow.total_cost.toFixed(4)}</p>
                      </div>
                    )}

                    <div className={getStatusClass(workflow.status)}>
                      {workflow.status}
                    </div>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
