'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import {
  ArrowRight, Bot, Brain, GitBranch, ShieldCheck, Wrench, Radio,
  MessageSquare, Workflow, FileText, Database, Zap, DollarSign,
  CheckCircle2, XCircle, Activity,
} from 'lucide-react'
import GlassCard from '@/components/GlassCard'
import HeroOrchestration from '@/components/HeroOrchestration'
import ActivityTicker from '@/components/ActivityTicker'
import Reveal from '@/components/Reveal'
import CountUp from '@/components/CountUp'
import { apiFetch } from '@/lib/api'

interface HealthResponse {
  status: string
  services: Record<string, string>
}

interface MemoryStats {
  total_workflows: number
  success_rate: number
  avg_cost: number
}

const PIPELINE_STEPS = [
  {
    icon: MessageSquare,
    title: 'Prompt',
    detail: 'You describe a goal in plain language',
    color: 'text-slate-300',
  },
  {
    icon: Brain,
    title: 'Supervisor',
    detail: 'LLM planner builds a task DAG, informed by RAG memory of past workflows',
    color: 'text-purple-300',
  },
  {
    icon: Workflow,
    title: 'Temporal',
    detail: 'Durable orchestration — retries, timeouts, human approval gates',
    color: 'text-blue-300',
  },
  {
    icon: Bot,
    title: 'Agents',
    detail: 'Research, analysis, and writer agents execute in dependency order',
    color: 'text-emerald-300',
  },
  {
    icon: Wrench,
    title: 'Tool Gateway',
    detail: 'Permissioned access to live web search, SQL, files, and sandboxed code',
    color: 'text-amber-300',
  },
  {
    icon: FileText,
    title: 'Result + Memory',
    detail: 'Grounded report delivered; the run is embedded into memory for next time',
    color: 'text-pink-300',
  },
]

const CAPABILITIES = [
  {
    icon: Brain,
    title: 'LLM-Powered Planning',
    body: 'A Supervisor agent analyzes each request and emits a task DAG — different prompts produce different agent pipelines, nothing is hardcoded.',
    href: '/workflows',
    tone: 'blue' as const,
  },
  {
    icon: GitBranch,
    title: 'Durable Orchestration',
    body: 'Temporal owns the DAG: dependency ordering, bounded retries, and workflows that survive process restarts mid-run.',
    href: '/workflows',
    tone: 'blue' as const,
  },
  {
    icon: ShieldCheck,
    title: 'Human-in-the-Loop',
    body: 'Optional plan approval parks the workflow durably until you approve or reject the Supervisor’s plan — agents spend nothing until you say go.',
    href: '/approvals',
    tone: 'emerald' as const,
  },
  {
    icon: Database,
    title: 'Hybrid RAG Memory',
    body: 'Every run is embedded into pgvector. The Supervisor retrieves similar past workflows (BM25 + dense search) to plan better over time.',
    href: '/memory',
    tone: 'emerald' as const,
  },
  {
    icon: DollarSign,
    title: 'Cost Governance',
    body: 'Every LLM call is metered through a LiteLLM gateway with per-user rate limits and monthly budgets enforced before agents run.',
    href: '/rate-limiting',
    tone: 'amber' as const,
  },
  {
    icon: Radio,
    title: 'Event-Driven Observability',
    body: 'Agent lifecycle events stream to Kafka; latency, cost, and success metrics land in dashboards — agents never know who’s watching.',
    href: '/metrics',
    tone: 'amber' as const,
  },
]

const STACK = [
  'FastAPI', 'Temporal', 'Kafka', 'PostgreSQL + pgvector', 'Redis',
  'LiteLLM', 'Langfuse', 'Next.js',
]

