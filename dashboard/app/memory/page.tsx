'use client'

import { useEffect, useState } from 'react'
import { Brain, Search, Database, GitMerge, Zap, CheckCircle2 } from 'lucide-react'
import GlassCard from '@/components/GlassCard'
import { apiFetch, ApiError } from '@/lib/api'

interface MemoryStatistics {
  total_workflows: number
  success_count: number
  failure_count: number
  success_rate: number
  avg_cost: number
  avg_tokens: number
  avg_execution_time_ms: number
}

interface WorkflowMemory {
  workflow_id: string
  user_request: string
  agents_selected: string[]
  total_cost: number
  success: boolean
  success_rate: number
}

interface RankedWorkflow {
  workflow_memory: WorkflowMemory
  relevance_score: number
  success_bonus: number
  cost_bonus: number
  final_score: number
}

interface RetrievalResponse {
  query: string
  results: RankedWorkflow[]
  retrieval_time_ms: number
  sparse_results_count: number
  dense_results_count: number
  candidate_pool_size: number
  took_rerank_time_ms: number
}

export default function MemoryPage() {
  const [stats, setStats] = useState<MemoryStatistics | null>(null)
  const [query, setQuery] = useState('Tell me about the history of Python as a programming language')
  const [topK, setTopK] = useState(3)
  const [minSimilarity, setMinSimilarity] = useState(0.5)
  const [response, setResponse] = useState<RetrievalResponse | null>(null)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<MemoryStatistics>('/api/memory/statistics')
      .then(setStats)
      .catch(() => {})
  }, [])

  const runSearch = async () => {
    if (!query.trim()) return
    setSearching(true)
    setError(null)
    try {
      const result = await apiFetch<RetrievalResponse>('/api/memory/retrieve', {
        method: 'POST',
        body: JSON.stringify({
          query,
          top_k: topK,
          min_similarity: minSimilarity,
        }),
      })
      setResponse(result)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the API')
      setResponse(null)
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <h1 className="text-4xl font-bold text-slate-100 flex items-center gap-3">
          <Brain className="w-8 h-8 text-purple-400" />
          Memory & RAG
        </h1>
        <p className="text-slate-400">Hybrid retrieval (BM25 + dense vector search) over past workflows</p>
      </div>

      <div className="bento-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
        <GlassCard tone="blue" className="p-4">
          <div className="flex items-center gap-2 text-blue-300 mb-1">
            <Database className="w-4 h-4" />
            <p className="text-xs font-medium">Stored Workflows</p>
          </div>
          <p className="text-3xl font-bold text-slate-100">{stats?.total_workflows ?? '—'}</p>
        </GlassCard>
        <GlassCard tone="emerald" className="p-4">
          <div className="flex items-center gap-2 text-emerald-300 mb-1">
            <CheckCircle2 className="w-4 h-4" />
            <p className="text-xs font-medium">Success Rate</p>
          </div>
          <p className="text-3xl font-bold text-slate-100">{((stats?.success_rate ?? 0) * 100).toFixed(0)}%</p>
        </GlassCard>
        <GlassCard tone="amber" className="p-4">
          <div className="flex items-center gap-2 text-amber-300 mb-1">
            <Zap className="w-4 h-4" />
            <p className="text-xs font-medium">Avg Cost</p>
          </div>
          <p className="text-3xl font-bold text-slate-100">${(stats?.avg_cost ?? 0).toFixed(4)}</p>
        </GlassCard>
        <GlassCard tone="slate" className="p-4">
          <div className="flex items-center gap-2 text-slate-300 mb-1">
            <GitMerge className="w-4 h-4" />
            <p className="text-xs font-medium">Avg Tokens</p>
          </div>
          <p className="text-3xl font-bold text-slate-100">{stats?.avg_tokens ?? '—'}</p>
        </GlassCard>
      </div>

      <GlassCard tone="slate" className="p-5">
        <h3 className="font-semibold text-slate-100 mb-4">Test Retrieval</h3>
        <div className="flex flex-col md:flex-row gap-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runSearch()}
            placeholder="Enter a query to test hybrid search…"
            className="flex-1 px-4 py-2.5 rounded-xl bg-slate-900/60 border border-white/10 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-purple-500/50"
          />
          <div className="flex gap-2">
            <input
              type="number"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              min={1}
              max={20}
              title="top_k"
              className="w-20 px-3 py-2.5 rounded-xl bg-slate-900/60 border border-white/10 text-slate-100 focus:outline-none focus:border-purple-500/50"
            />
            <input
              type="number"
              value={minSimilarity}
              onChange={(e) => setMinSimilarity(Number(e.target.value))}
              min={0}
              max={1}
              step={0.05}
              title="min_similarity"
              className="w-24 px-3 py-2.5 rounded-xl bg-slate-900/60 border border-white/10 text-slate-100 focus:outline-none focus:border-purple-500/50"
            />
            <button
              onClick={runSearch}
              disabled={searching}
              className="px-5 py-2.5 rounded-xl bg-purple-500/20 border border-purple-500/40 text-purple-200 hover:bg-purple-500/30 transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              <Search className="w-4 h-4" />
              {searching ? 'Searching…' : 'Search'}
            </button>
          </div>
        </div>

        {error && <p className="text-sm text-red-300 mt-3">Couldn't reach the API: {error}</p>}

        {response && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-5">
              <div className="rounded-xl bg-slate-900/40 border border-white/10 p-3 text-center">
                <p className="text-xs text-slate-400 mb-1">Sparse (BM25)</p>
                <p className="text-xl font-bold text-slate-100">{response.sparse_results_count}</p>
              </div>
              <div className="rounded-xl bg-slate-900/40 border border-white/10 p-3 text-center">
                <p className="text-xs text-slate-400 mb-1">Dense (Vector)</p>
                <p className="text-xl font-bold text-slate-100">{response.dense_results_count}</p>
              </div>
              <div className="rounded-xl bg-slate-900/40 border border-white/10 p-3 text-center">
                <p className="text-xs text-slate-400 mb-1">Candidate Pool</p>
                <p className="text-xl font-bold text-slate-100">{response.candidate_pool_size}</p>
              </div>
              <div className="rounded-xl bg-slate-900/40 border border-white/10 p-3 text-center">
                <p className="text-xs text-slate-400 mb-1">Rerank Time</p>
                <p className="text-xl font-bold text-slate-100">{response.took_rerank_time_ms.toFixed(2)}ms</p>
              </div>
              <div className="rounded-xl bg-slate-900/40 border border-white/10 p-3 text-center">
                <p className="text-xs text-slate-400 mb-1">Total Time</p>
                <p className="text-xl font-bold text-slate-100">{response.retrieval_time_ms.toFixed(0)}ms</p>
              </div>
            </div>

            <div className="mt-5 space-y-2">
              {response.results.length === 0 ? (
                <p className="text-sm text-slate-400 py-6 text-center">No similar workflows found above the similarity threshold.</p>
              ) : (
                response.results.map((r) => (
                  <div
                    key={r.workflow_memory.workflow_id}
                    className="rounded-xl bg-slate-900/40 border border-white/10 p-4 flex items-center justify-between gap-4"
                  >
                    <div className="min-w-0">
                      <p className="text-slate-100 text-sm truncate">{r.workflow_memory.user_request}</p>
                      <p className="text-xs text-slate-400 mt-1">
                        {r.workflow_memory.agents_selected.join(' → ')} · ${r.workflow_memory.total_cost.toFixed(4)}
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-lg font-bold text-purple-300">{(r.final_score * 100).toFixed(0)}%</p>
                      <p className="text-xs text-slate-500">match score</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </GlassCard>
    </div>
  )
}
