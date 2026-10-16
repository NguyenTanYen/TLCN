// Chương trình đào tạo: danh sách CTĐT → CĐR (PLO) và chỉ số PI, học phần theo học kỳ, ma trận học phần – PI.
import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api, auth } from '../api'
import { ActionButton, Badge, Card, Crumbs, Field, Loading, Modal, Tabs } from '../components/ui'
import { useApi } from '../hooks'

const GROUP_VI = { 1: 'Kiến thức', 2: 'Kỹ năng', 3: 'Mức tự chủ và trách nhiệm', 4: 'Nhóm 4' }

export function ProgramList() {
  const list = useApi('/api/programs')
  const isAdmin = auth.user()?.role === 'admin'
  const [form, setForm] = useState(null)
  return <>
    <div className="page-h"><div><h1>Chương trình đào tạo</h1>
      <p className="muted">Mỗi CTĐT gồm các chuẩn đầu ra (PLO) với chỉ số đo (PI), danh sách học phần theo học kỳ và ma trận học phần – PI. Học phần và CLO được quản lý theo CTĐT.</p></div>
      {isAdmin && <button className="btn primary" onClick={() => setForm({})}>+ CTĐT mới</button>}</div>
    <Loading {...list} />
    <div className="grid3">{list.data?.map(p => <Card key={p.id} title={<Link to={`/programs/${p.id}`}>{p.code}</Link>}>
      <div className="big">{p.name}</div>
      <div className="muted small">{p.name_en || ''}{p.major_code ? ` · mã ngành ${p.major_code}` : ''}{p.cohort_year ? ` · áp dụng khóa ${p.cohort_year}` : ''}</div>
      <div className="row gap wrap mt"><span className="pill">{p.n_plos} PLO</span><span className="pill">{p.n_pis} PI</span><span className="pill">{p.n_courses} học phần</span>
        {p.total_credits && <span className="pill blue">{p.total_credits} TC</span>}</div>
      <div className="row gap mt"><Link className="btn primary sm" to={`/programs/${p.id}`}>Xem CTĐT</Link><Link className="btn sm" to={`/programs/${p.id}?tab=courses`}>Học phần</Link></div>
    </Card>)}</div>
    {form && <ProgramForm p={form} onClose={() => setForm(null)} onSaved={() => { setForm(null); list.reload() }} />}
  </>
}

export function ProgramDetail() {
  const { id } = useParams()
  const [sp, setSp] = useSearchParams()
  const tab = sp.get('tab') || 'plo'
  const prog = useApi(`/api/programs/${id}`)
  const isAdmin = auth.user()?.role === 'admin'
  const [edit, setEdit] = useState(null)
  const p = prog.data
  if (!p) return <Loading {...prog} />
  return <>
    <div className="page-h"><div><Crumbs items={[['/programs', 'Chương trình đào tạo'], [null, p.code]]} />
      <h1>{p.name} <small className="muted">({p.code})</small></h1>
      <p className="muted">{[p.name_en, p.major_code && `Mã ngành ${p.major_code}`, p.level, p.faculty, p.cohort_year && `Áp dụng từ khóa ${p.cohort_year}`,
        p.total_credits && `${p.total_credits} tín chỉ`, p.decision_no && `QĐ ${p.decision_no}`].filter(Boolean).join(' · ')}</p></div>
      {isAdmin && <button className="btn" onClick={() => setEdit('program')}>Sửa thông tin CTĐT</button>}</div>
    <Tabs value={tab} onChange={t => setSp({ tab: t })} tabs={[['plo', `Chuẩn đầu ra (${p.plos.length} PLO)`], ['courses', `Học phần (${p.courses.length})`], ['matrix', 'Ma trận học phần – PI'], ['info', 'Mục tiêu']]} />
    {tab === 'plo' && <PloTab p={p} isAdmin={isAdmin} onEdit={setEdit} />}
    {tab === 'courses' && <CoursesTab p={p} />}
    {tab === 'matrix' && <MatrixTab p={p} isAdmin={isAdmin} reload={prog.reload} />}
    {tab === 'info' && <Card title="Mục tiêu chung">{p.objective ? <p style={{ lineHeight: 1.6 }}>{p.objective}</p> : <p className="muted">Chưa có.</p>}
      <p className="muted small">Chỉ tiêu đạt CĐR CTĐT: {p.target_pct}%</p></Card>}
    {edit === 'program' && <ProgramForm p={p} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); prog.reload() }} />}
    {edit && edit !== 'program' && <PloForm plo={edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); prog.reload() }} />}
  </>
}

