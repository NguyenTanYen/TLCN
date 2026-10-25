// Đề giấy sinh & chấm trên hệ thống: mã đề → xem trước đề (1 hoặc 2 cột) và phiếu trả lời ngay trên màn hình → xuất PDF/Word → chấm ảnh phiếu.
import { useEffect, useMemo, useState, useRef } from 'react'
import { api } from '../api'
import { ActionButton, Badge, Card, Field, FileButton, Loading, Modal, Stat, useToast } from './ui'
import { useApi } from '../hooks'

const authFetch = (url, opts = {}) => fetch(url, { ...opts, headers: { ...(opts.headers || {}), Authorization: `Bearer ${localStorage.getItem('tlcn_token')}` } })

export default function PaperSystem({ e, st, reload }) {
  const [tab, setTab] = useState(st.versions.length ? 'preview' : 'versions')
  return <Card title="Đề thi giấy – in và chấm trên hệ thống" actions={<span className="muted small">Không cần Moodle · chấm bằng máy quét hoặc ảnh chụp điện thoại</span>}>
    <div className="tabs">{[['versions', '1. Mã đề'], ['preview', '2. Xem trước & xuất đề', !st.versions.length], ['sheet', '3. Phiếu trả lời', !st.versions.length],
      ['scan', '4. Chấm phiếu', !st.versions.length]].map(([k, l, d]) => <button key={k} disabled={d} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>)}</div>
    {tab === 'versions' && <Versions e={e} st={st} reload={reload} onDone={() => setTab('preview')} />}
    {tab === 'preview' && <Preview e={e} st={st} reload={reload} />}
    {tab === 'sheet' && <Sheet e={e} st={st} reload={reload} />}
    {tab === 'scan' && <Scan e={e} st={st} reload={reload} />}
  </Card>
}

function Versions({ e, st, reload, onDone }) {
  const [f, setF] = useState({ n_versions: Math.max(2, st.versions.length || 2), shuffle_questions: true, shuffle_options: true })
  const counts = [...new Set(e.questions.map(q => q.n_options).filter(Boolean))]
  return <>
    {st.versions.length > 0 && <p>Đã sinh <b>{st.versions.length}</b> mã đề: {st.versions.map(v => <Badge key={v.id} tone="blue">{v.version_code}</Badge>)}. Mã đề 01 giữ nguyên thứ tự gốc; các mã sau xáo trộn.</p>}
    <div className="row gap wrap">
      <Field label="Số mã đề"><select value={f.n_versions} onChange={x => setF({ ...f, n_versions: Number(x.target.value) })}>
        {[1, 2, 3, 4, 5, 6, 7, 8].map(n => <option key={n} value={n}>{n} mã đề ({Array.from({ length: n }, (_, i) => String(i + 1).padStart(2, '0')).join(', ')})</option>)}</select></Field>
      <label className="row gap check"><input type="checkbox" checked={f.shuffle_questions} onChange={x => setF({ ...f, shuffle_questions: x.target.checked })} /> Xáo thứ tự câu</label>
      <label className="row gap check"><input type="checkbox" checked={f.shuffle_options} onChange={x => setF({ ...f, shuffle_options: x.target.checked })} /> Xáo thứ tự phương án</label>
    </div>
    <p className="muted small">Mỗi câu giữ đúng số phương án của câu (2, 3, 4… tùy câu{counts.length ? `; đề này có câu ${counts.sort().join(', ')} phương án` : ''}); phiếu trả lời in đúng số ô tương ứng.</p>
    <div className="row gap">
      {st.versions.length > 0 && <ActionButton className="btn danger" disabled={st.n_scanned > 0} confirm="Xóa các mã đề đã sinh? Đề/phiếu đã in theo mã đề cũ sẽ không chấm được."
        okMsg="Đã xóa mã đề" onRun={async () => { await api.del(`/api/exams/${e.id}/paper/versions`); reload() }}>Xóa mã đề</ActionButton>}
      <ActionButton className="btn primary" disabled={st.n_scanned > 0} confirm={st.versions.length ? 'Sinh lại mã đề? Đề/phiếu đã in theo mã đề cũ sẽ không chấm được.' : undefined}
        okMsg={r => `Đã sinh ${r.versions.length} mã đề`} onRun={async () => { const r = await api.post(`/api/exams/${e.id}/paper/versions`, f); await reload(); onDone(); return r }}>
        {st.versions.length ? 'Sinh lại mã đề' : 'Sinh mã đề'}</ActionButton>
    </div>
  </>
}

