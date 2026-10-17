// Trang chính của giảng viên: Môn học → các lớp HP mình dạy → bài kiểm tra. Bấm vào môn để xem đề cương chi tiết.
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { ActionButton, Badge, Card, Field, Loading } from '../components/ui'
import { useApi } from '../hooks'
import { MoodleCourses } from './Sections'
import { useMoodleBase } from '../moodle'

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
        <p className="muted">Mỗi môn hiện các lớp học phần bạn phụ trách. Bấm tên môn để xem đề cương chi tiết, lớp và kết quả CĐR của môn; bấm lớp để quản lý bài kiểm tra.</p></div>
      <Field label="Học kỳ"><select value={sem} onChange={e => setSem(e.target.value)}>
        <option value="">Tất cả học kỳ</option>{sems.map(([id, n]) => <option key={id} value={id}>{n}</option>)}</select></Field>
    </div>
    <Loading {...secs} />
    <MoodleCourses onImported={secs.reload} />
    <div className="grid2">
      {groups.map(g => { const c = info(g.course_id); return <Card key={g.course_id} className="course-card">
        <div className="cc-h">
          <div><h3><Link to={`/courses/${g.course_id}`}>{g.name}</Link></h3>
            <div className="muted small">{g.code}{c ? ` · ${c.credits} tín chỉ${c.course_structure ? ` ${c.course_structure}` : ''}` : ''}{c?.programs ? ` · CTĐT ${c.programs}` : ''}</div></div>
          <div className="row gap wrap"><Link className="btn sm" to={`/courses/${g.course_id}?tab=syllabus`}>Đề cương</Link>
            <Link className="btn sm" to={`/courses/${g.course_id}?tab=results`}>Kết quả CĐR</Link>
            <Link className="btn sm primary" to={`/courses/${g.course_id}?tab=exams&new=1`}>+ Tạo bài KT</Link></div>
        </div>
        <div className="stack" style={{ gap: 8 }}>
          {g.sections.map(s => <div key={s.id} className="secrow">
            <div><Link to={`/sections/${s.id}`}><b>{s.section_code}</b></Link><div className="muted small">{s.semester}</div></div>
            <div className="row gap wrap small"><span className="pill">{s.n_students} SV</span><span className="pill">{s.n_exams} bài KT</span>
              {s.moodle_course_id ? <a className="pill blue" href={moodle && `${moodle}/course/view.php?id=${s.moodle_course_id}`} target="_blank" rel="noreferrer" title="Mở khóa học trên Moodle">Moodle #{s.moodle_course_id} ↗</a>
                : <Badge tone="amber">Chưa gắn Moodle</Badge>}</div>
            <div className="row gap"><Link className="btn sm primary" to={`/sections/${s.id}`}>Mở lớp</Link></div>
          </div>)}
        </div>
        <div className="row gap wrap">
          <ActionButton className="btn sm" title="Gắn các lớp với khóa học Moodle trùng mã lớp và cập nhật danh sách SV từ Moodle"
            okMsg={r => r.sections.map(x => `${x.section_code}: ${x.status}${x.added_students ? `, +${x.added_students} SV` : ''}`).join(' · ')}
            onRun={async () => { const r = await api.post(`/api/courses/${g.course_id}/moodle-sync-sections`); secs.reload(); return r }}>⟳ Đồng bộ các lớp với Moodle</ActionButton>
          <Link className="btn sm ghost" to={`/courses/${g.course_id}?tab=combine`}>Gộp bài KT đánh giá CĐR</Link>
          <Link className="btn sm ghost" to={`/questions?course=${g.course_id}`}>Ngân hàng câu hỏi</Link>
        </div>
      </Card> })}
    </div>
    {secs.data?.length === 0 && <div className="alert">Bạn chưa được phân công lớp học phần nào. Bộ môn tạo lớp và gán giảng viên, hoặc đưa khóa học từ Moodle vào ở khung bên trên.</div>}
  </>
}
