// Ôn tập: xem SV nào yếu ở chương/câu nào → chọn một SV hoặc cả nhóm cùng yếu một chương → tạo bài kiểm tra lại đúng phần đó.
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
  const prog = useApi(`/api/class-sections/${id}/remedial-exams`)      // góp ý F5: tiến bộ sau phụ đạo
  const [open, setOpen] = useState(null)
  const [pick, setPick] = useState([])
  const [mk, setMk] = useState(false)
  const [view, setView] = useState('chapters')
  const [chapPick, setChapPick] = useState([])
  const [outlines, setOutlines] = useState([])      // chương được chọn khi tạo bài cho nhóm
  const d = ov.data
  const sel = exams || d?.selected || []
  const weak = useMemo(() => (d?.students || []).filter(s => s.n_wrong > 0), [d])
  return <>
    <div className="page-h"><div><Crumbs items={[['/', 'Môn học của tôi'], cs && [`/courses/${cs.course_id}`, cs.course_code], cs && [`/sections/${id}`, cs.section_code], [null, 'Ôn tập']]} />
      <h1>Ôn tập cho sinh viên còn yếu</h1>
      <p className="muted">Xem sinh viên nào còn yếu ở chương nào, rồi tạo bài kiểm tra lại đúng phần kiến thức đó cho một sinh viên hoặc cả nhóm. Hệ thống không đánh giá chuẩn đầu ra (CLO) riêng cho từng sinh viên; chỉ dựa vào các câu làm sai.</p></div>
      <button className="btn primary" disabled={!pick.length} onClick={() => { setOutlines([]); setMk(true) }}>{pick.length ? `Tạo bài ôn tập cho ${pick.length} SV đã chọn` : 'Chọn SV để tạo bài ôn tập'}</button></div>
    <Loading {...ov} />
    {d && <>
      <Card title="Bài kiểm tra dùng để tính">
        <div className="row gap wrap">{d.exams.map(e => <label key={e.id} className="row gap check">
          <input type="checkbox" checked={sel.includes(e.id)} onChange={ev => setExams(ev.target.checked ? [...sel, e.id] : sel.filter(x => x !== e.id))} />
          {e.exam_title} <small className="muted">({e.n_questions} câu)</small>{e.parent_exam_id && <Badge tone="amber">Ôn tập</Badge>}</label>)}</div>
      </Card>
      <div className="stats">
        <Stat label="SV có làm bài" value={d.students.length} />
        <Stat label="SV có câu sai" value={weak.length} tone="amber" />
        <Stat label="Số câu sai trung bình" value={d.students.length ? (d.students.reduce((a, s) => a + s.n_wrong, 0) / d.students.length).toFixed(1) : '—'} />
        <Stat label="Câu bị sai nhiều nhất" value={d.questions[0] ? `${d.questions[0].n_wrong} SV` : '—'} sub={d.questions[0]?.content.slice(0, 60)} tone="red" />
      </div>
      <div className="tabs">{[['chapters', 'Theo chương (tạo bài cho nhóm)'], ['students', 'Theo sinh viên'], ['questions', 'Theo câu hỏi']].map(([k, l]) =>
        <button key={k} className={view === k ? 'on' : ''} onClick={() => setView(k)}>{l}</button>)}</div>
      {view === 'chapters' && <Card title="Chương nào nhiều sinh viên còn yếu?">
        <p className="muted small">Tích chọn một hoặc nhiều chương, hệ thống gom các sinh viên còn sai ở những chương đó và tạo bài kiểm tra lại gồm chính các câu đã sai cùng một số câu tương tự.</p>
        {d.chapters.length === 0 ? <div className="alert green">Chưa có chương nào có sinh viên làm sai.</div> :
          <table className="tbl"><thead><tr><th style={{ width: 34 }} /><th>Chương</th><th className="num-c">SV còn yếu</th><th className="num-c">Tỷ lệ SV</th><th className="num-c">Lượt sai</th></tr></thead>
            <tbody>{d.chapters.map(c => <tr key={c.label} className={chapPick.includes(c.label) ? 'sel' : ''}>
              <td><input type="checkbox" aria-label={`Chọn ${c.label}`} checked={chapPick.includes(c.label)} onChange={e => setChapPick(p => e.target.checked ? [...p, c.label] : p.filter(x => x !== c.label))} /></td>
              <td><b>{c.label}</b></td><td className="num-c">{c.n_students}</td><td className="num-c">{c.pct_students}%</td><td className="num-c">{c.n_wrong}</td></tr>)}</tbody></table>}
        <div className="row mt"><span className="grow" /><button className="btn primary" disabled={!chapPick.length}
          onClick={() => { const cs = d.chapters.filter(c => chapPick.includes(c.label)); setPick([...new Set(cs.flatMap(c => c.student_ids))]); setOutlines(cs.map(c => c.outline_id).filter(Boolean)); setMk(true) }}>
          {chapPick.length ? `Tạo bài kiểm tra lại cho nhóm SV yếu ${chapPick.length} chương đã chọn` : 'Chọn chương để tạo bài cho nhóm'}</button></div>
      </Card>}
      {view === 'students' && <Card title="Số câu sai của từng sinh viên" actions={<span className="row gap">
        <button className="btn sm" onClick={() => setPick(weak.map(s => s.student_id))}>Chọn mọi SV có câu sai</button>
        {pick.length > 0 && <button className="btn sm ghost" onClick={() => setPick([])}>Bỏ chọn</button>}</span>}>
        <table className="tbl"><thead><tr><th style={{ width: 34 }} /><th>MSSV</th><th>Họ tên</th><th className="num-c">Câu sai</th><th className="num-c">Bỏ trống</th><th className="num-c">Tỷ lệ sai</th><th>Chương còn yếu</th><th /></tr></thead>
          <tbody>{d.students.map(s => <tr key={s.student_id} className={`click ${pick.includes(s.student_id) ? 'sel' : ''}`} onClick={() => setOpen(s)}>
            <td onClick={e => e.stopPropagation()}><input type="checkbox" aria-label={`Chọn ${s.student_code}`} checked={pick.includes(s.student_id)}
              onChange={e => setPick(p => e.target.checked ? [...p, s.student_id] : p.filter(x => x !== s.student_id))} /></td>
            <td>{s.student_code}</td><td><b>{s.full_name}</b></td><td className={`num-c ${s.wrong_pct >= 50 ? 'bad' : s.wrong_pct >= 30 ? 'warn' : ''}`}>{s.n_wrong}/{s.n_items}</td>
            <td className="num-c">{s.n_blank}</td><td className="num-c">{s.wrong_pct}%</td>
            <td>{s.weak_chapters.slice(0, 3).map(c => <span key={c} className="pill amber">{c}</span>)}{s.weak_chapters.length > 3 && <span className="muted small"> +{s.weak_chapters.length - 3}</span>}</td>
            <td><button className="btn sm" onClick={e => { e.stopPropagation(); setOpen(s) }}>Câu sai ›</button></td></tr>)}</tbody></table>
      </Card>}
      {view === 'questions' && <Card title="Số sinh viên làm sai từng câu">
        <table className="tbl"><thead><tr><th>Bài</th><th>Câu</th><th>Nội dung</th><th className="num-c">SV sai</th><th className="num-c">Tỷ lệ sai</th></tr></thead>
          <tbody>{d.questions.map(q => <tr key={`${q.exam_id}-${q.question_id}`}><td className="small">{d.exams.find(e => e.id === q.exam_id)?.exam_title}</td><td>{q.order_index}</td>
            <td className="clip" title={q.content}>{q.content}</td><td className="num-c">{q.n_wrong}/{q.n_students}</td>
            <td className={`num-c ${q.wrong_pct >= 60 ? 'bad' : q.wrong_pct >= 40 ? 'warn' : ''}`}>{q.wrong_pct}%</td></tr>)}</tbody></table>
      </Card>}
    </>}
    {prog.data?.length > 0 && <Progress list={prog.data} />}
    {open && <WrongList cs={id} s={open} exams={sel} onClose={() => setOpen(null)} onMake={() => { setPick([open.student_id]); setOutlines([]); setOpen(null); setMk(true) }} />}
    {mk && <MakeRemedial cs={id} ids={pick} outlines={outlines} exams={sel} students={d?.students || []} onClose={() => setMk(false)} />}
  </>
}