function PloTab({ p, isAdmin, onEdit }) {
  const groups = [...new Set(p.plos.map(x => x.group_no))].sort()
  return groups.map(g => <Card key={g} title={`${GROUP_VI[g] || `Nhóm ${g}`}`}>
    <table className="tbl"><thead><tr><th>CĐR</th><th>Nội dung</th><th>Trình độ NL</th><th>Phân loại</th><th>Chỉ tiêu</th><th>Chỉ số PI (trình độ năng lực)</th>{isAdmin && <th />}</tr></thead>
      <tbody>{p.plos.filter(x => x.group_no === g).map(x => <tr key={x.id}>
        <td><b>{x.plo_code}</b></td><td className="wrap-cell">{x.description}</td><td>{x.competency_level ?? '—'}</td><td>{x.plo_type || '—'}</td><td>{x.target_pct}%</td>
        <td className="wrap-cell">{x.pis.length ? x.pis.map(pi => <div key={pi.id} className="mb"><b>{pi.pi_code}</b>{pi.competency_level ? ` (${pi.competency_level})` : ''}: {pi.description}
          {pi.courses && <div className="small muted">Học phần: {pi.courses.split(',').length}</div>}</div>) : <span className="muted">Chưa khai báo PI</span>}</td>
        {isAdmin && <td><button className="btn sm" onClick={() => onEdit(x)}>Sửa</button></td>}
      </tr>)}</tbody></table>
  </Card>)
}

function CoursesTab({ p }) {
  const sems = [...new Set(p.courses.map(c => c.semester_no))].sort((a, b) => (a ?? 99) - (b ?? 99))
  return sems.map(s => <Card key={s ?? 'x'} title={s ? `Học kỳ ${s}` : 'Học phần tự chọn / chưa xếp học kỳ'}>
    <table className="tbl compact"><thead><tr><th>Mã HP</th><th>Tên học phần</th><th className="num-c">TC</th><th>LT/TH</th><th>Khối kiến thức</th><th>Tiên quyết</th><th>CLO</th><th>Lớp HP</th></tr></thead>
      <tbody>{p.courses.filter(c => c.semester_no === s).map(c => <tr key={c.id}><td><Link to={`/courses/${c.id}`}><b>{c.course_code}</b></Link></td>
        <td><Link to={`/courses/${c.id}`}>{c.course_name}</Link>{c.is_elective ? <Badge tone="amber">Tự chọn</Badge> : null}</td><td className="num-c">{c.credits}</td>
        <td>{c.credits_theory != null ? `${c.credits_theory}/${c.credits_practice ?? 0}` : '—'}</td><td className="small">{c.knowledge_block || '—'}</td>
        <td className="small">{c.prerequisites || '—'}</td><td>{c.n_clos || <span className="muted">0</span>}</td><td>{c.n_sections || <span className="muted">0</span>}</td></tr>)}</tbody></table>
  </Card>)
}

