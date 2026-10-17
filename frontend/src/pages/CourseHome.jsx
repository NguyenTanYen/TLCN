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
import { AssessmentsForm, GeneralForm, OutlineForm, ReferencesForm, SYL_TEXT, TextForm } from '../components/SyllabusForms'



export default function CourseHome() {
  const { id } = useParams()
  const [sp, setSp] = useSearchParams()
  const tab = sp.get('tab') || 'syllabus'
  const isAdmin = auth.user()?.role === 'admin'
  const [ver, setVer] = useState(null)   // góp ý F1: xem một phiên bản đề cương cụ thể (mặc định theo vai trò)
  const syl = useApi(`/api/courses/${id}/syllabus${ver ? `?version=${ver}` : ''}`)
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
    {s && tab === 'syllabus' && <Syllabus s={s} isAdmin={isAdmin} onEdit={() => setSp({ tab: 'setup' })} setVer={setVer} reload={syl.reload} />}
    {s && tab === 'sections' && <SectionsTab s={s} isAdmin={isAdmin} reload={syl.reload} />}
    {s && tab === 'exams' && <ExamsTab data={cex} onNew={() => setCreating(true)} />}
    {s && tab === 'results' && <ResultsTab s={s} />}
    {creating && s && cex.data && <NewExamFlow course={{ id: Number(id), code: s.course_code }} sections={cex.data.sections} onClose={closeNew} />}
    {s && tab === 'combine' && <Combine courseId={Number(id)} />}
    {s && tab === 'setup' && isAdmin && <Setup courseId={Number(id)} s={s} reload={syl.reload} />}
  </>
}

const Lvl = ({ v }) => v ? <span className={`lvl ${/^[IRM]$/.test(v) ? v : 'n'}`}>{v}</span> : null

