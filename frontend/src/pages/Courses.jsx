// UC-12: Khai báo học phần – môn học, lớp học phần, đề cương (chương), CLO và ánh xạ CLO–PLO.
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, auth } from '../api'
import { ActionButton, Badge, Card, CourseSelect, Field, Loading, Modal, ploLabel } from '../components/ui'
import { useApi } from '../hooks'
import { OutlineForm } from '../components/SyllabusForms'

const LEVEL_VI = { I: 'I – Giới thiệu', R: 'R – Củng cố', M: 'M – Thành thạo' }

export default function Courses() {
  const isAdmin = auth.user()?.role === 'admin'
  const courses = useApi('/api/courses')
  const sections = useApi('/api/class-sections')
  const myCourses = useMemo(() => {
    if (!courses.data) return []
    if (isAdmin) return courses.data
    const ids = new Set((sections.data || []).map(s => s.course_id))
    return courses.data.filter(c => ids.has(c.id))
  }, [courses.data, sections.data, isAdmin])
  const [sp] = useSearchParams()
  const [cid, setCid] = useState(Number(sp.get('course')) || null)
  useEffect(() => { if (!cid && myCourses.length && sections.data) setCid((sections.data?.[0]?.course_id) || myCourses[0].id) }, [myCourses, sections.data, cid])
  const course = useApi(cid ? `/api/courses/${cid}` : null)
  const setup = useApi(cid ? `/api/courses/${cid}/setup` : null)
  const [dlg, setDlg] = useState(null)
  const reload = () => { course.reload(); setup.reload(); sections.reload(); courses.reload() }
  const c = course.data
  const mySecs = (sections.data || []).filter(s => s.course_id === cid)

  return (
    <>
      <div className="page-h">
        <div><h1>Học phần &amp; chuẩn đầu ra</h1>
          <p className="muted">Khai báo một học phần để ra đề và đo CĐR: lớp học phần → chương → CLO và ánh xạ PLO → kế hoạch đánh giá CLO → câu hỏi.</p></div>
        <div className="row gap wrap">
          <Field label="Môn học"><CourseSelect courses={myCourses} value={cid || ''} onChange={v => setCid(Number(v))} /></Field>
          {isAdmin && <button className="btn primary" onClick={() => setDlg({ kind: 'course' })}>+ Môn học mới</button>}
        </div>
      </div>
      {!isAdmin && !myCourses.length && <div className="alert amber">Bạn chưa phụ trách lớp học phần nào. Bộ môn (Quản trị) cần tạo lớp học phần và gán bạn làm giảng viên trước.</div>}
      <Loading {...course} />
      {c && <>
        <Card title="Các bước khai báo học phần">
          <ol className="steps setup">{setup.data?.steps.map(s => <li key={s.key} className={s.ok ? 'ok' : ''}>
            <span className={`badge ${s.ok ? 'green' : s.key === 'plans' ? 'amber' : 'red'}`}>{s.ok ? '✓' : '!'}</span> <b>{s.label}</b> <span className="muted small">– {s.detail}</span></li>)}</ol>
          {setup.data?.ready ? <div className="alert green mt">Học phần đã sẵn sàng: có thể tạo bài kiểm tra theo ma trận và đo CĐR.</div>
            : <p className="muted small mt">Hoàn thành các bước còn đánh dấu "!" theo thứ tự từ trên xuống. Câu hỏi nhập/gán CLO ở trang <Link to="/questions">Ngân hàng câu hỏi</Link>.</p>}
        </Card>
        <div className="grid2">
          <CourseInfo c={c} onSaved={reload} />
          <Card title={`Lớp học phần (${mySecs.length})`} actions={isAdmin && <button className="btn sm primary" onClick={() => setDlg({ kind: 'section', data: { course_id: cid } })}>+ Lớp HP</button>}>
            <table className="tbl compact"><thead><tr><th>Mã lớp</th><th>Học kỳ</th><th>GV</th><th>Moodle</th><th /></tr></thead>
              <tbody>{mySecs.map(s => <tr key={s.id}><td><Link to={`/sections/${s.id}`}><b>{s.section_code}</b></Link></td><td>{s.semester}</td><td>{s.lecturer}</td>
                <td>{s.moodle_course_id ? `#${s.moodle_course_id}` : <span className="muted">chưa gắn</span>}</td>
                <td className="row gap"><Link className="btn sm" to={`/sections/${s.id}/clo?tab=bm6a`} title="Kế hoạch đánh giá và kết quả chuẩn đầu ra của lớp">Kế hoạch</Link>
                  {s.moodle_course_id && <ActionButton className="btn sm ghost" title="Lấy SV mới ghi danh trên Moodle vào danh sách lớp" okMsg={r => `Thêm ${r.added} SV – lớp có ${r.n_students} SV`}
                    onRun={async () => { const r = await api.post(`/api/class-sections/${s.id}/moodle-roster`); sections.reload(); return r }}>↻ SV</ActionButton>}
                  {isAdmin && <button className="btn sm ghost" onClick={() => setDlg({ kind: 'section', data: s })}>Sửa</button>}</td></tr>)}</tbody></table>
            {!mySecs.length && <p className="muted small">Chưa có lớp học phần. {isAdmin ? 'Bấm "+ Lớp HP" để tạo và gán giảng viên.' : 'Liên hệ Bộ môn.'}</p>}
            <p className="muted small">Khóa học đã tạo trên Moodle: dùng "Đưa vào hệ thống" ở trang <Link to="/courses">Lớp học phần</Link> (tự gắn khóa học và lấy danh sách SV). Lớp tạo tay được gắn khóa học Moodle khi tạo Quiz/đề giấy lần đầu.</p>
          </Card>
        </div>
        <Outlines c={c} onSaved={reload} />
        <Clos c={c} onEdit={x => setDlg({ kind: 'clo', data: x })} onSaved={reload} />
      </>}
      {dlg?.kind === 'course' && <CourseForm onClose={() => setDlg(null)} onSaved={id => { setDlg(null); reload(); setCid(id) }} />}
      {dlg?.kind === 'section' && <SectionForm s={dlg.data} onClose={() => setDlg(null)} onSaved={() => { setDlg(null); reload() }} />}
      {dlg?.kind === 'clo' && c && <CloForm c={c} clo={dlg.data} onClose={() => setDlg(null)} onSaved={() => { setDlg(null); reload() }} />}
    </>
  )
}

