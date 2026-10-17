// Trang một học phần: đề cương chi tiết (mọi tài khoản xem), các lớp HP, kết quả CĐR của môn, gộp bài KT, khai báo (Bộ môn).
import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api, auth, fmtPct, STATUS_VI } from '../api'
import { Achieved, ActionButton, Badge, Card, Crumbs, Loading, Tabs } from '../components/ui'
import { DeployDialog, NewExamFlow, TYPE_VI } from '../components/NewExam'
import { useApi } from '../hooks'
import { useMoodleBase } from '../moodle'
import Combine from '../components/Combine'
import { Clos, CloForm, CourseInfo, Outlines, SectionForm } from './Courses'



export default function CourseHome() {
  const { id } = useParams()
  const [sp, setSp] = useSearchParams()
  const tab = sp.get('tab') || 'syllabus'
  const isAdmin = auth.user()?.role === 'admin'
  const syl = useApi(`/api/courses/${id}/syllabus`)
  const s = syl.data
  const cex = useApi(`/api/courses/${id}/exams`)
  const [creating, setCreating] = useState(sp.get('new') === '1')
  const closeNew = () => { setCreating(false); if (sp.get('new')) setSp({ tab }) }
  return <>
    <div className="page-h">
      <div><Crumbs items={[isAdmin ? ['/courses', 'Học phần'] : ['/', 'Môn học của tôi'], [null, s?.course_code || '…']]} />
        <h1>{s?.course_name || 'Học phần'}</h1>
        {s && <p className="muted">{s.course_code} · {s.credits} tín chỉ{s.course_structure ? ` · ${s.course_structure}` : ''}
          {s.programs.length ? ` · ${s.programs.map(p => p.code).join(', ')}` : ''}</p>}</div>
      <div className="row gap wrap">
        <Link className="btn" to={`/questions?course=${id}`}>Ngân hàng câu hỏi ({s?.n_questions ?? '…'})</Link>
        {tab === 'syllabus' && <button className="btn" onClick={() => window.print()}>🖶 In đề cương</button>}
        <button className="btn primary" onClick={() => setCreating(true)}>+ Tạo bài kiểm tra</button>
      </div>
    </div>
    <Tabs value={tab} onChange={t => setSp({ tab: t })} tabs={[
      ['syllabus', 'Đề cương chi tiết'], ['sections', `Lớp học phần (${s?.sections.length ?? 0})`], ['exams', `Đề kiểm tra (${cex.data?.exams.length ?? 0})`],
      ['results', 'Kết quả CĐR của môn'],
      ['combine', 'Gộp bài KT đánh giá CĐR'], isAdmin && ['setup', 'Khai báo (Bộ môn)']]} />
    <Loading {...syl} />
    {s && tab === 'syllabus' && <Syllabus s={s} isAdmin={isAdmin} onEdit={() => setSp({ tab: 'setup' })} />}
    {s && tab === 'sections' && <SectionsTab s={s} isAdmin={isAdmin} reload={syl.reload} />}
    {s && tab === 'exams' && <ExamsTab data={cex} onNew={() => setCreating(true)} />}
    {s && tab === 'results' && <ResultsTab s={s} />}
    {creating && s && cex.data && <NewExamFlow course={{ id: Number(id), code: s.course_code }} sections={cex.data.sections} onClose={closeNew} />}
    {s && tab === 'combine' && <Combine courseId={Number(id)} />}
    {s && tab === 'setup' && isAdmin && <Setup courseId={Number(id)} s={s} reload={syl.reload} />}
  </>
}

const Lvl = ({ v }) => v ? <span className={`lvl ${/^[IRM]$/.test(v) ? v : 'n'}`}>{v}</span> : null

