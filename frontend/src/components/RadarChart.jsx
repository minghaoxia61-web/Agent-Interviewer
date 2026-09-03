// 轻量 SVG 雷达图（零依赖，Phase 2 可换 ECharts）
const SIZE = 320
const CENTER = SIZE / 2
const RADIUS = 110

function pointAt(index, total, value) {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2
  const r = (RADIUS * value) / 10
  return [CENTER + r * Math.cos(angle), CENTER + r * Math.sin(angle)]
}

function polygon(values, total) {
  return values.map((v, i) => pointAt(i, total, v).join(',')).join(' ')
}

export default function RadarChart({ dims }) {
  const total = dims.length
  const rings = [2, 4, 6, 8, 10]
  const scores = dims.map((d) => Math.max(0.2, d.score))
  const labels = dims.map((d) => {
    const [x, y] = pointAt(dims.indexOf(d), total, 12.6)
    return { x, y, label: d.label, score: d.score }
  })

  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="w-full max-w-sm mx-auto">
      {rings.map((ring) => (
        <polygon
          key={ring}
          points={polygon(Array(total).fill(ring), total)}
          fill="none"
          stroke="currentColor"
          className="text-slate-700"
          strokeWidth="1"
        />
      ))}
      {dims.map((_, i) => {
        const [x, y] = pointAt(i, total, 10)
        return (
          <line key={i} x1={CENTER} y1={CENTER} x2={x} y2={y}
            stroke="currentColor" className="text-slate-700" strokeWidth="1" />
        )
      })}
      <polygon
        points={polygon(scores, total)}
        className="fill-indigo-500/30 stroke-indigo-400"
        strokeWidth="2"
      />
      {scores.map((v, i) => {
        const [x, y] = pointAt(i, total, v)
        return <circle key={i} cx={x} cy={y} r="3.5" className="fill-indigo-300" />
      })}
      {labels.map((l, i) => (
        <g key={i}>
          <text x={l.x} y={l.y - 6} textAnchor="middle" className="fill-slate-300" fontSize="13">
            {l.label}
          </text>
          <text x={l.x} y={l.y + 10} textAnchor="middle" className="fill-indigo-300 font-semibold" fontSize="13">
            {l.score}
          </text>
        </g>
      ))}
    </svg>
  )
}
