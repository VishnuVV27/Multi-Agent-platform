'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  X, Brain, Search, BarChart3, PenLine, ShieldCheck, ZoomIn, ZoomOut,
  Clock, DollarSign, Cpu, CheckCircle2, XCircle, Loader2, Moon, Code2,
  ClipboardCheck,
} from 'lucide-react'
import Markdown from '@/components/Markdown'
import { API_BASE_URL } from '@/lib/api'

/**
 * Mission Control — the workflow rendered as a living AI operations room.
 *
 * Every planned agent is an animated robot character at a holographic
 * workstation. The task orb physically travels between stations as the real
 * workflow progresses; emotions, screens, and room lighting are all driven
 * by live run data. Clicking a station dims the room and opens a cinematic
 * inspection panel with the agent's actual inputs, outputs, and metrics.
 */

export interface MCAgentRun {
  agent_id: string
  agent_name: string | null
  status: string
  duration_ms: number | null
  cost: number | null
  tokens_used: number | null
  success: boolean
  error_message: string | null
  prompt_version?: string | null
  task_input?: string | null
  task_output: string | null
}

interface MissionControlProps {
  workflowId: string
  prompt: string
  status: string // running | waiting_approval | completed | failed | rejected
  plan: string[] // agents_selected, in execution order
  runs: MCAgentRun[]
  approvalReady: boolean
  onDecide: (approve: boolean) => void
  deciding: boolean
}

interface AgentProgress {
  agent_id: string
  phase: string
  detail?: string
  preview?: string
  ts?: number
}

type Emotion = 'working' | 'sleeping' | 'celebrating' | 'error' | 'waiting' | 'done'

const AGENT_META: Record<string, { label: string; role: string; color: string; icon: typeof Brain }> = {
  supervisor_agent: { label: 'Supervisor', role: 'Mission Planning', color: '#a855f7', icon: Brain },
  research_agent: { label: 'Researcher', role: 'Research Lab', color: '#10b981', icon: Search },
  coding_agent: { label: 'Coder', role: 'Development Studio', color: '#3b82f6', icon: Code2 },
  analysis_agent: { label: 'Analyst', role: 'Analytics Center', color: '#f59e0b', icon: BarChart3 },
  writer_agent: { label: 'Writer', role: 'Writing Studio', color: '#ec4899', icon: PenLine },
  critic_agent: { label: 'Critic', role: 'Quality Control', color: '#06b6d4', icon: ClipboardCheck },
}

// Mirrors SupervisorAgent.SOURCE_AGENTS: the leading run of source agents in
// a plan has no inter-dependencies — they execute concurrently. Everything
// after joins all prior work.
const SOURCE_AGENTS = new Set(['research_agent', 'coding_agent'])

// Each department has a fixed home on the two-row operations floor; rooms
// only materialize for agents actually in the plan.
const ROOM_HOMES: Record<string, { x: number; y: number; room: string }> = {
  supervisor_agent: { x: 13, y: 46, room: 'Planning Room' },
  research_agent: { x: 38, y: 26, room: 'Research Lab' },
  coding_agent: { x: 38, y: 72, room: 'Development Studio' },
  analysis_agent: { x: 61, y: 46, room: 'Analytics Center' },
  writer_agent: { x: 84, y: 26, room: 'Writing Studio' },
  critic_agent: { x: 84, y: 72, room: 'Quality Control' },
}

function predecessorsOf(plan: string[], idx: number): string[] {
  const inInitialSourceWave =
    SOURCE_AGENTS.has(plan[idx]) && plan.slice(0, idx).every(a => SOURCE_AGENTS.has(a))
  return inInitialSourceWave ? [] : plan.slice(0, idx)
}

const PARTICLES = [
  { left: '8%', top: '30%', size: 3, delay: '0s' },
  { left: '22%', top: '18%', size: 2, delay: '-2s' },
  { left: '38%', top: '34%', size: 3, delay: '-4s' },
  { left: '55%', top: '15%', size: 2, delay: '-1s' },
  { left: '70%', top: '28%', size: 3, delay: '-5s' },
  { left: '85%', top: '20%', size: 2, delay: '-3s' },
  { left: '15%', top: '52%', size: 2, delay: '-6s' },
  { left: '90%', top: '48%', size: 3, delay: '-7s' },
]

