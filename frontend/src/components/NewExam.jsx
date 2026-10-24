// Tạo bài kiểm tra – dùng chung cho trang môn học (đề của môn, giao cho lớp HP khi xuất) và trang lớp HP (bài của lớp).
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { ActionButton, Badge, Field, Modal } from './ui'
import { useApi } from '../hooks'
import Blueprint from './Blueprint'
import { ManualExamForm } from './ManualExam'

export const TYPE_VI = { online: 'Trực tuyến (Moodle)', paper: 'Trên giấy', manual: 'Nhập điểm' }

const CHOICES = [
  { k: 'online', icon: '🖥', title: 'Trắc nghiệm trực tuyến', sub: 'Moodle Quiz',
    desc: 'Chọn câu từ ngân hàng hoặc sinh đề theo ma trận; tạo Quiz trên khóa học Moodle, SV làm bài trực tuyến, hệ thống đồng bộ và phân tích.' },
  { k: 'paper', icon: '📝', title: 'Trắc nghiệm trên giấy', sub: 'In đề – chấm phiếu',
    desc: 'Hệ thống sinh mã đề, in đề và phiếu trả lời, chấm phiếu bằng ảnh quét hoặc ảnh chụp điện thoại (hoặc dùng Moodle Offline Quiz).' },
  { k: 'manual', icon: '✍', title: 'Nhập điểm', sub: 'Tự luận, thực hành, đồ án',
    desc: 'Khai báo các câu/ý chấm điểm gắn CLO rồi nhập điểm tay hoặc từ Excel – cho bài làm ngoài hệ thống.' },
]

export function ExamTypeChooser({ onPick, onClose, note, children }) {
  return <Modal title="Tạo bài kiểm tra" size="md" onClose={onClose}>
    {children}
    {note && <p className="muted small mb">{note}</p>}
    <div className="choice-grid">{CHOICES.map(c =>
      <button key={c.k} className="choice" onClick={() => onPick(c.k)}>
        <span className="choice-ic" aria-hidden="true">{c.icon}</span>
        <span className="choice-t">{c.title}</span><span className="choice-s">{c.sub}</span>
        <span className="choice-d">{c.desc}</span>
      </button>)}</div>
  </Modal>
}

// cs: tạo bài cho một lớp HP; course {id, code} + sections (các lớp HP của GV trong môn): từ trang môn – chọn lớp trước
// (góp ý 21/10: mặc định là bài của một lớp; "đề dùng chung" cho nhiều lớp là lựa chọn riêng)
export function NewExamFlow({ cs, course, sections, start = 'choose', onClose }) {
  const [step, setStep] = useState(start)
  const [target, setTarget] = useState(cs || !sections?.length ? 'all' : String(sections[0].id))
  const sec = cs || (target !== 'all' ? { ...sections.find(x => String(x.id) === target), course_id: course.id } : null)
  const note = sec ? `Bài kiểm tra của lớp ${sec.section_code}.`
    : `Đề dùng chung của môn ${course.code}: soạn một lần, khi xuất (tạo Quiz, in đề, nhập điểm) mới chọn giao cho các lớp học phần.`
  if (step === 'choose') return <ExamTypeChooser note={note} onPick={setStep} onClose={onClose}>
    {!cs && sections?.length > 0 && <Field label="Bài kiểm tra dành cho"><select value={target} onChange={e => setTarget(e.target.value)}>
      {sections.map(x => <option key={x.id} value={x.id}>Lớp {x.section_code} ({x.semester})</option>)}
      <option value="all">Nhiều lớp – đề dùng chung, chọn lớp khi xuất</option></select></Field>}
  </ExamTypeChooser>
  if (step === 'manual') return <ManualExamForm cs={sec} courseId={course?.id} sections={sections} onClose={onClose} />
  return <CreateExam cs={sec} course={course} type={step} onClose={onClose} />
}

const STEPS = ['Thông tin bài', 'Chọn câu hỏi', 'Kiểm tra & lưu']

