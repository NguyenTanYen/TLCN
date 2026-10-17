import { Fragment, useState } from 'react'
import { Bar } from 'react-chartjs-2'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, fmtNum, STATUS_VI } from '../api'
import { C } from '../charts'
import { ActionButton, Badge, Card, Crumbs, Field, Loading, Stat, diClass, pClass, useToast } from '../components/ui'
import { ManualGrades } from '../components/ManualExam'
import PaperSystem from '../components/PaperSystem'
import { useApi } from '../hooks'
import { MatrixTable } from '../components/Blueprint'
import Timing from '../components/Timing'
import ExamTemplate from '../components/ExamTemplate'
import { DeployDialog, TYPE_VI } from '../components/NewExam'

const STEPS = ['Draft', 'Published', 'Synced', 'Analyzed']
const CLS_TONE = { 'Tốt': 'green', 'Chấp nhận được': 'blue', 'Quá dễ': 'amber', 'Quá khó': 'amber', 'Cần xem lại (DI thấp)': 'amber', 'Cần loại bỏ/kiểm tra đáp án': 'red' }


export default function ExamDetail() {
  const { id } = useParams()
  const exam = useApi(`/api/exams/${id}`)
  const [sp, setSp] = useSearchParams()
  const tab = sp.get('tab') || 'flow'
  const setTab = t => setSp({ tab: t })
  const [copy, setCopy] = useState(false)
  const e = exam.data
  if (!e) return <Loading {...exam} />
  if (e.is_template) return <ExamTemplate e={e} reload={exam.reload} />
  const analyzed = e.status === 'Analyzed'
  return (
    <>
      <div className="page-h">
        <div><Crumbs items={[['/', 'Môn học của tôi'], [`/courses/${e.course_id}`, e.course_code], [`/sections/${e.class_section_id}`, e.section_code], [null, `Bài KT #${e.id}`]]} />
          <h1>{e.exam_title} {e.parent_exam_id && <Badge tone="amber">Phụ đạo</Badge>}</h1>
          <p className="muted">{e.course_code} – {e.course_name} · {e.semester} · {TYPE_VI[e.exam_type]} ·
            minh chứng {e.assessment_type === 'final' ? 'Cuối kỳ' : 'Quá trình'} · {e.questions.length} {e.exam_type === 'manual' ? 'câu/ý' : 'câu'} · thang {e.max_score}
            {e.target_students ? ` · dành cho ${e.target_students.split(',').length} SV` : ''}</p></div>
        <div className="row gap wrap">
          <ActionButton className={`btn ${e.counts_for_clo ? '' : 'ghost'}`} title="Gộp bài này vào kết quả CLO của lớp (BM6, PI, PLO)"
            okMsg={r => r.counts_for_clo ? 'Đã gộp vào minh chứng CLO' : 'Đã bỏ khỏi minh chứng CLO'}
            onRun={async () => { const r = await api.patch(`/api/exams/${e.id}/evidence`, { counts_for_clo: !e.counts_for_clo }); exam.reload(); return r }}>
            {e.counts_for_clo ? '✓ Minh chứng CLO' : 'Không tính minh chứng'}</ActionButton>
          <button className="btn" onClick={() => setCopy(true)}>⧉ Dùng đề cho lớp khác</button>
          {analyzed && <Link className="btn" to={`/sections/${e.class_section_id}/stats?exam=${e.id}`}>Thống kê lớp</Link>}
          {analyzed && <ActionButton className="btn primary" title="Biểu mẫu BM6c riêng của bài kiểm tra này: tổng hợp + minh chứng từng CLO bài KT đo"
            onRun={() => api.download(`/api/reports/exams/${e.id}/bm6c.xlsx`, `BM6c_${e.section_code}.xlsx`)}>⬇ Xuất BM6c bài KT này</ActionButton>}
          {e.publish_flag ? <Badge tone="amber">SV đã xem được kết quả</Badge> : <Badge>Đang bảo lưu kết quả</Badge>}</div>
      </div>
      {e.timing_alerts?.n_warning > 0 && tab !== 'timing' && <div className="alert amber row gap wrap">
        <span>⚠ <b>{e.timing_alerts.n_warning} SV</b> có dấu hiệu làm bài bất thường (làm quá nhanh – nghi chọn đại, chọn xong không nộp để hết giờ…).</span>
        <span className="grow" /><button className="btn sm" onClick={() => setTab('timing')}>Xem thời gian làm bài</button></div>}
      <div className="stepper">{STEPS.map((s, i) => <div key={s} className={STEPS.indexOf(e.status) >= i ? 'done' : ''}><span>{i + 1}</span>{e.exam_type === 'manual' && s === 'Synced' ? 'Đã nhập điểm' : STATUS_VI[s]}</div>)}</div>
      <div className="tabs">
        {[['flow', e.exam_type === 'manual' ? 'Câu/ý & nhập điểm' : 'Quy trình & dữ liệu'], ['overview', 'Tổng quan điểm'], ['items', 'Phân tích câu hỏi'], ['students', 'Kết quả sinh viên'],
          ...(e.exam_type === 'online' ? [['timing', 'Thời gian làm bài']] : []), ['log', 'Nhật ký']].map(([k, l]) =>
          <button key={k} className={tab === k ? 'on' : ''} disabled={(!analyzed && ['overview', 'items', 'students'].includes(k)) || (k === 'timing' && !['Synced', 'Analyzed'].includes(e.status))} onClick={() => setTab(k)}>
            {l}{k === 'timing' && e.timing_alerts?.n_warning ? <span className="tab-badge">{e.timing_alerts.n_warning}</span> : null}</button>)}
      </div>
      {(tab === 'flow' || tab === 'grades') && (e.exam_type === 'manual' ? <ManualFlow e={e} reload={exam.reload} /> : <Flow e={e} reload={exam.reload} />)}
      {tab === 'overview' && <Overview id={id} />}
      {tab === 'items' && <Items id={id} manual={e.exam_type === 'manual'} />}
      {tab === 'students' && <Students id={id} cs={e.class_section_id} />}
      {tab === 'timing' && <Timing examId={id} sectionCode={e.section_code} />}
      {tab === 'log' && <Log id={id} />}
      {copy && <DeployDialog e={e} onClose={() => setCopy(false)} />}
    </>
  )
}

