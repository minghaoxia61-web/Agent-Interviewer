import { useEffect, useRef, useState } from 'react'
import { Bot, Flag, Loader2, SendHorizonal, Swords, User, Zap } from 'lucide-react'
import {
  finishInterview, getReport, getSessionState, sendMessage, startInterview, WS_BASE,
} from '../api.js'
import { Card } from './ui.jsx'

const STAGES = [
  { key: 'intro', label: '开场' },
  { key: 'project_probing', label: '项目深挖' },
  { key: 'tech_drill', label: '技术基础' },
  { key: 'stress_test', label: '压力测试' },
  { key: 'end', label: '报告' },
]
const REASON_TEXT = {
  answer_too_short: '回答过短', no_numbers: '缺少量化', hedge_words: '表述模糊', no_causal_chain: '因果链缺失',
}

function StageBar({ stage }) {
  const activeIdx = stage === 'end' ? STAGES.length - 1
    : Math.max(0, STAGES.findIndex((s) => s.key === stage))
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {STAGES.map((s, i) => (
        <div key={s.key} className="flex items-center gap-1.5">
          <span className={`stage ${
            i < activeIdx ? 'done'
            : i === activeIdx ? 'cur'
            : ''}`}>
            {s.label}
          </span>
          {i < STAGES.length - 1 && <span className="text-slate-700 text-xs">›</span>}
        </div>
      ))}
    </div>
  )
}

