// Trang chính của giảng viên: Môn học → các lớp HP mình dạy → bài kiểm tra. Bấm vào môn để xem đề cương chi tiết.
import { useMemo, useState } from 'react'
import { PageHelp } from '../components/Help'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { ActionButton, Badge, Card, Field, Loading } from '../components/ui'
import { useApi } from '../hooks'
import { MoodleCourses } from './Sections'
import { openMoodle, useMoodleBase } from '../moodle'

export default function MyCourses() {
  const secs = useApi('/api/class-sections')
  const courses = useApi('/api/courses').data
  const moodle = useMoodleBase()
  const [sem, setSem] = useState('')
  const sems = useMemo(() => [...new Map((secs.data || []).map(s => [s.semester_id, s.semester])).entries()], [secs.data])
  const groups = useMemo(() => {
    const m = new Map()
    for (const s of secs.data || []) {
      if (sem && String(s.semester_id) !== sem) continue
      if (!m.has(s.course_id)) m.set(s.course_id, { course_id: s.course_id, code: s.course_code, name: s.course_name, sections: [] })
      m.get(s.course_id).sections.push(s)
    }
    return [...m.values()]
  }, [secs.data, sem])
  const info = id => courses?.find(c => c.id === id)
  return <>
    <div className="page-h">
      <div><h1>Môn học của tôi</h1>
        <p className="muted">Các môn và lớp học phần bạn phụ trách. Bấm tên môn để xem đề cương; bấm "Mở lớp" để tạo bài kiểm tra, xem điểm và kết quả của lớp đó.</p></div>
      <Field label="Học kỳ"><select value={sem} onChange={e => setSem(e.target.value)}>
        <option value="">Tất cả học kỳ</option>{sems.map(([id, n]) => <option key={id} value={id}>{n}</option>)}</select></Field>
    </div>
    <PageHelp id="mycourses"><p>Đây là trang đầu tiên của giảng viên. Mỗi thẻ là một <b>môn</b> bạn dạy; bên trong là các <b>lớp học phần</b> của môn đó.</p>
      <ul><li><b>Đề cương</b>: xem mục tiêu, chuẩn đầu ra và cách đánh giá của môn.</li>
        <li><b>+ Tạo bài kiểm tra</b>: soạn một đề cho cả môn; lúc đưa cho sinh viên bạn mới chọn lớp nào.</li>
        <li><b>Mở lớp</b>: làm việc với một lớp cụ thể: bài kiểm tra, điểm, ôn tập cho sinh viên còn yếu.</li></ul></PageHelp>
    <Loading {...secs} />
    <MoodleCourses onImported={secs.reload} />
    <div className="grid2">
      {groups.map(g => { const c = info(g.course_id); return <Card key={g.course_id} className="course-card">
        <div className="cc-h">
          <div><h3><Link to={`/courses/${g.course_id}`}>{g.name}</Link></h3>
            <div className="muted small">{g.code}{c ? ` · ${c.credits} tín chỉ${c.course_structure ? ` ${c.course_structure}` : ''}` : ''}{c?.programs ? ` · CTĐT ${c.programs}` : ''}</div></div>
          <div className="row gap wrap"><Link className="btn sm" to={`/courses/${g.course_id}?tab=syllabus`}>Đề cương</Link>
            <Link className="btn sm" to={`/courses/${g.course_id}?tab=results`}>Kết quả chuẩn đầu ra</Link>
            <Link className="btn sm primary" to={`/courses/${g.course_id}?new=1`}>+ Tạo bài kiểm tra</Link></div>
        </div>
        <div className="stack" style={{ gap: 8 }}>
          {g.sections.map(s => <div key={s.id} className="secrow">
            <div><Link to={`/sections/${s.id}`}><b>{s.section_code}</b></Link><div className="muted small">{s.semester}</div></div>
            <div className="row gap wrap small"><span className="pill">{s.n_students} SV</span><span className="pill">{s.n_exams} bài kiểm tra</span>
              {s.moodle_course_id ? <a className="pill blue" href={moodle && `${moodle}/course/view.php?id=${s.moodle_course_id}`} onClick={e => { e.preventDefault(); openMoodle(`/course/view.php?id=${s.moodle_course_id}`) }} title="Mở khóa học trên Moodle">Moodle #{s.moodle_course_id} ↗</a>
                : <Badge tone="amber">Chưa gắn Moodle</Badge>}</div>
            <div className="row gap"><Link className="btn sm primary" to={`/sections/${s.id}`}>Mở lớp</Link></div>
          </div>)}
        </div>
        <div className="row gap wrap">
          <ActionButton className="btn sm" title="Gắn các lớp với khóa học Moodle trùng mã lớp và cập nhật danh sách SV từ Moodle"
            okMsg={r => r.sections.map(x => `${x.section_code}: ${x.status}${x.added_students ? `, +${x.added_students} SV` : ''}`).join(' · ')}
            onRun={async () => { const r = await api.post(`/api/courses/${g.course_id}/moodle-sync-sections`); secs.reload(); return r }}>⟳ Cập nhật lớp từ Moodle</ActionButton>
        </div>
      </Card> })}
    </div>
    {secs.data?.length === 0 && <div className="alert">Bạn chưa được phân công lớp học phần nào. Bộ môn tạo lớp và gán giảng viên, hoặc đưa khóa học từ Moodle vào ở khung bên trên.</div>}
  </>
}