function ManualFlow({ e, reload }) {
  const nav = useNavigate()
  return <>
    <ManualGrades e={e} reload={reload} />
    <Card title="Phân tích & công bố">
      <div className="row gap wrap">
        <ActionButton className="btn" disabled={!e.n_attempts} okMsg="Đã phân tích lại" onRun={async () => { await api.post(`/api/exams/${e.id}/analyze`); reload() }}>Phân tích lại</ActionButton>
        <ActionButton className={e.publish_flag ? 'btn' : 'btn primary'} disabled={e.status !== 'Analyzed'}
          okMsg={r => (r.publish_flag ? 'Đã công bố cho SV' : 'Đã thu hồi') + (r.moodle ? ` – Moodle đã nhận ${r.moodle.saved} kết quả` : r.moodle_error ? ` – chưa gửi lên Moodle: ${r.moodle_error}` : '')}
          onRun={async () => { const r = await api.patch(`/api/exams/${e.id}/publish`, { publish: !e.publish_flag }); reload(); return r }}>{e.publish_flag ? 'Thu hồi công bố' : 'Công bố kết quả lên Moodle'}</ActionButton>
        {!e.n_attempts && <ActionButton className="btn danger" confirm={`Xóa bài "${e.exam_title}"?`} onRun={async () => { await api.del(`/api/exams/${e.id}`); nav(`/sections/${e.class_section_id}`) }}>Xóa bài KT</ActionButton>}
      </div>
      <p className="mt"><b>{e.n_attempts}</b> SV có điểm · <b>{e.n_absent}</b> vắng / {e.n_enrolled} SV của lớp</p>
    </Card>
  </>
}

const escapeHtml = t => t.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

