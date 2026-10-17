import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, STATUS_VI } from '../api'
import { ActionButton, Badge, Card, Crumbs, FileButton, Loading, useToast } from '../components/ui'
import { useApi } from '../hooks'
import { NewExamFlow, TYPE_VI } from '../components/NewExam'
import { useMoodleBase } from '../moodle'

const ASSESS_VI = { process: 'Quá trình', final: 'Cuối kỳ' }

export default function SectionDetail() {
  const { id } = useParams()
  const secs = useApi('/api/class-sections')
  const cs = secs.data?.find(x => String(x.id) === id)
  const exams = useApi(`/api/class-sections/${id}/exams`)
  const students = useApi(`/api/class-sections/${id}/students`)
  const [tab, setTab] = useState('exams')
  const [creating, setCreating] = useState(false)
  const toast = useToast()
  const nav = useNavigate()
  const moodle = useMoodleBase()

  const importStudents = async file => {
    try { const r = await api.upload(`/api/class-sections/${id}/students/import`, file); toast(`Đã thêm ${r.added} SV vào lớp`); students.reload() }
    catch (e) { toast(e.message, 'red') }
  }

  return (
    <>
      <div className="page-h">
        <div><Crumbs items={[['/', 'Môn học của tôi'], cs && [`/courses/${cs.course_id}`, `${cs.course_code} – ${cs.course_name}`], [null, cs?.section_code]]} />
          <h1>Lớp {cs?.section_code}</h1>
          <p className="muted">{cs?.course_name} · {cs?.semester} · GV {cs?.lecturer} · {cs?.n_students} SV ·{' '}
            {cs?.moodle_course_id ? <a href={moodle && `${moodle}/course/view.php?id=${cs.moodle_course_id}`} target="_blank" rel="noreferrer">Khóa học Moodle #{cs.moodle_course_id} ↗</a>
              : <ActionButton className="btn sm" title="Tìm khóa học Moodle có tên rút gọn hoặc mã khóa học trùng mã lớp" okMsg={r => `Đã gắn với khóa học Moodle #${r.moodle_course_id}`}
                onRun={async () => { const r = await api.post(`/api/class-sections/${id}/moodle-autolink`); secs.reload(); return r }}>Gắn Moodle theo mã lớp</ActionButton>}</p></div>
        <div className="row gap wrap"><Link className="btn" to={`/courses/${cs?.course_id}?tab=syllabus`}>Đề cương</Link>
          <Link className="btn" to={`/sections/${id}/stats`}>Thống kê lớp &amp; từng SV</Link>
          <Link className="btn" to={`/sections/${id}/remedial`}>Phụ đạo (câu sai)</Link>
          <Link className="btn" to={`/sections/${id}/clo`}>Kết quả CĐR (BM6)</Link>
          <button className="btn primary" onClick={() => setCreating(true)}>+ Tạo bài kiểm tra</button></div>
      </div>
      <div className="tabs">
        <button className={tab === 'exams' ? 'on' : ''} onClick={() => setTab('exams')}>Bài kiểm tra ({exams.data?.length ?? 0})</button>
        <button className={tab === 'students' ? 'on' : ''} onClick={() => setTab('students')}>Danh sách SV ({students.data?.length ?? 0})</button>
      </div>
      {tab === 'exams' && <Card>
        <Loading {...exams} />
        <table className="tbl">
          <thead><tr><th>#</th><th>Tên bài KT</th><th>Hình thức</th><th>Loại minh chứng</th><th>Ngày</th><th>Số câu</th><th>Bài làm</th><th>Trạng thái</th><th title="Gộp vào kết quả CLO của lớp (BM6)">Minh chứng</th><th /></tr></thead>
          <tbody>{exams.data?.map(e => (
            <tr key={e.id}>
              <td>{e.id}</td><td><b>{e.exam_title}</b>{e.source_exam_id && <div className="muted small">giao từ đề #{e.source_exam_id}</div>}</td><td>{TYPE_VI[e.exam_type]}</td><td>{ASSESS_VI[e.assessment_type]}</td>
              <td>{e.exam_date || '—'}</td><td>{e.questions.length}</td><td>{e.n_attempts} dự thi · {e.n_absent} vắng</td>
              <td><Badge tone={e.status === 'Analyzed' ? 'green' : e.status === 'Draft' ? 'gray' : 'blue'}>{STATUS_VI[e.status]}</Badge>
                {e.publish_flag && <Badge tone="amber">Đã công bố</Badge>}
                {e.timing_alerts?.n_warning > 0 && <Link to={`/exams/${e.id}?tab=timing`} title="Lượt làm bài có dấu hiệu bất thường (thời gian làm bài)"><Badge tone="red">⚠ {e.timing_alerts.n_warning} cảnh báo</Badge></Link>}</td>
              <td>{e.counts_for_clo ? <Badge tone="green">Có gộp</Badge> : <Badge>Không</Badge>}</td>
              <td><Link className="btn sm" to={`/exams/${e.id}`}>Mở</Link></td>
            </tr>))}
          </tbody>
        </table>
      </Card>}
      {tab === 'students' && <Card actions={<FileButton className="btn sm" accept=".csv" label="Nhập CSV (student_code, full_name, class_name)" onPick={importStudents} />}>
        <Loading {...students} />
        <table className="tbl"><thead><tr><th>MSSV</th><th>Họ tên</th><th>Lớp</th><th>Moodle user</th><th>Trạng thái</th><th /></tr></thead>
          <tbody>{students.data?.map(s => <tr key={s.id} className="click" onClick={() => nav(`/sections/${id}/students/${s.id}`)}><td>{s.student_code}</td><td><b>{s.full_name}</b></td><td>{s.class_name}</td>
            <td>{s.moodle_user_id ?? '—'}</td><td>{s.status === 'active' ? 'Đang học' : 'Rút HP'}</td>
            <td><Link className="btn sm" to={`/sections/${id}/students/${s.id}`} onClick={e => e.stopPropagation()}>Xem kết quả</Link></td></tr>)}</tbody></table>
      </Card>}
      {creating && cs && <NewExamFlow cs={cs} onClose={() => setCreating(false)} />}
    </>
  )
}