const PAPER_KEYS = ['columns', 'font_size', 'school', 'faculty', 'exam_name', 'duration', 'notes', 'show_points', 'option_layout']

function Preview({ e, st, reload }) {
  const [p, setP] = useState(st.paper)
  const [vi, setVi] = useState(0)
  const [showKey, setShowKey] = useState(false)
  const [edit, setEdit] = useState(null)
  const v = st.versions[vi] || st.versions[0]
  if (!v) return <Loading loading />
  const dirty = PAPER_KEYS.some(k => String(p[k]) !== String(st.paper[k]))
  const save = () => api.put(`/api/exams/${e.id}/paper/settings`, { paper: p, sheet: st.sheet })
  const optCols = q => {
    if (p.option_layout !== 'auto') return Number(p.option_layout)
    const longest = Math.max(...q.options.map(o => o.content.length + 3))
    const width = p.columns === 2 ? 44 : 92
    return q.options.length <= 4 && longest * q.options.length <= width ? q.options.length : longest * 2 <= width ? 2 : 1
  }
  return <>
    <div className="grid3">
      <Field label="Bố cục"><select value={p.columns} onChange={x => setP({ ...p, columns: Number(x.target.value) })}>
        <option value={1}>1 cột (để nguyên)</option><option value={2}>Chia 2 cột trên một mặt (tiết kiệm giấy)</option></select></Field>
      <Field label="Cỡ chữ"><select value={p.font_size} onChange={x => setP({ ...p, font_size: Number(x.target.value) })}>{[10, 10.5, 11, 11.5, 12, 13].map(n => <option key={n} value={n}>{n} pt</option>)}</select></Field>
      <Field label="Phương án"><select value={p.option_layout} onChange={x => setP({ ...p, option_layout: x.target.value })}>
        <option value="auto">Tự động (đủ chỗ thì xếp trên một dòng)</option><option value="1">Mỗi dòng 1 phương án</option><option value="2">2 phương án / dòng</option><option value="4">4 phương án / dòng</option></select></Field>
      <Field label="Trường"><input value={p.school} onChange={x => setP({ ...p, school: x.target.value })} /></Field>
      <Field label="Khoa"><input value={p.faculty} onChange={x => setP({ ...p, faculty: x.target.value })} /></Field>
      <Field label="Tiêu đề đề thi"><input value={p.exam_name} placeholder={e.exam_title.toUpperCase()} onChange={x => setP({ ...p, exam_name: x.target.value })} /></Field>
      <Field label="Thời gian"><input value={p.duration} placeholder="VD 45 phút" onChange={x => setP({ ...p, duration: x.target.value })} /></Field>
      <Field label="Lời dặn"><input value={p.notes} onChange={x => setP({ ...p, notes: x.target.value })} /></Field>
      <div><label className="row gap check"><input type="checkbox" checked={!!p.show_points} onChange={x => setP({ ...p, show_points: x.target.checked })} /> In điểm từng câu</label>
        <label className="row gap check"><input type="checkbox" checked={showKey} onChange={x => setShowKey(x.target.checked)} /> Tô đáp án trên bản xem trước</label></div>
    </div>
    <div className="row gap wrap mb">
      <b>Mã đề:</b>{st.versions.map((x, i) => <button key={x.id} className={`chip ${i === vi ? 'on' : ''}`} onClick={() => setVi(i)}>{x.version_code}</button>)}
      <span className="grow" />
      {dirty && <ActionButton className="btn" okMsg="Đã lưu tùy chọn in" onRun={async () => { await save(); reload() }}>Lưu tùy chọn</ActionButton>}
      <ActionButton className="btn primary" onRun={async () => { if (dirty) await save(); return api.download(`/api/exams/${e.id}/paper/exam.pdf?version=${v.version_code}`, `De_${v.version_code}.pdf`) }}>⬇ PDF mã {v.version_code}</ActionButton>
      <ActionButton className="btn" onRun={async () => { if (dirty) await save(); return api.download(`/api/exams/${e.id}/paper/exam.docx?version=${v.version_code}`, `De_${v.version_code}.docx`) }}>⬇ Word mã {v.version_code}</ActionButton>
      <ActionButton className="btn" onRun={async () => { if (dirty) await save(); return api.download(`/api/exams/${e.id}/paper/exam.pdf`, 'De_tat_ca.pdf') }}>⬇ PDF tất cả mã đề</ActionButton>
      <ActionButton className="btn" onRun={() => api.download(`/api/exams/${e.id}/paper/answer-key.pdf`, 'DapAn.pdf')}>⬇ Đáp án</ActionButton>
      <ActionButton className="btn" onRun={async () => { if (dirty) await save(); await api.download(`/api/exams/${e.id}/paper/package.zip`, 'DeThiGiay.zip'); reload() }}>⬇ Trọn bộ (.zip)</ActionButton>
    </div>
    <div className="paper-preview">
      <div className="a4" style={{ '--fs': `${(p.font_size || 11.5) * 1.333}px` }}>
        <div className="ph"><div><b>{p.school}</b>{p.faculty}</div><div><b>{p.exam_name || e.exam_title.toUpperCase()}</b>Môn: {e.course_name} – Mã môn: {e.course_code}<br />
          {p.duration ? `Thời gian: ${p.duration} – ` : ''}{v.questions.length} câu – {e.semester}</div></div>
        <div className="pinfo"><b>MÃ ĐỀ: {v.version_code}</b><span>Họ tên SV: ....................................................</span><span>MSSV: .......................</span></div>
        {p.notes && <p style={{ fontStyle: 'italic', margin: '0 0 8px', fontSize: '0.9em' }}>{p.notes}</p>}
        <div className={`qs ${p.columns === 2 ? 'c2' : ''}`}>{v.questions.map(q => <div key={q.position} className="q">
          <div><b>Câu {q.position}.</b>{p.show_points ? <i> ({q.points} điểm)</i> : ''} {q.content}
            <button className="btn sm ghost no-print" title="Sửa câu hỏi (cập nhật ngân hàng câu hỏi và mọi mã đề)" onClick={() => setEdit(q.question_id)}>✎</button></div>
          <div className="opts" style={{ gridTemplateColumns: `repeat(${optCols(q)}, 1fr)` }}>{q.options.map(o =>
            <div key={o.label} className={showKey && o.label === q.answer ? 'ans' : ''}><b>{o.label}.</b> {o.content}</div>)}</div>
        </div>)}</div>
        <p style={{ textAlign: 'center', fontWeight: 700 }}>--- HẾT ---</p>
      </div>
    </div>
    <p className="muted small">Bản xem trước theo đúng nội dung và thứ tự của mã đề; tệp PDF/Word dùng cùng tùy chọn (khổ A4, phông Times New Roman nếu máy có). Bấm ✎ để sửa nội dung câu hoặc phương án ngay tại đây.</p>
    {edit && <EditQuestion id={edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); reload() }} />}
  </>
}

