import { Link } from 'react-router-dom'
import { Card, Loading } from '../components/ui'
import { useApi } from '../hooks'

export default function Sections() {
  const { data, error, loading } = useApi('/api/class-sections')
  return (
    <>
      <div className="page-h"><div><h1>Lớp học phần</h1><p className="muted">Các lớp học phần bạn phụ trách – chọn lớp để quản lý bài kiểm tra và xem kết quả đo lường CĐR.</p></div></div>
      <Loading error={error} loading={loading} />
      <div className="grid3">
        {data?.map(cs => (
          <Card key={cs.id} title={cs.section_code}>
            <div className="big">{cs.course_name}</div>
            <div className="muted">{cs.course_code} · {cs.semester} · GV {cs.lecturer}</div>
            <div className="row gap mt">
              <span className="pill">{cs.n_students} SV</span><span className="pill">{cs.n_exams} bài KT</span>
              {cs.moodle_course_id && <span className="pill blue">Moodle course #{cs.moodle_course_id}</span>}
            </div>
            <div className="row gap mt">
              <Link className="btn primary" to={`/sections/${cs.id}`}>Bài kiểm tra</Link>
              <Link className="btn" to={`/sections/${cs.id}/clo`}>Kết quả CĐR (BM6)</Link>
            </div>
          </Card>
        ))}
      </div>
      {data?.length === 0 && <div className="alert">Chưa có lớp học phần nào được phân công.</div>}
    </>
  )
}
