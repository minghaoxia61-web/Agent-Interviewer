import { useEffect, useMemo, useState } from 'react'
import { Building2, Search, Tags } from 'lucide-react'
import { getQuestions } from '../api.js'
import { Card, EmptyState, SectionTitle } from './ui.jsx'

export default function QuestionBank() {
  const [data, setData] = useState(null)
  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [company, setCompany] = useState('')

  useEffect(() => { getQuestions().then(setData).catch(() => {}) }, [])

  const items = useMemo(() => {
    if (!data) return []
    const needle = q.trim().toLowerCase()
    return data.items.filter((it) => {
      if (category && it.category !== category) return false
      if (company && it.company !== company) return false
      if (needle && !(it.question.toLowerCase().includes(needle)
        || it.keywords.some((k) => k.toLowerCase().includes(needle)))) return false
      return true
    })
  }, [data, q, category, company])

  return (
    <div className="space-y-6">
      <div className="page-title" style={{ marginBottom: 8 }}>
        <div>
          <div className="big">真题题库</div>
          <div className="en2">Question Bank</div>
        </div>
        <div className="ln" />
      </div>
      <div>
        <p className="text-sm text-slate-500">
          大厂面经真题库，也是模拟面试「技术基础」环节的题目来源（RAG 检索）
        </p>
      </div>

      <Card className="p-5 space-y-4">
        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="搜索题目或关键词，如：Redis / 索引 / 限流"
            className="input w-full !pl-10" />
        </div>
        <div className="flex flex-wrap gap-1.5">
          <button onClick={() => setCategory('')}
            className={`chip ${!category ? 'border-indigo-500/40 bg-indigo-500/15 text-indigo-200' : 'border-slate-700 text-slate-400'}`}>
            全部分类
          </button>
          {data?.categories?.map((c) => (
            <button key={c} onClick={() => setCategory(category === c ? '' : c)}
              className={`chip ${category === c ? 'border-indigo-500/40 bg-indigo-500/15 text-indigo-200' : 'border-slate-700 text-slate-400'}`}>
              {c}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-1.5 items-center">
          <Building2 className="w-3.5 h-3.5 text-slate-600" />
          {data?.companies?.map((cName) => (
            <button key={cName} onClick={() => setCompany(company === cName ? '' : cName)}
              className={`chip ${company === cName ? 'border-fuchsia-500/40 bg-fuchsia-500/15 text-fuchsia-200' : 'border-slate-700 text-slate-400'}`}>
              {cName}
            </button>
          ))}
          <span className="ml-auto text-xs text-slate-500">命中 {items.length} / {data?.total ?? 0} 题</span>
        </div>
      </Card>

      {items.length === 0 ? (
        <EmptyState icon={Search} title="没有匹配的题目" desc="换个关键词或清空筛选条件试试。" />
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {items.map((it) => (
            <Card key={it.id} className="p-5 hover:border-indigo-500/30 transition-colors">
              <div className="flex items-center gap-2 mb-2.5">
                <span className="chip border-fuchsia-500/30 bg-fuchsia-500/10 text-fuchsia-300">{it.company}</span>
                <span className="chip border-slate-700 text-slate-400"><Tags className="w-3 h-3 inline mr-1 -mt-0.5" />{it.category}</span>
              </div>
              <p className="text-sm text-slate-200 leading-relaxed">{it.question}</p>
              <div className="flex flex-wrap gap-1.5 mt-3">
                {it.keywords.map((k) => (
                  <span key={k} className="text-[11px] px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-500">{k}</span>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
