import { useEffect, useState } from 'react'
import { api, fmtPct } from '../api'
import { Achieved, ActionButton, Card, Field, Loading, Modal } from '../components/ui'
import { useApi, useDefaultYear } from '../hooks'

export default function PiPlans() {
  const { sems, years, year, setYear, latestSemesterId } = useDefaultYear()
  const plans = useApi(year ? `/api/pi-plans?academic_year=${year}` : null)
  const assigns = useApi('/api/assignments')
  const [form, setForm] = useState(null)
  return (
    <>
      <div className="page-h"><div><h1>Kế hoạch đo lường PI (BM3b)</h1><p className="muted">Mỗi PI của CĐR được đo tại một môn học, trong học kỳ xác định, do GV phụ trách, lấy minh chứng từ các CLO của môn.</p></div>
        <div className="row gap"><Field label="Năm học"><select value={year || ''} onChange={e => setYear(e.target.value)}>{years.map(y => <option key={y}>{y}</option>)}</select></Field>
          <button className="btn primary" onClick={() => setForm({})}>+ Thêm kế hoạch</button></div></div>
      <Card title={`Kế hoạch năm học ${year}`}>
        <Loading {...plans} />
        <table className="tbl"><thead><tr><th>CĐR</th><th>PI</th><th>Môn học lấy minh chứng</th><th>CLO minh chứng</th><th>Phương pháp</th><th>Chu kỳ</th><th>Thời gian</th><th>GV phụ trách</th><th>Chỉ tiêu</th><th>Kết quả</th><th /></tr></thead>
          <tbody>{plans.data?.map(p => <tr key={p.id}><td><b>{p.plo_code}</b></td><td title={p.pi_description}>{p.pi_code}</td><td>{p.course_code} – {p.course_name}</td><td>{p.clo_codes || '—'}</td>
            <td>{p.method}</td><td>{p.cycle}</td><td>{p.semester}</td><td>{p.lecturer || '—'}</td><td>{p.target_pct}%</td>
            <td>{p.n_evaluated ? <>{p.n_achieved}/{p.n_evaluated} = {fmtPct(p.achieved_pct)} <Achieved ok={!!p.is_achieved} /></> : <Achieved ok={null} />}</td>
            <td className="row gap"><button className="btn sm" onClick={() => setForm(p)}>Sửa</button>
              <ActionButton className="btn sm ghost" okMsg="Đã xóa" title="Xóa kế hoạch" confirm={`Xóa kế hoạch đo ${p.pi_code} tại môn ${p.course_code}? Kết quả PI của kế hoạch này cũng bị xóa.`} onRun={async () => { await api.del(`/api/pi-plans/${p.id}`); plans.reload() }}>✕</ActionButton></td></tr>)}</tbody></table>
      </Card>
      <Card title="Phân công đánh giá PI theo học kỳ">
        <div className="row gap">{[...new Map((assigns.data || []).map(a => [a.semester_id, a.semester])).entries()].map(([id, name]) =>
          <ActionButton key={id} className="btn sm" onRun={() => api.download(`/api/reports/semesters/${id}/assignments.xlsx`, `Phan_cong_danh_gia_PIs_${name}.xlsx`)}>⬇ Xuất bảng phân công {name} (.xlsx)</ActionButton>)}</div>
        <table className="tbl"><thead><tr><th>Học kỳ</th><th>Môn học</th><th>GV phụ trách</th><th>Ghi chú</th></tr></thead>
          <tbody>{assigns.data?.map((a, i) => <tr key={i}><td>{a.semester}</td><td>{a.course_code} – {a.course_name}</td><td>{a.lecturer}</td><td>{a.note}</td></tr>)}</tbody></table>
      </Card>
      {form && <PlanForm plan={form} sems={sems || []} defSem={latestSemesterId} onClose={() => setForm(null)} onSaved={() => { setForm(null); plans.reload() }} />}
    </>
  )
}

