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

// 登录身份（GitHub OAuth）：登录后 visitor 即固定为 gh 身份，令牌 30 天有效
export function getLogin() {
  try {
    return JSON.parse(localStorage.getItem('rai.login') || 'null')
  } catch {
    return null
  }
}

export function setLogin(login) {
  if (login) {
    localStorage.setItem('rai.login', JSON.stringify(login))
    localStorage.setItem('rai.visitor', login.owner)
    localStorage.setItem('rai.login_token', login.login_token)
  } else {
    localStorage.removeItem('rai.login')
    localStorage.removeItem('rai.login_token')
    localStorage.removeItem('rai.visitor')
  }
}

// 访客标识：数据隔离用（后端按它过滤会话/投递记录），与令牌无关
export function visitorId() {
  const login = getLogin()
  if (login?.owner) return login.owner
  let v = localStorage.getItem('rai.visitor')
  if (!v) {
    v = crypto.randomUUID ? crypto.randomUUID() : 'v-' + Date.now() + '-' + Math.random().toString(36).slice(2)
    localStorage.setItem('rai.visitor', v)
  }
  return v
}

function authHeaders(extra = {}) {
  const h = { 'X-Visitor-Id': visitorId() }
  const t = apiToken()
  if (t) h['X-API-Token'] = t
  const lt = localStorage.getItem('rai.login_token')
  if (lt) h['X-Login-Token'] = lt
  return { ...h, ...extra }
}

function wsUrl(path) {
  const qs = new URLSearchParams(authHeaders())
  return WS_BASE + path + `?${qs.toString()}`
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

// 统一请求：默认 60s 超时（上传 120s），GET 网络失败自动重试一次
async function request(path, { method = 'GET', body, headers = {}, timeoutMs = 60000, retries } = {}) {
  const attempt = retries ?? (method === 'GET' ? 1 : 0)
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  let res
  try {
    res = await fetch(A + path, {
      method,
      headers: authHeaders(headers),
      body,
      signal: ctrl.signal,
    })
  } catch (e) {
    clearTimeout(timer)
    if (attempt > 0) {
      return request(path, { method, body, headers, timeoutMs, retries: attempt - 1 })
    }
    throw new Error('网络异常或请求超时，请重试')
  }
  clearTimeout(timer)
  return handle(res)
}

const jsonHeaders = { 'Content-Type': 'application/json' }

export async function uploadResume(file, targetPosition) {
  const form = new FormData()
  form.append('file', file)
  form.append('target_position', targetPosition)
  return request('/api/resume/upload', { method: 'POST', body: form, timeoutMs: 120000 })
}

export async function startInterview(sessionId) {
  return request(`/api/interview/${sessionId}/start`, { method: 'POST' })
}

export async function sendMessage(sessionId, message) {
  return request(`/api/interview/${sessionId}/message`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ message }),
  })
}

export async function getSessionState(sessionId) {
  return request(`/api/interview/${sessionId}/state`)
}

export async function finishInterview(sessionId) {
  return request(`/api/interview/${sessionId}/finish`, { method: 'POST' })
}

export async function getReport(sessionId) {
  return request(`/api/report/${sessionId}`)
}

export async function getDashboard() {
  return request('/api/workbench/dashboard')
}

export async function getSessions() {
  return request('/api/workbench/sessions')
}

export async function getQuestions(params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString()
  return request(`/api/workbench/questions${qs ? `?${qs}` : ''}`)
}

export async function getApplications() {
  return request('/api/applications')
}

export async function createApplication(data) {
  return request('/api/applications', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(data),
  })
}

export async function updateApplication(id, patch) {
  return request(`/api/applications/${id}`, {
    method: 'PUT',
    headers: jsonHeaders,
    body: JSON.stringify(patch),
  })
}

export async function deleteApplication(id) {
  return request(`/api/applications/${id}`, { method: 'DELETE' })
}

export async function matchJd(sessionId, jd) {
  return request(`/api/resume/${sessionId}/jd-match`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ jd }),
    timeoutMs: 120000,
  })
}

export async function getAnalysis(sessionId) {
  return request(`/api/resume/${sessionId}/analysis`)
}

export async function startPractice(category, company, count = 5) {
  return request('/api/practice/start', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ category, company, count }),
  })
}

export async function submitPracticeAnswer(pid, answer) {
  return request(`/api/practice/${pid}/answer`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ answer }),
    timeoutMs: 120000,
  })
}

export async function getPractice(pid) {
  return request(`/api/practice/${pid}`)
}

export async function getPracticeHistory() {
  return request('/api/practice/history')
}

export async function getReview(sessionId) {
  return request(`/api/interview/${sessionId}/review`)
}

export async function getGithubAuthUrl() {
  return request('/api/auth/github/url')
}

export async function exchangeGithubToken(code, state, vid) {
  return request('/api/auth/github/token', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ code, state, visitor_id: vid }),
  })
}

export async function verifyLoginToken(loginToken) {
  return request('/api/auth/verify', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ login_token: loginToken }),
  })
}

export async function getPracticeMistakes() {
  return request('/api/practice/mistakes')
}

export async function startPracticeFromMistakes(questionIds) {
  return request('/api/practice/mistakes/start', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ question_ids: questionIds }),
  })
}

export { wsUrl }
