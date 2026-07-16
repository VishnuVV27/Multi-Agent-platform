'use client'

export default function RateLimitingPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">Budget & Rate Limiting</h2>

      <div className="grid grid-cols-3 gap-4">
        <div className="metric-card">
          <p className="text-sm text-slate-400">Monthly Budget</p>
          <p className="text-3xl font-bold">$10.00</p>
          <div className="mt-2">
            <div className="bg-slate-700 rounded-full h-2">
              <div className="bg-blue-500 h-2 rounded-full" style={{ width: '45%' }} />
            </div>
            <p className="text-xs text-slate-400 mt-1">$4.50 / $10.00 (45%)</p>
          </div>
        </div>

        <div className="metric-card">
          <p className="text-sm text-slate-400">Requests Per Minute</p>
          <p className="text-3xl font-bold">15 / 20</p>
          <p className="text-xs text-slate-400 mt-2">5 remaining</p>
        </div>

        <div className="metric-card">
          <p className="text-sm text-slate-400">Daily Token Usage</p>
          <p className="text-3xl font-bold">62K / 100K</p>
          <p className="text-xs text-slate-400 mt-2">38K remaining</p>
        </div>
      </div>

      <div className="metric-card">
        <h3 className="font-bold mb-4">Tier: Free</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-slate-400">Requests/Min</p>
            <p className="font-mono">20</p>
          </div>
          <div>
            <p className="text-slate-400">Requests/Hour</p>
            <p className="font-mono">500</p>
          </div>
          <div>
            <p className="text-slate-400">Monthly Budget</p>
            <p className="font-mono">$10.00</p>
          </div>
          <div>
            <p className="text-slate-400">Daily Tokens</p>
            <p className="font-mono">100,000</p>
          </div>
        </div>
      </div>
    </div>
  )
}