export function Syllabus({ s, isAdmin, onEdit, setVer, reload }) {
  const plans = s.clos.map(c => c.plan).filter(Boolean)
  const d = s.doc
  const [dlg, setDlg] = useState(null)
  const canEdit = isAdmin && d?.status === 'draft'                 // bản nháp mới nhất mới sửa được
  const edit = (kind, extra) => canEdit && <button className="btn sm ghost no-print" onClick={() => setDlg({ kind, ...extra })}>Sửa</button>
  const done = () => { setDlg(null); reload() }
  const run = async (path, v) => { await api.post(path); setVer(null); reload(); return v }
  const lt = s.outlines.reduce((n, o) => n + (o.theory_hours || 0), 0), th = s.outlines.reduce((n, o) => n + (o.practice_hours || 0), 0)
  const total = (d?.assessments || []).reduce((n, a) => n + a.weight_pct, 0)
  const text = (n, k) => <><h4>{n}. {SYL_TEXT[k]} {edit('text', { field: k })}</h4>
    {d?.[k] ? <p className="desc prewrap">{d[k]}</p> : <p className="muted">Chưa có nội dung.</p>}</>
  return <>
  {isAdmin && (!d || (d.status === 'draft' && d.is_latest)) && <Card className="no-print" title={d ? `Kiểm tra trước khi duyệt – bản nháp phiên bản ${d.version_no}` : 'Học phần chưa có đề cương chi tiết'}
    actions={d ? <ActionButton className="btn sm primary" okMsg="Đã duyệt đề cương" onRun={() => run(`/api/courses/${s.id}/syllabus/approve`)}
      disabled={s.checks.some(k => k.required && !k.ok)}>✓ Duyệt đề cương</ActionButton>
      : <ActionButton className="btn sm primary" okMsg="Đã tạo bản nháp phiên bản 1" onRun={() => run(`/api/courses/${s.id}/syllabus/versions`)}>+ Soạn đề cương</ActionButton>}>
    <ul className="checklist">{s.checks.map(k => <li key={k.key} className={k.ok ? 'ok' : k.required ? 'bad' : 'warn'}>
      <span aria-hidden>{k.ok ? '✓' : k.required ? '✕' : '!'}</span> {k.label}{k.detail && <span className="small muted"> – {k.detail}</span>}</li>)}</ul>
    <p className="small muted">Mục ✕ là bắt buộc trước khi duyệt; mục ! chỉ là cảnh báo. Chương và CLO sửa ở tab "Khai báo (Bộ môn)".</p>
  </Card>}
  <Card className="syl" title="ĐỀ CƯƠNG CHI TIẾT HỌC PHẦN" actions={<div className="row gap wrap no-print">
    {d && <Badge tone={d.status === 'approved' ? 'green' : d.status === 'draft' ? 'amber' : 'gray'}>Phiên bản {d.version_no}: {d.status_label}</Badge>}
    {s.versions.length > 1 && <select value={d?.version_no || ''} onChange={e => setVer(Number(e.target.value))} aria-label="Xem phiên bản">
      {s.versions.map(v => <option key={v.version_no} value={v.version_no}>Phiên bản {v.version_no} – {v.status_label}</option>)}</select>}
    {isAdmin && d && d.status !== 'draft' && !s.versions.some(v => v.status === 'draft') &&
      <ActionButton className="btn sm" okMsg="Đã tạo bản nháp mới" onRun={() => run(`/api/courses/${s.id}/syllabus/versions`)}>Tạo phiên bản mới</ActionButton>}
    {isAdmin ? <button className="btn sm" onClick={onEdit}>Khai báo chương, CLO</button> : <span className="muted small">Bộ môn quản lý – giảng viên chỉ xem</span>}</div>}>
    {isAdmin && d && d.status !== 'draft' && <div className="alert blue no-print">Đề cương đã duyệt không sửa trực tiếp – bấm "Tạo phiên bản mới" để soạn bản nháp (chép nội dung bản này).</div>}
    <h4>1. Thông tin chung {edit('general')}</h4>
    <dl className="kv">
      <dt>Tên học phần</dt><dd><b>{s.course_name}</b>{d?.english_name && <div className="muted">{d.english_name}</div>}</dd>
      <dt>Mã học phần</dt><dd>{s.course_code}</dd>
      <dt>Số tín chỉ</dt><dd>{s.credits}{s.credits_theory != null || s.credits_practice != null ? ` (LT ${s.credits_theory ?? 0} – TN/TH ${s.credits_practice ?? 0})` : ''}{s.course_structure ? ` · cấu trúc ${s.course_structure}` : ''}
        {d?.self_study_hours != null && ` · tự học ${d.self_study_hours} giờ`}</dd>
      <dt>Thuộc CTĐT</dt><dd>{s.programs.length ? s.programs.map(p => <div key={p.id}><Link to={`/programs/${p.id}`}><b>{p.code}</b> – {p.name}</Link>
        {p.semester_no ? ` · học kỳ ${p.semester_no}` : ''}{p.knowledge_block ? ` · ${p.knowledge_block}` : ''}{p.is_elective ? <Badge tone="amber">Tự chọn</Badge> : <Badge>Bắt buộc</Badge>}</div>)
        : <span className="muted">Chưa gán CTĐT</span>}</dd>
      <dt>Học phần trước / tiên quyết</dt><dd>{s.prerequisite_list.length ? s.prerequisite_list.map(p => <span key={p.course_code} className="chip-l">
        {p.id ? <Link to={`/courses/${p.id}`}>{p.course_code}{p.course_name ? ` – ${p.course_name}` : ''}</Link> : p.course_code}</span>) : 'Không'}</dd>
      <dt>Là tiên quyết của</dt><dd>{s.required_by.length ? s.required_by.map(p => <span key={p.id} className="chip-l"><Link to={`/courses/${p.id}`}>{p.course_code} – {p.course_name}</Link></span>) : '—'}</dd>
      <dt>Chỉ tiêu đạt CĐR môn học</dt><dd>{s.clo_target_pct}% SV đạt</dd>
      {d && <><dt>Áp dụng từ</dt><dd>{d.effective_semester || '—'}{d.approved_at && <span className="muted"> · duyệt ngày {new Date(d.approved_at).toLocaleDateString('vi-VN')}</span>}</dd></>}
    </dl>
    <h4>2. Mô tả vắn tắt học phần</h4>
    {s.description ? <p className="desc">{s.description}</p> : <p className="muted">Chưa có mô tả.</p>}
    {text(3, 'objectives')}
    <h4>4. Chuẩn đầu ra học phần (CLO)</h4>
    {s.clos.length ? <table className="tbl"><thead><tr><th>CLO</th><th>Mô tả</th><th>Mức Bloom</th><th>Đóng góp cho PI › PLO (I/R/M)</th><th className="num-c">Câu hỏi</th></tr></thead>
      <tbody>{s.clos.map(c => <tr key={c.id}><td><b>{c.clo_code}</b></td><td className="wrap-cell">{c.description}</td><td>{c.bloom || '—'}</td>
        <td>{c.pis?.length ? c.pis.map(p => <span key={`${p.program_code}${p.pi_id}`} className="chip-l" title={p.program_code}>{p.plo_code} › {p.pi_code} <Lvl v={p.level} /> <small className="muted">{p.program_code}</small></span>)
          : c.plos.length ? <>{c.plos.map(p => <span key={`${p.program_code}${p.plo_id}`} className="chip-l" title={p.program_code}>{p.plo_code} <Lvl v={p.level} /> <small className="muted">{p.program_code}</small></span>)} <Badge tone="amber">Chưa gắn PI</Badge></>
          : <Badge tone="red">Chưa ánh xạ</Badge>}</td>
        <td className="num-c">{c.n_questions}</td></tr>)}</tbody></table> : <p className="muted">Chưa khai báo CLO.</p>}
    <h4>5. Học phần đáp ứng chỉ số PI của CTĐT (Phụ lục II)</h4>
    {s.programs.some(p => p.pis.length) ? s.programs.filter(p => p.pis.length).map(p => <div key={p.id} className="mb">
      <div className="small"><b>{p.code}</b> – {p.name}</div>
      <table className="tbl compact"><thead><tr><th>PLO</th><th>PI</th><th>Nội dung PI</th><th>Mức đáp ứng</th><th>Trình độ năng lực PI</th><th>CLO đáp ứng</th></tr></thead>
        <tbody>{p.pis.map(pi => <tr key={pi.id} className={pi.covered ? '' : 'warn-row'}><td>{pi.plo_code}</td><td><b>{pi.pi_code}</b></td><td className="wrap-cell">{pi.description}</td><td><Lvl v={pi.level} /></td><td>{pi.competency_level ?? '—'}</td>
          <td>{pi.clos?.length ? pi.clos.map(m => <span key={m.clo_id} className="pill blue">{s.clos.find(c => c.id === m.clo_id)?.clo_code} ({m.level})</span>)
            : <Badge tone="red" title="CTĐT giao PI này cho học phần nhưng chưa có CLO nào đáp ứng">Chưa có CLO</Badge>}</td></tr>)}</tbody></table>
    </div>) : <p className="muted">Chưa có ma trận học phần – PI.</p>}
    <h4>6. Nội dung chi tiết học phần</h4>
    {s.outlines.length ? <table className="tbl compact"><thead><tr><th>Chương</th><th>Nội dung</th><th className="num-c">LT</th><th className="num-c">TH</th><th>CLO</th>{isAdmin && <th className="no-print" />}</tr></thead>
      <tbody>{s.outlines.map(o => <tr key={o.id}><td><b>Chương {o.chapter_number}.</b> {o.chapter_name}</td>
        <td className="wrap-cell">{o.content || <span className="muted">—</span>}{o.teaching_activities && <div className="small muted">Hoạt động dạy học: {o.teaching_activities}</div>}</td>
        <td className="num-c">{o.theory_hours ?? '—'}</td><td className="num-c">{o.practice_hours ?? '—'}</td>
        <td>{o.clos.map(x => x.clo_code).join(', ') || <span className="muted">—</span>}</td>
        {isAdmin && <td className="no-print"><button className="btn sm ghost" onClick={() => setDlg({ kind: 'outline', o })}>Sửa</button></td>}</tr>)}
        <tr className="sub"><td colSpan={2}><b>Tổng số tiết</b></td><td className="num-c"><b>{lt}</b></td><td className="num-c"><b>{th}</b></td><td colSpan={isAdmin ? 2 : 1} /></tr></tbody></table>
      : <p className="muted">Chưa khai báo các chương.{isAdmin && <> Thêm chương ở tab <button className="btn sm ghost no-print" onClick={onEdit}>Khai báo (Bộ môn)</button>, sau đó bấm <b>Sửa</b> từng chương ở đây để nhập nội dung, số tiết và CLO.</>}</p>}
    {text(7, 'teaching_methods')}
    <h4>8. Đánh giá học phần {edit('assess')}</h4>
    {d?.assessments.length ? <table className="tbl compact"><thead><tr><th>Mã</th><th>Thành phần</th><th>Hình thức</th><th>Thời điểm</th><th className="num-c">Tỷ trọng</th><th>CLO</th></tr></thead>
      <tbody>{d.assessments.map(a => <tr key={a.id}><td><b>{a.component_code}</b></td><td>{a.name}</td><td>{a.method || '—'}</td><td>{a.timing || '—'}</td>
        <td className="num-c">{a.weight_pct}%</td><td>{a.clos.map(x => x.clo_code).join(', ') || '—'}</td></tr>)}
        <tr className={`sub ${Math.abs(total - 100) > 0.01 ? 'warn-row' : ''}`}><td colSpan={4}><b>Tổng</b></td><td className="num-c"><b>{total}%</b></td><td /></tr></tbody></table>
      : <p className="muted">Chưa có kế hoạch đánh giá học phần.</p>}
    <h4>9. Kế hoạch kiểm tra – đánh giá CLO (BM6a)</h4>
    {plans.length ? <table className="tbl compact"><thead><tr><th>CLO</th><th>Học kỳ</th><th>Bài KT có CLO</th><th>Minh chứng</th><th>Phương pháp</th><th>Ngưỡng đạt</th><th>Chỉ tiêu</th></tr></thead>
      <tbody>{s.clos.filter(c => c.plan).map(c => <tr key={c.id}><td><b>{c.clo_code}</b></td><td>{c.plan.semester}</td><td>{c.plan.assessments_text || '—'}</td>
        <td>{{ process: 'Quá trình', final: 'Cuối kỳ', any: 'Mọi bài KT' }[c.plan.evidence_type]}</td><td>{c.plan.method}</td><td>≥ {c.plan.pass_threshold_pct}% điểm</td><td>{c.plan.target_pct}% SV</td></tr>)}</tbody></table>
      : <p className="muted">Chưa lập kế hoạch BM6a (giảng viên lập ở trang Kết quả CĐR của lớp).</p>}
    <h4>10. Tài liệu học tập {edit('refs')}</h4>
    {[['main', 'Giáo trình chính'], ['extra', 'Tài liệu tham khảo']].map(([t, label]) => { const r = (d?.references || []).filter(x => x.ref_type === t)
      return <div key={t}><b className="small">{label}</b>{r.length ? <ol className="refs">{r.map(x => <li key={x.id}>{x.citation}</li>)}</ol> : <p className="muted">—</p>}</div> })}
    {text(11, 'course_policy')}
  </Card>
  {dlg?.kind === 'general' && <GeneralForm s={s} onClose={() => setDlg(null)} onSaved={done} />}
  {dlg?.kind === 'text' && <TextForm s={s} field={dlg.field} onClose={() => setDlg(null)} onSaved={done} />}
  {dlg?.kind === 'assess' && <AssessmentsForm s={s} onClose={() => setDlg(null)} onSaved={done} />}
  {dlg?.kind === 'refs' && <ReferencesForm s={s} onClose={() => setDlg(null)} onSaved={done} />}
  {dlg?.kind === 'outline' && <OutlineForm s={s} o={dlg.o} onClose={() => setDlg(null)} onSaved={done} />}
  </>
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
        <span className={`badge ${x.ok ? 'green' : ['plans', 'syllabus'].includes(x.key) ? 'amber' : 'red'}`}>{x.ok ? '✓' : '!'}</span> <b>{x.label}</b> <span className="muted small">– {x.detail}</span></li>)}</ol>
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