// Soạn bài trắc nghiệm theo 3 bước: thông tin → chọn câu (sinh tự động hoặc tự chọn) → xem lại điểm từng câu, độ phủ CLO rồi lưu
function CreateExam({ cs, course, type, onClose }) {
  const nav = useNavigate()
  const courseId = cs ? cs.course_id : course.id
  const base = cs ? `/api/class-sections/${cs.id}` : `/api/courses/${course.id}`
  const bank = useApi(`/api/questions?course_id=${courseId}`)
  const [f, setF] = useState({ exam_title: '', exam_type: type || 'online', assessment_type: 'final', exam_date: '', duration_minutes: 45, max_score: 10 })
  const [step, setStep] = useState(0)
  const [how, setHow] = useState(null)       // 'auto' | 'manual'
  const [picked, setPicked] = useState({}) // question_id -> points
  const [filter, setFilter] = useState('')
  const list = useMemo(() => (bank.data || []).filter(q => !q.is_cancelled && q.tagged !== false &&
    (!filter || q.clos.some(c => c.clo_code === filter) || q.chapter === filter)), [bank.data, filter])
  const chips = useMemo(() => [...new Set((bank.data || []).flatMap(q => [...q.clos.map(c => c.clo_code), q.chapter]).filter(Boolean))].sort(), [bank.data])
  const n = Object.keys(picked).length
  const badPts = Object.values(picked).some(v => !(Number(v) > 0))
  const total = Object.values(picked).reduce((a, b) => a + Number(b || 0), 0)
  const coverage = useMemo(() => {
    const m = {}
    for (const q of bank.data || []) if (picked[q.id]) for (const c of q.clos) m[c.clo_code] = (m[c.clo_code] || 0) + c.weight * Number(picked[q.id])
    return m
  }, [bank.data, picked])
  const infoOk = f.exam_title.trim().length >= 3 && Number(f.max_score) > 0
  const canGo = i => i === 0 || (i === 1 && infoOk) || (i === 2 && infoOk && n > 0)
  const chosen = (bank.data || []).filter(q => picked[q.id] !== undefined)
  const spread = () => {   // chia đều thang điểm cho các câu (làm tròn 0,01; câu cuối nhận phần dư)
    const max = Number(f.max_score) || 10, each = Math.floor(max / n * 100) / 100, ids = Object.keys(picked)
    setPicked(Object.fromEntries(ids.map((id, i) => [id, i === ids.length - 1 ? Math.round((max - each * (n - 1)) * 100) / 100 : each])))
  }
  const toggle = (id, on) => setPicked(p => { const x = { ...p }; on ? x[id] = 0.5 : delete x[id]; return x })

  const save = async () => {
    const items = Object.entries(picked).map(([question_id, points]) => ({ question_id: Number(question_id), points: Number(points) }))
    const owner = cs ? { class_section_id: cs.id } : { course_id: course.id }
    const body = { ...f, ...owner, items, exam_date: f.exam_date || null, duration_minutes: Number(f.duration_minutes) || null, max_score: Number(f.max_score) }
    const e = await api.post('/api/exams', body)
    nav(`/exams/${e.id}`)
  }
  const summary = <span>Đã chọn <b>{n}</b> câu · tổng điểm thô <b>{total.toFixed(2)}</b></span>
  return (
    <Modal title={cs ? `Tạo bài kiểm tra – lớp ${cs.section_code}` : `Tạo đề dùng chung – môn ${course.code}`} onClose={onClose} size="wide">
      <ol className="wiz">{STEPS.map((t, i) => <li key={t} className={i === step ? 'on' : i < step ? 'done' : ''}>
        <button type="button" disabled={!canGo(i)} onClick={() => setStep(i)}>{i < step ? '✓' : i + 1}. {t}</button></li>)}</ol>

      {step === 0 && <>
        {!cs && <div className="alert blue small">Đề được lưu ở môn học. Khi xuất (tạo Quiz trên Moodle, in đề, chấm phiếu) bạn chọn giao cho một hoặc nhiều lớp học phần – mỗi lớp nhận một bài riêng để chấm và phân tích.</div>}
        <p className="muted small">Hình thức: <b>{TYPE_VI[f.exam_type]}</b></p>
        <div className="grid3">
          <Field label="Tên bài kiểm tra"><input value={f.exam_title} onChange={e => setF({ ...f, exam_title: e.target.value })} placeholder="VD: Thi cuối kỳ" /></Field>
          <Field label="Bài KT lấy minh chứng (BM6a)" hint="Bài cuối kỳ hay bài quá trình theo kế hoạch đánh giá CLO"><select value={f.assessment_type} onChange={e => setF({ ...f, assessment_type: e.target.value })}>
            <option value="process">Quá trình</option><option value="final">Cuối kỳ</option></select></Field>
          <Field label="Thang điểm"><input type="number" value={f.max_score} onChange={e => setF({ ...f, max_score: e.target.value })} /></Field>
          <Field label="Ngày kiểm tra"><input type="date" value={f.exam_date} onChange={e => setF({ ...f, exam_date: e.target.value })} /></Field>
          <Field label="Thời gian (phút)"><input type="number" value={f.duration_minutes} onChange={e => setF({ ...f, duration_minutes: e.target.value })} /></Field>
        </div>
        <div className="row mt"><span className="grow" /><button className="btn ghost" onClick={onClose}>Hủy</button>
          <button className="btn primary" disabled={!infoOk} onClick={() => setStep(1)}>Tiếp: chọn câu hỏi →</button></div>
      </>}

      {step === 1 && <>
        <div className="choice-grid two">
          <button type="button" className={`choice ${how === 'auto' ? 'on' : ''}`} onClick={() => setHow('auto')}>
            <span className="choice-t">⚙ Sinh đề tự động</span><span className="choice-s">Khuyên dùng</span>
            <span className="choice-d">Nhập số câu và độ khó; hệ thống tự chọn câu theo ma trận chương × mức độ nhận thức, phủ đủ CLO.</span></button>
          <button type="button" className={`choice ${how === 'manual' ? 'on' : ''}`} onClick={() => setHow('manual')}>
            <span className="choice-t">☑ Tự chọn câu từ ngân hàng</span><span className="choice-s">Chọn từng câu</span>
            <span className="choice-d">Lọc theo CLO hoặc chương rồi tích các câu muốn đưa vào đề.</span></button>
        </div>
        {how === 'auto' && <div className="mt"><Blueprint base={base} maxScore={f.max_score} picked={picked}
          onApply={items => { setFilter(''); setPicked(Object.fromEntries(items.map(i => [i.question_id, i.points]))) }} /></div>}
        {how === 'manual' && <>
          <div className="row gap wrap mt"><b>Lọc:</b>
            <button className={`chip ${!filter ? 'on' : ''}`} onClick={() => setFilter('')}>Tất cả</button>
            {chips.map(c => <button key={c} className={`chip ${filter === c ? 'on' : ''}`} onClick={() => setFilter(c)}>{c}</button>)}
            <span className="grow" />
            {(bank.data || []).some(q => q.tagged === false) && <span className="muted small">Ẩn {(bank.data || []).filter(q => q.tagged === false).length} câu chưa gán CLO/Bloom</span>}
            <button className="btn sm" onClick={() => setPicked(p => ({ ...p, ...Object.fromEntries(list.filter(q => p[q.id] === undefined).map(q => [q.id, 0.5])) }))}>Chọn tất cả đang lọc</button>
            {n > 0 && <button className="btn sm ghost" onClick={() => setPicked({})}>Bỏ chọn tất cả</button>}
          </div>
          <div className="scroll mt">
            <table className="tbl"><thead><tr><th /><th>ID</th><th>Nội dung</th><th>Chương</th><th>Bloom</th><th>CLO (trọng số)</th><th>p TB</th></tr></thead>
              <tbody>{list.map(q => (
                <tr key={q.id} className={picked[q.id] !== undefined ? 'sel' : ''}>
                  <td><input type="checkbox" aria-label={`Chọn câu ${q.id}`} checked={picked[q.id] !== undefined} onChange={e => toggle(q.id, e.target.checked)} /></td>
                  <td>{q.id}</td><td className="clip">{q.content}</td><td>{q.chapter}</td><td>{q.bloom}</td>
                  <td>{q.clos.map(c => `${c.clo_code}${c.weight < 1 ? ` (${c.weight})` : ''}`).join(', ')}</td>
                  <td>{q.usage?.avg_p ?? '—'}</td>
                </tr>))}</tbody></table>
          </div>
        </>}
        <div className="row gap mt wrap">{summary}<span className="grow" />
          <button className="btn ghost" onClick={() => setStep(0)}>← Quay lại</button>
          <button className="btn primary" disabled={!n} onClick={() => setStep(2)}>Tiếp: kiểm tra đề →</button></div>
      </>}

      {step === 2 && <>
        <div className="row gap wrap"><b>Độ phủ CLO (điểm):</b>
          {Object.entries(coverage).sort().map(([c, v]) => <span key={c} className="pill blue">{c}: {v.toFixed(2)} đ</span>)}
          <span className="grow" />
          <button className="btn sm" onClick={spread} title="Mỗi câu nhận điểm bằng nhau, tổng bằng thang điểm">Chia đều {f.max_score} điểm cho {n} câu</button></div>
        <div className="scroll mt">
          <table className="tbl"><thead><tr><th>ID</th><th>Nội dung</th><th>Chương</th><th>Bloom</th><th>CLO</th><th>Điểm</th><th /></tr></thead>
            <tbody>{chosen.map(q => <tr key={q.id}>
              <td>{q.id}</td><td className="clip">{q.content}</td><td>{q.chapter}</td><td>{q.bloom}</td>
              <td>{q.clos.map(c => c.clo_code).join(', ')}</td>
              <td><input className="num" type="number" step="0.25" min="0.25" aria-label={`Điểm câu ${q.id}`} value={picked[q.id]} onChange={e => setPicked(p => ({ ...p, [q.id]: e.target.value }))} /></td>
              <td><button className="btn sm ghost" aria-label={`Bỏ câu ${q.id}`} onClick={() => toggle(q.id, false)}>✕</button></td></tr>)}</tbody></table>
        </div>
        <div className="row gap mt wrap">{summary}<span className="grow" />
          {badPts && <small className="bad-t">Điểm mỗi câu phải lớn hơn 0</small>}
          <button className="btn ghost" onClick={() => setStep(1)}>← Quay lại</button>
          <ActionButton className="btn primary" disabled={!n || badPts || !infoOk} onRun={save}>
            {cs ? 'Lưu bài kiểm tra' : 'Lưu đề dùng chung'}</ActionButton>
        </div>
      </>}
    </Modal>
  )
}