export function CourseInfo({ c, onSaved }) {
  const pick = x => ({ course_name: x.course_name, credits: x.credits, clo_target_pct: x.clo_target_pct, credits_theory: x.credits_theory ?? '',
    credits_practice: x.credits_practice ?? '', course_structure: x.course_structure || '', prerequisites: x.prerequisites || '', description: x.description || '' })
  const [f, setF] = useState(pick(c))
  useEffect(() => setF(pick(c)), [c])
  const num = v => (v === '' || v === null ? null : Number(v))
  return <Card title={`Thông tin học phần ${c.course_code}`}>
    <Field label="Tên học phần"><input value={f.course_name} onChange={e => setF({ ...f, course_name: e.target.value })} /></Field>
    <div className="row gap wrap">
      <Field label="Số tín chỉ"><input className="num" type="number" min="1" value={f.credits} onChange={e => setF({ ...f, credits: e.target.value })} /></Field>
      <Field label="TC lý thuyết"><input className="num" type="number" min="0" value={f.credits_theory} onChange={e => setF({ ...f, credits_theory: e.target.value })} /></Field>
      <Field label="TC TN/TH/TT"><input className="num" type="number" min="0" value={f.credits_practice} onChange={e => setF({ ...f, credits_practice: e.target.value })} /></Field>
      <Field label="Cấu trúc" hint="VD 3(2:1:6)"><input className="num" value={f.course_structure} onChange={e => setF({ ...f, course_structure: e.target.value })} /></Field>
      <Field label="Chỉ tiêu đạt CĐR môn học (%)" hint="Tỷ lệ sinh viên đạt cả môn để môn được xem là đạt"><input className="num" type="number" min="0" max="100" value={f.clo_target_pct} onChange={e => setF({ ...f, clo_target_pct: e.target.value })} /></Field>
    </div>
    <Field label="Học phần trước / tiên quyết (mã, cách nhau dấu phẩy)"><input value={f.prerequisites} onChange={e => setF({ ...f, prerequisites: e.target.value })} placeholder="VD DBSY230184, DASA230179" /></Field>
    <Field label="Mô tả vắn tắt học phần"><textarea rows={5} value={f.description} onChange={e => setF({ ...f, description: e.target.value })} /></Field>
    <ActionButton className="btn primary" okMsg="Đã lưu thông tin học phần" onRun={async () => {
      await api.put(`/api/courses/${c.id}`, { course_name: f.course_name, credits: Number(f.credits), clo_target_pct: Number(f.clo_target_pct),
        credits_theory: num(f.credits_theory), credits_practice: num(f.credits_practice), course_structure: f.course_structure.trim() || null,
        prerequisites: f.prerequisites.trim() || null, description: f.description.trim() || null }); onSaved() }}>Lưu</ActionButton>
  </Card>
}