function extractReadable(taskOutput: string | null): string | null {
  if (!taskOutput) return null
  try {
    const parsed = JSON.parse(taskOutput)
    if (parsed.code) {
      // Coding agent: show summary, the code, and its REAL execution output
      return `${parsed.summary ?? ''}\n\n\`\`\`python\n${parsed.code}\n\`\`\`\n\n**Execution output:**\n\`\`\`\n${parsed.execution_output ?? ''}\n\`\`\``
    }
    return parsed.content ?? parsed.summary ?? parsed.analysis ?? JSON.stringify(parsed, null, 2)
  } catch {
    return taskOutput
  }
}

function extractSources(taskOutput: string | null): string[] {
  if (!taskOutput) return []
  try {
    const parsed = JSON.parse(taskOutput)
    return (parsed.findings ?? []).slice(0, 3).map((f: { title?: string }) => f.title ?? '')
  } catch {
    return []
  }
}

function AgentBot({ emotion }: { emotion: Emotion }) {
  const cls =
    emotion === 'working' ? 'mc-bot-working'
    : emotion === 'sleeping' ? 'mc-bot-sleeping'
    : emotion === 'celebrating' ? 'mc-bot-celebrating'
    : emotion === 'error' ? 'mc-bot-error'
    : emotion === 'waiting' ? 'mc-bot-waiting'
    : ''
  return (
    <div className={`mc-bot ${cls}`}>
      {emotion === 'sleeping' && (
        <div className="mc-zzz">z<span>z</span></div>
      )}
      <div className="mc-bot-head">
        <div className="mc-bot-antenna" />
        <div className="mc-bot-eye" />
        <div className="mc-bot-eye" />
      </div>
      <div className="mc-bot-body">
        <div className="mc-bot-core" />
      </div>
      <div className="mc-bot-arm mc-bot-arm-l" />
      <div className="mc-bot-arm mc-bot-arm-r" />
    </div>
  )
}

function StreamingText({ text }: { text: string }) {
  // Live LLM output tail on a holo monitor — last ~200 chars, cursor blinking
  return (
    <p className="text-[7.5px] leading-[1.5] text-slate-300 font-mono break-words max-h-[52px] overflow-hidden">
      …{text.slice(-200)}
      <span className="inline-block w-[4px] h-[8px] bg-slate-300 ml-0.5 align-middle animate-pulse" />
    </p>
  )
}