const pctCell = v => v == null ? <span className="muted">—</span> : `${v}%`
const ST_VI = { finished: 'Đã nộp', inprogress: 'Đang làm', not_started: 'Chưa làm' }

// Mỗi bài phụ đạo: SV được giao, điểm trên chính các câu đã đưa lại ở bài trước → ở bài phụ đạo
function Progress({ list }) {
  return <Card title={`Bài ôn tập đã giao (${list.length}) – tiến bộ của sinh viên`}>
    <p className="muted small">"Trước": tỷ lệ điểm trên các câu của bài ôn tập mà SV đã làm ở bài kiểm tra chính thức. "Sau (cùng câu)": tỷ lệ điểm trên chính các câu đó ở bài ôn tập. "Cả bài": gồm cả câu tương tự.</p>
    {list.map(x => <details key={x.exam_id} className="mb" open={list.length === 1}>
      <summary className="row gap wrap"><Link to={`/exams/${x.exam_id}`} onClick={e => e.stopPropagation()}><b>{x.exam_title}</b></Link>
        <span className="small muted">{x.n_questions} câu · {x.n_done}/{x.n_targets} SV đã nộp{x.moodle_quiz_id ? ` · Quiz ${x.moodle_quiz_id}` : ''}</span>
        {x.avg_gain != null && <Badge tone={x.avg_gain > 0 ? 'green' : x.avg_gain < 0 ? 'red' : 'gray'}>{x.avg_gain > 0 ? '+' : ''}{x.avg_gain} điểm %</Badge>}</summary>
      <table className="tbl compact"><thead><tr><th>MSSV</th><th>Họ tên</th><th>Trạng thái</th><th className="num-c">Câu đưa lại</th><th className="num-c">Trước</th><th className="num-c">Sau (cùng câu)</th><th className="num-c">Thay đổi</th><th className="num-c">Cả bài</th></tr></thead>
        <tbody>{x.students.map(s => <tr key={s.student_id}><td>{s.student_code}</td><td>{s.full_name}</td>
          <td><Badge tone={s.status === 'finished' ? 'green' : 'gray'}>{ST_VI[s.status] || s.status}</Badge></td><td className="num-c">{s.n_reused}</td>
          <td className="num-c">{pctCell(s.before_pct)}</td><td className="num-c">{pctCell(s.after_same_pct)}</td>
          <td className={`num-c ${s.gain > 0 ? 'pos' : s.gain < 0 ? 'neg' : ''}`}>{s.gain == null ? '—' : `${s.gain > 0 ? '+' : ''}${s.gain}`}</td>
          <td className="num-c">{pctCell(s.after_pct)}</td></tr>)}</tbody></table>
    </details>)}
  </Card>
}

