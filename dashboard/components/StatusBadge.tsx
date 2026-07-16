import { Activity, Check, X, Clock } from 'lucide-react'

type Status = 'running' | 'completed' | 'failed' | 'pending' | string

const STATUS_STYLES: Record<string, string> = {
  running: 'bg-blue-500/20 text-blue-300',
  completed: 'bg-emerald-500/20 text-emerald-300',
  failed: 'bg-red-500/20 text-red-300',
  pending: 'bg-amber-500/20 text-amber-300',
}

const STATUS_ICONS: Record<string, JSX.Element> = {
  running: <Activity className="w-3.5 h-3.5 animate-spin" />,
  completed: <Check className="w-3.5 h-3.5" />,
  failed: <X className="w-3.5 h-3.5" />,
  pending: <Clock className="w-3.5 h-3.5" />,
}

export default function StatusBadge({ status }: { status: Status }) {
  const style = STATUS_STYLES[status] ?? 'bg-slate-500/20 text-slate-300'
  const icon = STATUS_ICONS[status] ?? <Clock className="w-3.5 h-3.5" />

  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium backdrop-blur-sm ${style}`}>
      {icon}
      {status}
    </span>
  )
}
