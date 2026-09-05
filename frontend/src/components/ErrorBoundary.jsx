import React from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'

// 全局错误边界：渲染异常时给出可恢复的兜底 UI，而不是白屏
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // 保留到控制台便于排查；生产环境可上报
    console.error('[RAI] 渲染异常:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center p-6">
          <div className="card p-8 max-w-md text-center">
            <AlertTriangle className="w-10 h-10 text-amber-300 mx-auto mb-3" />
            <p className="text-white font-semibold mb-1">页面出了一点问题</p>
            <p className="text-xs text-slate-500 break-all mb-5">
              {String(this.state.error?.message || this.state.error)}
            </p>
            <div className="flex justify-center gap-2">
              <button className="btn-ghost" onClick={() => this.setState({ error: null })}>
                <RotateCcw className="w-4 h-4" /> 重试
              </button>
              <button className="btn-primary" onClick={() => window.location.reload()}>
                刷新页面
              </button>
            </div>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