export default function ChatScreen({ session, onFinished }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [stage, setStage] = useState('intro')
  const [thinking, setThinking] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [ending, setEnding] = useState(false)
  const [error, setError] = useState('')
  const [alreadyFinished, setAlreadyFinished] = useState(false)
  const scrollRef = useRef(null)
  const startedRef = useRef(false)
  const wsRef = useRef(null)
  const wsReadyRef = useRef(false)

  // ---------- WebSocket ----------
  function connectWs() {
    return new Promise((resolve, reject) => {
      try {
        const ws = new WebSocket(`${WS_BASE}/ws/interview/${session.id}`)
        ws.onopen = () => { wsReadyRef.current = true; resolve(ws) }
        ws.onerror = () => { if (!wsReadyRef.current) reject(new Error('ws')) }
        ws.onclose = () => { wsReadyRef.current = false }
        ws.onmessage = (ev) => { try { handleFrame(JSON.parse(ev.data)) } catch { /* 忽略坏帧 */ } }
        wsRef.current = ws
      } catch (e) { reject(e) }
    })
  }

  function appendToken(chunk) {
    setMessages((prev) => {
      const last = prev[prev.length - 1]
      if (last && last.role === 'assistant' && last.streaming) {
        return [...prev.slice(0, -1), { ...last, content: last.content + chunk }]
      }
      return [...prev, { role: 'assistant', content: chunk, streaming: true }]
    })
  }

  function finalize(frame) {
    setStreaming(false)
    setThinking(false)
    setStage(frame.stage)
    setMessages((prev) => {
      const last = prev[prev.length - 1]
      const finalMsg = {
        role: 'assistant',
        content: frame.assistant_message,
        meta: frame.decision ? {
          decision: frame.decision,
          decision_reasons: frame.decision_reasons || [],
          probe_depth: frame.probe_depth,
        } : null,
      }
      if (last && last.role === 'assistant' && last.streaming) {
        return [...prev.slice(0, -1), finalMsg]
      }
      return [...prev, finalMsg]
    })
    if (frame.finished) {
      getReport(session.id).then(onFinished).catch((e) => setError(e.message))
    }
  }

  function handleFrame(frame) {
    if (frame.type === 'token') appendToken(frame.data)
    else if (frame.type === 'final') finalize(frame)
    else if (frame.type === 'error') {
      setError(frame.message || '服务端错误')
      setThinking(false)
      setStreaming(false)
    }
  }

  // ---------- 生命周期 ----------
  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true
    // 断点续面：已有对话则恢复，否则开场（WS 优先，REST 兜底）
    getSessionState(session.id)
      .then((st) => {
        if (st.finished) { setAlreadyFinished(true); setStage('end'); return }
        if (st.total_turns > 0) {
          setStage(st.stage)
          setMessages(st.messages.map((m) => ({
            role: m.role,
            content: m.content,
            meta: m.meta ? {
              decision: m.meta.decision,
              decision_reasons: m.meta.reasons || [],
              probe_depth: m.meta.probe_depth,
            } : null,
          })))
          return
        }
        setThinking(true)
        connectWs()
          .then((ws) => ws.send(JSON.stringify({ type: 'start' })))
          .catch(() => {
            startInterview(session.id)
              .then((r) => finalize({ ...r, assistant_message: r.assistant_message }))
              .catch((e) => { setError(e.message); setThinking(false) })
          })
      })
      .catch((e) => setError(e.message))
    return () => { try { wsRef.current?.close() } catch { /* noop */ } }
  }, [session.id])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, thinking])

  // ---------- 发送 ----------
  async function send() {
    const text = input.trim()
    if (!text || thinking) return
    setInput('')
    setError('')
    setMessages((m) => [...m, { role: 'user', content: text }])
    setThinking(true)
    if (wsReadyRef.current) {
      setStreaming(true)
      wsRef.current.send(JSON.stringify({ type: 'message', data: text }))
      return
    }
    try {
      const r = await sendMessage(session.id, text)
      finalize({ ...r, type: 'final' })
    } catch (e) {
      setError(e.message)
      setThinking(false)
    }
  }

  async function endNow() {
    if (ending) return
    setEnding(true)
    try {
      const rep = await finishInterview(session.id)
      onFinished(rep)
    } catch (e) {
      setError(e.message)
      setEnding(false)
    }
  }

  if (alreadyFinished) {
    return (
      <Card className="p-10 text-center">
        <Swords className="w-10 h-10 text-slate-700 mx-auto mb-3" />
        <p className="text-slate-300">这场面试已经结束并生成过报告</p>
        <p className="text-xs text-slate-500 mt-1">可在「成长档案」查看报告，或上传简历开启新一场。</p>
        <button className="btn-ghost mt-5" onClick={() => window.location.reload()}>刷新页面</button>
      </Card>
    )
  }

  return (
    <div className="flex flex-col h-[calc(100vh-11.875rem)] lg:h-[calc(100vh-9.125rem)]">
      {/* 顶栏 */}
      <Card className="flex items-center gap-3 px-4 py-3 mb-3">
        <Swords className="w-5 h-5 text-indigo-300 shrink-0" />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-white truncate">模拟面试 · {session.target_position}</p>
          <p className="text-xs text-slate-500 truncate">{session.filename || '上次会话'}</p>
        </div>
        <div className="ml-auto hidden md:block"><StageBar stage={stage} /></div>
        <button onClick={endNow} disabled={ending}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-rose-500/40 text-rose-300 hover:bg-rose-500/10 disabled:opacity-50 shrink-0">
          <Flag className="w-3.5 h-3.5" /> {ending ? '生成中…' : '结束面试'}
        </button>
      </Card>
      <div className="md:hidden mb-3"><StageBar stage={stage} /></div>

      {/* 消息区 */}
      <Card className="flex-1 overflow-y-auto chat-scroll px-4 py-5 space-y-4 min-h-0">
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-2.5 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`msg-av ${
              m.role === 'user' ? 'bg-slate-700/80 text-slate-300' : 'bg-gradient-to-br from-indigo-400 to-indigo-500 text-[#04122b]'}`}>
              {m.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>
            <div className={`bub max-w-[82%] whitespace-pre-wrap ${
              m.role === 'user'
                ? 'bg-gradient-to-br from-indigo-400 to-indigo-500 text-[#04122b] font-medium'
                : 'bg-slate-900/75 border border-indigo-500/20 text-slate-300'}`}>
              {m.content}
              {m.streaming && <span className="inline-block w-1.5 h-4 bg-indigo-300 ml-1 align-middle animate-pulse" />}
              {m.meta?.decision === 'follow_up' && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <span className="chip border-rose-500/40 bg-rose-500/10 text-rose-300">追问 ×{m.meta.probe_depth}</span>
                  {m.meta.decision_reasons.map((r) => (
                    <span key={r} className="chip border-slate-700 bg-slate-800/60 text-slate-400">
                      {REASON_TEXT[r] || r}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {thinking && !streaming && (
          <div className="flex gap-2.5">
            <div className="msg-av bg-gradient-to-br from-indigo-400 to-indigo-500 text-[#04122b]">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bub bg-slate-900/75 border border-indigo-500/20 flex items-center gap-1">
              <span className="typing-dot w-1.5 h-1.5 rounded-full bg-slate-400 inline-block" />
              <span className="typing-dot w-1.5 h-1.5 rounded-full bg-slate-400 inline-block" />
              <span className="typing-dot w-1.5 h-1.5 rounded-full bg-slate-400 inline-block" />
            </div>
          </div>
        )}
        {error && <p className="text-center text-sm text-rose-300">{error}</p>}
      </Card>

      {/* 输入区 */}
      <div className="mt-3 flex items-end gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              send()
            }
          }}
          rows={2}
          placeholder="回答面试官的问题…（Enter 发送，Shift+Enter 换行）"
          className="input flex-1 resize-none"
        />
        <div className="self-stretch flex flex-col justify-between items-center gap-1">
          <button onClick={send} disabled={thinking || !input.trim()}
            className="btn-primary !px-4 grow">
            {thinking ? <Loader2 className="w-5 h-5 animate-spin" /> : <SendHorizonal className="w-5 h-5" />}
          </button>
          <span className={`text-[9px] flex items-center gap-0.5 ${wsReadyRef.current ? 'text-emerald-400/70' : 'text-slate-600'}`}>
            <Zap className="w-2.5 h-2.5" /> {wsReadyRef.current ? '流式' : 'REST'}
          </span>
        </div>
      </div>
    </div>
  )
}