function EditQuestion({ id, onClose, onSaved }) {
  const q = useApi(`/api/questions/${id}`)
  const [f, setF] = useState(null)
  useEffect(() => { if (q.data) setF({ content: q.data.content, options: q.data.options.map(o => ({ content: o.content, is_correct: o.is_correct })) }) }, [q.data])
  if (!f) return <Modal title="Sửa câu hỏi" onClose={onClose}><Loading {...q} /></Modal>
  const d = q.data
  return <Modal title={`Sửa câu hỏi #${id}`} onClose={onClose}>
    <Field label="Nội dung"><textarea rows={3} value={f.content} onChange={x => setF({ ...f, content: x.target.value })} /></Field>
    {f.options.map((o, i) => <div key={i} className="row gap opt"><input type="radio" name="corr" checked={o.is_correct} aria-label="Đáp án đúng"
      onChange={() => setF({ ...f, options: f.options.map((y, k) => ({ ...y, is_correct: k === i })) })} />
      <b>{'ABCDEF'[i]}.</b><input style={{ flex: 1 }} value={o.content} onChange={x => setF({ ...f, options: f.options.map((y, k) => k === i ? { ...y, content: x.target.value } : y) })} />
      {f.options.length > 2 && <button className="btn sm ghost" onClick={() => setF({ ...f, options: f.options.filter((_, k) => k !== i) })}>✕</button>}</div>)}
    {f.options.length < 6 && <button className="btn sm" onClick={() => setF({ ...f, options: [...f.options, { content: '', is_correct: false }] })}>+ Phương án</button>}
    <p className="muted small">Thêm/bớt phương án thì cần sinh lại mã đề để đề và phiếu cập nhật số ô.</p>
    <div className="row"><span className="grow" /><ActionButton className="btn primary" okMsg="Đã lưu câu hỏi" disabled={f.options.filter(o => o.is_correct).length !== 1 || f.options.some(o => !o.content.trim())}
      onRun={async () => { await api.put(`/api/questions/${id}`, { course_id: d.course_id, outline_id: d.outline_id, bloom_level_id: d.bloom_level_id, content: f.content,
        options: f.options, clos: d.clos.map(c => ({ clo_id: c.clo_id, weight: c.weight })) }); onSaved() }}>Lưu</ActionButton></div>
  </Modal>
}

