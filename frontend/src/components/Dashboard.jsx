import { useEffect, useState } from 'react'
import {
  ArrowRight, Award, BrainCircuit, FileSearch, Flame, Library,
  PlayCircle, Swords, TrendingUp, Zap,
} from 'lucide-react'
import { getDashboard } from '../api.js'
import { Card, EmptyState, SectionTitle, ScoreChip, StatCard } from './ui.jsx'

const MODULES = [
  { key: 'diagnosis', icon: FileSearch, title: '简历诊断', desc: 'AI 体检打分 + 漏洞挖掘，给简历开药方' },
  { key: 'interview', icon: Swords, title: '模拟面试', desc: 'LangGraph 驱动的动态追问，打破砂锅问到底' },
  { key: 'questions', icon: Library, title: '真题题库', desc: '字节 / 腾讯等大厂面经，按分类检索' },
  { key: 'archive', icon: TrendingUp, title: '成长档案', desc: '历次评估报告与五维分数趋势' },
]

export default function Dashboard({ go, onResume, llmMode }) {
  const [data, setData] = useState(null)

  useEffect(() => { getDashboard().then(setData).catch(() => {}) }, [])

  const hour = new Date().getHours()
  const greet = hour < 6 ? '夜深了' : hour < 12 ? '早上好' : hour < 18 ? '下午好' : '晚上好'

  return (
    <div className="space-y-6">
      {/* Hero */}
      <Card className="hero p-6 sm:p-8 lg:p-10">
        <div className="hero-art" />
        <div className="relative">
          <p className="kicker en"><span className="dot" /> AI-Powered Career Training</p>
          <h1>{greet}，<em>今天为 Offer</em><br className="hidden sm:block" />做了什么准备？</h1>
          <p className="text-slate-400 mt-2 max-w-xl text-sm leading-relaxed">
            上传简历做一次体检，再让面试官对着你简历里最可疑的三处发起追问——
            每一次追问都有据可查，每一份报告都能看见成长。
          </p>
          <div className="flex flex-wrap gap-3 mt-6">
            <button className="btn-primary" onClick={() => go('diagnosis')}>
              <FileSearch className="w-4 h-4" /> 上传简历开始诊断 <span className="en text-[10px] opacity-70 tracking-widest">START</span>
            </button>
            {data?.unfinished && (
              <button className="btn-ghost" onClick={() => onResume(data.unfinished)}>
                <PlayCircle className="w-4 h-4 text-emerald-300" />
                继续上次面试（{data.unfinished.target_position}）
              </button>
            )}
          </div>
        </div>
      </Card>

      {/* 数据统计 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Swords} label="模拟面试场次" value={data ? data.session_count : '—'}
          hint={data ? `${data.finished_count} 场已完成` : ''} />
        <StatCard icon={Award} label="平均综合得分" value={data?.avg_score ?? '—'} hint="满分 10" />
        <StatCard icon={Flame} label="历史最佳" value={data?.best_score ?? '—'} hint="超越 80 分即达大厂通过线" />
        <StatCard icon={Library} label="题库真题" value={data ? data.question_count : '—'}
          hint={data?.llm_mode === 'real' ? `引擎：${data.llm_model}` : '引擎：Mock 演示模式'} />
      </div>

      {/* 模块入口 */}
      <div>
        <SectionTitle icon={BrainCircuit} title="功能模块" desc="Modules" />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {MODULES.map(({ key, icon: Icon, title, desc }) => (
            <Card key={key} className="mod p-5 text-left" style={{ cursor: 'pointer' }}>
              <div onClick={() => go(key)}>
                <div className="mod-ico"><Icon className="w-6 h-6" /></div>
                <p className="font-bold text-white">{title}</p>
                <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{desc}</p>
                <ArrowRight className="w-4 h-4 text-indigo-300 opacity-60 mt-3" />
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* 最近面试 */}
      <div>
        <SectionTitle icon={TrendingUp} title="最近面试" desc="Recent"
          right={<button className="text-xs text-indigo-300 hover:text-indigo-200" onClick={() => go('archive')}>全部档案 →</button>} />
        {data && data.recent.length === 0 && (
          <EmptyState icon={Swords} title="还没有面试记录"
            desc="上传简历并完成第一场模拟面试后，这里会展示你的评估轨迹。"
            action={<button className="btn-primary" onClick={() => go('diagnosis')}>从简历诊断开始</button>} />
        )}
        <Card className="py-1.5" style={{ '--notch': '10px' }}>
          {data?.recent?.map((s) => (
            <div key={s.id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-indigo-500/5 transition-colors">
              <div className="min-w-0 flex-1">
                <p className="text-sm text-white font-medium truncate">
                  {s.target_position || '未指定岗位'} · {s.resume_name || '未署名'}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {s.created_at.replace('T', ' ')} · {s.total_turns} 轮对话 · 挖出 {s.weakness_count} 个疑点
                </p>
              </div>
              {s.finished
                ? <ScoreChip value={s.overall} suffix=" / 10" />
                : <span className="chip border-indigo-500/40 bg-indigo-500/10 text-indigo-300">进行中</span>}
              <button className="btn-ghost !px-3 !py-1.5 text-xs" onClick={() => onResume(s)}>
                {s.finished ? '再战一场' : '继续'}
              </button>
            </div>
          ))}
        </Card>
      </div>
    </div>
  )
}
