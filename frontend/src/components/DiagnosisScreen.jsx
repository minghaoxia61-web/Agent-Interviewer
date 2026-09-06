import { useEffect, useRef, useState } from 'react'
import {
  AlertCircle, ArrowRight, FileText, Loader2, ShieldCheck, Target, UploadCloud,
} from 'lucide-react'
import { getAnalysis, matchJd, uploadResume } from '../api.js'
import { Card, DimBar, ScoreChip, ScoreRing, SectionTitle } from './ui.jsx'
import TrendChart from './TrendChart.jsx'

const DIM_LABELS = {
  quantified: '量化程度', project_depth: '项目深度', keyword_match: '岗位匹配',
  clarity: '表述清晰', completeness: '信息完整',
}
const WEAK_META = {
  magic_number: { label: '数字存疑', color: 'bg-rose-500/15 text-rose-300 border-rose-500/30' },
  vague_scope: { label: '职责模糊', color: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
  buzzword_stack: { label: '名词堆砌', color: 'bg-sky-500/15 text-sky-300 border-sky-500/30' },
  missing_metric: { label: '缺少度量', color: 'bg-violet-500/15 text-violet-300 border-violet-500/30' },
}

export default function DiagnosisScreen({ onUploaded, go }) {
  const [file, setFile] = useState(null)
  const [position, setPosition] = useState('后端开发工程师')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const inputRef = useRef(null)
  // JD 对比诊断
  const [jdText, setJdText] = useState('')
  const [jdLoading, setJdLoading] = useState(false)
  const [jdError, setJdError] = useState('')
  const [jdResult, setJdResult] = useState(null)

  async function runJdMatch() {
    if (!jdText.trim() || jdLoading) return
    setJdLoading(true)
    setJdError('')
    try {
      setJdResult(await matchJd(result.session_id, jdText))
    } catch (e) {
      setJdError(e.message)
    } finally {
      setJdLoading(false)
    }
  }

  async function doUpload(f) {
    setLoading(true)
    setError('')
    try {
      const data = await uploadResume(f, position)
      setResult(data)
      onUploaded(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function onPick(f) {
    if (!f) return
    setFile(f)
    doUpload(f)
  }

  // 后台分析轮询：挖掘与诊断并行执行完成后自动刷新结果
  useEffect(() => {
    if (!result || result.analysis_status !== 'processing') return
    const timer = setInterval(async () => {
      try {
        const a = await getAnalysis(result.session_id)
        if (a.analysis_status !== 'processing') {
          setResult((prev) => ({ ...prev, ...a }))
        }
      } catch { /* 网络抖动时继续轮询 */ }
    }, 2500)
    return () => clearInterval(timer)
  }, [result?.session_id, result?.analysis_status])

  return (
    <div className="space-y-6">
      <div className="page-title" style={{ marginBottom: 8 }}>
        <div>
          <div className="big">简历诊断</div>
          <div className="en2">Resume Diagnosis</div>
        </div>
        <div className="ln" />
      </div>
      <div>
        <p className="text-sm text-slate-500">
          上传简历 → 结构化解析 → 五维体检打分 → 挖出最容易被面试官抓住的 3 个疑点
        </p>
      </div>

      {!result ? (
        <Card className="p-7">
          <label
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); onPick(e.dataTransfer.files?.[0]) }}
            className="dropzone flex flex-col items-center justify-center gap-3 border-2 border-dashed border-indigo-500/30 hover:border-indigo-400/60 py-14 cursor-pointer transition-colors"
          >
            <input ref={inputRef} type="file" className="hidden" accept=".pdf,.txt,.md"
              onChange={(e) => onPick(e.target.files?.[0])} />
            {loading ? (
              <>
                <Loader2 className="w-10 h-10 text-indigo-400 animate-spin" />
                <p className="text-slate-300">正在解析简历、体检打分、挖掘疑点…</p>
              </>
            ) : (
              <>
                <UploadCloud className="w-10 h-10 text-slate-500" />
                <p className="text-slate-300">点击或拖拽上传简历</p>
                <p className="text-xs text-slate-500">支持 PDF / TXT / Markdown，10MB 以内</p>
              </>
            )}
          </label>

          <div className="mt-5 flex flex-col sm:flex-row sm:items-center gap-3">
            <label className="text-sm text-slate-400 whitespace-nowrap">目标岗位</label>
            <input value={position} onChange={(e) => setPosition(e.target.value)}
              placeholder="如：后端开发工程师 / 前端 / 算法"
              className="input flex-1" />
          </div>

          {error && (
            <div className="mt-4 flex items-center gap-2 text-sm text-rose-300 bg-rose-500/10 border border-rose-500/30 rounded-xl px-3.5 py-2.5">
              <AlertCircle className="w-4 h-4" /> {error}
            </div>
          )}
          {file && !loading && !error && (
            <p className="mt-4 flex items-center gap-2 text-sm text-slate-400">
              <FileText className="w-4 h-4" /> {file.name}
            </p>
          )}
        </Card>
      ) : (
        <>
          {result.analysis_status === 'processing' ? (
            <Card className="p-12 flex flex-col items-center text-center">
              <Loader2 className="w-10 h-10 text-indigo-400 animate-spin mb-4" />
              <p className="text-slate-200 font-medium">AI 正在并行执行漏洞挖掘与体检诊断…</p>
              <p className="text-xs text-slate-500 mt-2">
                真实 LLM 模式约需 15~40 秒，完成后自动展示结果。此页面可以随时离开，分析在后台继续。
              </p>
            </Card>
          ) : result.analysis_status === 'failed' ? (
            <Card className="p-12 text-center">
              <AlertCircle className="w-10 h-10 text-rose-400 mx-auto mb-3" />
              <p className="text-slate-200 font-medium">分析失败：{result.analysis_error || '未知错误'}</p>
              <button className="btn-ghost mt-4" onClick={() => setResult(null)}>重新上传</button>
            </Card>
          ) : (
          <>
          {/* 体检总览 */}
          <Card className="p-6 lg:p-7">
            <SectionTitle icon={ShieldCheck} title="简历体检报告"
              desc={`解析模式：${result.parse_mode === 'llm' ? 'LLM' : '规则'} · 诊断模式：${result.diagnosis.mode === 'llm' ? 'LLM' : '确定性规则'} · 文件：${result.filename || '—'}`} />
            <div className="flex flex-col lg:flex-row items-center gap-8">
              <div className="flex flex-col items-center">
                <ScoreRing value={result.diagnosis.overall} size={132} label="简历竞争力 / 100" />
                <p className="text-xs text-slate-400 mt-3 max-w-[220px] text-center leading-relaxed">
                  {result.diagnosis.comment}
                </p>
              </div>
              <div className="flex-1 w-full space-y-4">
                {Object.entries(DIM_LABELS).map(([key, label]) => (
                  <DimBar key={key} label={label} value={result.diagnosis.scores?.[key] ?? 0} />
                ))}
              </div>
            </div>
          </Card>

          {/* 漏洞疑点 */}
          <Card className="p-6 lg:p-7">
            <SectionTitle title={`待深挖疑点（${result.weaknesses.length}）`}
              desc="这些是面试官最可能盯住不放的地方" />
            <ul className="space-y-3">
              {result.weaknesses.map((w, i) => {
                const meta = WEAK_META[w.dimension] || WEAK_META.vague_scope
                return (
                  <li key={i} className="card weak p-4">
                    <span className={`chip ${meta.color}`}>{meta.label}</span>
                    <p className="mt-2 text-sm text-slate-200">「{w.quote}」</p>
                    <p className="mt-1.5 text-xs text-slate-400 leading-relaxed">{w.reason}</p>
                  </li>
                )
              })}
            </ul>
          </Card>

          {/* 优化建议 */}
          <Card className="p-6 lg:p-7">
            <SectionTitle title="优化建议" desc="按建议打磨后，再来一场模拟面试检验" />
            <ul className="space-y-3">
              {result.diagnosis.suggestions?.map((s, i) => (
                <li key={i} className="flex gap-3">
                  <span className="shrink-0 w-6 h-6 rounded-lg bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 text-xs flex items-center justify-center font-bold mt-0.5">
                    {i + 1}
                  </span>
                  <p className="text-sm text-slate-300 leading-relaxed">{s.text}</p>
                </li>
              ))}
            </ul>
            <button className="btn-primary mt-6 w-full sm:w-auto" onClick={() => go('interview')}>
              带着这些疑点开始模拟面试 <ArrowRight className="w-4 h-4" />
            </button>
          </Card>
          </>
          )}

          {/* JD 对比诊断（resume 解析完成即可用，无需等待后台分析） */}
          <Card className="p-6 lg:p-7">
            <SectionTitle icon={Target} title="JD 匹配度分析"
              desc="粘贴目标岗位的 JD 描述，对比简历计算关键词覆盖率与差距" />
            <textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              rows={5}
              placeholder="把招聘 JD 全文粘贴到这里：岗位职责、任职要求…"
              className="input w-full resize-none" />
            <div className="flex items-center gap-3 mt-3">
              <button className="btn-primary" onClick={runJdMatch} disabled={jdLoading || !jdText.trim()}>
                {jdLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Target className="w-4 h-4" />}
                {jdLoading ? '分析中…' : '分析匹配度'}
              </button>
              {jdError && <p className="text-sm text-rose-300">{jdError}</p>}
            </div>

            {jdResult && (
              <div className="mt-6 space-y-5 rise">
                <div className="flex items-center gap-6 flex-wrap">
                  <ScoreRing value={jdResult.match_score} size={110} label="JD 匹配度 / 100" />
                  <div className="flex-1 min-w-56">
                    <p className="text-sm text-slate-300 leading-relaxed">{jdResult.summary}</p>
                    <p className="text-xs text-slate-500 mt-2">
                      共识别 {jdResult.keywords_total} 个关键词 · 命中 {jdResult.matched.length} · 缺失 {jdResult.missing.length}
                      （模式：{jdResult.mode === 'llm' ? 'LLM' : jdResult.mode === 'deterministic' ? '规则' : 'Mock'}）
                    </p>
                  </div>
                </div>
                {jdResult.history && jdResult.history.length > 1 && (
                  <div className="mt-4">
                    <p className="text-xs font-semibold text-slate-400 mb-1">匹配度趋势（按分析时间）</p>
                    <TrendChart points={jdResult.history.map((h, i) => ({
                      label: (h.ts || '').slice(11, 16) || `#${i + 1}`,
                      value: h.match_score,
                    }))} max={100} />
                  </div>
                )}
                <div className="grid md:grid-cols-2 gap-4">
                  <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4">
                    <p className="text-xs font-semibold text-emerald-300 mb-2.5">✓ 已体现（{jdResult.matched.length}）</p>
                    <div className="flex flex-wrap gap-1.5">
                      {jdResult.matched.map((k) => (
                        <span key={k} className="chip border-emerald-500/30 bg-emerald-500/10 text-emerald-300">{k}</span>
                      ))}
                      {jdResult.matched.length === 0 && <span className="text-xs text-slate-600">无</span>}
                    </div>
                  </div>
                  <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4">
                    <p className="text-xs font-semibold text-rose-300 mb-2.5">✗ 缺失（{jdResult.missing.length}）</p>
                    <div className="flex flex-wrap gap-1.5">
                      {jdResult.missing.map((k) => (
                        <span key={k} className="chip border-rose-500/30 bg-rose-500/10 text-rose-300">{k}</span>
                      ))}
                      {jdResult.missing.length === 0 && <span className="text-xs text-slate-600">无</span>}
                    </div>
                  </div>
                </div>
                <ul className="space-y-2.5">
                  {jdResult.suggestions?.map((s, i) => (
                    <li key={i} className="flex gap-3">
                      <span className="shrink-0 chip border-amber-500/30 bg-amber-500/10 text-amber-300 h-fit">{s.keyword}</span>
                      <p className="text-sm text-slate-300 leading-relaxed">{s.text}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
