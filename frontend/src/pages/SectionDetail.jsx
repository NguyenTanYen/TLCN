import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, STATUS_VI } from '../api'
import { ActionButton, Badge, Card, Field, Loading, Modal, useToast } from '../components/ui'
import { useApi } from '../hooks'

const TYPE_VI = { online: 'Trực tuyến (Moodle)', paper: 'Trên giấy' }
const ASSESS_VI = { process: 'Quá trình', final: 'Cuối kỳ' }

export default function SectionDetail() {
  const { id } = useParams()
  const cs = useApi('/api/class-sections').data?.find(x => String(x.id) === id)
  const exams = useApi(`/api/class-sections/${id}/exams`)
  const students = useApi(`/api/class-sections/${id}/students`)
  const [tab, setTab] = useState('exams')
  const [creating, setCreating] = useState(false)
  const toast = useToast()

  const importStudents = async file => {
    try { const r = await api.upload(`/api/class-sections/${id}/students/import`, file); toast(`Đã thêm ${r.added} SV vào lớp`); students.reload() }
    catch (e) { toast(e.message, 'red') }
  }

  return (
    <>
      <div className="page-h">
        <div><div className="crumb"><Link to="/">Lớp học phần</Link> / {cs?.section_code}</div>
          <h1>{cs?.course_name}</h1><p className="muted">{cs?.course_code} · {cs?.semester} · GV {cs?.lecturer}</p></div>
        <div className="row gap"><Link className="btn" to={`/sections/${id}/clo`}>Kết quả CĐR (BM6)</Link>
          <button className="btn primary" onClick={() => setCreating(true)}>+ Tạo bài kiểm tra</button></div>
      </div>
      <div className="tabs">
        <button className={tab === 'exams' ? 'on' : ''} onClick={() => setTab('exams')}>Bài kiểm tra ({exams.data?.length ?? 0})</button>
        <button className={tab === 'students' ? 'on' : ''} onClick={() => setTab('students')}>Danh sách SV ({students.data?.length ?? 0})</button>
      </div>
      {tab === 'exams' && <Card>
        <Loading {...exams} />
        <table className="tbl">
          <thead><tr><th>#</th><th>Tên bài KT</th><th>Hình thức</th><th>Loại minh chứng</th><th>Ngày</th><th>Số câu</th><th>Bài làm</th><th>Trạng thái</th><th /></tr></thead>
          <tbody>{exams.data?.map(e => (
            <tr key={e.id}>
              <td>{e.id}</td><td><b>{e.exam_title}</b></td><td>{TYPE_VI[e.exam_type]}</td><td>{ASSESS_VI[e.assessment_type]}</td>
              <td>{e.exam_date || '—'}</td><td>{e.questions.length}</td><td>{e.n_attempts} dự thi · {e.n_absent} vắng</td>
              <td><Badge tone={e.status === 'Analyzed' ? 'green' : e.status === 'Draft' ? 'gray' : 'blue'}>{STATUS_VI[e.status]}</Badge>
                {e.publish_flag && <Badge tone="amber">Đã công bố</Badge>}</td>
              <td><Link className="btn sm" to={`/exams/${e.id}`}>Mở</Link></td>
            </tr>))}
          </tbody>
        </table>
      </Card>}
      {tab === 'students' && <Card actions={<label className="btn sm">Nhập CSV (student_code, full_name, class_name)
        <input type="file" accept=".csv" hidden onChange={e => e.target.files[0] && importStudents(e.target.files[0])} /></label>}>
        <Loading {...students} />
        <table className="tbl"><thead><tr><th>MSSV</th><th>Họ tên</th><th>Lớp</th><th>Moodle user</th><th>Trạng thái</th></tr></thead>
          <tbody>{students.data?.map(s => <tr key={s.id}><td>{s.student_code}</td><td>{s.full_name}</td><td>{s.class_name}</td>
            <td>{s.moodle_user_id ?? '—'}</td><td>{s.status === 'active' ? 'Đang học' : 'Rút HP'}</td></tr>)}</tbody></table>
      </Card>}
      {creating && cs && <CreateExam cs={cs} onClose={() => setCreating(false)} />}
    </>
  )
}

