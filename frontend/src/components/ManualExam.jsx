// Bài KT nhập điểm: khai báo câu/ý chấm tay + CLO; lưới nhập điểm; nhập/xuất Excel; tạo bài từ file Excel bất kỳ.
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { ActionButton, Badge, Card, Field, FileButton, Loading, Modal, useToast } from './ui'
import { useApi } from '../hooks'

const blank = n => ({ title: `Câu ${n}`, points: 2, clos: [] })

// Chọn CLO cho một câu/ý: nhiều CLO thì chia đều trọng số (tổng = 1)
function CloPick({ clos, value, onChange }) {
  return <div className="row gap wrap">{clos.map(c => <label key={c.id} className="row gap check" title={c.description}>
    <input type="checkbox" checked={value.includes(c.id)} onChange={e => onChange(e.target.checked ? [...value, c.id] : value.filter(x => x !== c.id))} />{c.clo_code}</label>)}</div>
}

export const weights = ids => ids.map((id, i) => ({ clo_id: id, weight: i < ids.length - 1 ? Math.round(100 / ids.length) / 100 : Math.round((1 - Math.round(100 / ids.length) / 100 * (ids.length - 1)) * 100) / 100 }))

// cs: bài của một lớp HP; courseId (+ sections): đề nhập điểm của môn – giao cho lớp HP sau
export function ManualExamForm({ cs, courseId, sections, onClose }) {
  const nav = useNavigate()
  const cid = cs ? cs.course_id : courseId
  const course = useApi(`/api/courses/${cid}`).data
  const [xcs, setXcs] = useState(cs || (sections?.length === 1 ? sections[0] : null))  // lớp nhận file Excel có điểm
  const [f, setF] = useState({ exam_title: '', assessment_type: 'process', exam_date: '', max_score: 10, counts_for_clo: true })
  const [items, setItems] = useState([blank(1), blank(2), blank(3)])
  const [mode, setMode] = useState('form')
  const total = items.reduce((a, b) => a + Number(b.points || 0), 0)
  const bad = items.some(i => !i.title.trim() || !(Number(i.points) > 0) || !i.clos.length)
  const save = async () => {
    const r = await api.post(cs ? `/api/class-sections/${cs.id}/manual-exams` : `/api/courses/${cid}/manual-exams`, { ...f, exam_date: f.exam_date || null, max_score: Number(f.max_score),
      items: items.map(i => ({ title: i.title.trim(), points: Number(i.points), clos: weights(i.clos) })) })
    nav(`/exams/${r.id}`)
  }
  return <Modal size="wide" title={`Bài kiểm tra nhập điểm${cs ? ` – lớp ${cs.section_code}` : ' – đề của môn'}`} onClose={onClose}>
    <div className="tabs">{[['form', 'Khai báo câu/ý chấm điểm'], ['excel', 'Tạo từ file Excel có sẵn']].map(([k, l]) =>
      <button key={k} className={mode === k ? 'on' : ''} onClick={() => setMode(k)}>{l}</button>)}</div>
    <div className="grid3">
      <Field label="Tên bài"><input value={f.exam_title} onChange={e => setF({ ...f, exam_title: e.target.value })} placeholder="VD Bài tập lớn / Thực hành tuần 1–5" /></Field>
      <Field label="Bài KT lấy minh chứng (BM6a)"><select value={f.assessment_type} onChange={e => setF({ ...f, assessment_type: e.target.value })}>
        <option value="process">Quá trình</option><option value="final">Cuối kỳ</option></select></Field>
      <Field label="Thang điểm"><input className="num" type="number" value={f.max_score} onChange={e => setF({ ...f, max_score: e.target.value })} /></Field>
    </div>
    {mode === 'form' ? <>
      <table className="tbl compact"><thead><tr><th>#</th><th>Câu / ý chấm điểm</th><th>Điểm tối đa</th><th>Đo CLO</th><th /></tr></thead>
        <tbody>{items.map((it, i) => <tr key={i}><td>{i + 1}</td>
          <td><input style={{ width: '100%' }} value={it.title} onChange={e => setItems(x => x.map((y, k) => k === i ? { ...y, title: e.target.value } : y))} /></td>
          <td><input className="num tiny" type="number" step="0.25" min="0.25" value={it.points} onChange={e => setItems(x => x.map((y, k) => k === i ? { ...y, points: e.target.value } : y))} /></td>
          <td>{course && <CloPick clos={course.clos} value={it.clos} onChange={v => setItems(x => x.map((y, k) => k === i ? { ...y, clos: v } : y))} />}</td>
          <td><button className="btn sm ghost" aria-label="Xóa dòng" onClick={() => setItems(x => x.filter((_, k) => k !== i))}>✕</button></td></tr>)}</tbody></table>
      <div className="row gap mt"><button className="btn sm" onClick={() => setItems(x => [...x, blank(x.length + 1)])}>+ Thêm câu/ý</button>
        <span className="muted small">Tổng điểm tối đa: <b>{total}</b> (quy đổi về thang {f.max_score})</span><span className="grow" />
        {bad && <small className="bad-t">Mỗi câu/ý cần tên, điểm &gt; 0 và ít nhất một CLO</small>}
        <ActionButton className="btn primary" disabled={bad || f.exam_title.trim().length < 3 || !items.length} onRun={save}>{cs ? 'Tạo bài và nhập điểm' : 'Lưu đề của môn'}</ActionButton></div>
      {!cs && <p className="muted small mt">Sau khi lưu, bấm "Giao cho lớp HP" để chọn các lớp sẽ nhập điểm – mỗi lớp nhận một bảng điểm riêng.</p>}
    </> : <>
      {!cs && <Field label="File điểm của lớp học phần"><select value={xcs?.id || ''} onChange={e => setXcs(sections.find(s => String(s.id) === e.target.value) || null)}>
        <option value="">– Chọn lớp –</option>{(sections || []).map(s => <option key={s.id} value={s.id}>{s.section_code} · {s.semester} · {s.n_students} SV</option>)}</select></Field>}
      {xcs ? <ExcelCreate key={xcs.id} cs={xcs} f={f} clos={course?.clos || []} /> : <p className="muted small">File Excel đã có điểm của sinh viên nên cần chọn lớp học phần trước.</p>}
    </>}
  </Modal>
}

