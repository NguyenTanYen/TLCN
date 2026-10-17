import { createContext, useCallback, useContext, useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

// Nhãn PLO: CTĐT cũ lưu mã '1.3', CTĐT 2026 lưu 'PLO6' → không lặp chữ PLO
export const ploLabel = c => (/^PLO/i.test(String(c || '')) ? c : `PLO ${c}`)

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

// size: 'sm' (hộp xác nhận) | mặc định (biểu mẫu ngắn) | 'md' (lựa chọn, danh sách) | 'wide' (bảng, soạn đề)
export function Modal({ title, onClose, children, wide, size }) {
  const hid = useId()
  useEffect(() => {  // Esc để đóng
    const onKey = e => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="modal-bg" onMouseDown={onClose}>
      <div className={`modal ${wide ? 'wide' : size || ''}`} role="dialog" aria-modal="true" aria-labelledby={hid} onMouseDown={e => e.stopPropagation()}>
        <header className="card-h"><h3 id={hid}>{title}</h3><button className="btn ghost" aria-label="Đóng" autoFocus onClick={onClose}>✕</button></header>
        <div className="card-b">{children}</div>
      </div>
    </div>
  )
}

// group=true: nhóm nhiều ô (checkbox/radio có nhãn riêng) – dùng <fieldset> thay vì <label> để không lồng nhãn
export function Field({ label, children, hint, group }) {
  if (group) return <fieldset className="field"><legend>{label}</legend>{children}{hint && <small className="muted">{hint}</small>}</fieldset>
  return <label className="field"><span>{label}</span>{children}{hint && <small className="muted">{hint}</small>}</label>
}

// Nút chọn tệp: là <button> thật (dùng được bằng bàn phím), chọn lại cùng một tệp vẫn kích hoạt
export function FileButton({ label, accept, onPick, className = 'btn primary', disabled }) {
  const ref = useRef(null)
  return <>
    <button type="button" className={className} disabled={disabled} onClick={() => ref.current?.click()}>{label}</button>
    <input ref={ref} type="file" accept={accept} hidden onChange={e => { const f = e.target.files[0]; e.target.value = ''; f && onPick(f) }} />
  </>
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
  return <ToastCtx.Provider value={push}>{children}<div className="toasts" role="status" aria-live="polite">{items.map(i => <div key={i.id} className={`toast ${i.tone}`}>{i.msg}</div>)}</div></ToastCtx.Provider>
}
export const useToast = () => useContext(ToastCtx)

// Nút thực hiện hành động bất đồng bộ, tự báo lỗi/thành công
// confirm: câu hỏi xác nhận trước thao tác không hoàn tác được
export function ActionButton({ onRun, children, className = 'btn', okMsg, disabled, title, confirm }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  return (
    <button type="button" className={className} disabled={busy || disabled} title={title} onClick={async () => {
      if (confirm && !window.confirm(confirm)) return
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

// Chọn CTĐT đang làm việc (dùng với useProgram())
export function ProgramPicker({ programs, pid, setPid }) {
  return <Field label="Chương trình đào tạo"><select value={pid || ''} onChange={e => setPid(e.target.value)}>
    {programs?.map(p => <option key={p.id} value={p.id}>{p.code} – {p.name}{p.cohort_year ? ` (khóa ${p.cohort_year})` : ''}</option>)}</select></Field>
}

// Đường dẫn phân cấp trên đầu trang: [['/', 'Môn học'], [null, 'DBMS330284_01']]
export function Crumbs({ items }) {
  return <nav className="crumb" aria-label="Đường dẫn">{items.filter(Boolean).map(([to, label], i) => <span key={i}>{i > 0 && <span className="sep"> › </span>}
    {to ? <Link to={to}>{label}</Link> : <span>{label}</span>}</span>)}</nav>
}

// Thẻ chọn nhanh (tab) đồng bộ với ?tab= trên địa chỉ trang
export function Tabs({ tabs, value, onChange }) {
  return <div className="tabs" role="tablist">{tabs.filter(Boolean).map(([k, l, dis]) =>
    <button key={k} role="tab" aria-selected={value === k} className={value === k ? 'on' : ''} disabled={dis} onClick={() => onChange(k)}>{l}</button>)}</div>
}