function Sheet({ e, st, reload }) {
  const [s, setS] = useState(st.sheet)
  const [img, setImg] = useState(null)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const qs = new URLSearchParams({ title: s.title, student_digits: s.student_digits, version_digits: s.version_digits, essay_lines: s.essay_lines }).toString()
  useEffect(() => {
    let url, alive = true
    setBusy(true)
    const t = setTimeout(() => authFetch(`/api/exams/${e.id}/paper/answer-sheet.png?${qs}`).then(async r => {
      if (!r.ok) throw new Error((await r.json()).detail)
      url = URL.createObjectURL(await r.blob()); if (alive) setImg(url)
    }).catch(x => toast(x.message, 'red')).finally(() => alive && setBusy(false)), 350)
    return () => { alive = false; clearTimeout(t); if (url) URL.revokeObjectURL(url) }
  }, [qs])  // eslint-disable-line
  const dirty = ['title', 'student_digits', 'version_digits', 'essay_lines', 'note'].some(k => String(s[k]) !== String(st.sheet[k]))
  return <div className="grid2">
    <div>
      <Field label="Tiêu đề phiếu"><input value={s.title} onChange={x => setS({ ...s, title: x.target.value })} /></Field>
      <div className="row gap wrap">
        <Field label="Số chữ số MSSV"><input className="num" type="number" min="4" max="12" value={s.student_digits} onChange={x => setS({ ...s, student_digits: Number(x.target.value) })} /></Field>
        <Field label="Số chữ số mã đề"><input className="num" type="number" min="1" max="3" value={s.version_digits} onChange={x => setS({ ...s, version_digits: Number(x.target.value) })} /></Field>
        <Field label="Dòng phần tự luận"><input className="num" type="number" min="0" max="15" value={s.essay_lines} onChange={x => setS({ ...s, essay_lines: Number(x.target.value) })} /></Field>
      </div>
      <Field label="Hướng dẫn tô"><textarea rows={2} value={s.note} onChange={x => setS({ ...s, note: x.target.value })} /></Field>
      {st.sheet_printed && dirty && <div className="alert amber small">Phiếu đã được tải về để in. Nếu đổi số chữ số MSSV/mã đề hoặc số dòng tự luận, phiếu đã in theo bố cục cũ sẽ không chấm được.</div>}
      <div className="row gap wrap">
        {dirty && <ActionButton className="btn" okMsg="Đã lưu bố cục phiếu" onRun={async () => { await api.put(`/api/exams/${e.id}/paper/settings`, { paper: st.paper, sheet: s }); reload() }}>Lưu bố cục</ActionButton>}
        <ActionButton className="btn primary" disabled={dirty} title={dirty ? 'Lưu bố cục trước' : ''} onRun={async () => { await api.download(`/api/exams/${e.id}/paper/answer-sheet.pdf`, 'PhieuTraLoi.pdf'); reload() }}>⬇ Phiếu trả lời (PDF)</ActionButton>
        <ActionButton className="btn" disabled={dirty} onRun={async () => { await api.download(`/api/exams/${e.id}/paper/answer-sheet.pdf?copies=${e.n_enrolled || 40}`, 'PhieuTraLoi_ca_lop.pdf'); reload() }}>⬇ In cho cả lớp</ActionButton>
      </div>
      <ul className="small muted mt">
        <li>4 ô vuông đen ở 4 góc giúp nhận diện phiếu kể cả chụp nghiêng bằng điện thoại.</li>
        <li>Mỗi câu có đúng số ô bằng số phương án (theo mã đề nhiều phương án nhất ở vị trí câu đó).</li>
        <li>SV tô MSSV và mã đề ở hai lưới số bên trái; một phiếu dùng chung cho mọi mã đề.</li>
      </ul>
    </div>
    <div>{busy && <div className="muted small">Đang dựng bản xem trước…</div>}{img && <img className="sheet-img" src={img} alt="Xem trước phiếu trả lời" />}</div>
  </div>
}

