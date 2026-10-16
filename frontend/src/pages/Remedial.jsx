// Phụ đạo: mỗi SV sai bao nhiêu câu → bấm SV xem danh sách câu sai → tạo bài KT phụ đạo riêng (một SV hoặc nhóm SV).
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { ActionButton, Badge, Card, Crumbs, Field, Loading, Modal, Stat } from '../components/ui'
import { useApi } from '../hooks'

export default function Remedial() {
  const { id } = useParams()
  const cs = useApi('/api/class-sections').data?.find(x => String(x.id) === id)
  const [exams, setExams] = useState(null)       // null = mọi bài đã phân tích
  const ov = useApi(`/api/class-sections/${id}/remedial${exams ? `?exam_ids=${exams.join(',')}` : ''}`)
  const [open, setOpen] = useState(null)
  const [pick, setPick] = useState([])
  const [mk, setMk] = useState(false)
  const [view, setView] = useState('students')
  const d = ov.data
  const sel = exams || d?.selected || []
  const weak = useMemo(() => (d?.students || []).filter(s => s.n_wrong > 0), [d])
  return <>
    <div className="page-h"><div><Crumbs items={[['/', 'Môn học của tôi'], cs && [`/courses/${cs.course_id}`, cs.course_code], cs && [`/sections/${id}`, cs.section_code], [null, 'Phụ đạo']]} />
      <h1>Phụ đạo theo câu trả lời sai</h1>
      <p className="muted">Mỗi sinh viên làm sai bao nhiêu câu trên các bài đã chọn; bấm vào SV để xem danh sách câu sai và tạo bài kiểm tra phụ đạo riêng.</p></div>
      <button className="btn primary" disabled={!pick.length} onClick={() => setMk(true)}>{pick.length ? `Tạo bài phụ đạo cho ${pick.length} SV đã chọn` : 'Chọn SV để tạo bài phụ đạo'}</button></div>
    <Loading {...ov} />
    {d && <>
      <Card title="Bài kiểm tra dùng để tính">
        <div className="row gap wrap">{d.exams.map(e => <label key={e.id} className="row gap check">
          <input type="checkbox" checked={sel.includes(e.id)} onChange={ev => setExams(ev.target.checked ? [...sel, e.id] : sel.filter(x => x !== e.id))} />
          {e.exam_title} <small className="muted">({e.n_questions} câu)</small>{e.parent_exam_id && <Badge tone="amber">Phụ đạo</Badge>}</label>)}</div>
      </Card>
      <div className="stats">
        <Stat label="SV có làm bài" value={d.students.length} />
        <Stat label="SV có câu sai" value={weak.length} tone="amber" />
        <Stat label="Số câu sai trung bình" value={d.students.length ? (d.students.reduce((a, s) => a + s.n_wrong, 0) / d.students.length).toFixed(1) : '—'} />
        <Stat label="Câu bị sai nhiều nhất" value={d.questions[0] ? `${d.questions[0].n_wrong} SV` : '—'} sub={d.questions[0]?.content.slice(0, 60)} tone="red" />
      </div>
      <div className="tabs">{[['students', 'Theo sinh viên'], ['questions', 'Theo câu hỏi']].map(([k, l]) =>
        <button key={k} className={view === k ? 'on' : ''} onClick={() => setView(k)}>{l}</button>)}</div>
      {view === 'students' && <Card title="Số câu sai của từng sinh viên" actions={<span className="row gap">
        <button className="btn sm" onClick={() => setPick(weak.filter(s => s.weak_clos.length).map(s => s.student_id))}>Chọn SV chưa đạt CLO</button>
        {pick.length > 0 && <button className="btn sm ghost" onClick={() => setPick([])}>Bỏ chọn</button>}</span>}>
        <table className="tbl"><thead><tr><th style={{ width: 34 }} /><th>MSSV</th><th>Họ tên</th><th className="num-c">Câu sai</th><th className="num-c">Bỏ trống</th><th className="num-c">Tỷ lệ sai</th><th>CLO chưa đạt</th><th /></tr></thead>
          <tbody>{d.students.map(s => <tr key={s.student_id} className={`click ${pick.includes(s.student_id) ? 'sel' : ''}`} onClick={() => setOpen(s)}>
            <td onClick={e => e.stopPropagation()}><input type="checkbox" aria-label={`Chọn ${s.student_code}`} checked={pick.includes(s.student_id)}
              onChange={e => setPick(p => e.target.checked ? [...p, s.student_id] : p.filter(x => x !== s.student_id))} /></td>
            <td>{s.student_code}</td><td><b>{s.full_name}</b></td><td className={`num-c ${s.wrong_pct >= 50 ? 'bad' : s.wrong_pct >= 30 ? 'warn' : ''}`}>{s.n_wrong}/{s.n_items}</td>
            <td className="num-c">{s.n_blank}</td><td className="num-c">{s.wrong_pct}%</td>
            <td>{s.weak_clos.map(c => <span key={c} className="pill red">{c}</span>)}</td>
            <td><button className="btn sm" onClick={e => { e.stopPropagation(); setOpen(s) }}>Câu sai ›</button></td></tr>)}</tbody></table>
      </Card>}
      {view === 'questions' && <Card title="Số sinh viên làm sai từng câu">
        <table className="tbl"><thead><tr><th>Bài</th><th>Câu</th><th>Nội dung</th><th>CLO</th><th className="num-c">SV sai</th><th className="num-c">Tỷ lệ sai</th></tr></thead>
          <tbody>{d.questions.map(q => <tr key={`${q.exam_id}-${q.question_id}`}><td className="small">{d.exams.find(e => e.id === q.exam_id)?.exam_title}</td><td>{q.order_index}</td>
            <td className="clip" title={q.content}>{q.content}</td><td>{q.clos}</td><td className="num-c">{q.n_wrong}/{q.n_students}</td>
            <td className={`num-c ${q.wrong_pct >= 60 ? 'bad' : q.wrong_pct >= 40 ? 'warn' : ''}`}>{q.wrong_pct}%</td></tr>)}</tbody></table>
      </Card>}
    </>}
    {open && <WrongList cs={id} s={open} exams={sel} onClose={() => setOpen(null)} onMake={() => { setPick([open.student_id]); setOpen(null); setMk(true) }} />}
    {mk && <MakeRemedial cs={id} ids={pick} exams={sel} students={d?.students || []} onClose={() => setMk(false)} />}
  </>
}