function Flow({ e, reload }) {
  const toast = useToast()
  const nav = useNavigate()
  const [quiz, setQuiz] = useState(e.moodle_quiz_id || '')
  const [mcourse, setMcourse] = useState(e.moodle_course_id || '')
  return (<>
    {e.exam_type === 'paper' && <PaperFlow e={e} reload={reload} />}
    <div className="grid2">
      <div className="stack">
      <Card title="1. Đề thi">
        <table className="tbl compact"><thead><tr><th>#</th><th>Câu hỏi</th><th>CLO</th><th>Điểm</th></tr></thead>
          <tbody>{e.questions.map(q => <tr key={q.question_id} className={q.is_cancelled ? 'cancel' : ''}><td>{q.order_index}</td><td className="clip">{q.content}</td><td>{q.clos}</td><td>{q.points}</td></tr>)}</tbody></table>
      </Card>
      <ExamMatrix e={e} />
      </div>
      <div className="stack">
        {e.exam_type === 'online' ? <>
          <Card title="2. Phát hành lên Moodle">
            {e.moodle_quiz_id ? <><p>Đã liên kết với <b>Quiz {e.moodle_quiz_id}</b> (khóa học Moodle {e.moodle_course_id || '?'}). Sinh viên vào Moodle để làm bài.</p>
              {e.target_students && <div className="row gap wrap"><span className="small muted grow">Bài phụ đạo: chỉ {e.target_students.split(',').length} SV được giao thấy và làm được Quiz (nhóm Moodle + điều kiện truy cập).</span>
                <ActionButton className="btn sm" okMsg={r => `Nhóm Moodle có ${r.added.length} SV${r.skipped.length ? `, ${r.skipped.length} SV chưa ghi danh khóa học` : ''}`}
                  onRun={() => api.post(`/api/exams/${e.id}/moodle/restrict`)}>Giới hạn SV trên Moodle</ActionButton></div>}</> : <>
              <p className="muted">Tạo Quiz trực tiếp trên Moodle qua Web Service: nhập câu hỏi (idnumber <code>QB-&lt;id&gt;</code>) vào ngân hàng câu hỏi của khóa học, bật xáo trộn phương án và tự liên kết với bài KT.</p>
              <div className="row gap"><Field label="ID khóa học Moodle"><input className="num" value={mcourse} onChange={x => setMcourse(x.target.value)} /></Field>
                <ActionButton className="btn primary" disabled={!mcourse} okMsg={r => `Đã tạo Quiz ${r.quizid} (${r.questions} câu) trên Moodle`
                  + (r.restricted ? ` – chỉ ${r.restricted.added.length} SV được giao làm được` : '') + (r.restrict_error ? ` ⚠ ${r.restrict_error}` : '')}
                  onRun={async () => { const r = await api.post(`/api/exams/${e.id}/moodle/create-quiz`, { moodle_course_id: Number(mcourse) }); reload(); return r }}>⇪ Tạo Quiz trên Moodle</ActionButton></div>
              <details className="mt"><summary className="muted">Cách thủ công: tải XML, tự import và nhập ID Quiz</summary>
                <ActionButton className="btn mt" onRun={async () => { await api.download(`/api/exams/${e.id}/moodle-xml`, 'moodle.xml'); reload() }}>⬇ Tải Moodle XML</ActionButton>
                <div className="row gap mt"><Field label="ID Quiz trên Moodle"><input className="num" value={quiz} onChange={x => setQuiz(x.target.value)} /></Field>
                  <ActionButton className="btn" disabled={!(Number(quiz) > 0)} okMsg="Đã liên kết Quiz" onRun={async () => { await api.patch(`/api/exams/${e.id}/link-quiz`, { moodle_quiz_id: Number(quiz) }); reload() }}>Liên kết</ActionButton></div>
              </details></>}
          </Card>
          <Card title="3. Đồng bộ bài làm từ Moodle">
            <p className="muted">Đọc trực tiếp CSDL Moodle (thủ tục <code>sp_sync_exam</code>): lấy đúng lượt Moodle dùng để tính điểm (theo cách tính điểm của Quiz), giải mã thứ tự xáo trộn phương án, ghi nhận SV vắng.</p>
            <ActionButton className="btn primary" disabled={!e.moodle_quiz_id} okMsg={r => (r.analysis ? `Đồng bộ ${r.sync.n_attempts} bài làm, ${r.sync.n_absent} vắng – đã phân tích` : (r.analysis_skipped || 'Đã đồng bộ')) + (r.warnings ? ` ⚠ ${r.warnings.join('; ')}` : '')}
              onRun={async () => { const r = await api.post(`/api/exams/${e.id}/sync`); reload(); return r }}>⟳ Đồng bộ &amp; phân tích</ActionButton>
            {e.last_synced_at && <p className="muted mt">Lần gần nhất: {e.last_synced_at.replace('T', ' ')}</p>}
          </Card>
        </> : null}
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
            {e.status === 'Draft' && <ActionButton className="btn danger" confirm={`Xóa bài kiểm tra "${e.exam_title}"? Thao tác không hoàn tác được.`}
              onRun={async () => { await api.del(`/api/exams/${e.id}`); nav(`/sections/${e.class_section_id}`) }}>Xóa bài KT</ActionButton>}
          </div>
          <p className="mt"><b>{e.n_attempts}</b> bài làm · <b>{e.n_absent}</b> vắng</p>
        </Card>
      </div>
    </div>
  </>)
}

