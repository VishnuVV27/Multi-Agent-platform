'use client'

import { CheckCircle, XCircle, AlertCircle, AlertTriangle, Clock } from 'lucide-react'
import { useState } from 'react'

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

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'CRITICAL':
        return 'from-red-500/20 to-red-600/10 border-red-500/30'
      case 'HIGH':
        return 'from-orange-500/20 to-orange-600/10 border-orange-500/30'
      case 'MEDIUM':
        return 'from-amber-500/20 to-amber-600/10 border-amber-500/30'
      case 'LOW':
        return 'from-emerald-500/20 to-emerald-600/10 border-emerald-500/30'
      default:
        return 'from-blue-500/20 to-blue-600/10 border-blue-500/30'
    }
  }

  const getRiskIcon = (level: string) => {
    switch (level) {
      case 'CRITICAL':
        return <AlertTriangle className="w-5 h-5 text-red-400" />
      case 'HIGH':
        return <AlertCircle className="w-5 h-5 text-orange-400" />
      case 'MEDIUM':
        return <Clock className="w-5 h-5 text-amber-400" />
      case 'LOW':
        return <CheckCircle className="w-5 h-5 text-emerald-400" />
      default:
        return <AlertCircle className="w-5 h-5 text-blue-400" />
    }
  }

  const getRiskBadgeColor = (level: string) => {
    switch (level) {
      case 'CRITICAL':
        return 'bg-red-500/20 text-red-300'
      case 'HIGH':
        return 'bg-orange-500/20 text-orange-300'
      case 'MEDIUM':
        return 'bg-amber-500/20 text-amber-300'
      case 'LOW':
        return 'bg-emerald-500/20 text-emerald-300'
      default:
        return 'bg-blue-500/20 text-blue-300'
    }
  }

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
      <div className={`
        relative overflow-hidden rounded-2xl backdrop-blur-xl
        bg-gradient-to-br from-emerald-500/20 to-emerald-600/10
        border border-emerald-500/30 p-6
        flex items-center justify-center min-h-[280px]
      `}>
        <div className="text-center">
          <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3 animate-bounce" />
          <p className="text-emerald-300 font-medium">Approved</p>
        </div>
      </div>
    )
  }

  if (decided === 'rejected') {
    return (
      <div className={`
        relative overflow-hidden rounded-2xl backdrop-blur-xl
        bg-gradient-to-br from-red-500/20 to-red-600/10
        border border-red-500/30 p-6
        flex items-center justify-center min-h-[280px]
      `}>
        <div className="text-center">
          <XCircle className="w-12 h-12 text-red-400 mx-auto mb-3 animate-bounce" />
          <p className="text-red-300 font-medium">Rejected</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`
      relative overflow-hidden rounded-2xl backdrop-blur-xl
      bg-gradient-to-br ${getRiskColor(risk_level)}
      border p-6 transition-all duration-300 hover:shadow-lg
      hover:shadow-white/5 group
    `}>
      {/* Glass effect overlay */}
      <div className="absolute inset-0 bg-white/[0.01] pointer-events-none" />

      <div className="relative z-10 space-y-4">
        {/* Header: Agent info + Risk badge */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3 flex-1">
            <div className="w-10 h-10 rounded-lg bg-white/10 backdrop-blur flex items-center justify-center">
              {getRiskIcon(risk_level)}
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-100">
                🤖 {agent_name}
              </h3>
              <p className="text-xs text-slate-400">{agent_id}</p>
            </div>
          </div>
          <span className={`
            px-3 py-1 rounded-full text-xs font-medium
            ${getRiskBadgeColor(risk_level)}
            backdrop-blur-sm
          `}>
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
            className={`
              flex-1 py-2.5 rounded-lg font-medium text-sm
              transition-all duration-200
              bg-red-500/20 hover:bg-red-500/30 text-red-300 hover:text-red-200
              border border-red-500/30 hover:border-red-500/50
              disabled:opacity-50 disabled:cursor-not-allowed
              backdrop-blur-sm
            `}
          >
            {isLoading ? 'Processing...' : 'Reject'}
          </button>
          <button
            onClick={handleApprove}
            disabled={isLoading}
            className={`
              flex-1 py-2.5 rounded-lg font-medium text-sm
              transition-all duration-200
              bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 hover:text-emerald-200
              border border-emerald-500/30 hover:border-emerald-500/50
              disabled:opacity-50 disabled:cursor-not-allowed
              backdrop-blur-sm
            `}
          >
            {isLoading ? 'Processing...' : 'Approve'}
          </button>
        </div>
      </div>
    </div>
  )
}