export function Outlines({ c, onSaved }) {
  const [rows, setRows] = useState({})
  const [paste, setPaste] = useState('')
  const next = Math.max(0, ...c.outlines.map(o => o.chapter_number)) + 1
  const [nw, setNw] = useState({ chapter_number: next, chapter_name: '' })
  const [detail, setDetail] = useState(null)      // góp ý F1: nội dung, số tiết, CLO của chương
  const enter = e => { if (e.key === 'Enter') { e.preventDefault(); e.currentTarget.closest('tr').querySelector('button.enter-save')?.click() } }
  useEffect(() => setNw({ chapter_number: next, chapter_name: '' }), [c.id, c.outlines.length])  // eslint-disable-line
  const addMany = async () => {   // mỗi dòng một chương: "3. Tên chương" hoặc "Tên chương"
    let n = next, added = 0
    for (const line of paste.split('\n').map(x => x.trim()).filter(Boolean)) {
      const m = /^(?:chương\s*)?(\d+)\s*[.:)\-–]\s*(.+)$/i.exec(line)
      const num = m ? Number(m[1]) : n; const name = m ? m[2] : line
      await api.post(`/api/courses/${c.id}/outlines`, { chapter_number: num, chapter_name: name }); n = Math.max(n, num) + 1; added++
    }
    setPaste(''); onSaved(); return added
  }
  return <Card title={`Đề cương – các chương (${c.outlines.length})`}>
    <table className="tbl compact"><thead><tr><th style={{ width: 90 }}>Chương</th><th>Tên chương</th><th>Số tiết LT/TH · CLO</th><th /></tr></thead>
      <tbody>{c.outlines.map(o => { const r = rows[o.id] || o; return <tr key={o.id}>
        <td><input className="num tiny" type="number" min="1" value={r.chapter_number} onChange={e => setRows({ ...rows, [o.id]: { ...r, chapter_number: e.target.value } })} onKeyDown={enter} /></td>
        <td><input style={{ width: '100%' }} value={r.chapter_name} onChange={e => setRows({ ...rows, [o.id]: { ...r, chapter_name: e.target.value } })} onKeyDown={enter} /></td>
        <td className="small nowrap">{o.theory_hours ?? '—'}/{o.practice_hours ?? '—'} · {o.clos?.length ? o.clos.map(x => x.clo_code).join(', ') : <span className="muted">chưa gắn CLO</span>}</td>
        <td className="row gap"><ActionButton className={`btn sm enter-save ${rows[o.id] ? 'primary' : ''}`} disabled={!rows[o.id] || !String(r.chapter_name).trim()} title={rows[o.id] ? 'Lưu số và tên chương (Enter)' : 'Sửa số hoặc tên chương rồi bấm Lưu'}
            okMsg="Đã lưu chương" onRun={async () => { await api.put(`/api/outlines/${o.id}`, { chapter_number: Number(r.chapter_number), chapter_name: r.chapter_name }); setRows({ ...rows, [o.id]: undefined }); onSaved() }}>Lưu</ActionButton>
          <button className="btn sm" title="Nội dung, số tiết, hoạt động dạy học, CLO của chương" onClick={() => setDetail(o)}>Chi tiết</button>
          <ActionButton className="btn sm ghost" confirm={`Xóa chương ${o.chapter_number}?`} okMsg="Đã xóa" onRun={async () => { await api.del(`/api/outlines/${o.id}`); onSaved() }}>✕</ActionButton></td></tr> })}
        <tr className="sub"><td><input className="num tiny" type="number" min="1" value={nw.chapter_number} onChange={e => setNw({ ...nw, chapter_number: e.target.value })} onKeyDown={enter} /></td>
          <td><input style={{ width: '100%' }} placeholder="Tên chương mới… (nhấn Enter để thêm)" value={nw.chapter_name} onChange={e => setNw({ ...nw, chapter_name: e.target.value })} onKeyDown={enter} />
            {nw.chapter_name.trim() && <div className="small neg">Chưa lưu – nhấn Enter hoặc bấm "+ Thêm"</div>}</td>
          <td /><td><ActionButton className={`btn sm enter-save ${nw.chapter_name.trim() ? 'primary' : ''}`} disabled={!nw.chapter_name.trim()} okMsg="Đã thêm chương" onRun={async () => { await api.post(`/api/courses/${c.id}/outlines`, { chapter_number: Number(nw.chapter_number), chapter_name: nw.chapter_name }); onSaved() }}>+ Thêm</ActionButton></td></tr>
      </tbody></table>
    <details className="mt"><summary className="muted">Dán nhanh nhiều chương (mỗi dòng một chương, VD "1. Tổng quan…")</summary>
      <textarea rows={4} value={paste} onChange={e => setPaste(e.target.value)} placeholder={'1. Tổng quan về dữ liệu lớn\n2. Hệ sinh thái Hadoop\n3. Spark và xử lý phân tán'} />
      <ActionButton className="btn sm mt" disabled={!paste.trim()} okMsg={n => `Đã thêm ${n} chương`} onRun={addMany}>Thêm các chương</ActionButton></details>
    {detail && <OutlineForm s={c} o={detail} onClose={() => setDetail(null)} onSaved={() => { setDetail(null); onSaved() }} />}
  </Card>
}

