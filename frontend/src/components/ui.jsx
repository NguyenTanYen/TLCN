import { createContext, useCallback, useContext, useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

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

export function Modal({ title, onClose, children, wide, size }) {
  const hid = useId()
  useEffect(() => {
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

export function Field({ label, children, hint, group }) {
  if (group) return <fieldset className="field"><legend>{label}</legend>{children}{hint && <small className="muted">{hint}</small>}</fieldset>
  return <label className="field"><span>{label}</span>{children}{hint && <small className="muted">{hint}</small>}</label>
}

export function FileButton({ label, accept, onPick, className = 'btn primary', disabled }) {
  const ref = useRef(null)
  return <>
    <button type="button" className={className} disabled={disabled} onClick={() => ref.current?.click()}>{label}</button>
    <input ref={ref} type="file" accept={accept} hidden onChange={e => { const f = e.target.files[0]; e.target.value = ''; f && onPick(f) }} />
  </>
}

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

export function ProgramPicker({ programs, pid, setPid }) {
  return <Field label="Chương trình đào tạo"><select value={pid || ''} onChange={e => setPid(e.target.value)}>
    {programs?.map(p => <option key={p.id} value={p.id}>{p.code} – {p.name}{p.cohort_year ? ` (khóa ${p.cohort_year})` : ''}</option>)}</select></Field>
}

export function Crumbs({ items }) {
  return <nav className="crumb" aria-label="Đường dẫn">{items.filter(Boolean).map(([to, label], i) => <span key={i}>{i > 0 && <span className="sep"> › </span>}
    {to ? <Link to={to}>{label}</Link> : <span>{label}</span>}</span>)}</nav>
}

export function Flow({ steps, extra }) {
  return <div className="flow-wrap"><ol className="flow" role={steps.some(s => s?.tab) ? 'tablist' : undefined}>{steps.filter(Boolean).map((s, i) => {
    const body = <><span className="flow-n" aria-hidden="true">{s.done && !s.on ? '✓' : i + 1}</span><span className="flow-t"><b>{s.label}</b>{s.sub && <small>{s.sub}</small>}</span></>
    return <li key={i} className={`${s.done ? 'done' : ''} ${s.on ? 'on' : ''}`}>
      {s.to ? <Link className="flow-b" to={s.to}>{body}</Link>
        : <button type="button" className="flow-b" role={s.tab ? 'tab' : undefined} aria-selected={s.tab ? !!s.on : undefined} onClick={s.onClick}>{body}</button>}</li>
  })}</ol>{extra && <div className="flow-x">{extra}</div>}</div>
}

export const fold = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase()

export function CourseSelect({ courses, value, onChange, placeholder = '— chọn môn học —', allowEmpty = false, disabled }) {
  const label = c => `${c.course_code} – ${c.course_name}`
  const cur = (courses || []).find(c => String(c.id) === String(value))
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [hi, setHi] = useState(0)
  const box = useRef(null)
  const [pos, setPos] = useState(null)
  useEffect(() => {
    if (!open) return
    const place = () => { const r = box.current?.getBoundingClientRect(); if (r) { const w = Math.min(Math.max(r.width, 440), window.innerWidth - 16); setPos({ left: Math.max(8, Math.min(r.left, window.innerWidth - w - 8)), top: r.bottom + 2, width: w }) } }
    const off = e => { if (box.current && !box.current.contains(e.target)) setOpen(false) }
    place()
    document.addEventListener('mousedown', off)
    window.addEventListener('scroll', place, true); window.addEventListener('resize', place)
    return () => { document.removeEventListener('mousedown', off); window.removeEventListener('scroll', place, true); window.removeEventListener('resize', place) }
  }, [open])
  const words = fold(q).split(/\s+/).filter(Boolean)
  const list = (courses || []).filter(c => { const t = fold(label(c)); return words.every(w => t.includes(w)) }).slice(0, 200)
  const items = allowEmpty ? [null, ...list] : list
  const pick = c => { onChange(c ? String(c.id) : ''); setOpen(false); setQ('') }
  const key = e => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setHi(h => Math.min(h + 1, items.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHi(h => Math.max(h - 1, 0)) }
    else if (e.key === 'Enter') { if (open && items.length) { e.preventDefault(); pick(items[hi]) } }
    else if (e.key === 'Escape') { if (open) { e.stopPropagation(); setOpen(false); setQ('') } }
  }
  return <div className="combo" ref={box}>
    <input role="combobox" aria-expanded={open} aria-autocomplete="list" disabled={disabled}
      value={open ? q : cur ? label(cur) : ''} placeholder={cur ? label(cur) : placeholder}
      onFocus={() => { setOpen(true); setQ(''); setHi(0) }} onClick={() => setOpen(true)}
      onChange={e => { setQ(e.target.value); setOpen(true); setHi(0) }} onKeyDown={key} />
    {open && pos && <ul className="combo-list" role="listbox" style={pos}>
      {items.map((c, i) => <li key={c ? c.id : '_'} role="option" aria-selected={c ? String(c.id) === String(value) : !value}
        className={`${i === hi ? 'hi' : ''} ${c && String(c.id) === String(value) ? 'sel' : ''}`}
        onMouseEnter={() => setHi(i)} onMouseDown={e => { e.preventDefault(); pick(c) }}>
        {c ? <><b>{c.course_code}</b> – {c.course_name}</> : <span className="muted">{placeholder}</span>}</li>)}
      {!list.length && <li className="muted empty">Không có học phần khớp "{q}"</li>}
    </ul>}
  </div>
}

export function Tabs({ tabs, value, onChange }) {
  return <div className="tabs" role="tablist">{tabs.filter(Boolean).map(([k, l, dis]) =>
    <button key={k} role="tab" aria-selected={value === k} className={value === k ? 'on' : ''} disabled={dis} onClick={() => onChange(k)}>{l}</button>)}</div>
}
