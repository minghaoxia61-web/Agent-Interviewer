import { useMemo } from 'react'
import { marked } from 'marked'
import { ArrowLeft, Award, RotateCcw, Target } from 'lucide-react'
import RadarChart from './RadarChart.jsx'
import { Card, ScoreChip, SectionTitle } from './ui.jsx'

export default function ReportScreen({ report, onBack, onRestart }) {
  const html = useMemo(() => marked.parse(report.markdown || ''), [report.markdown])

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button className="btn-ghost !px-3" onClick={onBack}><ArrowLeft className="w-4 h-4" /></button>
        <div className="flex-1 min-w-0">
          <div className="page-title" style={{ marginBottom: 4 }}>
            <Award className="w-6 h-6 text-emerald-300 mb-1" />
            <div>
              <div className="big" style={{ fontSize: 26 }}>面试评估报告</div>
              <div className="en2">Evaluation Report</div>
            </div>
            <div className="ln" />
          </div>
          <p className="text-sm text-slate-500 mt-1">
            会话 {report.session_id} · 综合得分 <ScoreChip value={report.overall} suffix=" / 10" />
          </p>
        </div>
        <button className="btn-primary" onClick={onRestart}><RotateCcw className="w-4 h-4" /> 再战一场</button>
      </div>

      <div className="grid lg:grid-cols-[1fr_1.2fr] gap-6 items-stretch">
        <Card className="p-6">
          <SectionTitle icon={Target} title="五维雷达图" desc="技术深度 / 逻辑严谨 / 工程素养 / 沟通表达 / 抗压应变" />
          <RadarChart dims={report.scores} />
          <div className="grid grid-cols-5 gap-2 mt-3">
            {report.scores.map((s) => (
              <div key={s.key} className="text-center">
                <ScoreChip value={s.score} />
                <p className="text-[11px] text-slate-500 mt-1.5">{s.label}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-6 flex flex-col">
          <SectionTitle title="总评" desc="LLM-as-a-Judge 基于完整轨迹给出" />
          <p className="text-sm text-slate-300 leading-relaxed">{report.summary || '（无）'}</p>
          <div className="mt-auto pt-4 text-xs text-slate-600 leading-relaxed">
            本报告的每一分都可在 Trace 轨迹中回溯验证；追问判定由确定性规则驱动，代码位于 app/core/rules.py。
          </div>
        </Card>
      </div>

      <Card className="p-6 lg:p-7">
        <div className="report-body" dangerouslySetInnerHTML={{ __html: html }} />
      </Card>
    </div>
  )
}
