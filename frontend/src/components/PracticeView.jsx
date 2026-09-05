import { useEffect, useState } from 'react'
import {
  CheckCircle2, Dumbbell, GraduationCap, History, Loader2, SendHorizonal, XCircle,
} from 'lucide-react'
import { getPractice, getPracticeHistory, startPractice, submitPracticeAnswer } from '../api.js'
import { Card, SectionTitle, ScoreRing } from './ui.jsx'

const AVG = (arr) => arr.length ? Math.round((arr.reduce((a, b) => a + b, 0) / arr.length) * 10) / 10 : null

export default function PracticeView() {
  const [history, setHistory] = useState(null)
  const [active, setActive] = useState(null) // {id, items, finished}
  const [category, setCategory] = useState('不限')
  const [count, setCount] = useState(5)
  const [starting, setStarting] = useState(false)
  const [answer, setAnswer] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [lastFeedback, setLastFeedback] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { getPracticeHistory().then(setHistory).catch(() => {}) }, [])

  const items = active?.items || []
  const idx = items.findIndex((it) => it.answer === null || it.answer === undefined)
  const current = idx >= 0 ? items[idx] : null
  const answered = items.filter((it) => it.score !== null && it.score !== undefined)

  async function start() {
    setStarting(true)
    setError('')
    try {
      const d = await startPractice(category === '不限' ? null : category, null, count)
      const full = await getPractice(d.practice_id)
      setActive({ id: d.practice_id, ...full })
      setLastFeedback(null)
      setAnswer('')
    } catch (e) {
      setError(e.message)
    } finally {
      setStarting(false)
    }
  }

  async function submit() {
    if (!answer.trim() || submitting || !current) return
    setSubmitting(true)
    setError('')
    try {
      const d = await submitPracticeAnswer(active.id, answer.trim())
      setLastFeedback({ ...d, question: current.question })
      setAnswer('')
      const full = await getPractice(active.id)
      setActive({ id: active.id, ...full })
      if (d.finished) getPracticeHistory().then(setHistory).catch(() => {})
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="page-title" style={{ marginBottom: 8 }}>
        <div>
          <div className="big">刷题练习</div>
          <div className="en2">Question Drills</div>
        </div>
        <div className="ln" />
      </div>
      <p className="text-sm text-slate-500">选一组大厂真题逐题作答，AI 教练批改打分并给出参考要点。</p>

      {/* 开始新练习 */}
      {!active && (
        <Card className="p-6">
          <SectionTitle icon={GraduationCap} title="开始一组练习" />
          <div className="flex flex-col sm:flex-row gap-3">
            <select value={category} onChange={(e) => setCategory(e.target.value)} className="input flex-1">
              <option value="不限">分类：不限</option>
              {['Redis', 'MySQL', '操作系统', '网络', 'Python', 'Go', '系统设计', '消息队列',
                '分布式', '缓存', '安全', '架构', '容器化', '接口设计', '性能优化', '数据库'].map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <select value={count} onChange={(e) => setCount(Number(e.target.value))} className="input">
              {[3, 5, 8].map((n) => <option key={n} value={n}>{n} 题</option>)}
            </select>
            <button className="btn-primary" onClick={start} disabled={starting}>
              {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Dumbbell className="w-4 h-4" />} 开始
            </button>
          </div>
        </Card>
      )}

      {/* 进行中的练习 */}
      {active && !active.finished && current && (
        <Card className="p-6 space-y-4">
          <div className="flex items-center gap-3">
            <p className="text-sm font-semibold text-white">第 {idx + 1} / {items.length} 题</p>
            <span className="chip border-slate-700 text-slate-400">{current.qid}</span>
          </div>
          <p className="text-base text-slate-100 leading-relaxed">{current.question}</p>
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            rows={6}
            placeholder="像真实面试一样组织你的回答：先结论，再展开，带数字和权衡…"
            className="input w-full resize-none" />
          <div className="flex justify-end">
            <button className="btn-primary" onClick={submit}
              disabled={submitting || !answer.trim()}>
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <SendHorizonal className="w-4 h-4" />}
              提交回答
            </button>
          </div>
          {lastFeedback && (
            <div className="rise space-y-3 border-t border-slate-800 pt-4">
              <div className="flex items-center gap-4">
                <ScoreRing value={lastFeedback.score * 10} size={84} label="本题 / 100" />
                <div className="flex-1 space-y-1 text-sm">
                  {lastFeedback.feedback.strengths.map((s, i) => (
                    <p key={i} className="text-emerald-300 flex gap-1.5"><CheckCircle2 className="w-4 h-4 shrink-0" />{s}</p>
                  ))}
                  {lastFeedback.feedback.gaps.map((g, i) => (
                    <p key={i} className="text-rose-300 flex gap-1.5"><XCircle className="w-4 h-4 shrink-0" />{g}</p>
                  ))}
                </div>
              </div>
              {lastFeedback.feedback.reference?.length > 0 && (
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4">
                  <p className="text-xs font-semibold text-indigo-300 mb-2">参考回答要点</p>
                  <ul className="list-disc pl-5 space-y-1 text-sm text-slate-300">
                    {lastFeedback.feedback.reference.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {/* 完成总结 */}
      {active && active.finished && (
        <Card className="p-6 space-y-4">
          <SectionTitle icon={CheckCircle2} title="本组练习完成"
            desc={`平均 ${AVG(answered.map((i) => i.score)) ?? '—'} / 10`} />
          <div className="space-y-2">
            {items.map((it, i) => (
              <div key={i} className="flex items-center gap-3 text-sm">
                <span className={`font-bold w-10 ${it.score >= 7 ? 'text-emerald-300' : it.score >= 5 ? 'text-amber-300' : 'text-rose-300'}`}>
                  {it.score}
                </span>
                <span className="flex-1 text-slate-300 truncate">{it.question}</span>
              </div>
            ))}
          </div>
          <button className="btn-primary" onClick={() => { setActive(null); setLastFeedback(null) }}>
            <Dumbbell className="w-4 h-4" /> 再来一组
          </button>
        </Card>
      )}

      {/* 练习历史 */}
      <Card className="p-6">
        <SectionTitle icon={History} title="练习记录" />
        {history && history.length === 0 && (
          <p className="text-sm text-slate-500 py-4 text-center">还没有练习记录，开始第一组吧。</p>
        )}
        <div className="space-y-2">
          {(history || []).map((h) => (
            <div key={h.id} className="flex items-center gap-3 text-sm px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-800">
              <span className="text-slate-300">{h.created_at.replace('T', ' ')}</span>
              <span className="text-slate-500">{h.answered}/{h.count} 题</span>
              {h.avg_score != null && <span className="ml-auto font-semibold text-indigo-300">均分 {h.avg_score}</span>}
            </div>
          ))}
        </div>
      </Card>

      {error && <p className="text-sm text-rose-300">{error}</p>}
    </div>
  )
}
