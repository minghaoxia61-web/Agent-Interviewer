import { useEffect, useState } from 'react'
import { ClipboardList, FileText, PlayCircle } from 'lucide-react'
import { getSessions } from '../api.js'
import { Card, EmptyState, ScoreChip, SectionTitle } from './ui.jsx'
import TrendChart from './TrendChart.jsx'

const STAGE_LABELS = {
  intro: '开场', project_probing: '项目深挖', tech_drill: '技术基础',
  stress_test: '压力测试', evaluation: '评估中', end: '已结束',
}

export default function Archive({ onView, onReview, onResume, go }) {
  const [sessions, setSessions] = useState(null)

  useEffect(() => { getSessions().then(setSessions).catch(() => {}) }, [])

  const trend = (sessions || [])
    .filter((s) => s.finished && s.overall != null)
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
    .map((s) => ({ label: s.created_at.slice(5, 10), value: s.overall }))

  return (
    <div className="space-y-6">
      <div className="page-title" style={{ marginBottom: 8 }}>
        <div>
          <div className="big">成长档案</div>
          <div className="en2">Growth Archive</div>
        </div>
        <div className="ln" />
      </div>
      <div>
        <p className="text-sm text-slate-500">每一次模拟面试都是一次可回溯的训练记录</p>
      </div>

      <Card className="p-6">
        <SectionTitle title="综合得分趋势" desc="横轴为面试日期（月/日）" />
        {trend.length === 0 ? (
          <p className="text-sm text-slate-500 py-8 text-center">
            完成第一场面试后，这里会出现你的成长曲线。
          </p>
        ) : (
          <TrendChart points={trend} />
        )}
      </Card>

      <div>
        <SectionTitle icon={ClipboardList} title={`全部会话（${sessions?.length ?? 0}）`} />
        {sessions && sessions.length === 0 && (
          <EmptyState icon={FileText} title="暂无档案"
            desc="去简历诊断上传第一份简历，开启训练之旅。"
            action={<button className="btn-primary" onClick={() => go('diagnosis')}>去上传</button>} />
        )}
        <div className="space-y-2.5">
          {(sessions || []).map((s) => (
            <Card key={s.id} className="p-4.5 px-5 flex flex-wrap items-center gap-3 hover:border-indigo-500/30 transition-colors">
              <div className="min-w-0 flex-1 basis-48">
                <p className="text-sm text-white font-medium truncate">
                  {s.target_position || '未指定岗位'} · {s.resume_name || '未署名'}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {s.created_at.replace('T', ' ')} · {s.total_turns} 轮 ·
                  {s.finished ? ` 已结束（${STAGE_LABELS[s.stage] || s.stage}）` : ` 进行中（${STAGE_LABELS[s.stage] || s.stage}）`}
                </p>
              </div>
              {s.diagnosis_overall != null && (
                <span className="chip border-sky-500/30 bg-sky-500/10 text-sky-300">简历 {s.diagnosis_overall}</span>
              )}
              {s.finished
                ? <ScoreChip value={s.overall} suffix=" / 10" />
                : <span className="chip border-indigo-500/30 bg-indigo-500/10 text-indigo-300">进行中</span>}
              <div className="flex gap-2">
                {s.total_turns > 0 && (
                  <button className="btn-ghost !px-3 !py-1.5 text-xs" onClick={() => onReview(s.id)}>
                    <GitBranch className="w-3.5 h-3.5" /> 复盘
                  </button>
                )}
                {s.finished
                  ? <button className="btn-ghost !px-3 !py-1.5 text-xs" onClick={() => onView(s.id)}>
                      <FileText className="w-3.5 h-3.5" /> 查看报告
                    </button>
                  : <button className="btn-primary !px-3 !py-1.5 text-xs" onClick={() => onResume(s)}>
                      <PlayCircle className="w-3.5 h-3.5" /> 继续面试
                    </button>}
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}