export function Syllabus({ s, isAdmin, onEdit }) {
  const plans = s.clos.map(c => c.plan).filter(Boolean)
  return <Card className="syl" title="ĐỀ CƯƠNG CHI TIẾT HỌC PHẦN" actions={isAdmin ? <button className="btn sm" onClick={onEdit}>Chỉnh sửa</button>
    : <span className="muted small">Bộ môn quản lý – giảng viên chỉ xem</span>}>
    <h4>1. Thông tin chung</h4>
    <dl className="kv">
      <dt>Tên học phần</dt><dd><b>{s.course_name}</b></dd>
      <dt>Mã học phần</dt><dd>{s.course_code}</dd>
      <dt>Số tín chỉ</dt><dd>{s.credits}{s.credits_theory != null || s.credits_practice != null ? ` (LT ${s.credits_theory ?? 0} – TN/TH ${s.credits_practice ?? 0})` : ''}{s.course_structure ? ` · cấu trúc ${s.course_structure}` : ''}</dd>
      <dt>Thuộc CTĐT</dt><dd>{s.programs.length ? s.programs.map(p => <div key={p.id}><Link to={`/programs/${p.id}`}><b>{p.code}</b> – {p.name}</Link>
        {p.semester_no ? ` · học kỳ ${p.semester_no}` : ''}{p.knowledge_block ? ` · ${p.knowledge_block}` : ''}{p.is_elective ? <Badge tone="amber">Tự chọn</Badge> : <Badge>Bắt buộc</Badge>}</div>)
        : <span className="muted">Chưa gán CTĐT</span>}</dd>
      <dt>Học phần trước / tiên quyết</dt><dd>{s.prerequisite_list.length ? s.prerequisite_list.map(p => <span key={p.course_code} className="chip-l">
        {p.id ? <Link to={`/courses/${p.id}`}>{p.course_code}{p.course_name ? ` – ${p.course_name}` : ''}</Link> : p.course_code}</span>) : 'Không'}</dd>
      <dt>Là tiên quyết của</dt><dd>{s.required_by.length ? s.required_by.map(p => <span key={p.id} className="chip-l"><Link to={`/courses/${p.id}`}>{p.course_code} – {p.course_name}</Link></span>) : '—'}</dd>
      <dt>Chỉ tiêu đạt CĐR môn học</dt><dd>{s.clo_target_pct}% SV đạt</dd>
    </dl>
    <h4>2. Mô tả vắn tắt học phần</h4>
    {s.description ? <p className="desc">{s.description}</p> : <p className="muted">Chưa có mô tả.</p>}
    <h4>3. Chuẩn đầu ra học phần (CLO)</h4>
    {s.clos.length ? <table className="tbl"><thead><tr><th>CLO</th><th>Mô tả</th><th>Mức Bloom</th><th>Đóng góp cho PLO (I/R/M)</th><th className="num-c">Câu hỏi</th></tr></thead>
      <tbody>{s.clos.map(c => <tr key={c.id}><td><b>{c.clo_code}</b></td><td className="wrap-cell">{c.description}</td><td>{c.bloom || '—'}</td>
        <td>{c.plos.length ? c.plos.map(p => <span key={`${p.program_code}${p.plo_id}`} className="chip-l" title={p.program_code}>{p.plo_code} <Lvl v={p.level} /> <small className="muted">{p.program_code}</small></span>) : <Badge tone="red">Chưa ánh xạ</Badge>}</td>
        <td className="num-c">{c.n_questions}</td></tr>)}</tbody></table> : <p className="muted">Chưa khai báo CLO.</p>}
    <h4>4. Học phần đáp ứng chỉ số PI của CTĐT (Phụ lục II)</h4>
    {s.programs.some(p => p.pis.length) ? s.programs.filter(p => p.pis.length).map(p => <div key={p.id} className="mb">
      <div className="small"><b>{p.code}</b> – {p.name}</div>
      <table className="tbl compact"><thead><tr><th>PLO</th><th>PI</th><th>Nội dung PI</th><th>Mức đáp ứng</th><th>Trình độ năng lực PI</th></tr></thead>
        <tbody>{p.pis.map(pi => <tr key={pi.id}><td>{pi.plo_code}</td><td><b>{pi.pi_code}</b></td><td className="wrap-cell">{pi.description}</td><td><Lvl v={pi.level} /></td><td>{pi.competency_level ?? '—'}</td></tr>)}</tbody></table>
    </div>) : <p className="muted">Chưa có ma trận học phần – PI.</p>}
    <h4>5. Nội dung học phần</h4>
    {s.outlines.length ? <ol className="steps">{s.outlines.map(o => <li key={o.id}><b>Chương {o.chapter_number}.</b> {o.chapter_name}</li>)}</ol> : <p className="muted">Chưa khai báo các chương.</p>}
    <h4>6. Kế hoạch kiểm tra – đánh giá CLO (BM6a)</h4>
    {plans.length ? <table className="tbl compact"><thead><tr><th>CLO</th><th>Học kỳ</th><th>Bài KT có CLO</th><th>Minh chứng</th><th>Phương pháp</th><th>Ngưỡng đạt</th><th>Chỉ tiêu</th></tr></thead>
      <tbody>{s.clos.filter(c => c.plan).map(c => <tr key={c.id}><td><b>{c.clo_code}</b></td><td>{c.plan.semester}</td><td>{c.plan.assessments_text || '—'}</td>
        <td>{{ process: 'Quá trình', final: 'Cuối kỳ', any: 'Mọi bài KT' }[c.plan.evidence_type]}</td><td>{c.plan.method}</td><td>≥ {c.plan.pass_threshold_pct}% điểm</td><td>{c.plan.target_pct}% SV</td></tr>)}</tbody></table>
      : <p className="muted">Chưa lập kế hoạch BM6a (giảng viên lập ở trang Kết quả CĐR của lớp).</p>}
  </Card>
}