function CameraPane({ onShot, last, autoSave, setAutoSave }) {
  const vref = useRef(null), sref = useRef(null)
  const [err, setErr] = useState(''), [busy, setBusy] = useState(false), [ready, setReady] = useState(false)
  useEffect(() => {
    let dead = false
    if (!navigator.mediaDevices?.getUserMedia) { setErr('Trình duyệt không cho dùng camera ở địa chỉ này (cần HTTPS). Dùng nút "Chụp bằng điện thoại" bên cạnh.'); return }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false })
      .then(stream => { if (dead) { stream.getTracks().forEach(t => t.stop()); return }
        sref.current = stream; vref.current.srcObject = stream; vref.current.play().then(() => setReady(true)).catch(() => setReady(true)) })
      .catch(x => setErr(x.name === 'NotAllowedError' ? 'Bạn chưa cho phép dùng camera – bấm biểu tượng ổ khóa cạnh địa chỉ để cho phép.' : `Không mở được camera: ${x.message}`))
    return () => { dead = true; sref.current?.getTracks().forEach(t => t.stop()) }
  }, [])
  const shoot = () => {
    const v = vref.current; if (!v || !v.videoWidth) return
    const c = document.createElement('canvas'); c.width = v.videoWidth; c.height = v.videoHeight
    c.getContext('2d').drawImage(v, 0, 0)
    c.toBlob(async b => { setBusy(true); try { await onShot(new File([b], `camera_${Date.now()}.jpg`, { type: 'image/jpeg' })) } catch (x) { /* thông báo ở onShot */ } finally { setBusy(false) } }, 'image/jpeg', 0.92)
  }
  return <div className="cam-pane mt">
    {err ? <div className="alert red small">{err}</div> : <>
      <div className="cam-box"><video ref={vref} playsInline muted /><div className="cam-guide" /></div>
      <div className="row gap wrap mt">
        <button className="btn primary" disabled={!ready || busy} onClick={shoot}>{busy ? 'Đang chấm…' : '📸 Chụp & chấm'}</button>
        <label className="small"><input type="checkbox" checked={autoSave} onChange={x => setAutoSave(x.target.checked)} /> Tự lưu khi phiếu đọc chắc chắn (không có cảnh báo)</label>
      </div>
      <p className="muted small">Đặt phiếu phẳng, vừa khung, đủ 4 ô định vị ở góc và đủ sáng rồi bấm chụp. Kết quả hiện ngay; phiếu cần xem lại được giữ trong danh sách bên dưới. Quét lại cùng MSSV sẽ thay phiếu cũ.</p>
    </>}
    {last && <div className={`alert ${last.bad ? 'amber' : 'green'} small`}>{last.text}</div>}
  </div>
}