export default function HomePage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [stats, setStats] = useState<MemoryStats | null>(null)

  useEffect(() => {
    apiFetch<HealthResponse>('/health').then(setHealth).catch(() => setHealth(null))
    apiFetch<MemoryStats>('/api/memory/statistics').then(setStats).catch(() => {})
  }, [])

  return (
    <div className="space-y-16 pb-8">
      {/* Hero */}
      <section className="relative pt-10 md:pt-14">
        {/* Ambient animated blobs */}
        <div className="hero-blob w-96 h-96 bg-blue-600 -top-20 -left-24" style={{ animationDelay: '0s' }} />
        <div className="hero-blob w-80 h-80 bg-purple-600 top-10 right-0" style={{ animationDelay: '-5s' }} />
        <div className="hero-blob w-72 h-72 bg-emerald-600 bottom-0 left-1/3" style={{ animationDelay: '-9s' }} />

        <div className="relative grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
          <div className="space-y-6 text-center lg:text-left">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-300 text-xs font-medium">
              <Zap className="w-3.5 h-3.5" />
              Multi-Agent AI Orchestration Platform
            </div>
            <h1 className="text-5xl md:text-6xl font-bold tracking-tight text-slate-100">
              One prompt.
              <br />
              <span className="bg-gradient-to-r from-blue-400 via-purple-400 to-emerald-400 bg-clip-text text-transparent">
                A team of agents.
              </span>
            </h1>
            <p className="max-w-xl mx-auto lg:mx-0 text-lg text-slate-400 leading-relaxed">
              SupervisorFlow turns a natural-language request into a plan of specialized AI
              agents — researched with live web data, orchestrated durably by Temporal, gated
              by human approval, and remembered for the next run.
            </p>
            <div className="flex items-center justify-center lg:justify-start gap-3 pt-2">
              <Link
                href="/workflows"
                className="inline-flex items-center gap-2 px-5 py-3 rounded-xl font-medium text-sm text-white bg-blue-600 hover:bg-blue-500 transition-colors shadow-lg shadow-blue-500/25"
              >
                Launch a workflow
                <ArrowRight className="w-4 h-4" />
              </Link>
              <a
                href="#how-it-works"
                className="inline-flex items-center gap-2 px-5 py-3 rounded-xl font-medium text-sm text-slate-300 bg-white/5 hover:bg-white/10 border border-white/10 transition-colors"
              >
                How it works
              </a>
            </div>
          </div>

          {/* Live animated pipeline demo */}
          <HeroOrchestration />
        </div>
      </section>

      {/* Live status */}
      <section>
        <GlassCard tone="slate" className="p-5">
          <div className="flex flex-col md:flex-row md:items-center gap-5 md:gap-8">
            <div className="flex items-center gap-2 shrink-0">
              <span className={`w-2.5 h-2.5 rounded-full ${health?.status === 'operational' ? 'bg-emerald-400 animate-pulse' : health ? 'bg-amber-400' : 'bg-slate-600'}`} />
              <span className="text-sm font-medium text-slate-200">
                {health?.status === 'operational' ? 'All systems operational' : health ? 'Degraded' : 'API offline'}
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {['database', 'redis', 'temporal', 'kafka'].map((svc) => {
                const s = health?.services?.[svc]
                const ok = s === 'healthy'
                return (
                  <span
                    key={svc}
                    className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md border ${
                      ok
                        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                        : 'bg-slate-800/60 border-white/10 text-slate-500'
                    }`}
                  >
                    {ok ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                    {svc}
                  </span>
                )
              })}
            </div>
            {stats && (
              <div className="flex items-center gap-6 md:ml-auto text-sm">
                <div>
                  <span className="text-slate-100 font-bold">
                    <CountUp value={stats.total_workflows} />
                  </span>
                  <span className="text-slate-500 ml-1.5">workflows run</span>
                </div>
                <div>
                  <span className="text-slate-100 font-bold">
                    <CountUp value={stats.success_rate * 100} format={(n) => `${n.toFixed(0)}%`} />
                  </span>
                  <span className="text-slate-500 ml-1.5">success</span>
                </div>
                <div>
                  <span className="text-slate-100 font-bold">
                    <CountUp value={stats.avg_cost} format={(n) => `$${n.toFixed(4)}`} />
                  </span>
                  <span className="text-slate-500 ml-1.5">avg cost</span>
                </div>
              </div>
            )}
          </div>
        </GlassCard>
      </section>

      {/* Live activity from real runs */}
      <section className="-mt-8">
        <ActivityTicker />
      </section>

      {/* How it works */}
      <section id="how-it-works" className="space-y-8 scroll-mt-24">
        <div className="text-center space-y-2">
          <h2 className="text-3xl font-bold text-slate-100">How it works</h2>
          <p className="text-slate-400 max-w-xl mx-auto">
            Not a chatbot with extra steps — a real orchestration pipeline where every stage is a
            separate, observable, restartable unit of work.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {PIPELINE_STEPS.map((step, i) => (
            <Reveal key={step.title} delay={i * 90}>
              <GlassCard tone="slate" hover className="p-5 relative h-full">
                <span className="absolute top-4 right-4 text-3xl font-bold text-white/5">
                  {i + 1}
                </span>
                <step.icon className={`w-6 h-6 mb-3 ${step.color}`} />
                <h3 className="font-semibold text-slate-100 mb-1.5 flex items-center gap-2">
                  {step.title}
                  {i < PIPELINE_STEPS.length - 1 && (
                    <ArrowRight className="w-3.5 h-3.5 text-slate-600" />
                  )}
                </h3>
                <p className="text-sm text-slate-400 leading-relaxed">{step.detail}</p>
              </GlassCard>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Capabilities */}
      <section className="space-y-8">
        <div className="text-center space-y-2">
          <h2 className="text-3xl font-bold text-slate-100">Built like production, not a demo</h2>
          <p className="text-slate-400 max-w-xl mx-auto">
            Eleven architecture components — registry, contracts, gateways, approvals,
            memory, budgets — collapsed into one working vertical slice.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {CAPABILITIES.map((cap, i) => (
            <Reveal key={cap.title} delay={i * 90}>
              <Link href={cap.href} className="block h-full">
                <GlassCard tone={cap.tone} hover className="p-5 h-full cursor-pointer">
                  <cap.icon className="w-6 h-6 mb-3 text-slate-200" />
                  <h3 className="font-semibold text-slate-100 mb-1.5">{cap.title}</h3>
                  <p className="text-sm text-slate-400 leading-relaxed">{cap.body}</p>
                </GlassCard>
              </Link>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Stack */}
      <section className="text-center space-y-5">
        <p className="text-xs font-medium uppercase tracking-widest text-slate-500">
          Powered by
        </p>
        <div className="flex flex-wrap items-center justify-center gap-2.5">
          {STACK.map((tech) => (
            <span
              key={tech}
              className="text-sm px-3.5 py-1.5 rounded-lg bg-white/5 border border-white/10 text-slate-300"
            >
              {tech}
            </span>
          ))}
        </div>
        <div className="pt-4">
          <Link
            href="/workflows"
            className="inline-flex items-center gap-2 text-sm text-blue-300 hover:text-blue-200 transition-colors"
          >
            <Activity className="w-4 h-4" />
            Open the console
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>
    </div>
  )
}
