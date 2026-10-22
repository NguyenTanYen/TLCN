import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, auth, STATUS_VI } from '../api'
import { ActionButton, Badge, Card, Crumbs, FileButton, Flow, Loading, useToast } from '../components/ui'
import { useApi } from '../hooks'
import { NewExamFlow, TYPE_VI } from '../components/NewExam'
import { useMoodleBase } from '../moodle'

const ASSESS_VI = { process: 'Quá trình', final: 'Cuối kỳ' }

// Nút "bước tiếp theo" của một bài KT theo trạng thái (góp ý 21/10: nhìn vào là biết phải làm gì)
const nextStep = e => e.status === 'Analyzed' ? ['Xem kết quả', 'btn sm']
  : e.status === 'Draft' ? [{ online: 'Tạo Quiz trên Moodle', paper: 'In đề & chấm phiếu', manual: 'Nhập điểm' }[e.exam_type] || 'Mở', 'btn sm primary']
  : e.status === 'Synced' ? ['Phân tích', 'btn sm primary']
  : [{ online: 'Đồng bộ & phân tích', paper: 'Chấm phiếu & phân tích', manual: 'Nhập điểm & phân tích' }[e.exam_type] || 'Mở', 'btn sm primary']

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
  const isAdmin = auth.user()?.role === 'admin'
  const ex = exams.data || []
  const analyzed = ex.filter(e => e.status === 'Analyzed').length

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
        <div className="row gap wrap"><Link className="btn" to={`/sections/${id}/stats`}>Thống kê lớp &amp; từng SV</Link>
          {!isAdmin && <button className="btn primary" onClick={() => setCreating(true)}>+ Tạo bài kiểm tra</button>}</div>
      </div>
      {/* luồng công việc của lớp: tạo bài → thu bài & phân tích → kết quả CĐR → ôn tập */}
      <Flow steps={[
        !isAdmin && { label: 'Tạo bài kiểm tra', sub: 'Trực tuyến, trên giấy hoặc nhập điểm', done: ex.length > 0, onClick: () => setCreating(true) },
        { label: 'Thu bài & phân tích', sub: ex.length ? `${analyzed}/${ex.length} bài đã phân tích` : 'Mở bài → Đồng bộ & phân tích', done: analyzed > 0, on: tab === 'exams', onClick: () => setTab('exams') },
        { label: 'Kết quả CĐR (BM6)', sub: 'Tỷ lệ SV đạt từng CLO của lớp', done: analyzed > 0, to: `/sections/${id}/clo` },
        { label: 'Ôn tập', sub: 'Bài riêng cho SV làm sai', to: `/sections/${id}/remedial` },
      ]} />
      <div className="tabs">
        <button className={tab === 'exams' ? 'on' : ''} onClick={() => setTab('exams')}>Bài kiểm tra ({exams.data?.length ?? 0})</button>
        <button className={tab === 'students' ? 'on' : ''} onClick={() => setTab('students')}>Danh sách SV ({students.data?.length ?? 0})</button>
      </div>
      {tab === 'exams' && <Card>
        <Loading {...exams} />
        {exams.data && !ex.length ? <div className="empty"><p>Lớp chưa có bài kiểm tra.</p>
          {!isAdmin && <button className="btn primary" onClick={() => setCreating(true)}>Tạo bài kiểm tra đầu tiên</button>}</div>
        : <table className="tbl">
          <thead><tr><th>Bài kiểm tra</th><th className="num-c">Số câu</th><th>Bài làm</th><th>Trạng thái</th><th>Bước tiếp theo</th></tr></thead>
          <tbody>{ex.map(e => { const [label, cls] = nextStep(e)
            return <tr key={e.id}>
              <td><Link to={`/exams/${e.id}`}><b>{e.exam_title}</b></Link>
                <div className="muted small">#{e.id} · {TYPE_VI[e.exam_type]} · {ASSESS_VI[e.assessment_type]}{e.exam_date ? ` · ${e.exam_date}` : ''}{e.source_exam_id ? ` · giao từ đề #${e.source_exam_id}` : ''}</div></td>
              <td className="num-c">{e.questions.length}</td><td>{e.n_attempts} dự thi · {e.n_absent} vắng</td>
              <td><Badge tone={e.status === 'Analyzed' ? 'green' : e.status === 'Draft' ? 'gray' : 'blue'}>{STATUS_VI[e.status]}</Badge>
                {e.publish_flag && <Badge tone="amber">Đã công bố</Badge>}
                {!e.counts_for_clo && <span title="Không gộp vào kết quả CLO của lớp (BM6)"><Badge>Không tính BM6</Badge></span>}
                {e.timing_alerts?.n_warning > 0 && <Link to={`/exams/${e.id}?tab=timing`} title="Lượt làm bài có dấu hiệu bất thường (thời gian làm bài)"><Badge tone="red">⚠ {e.timing_alerts.n_warning} cảnh báo</Badge></Link>}</td>
              <td><Link className={cls} to={`/exams/${e.id}`}>{label}</Link></td>
            </tr> })}
          </tbody>
        </table>}
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