function WrongList({ cs, s, exams, onClose, onMake }) {
  const r = useApi(`/api/class-sections/${cs}/remedial/students/${s.student_id}?exam_ids=${exams.join(',')}`)
  return <Modal wide title={`Câu trả lời sai – ${s.full_name} (${s.student_code})`} onClose={onClose}>
    <Loading {...r} />
    {r.data && <>
      <p className="muted small">{r.data.wrong.length} câu sai / bỏ trống / chưa đủ điểm. Chương còn yếu: {s.weak_chapters.join('; ') || 'không'}.</p>
      <div className="scroll tall"><table className="tbl compact"><thead><tr><th>Bài kiểm tra</th><th>Câu</th><th>Nội dung</th><th>SV chọn</th><th>Đáp án đúng</th><th>Chương</th></tr></thead>
        <tbody>{r.data.wrong.map((w, i) => <tr key={i}><td className="small">{w.exam_title}</td><td>{w.version_pos || w.order_index}</td><td className="wrap-cell">{w.content}</td>
          <td className="ans-bad">{w.question_type === 'manual' ? `${w.score_earned}/${w.points} đ` : w.chosen_label ? `${w.chosen_label}. ${w.chosen_content}` : <span className="ans-blank">(bỏ trống)</span>}</td>
          <td className="ans-ok">{w.correct_label ? `${w.correct_label}. ${w.correct_content}` : '—'}</td>
          <td className="small">{w.chapter_number ? `Ch. ${w.chapter_number}` : '—'}</td></tr>)}</tbody></table></div>
      <div className="row mt"><span className="grow" /><button className="btn primary" onClick={onMake}>Tạo bài ôn tập cho SV này</button></div>
    </>}
  </Modal>
}

