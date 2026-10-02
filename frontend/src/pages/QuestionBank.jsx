import { useEffect, useMemo, useState } from 'react'
import { api, auth } from '../api'
import { ActionButton, Badge, Card, Field, Loading, Modal, diClass, pClass } from '../components/ui'
import { useApi } from '../hooks'
import { ImportQuestions, TagFromFile } from '../components/QuestionImport'

export default function QuestionBank() {
  const sections = useApi('/api/class-sections').data
  const courses = useApi('/api/courses').data
  const bloom = useApi('/api/bloom-levels').data
  const isAdmin = auth.user()?.role === 'admin'
  // GV chỉ thấy các môn mình phụ trách (có lớp HP); Quản trị thấy mọi môn
  const myCourses = useMemo(() => {
    if (!courses) return null
    if (isAdmin) return courses
    const ids = new Set((sections || []).map(s => s.course_id))
    return courses.filter(c => ids.has(c.id))
  }, [courses, sections, isAdmin])
  const [courseId, setCourseId] = useState(null)
  useEffect(() => {
    if (courseId || !myCourses?.length || !sections) return
    setCourseId(sections[0]?.course_id ?? myCourses[0].id)
  }, [sections, myCourses, courseId])
  const course = useApi(courseId ? `/api/courses/${courseId}` : null).data
  const [flt, setFlt] = useState({ clo_id: '', outline_id: '', bloom_level_id: '', q: '', include_cancelled: false, untagged: false })
  const qs = new URLSearchParams(Object.entries({ course_id: courseId, ...flt }).filter(([, v]) => v !== '' && v !== false && v !== null)).toString()
  const list = useApi(courseId ? `/api/questions?${qs}` : null)
  const [edit, setEdit] = useState(null)
  const [dlg, setDlg] = useState(null)
  const untagged = useApi(courseId ? `/api/questions?course_id=${courseId}&untagged=true` : null)
  const nUntagged = untagged.data?.length || 0
  const reloadAll = () => { list.reload(); untagged.reload() }

  return (
    <>
      <div className="page-h">
        <div><h1>Ngân hàng câu hỏi</h1><p className="muted">UC-01 · Mỗi câu hỏi gắn chương, mức Bloom và một/nhiều CLO có trọng số (tổng = 1).</p></div>
        <div className="row gap wrap">
          <button className="btn" disabled={!course} onClick={() => setDlg('import')}>⬆ Nhập câu hỏi từ file</button>
          <button className="btn" disabled={!course} onClick={() => setDlg('tag')}>Gán CLO/Bloom từ file{nUntagged > 0 && <Badge tone="amber">{nUntagged} chưa gán</Badge>}</button>
          <button className="btn primary" disabled={!course} onClick={() => setEdit({})}>+ Thêm câu hỏi</button>
        </div>
      </div>
      {nUntagged > 0 && <div className="alert amber row gap wrap"><span className="grow">Có <b>{nUntagged}</b> câu hỏi chưa gán đủ CLO và mức Bloom – chưa đưa được vào đề.
        Gán từng câu (bấm Chi tiết) hoặc gán hàng loạt bằng file Excel.</span>
        <button className="btn sm" onClick={() => setFlt({ ...flt, untagged: !flt.untagged })}>{flt.untagged ? 'Hiện tất cả' : 'Chỉ xem câu chưa gán'}</button>
        <button className="btn sm primary" onClick={() => setDlg('tag')}>Gán từ file</button></div>}
      <Card>
        <div className="row gap wrap">
          <Field label="Môn học"><select value={courseId || ''} onChange={e => { setCourseId(Number(e.target.value)); setFlt(x => ({ ...x, clo_id: '', outline_id: '' })) }}>
            {myCourses?.map(c => <option key={c.id} value={c.id}>{c.course_code} – {c.course_name}</option>)}</select></Field>
          <Field label="CLO"><select value={flt.clo_id} onChange={e => setFlt({ ...flt, clo_id: e.target.value })}><option value="">Tất cả</option>
            {course?.clos.map(c => <option key={c.id} value={c.id}>{c.clo_code}</option>)}</select></Field>
          <Field label="Chương"><select value={flt.outline_id} onChange={e => setFlt({ ...flt, outline_id: e.target.value })}><option value="">Tất cả</option>
            {course?.outlines.map(o => <option key={o.id} value={o.id}>Chương {o.chapter_number}</option>)}</select></Field>
          <Field label="Mức Bloom"><select value={flt.bloom_level_id} onChange={e => setFlt({ ...flt, bloom_level_id: e.target.value })}><option value="">Tất cả</option>
            {bloom?.map(b => <option key={b.id} value={b.id}>{b.id}. {b.name_vi}</option>)}</select></Field>
          <Field label="Tìm nội dung"><input value={flt.q} onChange={e => setFlt({ ...flt, q: e.target.value })} placeholder="từ khóa…" /></Field>
          <label className="row gap check"><input type="checkbox" checked={flt.untagged} onChange={e => setFlt({ ...flt, untagged: e.target.checked })} /> Chỉ câu chưa gán</label>
          <label className="row gap check"><input type="checkbox" checked={flt.include_cancelled} onChange={e => setFlt({ ...flt, include_cancelled: e.target.checked })} /> Hiện câu đã Hủy</label>
        </div>
      </Card>
      <Card title={`${list.data?.length ?? 0} câu hỏi`}>
        <Loading {...list} />
        <table className="tbl">
          <thead><tr><th>ID</th><th>Nội dung</th><th>Chương</th><th>Bloom</th><th>CLO</th><th>Đáp án</th><th title="Số đề đã dùng">Đề</th><th>p TB</th><th>DI TB</th><th /></tr></thead>
          <tbody>{list.data?.map(q => (
            <tr key={q.id} className={q.is_cancelled ? 'cancel' : ''}>
              <td>{q.id}</td><td className="clip">{q.content}{q.is_cancelled && <Badge tone="red">Đã Hủy</Badge>}</td>
              <td>{q.chapter || '—'}</td><td>{q.bloom || '—'}</td>
              <td>{q.clos.length ? q.clos.map(c => c.weight < 1 ? `${c.clo_code}(${c.weight})` : c.clo_code).join(', ') : ''}{!q.tagged && <Badge tone="amber">Chưa gán</Badge>}</td>
              <td>{q.options.find(o => o.is_correct)?.label}</td><td>{q.usage?.n_exams}</td>
              <td className={`num-c ${pClass(q.usage?.avg_p)}`}>{q.usage?.avg_p ?? '—'}</td>
              <td className={`num-c ${diClass(q.usage?.avg_di)}`}>{q.usage?.avg_di ?? '—'}</td>
              <td><button className="btn sm" onClick={() => setEdit(q)}>Chi tiết</button></td>
            </tr>))}</tbody>
        </table>
      </Card>
      {dlg === 'import' && course && <ImportQuestions course={course} onClose={() => setDlg(null)} onDone={reloadAll} />}
      {dlg === 'tag' && course && <TagFromFile course={course} untagged={nUntagged} onClose={() => setDlg(null)} onDone={reloadAll} />}
      {edit && course && <QuestionForm q={edit} course={course} bloom={bloom || []} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); reloadAll() }} />}
    </>
  )
}

