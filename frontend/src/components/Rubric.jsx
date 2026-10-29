// Rubric chấm điểm theo tiêu chí: soạn rubric của môn, tạo bài chấm theo rubric, bảng chấm chọn mức cho từng sinh viên
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { ActionButton, Badge, Card, Field, Loading, Modal } from './ui'
import { useApi } from '../hooks'

const DEFAULT_LEVELS = [{ label: 'Tốt', descriptor: '', score_pct: 100 }, { label: 'Khá', descriptor: '', score_pct: 75 },
  { label: 'Đạt', descriptor: '', score_pct: 50 }, { label: 'Chưa đạt', descriptor: '', score_pct: 0 }]
const blankCriterion = clo => ({ name: '', points: 2, clo_id: clo || '', levels: DEFAULT_LEVELS.map(l => ({ ...l })) })

// ---- danh sách rubric của môn
export function RubricsTab({ courseId, readOnly }) {
  const list = useApi(`/api/courses/${courseId}/rubrics`)
  const [edit, setEdit] = useState(null)       // null | 'new' | id
  const dup = id => api.post(`/api/rubrics/${id}/duplicate`).then(() => list.reload())
  const del = id => window.confirm('Xóa rubric này?') && api.del(`/api/rubrics/${id}`).then(() => list.reload())
  return <Card title="Rubric chấm điểm" actions={!readOnly && <button className="btn sm primary" onClick={() => setEdit('new')}>+ Tạo rubric</button>}>
    <p className="muted small">Rubric là bảng tiêu chí chấm cho bài tự luận, đồ án, báo cáo, thực hành. Mỗi tiêu chí đo một chuẩn đầu ra (CLO) và có các mức (Tốt, Khá, Đạt…) quy ra % điểm.
      Khi chấm, giảng viên chỉ cần chọn mức cho từng tiêu chí; điểm và mức đạt CLO được tính tự động.</p>
    {!list.data ? <Loading {...list} /> : list.data.length === 0 ? <div className="empty"><p>Môn này chưa có rubric.</p>
      {!readOnly && <button className="btn primary" onClick={() => setEdit('new')}>+ Tạo rubric đầu tiên</button>}</div> :
      <table className="tbl"><thead><tr><th>Tên rubric</th><th>Số tiêu chí</th><th>Tổng điểm</th><th>Trạng thái</th><th /></tr></thead>
        <tbody>{list.data.map(r => <tr key={r.id}><td><b>{r.name}</b><div className="muted small">{r.description}</div></td><td>{r.n_criteria}</td><td>{Number(r.total_points)}</td>
          <td>{r.in_use ? <Badge tone="blue">Đã dùng để chấm</Badge> : <Badge>Chưa dùng</Badge>}</td>
          <td className="row gap">
            <button className="btn sm" onClick={() => setEdit(r.id)}>{r.in_use || readOnly ? 'Xem' : 'Sửa'}</button>
            {!readOnly && <button className="btn sm" onClick={() => dup(r.id)}>Nhân bản</button>}
            {!readOnly && !r.in_use && <button className="btn sm" onClick={() => del(r.id)}>Xóa</button>}</td></tr>)}</tbody></table>}
    {edit && <RubricForm courseId={courseId} id={edit === 'new' ? null : edit} readOnly={readOnly} onClose={() => { setEdit(null); list.reload() }} />}
  </Card>
}

