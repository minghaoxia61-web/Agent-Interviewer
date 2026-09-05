// 统一的 API 客户端：开发模式走 Vite 代理，生产模式同源（FastAPI 静态托管）
// 生产 / GitHub Pages：可用 VITE_API_BASE 指向独立部署的后端；留空则走同源相对路径。
// 后端配置了 ACCESS_TOKEN 时，所有请求自动携带 X-API-Token（localStorage 持久化），
// 收到 401 时广播 rai-auth-required 事件，由 App 弹出令牌输入框。
const A = import.meta.env.VITE_API_BASE || ''
export const WS_BASE = A
  ? A.replace(/^http/, 'ws').replace(/\/$/, '')
  : (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host

export function apiToken() {
  return localStorage.getItem('rai.token') || ''
}

export function setApiToken(token) {
  if (token) localStorage.setItem('rai.token', token)
  else localStorage.removeItem('rai.token')
}

function authHeaders(extra = {}) {
  const t = apiToken()
  return t ? { 'X-API-Token': t, ...extra } : { ...extra }
}

function wsUrl(path) {
  const t = apiToken()
  return WS_BASE + path + (t ? `?token=${encodeURIComponent(t)}` : '')
}

async function handle(res) {
  if (!res.ok) {
    if (res.status === 401) {
      window.dispatchEvent(new CustomEvent('rai-auth-required'))
    }
    let detail = `请求失败 (${res.status})`
    try {
      const data = await res.json()
      if (data.detail) detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json()
}

export async function uploadResume(file, targetPosition) {
  const form = new FormData()
  form.append('file', file)
  form.append('target_position', targetPosition)
  const res = await fetch(A + '/api/resume/upload', { method: 'POST', body: form, headers: authHeaders() })
  return handle(res)
}

export async function startInterview(sessionId) {
  const res = await fetch(A + `/api/interview/${sessionId}/start`, { method: 'POST', headers: authHeaders() })
  return handle(res)
}

export async function sendMessage(sessionId, message) {
  const res = await fetch(A + `/api/interview/${sessionId}/message`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ message }),
  })
  return handle(res)
}

export async function getSessionState(sessionId) {
  const res = await fetch(A + `/api/interview/${sessionId}/state`, { headers: authHeaders() })
  return handle(res)
}

export async function finishInterview(sessionId) {
  const res = await fetch(A + `/api/interview/${sessionId}/finish`, { method: 'POST', headers: authHeaders() })
  return handle(res)
}

export async function getReport(sessionId) {
  const res = await fetch(A + `/api/report/${sessionId}`, { headers: authHeaders() })
  return handle(res)
}

export async function getDashboard() {
  const res = await fetch(A + '/api/workbench/dashboard', { headers: authHeaders() })
  return handle(res)
}

export async function getSessions() {
  const res = await fetch(A + '/api/workbench/sessions', { headers: authHeaders() })
  return handle(res)
}

export async function getQuestions(params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString()
  const res = await fetch(A + `/api/workbench/questions${qs ? `?${qs}` : ''}`, { headers: authHeaders() })
  return handle(res)
}

export async function getApplications() {
  const res = await fetch(A + '/api/applications', { headers: authHeaders() })
  return handle(res)
}

export async function createApplication(data) {
  const res = await fetch(A + '/api/applications', {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(data),
  })
  return handle(res)
}

export async function updateApplication(id, patch) {
  const res = await fetch(A + `/api/applications/${id}`, {
    method: 'PUT',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(patch),
  })
  return handle(res)
}

export async function deleteApplication(id) {
  const res = await fetch(A + `/api/applications/${id}`, { method: 'DELETE', headers: authHeaders() })
  return handle(res)
}

export async function matchJd(sessionId, jd) {
  const res = await fetch(A + `/api/resume/${sessionId}/jd-match`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ jd }),
  })
  return handle(res)
}

export { wsUrl }