function QuestionForm({ q, course, bloom, onClose, onSaved }) {
  const locked = (q.usage?.n_results || 0) > 0
  const [f, setF] = useState(() => ({
    // câu mới: gợi ý chương 1, Bloom 2; câu nhập từ file chưa gán: để trống để GV chủ động chọn (không gán ngầm)
    content: q.content || '', outline_id: q.id ? (q.outline_id || '') : (course.outlines[0]?.id || ''),
    bloom_level_id: q.id ? (q.bloom_level_id || '') : 2,
    options: q.options?.map(o => ({ content: o.content, is_correct: o.is_correct })) || [0, 1, 2, 3].map(i => ({ content: '', is_correct: i === 0 })),
    clos: Object.fromEntries((q.clos || []).map(c => [c.clo_id, c.weight])),
  }))
  const [reason, setReason] = useState('')
  const wsum = useMemo(() => Object.values(f.clos).reduce((a, b) => a + Number(b || 0), 0), [f.clos])
  const setOpt = (i, patch) => setF(x => ({ ...x, options: x.options.map((o, j) => j === i ? { ...o, ...patch } : patch.is_correct ? { ...o, is_correct: false } : o) }))
  const body = () => ({ course_id: course.id, outline_id: f.outline_id ? Number(f.outline_id) : null, bloom_level_id: Number(f.bloom_level_id), content: f.content,
    options: f.options, clos: Object.entries(f.clos).map(([clo_id, weight]) => ({ clo_id: Number(clo_id), weight: Number(weight) })) })
  const problem = !f.content.trim() ? 'Chưa nhập nội dung câu hỏi'
    : f.options.some(o => !o.content.trim()) ? 'Còn phương án để trống'
    : !f.bloom_level_id ? 'Chưa chọn mức Bloom'
    : !Object.keys(f.clos).length ? 'Chưa gán CLO'
    : Object.values(f.clos).some(w => !(Number(w) > 0 && Number(w) <= 1)) ? 'Trọng số CLO phải trong khoảng (0; 1]'
    : Math.abs(wsum - 1) > 1e-6 ? 'Tổng trọng số CLO phải bằng 1' : null
  const save = async () => { q.id ? await api.put(`/api/questions/${q.id}`, body()) : await api.post('/api/questions', body()); onSaved() }

  return (
    <Modal title={q.id ? `Câu hỏi #${q.id}` : 'Thêm câu hỏi'} onClose={onClose} wide>
      {locked && <div className="alert amber">Câu hỏi đã có {q.usage.n_results} kết quả làm bài (p TB = {q.usage.avg_p}, DI TB = {q.usage.avg_di}) nên
        <b> không được sửa nội dung/đáp án</b> để giữ toàn vẹn minh chứng. Nếu câu có vấn đề, hãy <b>Hủy</b> và tạo câu mới.</div>}
      <Field label="Nội dung câu hỏi"><textarea rows={3} disabled={locked} value={f.content} onChange={e => setF({ ...f, content: e.target.value })} /></Field>
      <div className="grid2">
        <Field label="Chương (đề cương)"><select disabled={locked} value={f.outline_id || ''} onChange={e => setF({ ...f, outline_id: e.target.value })}>
          <option value="">— Chưa chọn —</option>
          {course.outlines.map(o => <option key={o.id} value={o.id}>Chương {o.chapter_number}. {o.chapter_name}</option>)}</select></Field>
        <Field label="Mức Bloom"><select disabled={locked} value={f.bloom_level_id} onChange={e => setF({ ...f, bloom_level_id: e.target.value })}>
          <option value="">— Chưa chọn —</option>
          {bloom.map(b => <option key={b.id} value={b.id}>{b.id}. {b.name_vi} ({b.code})</option>)}</select></Field>
      </div>
      <h4>Phương án trả lời <small className="muted">(chọn đúng một đáp án)</small></h4>
      {f.options.map((o, i) => (
        <div key={i} className="row gap opt">
          <input type="radio" name="correct" disabled={locked} checked={o.is_correct} onChange={() => setOpt(i, { is_correct: true })} />
          <b>{'ABCDEFGHIJ'[i]}.</b>
          <input className="grow" disabled={locked} value={o.content} onChange={e => setOpt(i, { content: e.target.value })} />
          {!locked && f.options.length > 2 && <button className="btn ghost sm" onClick={() => setF(x => ({ ...x, options: x.options.filter((_, j) => j !== i) }))}>✕</button>}
        </div>))}
      {!locked && f.options.length < 10 && <button className="btn sm" onClick={() => setF(x => ({ ...x, options: [...x.options, { content: '', is_correct: false }] }))}>+ Phương án</button>}
      <h4>Ánh xạ CLO và trọng số <small className={Math.abs(wsum - 1) < 1e-6 ? 'ok-t' : 'bad-t'}>(tổng = {wsum.toFixed(2)})</small></h4>
      <div className="grid2">{course.clos.map(c => (
        <div key={c.id} className="row gap clo-w">
          <input type="checkbox" disabled={locked} checked={f.clos[c.id] !== undefined}
            onChange={e => setF(x => { const m = { ...x.clos }; e.target.checked ? m[c.id] = 1 : delete m[c.id]; return { ...x, clos: m } })} />
          <span className="grow"><b>{c.clo_code}</b> <small className="muted">{c.description}</small></span>
          {f.clos[c.id] !== undefined && <input className="num" type="number" step="0.1" min="0.1" max="1" disabled={locked} value={f.clos[c.id]}
            onChange={e => setF(x => ({ ...x, clos: { ...x.clos, [c.id]: e.target.value } }))} />}
        </div>))}</div>
      <div className="row gap mt wrap">
        {q.id && !q.is_cancelled && <>
          <input placeholder="Lý do Hủy câu hỏi…" value={reason} onChange={e => setReason(e.target.value)} />
          <ActionButton className="btn danger" disabled={reason.trim().length < 3} okMsg="Đã Hủy câu hỏi" confirm="Hủy câu hỏi này? Câu đã Hủy bị loại khỏi phân tích CLO và không đưa được vào đề mới." onRun={async () => { await api.patch(`/api/questions/${q.id}/cancel`, { reason }); onSaved() }}>Hủy câu hỏi</ActionButton>
        </>}
        {q.is_cancelled && <span className="muted">Lý do Hủy: {q.cancel_reason}</span>}
        {q.id && !q.usage?.n_exams && <ActionButton className="btn ghost" okMsg="Đã xóa" confirm={`Xóa hẳn câu hỏi #${q.id}? Thao tác không hoàn tác được.`} onRun={async () => { await api.del(`/api/questions/${q.id}`); onSaved() }}>Xóa</ActionButton>}
        <span className="grow" />
        {!locked && problem && <small className="bad-t">{problem}</small>}
        {!locked && <ActionButton className="btn primary" disabled={!!problem} okMsg="Đã lưu câu hỏi" onRun={save}>Lưu</ActionButton>}
      </div>
    </Modal>
  )
}