function RubricForm({ courseId, id, readOnly, onClose }) {
  const clos = useApi(`/api/courses/${courseId}`).data?.clos || []
  const cur = useApi(id ? `/api/rubrics/${id}` : null)
  const [f, setF] = useState({ name: '', description: '', criteria: [blankCriterion()] })
  useEffect(() => {
    if (cur.data) setF({ name: cur.data.name, description: cur.data.description || '', criteria: cur.data.criteria.map(c => ({ name: c.name, points: c.points, clo_id: c.clo_id,
      levels: c.levels.map(l => ({ label: l.label, descriptor: l.descriptor || '', score_pct: l.score_pct })) })) })
  }, [cur.data])
  useEffect(() => { if (!id && clos.length && !f.criteria[0].clo_id) setF(x => ({ ...x, criteria: x.criteria.map(c => ({ ...c, clo_id: clos[0].id })) })) }, [clos.length])  // eslint-disable-line
  const locked = readOnly || cur.data?.in_use
  const setC = (i, patch) => setF(x => ({ ...x, criteria: x.criteria.map((c, j) => j === i ? { ...c, ...patch } : c) }))
  const setL = (i, k, patch) => setC(i, { levels: f.criteria[i].levels.map((l, j) => j === k ? { ...l, ...patch } : l) })
  const total = f.criteria.reduce((s, c) => s + Number(c.points || 0), 0)
  const body = () => ({ name: f.name, description: f.description || null, criteria: f.criteria.map(c => ({ name: c.name, points: Number(c.points), clo_id: Number(c.clo_id),
    levels: c.levels.map(l => ({ label: l.label, descriptor: l.descriptor || null, score_pct: Number(l.score_pct) })) })) })
  return <Modal title={id ? (locked ? `Rubric: ${f.name}` : 'Sửa rubric') : 'Tạo rubric'} onClose={onClose} wide>
    {locked && !readOnly && <div className="alert amber">Rubric đã được dùng để chấm điểm nên chỉ xem. Muốn thay đổi, bấm "Nhân bản" ở danh sách rồi sửa bản mới.</div>}
    <fieldset disabled={locked} className="plain">
      <div className="grid2"><Field label="Tên rubric"><input value={f.name} onChange={e => setF({ ...f, name: e.target.value })} placeholder="VD: Chấm báo cáo đồ án" /></Field>
        <Field label="Ghi chú (không bắt buộc)"><input value={f.description} onChange={e => setF({ ...f, description: e.target.value })} /></Field></div>
      {f.criteria.map((c, i) => <div key={i} className="rub-crit">
        <div className="row gap wrap"><b>Tiêu chí {i + 1}</b><span className="grow" />
          {!locked && f.criteria.length > 1 && <button className="btn sm" onClick={() => setF({ ...f, criteria: f.criteria.filter((_, j) => j !== i) })}>Xóa tiêu chí</button>}</div>
        <div className="grid3 compact-grid">
          <Field label="Tên tiêu chí"><input value={c.name} onChange={e => setC(i, { name: e.target.value })} placeholder="VD: Nội dung chuyên môn" /></Field>
          <Field label="Điểm tối đa"><input type="number" min="0.5" step="0.5" value={c.points} onChange={e => setC(i, { points: e.target.value })} /></Field>
          <Field label="Đo chuẩn đầu ra (CLO)"><select value={c.clo_id} onChange={e => setC(i, { clo_id: e.target.value })}>
            {clos.map(k => <option key={k.id} value={k.id}>{k.clo_code} – {(k.description || '').slice(0, 50)}</option>)}</select></Field>
        </div>
        <table className="tbl compact"><thead><tr><th>Mức</th><th>Mô tả biểu hiện</th><th>% điểm tối đa</th><th>Điểm</th><th /></tr></thead>
          <tbody>{c.levels.map((l, k) => <tr key={k}>
            <td><input value={l.label} onChange={e => setL(i, k, { label: e.target.value })} /></td>
            <td><input value={l.descriptor} onChange={e => setL(i, k, { descriptor: e.target.value })} placeholder="VD: Trình bày đầy đủ, chính xác" /></td>
            <td><input type="number" min="0" max="100" value={l.score_pct} onChange={e => setL(i, k, { score_pct: e.target.value })} /></td>
            <td>{(Number(c.points || 0) * Number(l.score_pct || 0) / 100).toFixed(2)}</td>
            <td>{!locked && c.levels.length > 2 && <button className="btn sm" onClick={() => setC(i, { levels: c.levels.filter((_, j) => j !== k) })}>✕</button>}</td></tr>)}</tbody></table>
        {!locked && c.levels.length < 6 && <button className="btn sm" onClick={() => setC(i, { levels: [...c.levels, { label: '', descriptor: '', score_pct: 0 }] })}>+ Thêm mức</button>}
      </div>)}
      {!locked && f.criteria.length < 20 && <button className="btn" onClick={() => setF({ ...f, criteria: [...f.criteria, blankCriterion(clos[0]?.id)] })}>+ Thêm tiêu chí</button>}
    </fieldset>
    <div className="row mt"><span className="muted">Tổng điểm các tiêu chí: <b>{total}</b></span><span className="grow" />
      {!locked && <ActionButton className="btn primary" okMsg="Đã lưu rubric" onRun={async () => { await (id ? api.put(`/api/rubrics/${id}`, body()) : api.post(`/api/courses/${courseId}/rubrics`, body())); onClose() }}>Lưu rubric</ActionButton>}
    </div>
  </Modal>
}

