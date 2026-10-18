'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import {
  ArrowLeft, Activity, Clock, DollarSign, Cpu, ArrowRight, Send,
  Brain, ShieldCheck, CheckCircle2, XCircle, Loader2, CircleDashed, User,
} from 'lucide-react'
import Link from 'next/link'
import GlassCard from '@/components/GlassCard'
import StatusBadge from '@/components/StatusBadge'
import Markdown from '@/components/Markdown'
import MissionControl from '@/components/MissionControl'
import { apiFetch, ApiError, DEFAULT_USER_ID } from '@/lib/api'

interface AgentRun {
  agent_id: string
  agent_name: string | null
  status: string
  duration_ms: number | null
  cost: number | null
  tokens_used: number | null
  success: boolean
  error_message: string | null
  task_input?: string | null
  task_output: string | null
}

interface WorkflowDetail {
  workflow_id: string
  status: string
  prompt?: string
  parent_workflow_id?: string | null
  agents_selected?: string[]
  total_cost?: number | null
  total_tokens?: number | null
  execution_time_ms?: number | null
  quality_score?: number | null
  created_at?: string
  completed_at?: string
  error?: string | null
}

interface PendingApproval {
  approval_id: string
  workflow_id: string
  action: string
}

// Each agent stores its result as JSON with different shapes (writer_agent's
// deliverable is `content`, research_agent's is `summary`, analysis_agent's
// is `analysis`) — try the known human-readable fields before falling back
// to the raw JSON.
function extractReadableOutput(taskOutput: string | null): string | null {
  if (!taskOutput) return null
  try {
    const parsed = JSON.parse(taskOutput)
    if (parsed.code) {
      // Coding agent: summary + code + real execution output
      return `${parsed.summary ?? ''}\n\n\`\`\`python\n${parsed.code}\n\`\`\`\n\n**Execution output:**\n\`\`\`\n${parsed.execution_output ?? ''}\n\`\`\``
    }
    return parsed.content ?? parsed.summary ?? parsed.analysis ?? JSON.stringify(parsed, null, 2)
  } catch {
    return taskOutput
  }
}

function finalOutputOf(runs: AgentRun[]): { run: AgentRun; text: string } | null {
  // The deliverable is the last successful WRITER run (revisions replace
  // drafts) — the critic runs after it but its review is not the output.
  const reversed = [...runs].reverse()
  const last =
    reversed.find(a => a.success && a.agent_id === 'writer_agent') ??
    reversed.find(a => a.success && a.agent_id !== 'critic_agent') ??
    reversed.find(a => a.success)
  if (!last) return null
  const text = extractReadableOutput(last.task_output)
  return text ? { run: last, text } : null
}

type NodeState = 'completed' | 'failed' | 'running' | 'pending'

const NODE_STYLES: Record<NodeState, string> = {
  completed: 'border-emerald-500/40 bg-emerald-500/10',
  failed: 'border-red-500/40 bg-red-500/10',
  running: 'border-blue-500/50 bg-blue-500/10 shadow-lg shadow-blue-500/20',
  pending: 'border-white/10 bg-white/5 opacity-60',
}

function NodeIcon({ state }: { state: NodeState }) {
  if (state === 'completed') return <CheckCircle2 className="w-4 h-4 text-emerald-400" />
  if (state === 'failed') return <XCircle className="w-4 h-4 text-red-400" />
  if (state === 'running') return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
  return <CircleDashed className="w-4 h-4 text-slate-500" />
}