function WrongList({ cs, s, exams, onClose, onMake }) {
  const r = useApi(`/api/class-sections/${cs}/remedial/students/${s.student_id}?exam_ids=${exams.join(',')}`)
  return <Modal wide title={`Câu trả lời sai – ${s.full_name} (${s.student_code})`} onClose={onClose}>
    <Loading {...r} />
    {r.data && <>
      <p className="muted small">{r.data.wrong.length} câu sai / bỏ trống / chưa đủ điểm. CLO chưa đạt: {s.weak_clos.join(', ') || 'không'}.</p>
      <div className="scroll tall"><table className="tbl compact"><thead><tr><th>Bài KT</th><th>Câu</th><th>Nội dung</th><th>SV chọn</th><th>Đáp án đúng</th><th>CLO</th><th>Chương</th></tr></thead>
        <tbody>{r.data.wrong.map((w, i) => <tr key={i}><td className="small">{w.exam_title}</td><td>{w.version_pos || w.order_index}</td><td className="wrap-cell">{w.content}</td>
          <td className="ans-bad">{w.question_type === 'manual' ? `${w.score_earned}/${w.points} đ` : w.chosen_label ? `${w.chosen_label}. ${w.chosen_content}` : <span className="ans-blank">(bỏ trống)</span>}</td>
          <td className="ans-ok">{w.correct_label ? `${w.correct_label}. ${w.correct_content}` : '—'}</td><td>{w.clos}</td>
          <td className="small">{w.chapter_number ? `Ch. ${w.chapter_number}` : '—'}</td></tr>)}</tbody></table></div>
      <div className="row mt"><span className="grow" /><button className="btn primary" onClick={onMake}>Tạo bài phụ đạo cho SV này</button></div>
    </>}
  </Modal>
}

function MakeRemedial({ cs, ids, exams, students, onClose }) {
  const nav = useNavigate()
  const names = students.filter(s => ids.includes(s.student_id))
  const [f, setF] = useState({ exam_title: names.length === 1 ? `Phụ đạo – ${names[0].full_name}` : `Phụ đạo – nhóm ${names.length} SV`, exam_type: 'online',
    include_wrong: true, similar_per_question: 1, max_questions: 30, max_score: 10 })
  return <Modal title="Tạo bài kiểm tra phụ đạo" onClose={onClose}>
    <p className="small">Cho: {names.map(s => s.student_code).join(', ')}</p>
    <Field label="Tên bài"><input value={f.exam_title} onChange={e => setF({ ...f, exam_title: e.target.value })} /></Field>
    <div className="row gap wrap">
      <Field label="Hình thức"><select value={f.exam_type} onChange={e => setF({ ...f, exam_type: e.target.value })}><option value="online">Trực tuyến (Moodle)</option><option value="paper">Trên giấy</option></select></Field>
      <Field label="Câu tương tự / câu sai" hint="cùng CLO, ưu tiên cùng chương, chưa từng dùng ở lớp"><select value={f.similar_per_question} onChange={e => setF({ ...f, similar_per_question: Number(e.target.value) })}>
        {[0, 1, 2, 3].map(n => <option key={n} value={n}>{n}</option>)}</select></Field>
      <Field label="Tối đa số câu"><input className="num" type="number" value={f.max_questions} onChange={e => setF({ ...f, max_questions: Number(e.target.value) })} /></Field>
    </div>
    <label className="row gap check"><input type="checkbox" checked={f.include_wrong} onChange={e => setF({ ...f, include_wrong: e.target.checked })} /> Đưa lại chính các câu SV đã làm sai</label>
    <p className="muted small">Bài phụ đạo mặc định không gộp vào minh chứng CLO (BM6). Sau khi tạo, phát hành lên Moodle hoặc in đề như bài thường.</p>
    <div className="row"><span className="grow" /><ActionButton className="btn primary" okMsg={r => `Đã tạo bài phụ đạo ${r.n_questions} câu (${r.n_wrong_reused} câu đã sai, ${r.n_similar} câu tương tự)`}
      onRun={async () => { const r = await api.post(`/api/class-sections/${cs}/remedial-exams`, { ...f, student_ids: ids, exam_ids: exams }); nav(`/exams/${r.id}`); return r }}>Tạo bài</ActionButton></div>
  </Modal>
}
