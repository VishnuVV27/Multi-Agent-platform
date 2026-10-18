'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { Activity, Plus, X, ShieldCheck, Gauge, Sparkles } from 'lucide-react'
import GlassCard from '@/components/GlassCard'
import StatusBadge from '@/components/StatusBadge'
import SkillSelect from '@/components/SkillSelect'
import { apiFetch, ApiError, DEFAULT_USER_ID } from '@/lib/api'

interface Workflow {
  workflow_id: string
  status: string
  created_at: string
  prompt?: string | null
  total_cost?: number | null
  quality_score?: number | null
  agents_selected?: string[]
}

interface WorkflowListResponse {
  workflows: Workflow[]
  count: number
}

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [prompt, setPrompt] = useState('')
  const [requireApproval, setRequireApproval] = useState(false)
  const [limiterOn, setLimiterOn] = useState(false)
  const [maxTokens, setMaxTokens] = useState(500)
  const [skills, setSkills] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    try {
      setError(null)
      const data = await apiFetch<WorkflowListResponse>('/api/workflows/')
      setWorkflows(data.workflows)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the API')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    // Live-refresh the list while workflows are running
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [load])

  const handleCreate = async () => {
    if (!prompt.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      await apiFetch('/api/workflows/', {
        method: 'POST',
        body: JSON.stringify({
          prompt,
          user_id: DEFAULT_USER_ID,
          require_approval: requireApproval,
          output_token_limit: limiterOn ? maxTokens : null,
          enabled_skills: skills.length > 0 ? skills : null,
        }),
      })
      setPrompt('')
      setSkills([])
      setShowForm(false)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create workflow')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex justify-between items-center">
        <div className="space-y-1">
          <h1 className="text-4xl font-bold text-slate-100">Workflows</h1>
          <p className="text-slate-400">
            Each workflow is planned by the Supervisor agent and orchestrated by Temporal
          </p>
        </div>
        <button
          onClick={() => setShowForm(v => !v)}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm text-blue-300 bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/30 hover:border-blue-500/50 backdrop-blur-sm transition-colors"
        >
          {showForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          {showForm ? 'Cancel' : 'New Workflow'}
        </button>
      </div>

      {/* z-10 on the form card: it and the workflow cards below each create
          stacking contexts (backdrop-blur), and later DOM siblings paint on
          top — without this the skills dropdown falls behind the cards grid.
          Kept below the nav's z-20. */}
      {showForm && (
        <GlassCard tone="blue" clip={false} className="p-5 space-y-4 z-10">
          <label className="text-xs font-medium text-blue-300 uppercase tracking-wide">
            What do you want the agents to do?
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g. Research the current state of open-source LLMs and write a comparison report"
            rows={3}
            className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-blue-500/50"
          />
          {/* Skills */}
          <div className="space-y-1.5">
            <label className="flex items-center gap-1.5 text-xs font-medium text-blue-300 uppercase tracking-wide">
              <Sparkles className="w-3.5 h-3.5" />
              Skills
            </label>
            <SkillSelect selected={skills} onChange={setSkills} />
          </div>

          <div className="flex flex-col md:flex-row md:items-center gap-3 md:gap-8">
            <label className="flex items-center gap-2.5 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={requireApproval}
                onChange={(e) => setRequireApproval(e.target.checked)}
                className="w-4 h-4 rounded accent-emerald-500"
              />
              <span className="flex items-center gap-1.5 text-sm text-slate-300">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                Require plan approval
              </span>
            </label>

            {/* Output token limiter */}
            <label className="flex items-center gap-2.5 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={limiterOn}
                onChange={(e) => setLimiterOn(e.target.checked)}
                className="w-4 h-4 rounded accent-amber-500"
              />
              <span className="flex items-center gap-1.5 text-sm text-slate-300">
                <Gauge className="w-4 h-4 text-amber-400" />
                Limit output tokens
              </span>
            </label>
            {limiterOn && (
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(Number(e.target.value))}
                  min={100}
                  max={4000}
                  step={100}
                  className="w-24 rounded-lg bg-white/5 border border-amber-500/40 px-2.5 py-1.5 text-sm text-slate-100 focus:outline-none focus:border-amber-400"
                />
                <span className="text-xs text-slate-500">max tokens per LLM call (100–4000)</span>
              </div>
            )}
          </div>
          <button
            onClick={handleCreate}
            disabled={submitting || !prompt.trim()}
            className="px-4 py-2 rounded-lg font-medium text-sm text-blue-300 bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? 'Planning…' : 'Start Workflow'}
          </button>
        </GlassCard>
      )}

      {error && (
        <GlassCard tone="red" className="p-4 text-sm text-red-200">
          {error}
        </GlassCard>
      )}

      {loading ? (
        <div className="text-center py-16">
          <Activity className="w-8 h-8 animate-spin mx-auto mb-4 text-blue-400" />
          <p className="text-slate-400">Loading workflows...</p>
        </div>
      ) : workflows.length === 0 ? (
        <GlassCard tone="slate" className="p-12 text-center">
          <p className="text-slate-400">No workflows yet — start one above</p>
        </GlassCard>
      ) : (
        <div className="bento-grid">
          {workflows.map((workflow) => (
            <Link key={workflow.workflow_id} href={`/workflows/${workflow.workflow_id}`}>
              <GlassCard tone="slate" hover className="p-5 cursor-pointer h-full">
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="min-w-0">
                    <p className="text-sm text-slate-100 line-clamp-2">
                      {workflow.prompt || workflow.workflow_id}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                      {new Date(workflow.created_at).toLocaleString()}
                    </p>
                  </div>
                  <StatusBadge status={workflow.status} />
                </div>

                {workflow.agents_selected && workflow.agents_selected.length > 0 && (
                  <div className="flex items-center flex-wrap gap-1.5 mb-3">
                    {workflow.agents_selected.map((agent, i) => (
                      <span key={agent} className="flex items-center gap-1.5">
                        {i > 0 && <span className="text-slate-600 text-xs">→</span>}
                        <span className="text-xs px-2 py-1 rounded-md bg-white/5 text-slate-300 border border-white/10">
                          {agent.replace('_agent', '')}
                        </span>
                      </span>
                    ))}
                  </div>
                )}

                <div className="flex items-center gap-3">
                  {workflow.total_cost != null && (
                    <p className="text-sm font-mono text-slate-400">${workflow.total_cost.toFixed(4)}</p>
                  )}
                  {workflow.quality_score != null && (
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full border ${
                        workflow.quality_score >= 70
                          ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300'
                          : 'bg-amber-500/15 border-amber-500/40 text-amber-300'
                      }`}
                      title="Critic Agent quality score"
                    >
                      ★ {workflow.quality_score.toFixed(0)}
                    </span>
                  )}
                </div>
              </GlassCard>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
