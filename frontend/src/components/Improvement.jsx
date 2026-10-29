import { useState } from 'react'
import { api, fmtPct } from '../api'
import { ActionButton, Badge, Card, Field, Loading } from './ui'
import { useApi } from '../hooks'

const ST = { open: ['Chưa làm', 'gray'], doing: ['Đang làm', 'blue'], done: ['Đã làm', 'amber'], verified: ['Đã kiểm chứng', 'green'] }
const ARROW = { up: ['▲', 'ok-t'], down: ['▼', 'bad-t'], flat: ['●', 'muted'] }

// So sánh kết quả từng CLO của học phần qua các học kỳ (gộp các lớp cùng học kỳ)
export function CloTrend({ courseId }) {
  const { data, ...st } = useApi(`/api/courses/${courseId}/clo-trend`)
  if (!data) return <Loading {...st} />
  const sems = data.semesters
  return <Card title="Xu hướng đạt CLO qua các học kỳ">
    {sems.length < 2
      ? <p className="muted">Môn này mới có {sems.length} học kỳ có số liệu. Từ học kỳ thứ hai, bảng sẽ so sánh với kỳ trước để biết các cải tiến có hiệu quả không.</p>
      : <div className="scroll"><table className="tbl compact"><thead><tr><th>CLO</th>{sems.map(s => <th key={s.semester_id}>{s.semester}</th>)}<th>So với kỳ trước</th></tr></thead>
        <tbody>{data.clos.map(c => <tr key={c.clo_id}><td><b>{c.clo_code}</b></td>
          {sems.map(s => { const p = c.points.find(x => x.semester_id === s.semester_id); return <td key={s.semester_id}>{p ? <span className={p.is_achieved ? 'ok-t' : 'bad-t'}>{fmtPct(p.achieved_pct)}</span> : '—'}</td> })}
          <td>{c.trend ? <span className={ARROW[c.trend][1]}>{ARROW[c.trend][0]} {c.change > 0 ? '+' : ''}{c.change} điểm %</span> : '—'}</td></tr>)}</tbody></table></div>}
    <p className="muted small mt">Màu xanh = đạt chỉ tiêu của kỳ đó, đỏ = chưa đạt. Số liệu gộp mọi lớp học phần của môn trong học kỳ (nên có thể khác bảng kết quả của riêng một lớp); chỉ tính các lớp đã phân tích.</p>
  </Card>
}

// Hành động cải tiến của lớp: người phụ trách, hạn, trạng thái, kết quả kiểm chứng
export function ImprovementActions({ csId, clos }) {
  const { data, reload, ...st } = useApi(`/api/class-sections/${csId}/improvement-actions`)
  const empty = { description: '', clo_id: '', owner: '', due_date: '' }
  const [f, setF] = useState(empty)
  const set = k => e => setF({ ...f, [k]: e.target.value })
  const patch = (a, body) => api.patch(`/api/improvement-actions/${a.id}`, body).then(reload)
  return <Card title="Hành động cải tiến (đóng vòng đánh giá)">
    <p className="muted small">Với CLO chưa đạt, ghi hành động sẽ làm, ai làm, hạn nào. Đến kỳ sau, ghi kết quả kiểm chứng (CLO có tăng không) rồi chuyển sang "Đã kiểm chứng".</p>
    {!data ? <Loading {...st} /> : data.length === 0 ? <p className="muted">Chưa có hành động nào.</p> :
      <table className="tbl compact"><thead><tr><th>CLO</th><th>Hành động</th><th>Phụ trách</th><th>Hạn</th><th>Trạng thái</th><th>Kết quả kiểm chứng</th><th /></tr></thead>
        <tbody>{data.map(a => <tr key={a.id}><td>{a.clo_code || 'Cả lớp'}</td><td>{a.description}</td><td>{a.owner || '—'}</td>
          <td>{a.due_date || '—'} {a.overdue && <Badge tone="red">Quá hạn</Badge>}</td>
          <td><select value={a.status} onChange={e => { const v = e.target.value; if (v === 'verified' && !a.result) { const r = window.prompt('Ghi kết quả kiểm chứng (VD: CLO2 tăng từ 55% lên 72%):'); if (!r) return; patch(a, { status: v, result: r }) } else patch(a, { status: v }) }}>
            {Object.entries(ST).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}</select></td>
          <td className="clip">{a.result || '—'}</td>
          <td><button className="btn sm" onClick={() => { if (window.confirm('Xóa hành động này?')) api.del(`/api/improvement-actions/${a.id}`).then(reload) }}>Xóa</button></td></tr>)}</tbody></table>}
    <div className="grid2 mt">
      <Field label="Hành động cải tiến"><input value={f.description} onChange={set('description')} placeholder="VD: Thêm 2 buổi bài tập truy vấn lồng" /></Field>
      <Field label="CLO liên quan"><select value={f.clo_id} onChange={set('clo_id')}><option value="">Cả lớp</option>{clos.map(c => <option key={c.clo_id} value={c.clo_id}>{c.clo_code}{c.is_achieved === false ? ' (chưa đạt)' : ''}</option>)}</select></Field>
      <Field label="Người phụ trách"><input value={f.owner} onChange={set('owner')} /></Field>
      <Field label="Hạn hoàn thành"><input type="date" value={f.due_date} onChange={set('due_date')} /></Field>
    </div>
    <div className="row"><span className="grow" /><ActionButton className="btn primary" okMsg="Đã thêm hành động cải tiến" disabled={f.description.trim().length < 3}
      onRun={() => api.post(`/api/class-sections/${csId}/improvement-actions`, { description: f.description, clo_id: f.clo_id ? Number(f.clo_id) : null, owner: f.owner || null, due_date: f.due_date || null }).then(() => { setF(empty); reload() })}>+ Thêm hành động</ActionButton></div>
  </Card>
}
