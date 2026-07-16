'use client'

import { useEffect, useState } from 'react'

export default function MetricsPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">Metrics & Analytics</h2>

      <div className="grid grid-cols-4 gap-4">
        <div className="metric-card">
          <p className="text-sm text-slate-400">Total Cost (Today)</p>
          <p className="text-3xl font-bold">$4.10</p>
        </div>
        <div className="metric-card">
          <p className="text-sm text-slate-400">Workflows (Today)</p>
          <p className="text-3xl font-bold">18</p>
        </div>
        <div className="metric-card">
          <p className="text-sm text-slate-400">Success Rate</p>
          <p className="text-3xl font-bold">95%</p>
        </div>
        <div className="metric-card">
          <p className="text-sm text-slate-400">Avg Latency</p>
          <p className="text-3xl font-bold">5.4s</p>
        </div>
      </div>

      <div className="metric-card">
        <h3 className="font-bold">Coming Soon</h3>
        <p className="text-slate-400">Charts and detailed analytics will be displayed here</p>
      </div>
    </div>
  )
}