function ExcelCreate({ cs, f, clos }) {
  const nav = useNavigate()
  const toast = useToast()
  const [file, setFile] = useState(null)
  const [pre, setPre] = useState(null)
  const [cmap, setCmap] = useState({})
  const [pmap, setPmap] = useState({})
  const [enroll, setEnroll] = useState(false)
  const send = async (dry, fl = file) => {
    const fd = new FormData()
    fd.append('file', fl); fd.append('exam_title', f.exam_title || ''); fd.append('assessment_type', f.assessment_type); fd.append('max_score', String(f.max_score))
    fd.append('clo_map', JSON.stringify(cmap)); fd.append('points_map', JSON.stringify(pmap))
    const res = await fetch(`/api/class-sections/${cs.id}/manual-exams/import?dry_run=${dry}&enroll_missing=${enroll}`,
      { method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('tlcn_token')}` }, body: fd })
    const d = await res.json()
    if (!res.ok) throw new Error(d.detail || `Lỗi ${res.status}`)
    return d
  }
  const pickFile = async fl => {
    setFile(fl)
    try {
      const d = await send(true, fl); setPre(d)
      setCmap(Object.fromEntries(d.items.map(i => [i.col, i.clo_ids]))); setPmap(Object.fromEntries(d.items.map(i => [i.col, i.points])))
    } catch (e) { toast(e.message, 'red') }
  }
  const ready = pre && pre.items.every(i => (cmap[i.col] || []).length && Number(pmap[i.col]) > 0)
  return <>
    <p className="muted small">File Excel (.xlsx) có một dòng tiêu đề chứa cột <b>MSSV</b> (hoặc "Mã SV"), cột họ tên và các cột điểm. Có thể ghi điểm tối đa và CLO ngay trong tiêu đề,
      VD <code>Bài 1 (5đ) [CLO3]</code>, hoặc một dòng "Điểm tối đa" dưới tiêu đề; thiếu thông tin thì chọn ở bước xem trước. Cột STT, Tổng, Ghi chú được bỏ qua.</p>
    <FileButton className="btn" accept=".xlsx" label={file ? `Đổi file (${file.name})` : 'Chọn file Excel…'} onPick={pickFile} />
    {pre && <>
      <table className="tbl compact mt"><thead><tr><th>Cột trong file</th><th>Câu / ý</th><th>Điểm tối đa</th><th>Đo CLO</th></tr></thead>
        <tbody>{pre.items.map(i => <tr key={i.col}><td><code>{i.header}</code></td><td>{i.title}</td>
          <td><input className={`num tiny ${Number(pmap[i.col]) > 0 ? '' : 'bad'}`} type="number" value={pmap[i.col] ?? ''} onChange={e => setPmap({ ...pmap, [i.col]: e.target.value })} />
            {i.points_guessed && <small className="muted"> (ước từ điểm cao nhất)</small>}</td>
          <td><CloPick clos={clos} value={cmap[i.col] || []} onChange={v => setCmap({ ...cmap, [i.col]: v })} /></td></tr>)}</tbody></table>
      <p className="small">{pre.n_rows} dòng SV · {pre.n_matched} SV thuộc lớp{pre.missing_students.length ? <> · <b className="bad-t">{pre.missing_students.length} SV chưa có trong lớp</b>: {pre.missing_students.slice(0, 8).map(m => m.student_code).join(', ')}{pre.missing_students.length > 8 ? '…' : ''}</> : ''}</p>
      {pre.missing_students.length > 0 && <label className="row gap check"><input type="checkbox" checked={enroll} onChange={e => setEnroll(e.target.checked)} /> Ghi danh các SV này vào lớp (nếu không, bỏ qua dòng của họ)</label>}
      <div className="row"><span className="grow" />
        <ActionButton className="btn primary" disabled={!ready || f.exam_title.trim().length < 3} title={f.exam_title.trim().length < 3 ? 'Nhập tên bài' : ''}
          okMsg={r => `Đã tạo bài và nhập điểm ${r.saved} SV${r.absent ? `, ${r.absent} vắng` : ''} – đã phân tích`}
          onRun={async () => { const r = await send(false); if (r.dry_run) { setPre(r); throw new Error('Còn cột chưa đủ điểm tối đa/CLO') } nav(`/exams/${r.exam_id}`); return r }}>Tạo bài từ file</ActionButton></div>
    </>}
  </>
}

// Lưới nhập điểm của một bài nhập điểm
export function ManualGrades({ e, reload }) {
  const gb = useApi(`/api/exams/${e.id}/grades`)
  const toast = useToast()
  const [rows, setRows] = useState({})          // student_id -> {absent, scores}
  const [dirty, setDirty] = useState(new Set())
  const [file, setFile] = useState(null)
  const [pre, setPre] = useState(null)
  const [enroll, setEnroll] = useState(false)
  useEffect(() => {
    if (!gb.data) return
    setRows(Object.fromEntries(gb.data.students.map(s => [s.student_id, { absent: s.status === 'absent', scores: { ...s.scores } }])))
    setDirty(new Set())
  }, [gb.data])
  const items = gb.data?.items || []
  const set = (sid, patch) => { setRows(r => ({ ...r, [sid]: { ...r[sid], ...patch } })); setDirty(d => new Set(d).add(sid)) }
  const val = (sid, q) => rows[sid]?.scores[String(q)] ?? ''
  const badCell = (v, max) => v !== '' && v !== null && (isNaN(Number(String(v).replace(',', '.'))) || Number(String(v).replace(',', '.')) < 0 || Number(String(v).replace(',', '.')) > max)
  const anyBad = useMemo(() => [...dirty].some(sid => items.some(it => badCell(val(sid, it.question_id), it.points))), [dirty, rows, items])  // eslint-disable-line
  const save = async () => {
    const body = [...dirty].map(sid => ({ student_id: Number(sid), absent: rows[sid].absent,
      scores: Object.fromEntries(items.map(it => { const v = val(sid, it.question_id); return [it.question_id, v === '' || v === null ? null : Number(String(v).replace(',', '.'))] })) }))
    const r = await api.put(`/api/exams/${e.id}/grades`, { rows: body, analyze: true })
    gb.reload(); reload(); return r
  }
  const upload = async (dry, fl = file) => {
    const fd = new FormData(); fd.append('file', fl)
    const res = await fetch(`/api/exams/${e.id}/grades/import?dry_run=${dry}&enroll_missing=${enroll}`, { method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('tlcn_token')}` }, body: fd })
    const d = await res.json()
    if (!res.ok) throw new Error(d.detail || `Lỗi ${res.status}`)
    return d
  }
  const total = sid => rows[sid]?.absent ? '' : items.reduce((a, it) => a + (Number(String(val(sid, it.question_id)).replace(',', '.')) || 0), 0)
  if (!gb.data) return <Loading {...gb} />
  return <>
    <Card title={`Nhập điểm – ${items.length} câu/ý, tổng ${gb.data.raw_max} điểm (quy đổi thang ${gb.data.max_score})`} actions={<>
      <ActionButton className="btn sm" onRun={() => api.download(`/api/exams/${e.id}/grades.xlsx`, 'BangDiem.xlsx')}>⬇ Bảng điểm mẫu (Excel)</ActionButton>
      <FileButton className="btn sm" accept=".xlsx" label="⬆ Nhập từ Excel" onPick={async fl => { setFile(fl); try { setPre(await upload(true, fl)) } catch (x) { toast(x.message, 'red') } }} />
      <ActionButton className="btn sm primary" disabled={!dirty.size || anyBad} okMsg={r => `Đã lưu ${r.saved} SV có điểm, ${r.absent} vắng` + (r.analysis ? ' – đã phân tích' : '')} onRun={save}>
        Lưu {dirty.size ? `(${dirty.size} SV)` : ''} &amp; phân tích</ActionButton></>}>
      <div className="row gap wrap small mb">{items.map(it => <span key={it.question_id} className="pill">{it.order_index}. {it.title} – {it.points}đ · {it.clos}</span>)}</div>
      <div className="grid-wrap"><table className="grade-grid"><thead><tr><th>#</th><th>MSSV</th><th>Họ tên</th><th>Vắng</th>
        {items.map(it => <th key={it.question_id} title={it.title}>Câu {it.order_index}<small>/{it.points}</small></th>)}<th>Tổng</th></tr></thead>
        <tbody>{gb.data.students.map((s, i) => { const r = rows[s.student_id] || { scores: {} }; return <tr key={s.student_id} className={`${r.absent ? 'absent' : ''} ${dirty.has(s.student_id) ? 'dirty' : ''}`}>
          <td>{i + 1}</td><td>{s.student_code}</td><td>{s.full_name}{s.dropped && <Badge>Rút HP</Badge>}</td>
          <td><input type="checkbox" aria-label="Vắng" checked={!!r.absent} onChange={ev => set(s.student_id, { absent: ev.target.checked })} /></td>
          {items.map(it => { const v = val(s.student_id, it.question_id); return <td key={it.question_id}><input inputMode="decimal" disabled={r.absent} aria-label={`${s.student_code} câu ${it.order_index}`}
            className={badCell(v, it.points) ? 'bad' : ''} value={v} onChange={ev => set(s.student_id, { scores: { ...r.scores, [it.question_id]: ev.target.value } })} /></td> })}
          <td className="num-c">{total(s.student_id) === '' ? '—' : Number(total(s.student_id)).toFixed(2)}</td></tr> })}</tbody></table></div>
      <p className="muted small mt">Ô trống tính 0 điểm; dòng để trống hoàn toàn (không vắng) là chưa nhập điểm. Có thể dán điểm từ Excel vào từng ô hoặc nhập cả bảng bằng file.</p>
    </Card>
    {pre && <Modal title={`Nhập điểm từ ${file?.name}`} onClose={() => setPre(null)}>
      <p>{pre.n_rows} dòng SV · khớp {pre.n_matched} SV của lớp · {pre.columns.length} cột điểm.</p>
      {pre.errors?.length > 0 && <div className="alert red">{pre.errors.map((x, i) => <div key={i}>{x}</div>)}</div>}
      {pre.missing_students.length > 0 && <><p className="bad-t small">{pre.missing_students.length} SV chưa có trong lớp: {pre.missing_students.map(m => m.student_code).join(', ')}</p>
        <label className="row gap check"><input type="checkbox" checked={enroll} onChange={ev => setEnroll(ev.target.checked)} /> Ghi danh các SV này vào lớp</label></>}
      <div className="row"><span className="grow" /><ActionButton className="btn primary" disabled={pre.errors?.length > 0} okMsg={r => `Đã nhập điểm ${r.saved} SV, ${r.absent} vắng – đã phân tích`}
        onRun={async () => { const r = await upload(false); setPre(null); gb.reload(); reload(); return r }}>Nhập điểm</ActionButton></div>
    </Modal>}
  </>
}
