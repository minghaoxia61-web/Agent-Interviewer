// 共享 UI 原语（P3R 风格）：卡片 / 面板头 / 统计卡 / 分数徽章 / 分数环 / 维度条 / 空状态
function scoreTone(v) {
  if (v >= 8) return { text: 'text-emerald-300', bg: 'bg-emerald-500/10 border-emerald-500/40', fill: 'linear-gradient(90deg,#0ea36b,#5dffc0)' }
  if (v >= 6) return { text: 'text-sky-300', bg: 'bg-sky-500/10 border-sky-500/40', fill: 'linear-gradient(90deg,#1a72e8,#3fe0ff)' }
  if (v >= 4) return { text: 'text-amber-300', bg: 'bg-amber-500/10 border-amber-500/40', fill: 'linear-gradient(90deg,#b97e00,#ffd23f)' }
  return { text: 'text-rose-300', bg: 'bg-rose-500/10 border-rose-500/40', fill: 'linear-gradient(90deg,#b3123a,#ff3b5c)' }
}

export function Card({ className = '', style, children }) {
  return <div className={`card ${className}`} style={style}>{children}</div>
}

export function SectionTitle({ icon: Icon, title, desc, right }) {
  return (
    <div className="p-head">
      <div className="bar" />
      {Icon && <Icon className="w-4.5 h-4.5 text-indigo-300" />}
      <h3>{title}</h3>
      {desc && <span className="sub en">{desc}</span>}
      {right && <div className="right">{right}</div>}
    </div>
  )
}

export function StatCard({ icon: Icon, label, value, hint }) {
  return (
    <Card className="stat p-5 flex flex-col gap-1.5">
      {Icon && <Icon className="ico w-6 h-6" />}
      <p className="text-[11px] text-slate-500 tracking-wider">{label}</p>
      <p className="en text-3xl font-black text-white leading-none" style={{ textShadow: '0 0 20px rgba(63,224,255,.4)' }}>
        {value}
      </p>
      {hint && <p className="text-[10px] text-slate-500 opacity-80 truncate">{hint}</p>}
    </Card>
  )
}

export function ScoreChip({ value, suffix }) {
  if (value == null) return <span className="chip border-slate-700 text-slate-500">未评分</span>
  const t = scoreTone(value)
  return (
    <span className={`chip ${t.bg} ${t.text}`}>
      {value}{suffix || ''}
    </span>
  )
}

export function ScoreRing({ value, size = 120, label }) {
  const r = size / 2 - 10
  const c = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(100, value ?? 0)) / 100
  const id = `ring-${size}`
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#3fe0ff" /><stop offset="100%" stopColor="#1a72e8" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth="10" className="stroke-slate-900" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth="10" strokeLinecap="round"
          stroke={`url(#${id})`} strokeDasharray={`${c * pct} ${c}`}
          style={{ filter: 'drop-shadow(0 0 10px rgba(63,224,255,.7))', transition: 'stroke-dasharray .8s cubic-bezier(.2,.7,.3,1)' }} />
      </svg>
      <div className="absolute text-center">
        <p className="en text-3xl font-black text-white leading-none" style={{ textShadow: '0 0 22px rgba(63,224,255,.5)' }}>{value ?? '--'}</p>
        {label && <p className="text-[10px] text-slate-500 mt-1 tracking-wider">{label}</p>}
      </div>
    </div>
  )
}

export function DimBar({ label, value, max = 10 }) {
  const pct = Math.max(3, (value / max) * 100)
  const t = scoreTone(value)
  return (
    <div className="dim">
      <div className="flex justify-between text-xs mb-1.5">
        <span className="text-slate-400">{label}</span>
        <span className="en text-indigo-300 font-bold">{value}</span>
      </div>
      <div className="bar">
        <div className="fill" style={{ width: `${pct}%`, background: t.fill }} />
      </div>
    </div>
  )
}

export function EmptyState({ icon: Icon, title, desc, action }) {
  return (
    <Card className="p-12 flex flex-col items-center justify-center text-center">
      {Icon && <Icon className="w-12 h-12 text-slate-700 mb-4" />}
      <p className="text-slate-200 font-medium">{title}</p>
      {desc && <p className="text-sm text-slate-500 mt-1.5 max-w-sm">{desc}</p>}
      {action && <div className="mt-5">{action}</div>}
    </Card>
  )
}
