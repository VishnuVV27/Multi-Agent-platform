'use client'

import { useEffect, useState } from 'react'
import { CheckCircle2, XCircle, Loader2, ShieldCheck } from 'lucide-react'
import { apiFetch } from '@/lib/api'

interface Workflow {
  workflow_id: string
  status: string
  prompt?: string | null
  total_cost?: number | null
  agents_selected?: string[]
  created_at?: string
}

function timeAgo(iso?: string): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function StatusDot({ status }: { status: string }) {
  if (status === 'completed') return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
  if (status === 'running') return <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin shrink-0" />
  if (status === 'waiting_approval') return <ShieldCheck className="w-3.5 h-3.5 text-amber-400 shrink-0" />
  return <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
}

/**
 * Infinite marquee of real recent workflow activity. The list is rendered
 * twice so the -50% translate loops seamlessly. Pauses on hover.
 */
export default function ActivityTicker() {
  const [workflows, setWorkflows] = useState<Workflow[]>([])

  useEffect(() => {
    apiFetch<{ workflows: Workflow[] }>('/api/workflows/?limit=12')
      .then(d => setWorkflows(d.workflows.filter(w => w.prompt)))
      .catch(() => {})
  }, [])

  if (workflows.length === 0) return null

  const items = workflows.map(w => (
    <a
      key={w.workflow_id}
      href={`/workflows/${w.workflow_id}`}
      className="inline-flex items-center gap-2 px-4 py-1.5 mx-2 rounded-full bg-white/[0.04] border border-white/10 hover:bg-white/[0.08] hover:border-white/20 transition-colors shrink-0"
    >
      <StatusDot status={w.status} />
      <span className="text-xs text-slate-300 max-w-[280px] truncate">{w.prompt}</span>
      <span className="text-xs text-slate-600">·</span>
      <span className="text-xs text-slate-500 font-mono">
        {(w.agents_selected ?? []).length} agent{(w.agents_selected ?? []).length === 1 ? '' : 's'}
      </span>
      {w.total_cost != null && (
        <>
          <span className="text-xs text-slate-600">·</span>
          <span className="text-xs text-slate-500 font-mono">${w.total_cost.toFixed(4)}</span>
        </>
      )}
      <span className="text-xs text-slate-600">·</span>
      <span className="text-xs text-slate-500">{timeAgo(w.created_at)}</span>
    </a>
  ))

  return (
    <div className="relative overflow-hidden py-1">
      {/* Edge fades */}
      <div className="absolute inset-y-0 left-0 w-24 z-10 bg-gradient-to-r from-slate-950 to-transparent pointer-events-none" />
      <div className="absolute inset-y-0 right-0 w-24 z-10 bg-gradient-to-l from-slate-950 to-transparent pointer-events-none" />
      <div className="flex w-max animate-marquee">
        <div className="flex items-center">{items}</div>
        <div className="flex items-center" aria-hidden="true">{items}</div>
      </div>
    </div>
  )
}