function SectionsTab({ s, isAdmin, reload }) {
  const moodle = useMoodleBase()
  const [form, setForm] = useState(null)
  return <Card title={isAdmin ? 'Các lớp học phần của môn' : 'Các lớp bạn phụ trách'} actions={<>
    <ActionButton className="btn sm" okMsg={r => r.sections.map(x => `${x.section_code}: ${x.status}${x.added_students ? `, +${x.added_students} SV` : ''}`).join(' · ') || 'Không có lớp'}
      onRun={async () => { const r = await api.post(`/api/courses/${s.id}/moodle-sync-sections`); reload(); return r }}>⟳ Đồng bộ các lớp với Moodle</ActionButton>
    {isAdmin && <button className="btn sm primary" onClick={() => setForm({ course_id: s.id })}>+ Lớp HP</button>}</>}>
    <table className="tbl"><thead><tr><th>Mã lớp</th><th>Học kỳ</th><th>Giảng viên</th><th>SV</th><th>Bài KT</th><th>Moodle</th><th /></tr></thead>
      <tbody>{s.sections.map(x => <tr key={x.id}><td><Link to={`/sections/${x.id}`}><b>{x.section_code}</b></Link></td><td>{x.semester}</td><td>{x.lecturer}</td>
        <td>{x.n_students}</td><td>{x.n_exams}</td>
        <td>{x.moodle_course_id ? <a href={moodle && `${moodle}/course/view.php?id=${x.moodle_course_id}`} target="_blank" rel="noreferrer">Khóa học #{x.moodle_course_id} ↗</a> : <span className="muted">chưa gắn</span>}</td>
        <td className="row gap"><Link className="btn sm primary" to={`/sections/${x.id}`}>Mở lớp</Link><Link className="btn sm" to={`/sections/${x.id}/clo`}>BM6</Link>
          <Link className="btn sm ghost" to={`/sections/${x.id}/remedial`}>Phụ đạo</Link></td></tr>)}</tbody></table>
    {!s.sections.length && <p className="muted">Chưa có lớp học phần.</p>}
    <p className="muted small mt">"Đồng bộ các lớp với Moodle": lớp chưa gắn được tự gắn với khóa học Moodle có tên rút gọn hoặc mã khóa học trùng mã lớp; lớp đã gắn được cập nhật danh sách SV đang ghi danh.</p>
    {form && <SectionForm s={form} onClose={() => setForm(null)} onSaved={() => { setForm(null); reload() }} />}
  </Card>
}

// Đề của môn: soạn ở trang môn học, khi xuất mới giao cho lớp HP (mỗi lớp một bài riêng)
function ExamsTab({ data, onNew }) {
  const [dep, setDep] = useState(null)
  const d = data.data
  if (!d) return <Loading {...data} />
  return <Card title="Đề kiểm tra của môn" actions={<button className="btn sm primary" onClick={onNew}>+ Tạo bài kiểm tra</button>}>
    <p className="muted small">Soạn đề một lần cho cả môn; khi xuất (tạo Quiz trên Moodle, in đề và chấm phiếu, nhập điểm) chọn giao cho lớp học phần nào. Bài của từng lớp nằm ở trang lớp.</p>
    {d.exams.length ? <table className="tbl"><thead><tr><th>#</th><th>Tên đề</th><th>Hình thức</th><th>Loại minh chứng</th><th className="num-c">Số câu</th><th>Đã giao cho lớp</th><th /></tr></thead>
      <tbody>{d.exams.map(e => <tr key={e.id}><td>{e.id}</td><td><Link to={`/exams/${e.id}`}><b>{e.exam_title}</b></Link></td><td>{TYPE_VI[e.exam_type]}</td>
        <td>{e.assessment_type === 'final' ? 'Cuối kỳ' : 'Quá trình'}</td><td className="num-c">{e.questions.length}</td>
        <td>{e.deployments.length ? e.deployments.map(x => <Link key={x.exam_id} to={`/exams/${x.exam_id}`} className="chip-l" title={`${x.semester} · ${STATUS_VI[x.status]}`}>
          {x.section_code} <Badge tone={x.status === 'Analyzed' ? 'green' : x.status === 'Draft' ? 'gray' : 'blue'}>{STATUS_VI[x.status]}</Badge></Link>)
          : <span className="muted small">Chưa giao lớp nào</span>}</td>
        <td><div className="row gap"><button className="btn sm primary" onClick={() => setDep(e)}>Giao cho lớp HP / Xuất</button>
          <Link className="btn sm" to={`/exams/${e.id}`}>Mở</Link></div></td></tr>)}</tbody></table>
      : <div className="empty"><p>Chưa có đề nào của môn.</p><button className="btn primary" onClick={onNew}>+ Tạo bài kiểm tra</button></div>}
    {dep && <DeployDialog e={dep} onClose={() => setDep(null)} onDone={data.reload} />}
  </Card>
}

function ResultsTab({ s }) {
  const sems = [...new Set(s.clo_summary.map(r => r.semester))]
  return <>
    {!sems.length && <div className="alert">Môn chưa có kết quả đo CLO (cần ít nhất một bài KT đã phân tích).</div>}
    {sems.map(sem => <Card key={sem} title={`Kết quả CLO của môn – ${sem} (gộp các lớp HP, BM6b cấp môn)`}>
      <table className="tbl"><thead><tr><th>CLO</th><th className="num-c">SV đánh giá</th><th className="num-c">SV đạt</th><th className="num-c">Tỷ lệ đạt</th><th className="num-c">Chỉ tiêu</th><th>Kết luận</th></tr></thead>
        <tbody>{s.clo_summary.filter(r => r.semester === sem).map(r => <tr key={r.clo_code}><td><b>{r.clo_code}</b></td><td className="num-c">{r.n_evaluated}</td>
          <td className="num-c">{r.n_achieved}</td><td className="num-c">{fmtPct(r.achieved_pct)}</td><td className="num-c">{r.target_pct}%</td>
          <td><Achieved ok={Number(r.achieved_pct) + 1e-9 >= Number(r.target_pct)} /></td></tr>)}</tbody></table>
    </Card>)}
    <Card title="Kết quả từng lớp">
      <div className="row gap wrap">{s.sections.map(x => <Link key={x.id} className="btn" to={`/sections/${x.id}/clo`}>{x.section_code} – BM6</Link>)}</div>
    </Card>
  </>
}

function Setup({ courseId, s, reload }) {
  const course = useApi(`/api/courses/${courseId}`)
  const setup = useApi(`/api/courses/${courseId}/setup`)
  const progs = useApi('/api/programs').data
  const [dlg, setDlg] = useState(null)
  const c = course.data
  const all = () => { course.reload(); setup.reload(); reload() }
  if (!c) return <Loading {...course} />
  const inProg = new Set(s.programs.map(p => p.id))
  return <>
    <Card title="Các bước khai báo học phần">
      <ol className="steps setup">{setup.data?.steps.map(x => <li key={x.key} className={x.ok ? 'ok' : ''}>
        <span className={`badge ${x.ok ? 'green' : x.key === 'plans' ? 'amber' : 'red'}`}>{x.ok ? '✓' : '!'}</span> <b>{x.label}</b> <span className="muted small">– {x.detail}</span></li>)}</ol>
    </Card>
    <div className="grid2">
      <CourseInfo c={c} onSaved={all} />
      <Card title="Thuộc chương trình đào tạo">
        <table className="tbl compact"><thead><tr><th>CTĐT</th><th>Học kỳ</th><th>Khối kiến thức</th><th>Tự chọn</th><th /></tr></thead>
          <tbody>{progs?.map(p => { const m = s.programs.find(x => x.id === p.id); return <ProgRow key={p.id} p={p} m={m} courseId={courseId} onSaved={all} /> })}</tbody></table>
        <p className="muted small mt">{inProg.size ? `Học phần thuộc ${inProg.size} CTĐT.` : 'Học phần chưa thuộc CTĐT nào – CLO sẽ chọn được PLO của mọi CTĐT.'}</p>
      </Card>
    </div>
    <Outlines c={c} onSaved={all} />
    <Clos c={c} onEdit={x => setDlg(x)} onSaved={all} />
    {dlg && <CloForm c={c} clo={dlg} onClose={() => setDlg(null)} onSaved={() => { setDlg(null); all() }} />}
  </>
}

function ProgRow({ p, m, courseId, onSaved }) {
  const [f, setF] = useState({ semester_no: m?.semester_no ?? '', knowledge_block: m?.knowledge_block ?? '', is_elective: !!m?.is_elective })
  return <tr className={m ? '' : 'dim'}><td><b>{p.code}</b><div className="small muted">{p.name}</div></td>
    <td><input className="num tiny" type="number" min="1" max="12" value={f.semester_no} onChange={e => setF({ ...f, semester_no: e.target.value })} /></td>
    <td><input value={f.knowledge_block} onChange={e => setF({ ...f, knowledge_block: e.target.value })} placeholder="VD Cơ sở ngành" /></td>
    <td><input type="checkbox" checked={f.is_elective} onChange={e => setF({ ...f, is_elective: e.target.checked })} /></td>
    <td className="row gap"><ActionButton className="btn sm" okMsg="Đã lưu" onRun={async () => { await api.put(`/api/programs/${p.id}/courses`,
      { course_id: courseId, semester_no: f.semester_no === '' ? null : Number(f.semester_no), knowledge_block: f.knowledge_block || null, is_elective: f.is_elective }); onSaved() }}>{m ? 'Lưu' : '+ Thêm'}</ActionButton>
      {m && <ActionButton className="btn sm ghost" confirm={`Bỏ học phần khỏi ${p.code}? Ma trận PI của học phần trong CTĐT này cũng bị xóa.`} okMsg="Đã bỏ"
        onRun={async () => { await api.del(`/api/programs/${p.id}/courses/${courseId}`); onSaved() }}>✕</ActionButton>}</td></tr>
}
