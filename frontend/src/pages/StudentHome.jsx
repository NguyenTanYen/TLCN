import { Link } from 'react-router-dom'
import { Badge, Card, Loading } from '../components/ui'
import { useApi } from '../hooks'

export default function StudentHome() {
  const { data, ...st } = useApi('/api/me/exams')
  return (
    <>
      <div className="page-h"><div><h1>Kết quả học tập của tôi</h1><p className="muted">UC-05 · Xem mức độ đạt từng CĐR môn học và lộ trình ôn tập được đề xuất sau mỗi bài kiểm tra.</p></div></div>
      <Loading {...st} />
      <Card><table className="tbl"><thead><tr><th>Môn học</th><th>Lớp HP</th><th>Học kỳ</th><th>Bài kiểm tra</th><th>Bài làm</th><th>Kết quả</th><th /></tr></thead>
        <tbody>{data?.map(e => <tr key={e.id}><td>{e.course_code} – {e.course_name}</td><td>{e.section_code}</td><td>{e.semester}</td><td>{e.exam_title}</td>
          <td>{e.attempt_status === 'finished' ? 'Đã làm' : e.attempt_status === 'absent' ? 'Vắng' : '—'}</td>
          <td>{e.publish_flag ? <Badge tone="green">Đã công bố</Badge> : <Badge>Đang bảo lưu</Badge>}</td>
          <td>{e.publish_flag ? <Link className="btn sm primary" to={`/me/exams/${e.id}`}>Xem phân tích</Link> : null}</td></tr>)}</tbody></table></Card>
    </>
  )
}