// Ma trận đề của bài đã lưu: số câu theo chương × mức Bloom và điểm theo CLO
function ExamMatrix({ e }) {
  const qs = e.questions.filter(q => !q.is_cancelled)
  const chapters = [...new Map(qs.map(q => [q.outline_id ?? null, { outline_id: q.outline_id ?? null, chapter_number: q.chapter }])).values()]
    .sort((a, b) => (a.chapter_number ?? 99) - (b.chapter_number ?? 99))
  const cells = qs.map(q => ({ outline_id: q.outline_id ?? null, bloom_level_id: q.bloom_level_id }))
  const count = (o, b) => qs.filter(q => (q.outline_id ?? null) === o && (b === 'sum' || q.bloom_level_id === b)).length || ''
  const clo = {}
  qs.forEach(q => (q.clos || '').split(', ').filter(Boolean).forEach(c => { clo[c] = (clo[c] || 0) + 1 }))
  return <Card title="Ma trận đề (chương × mức Bloom)">
    <MatrixTable chapters={chapters} cells={cells} blooms={[1, 2, 3, 4, 5, 6]} render={count} />
    <div className="row gap wrap mt">{Object.entries(clo).sort().map(([c, n]) => <span key={c} className="pill blue">{c}: {n} câu</span>)}</div>
  </Card>
}

const FILE_VI = { question: 'Đề thi', answer: 'Phiếu trả lời', correction: 'Đáp án' }

function PaperFlow({ e, reload }) {
  const st = useApi(`/api/exams/${e.id}/paper`, [e.status, e.moodle_offlinequiz_id])
  const [mode, setMode] = useState(null)
  if (!st.data) return <Loading {...st} />
  const m = st.data.mode || mode
  const rl = () => Promise.all([st.reload(), reload()])
  if (m === 'system') return <PaperSystem e={e} st={st.data} reload={rl} />
  if (m === 'moodle') return <PaperMoodle e={e} reload={rl} />
  return <Card title="Bài thi giấy – chọn cách làm">
    <div className="stack">
      <button className="btn block" onClick={() => setMode('system')}><b>In và chấm ngay trên hệ thống</b>&nbsp;– sinh mã đề, xem trước đề (1 hoặc 2 cột), phiếu trả lời; chấm bằng ảnh quét / ảnh chụp điện thoại</button>
      <button className="btn block" onClick={() => setMode('moodle')}><b>Dùng Moodle Offline Quiz</b>&nbsp;– Moodle sinh đề, phiếu; tải phiếu quét lên Moodle để Moodle chấm, hệ thống đồng bộ về</button>
    </div>
  </Card>
}