function Pipeline({ workflow, runs }: { workflow: WorkflowDetail; runs: AgentRun[] }) {
  const plan = workflow.agents_selected ?? []
  const runByAgent = new Map(runs.map(a => [a.agent_id, a]))
  const nodes = plan.map((agentId): { agentId: string; run: AgentRun | null; state: NodeState } => {
    const run = runByAgent.get(agentId) ?? null
    if (run) return { agentId, run, state: run.success ? 'completed' : 'failed' }
    return { agentId, run: null, state: 'pending' }
  })
  if (workflow.status === 'running') {
    const firstPending = nodes.find(n => n.state === 'pending')
    if (firstPending) firstPending.state = 'running'
  }

  return (
    <div className="flex items-stretch gap-2 overflow-x-auto pb-1">
      <div className="rounded-xl border border-purple-500/40 bg-purple-500/10 p-3 min-w-[130px] shrink-0">
        <div className="flex items-center gap-2 mb-0.5">
          <CheckCircle2 className="w-4 h-4 text-purple-400" />
          <p className="text-sm font-medium text-slate-100">Supervisor</p>
        </div>
        <p className="text-xs text-slate-400">planned {plan.length}-agent DAG</p>
      </div>
      {nodes.map((node) => (
        <div key={node.agentId} className="flex items-center gap-2 shrink-0">
          <ArrowRight className="w-4 h-4 text-slate-600 shrink-0" />
          <div className={`rounded-xl border p-3 min-w-[130px] transition-all ${NODE_STYLES[node.state]}`}>
            <div className="flex items-center gap-2 mb-0.5">
              <NodeIcon state={node.state} />
              <p className="text-sm font-medium text-slate-100 capitalize">
                {node.agentId.replace('_agent', '')}
              </p>
            </div>
            {node.run ? (
              <p className="text-xs text-slate-400">
                {((node.run.duration_ms ?? 0) / 1000).toFixed(1)}s · ${(node.run.cost ?? 0).toFixed(4)}
              </p>
            ) : (
              <p className="text-xs text-slate-500">{node.state === 'running' ? 'executing…' : 'queued'}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function WorkflowThread() {
  const params = useParams()
  const router = useRouter()
  const workflow_id = params.id as string

  const [thread, setThread] = useState<WorkflowDetail[]>([])
  const [runsByWorkflow, setRunsByWorkflow] = useState<Record<string, AgentRun[]>>({})
  const [approval, setApproval] = useState<PendingApproval | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [followUp, setFollowUp] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [deciding, setDeciding] = useState(false)
  const [view, setView] = useState<'thread' | 'room'>('room')
  const bottomRef = useRef<HTMLDivElement>(null)

  const load = useCallback(async () => {
    try {
      setError(null)
      const threadData = await apiFetch<{ thread: WorkflowDetail[] }>(
        `/api/workflows/${workflow_id}/thread`,
      )
      const runs = threadData.thread ?? []
      const agentLists = await Promise.all(
        runs.map(w =>
          apiFetch<{ agents: AgentRun[] }>(`/api/workflows/${w.workflow_id}/agents`)
            .then(r => [w.workflow_id, r.agents] as const)
            .catch(() => [w.workflow_id, []] as const),
        ),
      )
      setThread(runs)
      setRunsByWorkflow(Object.fromEntries(agentLists))

      const waiting = runs.find(w => w.status === 'waiting_approval')
      if (waiting) {
        const pending = await apiFetch<{ requests: PendingApproval[] }>('/api/approvals/')
        setApproval(pending.requests.find(r => r.workflow_id === waiting.workflow_id) ?? null)
      } else {
        setApproval(null)
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the API')
    } finally {
      setLoading(false)
    }
  }, [workflow_id])

  const anyActive = thread.some(w => w.status === 'running' || w.status === 'waiting_approval')

  useEffect(() => {
    load()
    const interval = setInterval(() => {
      if (anyActive || thread.length === 0) load()
    }, 3000)
    return () => clearInterval(interval)
  }, [load, anyActive, thread.length])

  const sendFollowUp = async () => {
    if (!followUp.trim() || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const res = await apiFetch<{ workflow_id: string }>('/api/workflows/', {
        method: 'POST',
        body: JSON.stringify({
          prompt: followUp,
          user_id: DEFAULT_USER_ID,
          parent_workflow_id: workflow_id,
        }),
      })
      setFollowUp('')
      router.push(`/workflows/${res.workflow_id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to continue thread')
    } finally {
      setSubmitting(false)
    }
  }

  const decide = async (approve: boolean) => {
    if (!approval) return
    setDeciding(true)
    try {
      await apiFetch(`/api/approvals/${approval.approval_id}/${approve ? 'approve' : 'reject'}`, {
        method: 'POST',
        body: JSON.stringify(
          approve
            ? { approved_by: DEFAULT_USER_ID }
            : { rejected_by: DEFAULT_USER_ID, reason: 'Rejected from dashboard' }
        ),
      })
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Decision failed')
    } finally {
      setDeciding(false)
    }
  }

  if (loading && thread.length === 0) {
    return (
      <div className="text-center py-16">
        <Activity className="w-8 h-8 animate-spin mx-auto mb-4 text-blue-400" />
        <p className="text-slate-400">Loading...</p>
      </div>
    )
  }

  if (thread.length === 0) {
    return (
      <GlassCard tone="red" className="p-6 text-sm text-red-200">
        {error ? `Couldn't load this workflow: ${error}` : 'Workflow not found'}
      </GlassCard>
    )
  }

  const totalCost = thread.reduce((s, w) => s + (w.total_cost ?? 0), 0)
  const totalTokens = thread.reduce((s, w) => s + (w.total_tokens ?? 0), 0)
  const totalTime = thread.reduce((s, w) => s + (w.execution_time_ms ?? 0), 0)
  const latest = thread[thread.length - 1]

  return (
    <div className="space-y-6 pb-4">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/workflows" className="p-2 rounded-lg hover:bg-white/5 transition-colors shrink-0">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="min-w-0 flex-1">
          <h1 className="text-xl md:text-2xl font-bold text-slate-100 truncate">
            {thread[0].prompt}
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {thread.length} run{thread.length > 1 ? 's' : ''} in this thread
          </p>
        </div>
        <div className="flex items-center gap-4 shrink-0 text-sm text-slate-400">
          <span className="hidden md:flex items-center gap-1.5"><Clock className="w-4 h-4" />{(totalTime / 1000).toFixed(1)}s</span>
          <span className="hidden md:flex items-center gap-1.5"><DollarSign className="w-4 h-4" />${totalCost.toFixed(4)}</span>
          <span className="hidden md:flex items-center gap-1.5"><Cpu className="w-4 h-4" />{totalTokens}</span>
          {latest.quality_score != null && (
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                latest.quality_score >= 70
                  ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300'
                  : 'bg-amber-500/15 border-amber-500/40 text-amber-300'
              }`}
              title="Critic Agent quality score"
            >
              ★ {latest.quality_score.toFixed(0)}/100
            </span>
          )}
          <StatusBadge status={latest.status} />
        </div>
      </div>

      {/* View toggle */}
      <div className="flex items-center gap-1 p-1 rounded-xl bg-white/5 border border-white/10 w-fit">
        <button
          onClick={() => setView('room')}
          className={`px-3.5 py-1.5 rounded-lg text-sm transition-colors ${
            view === 'room'
              ? 'bg-blue-500/25 text-blue-200 border border-blue-500/40'
              : 'text-slate-400 hover:text-slate-200 border border-transparent'
          }`}
        >
          🛰️ Mission Control
        </button>
        <button
          onClick={() => setView('thread')}
          className={`px-3.5 py-1.5 rounded-lg text-sm transition-colors ${
            view === 'thread'
              ? 'bg-blue-500/25 text-blue-200 border border-blue-500/40'
              : 'text-slate-400 hover:text-slate-200 border border-transparent'
          }`}
        >
          💬 Thread
        </button>
      </div>

      {error && <GlassCard tone="red" className="p-4 text-sm text-red-200">{error}</GlassCard>}

      {/* Mission Control: the latest run as a living operations room */}
      {view === 'room' && (
        <MissionControl
          workflowId={latest.workflow_id}
          prompt={latest.prompt ?? ''}
          status={latest.status}
          plan={latest.agents_selected ?? []}
          runs={runsByWorkflow[latest.workflow_id] ?? []}
          approvalReady={approval !== null}
          onDecide={decide}
          deciding={deciding}
        />
      )}

      {/* Thread */}
      {view === 'thread' && (
      <div className="space-y-6">
        {thread.map((run, idx) => {
          const runs = runsByWorkflow[run.workflow_id] ?? []
          const output = finalOutputOf(runs)
          const isLatest = idx === thread.length - 1
          const isActive = run.status === 'running' || run.status === 'waiting_approval'

          return (
            <div key={run.workflow_id} className="space-y-3">
              {/* User prompt bubble */}
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-blue-500/20 border border-blue-500/40 flex items-center justify-center shrink-0 mt-0.5">
                  <User className="w-4 h-4 text-blue-300" />
                </div>
                <div className="rounded-2xl rounded-tl-sm bg-blue-500/10 border border-blue-500/20 px-4 py-2.5 max-w-3xl">
                  <p className="text-sm text-slate-100">{run.prompt}</p>
                </div>
              </div>

              {/* Platform response */}
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-purple-500/20 border border-purple-500/40 flex items-center justify-center shrink-0 mt-0.5">
                  <Brain className="w-4 h-4 text-purple-300" />
                </div>
                <div className="flex-1 min-w-0 space-y-3">
                  {/* Pipeline (always for active/latest, compact chips for older) */}
                  {(isLatest || isActive) ? (
                    <GlassCard tone="slate" className="p-4">
                      <Pipeline workflow={run} runs={runs} />
                      {run.error && <p className="text-sm text-red-300 mt-2">Error: {run.error}</p>}
                    </GlassCard>
                  ) : (
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <span>
                        {(run.agents_selected ?? []).map(a => a.replace('_agent', '')).join(' → ')}
                      </span>
                      <span>·</span>
                      <span>${(run.total_cost ?? 0).toFixed(4)}</span>
                      <span>·</span>
                      <StatusBadge status={run.status} />
                    </div>
                  )}

                  {/* Approval gate */}
                  {run.status === 'waiting_approval' && (
                    <GlassCard tone="amber" className="p-4">
                      <div className="flex items-center gap-2 text-amber-300 mb-2">
                        <ShieldCheck className="w-4 h-4" />
                        <p className="text-sm font-semibold">Waiting for your approval — nothing runs until you say go</p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => decide(true)}
                          disabled={deciding || !approval}
                          className="px-3.5 py-1.5 rounded-lg text-sm text-emerald-200 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 disabled:opacity-50 transition-colors"
                        >
                          {deciding ? 'Submitting…' : 'Approve & run'}
                        </button>
                        <button
                          onClick={() => decide(false)}
                          disabled={deciding || !approval}
                          className="px-3.5 py-1.5 rounded-lg text-sm text-red-200 bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 disabled:opacity-50 transition-colors"
                        >
                          Reject
                        </button>
                      </div>
                    </GlassCard>
                  )}

                  {/* Output */}
                  {output && (
                    <GlassCard tone={isLatest ? 'emerald' : 'slate'} className="p-4 md:p-5">
                      <Markdown>{output.text}</Markdown>
                    </GlassCard>
                  )}
                  {!output && run.status === 'running' && (
                    <div className="flex items-center gap-2 text-sm text-slate-400">
                      <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                      Agents are working…
                    </div>
                  )}
                  {run.status === 'rejected' && (
                    <p className="text-sm text-slate-500 italic">Plan rejected — nothing was executed.</p>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
      )}

      {/* Continue the thread */}
      <div ref={bottomRef} className="sticky bottom-4 pt-2">
        <GlassCard tone="blue" className="p-3">
          <div className="flex items-end gap-3">
            <textarea
              value={followUp}
              onChange={(e) => setFollowUp(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendFollowUp()
                }
              }}
              placeholder={
                anyActive
                  ? 'Wait for the current run to finish…'
                  : 'Continue working on this — refine, extend, ask for changes… (Enter to send)'
              }
              disabled={anyActive || submitting}
              rows={2}
              className="flex-1 resize-none rounded-lg bg-slate-950/60 border border-white/10 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-blue-500/50 disabled:opacity-50"
            />
            <button
              onClick={sendFollowUp}
              disabled={anyActive || submitting || !followUp.trim()}
              className="p-2.5 rounded-lg text-blue-300 bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
              title="Send follow-up"
            >
              {submitting ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
            </button>
          </div>
          <p className="text-[11px] text-slate-500 mt-2 ml-1">
            Follow-ups inherit this thread&apos;s output — the Supervisor plans only the agents needed for your change.
          </p>
        </GlassCard>
      </div>
    </div>
  )
}