function HoloScreen({
  agentId,
  emotion,
  run,
  plan,
  doneCount,
  progress,
}: {
  agentId: string
  emotion: Emotion
  run: MCAgentRun | null
  plan: string[]
  doneCount: number
  progress: AgentProgress | null
}) {
  const active = emotion === 'working'
  const liveText = active && progress?.preview ? progress.preview : null
  const livePhase = active && progress?.phase ? progress.phase : null

  if (agentId === 'supervisor_agent') {
    return (
      <div className={`mc-holo ${active ? 'mc-holo-active' : ''} w-[120px] p-2 mb-1.5`}>
        <p className="text-[8px] uppercase tracking-widest text-slate-400 mb-1">Execution Plan</p>
        {plan.map((a, i) => (
          <div key={a} className="flex items-center gap-1.5 py-0.5">
            {i < doneCount ? (
              <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400 shrink-0" />
            ) : (
              <span className="w-2.5 h-2.5 rounded-full border border-slate-500 shrink-0" />
            )}
            <span className={`text-[9px] ${i < doneCount ? 'text-slate-300' : 'text-slate-500'}`}>
              {AGENT_META[a]?.label ?? a.replace('_agent', '')}
            </span>
          </div>
        ))}
      </div>
    )
  }

  if (agentId === 'research_agent') {
    const sources = extractSources(run?.task_output ?? null)
    return (
      <div className={`mc-holo ${active ? 'mc-holo-active' : ''} w-[120px] p-2 mb-1.5`}>
        <p className="text-[8px] uppercase tracking-widest text-slate-400 mb-1">Live Sources</p>
        {liveText ? (
          <StreamingText text={liveText} />
        ) : sources.length > 0 ? (
          sources.map((s, i) => (
            <p key={i} className="text-[8px] text-slate-300 truncate py-0.5">◦ {s}</p>
          ))
        ) : (
          <div className="space-y-1.5 py-0.5">
            <div className="mc-holo-line w-full" />
            <div className="mc-holo-line w-4/5" style={{ animationDelay: '0.2s' }} />
            <div className="mc-holo-line w-full" style={{ animationDelay: '0.4s' }} />
            <div className="mc-holo-line w-3/5" style={{ animationDelay: '0.6s' }} />
          </div>
        )}
        {livePhase && (
          <p className="text-[7.5px] text-slate-400 truncate mt-1 border-t border-white/10 pt-1">{livePhase}</p>
        )}
      </div>
    )
  }

  if (agentId === 'coding_agent') {
    let terminalLine: string | null = null
    if (run?.task_output) {
      try {
        const parsed = JSON.parse(run.task_output)
        terminalLine = (parsed.execution_output ?? '').split('\n')[0] || null
      } catch { /* raw output — skip */ }
    }
    return (
      <div className={`mc-holo ${active ? 'mc-holo-active' : ''} w-[120px] p-2 mb-1.5`}>
        <p className="text-[8px] uppercase tracking-widest text-slate-400 mb-1">Code</p>
        {liveText ? (
          <StreamingText text={liveText} />
        ) : (
          <div className="space-y-1.5 py-0.5 pl-1">
            <div className="mc-holo-line w-2/3" />
            <div className="mc-holo-line w-full ml-2" style={{ animationDelay: '0.15s', width: '80%' }} />
            <div className="mc-holo-line ml-2" style={{ animationDelay: '0.3s', width: '60%' }} />
            <div className="mc-holo-line w-1/2" style={{ animationDelay: '0.45s' }} />
          </div>
        )}
        <div className="mt-1.5 rounded bg-black/50 border border-white/10 px-1.5 py-1">
          <p className="text-[8px] font-mono text-emerald-300 truncate">
            {terminalLine ? `> ${terminalLine}` : livePhase ? `> ${livePhase}` : active ? '> working…' : '> _'}
          </p>
        </div>
      </div>
    )
  }

  if (agentId === 'critic_agent') {
    let score: number | null = null
    let verdict: string | null = null
    if (run?.task_output) {
      try {
        const parsed = JSON.parse(run.task_output)
        score = parsed.overall_score ?? null
        verdict = parsed.verdict ?? null
      } catch { /* skip */ }
    }
    return (
      <div className={`mc-holo ${active ? 'mc-holo-active' : ''} w-[120px] p-2 mb-1.5`}>
        <p className="text-[8px] uppercase tracking-widest text-slate-400 mb-1">QA Scan</p>
        {score != null ? (
          <div className="text-center py-1">
            <p className={`text-lg font-bold leading-none ${score >= 70 ? 'text-cyan-300' : 'text-amber-300'}`}>
              {score.toFixed(0)}
              <span className="text-[9px] text-slate-500 font-normal">/100</span>
            </p>
            <p className={`text-[9px] uppercase tracking-wide mt-0.5 ${verdict === 'approve' ? 'text-emerald-400' : 'text-amber-400'}`}>
              {verdict === 'approve' ? '✓ approved' : '↻ revise'}
            </p>
          </div>
        ) : liveText ? (
          <StreamingText text={liveText} />
        ) : (
          <div className="space-y-1.5 py-0.5">
            <div className="mc-holo-line w-full" />
            <div className="mc-holo-line w-3/4" style={{ animationDelay: '0.2s' }} />
            <div className="mc-holo-line w-full" style={{ animationDelay: '0.4s' }} />
          </div>
        )}
        {livePhase && score == null && (
          <p className="text-[7.5px] text-slate-400 truncate mt-1 border-t border-white/10 pt-1">{livePhase}</p>
        )}
      </div>
    )
  }

  if (agentId === 'analysis_agent') {
    return (
      <div className={`mc-holo ${active ? 'mc-holo-active' : ''} w-[120px] p-2 mb-1.5`}>
        <p className="text-[8px] uppercase tracking-widest text-slate-400 mb-1.5">Insights</p>
        {liveText ? (
          <StreamingText text={liveText} />
        ) : (
          <div className="flex items-end gap-1.5 h-[30px] px-1">
            {[0.5, 0.9, 0.65, 1, 0.75, 0.55].map((h, i) => (
              <div
                key={i}
                className="mc-holo-bar"
                style={{
                  height: `${h * 30}px`,
                  animationDelay: `${i * 0.18}s`,
                  animationPlayState: active ? 'running' : 'paused',
                }}
              />
            ))}
          </div>
        )}
        {livePhase && (
          <p className="text-[7.5px] text-slate-400 truncate mt-1 border-t border-white/10 pt-1">{livePhase}</p>
        )}
      </div>
    )
  }

  // writer_agent & fallback: a document filling with text
  return (
    <div className={`mc-holo ${active ? 'mc-holo-active' : ''} w-[120px] p-2 mb-1.5`}>
      <p className="text-[8px] uppercase tracking-widest text-slate-400 mb-1">Draft</p>
      {liveText ? (
        <StreamingText text={liveText} />
      ) : (
        <div className="space-y-1.5 py-0.5">
          <div className="mc-holo-line w-1/2" style={{ height: 5 }} />
          <div className="mc-holo-line w-full" style={{ animationDelay: '0.15s' }} />
          <div className="mc-holo-line w-11/12" style={{ animationDelay: '0.3s' }} />
          <div className="mc-holo-line w-full" style={{ animationDelay: '0.45s' }} />
          <div className="mc-holo-line w-2/3" style={{ animationDelay: '0.6s' }} />
        </div>
      )}
      {livePhase && (
        <p className="text-[7.5px] text-slate-400 truncate mt-1 border-t border-white/10 pt-1">{livePhase}</p>
      )}
    </div>
  )
}

