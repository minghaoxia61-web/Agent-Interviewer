import { ArrowLeft, GitBranch } from 'lucide-react'
import { Card, SectionTitle } from './ui.jsx'

const STAGE_ORDER = [
  { key: 'project_probing', label: '项目深挖' },
  { key: 'tech_drill', label: '技术基础' },
  { key: 'stress_test', label: '压力测试' },
]
const REASON_TEXT = {
  answer_too_short: '回答过短', no_numbers: '缺少量化',
  hedge_words: '表述模糊', no_causal_chain: '因果链缺失',
}
const DECISION_META = {
  follow_up: { label: '追问', cls: 'border-rose-500/40 bg-rose-500/10 text-rose-300' },
  advance: { label: '推进', cls: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300' },
  advance_stage: { label: '进入下一阶段', cls: 'border-indigo-500/40 bg-indigo-500/10 text-indigo-300' },
}

function ChainCard({ chain }) {
  const dm = DECISION_META[chain.decision] || DECISION_META.advance
  return (
    <div className="card weak p-4 space-y-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="chip border-slate-700 text-slate-400">第 {chain.turn} 轮</span>
        <span className={`chip ${dm.cls}`}>{dm.label}{chain.decision === 'follow_up' ? ` ×${chain.depth}` : ''}</span>
        {chain.reasons.map((r) => (
          <span key={r} className="chip border-slate-700 bg-slate-800/60 text-slate-400">
            {REASON_TEXT[r] || r}
          </span>
        ))}
      </div>
      <p className="text-sm text-slate-200 leading-relaxed">
        <span className="text-indigo-300 font-semibold mr-1.5">问</span>{chain.question}
      </p>
      <p className="text-sm text-slate-400 leading-relaxed border-l-2 border-slate-700 pl-3">
        <span className="text-slate-300 font-semibold mr-1.5">答</span>{chain.answer}
      </p>
    </div>
  )
}

export default function ReviewView({ review, onBack }) {
  if (!review) {
    return (
      <Card className="p-10 text-center">
        <p className="text-slate-400">复盘数据加载中或不存在…</p>
        <button className="btn-ghost mt-4" onClick={onBack}>返回</button>
      </Card>
    )
  }
  const grouped = Object.fromEntries(STAGE_ORDER.map((s) => [s.key, []]))
  review.chains.forEach((c) => (grouped[c.stage] || grouped.project_probing).push(c))

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 flex-wrap">
        <button className="btn-ghost !px-3" onClick={onBack}><ArrowLeft className="w-4 h-4" /></button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <GitBranch className="w-6 h-6 text-indigo-300" /> 追问复盘
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {review.target_position} · 每一次「追问 or 推进」的决策与触发原因全程可回溯
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: '有效问答轮次', value: review.stats.turns },
          { label: '触发追问', value: review.stats.follow_ups },
          { label: '最大追问深度', value: review.stats.max_depth },
        ].map((s) => (
          <Card key={s.label} className="p-4 text-center">
            <p className="text-2xl font-bold text-white">{s.value}</p>
            <p className="text-xs text-slate-500 mt-1">{s.label}</p>
          </Card>
        ))}
      </div>

      {review.chains.length === 0 && (
        <Card className="p-10 text-center text-slate-500">这场面试还没有问答记录。</Card>
      )}

      {STAGE_ORDER.map(({ key, label }) => grouped[key].length > 0 && (
        <div key={key} className="space-y-3">
          <SectionTitle title={label} desc={`${grouped[key].length} 轮问答`} />
          {grouped[key].map((c, i) => <ChainCard key={i} chain={c} />)}
        </div>
      ))}

      <Card className="p-5 text-xs text-slate-500 leading-relaxed">
        决策由确定性规则驱动（app/core/rules.py）：回答过短 / 缺少量化 / 表述模糊 / 因果链缺失
        任一命中即触发追问，追问层数与推进时机全部记录在 Trace 轨迹中，可逐轮回溯验证。
      </Card>
    </div>
  )
}
