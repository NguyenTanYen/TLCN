import { createContext, useCallback, useContext, useState } from 'react'

export function Card({ title, actions, children, className = '' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && <header className="card-h"><h3>{title}</h3><div className="row gap">{actions}</div></header>}
      <div className="card-b">{children}</div>
    </section>
  )
}

export function Stat({ label, value, sub, tone }) {
  return <div className={`stat ${tone || ''}`}><div className="stat-l">{label}</div><div className="stat-v">{value}</div>{sub && <div className="stat-s">{sub}</div>}</div>
}

export const Badge = ({ tone = 'gray', children }) => <span className={`badge ${tone}`}>{children}</span>

export const Achieved = ({ ok }) => ok === null || ok === undefined
  ? <Badge>Chưa đo</Badge> : ok ? <Badge tone="green">Đạt</Badge> : <Badge tone="red">Không đạt</Badge>

export function Loading({ error, loading }) {
  if (error) return <div className="alert red">{error}</div>
  if (loading) return <div className="muted pad">Đang tải…</div>
  return null
}

export function Modal({ title, onClose, children, wide }) {
  return (
    <div className="modal-bg" onMouseDown={onClose}>
      <div className={`modal ${wide ? 'wide' : ''}`} onMouseDown={e => e.stopPropagation()}>
        <header className="card-h"><h3>{title}</h3><button className="btn ghost" onClick={onClose}>✕</button></header>
        <div className="card-b">{children}</div>
      </div>
    </div>
  )
}

export function Field({ label, children, hint }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small className="muted">{hint}</small>}</label>
}

// ---- thông báo nhanh (toast)
const ToastCtx = createContext(() => {})
export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const push = useCallback((msg, tone = 'green') => {
    const id = Math.random()
    setItems(x => [...x, { id, msg, tone }])
    setTimeout(() => setItems(x => x.filter(i => i.id !== id)), 4500)
  }, [])
  return <ToastCtx.Provider value={push}>{children}<div className="toasts">{items.map(i => <div key={i.id} className={`toast ${i.tone}`}>{i.msg}</div>)}</div></ToastCtx.Provider>
}
export const useToast = () => useContext(ToastCtx)

// Nút thực hiện hành động bất đồng bộ, tự báo lỗi/thành công
export function ActionButton({ onRun, children, className = 'btn', okMsg, disabled, title }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  return (
    <button className={className} disabled={busy || disabled} title={title} onClick={async () => {
      setBusy(true)
      try { const r = await onRun(); if (okMsg) toast(typeof okMsg === 'function' ? okMsg(r) : okMsg) }
      catch (e) { toast(e.message, 'red') } finally { setBusy(false) }
    }}>{busy ? 'Đang xử lý…' : children}</button>
  )
}

export function pClass(p) {
  if (p === null || p === undefined) return ''
  p = Number(p); return p > 0.85 || p < 0.25 ? 'warn' : 'ok'
}
export function diClass(di) {
  if (di === null || di === undefined) return ''
  di = Number(di); return di < 0 ? 'bad' : di < 0.2 ? 'warn' : di < 0.3 ? 'mid' : 'ok'
}