export default function MissionControl({
  workflowId, prompt, status, plan, runs, approvalReady, onDecide, deciding,
}: MissionControlProps) {
  const [selected, setSelected] = useState<string | null>(null)
  const [zoom, setZoom] = useState(1)
  const [progress, setProgress] = useState<Record<string, AgentProgress>>({})

  // Live progress over SSE while the mission is running: agents publish
  // phases and streaming LLM previews that render on their holo monitors.
  useEffect(() => {
    if (status !== 'running') return
    const es = new EventSource(`${API_BASE_URL}/api/workflows/${workflowId}/stream`)
    es.onmessage = (e) => {
      try {
        const data: AgentProgress = JSON.parse(e.data)
        if (data.agent_id) {
          setProgress(prev => ({ ...prev, [data.agent_id]: data }))
        }
      } catch { /* keepalive or malformed frame */ }
    }
    return () => es.close()
  }, [status, workflowId])

  const runByAgent = useMemo(() => new Map(runs.map(r => [r.agent_id, r])), [runs])
  const doneCount = runs.filter(r => r.success).length

  // Station layout: every agent lives at its department's fixed home on the
  // floor — rooms exist only for agents in this plan.
  const stations = useMemo(() => {
    const list: { agentId: string; x: number; y: number; room: string }[] = []
    const seen = new Set<string>()
    for (const agentId of ['supervisor_agent', ...plan]) {
      if (seen.has(agentId)) continue
      seen.add(agentId)
      const home = ROOM_HOMES[agentId] ?? { x: 50, y: 46, room: 'Annex' }
      list.push({ agentId, ...home })
    }
    return list
  }, [plan])

  // Agents actively executing RIGHT NOW: no run yet, and every dependency
  // (per the same source-wave rule the Supervisor's DAG builder uses) has
  // finished. With parallel plans this can be several agents at once.
  const workingAgents = useMemo(() => {
    if (status !== 'running') return new Set<string>()
    return new Set(
      plan.filter((agentId, idx) => {
        if (runByAgent.has(agentId)) return false
        return predecessorsOf(plan, idx).every(p => runByAgent.get(p)?.success)
      }),
    )
  }, [status, plan, runByAgent])

  // Emotion per station, from real state
  const emotionOf = (agentId: string): Emotion => {
    if (agentId === 'supervisor_agent') {
      if (status === 'waiting_approval') return 'waiting'
      if (status === 'failed' || status === 'rejected') return 'error'
      return 'done'
    }
    const run = runByAgent.get(agentId)
    if (run) {
      if (!run.success) return 'error'
      if (status === 'completed' && plan[plan.length - 1] === agentId) return 'celebrating'
      return 'done'
    }
    if (workingAgents.has(agentId)) return 'working'
    return 'sleeping'
  }

  // Task orbs: one per station currently doing work (parallel waves show
  // several), collapsing back to a single delivery/failure/waiting orb.
  const orbs = useMemo(() => {
    const at = (st: { x: number; y: number }, color: string) =>
      // Hover just left of the bot's head, clear of the holo screen above it
      ({ x: st.x - 5.5, y: st.y - 1, color })

    if (status === 'waiting_approval') return [at(stations[0], '#f59e0b')]
    if (status === 'running') {
      const active = stations.filter(s => workingAgents.has(s.agentId))
      if (active.length > 0) {
        return active.map(s => at(s, AGENT_META[s.agentId]?.color ?? '#3b82f6'))
      }
      return [at(stations[0], '#a855f7')]
    }
    if (status === 'completed') return [at(stations[stations.length - 1], '#10b981')]
    if (status === 'failed') {
      const failed = stations.find(s => {
        const r = runByAgent.get(s.agentId)
        return r && !r.success
      })
      return [at(failed ?? stations[0], '#ef4444')]
    }
    return [at(stations[0], '#a855f7')]
  }, [status, stations, workingAgents, runByAgent])

  // Corridor edges mirror the real DAG: supervisor feeds every initial
  // source agent; each later agent joins from all its predecessors.
  const streamEdges = useMemo(() => {
    const byAgent = new Map(stations.map(s => [s.agentId, s]))
    const edges: {
      from: { x: number; y: number }
      to: { x: number; y: number }
      fromId: string
      toId: string
    }[] = []
    plan.forEach((agentId, idx) => {
      const to = byAgent.get(agentId)
      if (!to) return
      const preds = predecessorsOf(plan, idx)
      const fromIds = preds.length === 0 ? ['supervisor_agent'] : preds
      fromIds.forEach(fromId => {
        const from = byAgent.get(fromId)
        if (from) edges.push({ from, to, fromId, toId: agentId })
      })
    })
    return edges
  }, [stations, plan])

  // Courier drones fly along ACTIVE corridors: from a finished upstream
  // station to one that's working right now (capped so parallel joins
  // don't fill the sky).
  const drones = useMemo(() => {
    if (status !== 'running') return []
    const doneOrSupervisor = (agentId: string) =>
      agentId === 'supervisor_agent' || runByAgent.get(agentId)?.success
    return streamEdges
      .filter(e => workingAgents.has(e.toId) && doneOrSupervisor(e.fromId))
      .slice(0, 3)
      .map(e => ({
        fromX: e.from.x, fromY: e.from.y - 10,
        toX: e.to.x, toY: e.to.y - 10,
        color: AGENT_META[e.toId]?.color ?? '#3b82f6',
      }))
  }, [status, streamEdges, workingAgents, runByAgent])

  const lightClass =
    status === 'running' ? 'mc-light-running'
    : status === 'waiting_approval' ? 'mc-light-waiting'
    : status === 'completed' ? 'mc-light-completed'
    : status === 'failed' || status === 'rejected' ? 'mc-light-failed'
    : 'mc-light-running'

  const selectedRun = selected ? (runByAgent.get(selected) ?? null) : null
  const selectedMeta = selected ? AGENT_META[selected] : null

  return (
    <div className="relative">
      <div className="mc-room h-[600px] md:h-[660px]">
        {/* Environment */}
        <div className="mc-floor" />
        <div className={`mc-light ${lightClass}`} />
        {PARTICLES.map((p, i) => (
          <div
            key={i}
            className="mc-particle"
            style={{ left: p.left, top: p.top, width: p.size, height: p.size, animationDelay: p.delay }}
          />
        ))}

        {/* Zoomable stage */}
        <div
          className="absolute inset-0 transition-transform duration-500"
          style={{ transform: `scale(${zoom})`, transformOrigin: '50% 55%' }}
        >
          {/* Department rooms (glass zones behind each present station) */}
          {stations.map(({ agentId, x, y, room }) => {
            const meta = AGENT_META[agentId]
            return (
              <div
                key={`room-${agentId}`}
                className="mc-room-zone"
                style={{ left: `${x}%`, top: `${y}%`, ['--dept' as string]: meta?.color ?? '#3b82f6' }}
              >
                <div className="mc-room-label">{room}</div>
              </div>
            )
          })}

          {/* Corridors mirroring the DAG (wide glow + animated data line) */}
          <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
            {streamEdges.map((edge, i) => {
              const streaming = status === 'running' || status === 'completed'
              return (
                <g key={i}>
                  <line
                    x1={edge.from.x} y1={edge.from.y - 8} x2={edge.to.x} y2={edge.to.y - 8}
                    stroke={streaming ? 'rgba(96,165,250,0.08)' : 'rgba(100,116,139,0.06)'}
                    strokeWidth="2.4"
                    strokeLinecap="round"
                  />
                  <line
                    x1={edge.from.x} y1={edge.from.y - 8} x2={edge.to.x} y2={edge.to.y - 8}
                    stroke={streaming ? 'rgba(96,165,250,0.45)' : 'rgba(100,116,139,0.25)'}
                    strokeWidth="0.3"
                    className={streaming ? 'mc-stream' : ''}
                  />
                </g>
              )
            })}
          </svg>

          {/* Courier drones on active corridors */}
          {drones.map((d, i) => (
            <div
              key={i}
              className="mc-drone"
              style={{
                ['--fly-from-x' as string]: `${d.fromX}%`,
                ['--fly-from-y' as string]: `${d.fromY}%`,
                ['--fly-to-x' as string]: `${d.toX}%`,
                ['--fly-to-y' as string]: `${d.toY}%`,
                ['--fly-duration' as string]: `${2.6 + i * 0.5}s`,
                ['--packet' as string]: d.color,
              }}
            >
              <div className="mc-drone-body">
                <div className="mc-drone-packet" />
              </div>
            </div>
          ))}

          {/* Ambient assistant bots patrolling the floor */}
          <div
            className="mc-walker"
            style={{
              top: '88%',
              ['--patrol-from' as string]: '6%',
              ['--patrol-to' as string]: '88%',
              ['--patrol-duration' as string]: '34s',
              ['--bot' as string]: '#64748b',
            }}
          >
            <div className="mc-walker-flip scale-[0.55] opacity-60">
              <AgentBot emotion="done" />
            </div>
          </div>
          <div
            className="mc-walker"
            style={{
              top: '6%',
              ['--patrol-from' as string]: '72%',
              ['--patrol-to' as string]: '12%',
              ['--patrol-duration' as string]: '46s',
              ['--bot' as string]: '#64748b',
            }}
          >
            <div className="mc-walker-flip scale-[0.45] opacity-40">
              <AgentBot emotion="done" />
            </div>
          </div>

          {/* Task orbs — one per concurrently-working station */}
          {orbs.map((orb, i) => (
            <div
              key={i}
              className="mc-orb"
              style={{
                left: `calc(${orb.x}% - 9px)`,
                top: `calc(${orb.y}% - 9px)`,
                ['--orb' as string]: orb.color,
              }}
            />
          ))}

          {/* Stations */}
          {stations.map(({ agentId, x, y }) => {
            const meta = AGENT_META[agentId] ?? {
              label: agentId.replace('_agent', ''), role: 'Agent', color: '#3b82f6', icon: Brain,
            }
            const emotion = emotionOf(agentId)
            const run = runByAgent.get(agentId) ?? null
            const dimmed = selected !== null && selected !== agentId
            return (
              <div
                key={agentId}
                className={`mc-station ${dimmed ? 'mc-station-dimmed' : ''} ${selected === agentId ? 'mc-station-selected' : ''}`}
                style={{ left: `${x}%`, top: `${y}%`, ['--bot' as string]: meta.color }}
                onClick={() => setSelected(selected === agentId ? null : agentId)}
              >
                <HoloScreen
                  agentId={agentId}
                  emotion={emotion}
                  run={run}
                  plan={plan}
                  doneCount={doneCount}
                  progress={progress[agentId] ?? null}
                />
                <AgentBot emotion={emotion} />
                <div className="mc-pedestal" />
                <div className="text-center mt-1">
                  <p className="text-[11px] font-semibold text-slate-100">{meta.label}</p>
                  <p className="text-[9px] text-slate-500">{meta.role}</p>
                  {run && (
                    <p className="text-[9px] font-mono text-slate-400 mt-0.5">
                      {((run.duration_ms ?? 0) / 1000).toFixed(1)}s · ${(run.cost ?? 0).toFixed(4)}
                    </p>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {/* Mission banner */}
        <div className="mc-banner absolute top-4 left-1/2 max-w-[75%]">
          <div className="flex items-center gap-2.5 rounded-full bg-slate-950/70 backdrop-blur-md border border-white/15 px-4 py-2">
            {status === 'running' && <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin shrink-0" />}
            {status === 'completed' && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />}
            {status === 'waiting_approval' && <ShieldCheck className="w-3.5 h-3.5 text-amber-400 shrink-0" />}
            {(status === 'failed' || status === 'rejected') && <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />}
            <p className="text-xs text-slate-200 truncate">
              <span className="text-slate-500 uppercase tracking-widest text-[9px] mr-2">Mission</span>
              {prompt}
            </p>
          </div>
        </div>

        {/* Approval gate hologram */}
        {status === 'waiting_approval' && (
          <div className="absolute left-1/2 top-[30%] -translate-x-1/2 z-20">
            <div className="mc-holo p-4 w-[290px] text-center" style={{ ['--bot' as string]: '#f59e0b' }}>
              <ShieldCheck className="w-6 h-6 text-amber-400 mx-auto mb-2" />
              <p className="text-sm text-slate-100 font-medium mb-1">Plan awaiting your approval</p>
              <p className="text-xs text-slate-400 mb-3">
                {plan.map(a => AGENT_META[a]?.label ?? a).join(' → ')}
              </p>
              <div className="flex justify-center gap-2">
                <button
                  onClick={() => onDecide(true)}
                  disabled={deciding || !approvalReady}
                  className="px-3.5 py-1.5 rounded-lg text-xs text-emerald-200 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 disabled:opacity-50 transition-colors"
                >
                  {deciding ? 'Submitting…' : 'Approve & run'}
                </button>
                <button
                  onClick={() => onDecide(false)}
                  disabled={deciding || !approvalReady}
                  className="px-3.5 py-1.5 rounded-lg text-xs text-red-200 bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 disabled:opacity-50 transition-colors"
                >
                  Reject
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Zoom controls */}
        <div className="absolute bottom-4 left-4 flex gap-1.5 z-20">
          <button
            onClick={() => setZoom(z => Math.min(z + 0.25, 1.75))}
            className="p-2 rounded-lg bg-slate-900/70 border border-white/10 text-slate-300 hover:text-white hover:bg-slate-800/80 transition-colors"
            title="Zoom in"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={() => setZoom(z => Math.max(z - 0.25, 0.75))}
            className="p-2 rounded-lg bg-slate-900/70 border border-white/10 text-slate-300 hover:text-white hover:bg-slate-800/80 transition-colors"
            title="Zoom out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
        </div>

        {/* Dim overlay when inspecting */}
        {selected && (
          <div
            className="absolute inset-0 bg-black/40 z-10 transition-opacity"
            onClick={() => setSelected(null)}
          />
        )}

        {/* Cinematic inspection panel */}
        {selected && selectedMeta && (
          <div className="mc-panel absolute top-0 right-0 bottom-0 w-full sm:w-[380px] z-40 bg-slate-950/90 backdrop-blur-xl border-l border-white/10 overflow-y-auto">
            <div className="sticky top-0 bg-slate-950/95 backdrop-blur-xl border-b border-white/10 p-4 flex items-center gap-3">
              <div
                className="w-9 h-9 rounded-xl flex items-center justify-center border"
                style={{
                  backgroundColor: `${selectedMeta.color}20`,
                  borderColor: `${selectedMeta.color}60`,
                }}
              >
                <selectedMeta.icon className="w-4.5 h-4.5" style={{ color: selectedMeta.color }} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-slate-100">{selectedMeta.label}</p>
                <p className="text-xs text-slate-500">
                  {selectedMeta.role}
                  {selectedRun?.prompt_version && (
                    <span className="ml-2 px-1.5 py-0.5 rounded bg-white/5 border border-white/10 font-mono text-[10px] text-slate-400" title="Prompt Registry version used for this run">
                      prompt v{selectedRun.prompt_version}
                    </span>
                  )}
                </p>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 space-y-4">
              {/* Status */}
              <div className="flex items-center gap-2">
                {selected === 'supervisor_agent' ? (
                  <>
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span className="text-sm text-slate-300">Planned {plan.length}-agent pipeline</span>
                  </>
                ) : selectedRun ? (
                  selectedRun.success ? (
                    <><CheckCircle2 className="w-4 h-4 text-emerald-400" /><span className="text-sm text-slate-300">Completed</span></>
                  ) : (
                    <><XCircle className="w-4 h-4 text-red-400" /><span className="text-sm text-slate-300">Failed</span></>
                  )
                ) : emotionOf(selected) === 'working' ? (
                  <><Loader2 className="w-4 h-4 text-blue-400 animate-spin" /><span className="text-sm text-slate-300">Executing…</span></>
                ) : (
                  <><Moon className="w-4 h-4 text-slate-500" /><span className="text-sm text-slate-400">Queued — waiting for upstream work</span></>
                )}
              </div>

              {/* Metrics */}
              {selectedRun && (
                <div className="grid grid-cols-3 gap-2">
                  <div className="rounded-xl bg-white/5 border border-white/10 p-2.5 text-center">
                    <Clock className="w-3.5 h-3.5 text-blue-300 mx-auto mb-1" />
                    <p className="text-sm font-bold text-slate-100">{((selectedRun.duration_ms ?? 0) / 1000).toFixed(1)}s</p>
                  </div>
                  <div className="rounded-xl bg-white/5 border border-white/10 p-2.5 text-center">
                    <DollarSign className="w-3.5 h-3.5 text-emerald-300 mx-auto mb-1" />
                    <p className="text-sm font-bold text-slate-100">${(selectedRun.cost ?? 0).toFixed(4)}</p>
                  </div>
                  <div className="rounded-xl bg-white/5 border border-white/10 p-2.5 text-center">
                    <Cpu className="w-3.5 h-3.5 text-amber-300 mx-auto mb-1" />
                    <p className="text-sm font-bold text-slate-100">{selectedRun.tokens_used ?? 0}</p>
                  </div>
                </div>
              )}

              {/* Task input */}
              {selectedRun?.task_input && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-1.5">Instruction received</p>
                  <p className="text-xs text-slate-300 rounded-xl bg-white/5 border border-white/10 p-3 leading-relaxed">
                    {selectedRun.task_input}
                  </p>
                </div>
              )}
              {selected === 'supervisor_agent' && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-1.5">Mission received</p>
                  <p className="text-xs text-slate-300 rounded-xl bg-white/5 border border-white/10 p-3 leading-relaxed">{prompt}</p>
                  <p className="text-[10px] uppercase tracking-widest text-slate-500 mt-3 mb-1.5">Plan produced</p>
                  <div className="rounded-xl bg-white/5 border border-white/10 p-3 space-y-1">
                    {plan.map((a, i) => (
                      <p key={a} className="text-xs text-slate-300">
                        <span className="text-slate-500 font-mono mr-2">t{i + 1}</span>
                        {AGENT_META[a]?.label ?? a}
                        <span className="text-slate-500"> — {AGENT_META[a]?.role}</span>
                      </p>
                    ))}
                  </div>
                </div>
              )}

              {/* Error */}
              {selectedRun?.error_message && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-red-400 mb-1.5">Error</p>
                  <p className="text-xs text-red-300 rounded-xl bg-red-500/10 border border-red-500/30 p-3">
                    {selectedRun.error_message}
                  </p>
                </div>
              )}

              {/* Output */}
              {selectedRun?.task_output && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-1.5">Output produced</p>
                  <div className="rounded-xl bg-white/5 border border-white/10 p-3 max-h-[300px] overflow-y-auto text-sm">
                    <Markdown>{extractReadable(selectedRun.task_output) ?? ''}</Markdown>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
