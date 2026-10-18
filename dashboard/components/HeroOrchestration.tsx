'use client'

import { useEffect, useRef, useState } from 'react'
import {
  Brain, Search, BarChart3, PenLine, FileText, CheckCircle2, Loader2,
} from 'lucide-react'

/**
 * Self-playing animated demo of the orchestration pipeline.
 *
 * Loops through: a prompt "types" itself → Supervisor plans → each agent
 * lights up and completes in sequence → the report materializes → reset.
 * Pure React state machine + CSS transitions, no animation libraries.
 */

const DEMO_PROMPTS = [
  'Research the EV market in India and write a report',
  'Compare the top 3 vector databases for production RAG',
  'Analyze our workflow costs and summarize the trends',
]

const AGENTS = [
  { id: 'research', label: 'Research', icon: Search, color: 'emerald', detail: 'live web search' },
  { id: 'analysis', label: 'Analysis', icon: BarChart3, color: 'amber', detail: 'insights & patterns' },
  { id: 'writer', label: 'Writer', icon: PenLine, color: 'pink', detail: 'grounded report' },
]

// Timeline (ms in each phase): typing happens per-char before phase 1
const PHASES = {
  planning: 1600,
  agent: 1400, // per agent
  report: 2600,
  reset: 700,
}

type Stage = 'typing' | 'planning' | 0 | 1 | 2 | 'report' | 'reset'

const COLOR = {
  emerald: {
    active: 'border-emerald-400/70 bg-emerald-500/15 shadow-emerald-500/30',
    icon: 'text-emerald-300',
  },
  amber: {
    active: 'border-amber-400/70 bg-amber-500/15 shadow-amber-500/30',
    icon: 'text-amber-300',
  },
  pink: {
    active: 'border-pink-400/70 bg-pink-500/15 shadow-pink-500/30',
    icon: 'text-pink-300',
  },
} as const