function MatrixTab({ p, isAdmin, reload }) {
  const pis = p.plos.flatMap(x => x.pis.map(pi => ({ ...pi, plo_code: x.plo_code })))
  const lv = {}
  p.pi_matrix.forEach(m => { lv[`${m.course_id}:${m.pi_id}`] = m.level || '•' })
  const [cell, setCell] = useState(null)
  const courses = p.courses.filter(c => pis.some(pi => lv[`${c.id}:${pi.id}`]) || isAdmin)
  return <Card title="Ma trận học phần đáp ứng PI (Phụ lục II)" actions={<span className="muted small">I/R/M: Giới thiệu/Củng cố/Thành thạo · 1–6: trình độ năng lực{isAdmin ? ' · bấm ô để sửa' : ''}</span>}>
    <div className="scroll tall"><table className="tbl compact mx"><thead><tr><th className="sticky-col">Học phần</th>
      {p.plos.map(x => <th key={x.id} colSpan={x.pis.length || 1} style={{ textAlign: 'center' }}>{x.plo_code}</th>)}</tr>
      <tr><th className="sticky-col" />{p.plos.map(x => x.pis.length ? x.pis.map(pi => <th key={pi.id} className="rot" title={pi.description}>{pi.pi_code}</th>) : <th key={x.id} />)}</tr></thead>
      <tbody>{courses.map(c => <tr key={c.id}><td className="sticky-col"><Link to={`/courses/${c.id}`}>{c.course_code}</Link> <small className="muted">{c.course_name.slice(0, 28)}</small></td>
        {p.plos.map(x => x.pis.length ? x.pis.map(pi => { const v = lv[`${c.id}:${pi.id}`]; return <td key={pi.id} className={`c ${isAdmin ? 'edit' : ''}`}
          onClick={() => isAdmin && setCell({ c, pi, v })}>{v && <span className={`lvl ${/^[IRM]$/.test(v) ? v : 'n'}`}>{v}</span>}</td> }) : <td key={x.id} />)}</tr>)}</tbody></table></div>
    {cell && <Modal title={`${cell.c.course_code} – ${cell.pi.pi_code}`} onClose={() => setCell(null)}>
      <p className="small">{cell.pi.description}</p>
      <div className="row gap wrap">{['I', 'R', 'M', '1', '2', '3', '4', '5', '6', ''].map(v => <ActionButton key={v || 'x'} className={`btn sm ${cell.v === v ? 'primary' : ''}`}
        onRun={async () => { await api.put(`/api/courses/${cell.c.id}/pi-levels`, { pi_id: cell.pi.id, level: v || null }); setCell(null); reload() }}>{v || 'Bỏ ánh xạ'}</ActionButton>)}</div>
    </Modal>}
  </Card>
}

function ProgramForm({ p, onClose, onSaved }) {
  const keys = ['code', 'name', 'name_en', 'major_code', 'faculty', 'department', 'cohort_year', 'total_credits', 'decision_no', 'objective', 'target_pct']
  const [f, setF] = useState(Object.fromEntries(keys.map(k => [k, p[k] ?? (k === 'target_pct' ? 75 : '')])))
  const num = v => (v === '' || v === null ? null : Number(v))
  const body = () => ({ ...f, cohort_year: num(f.cohort_year), total_credits: num(f.total_credits), target_pct: Number(f.target_pct),
    ...Object.fromEntries(['name_en', 'major_code', 'faculty', 'department', 'decision_no', 'objective'].map(k => [k, f[k] || null])) })
  const inp = (k, label, cls) => <Field label={label}><input className={cls} value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })} /></Field>
  return <Modal title={p.id ? `Sửa CTĐT ${p.code}` : 'Thêm chương trình đào tạo'} onClose={onClose} wide>
    <div className="grid3">{inp('code', 'Mã CTĐT')}{inp('name', 'Tên CTĐT')}{inp('name_en', 'Tên tiếng Anh')}{inp('major_code', 'Mã ngành')}{inp('faculty', 'Khoa quản lý')}
      {inp('department', 'Bộ môn')}{inp('cohort_year', 'Áp dụng từ khóa', 'num')}{inp('total_credits', 'Tổng tín chỉ', 'num')}{inp('decision_no', 'Quyết định ban hành')}{inp('target_pct', 'Chỉ tiêu đạt CĐR CTĐT (%)', 'num')}</div>
    <Field label="Mục tiêu chung"><textarea rows={4} value={f.objective} onChange={e => setF({ ...f, objective: e.target.value })} /></Field>
    <div className="row"><span className="grow" /><ActionButton className="btn primary" disabled={f.code.trim().length < 2 || f.name.trim().length < 2} okMsg="Đã lưu CTĐT"
      onRun={async () => { p.id ? await api.put(`/api/programs/${p.id}`, body()) : await api.post('/api/programs', body()); onSaved() }}>Lưu</ActionButton></div>
  </Modal>
}

function PloForm({ plo, onClose, onSaved }) {
  const [f, setF] = useState({ description: plo.description, target_pct: plo.target_pct })
  return <Modal title={`CĐR ${plo.plo_code}`} onClose={onClose}>
    <Field label="Nội dung"><textarea rows={4} value={f.description} onChange={e => setF({ ...f, description: e.target.value })} /></Field>
    <Field label="Chỉ tiêu (%)"><input type="number" value={f.target_pct} onChange={e => setF({ ...f, target_pct: e.target.value })} /></Field>
    <div className="row"><span className="grow" /><ActionButton className="btn primary" okMsg="Đã lưu"
      onRun={async () => { await api.put(`/api/plos/${plo.id}`, { description: f.description, target_pct: Number(f.target_pct) }); onSaved() }}>Lưu</ActionButton></div>
  </Modal>
}