export function Clos({ c, onEdit, onSaved }) {
  return <Card title={`CĐR môn học – CLO (${c.clos.length})`} actions={<button className="btn sm primary" onClick={() => onEdit({})}>+ CLO</button>}>
    <table className="tbl"><thead><tr><th>Mã</th><th>Nội dung</th><th>Bloom mục tiêu</th><th>Đóng góp cho PI (PLO)</th><th /></tr></thead>
      <tbody>{c.clos.map(x => <tr key={x.id}><td><b>{x.clo_code}</b></td><td className="clip">{x.description}</td><td>{x.bloom || '—'}</td>
        <td>{x.pis?.length ? x.pis.map(p => <span key={p.pi_id} className="pill blue" title={p.program_code}>{p.plo_code} › {p.pi_code} ({p.level})</span>)
          : x.plos.length ? <>{x.plos.map(p => <span key={p.plo_id} className="pill">{ploLabel(p.plo_code)} ({p.level})</span>)} <Badge tone="amber">Chưa gắn PI</Badge></>
          : <Badge tone="red">Chưa ánh xạ</Badge>}</td>
        <td className="row gap"><button className="btn sm" onClick={() => onEdit(x)}>Sửa</button>
          <ActionButton className="btn sm ghost" confirm={`Xóa ${x.clo_code}?`} okMsg="Đã xóa" onRun={async () => { await api.del(`/api/clos/${x.id}`); onSaved() }}>✕</ActionButton></td></tr>)}</tbody></table>
    {!c.clos.length && <p className="muted small">Chưa có CLO. Mỗi CLO cần mô tả, mức độ nhận thức mục tiêu và ít nhất một PI của CTĐT mà CLO đóng góp (mức I, R hoặc M) – PLO được suy ra từ PI, dùng để tính PI/PLO.</p>}
  </Card>
}

