// Lớp truy cập REST API – tự đính kèm JWT, chuẩn hóa thông báo lỗi tiếng Việt
const KEY = 'tlcn_token'

export const auth = {
  get token() { return localStorage.getItem(KEY) },
  set(token, user) { localStorage.setItem(KEY, token); localStorage.setItem('tlcn_user', JSON.stringify(user)) },
  user() { try { return JSON.parse(localStorage.getItem('tlcn_user')) } catch { return null } },
  clear() { localStorage.removeItem(KEY); localStorage.removeItem('tlcn_user') },
}

async function request(method, path, body, isForm = false) {
  const headers = {}
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`
  if (body && !isForm) headers['Content-Type'] = 'application/json'
  const res = await fetch(path, { method, headers, body: isForm ? body : body ? JSON.stringify(body) : undefined })
  if (res.status === 401 && !path.endsWith('/login')) { auth.clear(); window.location.href = '/login' }
  const ct = res.headers.get('content-type') || ''
  const data = ct.includes('json') ? await res.json() : res
  if (!res.ok) {
    let msg = data?.detail ?? `Lỗi ${res.status}`
    if (Array.isArray(msg)) msg = msg.map(d => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ')
    const err = new Error(msg); err.status = res.status; throw err
  }
  return data
}

export const api = {
  get: p => request('GET', p),
  post: (p, b) => request('POST', p, b),
  put: (p, b) => request('PUT', p, b),
  patch: (p, b) => request('PATCH', p, b),
  del: p => request('DELETE', p),
  upload: (p, file) => { const f = new FormData(); f.append('file', file); return request('POST', p, f, true) },
  async download(p, fallbackName) {
    const res = await request('GET', p)
    const blob = await res.blob()
    const cd = res.headers.get('content-disposition') || ''
    const name = /filename="?([^"]+)"?/.exec(cd)?.[1] || fallbackName
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click()
    setTimeout(() => URL.revokeObjectURL(a.href), 2000)
  },
}

export const fmtPct = v => (v === null || v === undefined ? '—' : `${Number(v).toFixed(2)}%`)
export const fmtNum = (v, d = 2) => (v === null || v === undefined ? '—' : Number(v).toFixed(d))
export const STATUS_VI = { Draft: 'Nháp', Published: 'Đã phát hành', Synced: 'Đã đồng bộ', Analyzed: 'Đã phân tích' }