// Giao đề cho lớp HP (khi xuất): đề của môn → các lớp đã chọn; bài của một lớp → các lớp khác cùng môn.
export function DeployDialog({ e, onClose, onDone }) {
  const nav = useNavigate()
  const secs = useApi('/api/class-sections').data
  const given = new Set((e.deployments || []).map(d => d.class_section_id))
  const options = (secs || []).filter(s => s.course_id === e.course_id && s.id !== e.class_section_id)
  const [sel, setSel] = useState([])
  const [moodle, setMoodle] = useState(true)
  const [res, setRes] = useState(null)
  const fresh = options.filter(s => !given.has(s.id))
  const verb = { online: 'tạo Quiz', paper: 'in đề và chấm phiếu', manual: 'nhập điểm' }[e.exam_type]
  const run = async () => { const r = await api.post(`/api/exams/${e.id}/copy`, { class_section_ids: sel, create_moodle: moodle }); setRes(r); onDone?.() }
  return <Modal title={e.is_template ? `Giao đề "${e.exam_title}" cho lớp học phần` : `Dùng đề "${e.exam_title}" cho lớp khác`} size="md" onClose={onClose}>
    {!res ? <>
      <p className="small">Chọn các lớp học phần sẽ làm bài. Mỗi lớp nhận một bài kiểm tra riêng (cùng câu hỏi, điểm, cấu hình) để {verb}; kết quả từng lớp được đồng bộ, phân tích riêng và có thể gộp ở trang môn học.</p>
      {options.length ? <div className="pick-list">
        {fresh.length > 1 && <label className="pick all"><input type="checkbox" checked={sel.length === fresh.length}
          onChange={x => setSel(x.target.checked ? fresh.map(s => s.id) : [])} /> <b>Chọn tất cả lớp chưa giao ({fresh.length})</b></label>}
        {options.map(s => { const done = given.has(s.id)
          return <label key={s.id} className={`pick ${done ? 'dim' : ''}`}>
            <input type="checkbox" disabled={done} checked={sel.includes(s.id)} onChange={x => setSel(x.target.checked ? [...sel, s.id] : sel.filter(i => i !== s.id))} />
            <span className="grow"><b>{s.section_code}</b> <span className="muted small">{s.semester} · {s.n_students} SV</span></span>
            {done ? <Badge tone="green">Đã giao</Badge> : e.exam_type === 'online' && (s.moodle_course_id ? <Badge tone="blue">Moodle #{s.moodle_course_id}</Badge> : <Badge tone="amber">Chưa gắn Moodle</Badge>)}
          </label> })}</div>
        : <p className="muted">Bạn chưa phụ trách lớp học phần nào {e.is_template ? 'của môn này' : 'khác của môn này'}.</p>}
      {e.exam_type === 'online' && <label className="row gap check mt"><input type="checkbox" checked={moodle} onChange={x => setMoodle(x.target.checked)} />
        Tạo luôn Quiz trên khóa học Moodle của từng lớp (lớp chưa gắn Moodle thì tạo sau ở trang bài kiểm tra)</label>}
      <div className="row mt"><span className="grow" /><button className="btn ghost" onClick={onClose}>Hủy</button>
        <ActionButton className="btn primary" disabled={!sel.length} onRun={run}>{e.is_template ? `Giao cho ${sel.length || ''} lớp` : `Sao đề sang ${sel.length || ''} lớp`}</ActionButton></div>
    </> : <>
      <table className="tbl compact"><thead><tr><th>Lớp</th><th>Bài kiểm tra</th><th>Kết quả</th></tr></thead>
        <tbody>{res.copies.map(c => <tr key={c.class_section_id}><td><b>{c.section_code}</b></td>
          <td><Link to={`/exams/${c.exam_id}`} onClick={onClose}>Bài #{c.exam_id} →</Link></td>
          <td className="small">{c.skipped ? c.moodle : c.moodle || 'Đã tạo bài kiểm tra cho lớp'}</td></tr>)}</tbody></table>
      <div className="row mt"><span className="grow" />
        {res.copies.length === 1 && <button className="btn primary" onClick={() => { onClose(); nav(`/exams/${res.copies[0].exam_id}`) }}>Mở bài của lớp {res.copies[0].section_code}</button>}
        <button className="btn" onClick={onClose}>Đóng</button></div>
    </>}
  </Modal>
}
