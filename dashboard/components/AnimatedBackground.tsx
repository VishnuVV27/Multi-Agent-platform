export default function AnimatedBackground() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full filter blur-3xl" />
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-emerald-500/10 rounded-full filter blur-3xl" />
      <div className="absolute top-1/3 right-1/3 w-72 h-72 bg-slate-500/10 rounded-full filter blur-3xl" />
    </div>
  )
}
