import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import {
  Briefcase, Columns3, FileSearch, LayoutDashboard, Library, Swords, TrendingUp,
} from 'lucide-react'
import { getSessionState } from './api.js'
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
  const itemRefs = useRef([])
  const cursorRef = useRef(null)

  const go = (m) => {
    setModule(m)
    localStorage.setItem('rai.module', m)
    history.replaceState(null, '', '#' + m)
  }
  const activeKey = module === 'report' ? 'archive' : module

  // 支持 URL hash 深链：#dashboard / #board / #report/<sessionId>
  useEffect(() => {
    const h = window.location.hash.replace(/^#/, '')
    if (!h) return
    if (h.startsWith('report/')) openReport(h.slice(7))
    else if (NAV.some((n) => n.key === h)) go(h)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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

  // 三角光标跟随选中菜单项
  const placeCursor = useCallback(() => {
    const idx = NAV.findIndex((n) => n.key === activeKey)
    const el = itemRefs.current[idx]
    if (el && cursorRef.current) {
      cursorRef.current.style.transform = `translateY(${el.offsetTop + el.offsetHeight / 2 - 13}px)`
    }
  }, [activeKey])
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
              className={`m-item ${activeKey === key ? 'active' : ''}`}>
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
          <div key={module} className="rise max-w-6xl mx-auto">
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
    </>
  )
}
