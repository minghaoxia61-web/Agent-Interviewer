import { useEffect, useMemo, useState } from 'react'
import {
  Briefcase, Building2, Pencil, Plus, Trash2, X,
} from 'lucide-react'
import {
  createApplication, deleteApplication, getApplications, updateApplication,
} from '../api.js'
import { Card, StatCard } from './ui.jsx'

const COLS = [
  { key: 'wishlist', label: '想投', dot: '#9fd4f5' },
  { key: 'applied', label: '已投递', dot: '#3fe0ff' },
  { key: 'written_test', label: '笔试', dot: '#7aa8ff' },
  { key: 'interview', label: '面试', dot: '#1a72e8' },
  { key: 'offer', label: 'Offer', dot: '#5dffc0' },
  { key: 'rejected', label: '已挂', dot: '#ff8095' },
]
const COL_KEYS = COLS.map((c) => c.key)

const EMPTY_FORM = { company: '', position: '', status: 'wishlist', salary: '', link: '', notes: '' }

function relTime(ts) {
  if (!ts) return ''
  const diff = (Date.now() - new Date(ts).getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  return `${Math.floor(diff / 86400)} 天前`
}

export default function Board() {
  const [items, setItems] = useState(null)
  const [modal, setModal] = useState(null) // {mode:'create'|'edit', form}
  const [dragId, setDragId] = useState(null)
  const [error, setError] = useState('')

  async function load() {
    const data = await getApplications()
    setItems(data.items)
  }
  useEffect(() => { load().catch((e) => setError(e.message)) }, [])

  const grouped = useMemo(() => {
    const g = Object.fromEntries(COL_KEYS.map((k) => [k, []]))
    ;(items || []).forEach((it) => (g[it.status] || g.wishlist).push(it))
    return g
  }, [items])

  async function saveForm() {
    const f = modal.form
    if (!f.company.trim() || !f.position.trim()) { setError('公司和岗位不能为空'); return }
    setError('')
    try {
      if (modal.mode === 'create') await createApplication(f)
      else await updateApplication(modal.form.id, f)
      setModal(null)
      await load()
    } catch (e) { setError(e.message) }
  }

  async function moveTo(id, status) {
    try { await updateApplication(id, { status }); await load() } catch (e) { setError(e.message) }
  }

  async function remove(id) {
    if (!window.confirm('删除这条投递记录？')) return
    try { await deleteApplication(id); await load() } catch (e) { setError(e.message) }
  }

  const stats = useMemo(() => {
    const all = items || []
    return {
      total: all.length,
      active: all.filter((i) => ['applied', 'written_test', 'interview'].includes(i.status)).length,
      offers: all.filter((i) => i.status === 'offer').length,
      week: all.filter((i) => Date.now() - new Date(i.created_at).getTime() < 7 * 86400 * 1000).length,
    }
  }, [items])

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="page-title" style={{ marginBottom: 4 }}>
            <div>
              <div className="big" style={{ fontSize: 26 }}>投递看板</div>
              <div className="en2">Application Board</div>
            </div>
            <div className="ln" />
          </div>
          <p className="text-sm text-slate-500">管理投递进度：拖拽卡片换列，点击卡片编辑</p>
        </div>
        <button className="btn-primary" onClick={() => setModal({ mode: 'create', form: { ...EMPTY_FORM } })}>
          <Plus className="w-4 h-4" /> 添加投递
        </button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Briefcase} label="投递总数" value={stats.total} />
        <StatCard icon={Building2} label="进行中" value={stats.active} hint="投递 / 笔试 / 面试" />
        <StatCard icon={Briefcase} label="Offer 数" value={stats.offers} />
        <StatCard icon={Plus} label="近 7 天新增" value={stats.week} />
      </div>

      {error && <p className="text-sm text-rose-300">{error}</p>}

      <div className="relative">
        <div className="flex gap-3 overflow-x-auto chat-scroll pb-3 items-start">
        {COLS.map((col) => (
          <div key={col.key}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => { if (dragId) { moveTo(dragId, col.key); setDragId(null) } }}
            className="card shrink-0 w-64 p-3 min-h-[420px]" style={{ '--notch': '12px' }}>
            <div className="flex items-center gap-2 px-1 pb-2.5">
              <span className="w-2 h-2 rotate-45" style={{ background: col.dot, boxShadow: `0 0 8px ${col.dot}` }} />
              <p className="text-sm font-medium text-slate-300">{col.label}</p>
              <span className="text-xs text-slate-600">{grouped[col.key]?.length ?? 0}</span>
              <button
                className="ml-auto text-slate-600 hover:text-indigo-300"
                onClick={() => setModal({ mode: 'create', form: { ...EMPTY_FORM, status: col.key } })}>
                <Plus className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-2.5">
              {(grouped[col.key] || []).map((it) => (
                <div key={it.id}
                  draggable
                  onDragStart={() => setDragId(it.id)}
                  onDragEnd={() => setDragId(null)}
                  onClick={() => setModal({ mode: 'edit', form: { ...it } })}
                  style={{ clipPath: 'polygon(0 8px,8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%)' }}
                  className={`border bg-slate-900/80 p-3 cursor-grab active:cursor-grabbing transition-colors ${
                    dragId === it.id ? 'border-indigo-500/60 opacity-60' : 'border-indigo-500/20 hover:border-indigo-500/50'}`}>
                  <div className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-white truncate">{it.company}</p>
                      <p className="text-xs text-slate-400 truncate mt-0.5">{it.position}</p>
                    </div>
                    <button className="text-slate-600 hover:text-rose-300 shrink-0"
                      onClick={(e) => { e.stopPropagation(); remove(it.id) }}>
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  {it.salary && <p className="text-xs text-emerald-300/90 mt-1.5">{it.salary}</p>}
                  {it.notes && <p className="text-xs text-slate-500 mt-1.5 line-clamp-2 leading-relaxed">{it.notes}</p>}
                  <div className="flex items-center justify-between mt-2.5">
                    <span className="text-[10px] text-slate-600">{relTime(it.updated_at)}</span>
                    <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                      <select
                        value={it.status}
                        onChange={(e) => moveTo(it.id, e.target.value)}
                        className="bg-slate-800 border border-slate-700 rounded-md text-[11px] text-slate-300 px-1 py-0.5 outline-none cursor-pointer">
                        {COLS.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
                      </select>
                    </div>
                  </div>
                </div>
              ))}
              {(grouped[col.key] || []).length === 0 && (
                <p className="text-xs text-slate-700 text-center py-6">拖卡片到这里</p>
              )}
            </div>
          </div>
        ))}
        </div>
        <div className="pointer-events-none absolute inset-y-0 right-0 w-14 bg-gradient-to-l from-[#03102a] to-transparent" />
      </div>

      {/* 新建 / 编辑弹窗 */}
      {modal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setModal(null)}>
          <Card className="w-full max-w-md p-6" >
            <div className="flex items-center gap-2 mb-5">
              <Pencil className="w-4 h-4 text-indigo-300" />
              <p className="font-semibold text-white">{modal.mode === 'create' ? '添加投递' : '编辑投递'}</p>
              <button className="ml-auto text-slate-500 hover:text-white" onClick={() => setModal(null)}>
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-3.5" onClick={(e) => e.stopPropagation()}>
              <div className="grid grid-cols-2 gap-3">
                <input className="input" placeholder="公司 *"
                  value={modal.form.company}
                  onChange={(e) => setModal({ ...modal, form: { ...modal.form, company: e.target.value } })} />
                <input className="input" placeholder="岗位 *"
                  value={modal.form.position}
                  onChange={(e) => setModal({ ...modal, form: { ...modal.form, position: e.target.value } })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <select className="input" value={modal.form.status}
                  onChange={(e) => setModal({ ...modal, form: { ...modal.form, status: e.target.value } })}>
                  {COLS.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
                </select>
                <input className="input" placeholder="薪资范围（可选）"
                  value={modal.form.salary}
                  onChange={(e) => setModal({ ...modal, form: { ...modal.form, salary: e.target.value } })} />
              </div>
              <input className="input" placeholder="投递链接（可选）"
                value={modal.form.link}
                onChange={(e) => setModal({ ...modal, form: { ...modal.form, link: e.target.value } })} />
              <textarea className="input resize-none" rows={3} placeholder="备注：内推人 / 进展 / 面经（可选）"
                value={modal.form.notes}
                onChange={(e) => setModal({ ...modal, form: { ...modal.form, notes: e.target.value } })} />
              <div className="flex justify-end gap-2 pt-1">
                <button className="btn-ghost" onClick={() => setModal(null)}>取消</button>
                <button className="btn-primary" onClick={saveForm}>保存</button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