// ---- tạo bài chấm theo rubric cho một lớp
export function RubricExamForm({ cs, onClose }) {
  const nav = useNavigate()
  const list = useApi(`/api/courses/${cs.course_id}/rubrics`)
  const [f, setF] = useState({ rubric_id: '', exam_title: '', assessment_type: 'process', exam_date: '', max_score: 10 })
  const rid = f.rubric_id || list.data?.[0]?.id || ''
  return <Modal title={`Tạo bài chấm theo rubric – lớp ${cs.section_code}`} onClose={onClose}>
    {!list.data ? <Loading {...list} /> : list.data.length === 0 ? <div className="alert amber">Môn này chưa có rubric. Vào trang môn học → thẻ "Rubric chấm điểm" để tạo trước.</div> : <>
      <Field label="Rubric dùng để chấm"><select value={rid} onChange={e => setF({ ...f, rubric_id: e.target.value })}>
        {list.data.map(r => <option key={r.id} value={r.id}>{r.name} ({r.n_criteria} tiêu chí, {Number(r.total_points)} điểm)</option>)}</select></Field>
      <Field label="Tên bài kiểm tra"><input value={f.exam_title} onChange={e => setF({ ...f, exam_title: e.target.value })} placeholder="VD: Báo cáo đồ án giữa kỳ" /></Field>
      <div className="grid2"><Field label="Loại đánh giá"><select value={f.assessment_type} onChange={e => setF({ ...f, assessment_type: e.target.value })}>
        <option value="process">Quá trình</option><option value="final">Cuối kỳ</option></select></Field>
        <Field label="Thang điểm"><input type="number" min="1" value={f.max_score} onChange={e => setF({ ...f, max_score: e.target.value })} /></Field></div>
      <div className="row"><span className="grow" /><ActionButton className="btn primary" disabled={f.exam_title.trim().length < 3}
        onRun={async () => { const r = await api.post(`/api/class-sections/${cs.id}/rubric-exams`, { ...f, rubric_id: Number(rid), exam_date: f.exam_date || null, max_score: Number(f.max_score) }); nav(`/exams/${r.id}`) }}>Tạo bài và bắt đầu chấm</ActionButton></div></>}
  </Modal>
}

