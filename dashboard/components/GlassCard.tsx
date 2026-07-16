import { ReactNode } from 'react'

export type GlassTone = 'blue' | 'emerald' | 'red' | 'orange' | 'amber' | 'slate'

const TONE_CLASSES: Record<GlassTone, string> = {
  blue: 'from-blue-500/20 to-blue-600/10 border-blue-500/30',
  emerald: 'from-emerald-500/20 to-emerald-600/10 border-emerald-500/30',
  red: 'from-red-500/20 to-red-600/10 border-red-500/30',
  orange: 'from-orange-500/20 to-orange-600/10 border-orange-500/30',
  amber: 'from-amber-500/20 to-amber-600/10 border-amber-500/30',
  slate: 'from-slate-700/20 to-slate-800/10 border-slate-600/30',
}

interface GlassCardProps {
  tone?: GlassTone
  hover?: boolean
  className?: string
  children: ReactNode
}

export default function GlassCard({ tone = 'slate', hover = false, className = '', children }: GlassCardProps) {
  return (
    <div
      className={`
        relative overflow-hidden rounded-2xl backdrop-blur-xl
        bg-gradient-to-br border ${TONE_CLASSES[tone]}
        ${hover ? 'transition-all duration-300 hover:shadow-lg hover:shadow-white/5' : ''}
        ${className}
      `}
    >
      <div className="absolute inset-0 bg-white/[0.01] pointer-events-none" />
      <div className="relative z-10">{children}</div>
    </div>
  )
}