export default function HeroOrchestration() {
  const [promptIdx, setPromptIdx] = useState(0)
  const [typed, setTyped] = useState('')
  const [stage, setStage] = useState<Stage>('typing')
  const timers = useRef<ReturnType<typeof setTimeout>[]>([])

  const schedule = (fn: () => void, ms: number) => {
    timers.current.push(setTimeout(fn, ms))
  }

  useEffect(() => {
    return () => timers.current.forEach(clearTimeout)
  }, [])

  // Stage driver
  useEffect(() => {
    const prompt = DEMO_PROMPTS[promptIdx]

    if (stage === 'typing') {
      if (typed.length < prompt.length) {
        schedule(() => setTyped(prompt.slice(0, typed.length + 1)), 28)
      } else {
        schedule(() => setStage('planning'), 500)
      }
      return
    }
    if (stage === 'planning') {
      schedule(() => setStage(0), PHASES.planning)
      return
    }
    if (typeof stage === 'number') {
      schedule(
        () => setStage(stage < AGENTS.length - 1 ? ((stage + 1) as Stage) : 'report'),
        PHASES.agent,
      )
      return
    }
    if (stage === 'report') {
      schedule(() => setStage('reset'), PHASES.report)
      return
    }
    // reset
    schedule(() => {
      setTyped('')
      setPromptIdx((promptIdx + 1) % DEMO_PROMPTS.length)
      setStage('typing')
    }, PHASES.reset)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage, typed, promptIdx])

  const agentState = (idx: number): 'done' | 'active' | 'idle' => {
    if (stage === 'report' || stage === 'reset') return 'done'
    if (typeof stage === 'number') {
      if (idx < stage) return 'done'
      if (idx === stage) return 'active'
    }
    return 'idle'
  }

  const supervisorActive = stage === 'planning'
  const supervisorDone = stage !== 'typing' && stage !== 'planning'
  const fading = stage === 'reset'

  return (
    <div className="animated-border rounded-2xl p-[1.5px]">
    <div
      className={`relative overflow-hidden rounded-2xl bg-slate-950/90 backdrop-blur-xl p-5 md:p-6 transition-opacity duration-500 ${fading ? 'opacity-30' : 'opacity-100'}`}
    >
      {/* Prompt bar */}
      <div className="flex items-center gap-3 rounded-xl bg-slate-950/70 border border-white/10 px-4 py-3 mb-6">
        <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse shrink-0" />
        <p className="text-sm text-slate-200 font-mono min-h-[1.25rem]">
          {typed}
          <span className="inline-block w-[7px] h-[15px] bg-blue-400 ml-0.5 align-middle animate-pulse" />
        </p>
      </div>

      {/* Pipeline */}
      <div className="flex items-center justify-between gap-1 md:gap-2">
        {/* Supervisor */}
        <div
          className={`flex-1 min-w-0 rounded-xl border px-1.5 py-2.5 text-center transition-all duration-500 ${
            supervisorActive
              ? 'border-purple-400/70 bg-purple-500/15 shadow-lg shadow-purple-500/30 scale-[1.03]'
              : supervisorDone
                ? 'border-purple-500/40 bg-purple-500/10'
                : 'border-white/10 bg-white/5 opacity-50'
          }`}
        >
          <div className="flex items-center justify-center mb-1.5">
            {supervisorActive ? (
              <Loader2 className="w-5 h-5 text-purple-300 animate-spin" />
            ) : supervisorDone ? (
              <CheckCircle2 className="w-5 h-5 text-purple-400" />
            ) : (
              <Brain className="w-5 h-5 text-slate-500" />
            )}
          </div>
          <p className="text-[11px] md:text-xs font-semibold text-slate-100 truncate">Supervisor</p>
          <p className="text-[10px] text-slate-400 hidden lg:block truncate">
            {supervisorActive ? 'planning DAG…' : supervisorDone ? '3-agent plan' : 'plans the DAG'}
          </p>
        </div>

        <Connector active={supervisorDone} />

        {AGENTS.map((agent, idx) => {
          const state = agentState(idx)
          const c = COLOR[agent.color as keyof typeof COLOR]
          return (
            <div key={agent.id} className="contents">
              {idx > 0 && <Connector active={agentState(idx - 1) === 'done'} />}
              <div
                className={`flex-1 min-w-0 rounded-xl border px-1.5 py-2.5 text-center transition-all duration-500 ${
                  state === 'active'
                    ? `${c.active} shadow-lg scale-[1.03]`
                    : state === 'done'
                      ? `border-white/20 bg-white/10`
                      : 'border-white/10 bg-white/5 opacity-50'
                }`}
              >
                <div className="flex items-center justify-center mb-1.5">
                  {state === 'active' ? (
                    <Loader2 className={`w-5 h-5 ${c.icon} animate-spin`} />
                  ) : state === 'done' ? (
                    <CheckCircle2 className={`w-5 h-5 ${c.icon}`} />
                  ) : (
                    <agent.icon className="w-5 h-5 text-slate-500" />
                  )}
                </div>
                <p className="text-[11px] md:text-xs font-semibold text-slate-100 truncate">{agent.label}</p>
                <p className="text-[10px] text-slate-400 hidden lg:block truncate">
                  {state === 'active' ? 'executing…' : agent.detail}
                </p>
              </div>
            </div>
          )
        })}

        <Connector active={stage === 'report' || stage === 'reset'} />

        {/* Report */}
        <div
          className={`flex-1 min-w-0 rounded-xl border px-1.5 py-2.5 text-center transition-all duration-500 ${
            stage === 'report' || stage === 'reset'
              ? 'border-blue-400/70 bg-blue-500/15 shadow-lg shadow-blue-500/30 scale-[1.03]'
              : 'border-white/10 bg-white/5 opacity-50'
          }`}
        >
          <div className="flex items-center justify-center mb-1.5">
            <FileText className={`w-5 h-5 ${stage === 'report' || stage === 'reset' ? 'text-blue-300' : 'text-slate-500'}`} />
          </div>
          <p className="text-[11px] md:text-xs font-semibold text-slate-100 truncate">Report</p>
          <p className="text-[10px] text-slate-400 hidden lg:block truncate">
            {stage === 'report' || stage === 'reset' ? 'delivered ✓' : 'cited sources'}
          </p>
        </div>
      </div>

      {/* Report skeleton materializing */}
      <div
        className={`mt-6 space-y-2 overflow-hidden transition-all duration-700 ${
          stage === 'report' || stage === 'reset' ? 'max-h-24 opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="h-2.5 w-1/3 rounded bg-blue-400/30" />
        <div className="h-2 w-full rounded bg-white/10" />
        <div className="h-2 w-5/6 rounded bg-white/10" />
        <div className="h-2 w-2/3 rounded bg-white/10" />
      </div>
    </div>
    </div>
  )
}

function Connector({ active }: { active: boolean }) {
  return (
    <div className="relative w-3 md:w-5 h-0.5 shrink-0 rounded bg-white/10 overflow-hidden">
      <div
        className={`absolute inset-0 bg-gradient-to-r from-blue-400 to-purple-400 transition-transform duration-700 origin-left ${
          active ? 'scale-x-100' : 'scale-x-0'
        }`}
      />
      {active && (
        <div className="absolute inset-y-0 w-2 bg-white/70 blur-[2px] animate-flow" />
      )}
    </div>
  )
}
