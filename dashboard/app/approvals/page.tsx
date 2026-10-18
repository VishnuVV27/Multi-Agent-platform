'use client'

import { useEffect, useState, useCallback } from 'react'
import ApprovalCard from '@/components/ApprovalCard'
import GlassCard from '@/components/GlassCard'
import { AlertCircle, CheckCircle, Activity } from 'lucide-react'
import { apiFetch, ApiError, DEFAULT_USER_ID } from '@/lib/api'

type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

interface ApprovalRequest {
  request_id: string
  agent_id: string
  agent_name: string
  action: string
  risk_level: RiskLevel
  description: string
  details?: string[]
  approval_window_minutes?: number
  created_at: string
}

interface RawApproval {
  id: string
  workflow_id: string
  agent_id: string
  action: string
  description: string | null
  risk_level: string
  context: Record<string, unknown> | null
  created_at: string
  expires_at: string | null
}

interface ApprovalListResponse {
  total: number
  pending: number
  approved: number
  rejected: number
  requests: RawApproval[]
}

function toApprovalRequest(raw: RawApproval): ApprovalRequest {
  const created = new Date(raw.created_at)
  const expires = raw.expires_at ? new Date(raw.expires_at) : null
  const windowMinutes = expires ? Math.max(1, Math.round((expires.getTime() - created.getTime()) / 60000)) : undefined

  return {
    request_id: raw.id,
    agent_id: raw.agent_id,
    agent_name: raw.agent_id.split('_').map(w => w[0].toUpperCase() + w.slice(1)).join(' '),
    action: raw.action.split('_').map(w => w[0].toUpperCase() + w.slice(1)).join(' '),
    risk_level: raw.risk_level.toUpperCase() as RiskLevel,
    description: raw.description ?? 'No additional description provided.',
    details: raw.context ? Object.entries(raw.context).map(([k, v]) => `${k}: ${v}`) : undefined,
    approval_window_minutes: windowMinutes,
    created_at: raw.created_at,
  }
}

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([])
  const [completedCount, setCompletedCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setError(null)
      const data = await apiFetch<ApprovalListResponse>('/api/approvals/')
      setApprovals(data.requests.map(toApprovalRequest))
      setCompletedCount(data.approved + data.rejected)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the API')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleApprove = async (request_id: string) => {
    setApprovals(prev => prev.filter(a => a.request_id !== request_id))
    setCompletedCount(c => c + 1)
    try {
      await apiFetch(`/api/approvals/${request_id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ approval_id: request_id, approved_by: DEFAULT_USER_ID }),
      })
    } catch {
      load() // resync with server if the call failed
    }
  }

  const handleReject = async (request_id: string) => {
    setApprovals(prev => prev.filter(a => a.request_id !== request_id))
    setCompletedCount(c => c + 1)
    try {
      await apiFetch(`/api/approvals/${request_id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ approval_id: request_id, rejected_by: DEFAULT_USER_ID, reason: 'Rejected via dashboard' }),
      })
    } catch {
      load()
    }
  }

  const criticalCount = approvals.filter(a => a.risk_level === 'CRITICAL').length

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-4xl font-bold text-slate-100">Approvals Required</h1>
        <p className="text-slate-400">
          {approvals.length} pending • {completedCount} completed
        </p>
      </div>

      {error && (
        <GlassCard tone="red" className="p-4 text-sm text-red-200">
          Couldn't load approvals from the API: {error}
        </GlassCard>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <GlassCard tone="red" className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-red-300 font-medium">Critical</p>
              <p className="text-2xl font-bold text-red-200">{criticalCount}</p>
            </div>
            <AlertCircle className="w-8 h-8 text-red-400" />
          </div>
        </GlassCard>

        <GlassCard tone="blue" className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-blue-300 font-medium">Pending</p>
              <p className="text-2xl font-bold text-blue-200">{approvals.length}</p>
            </div>
            <AlertCircle className="w-8 h-8 text-blue-400" />
          </div>
        </GlassCard>

        <GlassCard tone="emerald" className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-emerald-300 font-medium">Completed</p>
              <p className="text-2xl font-bold text-emerald-200">{completedCount}</p>
            </div>
            <CheckCircle className="w-8 h-8 text-emerald-400" />
          </div>
        </GlassCard>
      </div>

      {/* Bento Grid of Approval Cards */}
      {loading ? (
        <div className="text-center py-16">
          <Activity className="w-8 h-8 animate-spin mx-auto mb-4 text-blue-400" />
          <p className="text-slate-400">Loading approvals...</p>
        </div>
      ) : approvals.length > 0 ? (
        <div className="bento-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))' }}>
          {approvals.map((approval) => (
            <ApprovalCard
              key={approval.request_id}
              {...approval}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))}
        </div>
      ) : (
        <GlassCard tone="slate" className="p-12 text-center">
          <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
          <p className="text-slate-300 font-medium">All approvals complete</p>
          <p className="text-slate-400 text-sm mt-1">No pending requests</p>
        </GlassCard>
      )}
    </div>
  )
}