// ---- bảng chấm: mỗi dòng một sinh viên, mỗi cột một tiêu chí, chọn mức
export function RubricGrades({ e, reload }) {
  const g = useApi(`/api/exams/${e.id}/rubric-grid`)
  const [rows, setRows] = useState({})
  const [dirty, setDirty] = useState(new Set())
  useEffect(() => {
    if (!g.data) return
    setRows(Object.fromEntries(g.data.students.map(s => [s.student_id, { absent: s.status === 'absent', levels: { ...s.levels } }])))
    setDirty(new Set())
  }, [g.data])
  const crit = g.data?.rubric.criteria || []
  const set = (sid, patch) => { setRows(r => ({ ...r, [sid]: { ...r[sid], ...patch } })); setDirty(d => new Set(d).add(sid)) }
  const pts = (sid) => crit.reduce((s, c) => { const lid = rows[sid]?.levels[String(c.id)]; const l = c.levels.find(x => x.id === lid); return s + (l ? c.points * l.score_pct / 100 : 0) }, 0)
  const full = sid => crit.every(c => rows[sid]?.levels[String(c.id)])
  const partial = sid => !rows[sid]?.absent && crit.some(c => rows[sid]?.levels[String(c.id)]) && !full(sid)
  const anyPartial = useMemo(() => [...dirty].some(partial), [dirty, rows, crit])  // eslint-disable-line
  const save = async () => {
    const body = [...dirty].map(sid => ({ student_id: Number(sid), absent: rows[sid].absent, levels: Object.fromEntries(crit.map(c => [c.id, rows[sid].absent ? null : (rows[sid].levels[String(c.id)] || null)])) }))
    const r = await api.put(`/api/exams/${e.id}/rubric-grades`, { rows: body, analyze: true })
    g.reload(); reload(); return r
  }
  if (!g.data) return <Loading {...g} />
  const scale = g.data.max_score / (g.data.raw_max || 1)
  return <Card title={`Chấm theo rubric: ${g.data.rubric.name}`} actions={<Badge tone="blue">{g.data.students.filter(s => s.status === 'finished').length}/{g.data.students.length} SV đã có điểm</Badge>}>
    <p className="muted small">Với mỗi sinh viên, chọn mức cho <b>tất cả</b> tiêu chí (hoặc đánh dấu Vắng). Điểm tự tính theo % của mức. Bấm "Lưu và phân tích" để tính mức đạt chuẩn đầu ra.</p>
    <div className="scroll"><table className="tbl compact rub-grid"><thead><tr><th>MSSV</th><th>Họ tên</th><th>Vắng</th>
      {crit.map(c => <th key={c.id}>{c.name}<div className="muted small">{c.clo_code} · tối đa {c.points}</div></th>)}<th>Tổng</th></tr></thead>
      <tbody>{g.data.students.map(s => { const r = rows[s.student_id] || { levels: {} }; return <tr key={s.student_id} className={partial(s.student_id) ? 'bad-row' : ''}>
        <td>{s.student_code}</td><td>{s.full_name}{s.dropped && <Badge tone="gray">đã rút</Badge>}</td>
        <td><input type="checkbox" checked={!!r.absent} onChange={ev => set(s.student_id, { absent: ev.target.checked })} aria-label={`Vắng ${s.student_code}`} /></td>
        {crit.map(c => <td key={c.id}><select disabled={r.absent} value={r.levels[String(c.id)] || ''} aria-label={`${s.student_code} – ${c.name}`}
          onChange={ev => set(s.student_id, { levels: { ...r.levels, [String(c.id)]: ev.target.value ? Number(ev.target.value) : undefined } })}>
          <option value="">—</option>{c.levels.map(l => <option key={l.id} value={l.id} title={l.descriptor || ''}>{l.label} ({(c.points * l.score_pct / 100).toFixed(1)})</option>)}</select></td>)}
        <td><b>{r.absent ? 'Vắng' : full(s.student_id) ? (pts(s.student_id) * scale).toFixed(2) : '—'}</b></td></tr> })}</tbody></table></div>
    {anyPartial && <div className="alert amber mt">Có sinh viên mới chọn một phần tiêu chí (dòng tô màu): hãy chọn đủ mọi tiêu chí hoặc bỏ trống cả dòng trước khi lưu.</div>}
    <div className="row mt"><span className="grow" /><ActionButton className="btn primary" disabled={!dirty.size || anyPartial} okMsg="Đã lưu điểm và phân tích" onRun={save}>Lưu và phân tích ({dirty.size} SV thay đổi)</ActionButton></div>
  </Card>
}