function PaperMoodle({ e, reload }) {
  const [f, setF] = useState({ moodle_course_id: e.moodle_course_id || '', numgroups: 2, shuffle_questions: true, shuffle_answers: true, file_format: 'pdf', intro: '' })
  const oq = useApi(e.moodle_offlinequiz_id ? `/api/exams/${e.id}/moodle/offlinequiz` : null, [e.moodle_offlinequiz_id])
  const o = oq.data
  if (!e.moodle_offlinequiz_id) return (
    <Card title="2. Tạo đề thi giấy trên Moodle">
      <p className="muted">Moodle (plugin <b>Offline Quiz</b>) sinh <b>đề in</b>, <b>phiếu trả lời</b> và <b>đáp án</b> cho từng mã đề từ bộ câu hỏi này.
        Sau khi thi, phiếu được quét và tải lên Moodle – <b>Moodle nhận diện và chấm điểm</b>; hệ thống kéo kết quả về để phân tích.</p>
      <div className="grid2">
        <Field label="ID khóa học Moodle"><input className="num" value={f.moodle_course_id} onChange={x => setF({ ...f, moodle_course_id: x.target.value })} /></Field>
        <Field label="Số mã đề"><select value={f.numgroups} onChange={x => setF({ ...f, numgroups: Number(x.target.value) })}>
          {[1, 2, 3, 4, 5, 6].map(n => <option key={n} value={n}>{n} mã đề ({'ABCDEF'.slice(0, n).split('').join(', ')})</option>)}</select></Field>
        <Field label="Định dạng đề in"><select value={f.file_format} onChange={x => setF({ ...f, file_format: x.target.value })}>
          <option value="pdf">PDF</option><option value="docx">Word (.docx) – sửa được trước khi in</option></select></Field>
        <div>
          <label className="row gap check"><input type="checkbox" checked={f.shuffle_questions} onChange={x => setF({ ...f, shuffle_questions: x.target.checked })} /> Xáo trộn thứ tự câu giữa các mã đề</label>
          <label className="row gap check"><input type="checkbox" checked={f.shuffle_answers} onChange={x => setF({ ...f, shuffle_answers: x.target.checked })} /> Xáo trộn phương án</label>
        </div>
      </div>
      <Field label="Lời dặn in ở đầu đề (tùy chọn)"><textarea rows={2} value={f.intro} placeholder="VD: Thời gian làm bài 30 phút. Không sử dụng tài liệu." onChange={x => setF({ ...f, intro: x.target.value })} /></Field>
      <ActionButton className="btn primary mt" disabled={!f.moodle_course_id || !e.questions.length} okMsg={r => `Moodle đã tạo ${r.groups.length} mã đề – tải đề và phiếu để in`}
        onRun={async () => { const r = await api.post(`/api/exams/${e.id}/moodle/create-offlinequiz`, { ...f, moodle_course_id: Number(f.moodle_course_id), intro: f.intro ? `<p>${escapeHtml(f.intro)}</p>` : '' }); reload(); return r }}>⇪ Tạo đề thi giấy trên Moodle</ActionButton>
    </Card>)
  return <>
    <Card title="2. Đề thi & phiếu trả lời để in" actions={o && <a className="btn sm" href={o.url} target="_blank" rel="noreferrer">Mở trên Moodle ↗</a>}>
      <Loading {...oq} />
      {o && <>
        <p className="muted">Moodle đã sinh sẵn {o.groups.length} mã đề (Offline Quiz #{o.offlinequizid}). In <b>đề thi</b> và <b>phiếu trả lời</b> của mỗi mã đề; giữ <b>đáp án</b> để đối chiếu.</p>
        <table className="tbl compact"><thead><tr><th>Mã đề</th><th>Số câu</th><th>Tệp</th></tr></thead>
          <tbody>{o.groups.map(g => <tr key={g.letter}><td><b>{g.letter}</b></td><td>{g.questions}</td>
            <td><div className="row gap wrap">{g.files.map(x => <ActionButton key={x.filename} className="btn sm" onRun={() => api.download(x.download, x.filename)}>
              ⬇ {FILE_VI[x.kind]} ({x.filename.split('.').pop().toUpperCase()}, {Math.round(x.filesize / 1024)} KB)</ActionButton>)}</div></td></tr>)}</tbody></table>
        <ActionButton className="btn primary mt" onRun={() => api.download(o.zip, 'de_thi_giay.zip')}>⬇ Tải tất cả (.zip)</ActionButton>
      </>}
    </Card>
    <Card title="3. Quét phiếu – Moodle nhận diện & chấm">
      <ol className="steps small">
        <li>SV ghi <b>MSSV</b> bằng cách đánh dấu các ô số và làm bài trên phiếu trả lời của đúng mã đề.</li>
        <li>Quét phiếu thành ảnh (PNG/JPG/TIFF, nên 200–300 dpi) hoặc nén nhiều ảnh thành <b>.zip</b>, rồi tải lên Moodle:
          {o && <> <a href={o.uploadurl} target="_blank" rel="noreferrer">Tải phiếu đã quét lên Moodle ↗</a></>}</li>
        <li>Moodle nhận diện MSSV, mã đề, các ô đã đánh dấu và chấm điểm. Phiếu mờ/sai MSSV được đưa vào danh sách cần sửa
          {o && <> – <a href={o.correcturl} target="_blank" rel="noreferrer">sửa lỗi phiếu trên Moodle ↗</a></>}.</li>
      </ol>
      {o && <div className="stats mt">
        <Stat label="Bài đã chấm trên Moodle" value={o.results} tone="green" />
        <Stat label="Ảnh phiếu đang chờ chấm" value={o.pending} tone={o.pending ? 'amber' : ''} />
        <Stat label="Phiếu cần sửa trên Moodle" value={o.errorpages} tone={o.errorpages ? 'red' : ''} />
      </div>}
      <div className="row gap wrap">
        <ActionButton className="btn" okMsg={r => `Moodle đã chấm ${r.results} bài${r.errorpages ? ` – ${r.errorpages} phiếu cần sửa trên Moodle` : ''}`}
          onRun={async () => { const r = await api.post(`/api/exams/${e.id}/moodle/process-scans`); oq.setData(r); return r }}>Cho Moodle chấm phiếu đang chờ</ActionButton>
        <ActionButton className="btn primary" okMsg={r => (r.analysis ? `Đồng bộ ${r.sync.n_attempts} bài đã chấm, ${r.sync.n_absent} vắng – đã phân tích` : (r.analysis_skipped || 'Đã đồng bộ')) + (r.scans_error ? ` ⚠ Không gọi được Moodle chấm phiếu đang chờ: ${r.scans_error}` : '') + (r.warnings ? ` ⚠ ${r.warnings.join('; ')}` : '')}
          onRun={async () => { const r = await api.post(`/api/exams/${e.id}/sync`); reload(); oq.reload(); return r }}>⟳ Đồng bộ &amp; phân tích</ActionButton>
      </div>
      {e.last_synced_at && <p className="muted mt">Lần đồng bộ gần nhất: {e.last_synced_at.replace('T', ' ')}</p>}
    </Card>
  </>
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
        <Stat label={`Độ tin cậy của đề (${o.reliability || "KR-20"})`} value={o.kr20 == null ? '–' : fmtNum(o.kr20)} sub={o.kr20 == null ? '' : o.kr20 >= 0.7 ? 'đạt (≥ 0,7)' : 'thấp (< 0,7) – đề ít câu / ít phân hóa'} tone={o.kr20 == null ? '' : o.kr20 >= 0.7 ? 'green' : 'amber'} />
      </div>
      <Card title="Phổ điểm">
        <div className="chart"><Bar data={{ labels: o.histogram.map(h => h.range), datasets: [{ label: 'Số SV', data: o.histogram.map(h => h.count), backgroundColor: C.blue, borderRadius: 4 }] }}
          options={{ maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { ticks: { precision: 0 }, title: { display: true, text: 'Số SV' } }, x: { title: { display: true, text: 'Khoảng điểm' } } } }} /></div>
      </Card>
    </>
  )
}

