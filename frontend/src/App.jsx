import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import {
  Briefcase, Columns3, FileSearch, LayoutDashboard, Library, Swords, TrendingUp,
} from 'lucide-react'
import { getSessionState, setApiToken } from './api.js'
import Dashboard from './components/Dashboard.jsx'
import DiagnosisScreen from './components/DiagnosisScreen.jsx'
import ChatScreen from './components/ChatScreen.jsx'
import QuestionBank from './components/QuestionBank.jsx'
import Board from './components/Board.jsx'
import Archive from './components/Archive.jsx'
import ReportScreen from './components/ReportScreen.jsx'
import P3RBackground from './components/P3RBackground.jsx'
import { EmptyState } from './components/ui.jsx'

const NAV = [
  { key: 'dashboard', num: '01', label: '工作台', icon: LayoutDashboard },
  { key: 'diagnosis', num: '02', label: '简历诊断', icon: FileSearch },
  { key: 'interview', num: '03', label: '模拟面试', icon: Swords },
  { key: 'questions', num: '04', label: '真题题库', icon: Library },
  { key: 'board', num: '05', label: '投递看板', icon: Columns3 },
  { key: 'archive', num: '06', label: '成长档案', icon: TrendingUp },
]

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 10000); return () => clearInterval(t) }, [])
  const days = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  return (
    <div className="hud-clock">
      <div className="t en">{String(now.getHours()).padStart(2, '0')}:{String(now.getMinutes()).padStart(2, '0')}</div>
      <div className="d">{days[now.getDay()]} · {now.getMonth() + 1}月{now.getDate()}日</div>
    </div>
  )
}