function Scan({ e, st, reload }) {
  const toast = useToast()
  const [res, setRes] = useState(null)
  const [sheets, setSheets] = useState([])
  const [cur, setCur] = useState(0)
  const keys = useMemo(() => Object.fromEntries(st.versions.map(v => [v.version_code, Object.fromEntries(v.questions.map(q => [String(q.position), q]))])), [st.versions])
  const [cam, setCam] = useState(false)
  const [autoSave, setAutoSave] = useState(false)
  const [last, setLast] = useState(null)
  const upload = async (files, { append = false } = {}) => {
    const fd = new FormData(); [...files].forEach(f => fd.append('files', f))
    const r = await authFetch(`/api/exams/${e.id}/scan`, { method: 'POST', body: fd })
    const d = await r.json()
    if (!r.ok) throw new Error(d.detail || `Lỗi ${r.status}`)
    const good = d.sheets.filter(x => !x.error)
    if (append) {   // chụp liên tục: cộng dồn; quét lại cùng MSSV thì thay phiếu cũ
      setRes(p => ({ ...d, sheets: [...(p?.sheets || []).filter(x => !x.error), ...d.sheets] }))
      setSheets(p => { const codes = new Set(good.map(x => x.student_code).filter(c => c && !String(c).includes('?')))
        const next = [...p.filter(x => !codes.has(x.student_code)), ...good]; setCur(next.length - 1); return next })
    } else { setRes(d); setSheets(good); setCur(0) }
    return d
  }
  const score = s => { const k = keys[s.version_code]; if (!k) return null; return Object.entries(s.answers).reduce((a, [p, l]) => a + (k[p] && l === k[p].answer ? k[p].points : 0), 0) }
  const upd = (i, patch) => setSheets(x => x.map((y, k) => k === i ? { ...y, ...patch } : y))
  const s = sheets[cur]
  const ok = s => keys[s.version_code] && s.student_code && !String(s.student_code).includes('?')
  const commitSheets = list => api.post(`/api/exams/${e.id}/scan/commit`, { sheets: list.map(x => ({ student_code: x.student_code, version_code: x.version_code, answers: x.answers, source_name: x.source_name })) })
  const shot = async f => {   // camera: chụp xong là đọc và chấm ngay
    const d = await upload([f], { append: true })
    const x = d.sheets[0]
    if (!x || x.error) { setLast({ bad: true, text: x?.error || 'Không đọc được phiếu – chụp lại thẳng, đủ 4 góc, đủ sáng' }); return }
    const sc = score(x), good = ok(x) && !x.issues.length
    if (autoSave && good) {
      try { await commitSheets([x]); setSheets(p => p.filter(y => y.source_name !== x.source_name)); reload()
        setLast({ text: `✔ Đã chấm & lưu: ${x.student_code} – ${x.full_name || ''} · ${sc ?? '—'}/${x.raw_max ?? '—'} điểm` }) }
      catch (err) { setLast({ bad: true, text: err.message }) }
    } else setLast({ bad: !good, text: `${good ? '✔ Đã chấm' : '⚠ Cần xem lại'}: ${x.student_code || '?'} – ${x.full_name || 'không có trong lớp'} · ${sc ?? '—'}/${x.raw_max ?? '—'} điểm${x.issues.length ? ' · ' + x.issues.slice(0, 2).join('; ') : ''}` })
  }
  return <>
    <div className="row gap wrap">
      <FileButton className="btn primary" accept="image/*,.pdf" label="⬆ Tải ảnh phiếu / PDF đã quét" onPick={f => upload([f]).catch(x => toast(x.message, 'red'))} />
      <label className="btn">📷 Chụp bằng điện thoại / chọn nhiều ảnh
        <input type="file" accept="image/*,.pdf" capture="environment" multiple hidden onChange={ev => { const f = [...ev.target.files]; ev.target.value = ''; f.length && upload(f).catch(x => toast(x.message, 'red')) }} /></label>
      <button className="btn primary" onClick={() => setCam(c => !c)}>{cam ? '✕ Đóng camera' : '🎥 Quét bằng camera & chấm ngay'}</button>
      <span className="muted small">Ảnh JPG/PNG hoặc PDF nhiều trang (máy quét); chụp thẳng, đủ 4 góc phiếu, đủ sáng.</span>
    </div>
    {cam && <CameraPane onShot={shot} last={last} autoSave={autoSave} setAutoSave={setAutoSave} />}
    {res && <>
      <div className="stats mt"><Stat label="Phiếu đọc được" value={sheets.length} tone="green" />
        <Stat label="Phiếu lỗi" value={res.sheets.filter(x => x.error).length} tone={res.sheets.some(x => x.error) ? 'red' : ''} />
        <Stat label="Cần xem lại" value={sheets.filter(x => x.issues.length || !ok(x)).length} tone="amber" />
        <Stat label="Đã chấm trước đó" value={st.n_scanned} /></div>
      {res.sheets.filter(x => x.error).map((x, i) => <div key={i} className="alert red small">{x.source_name}: {x.error}</div>)}
      {sheets.length > 0 && <>
        <table className="tbl compact"><thead><tr><th>#</th><th>Tệp</th><th>MSSV</th><th>Họ tên</th><th>Mã đề</th><th className="num-c">Điểm</th><th>Ghi chú</th></tr></thead>
          <tbody>{sheets.map((x, i) => <tr key={i} className={`click ${i === cur ? 'sel' : ''}`} onClick={() => setCur(i)}><td>{i + 1}</td><td className="small">{x.source_name}</td>
            <td className={ok(x) ? '' : 'bad-t'}>{x.student_code || '?'}</td><td>{x.full_name || <span className="bad-t">không có trong lớp</span>}</td><td>{x.version_code}</td>
            <td className="num-c">{score(x) ?? '—'}/{x.raw_max ?? '—'}</td><td className="small">{x.issues.length ? <span className="bad-t">{x.issues.slice(0, 2).join('; ')}{x.issues.length > 2 ? '…' : ''}</span> : <span className="ok-t">OK</span>}</td></tr>)}</tbody></table>
        {s && <div className="scan-grid mt">
          <img src={s.image} alt={`Phiếu ${s.source_name}`} />
          <div>
            <div className="row gap wrap">
              <Field label="MSSV"><input value={s.student_code} onChange={x => upd(cur, { student_code: x.target.value.trim() })} /></Field>
              <Field label="Mã đề"><select value={s.version_code} onChange={x => upd(cur, { version_code: x.target.value })}>
                {!keys[s.version_code] && <option value={s.version_code}>{s.version_code || '?'} (không hợp lệ)</option>}{Object.keys(keys).map(c => <option key={c}>{c}</option>)}</select></Field>
              <Stat label="Điểm (thô)" value={score(s) ?? '—'} sub={`độ tin cậy ${Math.round(s.confidence * 100)}%`} />
            </div>
            {s.issues.length > 0 && <div className="alert amber small">{s.issues.map((t, i) => <div key={i}>{t}</div>)}</div>}
            <div className="ans-cells">{Object.keys(s.answers).sort((a, b) => a - b).map(p => { const k = keys[s.version_code]?.[p]; const v = s.answers[p]
              return <label key={p}><span className="small">{p}.</span><input value={v} maxLength={2} title={k ? `Đáp án: ${k.answer}` : ''}
                className={`${v.length > 1 || !v ? 'warn' : ''} ${k && v && v !== k.answer ? 'wrong' : ''}`}
                onChange={x => upd(cur, { answers: { ...s.answers, [p]: x.target.value.toUpperCase().replace(/[^A-F]/g, '') } })} /></label> })}</div>
            <p className="muted small">Ô vàng: bỏ trống hoặc tô nhiều ô (tính sai); chữ đỏ: khác đáp án. Sửa trực tiếp nếu máy đọc nhầm.</p>
            <div className="row gap"><button className="btn sm" disabled={cur === 0} onClick={() => setCur(cur - 1)}>‹ Phiếu trước</button>
              <button className="btn sm" disabled={cur >= sheets.length - 1} onClick={() => setCur(cur + 1)}>Phiếu sau ›</button>
              <button className="btn sm ghost" onClick={() => { setSheets(x => x.filter((_, k) => k !== cur)); setCur(Math.max(0, cur - 1)) }}>Bỏ phiếu này</button></div>
          </div>
        </div>}
        <div className="row gap mt"><span className="grow" />
          <ActionButton className="btn primary" disabled={!sheets.length || sheets.some(x => !ok(x))} title={sheets.some(x => !ok(x)) ? 'Còn phiếu sai MSSV/mã đề' : ''}
            okMsg={r => `Đã lưu ${r.saved} bài${r.absent ? `, ${r.absent} SV vắng` : ''}${r.analysis ? ' – đã phân tích' : ''}`}
            onRun={async () => { const r = await commitSheets(sheets); reload(); setRes(null); setSheets([]); setLast(null); return r }}>
            Lưu kết quả {sheets.length} phiếu &amp; phân tích</ActionButton></div>
      </>}
    </>}
  </>
}
