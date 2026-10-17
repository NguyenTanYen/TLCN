// Biểu mẫu soạn đề cương chi tiết có phiên bản (góp ý F1) – chỉ Bộ môn; bản đã duyệt phải tạo phiên bản mới để sửa.
import { useState } from 'react'
import { api } from '../api'
import { ActionButton, Field, Modal } from './ui'
import { useApi } from '../hooks'

export const SYL_TEXT = {
  objectives: 'Mục tiêu học phần', teaching_methods: 'Phương pháp giảng dạy', course_policy: 'Quy định của học phần',
}
const save = (cid, body) => api.put(`/api/courses/${cid}/syllabus`, body)
const numOrNull = v => (v === '' || v == null ? null : Number(v))
const Save = ({ onRun, disabled, msg = 'Đã lưu' }) =>
  <div className="row"><span className="grow" /><ActionButton className="btn primary" disabled={disabled} okMsg={msg} onRun={onRun}>Lưu</ActionButton></div>

export function GeneralForm({ s, onClose, onSaved }) {
  const d = s.doc || {}
  const sems = useApi('/api/semesters').data
  const [f, setF] = useState({ english_name: d.english_name || '', self_study_hours: d.self_study_hours ?? '', effective_semester_id: d.effective_semester_id || '' })
  return <Modal title="Thông tin chung của đề cương" onClose={onClose}>
    <p className="small muted">Tên, mã, số tín chỉ, cấu trúc, học phần tiên quyết và mô tả vắn tắt sửa ở "Thông tin học phần" (dùng chung mọi phiên bản).</p>
    <Field label="Tên học phần tiếng Anh"><input value={f.english_name} onChange={e => setF({ ...f, english_name: e.target.value })} /></Field>
    <div className="row gap">
      <Field label="Số giờ tự học"><input className="num" type="number" min="0" value={f.self_study_hours} onChange={e => setF({ ...f, self_study_hours: e.target.value })} /></Field>
      <Field label="Áp dụng từ học kỳ"><select value={f.effective_semester_id} onChange={e => setF({ ...f, effective_semester_id: e.target.value })}>
        <option value="">—</option>{sems?.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
    </div>
    <Save onRun={async () => { await save(s.id, { english_name: f.english_name, self_study_hours: numOrNull(f.self_study_hours),
      effective_semester_id: numOrNull(f.effective_semester_id) }); onSaved() }} />
  </Modal>
}

export function TextForm({ s, field, onClose, onSaved }) {
  const [v, setV] = useState(s.doc?.[field] || '')
  return <Modal title={SYL_TEXT[field]} onClose={onClose} size="md">
    <textarea rows={8} style={{ width: '100%' }} value={v} onChange={e => setV(e.target.value)} />
    <Save onRun={async () => { await save(s.id, { [field]: v }); onSaved() }} />
  </Modal>
}

export function AssessmentsForm({ s, onClose, onSaved }) {
  const blank = i => ({ component_code: `A${i}`, name: '', method: '', timing: '', weight_pct: '', clo_ids: [] })
  const [rows, setRows] = useState((s.doc?.assessments || []).map(a => ({ ...a, method: a.method || '', timing: a.timing || '', clo_ids: a.clos.map(x => x.id) })))
  const upd = (i, k, v) => setRows(r => r.map((x, j) => j === i ? { ...x, [k]: v } : x))
  const toggle = (i, id) => setRows(r => r.map((x, j) => j === i ? { ...x, clo_ids: x.clo_ids.includes(id) ? x.clo_ids.filter(y => y !== id) : [...x.clo_ids, id] } : x))
  const total = rows.reduce((n, r) => n + (Number(r.weight_pct) || 0), 0)
  return <Modal title="Đánh giá học phần" onClose={onClose} wide>
    <table className="tbl compact"><thead><tr><th style={{ width: 70 }}>Mã</th><th>Thành phần</th><th>Hình thức</th><th>Thời điểm</th><th style={{ width: 90 }}>Tỷ trọng %</th><th>CLO được đánh giá</th><th /></tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}>
        <td><input className="num tiny" value={r.component_code} maxLength={10} onChange={e => upd(i, 'component_code', e.target.value)} /></td>
        <td><input value={r.name} onChange={e => upd(i, 'name', e.target.value)} placeholder="VD Kiểm tra giữa kỳ" /></td>
        <td><input value={r.method} maxLength={150} onChange={e => upd(i, 'method', e.target.value)} placeholder="Trắc nghiệm, tự luận…" /></td>
        <td><input value={r.timing} maxLength={100} onChange={e => upd(i, 'timing', e.target.value)} placeholder="Tuần 8" /></td>
        <td><input className="num tiny" type="number" min="0.01" max="100" step="0.01" value={r.weight_pct} onChange={e => upd(i, 'weight_pct', e.target.value)} /></td>
        <td>{s.clos.map(c => <label key={c.id} className="chk" title={c.description}><input type="checkbox" checked={r.clo_ids.includes(c.id)} onChange={() => toggle(i, c.id)} /> {c.clo_code}</label>)}</td>
        <td><button className="btn sm ghost" onClick={() => setRows(x => x.filter((_, j) => j !== i))}>✕</button></td></tr>)}</tbody></table>
    <div className="row gap mt"><button className="btn sm" onClick={() => setRows(x => [...x, blank(x.length + 1)])}>+ Thành phần</button>
      <span className={Math.abs(total - 100) > 0.01 ? 'neg' : 'pos'}>Tổng: {total}%</span></div>
    <Save disabled={rows.some(r => !r.component_code.trim() || r.name.trim().length < 2 || !(Number(r.weight_pct) > 0))} msg="Đã lưu đánh giá học phần"
      onRun={async () => { await save(s.id, { assessments: rows.map(r => ({ component_code: r.component_code, name: r.name, method: r.method || null,
        timing: r.timing || null, weight_pct: Number(r.weight_pct), clo_ids: r.clo_ids })) }); onSaved() }} />
  </Modal>
}

