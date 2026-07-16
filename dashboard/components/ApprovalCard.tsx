'use client'

import { CheckCircle, XCircle, AlertCircle, AlertTriangle, Clock } from 'lucide-react'
import { useState } from 'react'
import GlassCard, { GlassTone } from './GlassCard'

interface ApprovalCardProps {
  request_id: string
  agent_id: string
  agent_name: string
  action: string
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  description: string
  details?: string[]
  approval_window_minutes?: number
  onApprove?: (request_id: string) => void
  onReject?: (request_id: string) => void
}

const RISK_TONE: Record<string, GlassTone> = {
  CRITICAL: 'red',
  HIGH: 'orange',
  MEDIUM: 'amber',
  LOW: 'emerald',
}

const RISK_ICON: Record<string, JSX.Element> = {
  CRITICAL: <AlertTriangle className="w-5 h-5 text-red-400" />,
  HIGH: <AlertCircle className="w-5 h-5 text-orange-400" />,
  MEDIUM: <Clock className="w-5 h-5 text-amber-400" />,
  LOW: <CheckCircle className="w-5 h-5 text-emerald-400" />,
}

const RISK_BADGE: Record<string, string> = {
  CRITICAL: 'bg-red-500/20 text-red-300',
  HIGH: 'bg-orange-500/20 text-orange-300',
  MEDIUM: 'bg-amber-500/20 text-amber-300',
  LOW: 'bg-emerald-500/20 text-emerald-300',
}

export default function ApprovalCard({
  request_id,
  agent_id,
  agent_name,
  action,
  risk_level,
  description,
  details,
  approval_window_minutes = 30,
  onApprove,
  onReject,
}: ApprovalCardProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [decided, setDecided] = useState<'approved' | 'rejected' | null>(null)

  const tone = RISK_TONE[risk_level] ?? 'blue'

  const handleApprove = async () => {
    setIsLoading(true)
    try {
      onApprove?.(request_id)
      setDecided('approved')
      setTimeout(() => setDecided(null), 2000)
    } finally {
      setIsLoading(false)
    }
  }

  const handleReject = async () => {
    setIsLoading(true)
    try {
      onReject?.(request_id)
      setDecided('rejected')
      setTimeout(() => setDecided(null), 2000)
    } finally {
      setIsLoading(false)
    }
  }

  if (decided === 'approved') {
    return (
      <GlassCard tone="emerald" className="p-6 flex items-center justify-center min-h-[280px]">
        <div className="text-center">
          <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3 animate-bounce" />
          <p className="text-emerald-300 font-medium">Approved</p>
        </div>
      </GlassCard>
    )
  }

  if (decided === 'rejected') {
    return (
      <GlassCard tone="red" className="p-6 flex items-center justify-center min-h-[280px]">
        <div className="text-center">
          <XCircle className="w-12 h-12 text-red-400 mx-auto mb-3 animate-bounce" />
          <p className="text-red-300 font-medium">Rejected</p>
        </div>
      </GlassCard>
    )
  }

  return (
    <GlassCard tone={tone} hover className="p-6 group">
      <div className="space-y-4">
        {/* Header: Agent info + Risk badge */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3 flex-1">
            <div className="w-10 h-10 rounded-lg bg-white/10 backdrop-blur flex items-center justify-center">
              {RISK_ICON[risk_level] ?? <AlertCircle className="w-5 h-5 text-blue-400" />}
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-100">
                🤖 {agent_name}
              </h3>
              <p className="text-xs text-slate-400">{agent_id}</p>
            </div>
          </div>
          <span className={`px-3 py-1 rounded-full text-xs font-medium backdrop-blur-sm ${RISK_BADGE[risk_level] ?? 'bg-blue-500/20 text-blue-300'}`}>
            {risk_level}
          </span>
        </div>

        {/* Action description */}
        <div className="space-y-2">
          <p className="text-sm font-medium text-slate-200">
            Needs approval: <span className="text-blue-300">{action}</span>
          </p>
          <p className="text-sm text-slate-400 leading-relaxed">
            {description}
          </p>
        </div>

        {/* Details list */}
        {details && details.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-white/10">
            {details.map((detail, idx) => (
              <div key={idx} className="flex items-center gap-2 text-xs text-slate-300">
                <span className="w-1 h-1 rounded-full bg-blue-400" />
                {detail}
              </div>
            ))}
          </div>
        )}

        {/* Approval window timer */}
        <div className="flex items-center gap-2 text-xs text-slate-400 pt-2">
          <Clock className="w-4 h-4" />
          <span>Approve within {approval_window_minutes} minutes</span>
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-4">
          <button
            onClick={handleReject}
            disabled={isLoading}
            className="flex-1 py-2.5 rounded-lg font-medium text-sm transition-all duration-200 bg-red-500/20 hover:bg-red-500/30 text-red-300 hover:text-red-200 border border-red-500/30 hover:border-red-500/50 disabled:opacity-50 disabled:cursor-not-allowed backdrop-blur-sm"
          >
            {isLoading ? 'Processing...' : 'Reject'}
          </button>
          <button
            onClick={handleApprove}
            disabled={isLoading}
            className="flex-1 py-2.5 rounded-lg font-medium text-sm transition-all duration-200 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 hover:text-emerald-200 border border-emerald-500/30 hover:border-emerald-500/50 disabled:opacity-50 disabled:cursor-not-allowed backdrop-blur-sm"
          >
            {isLoading ? 'Processing...' : 'Approve'}
          </button>
        </div>
      </div>
    </GlassCard>
  )
}
