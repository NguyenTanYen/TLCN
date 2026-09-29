import { Fragment, useState } from 'react'
import { Bar } from 'react-chartjs-2'
import { Link, useParams } from 'react-router-dom'
import { api, fmtNum, STATUS_VI } from '../api'
import { C } from '../charts'
import { ActionButton, Badge, Card, Field, Loading, Stat, diClass, pClass, useToast } from '../components/ui'
import { useApi } from '../hooks'

const STEPS = ['Draft', 'Published', 'Synced', 'Analyzed']
const CLS_TONE = { 'Tốt': 'green', 'Chấp nhận được': 'blue', 'Quá dễ': 'amber', 'Quá khó': 'amber', 'Cần xem lại (DI thấp)': 'amber', 'Cần loại bỏ/kiểm tra đáp án': 'red' }

export default function ExamDetail() {
  const { id } = useParams()
  const exam = useApi(`/api/exams/${id}`)
  const [tab, setTab] = useState('flow')
  const e = exam.data
  if (!e) return <Loading {...exam} />
  const analyzed = e.status === 'Analyzed'
  return (
    <>
      <div className="page-h">
        <div><div className="crumb"><Link to="/">Lớp học phần</Link> / <Link to={`/sections/${e.class_section_id}`}>{e.section_code}</Link> / Bài KT #{e.id}</div>
          <h1>{e.exam_title}</h1>
          <p className="muted">{e.course_code} – {e.course_name} · {e.semester} · {e.exam_type === 'online' ? 'Trực tuyến (Moodle)' : 'Trên giấy'} ·
            minh chứng {e.assessment_type === 'final' ? 'Cuối kỳ' : 'Quá trình'} · {e.questions.length} câu · thang {e.max_score}</p></div>
        <div className="row gap">{e.publish_flag ? <Badge tone="amber">SV đã xem được kết quả</Badge> : <Badge>Đang bảo lưu kết quả</Badge>}</div>
      </div>
      <div className="stepper">{STEPS.map((s, i) => <div key={s} className={STEPS.indexOf(e.status) >= i ? 'done' : ''}><span>{i + 1}</span>{STATUS_VI[s]}</div>)}</div>
      <div className="tabs">
        {[['flow', 'Quy trình & dữ liệu'], ['overview', 'Tổng quan điểm'], ['items', 'Phân tích câu hỏi'], ['students', 'Kết quả sinh viên'], ['log', 'Nhật ký đồng bộ']].map(([k, l]) =>
          <button key={k} className={tab === k ? 'on' : ''} disabled={!analyzed && ['overview', 'items', 'students'].includes(k)} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      {tab === 'flow' && <Flow e={e} reload={exam.reload} />}
      {tab === 'overview' && <Overview id={id} />}
      {tab === 'items' && <Items id={id} />}
      {tab === 'students' && <Students id={id} />}
      {tab === 'log' && <Log id={id} />}
    </>
  )
}

function Flow({ e, reload }) {
  const toast = useToast()
  const [quiz, setQuiz] = useState(e.moodle_quiz_id || '')
  const [mcourse, setMcourse] = useState(e.moodle_course_id || '')
  const [ver, setVer] = useState({ count: 2, start_code: 101, seed: '' })
  const upload = async file => {
    try {
      const r = await api.upload(`/api/exams/${e.id}/paper-import`, file)
      toast(`Đã nhập ${r.import.imported} phiếu, ${r.import.absent} SV vắng${r.import.warnings.length ? ` – ${r.import.warnings.length} cảnh báo` : ''}`, r.import.warnings.length ? 'amber' : 'green')
      r.import.warnings.slice(0, 5).forEach(w => toast(w, 'amber'))
      reload()
    } catch (ex) { toast(ex.message, 'red') }
  }
  return (
    <div className="grid2">
      <Card title="1. Đề thi">
        <table className="tbl compact"><thead><tr><th>#</th><th>Câu hỏi</th><th>CLO</th><th>Điểm</th></tr></thead>
          <tbody>{e.questions.map(q => <tr key={q.question_id} className={q.is_cancelled ? 'cancel' : ''}><td>{q.order_index}</td><td className="clip">{q.content}</td><td>{q.clos}</td><td>{q.points}</td></tr>)}</tbody></table>
      </Card>
      <div className="stack">
        {e.exam_type === 'online' ? <>
          <Card title="2. Phát hành lên Moodle">
            {e.moodle_quiz_id ? <p>Đã liên kết với <b>Quiz {e.moodle_quiz_id}</b> (khóa học Moodle {e.moodle_course_id || '?'}). Sinh viên vào Moodle để làm bài.</p> : <>
              <p className="muted">Tạo Quiz trực tiếp trên Moodle qua Web Service: nhập câu hỏi (idnumber <code>QB-&lt;id&gt;</code>) vào ngân hàng câu hỏi của khóa học, bật xáo trộn phương án và tự liên kết với bài KT.</p>
              <div className="row gap"><Field label="ID khóa học Moodle"><input className="num" value={mcourse} onChange={x => setMcourse(x.target.value)} /></Field>
                <ActionButton className="btn primary" disabled={!mcourse} okMsg={r => `Đã tạo Quiz ${r.quizid} (${r.questions} câu) trên Moodle`}
                  onRun={async () => { const r = await api.post(`/api/exams/${e.id}/moodle/create-quiz`, { moodle_course_id: Number(mcourse) }); reload(); return r }}>⇪ Tạo Quiz trên Moodle</ActionButton></div>
              <details className="mt"><summary className="muted">Cách thủ công: tải XML, tự import và nhập ID Quiz</summary>
                <ActionButton className="btn mt" onRun={async () => { await api.download(`/api/exams/${e.id}/moodle-xml`, 'moodle.xml'); reload() }}>⬇ Tải Moodle XML</ActionButton>
                <div className="row gap mt"><Field label="ID Quiz trên Moodle"><input className="num" value={quiz} onChange={x => setQuiz(x.target.value)} /></Field>
                  <ActionButton className="btn" okMsg="Đã liên kết Quiz" onRun={async () => { await api.patch(`/api/exams/${e.id}/link-quiz`, { moodle_quiz_id: Number(quiz) }); reload() }}>Liên kết</ActionButton></div>
              </details></>}
          </Card>
          <Card title="3. Đồng bộ bài làm từ Moodle">
            <p className="muted">Đọc trực tiếp CSDL Moodle (thủ tục <code>sp_sync_exam</code>): lấy lượt nộp cuối, giải mã thứ tự xáo trộn phương án, ghi nhận SV vắng.</p>
            <ActionButton className="btn primary" disabled={!e.moodle_quiz_id} okMsg={r => `Đồng bộ ${r.sync.n_attempts} bài làm, ${r.sync.n_absent} vắng – đã phân tích`}
              onRun={async () => { const r = await api.post(`/api/exams/${e.id}/sync`); reload(); return r }}>⟳ Đồng bộ &amp; phân tích</ActionButton>
            {e.last_synced_at && <p className="muted mt">Lần gần nhất: {e.last_synced_at.replace('T', ' ')}</p>}
          </Card>
        </> : <>
          <Card title="2. Sinh mã đề & in đề">
            {e.versions.length === 0 ? <>
              <p className="muted">Mỗi mã đề hoán vị thứ tự câu hỏi và phương án; hệ thống lưu lại để chấm theo đúng mã đề.</p>
              <div className="row gap">
                <Field label="Số mã đề"><input className="num" type="number" min="1" max="8" value={ver.count} onChange={x => setVer({ ...ver, count: x.target.value })} /></Field>
                <Field label="Mã đầu"><input className="num" type="number" value={ver.start_code} onChange={x => setVer({ ...ver, start_code: x.target.value })} /></Field>
                <Field label="Seed (tùy chọn)"><input className="num" value={ver.seed} onChange={x => setVer({ ...ver, seed: x.target.value })} /></Field>
              </div>
              <ActionButton className="btn primary" okMsg="Đã sinh mã đề" onRun={async () => { await api.post(`/api/exams/${e.id}/versions`, { count: Number(ver.count), start_code: Number(ver.start_code), seed: ver.seed ? Number(ver.seed) : null }); reload() }}>Sinh mã đề</ActionButton>
            </> : <div className="row gap wrap">
              {e.versions.map(v => <ActionButton key={v.id} className="btn" onRun={() => api.download(`/api/exams/${e.id}/versions/${v.id}/paper.docx`, `de_${v.version_code}.docx`)}>⬇ Đề mã {v.version_code} (.docx)</ActionButton>)}
              <ActionButton className="btn" onRun={() => api.download(`/api/exams/${e.id}/answer-key.xlsx`, 'dap_an.xlsx')}>⬇ Đáp án các mã đề (.xlsx)</ActionButton>
            </div>}
          </Card>
          <Card title="3. Nhập phiếu trả lời">
            <p className="muted">Tệp CSV/XLSX từ máy chấm: <code>student_code, version_code, Q1…Qn</code> (nhãn đã tô; để trống = bỏ trống). SV trong danh sách lớp không có phiếu được ghi nhận vắng.</p>
            <label className={`btn primary ${e.versions.length ? '' : 'disabled'}`}>⬆ Chọn tệp phiếu trả lời
              <input type="file" hidden accept=".csv,.xlsx" disabled={!e.versions.length} onChange={x => x.target.files[0] && upload(x.target.files[0])} /></label>
          </Card>
        </>}
        <Card title="4. Phân tích & công bố">
          <p className="muted">Tính p, DI (Kelley 27%), điểm CLO từng SV, tổng hợp CLO → PI → PLO và lộ trình ôn tập cá nhân.
            Khi công bố, kết quả (radar CLO, nhận định, chương cần ôn) được gửi sang Moodle để sinh viên xem tại khóa học → <i>Kết quả phân tích CĐR</i>.</p>
          <div className="row gap wrap">
            <ActionButton className="btn" disabled={!e.n_attempts} okMsg="Đã phân tích lại" onRun={async () => { await api.post(`/api/exams/${e.id}/analyze`); reload() }}>Phân tích lại</ActionButton>
            <ActionButton className={e.publish_flag ? 'btn' : 'btn primary'} disabled={e.status !== 'Analyzed'}
              okMsg={r => (r.publish_flag ? 'Đã công bố cho SV' : 'Đã thu hồi') + (r.moodle ? ` – Moodle đã nhận ${r.moodle.saved} kết quả` : r.moodle_error ? ` – chưa gửi được lên Moodle: ${r.moodle_error}` : '')}
              onRun={async () => { const r = await api.patch(`/api/exams/${e.id}/publish`, { publish: !e.publish_flag }); reload(); return r }}>{e.publish_flag ? 'Thu hồi công bố' : 'Công bố kết quả lên Moodle'}</ActionButton>
            <ActionButton className="btn" disabled={e.status !== 'Analyzed' || !e.moodle_course_id} okMsg={r => `Moodle đã nhận ${r.saved}/${r.sent} kết quả${r.notfound.length ? ` – không tìm thấy: ${r.notfound.join(', ')}` : ''}`}
              onRun={() => api.post(`/api/exams/${e.id}/moodle/push-results`)}>⇪ Gửi lại kết quả lên Moodle</ActionButton>
            {e.status === 'Draft' && <ActionButton className="btn danger" onRun={async () => { await api.del(`/api/exams/${e.id}`); window.location.href = `/sections/${e.class_section_id}` }}>Xóa bài KT</ActionButton>}
          </div>
          <p className="mt"><b>{e.n_attempts}</b> bài làm · <b>{e.n_absent}</b> vắng</p>
        </Card>
      </div>
    </div>
  )
}

function Overview({ id }) {
  const { data: o, ...st } = useApi(`/api/exams/${id}/overview`)
  if (!o) return <Loading {...st} />
  return (
    <>
      <div className="stats">
        <Stat label="SV dự thi" value={o.n_students} sub={`${o.n_absent} vắng`} />
        <Stat label="Điểm trung bình" value={fmtNum(o.mean)} sub={`/ ${o.max_score}`} />
        <Stat label="Thấp nhất – cao nhất" value={`${o.min} – ${o.max}`} />
        <Stat label="Tỷ lệ ≥ 50% thang điểm" value={`${o.pass_rate}%`} tone={o.pass_rate >= 50 ? 'green' : 'red'} />
      </div>
      <Card title="Phổ điểm">
        <div className="chart"><Bar data={{ labels: o.histogram.map(h => h.range), datasets: [{ label: 'Số SV', data: o.histogram.map(h => h.count), backgroundColor: C.blue, borderRadius: 4 }] }}
          options={{ maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { ticks: { precision: 0 }, title: { display: true, text: 'Số SV' } }, x: { title: { display: true, text: 'Khoảng điểm' } } } }} /></div>
      </Card>
    </>
  )
}

function Items({ id }) {
  const { data, ...st } = useApi(`/api/exams/${id}/item-stats`)
  const [open, setOpen] = useState(null)
  if (!data) return <Loading {...st} />
  const flagged = data.filter(d => !['Tốt', 'Chấp nhận được'].includes(d.classification))
  return (
    <>
      <div className="stats">
        <Stat label="Số câu" value={data.length} />
        <Stat label="Câu tốt / chấp nhận" value={data.length - flagged.length} tone="green" />
        <Stat label="Câu cần xem lại" value={flagged.length} tone={flagged.length ? 'amber' : ''} />
        <Stat label="DI âm (nghi sai đáp án)" value={data.filter(d => Number(d.di_value) < 0).length} tone="red" />
      </div>
      <Card title="Độ khó p và độ phân biệt DI từng câu">
        <div className="chart"><Bar data={{ labels: data.map(d => `C${d.order_index}`), datasets: [
          { label: 'Độ khó p', data: data.map(d => d.p_value), backgroundColor: C.blueA, borderColor: C.blue, borderWidth: 1 },
          { label: 'Độ phân biệt DI', data: data.map(d => d.di_value), backgroundColor: data.map(d => Number(d.di_value) < 0 ? C.red : Number(d.di_value) < 0.2 ? C.amber : C.green) }] }}
          options={{ maintainAspectRatio: false, scales: { y: { min: -1, max: 1 } } }} /></div>
        <p className="muted">Ngưỡng tham khảo: p ∈ [0,25; 0,85]; DI ≥ 0,3 tốt, 0,2–0,3 chấp nhận, &lt; 0,2 cần xem lại, &lt; 0 cần kiểm tra đáp án (Ebel &amp; Frisbie, 1991).</p>
      </Card>
      <Card title="Bảng chỉ số câu hỏi">
        <table className="tbl">
          <thead><tr><th>#</th><th>ID</th><th>Nội dung</th><th>Chương</th><th>CLO</th><th>p</th><th>DI</th><th>Phân loại</th><th /></tr></thead>
          <tbody>{data.map(d => <Fragment key={d.question_id}>
            <tr>
              <td>{d.order_index}</td><td>{d.question_id}</td><td className="clip">{d.content}</td><td>{d.chapter}</td><td>{d.clos}</td>
              <td className={`num-c ${pClass(d.p_value)}`}>{fmtNum(d.p_value, 3)}</td><td className={`num-c ${diClass(d.di_value)}`}>{fmtNum(d.di_value, 3)}</td>
              <td><Badge tone={CLS_TONE[d.classification] || 'gray'}>{d.classification}</Badge></td>
              <td><button className="btn sm ghost" onClick={() => setOpen(open === d.question_id ? null : d.question_id)}>{open === d.question_id ? '▲' : 'Phương án ▼'}</button></td>
            </tr>
            {open === d.question_id && <tr key={`${d.question_id}-x`} className="sub"><td colSpan={9}>
              <div className="dist">{d.distribution.map(x => {
                const pct = 100 * x.n / d.n_students
                return <div key={x.label} className="dist-row"><span className="dl">{x.label}{x.is_correct && ' ✓'}</span>
                  <span className="bar"><i style={{ width: `${pct}%` }} className={x.is_correct ? 'ok' : ''} /></span><span>{x.n} SV ({pct.toFixed(1)}%)</span></div>
              })}</div>
            </td></tr>}
          </Fragment>)}</tbody>
        </table>
      </Card>
    </>
  )
}

function Students({ id }) {
  const { data, ...st } = useApi(`/api/exams/${id}/students`)
  if (!data) return <Loading {...st} />
  const clos = [...new Set(data.flatMap(d => Object.keys(d.clos)))].sort()
  return (
    <Card title="Kết quả từng sinh viên theo CLO" actions={<span className="muted">✓ đạt ngưỡng · ✗ chưa đạt</span>}>
      <table className="tbl">
        <thead><tr><th>MSSV</th><th>Họ tên</th><th>Nguồn</th><th>Mã đề</th><th>Điểm thô</th>{clos.map(c => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{data.map(d => <tr key={d.attempt_id} className={d.status === 'absent' ? 'cancel' : ''}>
          <td>{d.student_code}</td><td>{d.full_name}</td><td>{d.status === 'absent' ? 'Vắng' : d.source === 'moodle' ? 'Moodle' : 'Phiếu giấy'}</td>
          <td>{d.version_code || '—'}</td><td>{d.status === 'absent' ? '—' : d.total_score}</td>
          {clos.map(c => <td key={c} className={d.clos[c] ? (d.clos[c].ok ? 'ok-t' : 'bad-t') : ''}>{d.clos[c] ? `${d.clos[c].pct}% ${d.clos[c].ok ? '✓' : '✗'}` : '—'}</td>)}
        </tr>)}</tbody>
      </table>
    </Card>
  )
}

function Log({ id }) {
  const { data, ...st } = useApi(`/api/exams/${id}/sync-runs`)
  if (!data) return <Loading {...st} />
  const K = { moodle: 'Đồng bộ Moodle', paper: 'Nhập phiếu giấy', analyze: 'Phân tích' }
  return <Card><table className="tbl"><thead><tr><th>#</th><th>Loại</th><th>Bắt đầu</th><th>Kết thúc</th><th>Kết quả</th><th>Bài làm</th><th>Vắng</th><th>Ghi chú</th></tr></thead>
    <tbody>{data.map(r => <tr key={r.id}><td>{r.id}</td><td>{K[r.kind]}</td><td>{r.started_at?.replace('T', ' ')}</td><td>{r.finished_at?.replace('T', ' ')}</td>
      <td><Badge tone={r.status === 'success' ? 'green' : r.status === 'failed' ? 'red' : 'gray'}>{r.status}</Badge></td><td>{r.n_attempts ?? '—'}</td><td>{r.n_absent ?? '—'}</td><td className="clip">{r.message}</td></tr>)}</tbody></table></Card>
}