export function CloForm({ c, clo, onClose, onSaved }) {
  const progs = useApi(`/api/courses/${c.id}/plos`).data
  const bloom = useApi('/api/bloom-levels').data
  const [f, setF] = useState({ clo_code: clo.clo_code || `CLO${c.clos.length + 1}`, description: clo.description || '', bloom_level_id: clo.bloom_level_id || '',
    pis: Object.fromEntries((clo.pis || []).map(p => [p.pi_id, p.level])) })
  // góp ý F2a: CLO ánh xạ tới PI (PI thuộc PLO); ma trận CLO – PLO được hệ thống suy ra từ PI
  const body = () => ({ clo_code: f.clo_code, description: f.description, bloom_level_id: f.bloom_level_id ? Number(f.bloom_level_id) : null,
    pis: Object.entries(f.pis).map(([pi_id, level]) => ({ pi_id: Number(pi_id), level })), plos: [] })
  const legacy = !clo.pis?.length && clo.plos?.length
  const save = async () => { clo.id ? await api.put(`/api/clos/${clo.id}`, body()) : await api.post('/api/clos', { course_id: c.id, ...body() }); onSaved() }
  return <Modal title={clo.id ? `Sửa ${clo.clo_code}` : 'Thêm CLO'} onClose={onClose} wide>
    <div className="row gap">
      <Field label="Mã CLO"><input className="num" value={f.clo_code} onChange={e => setF({ ...f, clo_code: e.target.value })} /></Field>
      <Field label="Mức Bloom mục tiêu"><select value={f.bloom_level_id} onChange={e => setF({ ...f, bloom_level_id: e.target.value })}>
        <option value="">—</option>{bloom?.map(b => <option key={b.id} value={b.id}>{b.id}. {b.name_vi}</option>)}</select></Field>
    </div>
    <Field label="Nội dung CLO"><textarea rows={2} value={f.description} onChange={e => setF({ ...f, description: e.target.value })} placeholder="VD: Trình bày được kiến trúc của hệ sinh thái Hadoop…" /></Field>
    <Field group label="Đóng góp cho PI của các CTĐT có học phần (chọn PI và mức I/R/M – PLO được suy ra từ PI)">
      {legacy && <p className="small muted">CLO này đang ánh xạ thẳng tới PLO ({clo.plos.map(p => ploLabel(p.plo_code)).join(', ')}). Chọn PI tương ứng rồi lưu để chuyển sang CLO → PI.</p>}
      <div className="scroll short">{progs?.map(pr => <div key={pr.id}><div className="small muted" style={{ padding: '6px 4px 2px' }}><b>{pr.code}</b> – {pr.name}</div>
      {pr.plos.map(p => <div key={p.id}>
        <div className="small" style={{ padding: '4px 4px 0' }}><b>{ploLabel(p.plo_code)}</b> <span className="muted">{p.description}</span></div>
        {(p.pis || []).map(i => <div key={i.id} className="row gap clo-w" style={{ paddingLeft: 18 }}>
          <input type="checkbox" checked={f.pis[i.id] !== undefined} onChange={e => setF(x => { const m = { ...x.pis }; e.target.checked ? m[i.id] = 'R' : delete m[i.id]; return { ...x, pis: m } })} />
          <span className="grow"><b>{i.pi_code}</b> <small className="muted">{i.description}</small>
            {i.course_level && <span className="pill green" title="Mức học phần đáp ứng PI theo ma trận CTĐT">CTĐT giao: {i.course_level}</span>}</span>
          {f.pis[i.id] !== undefined && <select value={f.pis[i.id]} onChange={e => setF(x => ({ ...x, pis: { ...x.pis, [i.id]: e.target.value } }))}>
            {Object.entries(LEVEL_VI).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}
        </div>)}
        {!p.pis?.length && <div className="small muted" style={{ paddingLeft: 18 }}>PLO chưa có PI</div>}
      </div>)}</div>)}</div></Field>
    <div className="row"><span className="grow" />
      <ActionButton className="btn primary" disabled={!f.clo_code.trim() || f.description.trim().length < 3} okMsg="Đã lưu CLO" onRun={save}>Lưu</ActionButton></div>
  </Modal>
}

export function CourseForm({ onClose, onSaved }) {
  const progs = useApi('/api/programs').data
  const [f, setF] = useState({ course_code: '', course_name: '', credits: 3, clo_target_pct: 75, program_ids: [] })
  return <Modal title="Thêm môn học" onClose={onClose}>
    <div className="row gap"><Field label="Mã môn"><input value={f.course_code} onChange={e => setF({ ...f, course_code: e.target.value })} placeholder="VD BDES333877" /></Field>
      <Field label="Số tín chỉ"><input className="num" type="number" min="1" value={f.credits} onChange={e => setF({ ...f, credits: e.target.value })} /></Field></div>
    <Field label="Tên môn học"><input value={f.course_name} onChange={e => setF({ ...f, course_name: e.target.value })} /></Field>
    <Field label="Chỉ tiêu đạt CĐR môn học (%)"><input className="num" type="number" value={f.clo_target_pct} onChange={e => setF({ ...f, clo_target_pct: e.target.value })} /></Field>
    <Field group label="Thuộc chương trình đào tạo">{progs?.map(p => <label key={p.id} className="row gap check"><input type="checkbox" checked={f.program_ids.includes(p.id)}
      onChange={e => setF({ ...f, program_ids: e.target.checked ? [...f.program_ids, p.id] : f.program_ids.filter(x => x !== p.id) })} /> {p.code} – {p.name}</label>)}</Field>
    <div className="row"><span className="grow" /><ActionButton className="btn primary" disabled={f.course_code.trim().length < 2 || f.course_name.trim().length < 2} okMsg="Đã thêm môn học"
      onRun={async () => { const r = await api.post('/api/courses', { ...f, credits: Number(f.credits), clo_target_pct: Number(f.clo_target_pct) }); onSaved(r.id) }}>Lưu</ActionButton></div>
  </Modal>
}

export function SectionForm({ s, onClose, onSaved }) {
  const sems = useApi('/api/semesters').data
  const lecs = useApi('/api/lecturers').data
  const courses = useApi('/api/courses').data
  const [f, setF] = useState({ course_id: s.course_id, semester_id: s.semester_id || '', lecturer_id: s.lecturer_id || '', section_code: s.section_code || '' })
  useEffect(() => { if (!f.semester_id && sems?.length) setF(x => ({ ...x, semester_id: sems[0].id })) }, [sems])  // eslint-disable-line
  useEffect(() => {   // lớp đã có: tìm id giảng viên theo tên
    if (s.id && !f.lecturer_id && lecs) { const l = lecs.find(x => x.full_name === s.lecturer); if (l) setF(x => ({ ...x, lecturer_id: l.id })) }
  }, [lecs])  // eslint-disable-line
  const body = () => ({ ...f, course_id: Number(f.course_id), semester_id: Number(f.semester_id), lecturer_id: Number(f.lecturer_id) })
  return <Modal title={s.id ? `Sửa lớp ${s.section_code}` : 'Thêm lớp học phần'} onClose={onClose}>
    <Field label="Môn học"><CourseSelect courses={courses} value={f.course_id} onChange={v => setF({ ...f, course_id: v })} /></Field>
    <div className="row gap">
      <Field label="Học kỳ"><select value={f.semester_id} onChange={e => setF({ ...f, semester_id: e.target.value })}>{sems?.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
      <Field label="Mã lớp học phần"><input value={f.section_code} onChange={e => setF({ ...f, section_code: e.target.value })} placeholder="VD BDES333877_01" /></Field>
    </div>
    <Field label="Giảng viên phụ trách"><select value={f.lecturer_id} onChange={e => setF({ ...f, lecturer_id: e.target.value })}><option value="">— chọn —</option>
      {lecs?.map(l => <option key={l.id} value={l.id}>{l.full_name} ({l.lecturer_code})</option>)}</select></Field>
    <div className="row gap"><span className="grow" />
      {s.id && <ActionButton className="btn danger" confirm={`Xóa lớp ${s.section_code}?`} okMsg="Đã xóa" onRun={async () => { await api.del(`/api/class-sections/${s.id}`); onSaved() }}>Xóa lớp</ActionButton>}
      <ActionButton className="btn primary" disabled={!f.semester_id || !f.lecturer_id || f.section_code.trim().length < 2} okMsg="Đã lưu lớp học phần"
        onRun={async () => { s.id ? await api.put(`/api/class-sections/${s.id}`, body()) : await api.post('/api/class-sections', body()); onSaved() }}>Lưu</ActionButton></div>
  </Modal>
}