export default function App() {
  const [module, setModule] = useState(() => localStorage.getItem('rai.module') || 'dashboard')
  const [session, setSession] = useState(null)
  const [report, setReport] = useState(null)
  const [llmMode, setLlmMode] = useState(null)
  const [focusIdx, setFocusIdx] = useState(() => {
    const k = localStorage.getItem('rai.module') || 'dashboard'
    return Math.max(0, NAV.findIndex((n) => n.key === (k === 'report' ? 'archive' : k)))
  })
  const [wipe, setWipe] = useState(0)
  const [phase, setPhase] = useState('idle')
  const itemRefs = useRef([])
  const cursorRef = useRef(null)
  const moduleRef = useRef(module)
  moduleRef.current = module
  const pendingRef = useRef(null)
  const firstGo = useRef(true)

  // 切屏：旧内容模糊淡出 → 柔和光带滑过 → 新内容模糊淡入（丝滑不硬切）
  const go = (m) => {
    localStorage.setItem('rai.module', m)
    history.replaceState(null, '', '#' + m)
    if (m === moduleRef.current) return
    if (firstGo.current) { setModule(m); return }
    pendingRef.current = m
    setPhase('out')
    setWipe((w) => w + 1)
  }
  const activeKey = module === 'report' ? 'archive' : module
  const activeIdx = NAV.findIndex((n) => n.key === activeKey)

  // 支持 URL hash 深链：#dashboard / #board / #report/<sessionId>
  useEffect(() => {
    const h = window.location.hash.replace(/^#/, '')
    if (!h) return
    if (h.startsWith('report/')) openReport(h.slice(7))
    else if (NAV.some((n) => n.key === h)) go(h)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  // 首次深链导航不做转场；之后的导航都走遮罩
  useEffect(() => { firstGo.current = false }, [])

  // 旧内容淡出完毕(约220ms)时切换模块，新内容随即模糊淡入
  useEffect(() => {
    if (phase !== 'out') return
    const t = setTimeout(() => {
      if (pendingRef.current) { setModule(pendingRef.current); pendingRef.current = null }
      setPhase('idle')
    }, 220)
    return () => clearTimeout(t)
  }, [phase])

  // 确认/点击切换后，键盘焦点回到当前项
  useEffect(() => { setFocusIdx(activeIdx) }, [activeIdx])

  // 全局键盘导航：↑↓ 移动光标 / ENTER 确认 / ESC 返回
  useEffect(() => {
    const onKey = (e) => {
      const t = e.target
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault()
        setFocusIdx((i) => (i + (e.key === 'ArrowDown' ? 1 : NAV.length - 1)) % NAV.length)
      } else if (e.key === 'Enter') {
        if (focusIdx !== activeIdx) go(NAV[focusIdx].key)
      } else if (e.key === 'Escape') {
        if (module === 'report') go('archive')
        else if (focusIdx !== activeIdx) setFocusIdx(activeIdx)
        else go('dashboard')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusIdx, activeIdx, module])

  // 恢复上次未完成的面试会话 + 引擎状态
  useEffect(() => {
    fetch('/api/health').then((r) => r.json()).then((h) => setLlmMode(h.llm_mode)).catch(() => {})
    const sid = localStorage.getItem('rai.lastSession')
    if (!sid) return
    getSessionState(sid)
      .then((st) => {
        if (!st.finished) {
          setSession({ ...st, id: st.session_id, filename: st.filename })
        }
      })
      .catch(() => localStorage.removeItem('rai.lastSession'))
  }, [])

  // 后端要求访问令牌（401 / WS 4401）时弹出输入框
  const [showAuth, setShowAuth] = useState(false)
  const [authInput, setAuthInput] = useState('')
  useEffect(() => {
    const need = () => setShowAuth(true)
    window.addEventListener('rai-auth-required', need)
    return () => window.removeEventListener('rai-auth-required', need)
  }, [])

  // 三角光标跟随键盘焦点（未确认时停在焦点项），移动时触发弹性回弹
  const placeCursor = useCallback(() => {
    const el = itemRefs.current[focusIdx]
    if (el && cursorRef.current) {
      cursorRef.current.style.transform = `translateY(${el.offsetTop + el.offsetHeight / 2 - 13}px)`
      const c = cursorRef.current
      c.classList.remove('hop')
      void c.offsetWidth
      c.classList.add('hop')
    }
  }, [focusIdx])
  useLayoutEffect(() => { placeCursor() }, [placeCursor])
  useEffect(() => {
    window.addEventListener('resize', placeCursor)
    window.addEventListener('load', placeCursor)
    return () => { window.removeEventListener('resize', placeCursor); window.removeEventListener('load', placeCursor) }
  }, [placeCursor])

  function handleUploaded(data) {
    setSession({ ...data, id: data.session_id })
    localStorage.setItem('rai.lastSession', data.session_id)
  }
  function resumeSession(st) {
    setSession({ ...st, id: st.session_id, filename: st.filename })
    go('interview')
  }
  function openReport(sid) {
    import('./api.js').then(({ getReport }) =>
      getReport(sid).then((r) => { setReport(r); go('report') }))
  }

  const pages = {
    dashboard: <Dashboard go={go} onResume={resumeSession} llmMode={llmMode} />,
    diagnosis: <DiagnosisScreen onUploaded={handleUploaded} go={go} />,
    interview: session
      ? (
        <ChatScreen
          key={session.id}
          session={session}
          onFinished={(r) => { setReport(r); go('report') }}
        />
      )
      : (
        <EmptyState
          icon={Swords}
          title="还没有可面试的简历"
          desc="先上传一份简历，AI 会完成解析、体检与漏洞挖掘，然后带着这些疑点对你发起模拟面试。"
          action={<button className="btn-primary" onClick={() => go('diagnosis')}>去上传简历</button>}
        />
      ),
    questions: <QuestionBank />,
    board: <Board />,
    archive: <Archive onView={openReport} onResume={resumeSession} go={go} />,
    report: <ReportScreen report={report} onBack={() => go('archive')} onRestart={() => go('diagnosis')} />,
  }

  const activeNum = NAV.find((n) => n.key === activeKey)?.num || '01'

  return (
    <>
      <P3RBackground />

      {/* 顶部 HUD */}
      <header className="hud">
        <div className="flex items-center gap-3">
          <div className="hud-mark"><span>R</span></div>
          <div className="hud-title">
            <b className="en">RAI WORKBENCH</b>
            <small>Resume · Agent · Insight</small>
          </div>
        </div>
        <div className="flex-1" />
        <div className="hud-main">
          <div className="poly en">MAIN</div>
          <div className="idx en">{activeNum}</div>
        </div>
        <Clock />
      </header>

      {/* 移动端横向导航 */}
      <nav className="mnav chat-scroll">
        {NAV.map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => go(key)}
            className={`chip whitespace-nowrap ${activeKey === key ? 'border-indigo-500/50 bg-indigo-500/20 text-white' : 'border-slate-700 text-slate-400'}`}>
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
      </nav>

      <div className="shell">
        {/* 左侧 P3R 菜单 */}
        <nav className="menu">
          <div className="menu-label en">Command</div>
          <div className="cursor" ref={cursorRef}>
            <svg viewBox="0 0 24 24"><polygon className="t-red" points="2,2 22,12 2,22" /><polygon className="t-white" points="7,6 18,12 7,18" /></svg>
          </div>
          {NAV.map(({ key, num, label, icon: Icon }, i) => (
            <button key={key} ref={(el) => { itemRefs.current[i] = el }}
              onClick={() => go(key)}
              className={`m-item ${activeKey === key ? 'active' : ''} ${i === focusIdx && activeKey !== key ? 'focus' : ''}`}>
              <span className="hl" />
              <span className="glow" />
              <span className="num en">{num}</span>
              <span className="ico"><Icon /></span>
              <span className="txt">{label}</span>
            </button>
          ))}
          <div className="menu-foot">
            引擎状态：{llmMode === 'real' ? '真实 LLM' : llmMode === 'mock' ? 'Mock 演示模式' : '连接中…'}
          </div>
        </nav>

        {/* 内容区 */}
        <main className="content">
          <div key={module} className={`${phase === 'out' ? 'leave' : 'rise'} max-w-6xl mx-auto`}>
            {pages[module] || pages.dashboard}
          </div>
        </main>
      </div>

      {/* 底部键位条 */}
      <footer className="keybar">
        <div className="kb"><span className="btn-k en">↑↓</span> 切换</div>
        <div className="kb"><span className="btn-k en">ENTER</span> 确认</div>
        <div className="kb"><span className="btn-k en">ESC</span> 返回</div>
        <div style={{ marginLeft: 'auto' }} className="en kb-brand">P3RE-STYLE · RAI WORKBENCH</div>
      </footer>

      {/* P3R 切屏转场：主光带 + 滞后拖影层 */}
      {wipe > 0 && <div key={wipe} className="p3r-wipe" aria-hidden="true" />}
      {wipe > 0 && <div key={`t${wipe}`} className="p3r-wipe trail" aria-hidden="true" />}

      {/* 访问令牌输入 */}
      {showAuth && (
        <div className="fixed inset-0 z-[60] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="card p-6 w-full max-w-sm">
            <p className="font-semibold text-white mb-1">需要访问令牌</p>
            <p className="text-xs text-slate-500 mb-4">
              后端已开启访问保护（ACCESS_TOKEN），请输入令牌后继续。
            </p>
            <input
              className="input w-full"
              placeholder="访问令牌"
              value={authInput}
              autoFocus
              onChange={(e) => setAuthInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && authInput.trim()) {
                  setApiToken(authInput.trim())
                  setShowAuth(false)
                }
              }}
            />
            <div className="flex justify-end gap-2 mt-4">
              <button className="btn-ghost" onClick={() => setShowAuth(false)}>取消</button>
              <button className="btn-primary" onClick={() => { setApiToken(authInput.trim()); setShowAuth(false) }}>
                保存并继续
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
