// Bộ môn: danh sách học phần theo CTĐT – bấm học phần để xem/sửa đề cương chi tiết, CLO, lớp.
import { useMemo, useState } from 'react'
import { PageHelp } from '../components/Help'
import { Link, useNavigate } from 'react-router-dom'
import { Card, Field, Loading } from '../components/ui'
import { useApi } from '../hooks'
import { CourseForm } from './Courses'

export default function CourseList() {
  const progs = useApi('/api/programs').data
  const [pid, setPid] = useState('')
  const list = useApi(`/api/courses${pid ? `?program_id=${pid}` : ''}`)
  const [q, setQ] = useState('')
  const [adding, setAdding] = useState(false)
  const nav = useNavigate()
  const rows = useMemo(() => (list.data || []).filter(c => !q || `${c.course_code} ${c.course_name}`.toLowerCase().includes(q.toLowerCase())), [list.data, q])
  return <>
    <div className="page-h"><div><h1>Học phần &amp; đề cương</h1>
      <p className="muted">Chọn chương trình đào tạo để xem các học phần của chương trình đó. Bấm một học phần để xem đề cương chi tiết, khai báo chương, chuẩn đầu ra môn học (CLO) và gắn CLO với chỉ báo (PI).</p></div>
      <div className="row gap wrap">
        <Field label="Chương trình đào tạo"><select value={pid} onChange={e => setPid(e.target.value)}><option value="">Tất cả</option>
          {progs?.map(p => <option key={p.id} value={p.id}>{p.code} – {p.name}</option>)}</select></Field>
        <Field label="Tìm"><input value={q} onChange={e => setQ(e.target.value)} placeholder="mã hoặc tên…" /></Field>
        <button className="btn primary" onClick={() => setAdding(true)}>+ Học phần mới</button>
      </div></div>
    <PageHelp id="courselist"><p>Danh sách học phần theo chương trình đào tạo. Với mỗi học phần, Bộ môn khai báo các chương, chuẩn đầu ra môn học (CLO), soạn đề cương chi tiết và mở lớp cho giảng viên.</p></PageHelp>
    <Card>
      <Loading {...list} />
      <div className="scroll tall"><table className="tbl"><thead><tr><th>Mã HP</th><th>Tên học phần</th><th className="num-c">TC</th><th>Cấu trúc</th><th>CTĐT</th><th>Tiên quyết</th><th>Đề cương</th></tr></thead>
        <tbody>{rows.map(c => <tr key={c.id} className="click" onClick={() => nav(`/courses/${c.id}`)}><td><b>{c.course_code}</b></td>
          <td><Link to={`/courses/${c.id}`} onClick={e => e.stopPropagation()}>{c.course_name}</Link></td><td className="num-c">{c.credits}</td>
          <td>{c.course_structure || '—'}</td><td className="small">{c.programs || <span className="muted">chưa gán</span>}</td><td className="small">{c.prerequisites || '—'}</td>
          <td>{c.description ? <span className="pill green">có mô tả</span> : <span className="pill amber">thiếu</span>}</td></tr>)}</tbody></table></div>
      <p className="muted small mt">{rows.length} học phần</p>
    </Card>
    {adding && <CourseForm onClose={() => setAdding(false)} onSaved={id => { setAdding(false); nav(`/courses/${id}?tab=setup`) }} />}
  </>
}