function MakeRemedial({ cs, ids, outlines, exams, students, onClose }) {
  const nav = useNavigate()
  const names = students.filter(s => ids.includes(s.student_id))
  const [f, setF] = useState({ exam_title: names.length === 1 ? `Ôn tập – ${names[0].full_name}` : `Ôn tập – nhóm ${names.length} SV`, exam_type: 'online',
    include_wrong: true, similar_per_question: 1, max_questions: 30, max_score: 10 })
  return <Modal title="Tạo bài ôn tập" onClose={onClose}>
    <p className="small">Dành cho {names.length} sinh viên: {names.map(s => s.student_code).join(', ')}{outlines.length > 0 && <><br />Chỉ lấy các câu sai thuộc {outlines.length} chương đã chọn.</>}</p>
    <Field label="Tên bài"><input value={f.exam_title} onChange={e => setF({ ...f, exam_title: e.target.value })} /></Field>
    <div className="row gap wrap">
      <Field label="Hình thức"><select value={f.exam_type} onChange={e => setF({ ...f, exam_type: e.target.value })}><option value="online">Trực tuyến (Moodle)</option><option value="paper">Trên giấy</option></select></Field>
      <Field label="Câu tương tự / câu sai" hint="câu mới cùng nội dung, ưu tiên cùng chương, lớp chưa từng làm"><select value={f.similar_per_question} onChange={e => setF({ ...f, similar_per_question: Number(e.target.value) })}>
        {[0, 1, 2, 3].map(n => <option key={n} value={n}>{n}</option>)}</select></Field>
      <Field label="Tối đa số câu"><input className="num" type="number" value={f.max_questions} onChange={e => setF({ ...f, max_questions: Number(e.target.value) })} /></Field>
    </div>
    <label className="row gap check"><input type="checkbox" checked={f.include_wrong} onChange={e => setF({ ...f, include_wrong: e.target.checked })} /> Đưa lại chính các câu SV đã làm sai</label>
    <p className="muted small">Bài ôn tập chỉ để sinh viên luyện lại kiến thức, không tính vào kết quả chuẩn đầu ra của lớp. Khi tạo bài trên Moodle, chỉ các sinh viên được giao mới thấy và làm được.</p>
    <div className="row"><span className="grow" /><ActionButton className="btn primary" okMsg={r => `Đã tạo bài ôn tập ${r.n_questions} câu (${r.n_wrong_reused} câu đã sai, ${r.n_similar} câu tương tự)`}
      onRun={async () => { const r = await api.post(`/api/class-sections/${cs}/remedial-exams`, { ...f, student_ids: ids, exam_ids: exams, outline_ids: outlines }); nav(`/exams/${r.id}`); return r }}>Tạo bài</ActionButton></div>
  </Modal>
}
