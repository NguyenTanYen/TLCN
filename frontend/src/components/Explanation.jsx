import { Fragment, useState } from 'react'
import { api } from '../api'
import { ActionButton, Badge, useToast } from './ui'

const NOTE = {
  refused: 'Mô hình không giải thích được bằng nội dung các trang này – SV chỉ nhận danh sách trang.',
  none: '',
}

function Cited({ text, sources, openPage }) {
  return text.split(/(\[Nguồn \d+\])/).map((part, i) => {
    const m = part.match(/^\[Nguồn (\d+)\]$/)
    const s = m && sources[Number(m[1]) - 1]
    if (!s) return <Fragment key={i}>{part}</Fragment>
    return <span key={i} className="cite">(<a href="#" onClick={ev => { ev.preventDefault(); openPage(s.url) }}>{s.title} – trang {s.page_no} ↗</a>)</span>
  })
}

export function Explanation({ examId, q, onChange, openPage }) {
  const x = q.explanation || { status: 'none' }
  const url = `/api/exams/${examId}/questions/${q.question_id}/explanation`
  const gen = async () => { const r = await api.post(url); onChange(q.question_id, r); return r }
  const review = rejected => async () => { const r = await api.patch(url, { rejected }); onChange(q.question_id, r); return r }
  if (x.status === 'ready') return <div className="explain">
    <div className="row gap">
      <span className="muted">Lời giải thích (mô hình {x.model}, chỉ dựa trên các trang trên):</span>
      <ActionButton className="btn sm ghost" title="Sai kiến thức hoặc lỗi chữ: không gửi cho SV (các trang vẫn gửi)"
        okMsg="Đã loại bỏ – SV không nhận lời giải thích này" onRun={review(true)}>✕ Loại bỏ</ActionButton>
    </div>
    <div><Cited text={x.text} sources={x.sources} openPage={openPage} /></div>
  </div>
  if (x.status === 'rejected') return <div className="explain rejected">
    <div className="row gap">
      <span><Badge tone="red">Đã loại bỏ</Badge> <span className="muted">SV chỉ nhận danh sách trang</span></span>
      <ActionButton className="btn sm ghost" okMsg="Đã khôi phục" onRun={review(false)}>↺ Khôi phục</ActionButton>
    </div>
    <div className="muted"><s>{x.text}</s></div>
  </div>
  if (x.status === 'missing') return <ActionButton className="btn sm mt" title="Mô hình ngôn ngữ trên máy chủ đọc các trang gợi ý rồi viết lời giải thích có trích trang (vài giây với GPU, vài phút nếu máy chủ chạy bằng CPU)"
    okMsg={r => r.status === 'ready' ? 'Đã sinh lời giải thích' : 'Mô hình không giải thích được bằng tài liệu này'} onRun={gen}>Sinh lời giải thích</ActionButton>
  return NOTE[x.status] ? <div className="muted mt">{NOTE[x.status]}</div> : null
}

export function GenerateAll({ examId, rows, onChange }) {
  const [batch, setBatch] = useState(null)
  const toast = useToast()
  const missing = rows.filter(q => q.n_wrong > 0 && q.explanation?.status === 'missing')
  if (!missing.length) return null
  const run = async () => {
    setBatch(0)
    let ok = 0
    try {
      for (const [i, q] of missing.entries()) {
        const r = await api.post(`/api/exams/${examId}/questions/${q.question_id}/explanation`)
        onChange(q.question_id, r)
        ok += r.status === 'ready'
        setBatch(i + 1)
      }
      toast(`Đã sinh ${ok}/${missing.length} lời giải thích`)
    } catch (e) { toast(e.message, 'red') } finally { setBatch(null) }
  }
  return <button className="btn sm primary" disabled={batch !== null} onClick={run} title="Sinh lần lượt cho mọi câu có SV làm sai – mỗi câu vài giây với GPU, vài phút nếu máy chủ chạy bằng CPU">
    {batch !== null ? `Đang sinh ${batch}/${missing.length}…` : `Sinh lời giải thích cho ${missing.length} câu`}</button>
}
