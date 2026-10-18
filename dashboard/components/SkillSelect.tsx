'use client'

import { useEffect, useRef, useState } from 'react'
import {
  ChevronDown, Check, Search, X, Zap, FileText, FlaskConical, ShieldCheck, Wrench,
} from 'lucide-react'
import { apiFetch } from '@/lib/api'

/**
 * Searchable multi-select of agent skills (skillsllm-style instruction
 * modules) served by /api/skills. Enabling a skill injects its behavior
 * instructions into the agents it targets — additive, the Supervisor
 * still plans freely.
 */

interface Skill {
  id: string
  label: string
  description: string
  category: string
  source?: string
  agents: string[]
}

const CATEGORY_META: Record<string, { icon: typeof Zap; color: string }> = {
  methodology: { icon: Zap, color: '#a855f7' },
  documents: { icon: FileText, color: '#ec4899' },
  research: { icon: FlaskConical, color: '#10b981' },
  quality: { icon: ShieldCheck, color: '#06b6d4' },
  development: { icon: Wrench, color: '#3b82f6' },
}

export default function SkillSelect({
  selected,
  onChange,
}: {
  selected: string[]
  onChange: (skills: string[]) => void
}) {
  const [skills, setSkills] = useState<Skill[]>([])
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    apiFetch<{ skills: Skill[] }>('/api/skills/')
      .then(d => setSkills(d.skills))
      .catch(() => {})
  }, [])

  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  const toggle = (id: string) =>
    onChange(selected.includes(id) ? selected.filter(s => s !== id) : [...selected, id])

  const metaOf = (skill: Skill) => CATEGORY_META[skill.category] ?? CATEGORY_META.development

  const q = query.toLowerCase()
  const filtered = skills.filter(
    s =>
      s.label.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q) ||
      s.category.toLowerCase().includes(q),
  )

  return (
    <div ref={rootRef} className="relative">
      {/* Field */}
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2 rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-left hover:border-white/20 transition-colors"
      >
        <div className="flex-1 flex items-center flex-wrap gap-1.5 min-h-[22px]">
          {selected.length === 0 ? (
            <span className="text-slate-500">No skills enabled — search & click to add behavior modules…</span>
          ) : (
            selected.map(id => {
              const skill = skills.find(s => s.id === id)
              if (!skill) return null
              const meta = metaOf(skill)
              return (
                <span
                  key={id}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs border"
                  style={{
                    backgroundColor: `${meta.color}18`,
                    borderColor: `${meta.color}55`,
                    color: meta.color,
                  }}
                >
                  <meta.icon className="w-3 h-3" />
                  {skill.label}
                  <span
                    role="button"
                    onClick={(e) => { e.stopPropagation(); toggle(id) }}
                    className="hover:opacity-70 cursor-pointer"
                  >
                    <X className="w-3 h-3" />
                  </span>
                </span>
              )
            })
          )}
        </div>
        <ChevronDown className={`w-4 h-4 text-slate-500 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-40 mt-1.5 w-full rounded-xl bg-slate-950/95 backdrop-blur-xl border border-white/15 shadow-2xl shadow-black/50 overflow-hidden">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-white/10">
            <Search className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search skills — try 'pdf', 'caveman', 'design'…"
              className="w-full bg-transparent text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none"
            />
          </div>
          <div className="max-h-64 overflow-y-auto py-1">
            {skills.length === 0 ? (
              <p className="px-3 py-3 text-sm text-slate-500">Loading skills…</p>
            ) : filtered.length === 0 ? (
              <p className="px-3 py-3 text-sm text-slate-500">No skills match “{query}”</p>
            ) : (
              filtered.map(skill => {
                const isSelected = selected.includes(skill.id)
                const meta = metaOf(skill)
                return (
                  <button
                    key={skill.id}
                    type="button"
                    onClick={() => toggle(skill.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-white/5 transition-colors ${isSelected ? 'bg-white/[0.04]' : ''}`}
                  >
                    <div
                      className="w-7 h-7 rounded-lg flex items-center justify-center border shrink-0"
                      style={{ backgroundColor: `${meta.color}18`, borderColor: `${meta.color}50` }}
                    >
                      <meta.icon className="w-3.5 h-3.5" style={{ color: meta.color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-200">
                        {skill.label}
                        {skill.source && (
                          <span className="ml-2 text-[10px] font-mono text-slate-500">{skill.source}</span>
                        )}
                      </p>
                      <p className="text-xs text-slate-500 truncate">{skill.description}</p>
                    </div>
                    <div
                      className={`w-[18px] h-[18px] rounded border flex items-center justify-center shrink-0 ${
                        isSelected ? 'bg-blue-500 border-blue-400' : 'border-slate-600'
                      }`}
                    >
                      {isSelected && <Check className="w-3 h-3 text-white" />}
                    </div>
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