function Items({ id, manual }) {
  const { data, ...st } = useApi(`/api/exams/${id}/item-stats`)
  const [open, setOpen] = useState(null)
  if (!data) return <Loading {...st} />
  const flagged = data.filter(d => !['Tốt', 'Chấp nhận được'].includes(d.classification))
  const hasT = data.some(d => d.median_time_sec != null)
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
        <p className="muted">Ngưỡng tham khảo: p ∈ [0,25; 0,85]; DI ≥ 0,3 tốt, 0,2–0,3 chấp nhận, &lt; 0,2 cần xem lại, &lt; 0 cần kiểm tra đáp án (Ebel &amp; Frisbie, 1991).
          {manual && ' Câu/ý nhập điểm: p = điểm trung bình / điểm tối đa; DI = chênh lệch tỷ lệ điểm trung bình nhóm 27% cao nhất và thấp nhất.'}</p>
      </Card>
      <Card title="Bảng chỉ số câu hỏi">
        <table className="tbl">
          <thead><tr><th>#</th><th>ID</th><th>Nội dung</th><th>Chương</th><th>CLO</th><th>p</th><th>DI</th>{hasT && <th title="Trung vị thời gian trả lời của lớp (Moodle Quiz)">TG trả lời</th>}<th>Phân loại</th><th /></tr></thead>
          <tbody>{data.map(d => <Fragment key={d.question_id}>
            <tr>
              <td>{d.order_index}</td><td>{d.question_id}</td><td className="clip">{d.content}</td><td>{d.chapter}</td><td>{d.clos}</td>
              <td className={`num-c ${pClass(d.p_value)}`}>{fmtNum(d.p_value, 3)}</td><td className={`num-c ${diClass(d.di_value)}`}>{fmtNum(d.di_value, 3)}</td>
              {hasT && <td className="num-c">{d.median_time_sec != null ? `${d.median_time_sec}″` : '—'}</td>}
              <td><Badge tone={CLS_TONE[d.classification] || 'gray'}>{d.classification}</Badge></td>
              <td><button className="btn sm ghost" onClick={() => setOpen(open === d.question_id ? null : d.question_id)}>{open === d.question_id ? '▲' : 'Phương án ▼'}</button></td>
            </tr>
            {open === d.question_id && <tr key={`${d.question_id}-x`} className="sub"><td colSpan={hasT ? 10 : 9}>
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

const SRC_VI = { moodle: 'Moodle Quiz', paper: 'Phiếu (Moodle chấm)', scan: 'Phiếu (hệ thống chấm)', manual: 'Nhập điểm' }

function Students({ id, cs }) {
  const { data, ...st } = useApi(`/api/exams/${id}/students`)
  const nav = useNavigate()
  if (!data) return <Loading {...st} />
  const clos = [...new Set(data.flatMap(d => Object.keys(d.clos)))].sort()
  return (
    <Card title="Kết quả từng sinh viên theo CLO" actions={<span className="muted">✓ đạt ngưỡng · ✗ chưa đạt · bấm vào SV để xem chi tiết &amp; phần cần học lại</span>}>
      <table className="tbl">
        <thead><tr><th>MSSV</th><th>Họ tên</th><th>Nguồn</th><th>Mã đề</th><th>Điểm thô</th>{clos.map(c => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{data.map(d => <tr key={d.attempt_id} className={`click ${d.status === 'absent' ? 'dim' : ''}`} onClick={() => nav(`/sections/${cs}/students/${d.student_id}?exam=${id}`)}>
          <td>{d.student_code}</td><td><Link to={`/sections/${cs}/students/${d.student_id}?exam=${id}`} onClick={ev => ev.stopPropagation()}>{d.full_name}</Link></td><td>{d.status === 'absent' ? 'Vắng' : SRC_VI[d.source] || d.source}</td>
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
  const K = { moodle: 'Đồng bộ Moodle', paper: 'Đồng bộ bài giấy (Moodle)', scan: 'Chấm phiếu trên hệ thống', manual: 'Nhập điểm', analyze: 'Phân tích' }
  return <Card><table className="tbl"><thead><tr><th>#</th><th>Loại</th><th>Bắt đầu</th><th>Kết thúc</th><th>Kết quả</th><th>Bài làm</th><th>Vắng</th><th>Ghi chú</th></tr></thead>
    <tbody>{data.map(r => <tr key={r.id}><td>{r.id}</td><td>{K[r.kind]}</td><td>{r.started_at?.replace('T', ' ')}</td><td>{r.finished_at?.replace('T', ' ')}</td>
      <td><Badge tone={r.status === 'success' ? 'green' : r.status === 'failed' ? 'red' : 'gray'}>{r.status}</Badge></td><td>{r.n_attempts ?? '—'}</td><td>{r.n_absent ?? '—'}</td><td className="clip">{r.message}</td></tr>)}</tbody></table></Card>
}
