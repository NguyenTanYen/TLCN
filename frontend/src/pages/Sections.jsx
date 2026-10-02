import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, auth } from '../api'
import { ActionButton, Card, Field, Loading, Modal } from '../components/ui'
import { useApi } from '../hooks'

export default function Sections() {
  const { data, error, loading, reload } = useApi('/api/class-sections')
  return (
    <>
      <div className="page-h"><div><h1>Lớp học phần</h1><p className="muted">Các lớp học phần bạn phụ trách – chọn lớp để quản lý bài kiểm tra và xem kết quả đo lường CĐR.</p></div></div>
      <Loading error={error} loading={loading} />
      <MoodleCourses onImported={reload} />
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

// Khóa học trên Moodle (GV là giảng viên của khóa) chưa có lớp HP trong hệ thống → đưa vào bằng một thao tác.
function MoodleCourses({ onImported }) {
  const isAdmin = auth.user()?.role === 'admin'
  const mc = useApi('/api/moodle/my-courses')
  const [sp, setSp] = useSearchParams()
  const [dlg, setDlg] = useState(null)
  const focus = Number(sp.get('moodle')) || null
  const pending = (mc.data || []).filter(c => !c.section)
  useEffect(() => {   // đến từ nút "Phân tích CĐR" của một khóa học chưa có lớp HP
    if (focus && mc.data) { const c = mc.data.find(x => x.moodle_course_id === focus); if (c && !c.section) setDlg(c) }
  }, [focus, mc.data])
  if (mc.error) return <div className="alert amber">Không đọc được danh sách khóa học trên Moodle: {mc.error}
    {/Không có chức năng API/.test(mc.error) && ' – hệ thống đang chạy bản cũ: đóng cửa sổ hệ thống rồi chạy lại 5_CHAY_HE_THONG.bat.'}</div>
  if (!pending.length) return null
  return <Card title={`Khóa học trên Moodle chưa có trong hệ thống (${pending.length})`} className="mb">
    <p className="muted small">{isAdmin ? 'Mọi khóa học trên Moodle chưa gắn lớp học phần.' : 'Các khóa học bạn là giảng viên trên Moodle nhưng chưa có lớp học phần tương ứng.'} Bấm "Đưa vào hệ thống" để tạo lớp học phần, gắn khóa học và lấy danh sách sinh viên đang ghi danh.</p>
    <table className="tbl compact"><thead><tr><th>Khóa học Moodle</th><th>Giảng viên</th><th className="num-c">SV</th><th /></tr></thead>
      <tbody>{pending.map(c => <tr key={c.moodle_course_id} className={c.moodle_course_id === focus ? 'hl' : ''}>
        <td><b>{c.shortname}</b> <small className="muted">#{c.moodle_course_id}</small><div className="small muted">{c.fullname}</div></td>
        <td className="small">{c.teachers.map(t => t.name).join(', ') || <span className="muted">chưa có</span>}</td>
        <td className="num-c">{c.n_students}</td>
        <td><button className="btn sm primary" onClick={() => setDlg(c)}>Đưa vào hệ thống</button></td></tr>)}</tbody></table>
    {dlg && <ImportForm c={dlg} isAdmin={isAdmin} onClose={() => { setDlg(null); if (focus) setSp({}) }}
      onDone={() => { setDlg(null); if (focus) setSp({}); mc.reload(); onImported() }} />}
  </Card>
}

function ImportForm({ c, isAdmin, onClose, onDone }) {
  const nav = useNavigate()
  const courses = useApi('/api/courses')
  const sems = useApi('/api/semesters').data
  const lecs = useApi(isAdmin ? '/api/lecturers' : null).data
  const s = c.suggest
  const [f, setF] = useState({ course_id: s.course_id || '', semester_id: s.semester_id || (s.new_semester ? 'new' : ''), section_code: s.section_code, lecturer_id: s.lecturer_id || '' })
  const [nw, setNw] = useState(null)   // Bộ môn tạo môn học mới ngay trong hộp thoại
  const run = async () => {
    let course_id = Number(f.course_id)
    if (nw) course_id = (await api.post('/api/courses', { ...nw, credits: Number(nw.credits), clo_target_pct: 75 })).id
    const sem = f.semester_id === 'new' ? { semester_id: null, new_semester: { academic_year: s.new_semester.academic_year, term: s.new_semester.term } } : { semester_id: Number(f.semester_id) }
    const r = await api.post(`/api/moodle/courses/${c.moodle_course_id}/import`, { course_id, ...sem,
      section_code: f.section_code, lecturer_id: isAdmin ? Number(f.lecturer_id) : null })
    onDone(); nav(`/courses?course=${course_id}`)
    return r
  }
  const noCourse = !s.course_id && !f.course_id
  return <Modal title={`Đưa khóa học Moodle "${c.shortname}" vào hệ thống`} onClose={onClose}>
    <p className="muted small">{c.fullname} · {c.n_students} SV đang ghi danh sẽ được đưa vào danh sách lớp.</p>
    {!nw && <Field label="Môn học" hint={noCourse ? 'Không tìm thấy môn có mã trùng tên khóa học – chọn môn, hoặc ' + (isAdmin ? 'tạo môn mới.' : 'nhờ Bộ môn thêm môn học (Học phần & CLO → + Môn học mới).') : undefined}>
      <select value={f.course_id} onChange={e => setF({ ...f, course_id: e.target.value })}><option value="">— chọn môn học —</option>
        {courses.data?.map(x => <option key={x.id} value={x.id}>{x.course_code} – {x.course_name}</option>)}</select></Field>}
    {isAdmin && !nw && <button type="button" className="btn sm ghost" onClick={() => setNw({ course_code: (c.shortname || '').split(/[_\s-]/)[0], course_name: (c.fullname || '').split(' – ')[0], credits: 3 })}>+ Môn học mới</button>}
    {nw && <div className="row gap wrap">
      <Field label="Mã môn mới"><input value={nw.course_code} onChange={e => setNw({ ...nw, course_code: e.target.value })} /></Field>
      <Field label="Tên môn học"><input value={nw.course_name} onChange={e => setNw({ ...nw, course_name: e.target.value })} /></Field>
      <Field label="Tín chỉ"><input className="num" type="number" min="1" value={nw.credits} onChange={e => setNw({ ...nw, credits: e.target.value })} /></Field>
      <button type="button" className="btn sm ghost" onClick={() => setNw(null)}>Chọn môn có sẵn</button></div>}
    <div className="row gap">
      <Field label="Học kỳ"><select value={f.semester_id} onChange={e => setF({ ...f, semester_id: e.target.value })}>
        {s.new_semester && <option value="new">{s.new_semester.name} (tạo mới theo ngày bắt đầu khóa học)</option>}
        {sems?.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
      <Field label="Mã lớp học phần"><input value={f.section_code} onChange={e => setF({ ...f, section_code: e.target.value })} /></Field>
    </div>
    {isAdmin && <Field label="Giảng viên phụ trách"><select value={f.lecturer_id} onChange={e => setF({ ...f, lecturer_id: e.target.value })}><option value="">— chọn —</option>
      {lecs?.map(l => <option key={l.id} value={l.id}>{l.full_name} ({l.lecturer_code})</option>)}</select></Field>}
    <div className="row"><span className="grow" />
      <ActionButton className="btn primary" disabled={(!nw && !f.course_id) || (nw && (nw.course_code.trim().length < 2 || nw.course_name.trim().length < 2)) || !f.semester_id || f.section_code.trim().length < 2 || (isAdmin && !f.lecturer_id)}
        okMsg={r => `Đã tạo lớp học phần, ${r.n_students} SV`} onRun={run}>Tạo lớp học phần</ActionButton></div>
  </Modal>
}