function PlanForm({ plan, sems, defSem, onClose, onSaved }) {
  const prog = useApi('/api/programs/1').data
  const courses = useApi('/api/courses').data
  const lecturers = useApi('/api/lecturers').data
  const [f, setF] = useState({ pi_id: plan.pi_id || '', course_id: plan.course_id || '', semester_id: plan.semester_id || defSem || '', method: plan.method || 'Bài thi trắc nghiệm (Moodle/giấy)',
    cycle: plan.cycle || '2 năm/lần', target_pct: plan.target_pct ?? 75, lecturer_id: plan.lecturer_id || '', clo_ids: [] })
  const course = useApi(f.course_id ? `/api/courses/${f.course_id}` : null).data
  const [inited, setInited] = useState(false)
  useEffect(() => {  // khi sửa: chuyển danh sách mã CLO đã lưu thành id
    if (!inited && course && String(course.id) === String(plan.course_id) && plan.clo_codes) {
      const codes = plan.clo_codes.split(','); setF(x => ({ ...x, clo_ids: course.clos.filter(c => codes.includes(c.clo_code)).map(c => c.id) })); setInited(true)
    }
  }, [course, inited, plan])
  const set = k => e => setF({ ...f, [k]: e.target.value })
  const pis = (prog?.plos || []).flatMap(p => p.pis.map(pi => ({ ...pi, plo_code: p.plo_code })))
  const save = async () => {
    const body = { ...f, pi_id: Number(f.pi_id), course_id: Number(f.course_id), semester_id: Number(f.semester_id), target_pct: Number(f.target_pct), lecturer_id: f.lecturer_id ? Number(f.lecturer_id) : null }
    plan.id ? await api.put(`/api/pi-plans/${plan.id}`, body) : await api.post('/api/pi-plans', body)
    onSaved()
  }
  return <Modal title={plan.id ? 'Sửa kế hoạch đo PI' : 'Thêm kế hoạch đo PI'} onClose={onClose}>
    <Field label="PI"><select value={f.pi_id} onChange={set('pi_id')}><option value="">— chọn —</option>
      {pis.map(pi => <option key={pi.id} value={pi.id}>{pi.plo_code} · {pi.pi_code}: {pi.description.slice(0, 70)}</option>)}</select></Field>
    <div className="grid2">
      <Field label="Môn học lấy minh chứng"><select value={f.course_id} onChange={e => setF({ ...f, course_id: e.target.value, clo_ids: [] })}><option value="">— chọn —</option>
        {courses?.map(c => <option key={c.id} value={c.id}>{c.course_code} – {c.course_name}</option>)}</select></Field>
      <Field label="Học kỳ"><select value={f.semester_id} onChange={set('semester_id')}>{sems.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>
      <Field label="Phương pháp"><input value={f.method} onChange={set('method')} /></Field>
      <Field label="Chu kỳ"><input value={f.cycle} onChange={set('cycle')} /></Field>
      <Field label="Chỉ tiêu (%)"><input type="number" value={f.target_pct} onChange={set('target_pct')} /></Field>
      <Field label="GV phụ trách"><select value={f.lecturer_id} onChange={set('lecturer_id')}><option value="">—</option>
        {lecturers?.map(l => <option key={l.id} value={l.id}>{l.full_name}</option>)}</select></Field>
    </div>
    {course && <Field group label="CLO của môn dùng làm minh chứng" hint="Không chọn CLO nào = dùng mọi CLO của môn có đóng góp cho CĐR của PI"><div className="row gap wrap">{course.clos.map(c => <label key={c.id} className="row gap check">
      <input type="checkbox" checked={f.clo_ids.includes(c.id)} onChange={e => setF({ ...f, clo_ids: e.target.checked ? [...f.clo_ids, c.id] : f.clo_ids.filter(x => x !== c.id) })} />{c.clo_code}</label>)}</div></Field>}
    <div className="row"><span className="grow" /><ActionButton className="btn primary" disabled={!f.pi_id || !f.course_id || !f.semester_id || !String(f.method).trim()} okMsg="Đã lưu kế hoạch" onRun={save}>Lưu</ActionButton></div>
  </Modal>
}