export function ReferencesForm({ s, onClose, onSaved }) {
  const [rows, setRows] = useState((s.doc?.references || []).map(r => ({ ...r })))
  const upd = (i, k, v) => setRows(r => r.map((x, j) => j === i ? { ...x, [k]: v } : x))
  return <Modal title="Tài liệu học tập" onClose={onClose} size="md">
    {rows.map((r, i) => <div key={i} className="row gap mb">
      <select value={r.ref_type} onChange={e => upd(i, 'ref_type', e.target.value)}><option value="main">Giáo trình chính</option><option value="extra">Tham khảo</option></select>
      <input className="grow" value={r.citation} onChange={e => upd(i, 'citation', e.target.value)} placeholder="Tác giả – Tên tài liệu, NXB, năm" />
      <button className="btn sm ghost" onClick={() => setRows(x => x.filter((_, j) => j !== i))}>✕</button></div>)}
    <button className="btn sm" onClick={() => setRows(x => [...x, { ref_type: 'main', citation: '' }])}>+ Tài liệu</button>
    <Save msg="Đã lưu tài liệu" onRun={async () => { await save(s.id, { references: rows.filter(r => r.citation.trim().length >= 3)
      .map(r => ({ ref_type: r.ref_type, citation: r.citation })) }); onSaved() }} />
  </Modal>
}

// Nội dung chi tiết một chương (dùng chung mọi phiên bản đề cương)
export function OutlineForm({ s, o, onClose, onSaved }) {
  const [f, setF] = useState({ content: o.content || '', theory_hours: o.theory_hours ?? '', practice_hours: o.practice_hours ?? '',
    teaching_activities: o.teaching_activities || '', clo_ids: (o.clos || []).map(x => x.id) })
  const toggle = id => setF(x => ({ ...x, clo_ids: x.clo_ids.includes(id) ? x.clo_ids.filter(y => y !== id) : [...x.clo_ids, id] }))
  return <Modal title={`Chương ${o.chapter_number}. ${o.chapter_name}`} onClose={onClose} size="md">
    <Field label="Nội dung chi tiết"><textarea rows={4} value={f.content} onChange={e => setF({ ...f, content: e.target.value })} /></Field>
    <div className="row gap">
      <Field label="Số tiết lý thuyết"><input className="num" type="number" min="0" value={f.theory_hours} onChange={e => setF({ ...f, theory_hours: e.target.value })} /></Field>
      <Field label="Số tiết thực hành"><input className="num" type="number" min="0" value={f.practice_hours} onChange={e => setF({ ...f, practice_hours: e.target.value })} /></Field>
    </div>
    <Field label="Hoạt động dạy và học"><textarea rows={2} value={f.teaching_activities} onChange={e => setF({ ...f, teaching_activities: e.target.value })} /></Field>
    <Field group label="CLO của chương">{s.clos.map(c => <label key={c.id} className="chk" title={c.description}>
      <input type="checkbox" checked={f.clo_ids.includes(c.id)} onChange={() => toggle(c.id)} /> {c.clo_code}</label>)}</Field>
    <Save msg="Đã lưu chương" onRun={async () => { await api.put(`/api/outlines/${o.id}`, { chapter_number: o.chapter_number, chapter_name: o.chapter_name,
      content: f.content, theory_hours: numOrNull(f.theory_hours), practice_hours: numOrNull(f.practice_hours),
      teaching_activities: f.teaching_activities, clo_ids: f.clo_ids }); onSaved() }} />
  </Modal>
}