function CreateExam({ cs, onClose }) {
  const nav = useNavigate()
  const bank = useApi(`/api/questions?course_id=${cs.course_id}`)
  const [f, setF] = useState({ exam_title: '', exam_type: 'online', assessment_type: 'final', exam_date: '', duration_minutes: 45, max_score: 10 })
  const [picked, setPicked] = useState({}) // question_id -> points
  const [filter, setFilter] = useState('')
  const list = useMemo(() => (bank.data || []).filter(q => !q.is_cancelled &&
    (!filter || q.clos.some(c => c.clo_code === filter) || q.chapter === filter)), [bank.data, filter])
  const chips = useMemo(() => [...new Set((bank.data || []).flatMap(q => [...q.clos.map(c => c.clo_code), q.chapter]).filter(Boolean))].sort(), [bank.data])
  const n = Object.keys(picked).length
  const total = Object.values(picked).reduce((a, b) => a + Number(b || 0), 0)
  const coverage = useMemo(() => {
    const m = {}
    for (const q of bank.data || []) if (picked[q.id]) for (const c of q.clos) m[c.clo_code] = (m[c.clo_code] || 0) + c.weight * Number(picked[q.id])
    return m
  }, [bank.data, picked])

  const save = async () => {
    const items = Object.entries(picked).map(([question_id, points]) => ({ question_id: Number(question_id), points: Number(points) }))
    const body = { ...f, class_section_id: cs.id, items, exam_date: f.exam_date || null, duration_minutes: Number(f.duration_minutes) || null, max_score: Number(f.max_score) }
    const e = await api.post('/api/exams', body)
    nav(`/exams/${e.id}`)
  }
  return (
    <Modal title="Tạo bài kiểm tra (UC-02)" onClose={onClose} wide>
      <div className="grid3">
        <Field label="Tên bài kiểm tra"><input value={f.exam_title} onChange={e => setF({ ...f, exam_title: e.target.value })} placeholder="VD: Thi cuối kỳ" /></Field>
        <Field label="Hình thức"><select value={f.exam_type} onChange={e => setF({ ...f, exam_type: e.target.value })}>
          <option value="online">Trực tuyến (Moodle Quiz)</option><option value="paper">Trên giấy (nhiều mã đề)</option></select></Field>
        <Field label="Bài KT lấy minh chứng (BM6a)"><select value={f.assessment_type} onChange={e => setF({ ...f, assessment_type: e.target.value })}>
          <option value="process">Quá trình</option><option value="final">Cuối kỳ</option></select></Field>
        <Field label="Ngày kiểm tra"><input type="date" value={f.exam_date} onChange={e => setF({ ...f, exam_date: e.target.value })} /></Field>
        <Field label="Thời gian (phút)"><input type="number" value={f.duration_minutes} onChange={e => setF({ ...f, duration_minutes: e.target.value })} /></Field>
        <Field label="Thang điểm"><input type="number" value={f.max_score} onChange={e => setF({ ...f, max_score: e.target.value })} /></Field>
      </div>
      <div className="row gap wrap mt"><b>Lọc:</b>
        <button className={`chip ${!filter ? 'on' : ''}`} onClick={() => setFilter('')}>Tất cả</button>
        {chips.map(c => <button key={c} className={`chip ${filter === c ? 'on' : ''}`} onClick={() => setFilter(c)}>{c}</button>)}
        <span className="grow" />
        <button className="btn sm" onClick={() => setPicked(Object.fromEntries(list.map(q => [q.id, picked[q.id] || 0.5])))}>Chọn tất cả đang lọc</button>
      </div>
      <div className="scroll mt">
        <table className="tbl"><thead><tr><th /><th>ID</th><th>Nội dung</th><th>Chương</th><th>Bloom</th><th>CLO (trọng số)</th><th>p TB</th><th>Điểm</th></tr></thead>
          <tbody>{list.map(q => (
            <tr key={q.id} className={picked[q.id] ? 'sel' : ''}>
              <td><input type="checkbox" checked={!!picked[q.id]} onChange={e => setPicked(p => { const x = { ...p }; e.target.checked ? x[q.id] = 0.5 : delete x[q.id]; return x })} /></td>
              <td>{q.id}</td><td className="clip">{q.content}</td><td>{q.chapter}</td><td>{q.bloom}</td>
              <td>{q.clos.map(c => `${c.clo_code}${c.weight < 1 ? ` (${c.weight})` : ''}`).join(', ')}</td>
              <td>{q.usage?.avg_p ?? '—'}</td>
              <td>{picked[q.id] !== undefined && <input className="num" type="number" step="0.25" value={picked[q.id]} onChange={e => setPicked(p => ({ ...p, [q.id]: e.target.value }))} />}</td>
            </tr>))}</tbody></table>
      </div>
      <div className="row gap mt wrap">
        <span>Đã chọn <b>{n}</b> câu · tổng điểm thô <b>{total.toFixed(2)}</b></span>
        {Object.entries(coverage).sort().map(([c, v]) => <span key={c} className="pill blue">{c}: {v.toFixed(2)} đ</span>)}
        <span className="grow" />
        <ActionButton className="btn primary" disabled={!n || f.exam_title.length < 3} onRun={save}>Lưu bài kiểm tra</ActionButton>
      </div>
    </Modal>
  )
}
