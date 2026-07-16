'use client'

import { useEffect, useState } from 'react'
import ApprovalCard from '@/components/ApprovalCard'
import { AlertCircle, CheckCircle } from 'lucide-react'

interface ApprovalRequest {
  request_id: string
  agent_id: string
  agent_name: string
  action: string
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  description: string
  details?: string[]
  approval_window_minutes?: number
  created_at: string
}

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([])
  const [completed, setCompleted] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(false)
    // Mock data - in production, fetch from API with WebSocket
    setApprovals([
      {
        request_id: 'apr_001',
        agent_id: 'coding_agent',
        agent_name: 'Coding Agent',
        action: 'Deploy to Production',
        risk_level: 'CRITICAL',
        description: 'Deploy version 2.1.0 to production environment with 5 breaking API changes',
        details: [
          'New payment processing integration',
          'Database schema migration',
          'Customer notification emails',
          'Requires database backup'
        ],
        approval_window_minutes: 120,
        created_at: new Date().toISOString(),
      },
      {
        request_id: 'apr_002',
        agent_id: 'sql_agent',
        agent_name: 'SQL Agent',
        action: 'Execute Production Query',
        risk_level: 'HIGH',
        description: 'Run customer data migration affecting 10,000+ records in production',
        details: [
          'Update customer_status table',
          'Backfill user_preferences',
          'Cascade delete old records'
        ],
        approval_window_minutes: 60,
        created_at: new Date(Date.now() - 180000).toISOString(),
      },
      {
        request_id: 'apr_003',
        agent_id: 'email_agent',
        agent_name: 'Email Agent',
        action: 'Send Customer Email Campaign',
        risk_level: 'MEDIUM',
        description: 'Send promotional email to 50,000 users',
        details: [
          'Recipient: Active users (segment: pro_tier)',
          'Subject: Q3 Product Updates',
          'Unsubscribe link: included'
        ],
        approval_window_minutes: 30,
        created_at: new Date(Date.now() - 600000).toISOString(),
      },
      {
        request_id: 'apr_004',
        agent_id: 'research_agent',
        agent_name: 'Research Agent',
        action: 'Access Private Documents',
        risk_level: 'MEDIUM',
        description: 'Access confidential client files for competitive analysis',
        details: [
          'Files: Q3_financial_report.pdf',
          'Reason: Market research for pricing strategy',
          'Duration: 24 hours'
        ],
        approval_window_minutes: 30,
        created_at: new Date(Date.now() - 120000).toISOString(),
      },
      {
        request_id: 'apr_005',
        agent_id: 'analytics_agent',
        agent_name: 'Analytics Agent',
        action: 'Export User Data',
        risk_level: 'LOW',
        description: 'Export anonymized user analytics for reporting',
        details: [
          'Data: Aggregated metrics only',
          'Format: CSV',
          'Retention: 30 days'
        ],
        approval_window_minutes: 15,
        created_at: new Date(Date.now() - 30000).toISOString(),
      },
    ])
  }, [])

  const handleApprove = (request_id: string) => {
    setCompleted([...completed, request_id])
    setApprovals(approvals.filter(a => a.request_id !== request_id))
  }

  const handleReject = (request_id: string) => {
    setCompleted([...completed, request_id])
    setApprovals(approvals.filter(a => a.request_id !== request_id))
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950/10 to-slate-950">
      {/* Animated background */}
      <div className="fixed inset-0 -z-10">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full filter blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-emerald-500/10 rounded-full filter blur-3xl" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-4 py-8 space-y-8">
        {/* Header */}
        <div className="space-y-2">
          <h1 className="text-4xl font-bold text-slate-100">
            Approvals Required
          </h1>
          <p className="text-slate-400">
            {approvals.length} pending • {completed.length} completed today
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-2xl backdrop-blur-xl bg-gradient-to-br from-red-500/20 to-red-600/10 border border-red-500/30 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-red-300 font-medium">Critical</p>
                <p className="text-2xl font-bold text-red-200">
                  {approvals.filter(a => a.risk_level === 'CRITICAL').length}
                </p>
              </div>
              <AlertCircle className="w-8 h-8 text-red-400" />
            </div>
          </div>

          <div className="rounded-2xl backdrop-blur-xl bg-gradient-to-br from-blue-500/20 to-blue-600/10 border border-blue-500/30 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-blue-300 font-medium">Pending</p>
                <p className="text-2xl font-bold text-blue-200">{approvals.length}</p>
              </div>
              <AlertCircle className="w-8 h-8 text-blue-400" />
            </div>
          </div>

          <div className="rounded-2xl backdrop-blur-xl bg-gradient-to-br from-emerald-500/20 to-emerald-600/10 border border-emerald-500/30 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-emerald-300 font-medium">Completed</p>
                <p className="text-2xl font-bold text-emerald-200">{completed.length}</p>
              </div>
              <CheckCircle className="w-8 h-8 text-emerald-400" />
            </div>
          </div>
        </div>

        {/* Bento Grid of Approval Cards */}
        {approvals.length > 0 ? (
          <div className="grid gap-4 auto-rows-min" style={{
            gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))',
            gridAutoRows: 'auto'
          }}>
            {approvals.map((approval) => (
              <div 
                key={approval.request_id}
                style={{
                  gridColumn: approval.risk_level === 'CRITICAL' ? 'span 1' : 'span 1',
                  gridRow: approval.risk_level === 'CRITICAL' ? 'span 1' : 'span 1'
                }}
              >
                <ApprovalCard
                  {...approval}
                  onApprove={handleApprove}
                  onReject={handleReject}
                />
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl backdrop-blur-xl bg-gradient-to-br from-slate-700/20 to-slate-800/10 border border-slate-600/30 p-12 text-center">
            <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
            <p className="text-slate-300 font-medium">All approvals complete</p>
            <p className="text-slate-400 text-sm mt-1">No pending requests</p>
          </div>
        )}
      </div>
    </div>
  )
}
