// 轻量 SVG 折线趋势图（默认 0-10 分制，max 可改，如 JD 匹配度 0-100）
const W = 640
const H = 190
const PAD = { l: 30, r: 16, t: 16, b: 26 }

export default function TrendChart({ points, max = 10 }) {
  const n = points.length
  const x = (i) => PAD.l + (n === 1 ? (W - PAD.l - PAD.r) / 2 : (i * (W - PAD.l - PAD.r)) / (n - 1))
  const y = (v) => PAD.t + (1 - v / max) * (H - PAD.t - PAD.b)
  const gridValues = Array.from({ length: 5 }, (_, i) => Math.round((max / 4) * i * 10) / 10)

  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i)},${y(p.value)}`).join(' ')
  const area = n > 1
    ? `${path} L${x(n - 1)},${H - PAD.b} L${x(0)},${H - PAD.b} Z`
    : ''

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-2xl mx-auto">
      {gridValues.map((g) => (
        <g key={g}>
          <line x1={PAD.l} y1={y(g)} x2={W - PAD.r} y2={y(g)}
            stroke="currentColor" className="text-slate-800" strokeWidth="1" />
          <text x={PAD.l - 6} y={y(g) + 3} textAnchor="end" fontSize="9" className="fill-slate-600">{g}</text>
        </g>
      ))}
      {n > 1 && <path d={area} className="fill-indigo-500/10" />}
      <path d={path} fill="none" stroke="currentColor" strokeWidth="2.5"
        strokeLinecap="round" strokeLinejoin="round" className="text-indigo-400"
        style={{ filter: 'drop-shadow(0 0 6px rgba(63,224,255,.8))' }} />
      {points.map((p, i) => (
        <g key={i}>
          <circle cx={x(i)} cy={y(p.value)} r="4" className="fill-indigo-300 stroke-slate-950" strokeWidth="2" />
          <text x={x(i)} y={y(p.value) - 10} textAnchor="middle" fontSize="10" className="fill-indigo-200 font-semibold">
            {p.value}
          </text>
          <text x={x(i)} y={H - 8} textAnchor="middle" fontSize="9" className="fill-slate-600">
            {p.label}
          </text>
        </g>
      ))}
    </svg>
  )
}
