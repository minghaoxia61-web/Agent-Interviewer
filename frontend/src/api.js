// 统一的 API 客户端：开发模式走 Vite 代理，生产模式同源（FastAPI 静态托管）

async function handle(res) {
  if (!res.ok) {
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
  const res = await fetch('/api/resume/upload', { method: 'POST', body: form })
  return handle(res)
}

export async function startInterview(sessionId) {
  const res = await fetch(`/api/interview/${sessionId}/start`, { method: 'POST' })
  return handle(res)
}

export async function sendMessage(sessionId, message) {
  const res = await fetch(`/api/interview/${sessionId}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  return handle(res)
}

export async function getSessionState(sessionId) {
  const res = await fetch(`/api/interview/${sessionId}/state`)
  return handle(res)
}

export async function finishInterview(sessionId) {
  const res = await fetch(`/api/interview/${sessionId}/finish`, { method: 'POST' })
  return handle(res)
}

export async function getReport(sessionId) {
  const res = await fetch(`/api/report/${sessionId}`)
  return handle(res)
}

export async function getDashboard() {
  const res = await fetch('/api/workbench/dashboard')
  return handle(res)
}

export async function getSessions() {
  const res = await fetch('/api/workbench/sessions')
  return handle(res)
}

export async function getQuestions(params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString()
  const res = await fetch(`/api/workbench/questions${qs ? `?${qs}` : ''}`)
  return handle(res)
}

export async function getApplications() {
  const res = await fetch('/api/applications')
  return handle(res)
}

export async function createApplication(data) {
  const res = await fetch('/api/applications', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return handle(res)
}

export async function updateApplication(id, patch) {
  const res = await fetch(`/api/applications/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  return handle(res)
}

export async function deleteApplication(id) {
  const res = await fetch(`/api/applications/${id}`, { method: 'DELETE' })
  return handle(res)
}

export async function matchJd(sessionId, jd) {
  const res = await fetch(`/api/resume/${sessionId}/jd-match`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jd }),
  })
  return handle(res)
}
