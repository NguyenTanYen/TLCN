import { useState } from 'react'
import { api } from '../api'
import { ActionButton, Badge, FileButton, Modal, Stat, useToast } from './ui'

const ACCEPT_Q = '.xlsx,.csv,.txt,.docx,.xml'
const ST_Q = { ok: ['green', 'Hợp lệ'], duplicate: ['amber', 'Trùng'], error: ['red', 'Lỗi'] }
const ST_T = { update: ['blue', 'Sẽ cập nhật'], unchanged: ['gray', 'Không đổi'], locked: ['amber', 'Đã có kết quả thi'], error: ['red', 'Lỗi'] }

const FilePick = ({ accept, onPick, label }) => <FileButton accept={accept} onPick={onPick} label={label} />

// ------------------------------------------------------------------ Bước 1: nhập hàng loạt câu hỏi
export function ImportQuestions({ course, onClose, onDone }) {
  const [file, setFile] = useState(null)
  const [skipDup, setSkipDup] = useState(true)
  const [prev, setPrev] = useState(null)
  const [err, setErr] = useState('')
  const [done, setDone] = useState(null)
  const [busy, setBusy] = useState(false)
  const [show, setShow] = useState('all')
  const toast = useToast()

  const run = async (f, dry, skip = skipDup) => {
    setErr(''); setBusy(true)
    try {
      const r = await api.upload(`/api/questions/import?course_id=${course.id}&dry_run=${dry}&skip_duplicates=${skip}`, f)
      if (dry) setPrev(r); else { setDone(r); toast(`Đã nhập ${r.created_ids.length} câu hỏi`); onDone() }
    } catch (e) { setErr(e.message); if (dry) setPrev(null) } finally { setBusy(false) }
  }
  const pick = f => { setFile(f); setDone(null); run(f, true) }
  const s = prev?.summary
  const rows = (prev?.rows || []).filter(r => show === 'all' || r.status === show)

  return (
    <Modal title="Nhập câu hỏi hàng loạt từ file" onClose={onClose} wide>
      {done ? <>
        <div className="alert green">Đã thêm <b>{done.created_ids.length}</b> câu hỏi vào ngân hàng (ID {done.created_ids[0]}–{done.created_ids[done.created_ids.length - 1]}).
          {done.summary.untagged > 0 && <> Trong đó <b>{done.summary.untagged}</b> câu chưa gán CLO/Bloom.</>}</div>
        {done.summary.untagged > 0 && <p>Bước tiếp theo: tải file gán CLO cho các câu vừa nhập, điền cột <b>Chương, Bloom, CLO</b> rồi tải lên ở mục <b>Gán CLO/Bloom từ file</b>.</p>}
        <div className="row gap wrap">
          {done.summary.untagged > 0 && <ActionButton className="btn primary" onRun={() => api.download(`/api/questions/tagging-template?course_id=${course.id}&ids=${done.created_ids.join(',')}`, 'gan_clo.xlsx')}>⬇ Tải file gán CLO cho {done.created_ids.length} câu vừa nhập</ActionButton>}
          <span className="grow" /><button className="btn" onClick={onClose}>Đóng</button>
        </div>
      </> : <>
        <div className="grid2">
          <div>
            <p className="mt0">Môn <b>{course.course_code} – {course.course_name}</b>. Hỗ trợ các định dạng:</p>
            <ul className="small">
              <li><b>Excel / CSV</b> theo mẫu: Nội dung | A | B | C | D… | Đáp án | (Chương | Bloom | CLO)</li>
              <li><b>Aiken</b> (.txt hoặc Word .docx): câu hỏi, các dòng <code>A. …</code>, dòng <code>ANSWER: B</code></li>
              <li><b>Moodle XML</b> (.xml) xuất từ ngân hàng câu hỏi Moodle (trắc nghiệm một đáp án)</li>
            </ul>
            <p className="small muted">Chương, Bloom, CLO có thể để trống – câu sẽ ở trạng thái <b>Chưa gán</b> và được gán sau bằng file Excel.
              Câu chưa gán không đưa được vào đề.</p>
          </div>
          <div className="row gap wrap" style={{ alignContent: 'flex-start' }}>
            <ActionButton className="btn" onRun={() => api.download(`/api/questions/import-template?course_id=${course.id}`, 'mau_nhap_cau_hoi.xlsx')}>⬇ Tải file mẫu Excel</ActionButton>
            <FilePick accept={ACCEPT_Q} onPick={pick} label={file ? 'Chọn file khác…' : 'Chọn file câu hỏi…'} />
            {file && <span className="muted small">{file.name}</span>}
          </div>
        </div>
        {busy && <div className="muted pad">Đang đọc file…</div>}
        {err && <div className="alert red mt">{err}</div>}
        {s && <>
          <div className="stats mt">
            <Stat label="Đọc được" value={s.total} sub={`định dạng ${s.format}`} />
            <Stat label="Hợp lệ" value={s.ok} tone="green" />
            <Stat label="Trùng" value={s.duplicate} tone={s.duplicate ? 'amber' : ''} sub="đã có hoặc lặp trong file" />
            <Stat label="Lỗi (bỏ qua)" value={s.error} tone={s.error ? 'red' : ''} />
            <Stat label="Sẽ nhập" value={s.will_add} sub={`${s.untagged} câu chưa gán CLO/Bloom`} />
          </div>
          <div className="row gap wrap mb">
            {[['all', 'Tất cả'], ['error', `Lỗi (${s.error})`], ['duplicate', `Trùng (${s.duplicate})`], ['ok', `Hợp lệ (${s.ok})`]].map(([k, l]) =>
              <button key={k} className={`chip ${show === k ? 'on' : ''}`} onClick={() => setShow(k)}>{l}</button>)}
            <span className="grow" />
            <label className="row gap check"><input type="checkbox" checked={!skipDup} onChange={e => { setSkipDup(!e.target.checked); run(file, true, !e.target.checked) }} /> Vẫn nhập câu trùng</label>
          </div>
          <div className="scroll">
            <table className="tbl compact"><thead><tr><th>Dòng</th><th>Trạng thái</th><th>Nội dung</th><th>PA</th><th>Đáp án</th><th>Chương</th><th>Bloom</th><th>CLO</th><th>Ghi chú</th></tr></thead>
              <tbody>{rows.map((r, i) => <tr key={i}>
                <td>{r.row}</td><td><Badge tone={ST_Q[r.status][0]}>{ST_Q[r.status][1]}</Badge></td>
                <td className="clip" title={r.content + '\n' + r.options.map((o, j) => `${'ABCDEFGHIJ'[j]}. ${o}`).join('\n')}>{r.content || '—'}</td>
                <td>{r.options.length}</td><td>{r.answer || '—'}</td><td>{r.chapter || '—'}</td><td>{r.bloom_text || '—'}</td>
                <td>{r.clo_text || (r.status === 'error' ? '—' : <Badge tone="amber">Chưa gán</Badge>)}</td>
                <td className={r.errors.length ? 'bad-t small' : 'muted small'}>{[...r.errors, ...r.warnings.filter(w => !w.startsWith('Chưa đủ'))].join('; ')}</td>
              </tr>)}</tbody></table>
          </div>
          <div className="row gap mt"><span className="grow" /><button className="btn" onClick={onClose}>Hủy</button>
            <ActionButton className="btn primary" disabled={!s.will_add || busy} onRun={() => run(file, false)}>Nhập {s.will_add} câu hỏi</ActionButton></div>
        </>}
      </>}
    </Modal>
  )
}

// ------------------------------------------------------------------ Bước 2: gán CLO / Bloom / chương từ file
export function TagFromFile({ course, untagged, onClose, onDone }) {
  const [file, setFile] = useState(null)
  const [prev, setPrev] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(null)
  const [show, setShow] = useState('all')
  const toast = useToast()

  const run = async (f, dry) => {
    setErr(''); setBusy(true)
    try {
      const r = await api.upload(`/api/questions/tagging-import?course_id=${course.id}&dry_run=${dry}`, f)
      if (dry) setPrev(r); else { setDone(r); toast(`Đã cập nhật ${r.summary.update} câu hỏi`); onDone() }
    } catch (e) { setErr(e.message); setPrev(null) } finally { setBusy(false) }
  }
  const s = prev?.summary
  const rows = (prev?.rows || []).filter(r => show === 'all' || r.status === show)

  return (
    <Modal title="Gán CLO / mức Bloom / chương cho nhiều câu từ file Excel" onClose={onClose} wide>
      {done ? <>
        <div className="alert green">Đã cập nhật <b>{done.summary.update}</b> câu hỏi.
          {done.summary.untagged_left > 0 ? <> Còn <b>{done.summary.untagged_left}</b> câu chưa gán đủ CLO + Bloom.</> : <> Mọi câu hỏi của môn đã được gán đủ.</>}</div>
        <div className="row gap"><span className="grow" /><button className="btn primary" onClick={onClose}>Xong</button></div>
      </> : <>
        <ol className="steps">
          <li>Tải file gán CLO (mỗi dòng 1 câu, có sẵn ID, nội dung, đáp án và giá trị hiện tại; sheet <i>HuongDan</i> liệt kê chương, mức Bloom, CLO của môn).
            <div className="row gap wrap mt">
              <ActionButton className="btn" disabled={!untagged} onRun={() => api.download(`/api/questions/tagging-template?course_id=${course.id}&only_untagged=true`, 'gan_clo.xlsx')}>⬇ Các câu chưa gán ({untagged})</ActionButton>
              <ActionButton className="btn" onRun={() => api.download(`/api/questions/tagging-template?course_id=${course.id}`, 'gan_clo.xlsx')}>⬇ Toàn bộ ngân hàng câu hỏi</ActionButton>
            </div></li>
          <li>Điền cột <b>Chương</b> (số), <b>Bloom</b> (chọn 1–6), <b>CLO</b>: <code>CLO2</code>, <code>CLO1; CLO3</code> (chia đều) hoặc <code>CLO1:0.6; CLO3:0.4</code>. Ô trống = giữ nguyên.</li>
          <li>Tải file đã điền lên để xem trước thay đổi, rồi bấm Cập nhật.
            <div className="row gap wrap mt"><FilePick accept=".xlsx,.csv" onPick={f => { setFile(f); run(f, true) }} label={file ? 'Chọn file khác…' : 'Chọn file đã điền…'} />
              {file && <span className="muted small">{file.name}</span>}</div></li>
        </ol>
        {busy && <div className="muted pad">Đang kiểm tra…</div>}
        {err && <div className="alert red mt">{err}</div>}
        {s && <>
          <div className="stats mt">
            <Stat label="Dòng trong file" value={s.total} />
            <Stat label="Sẽ cập nhật" value={s.update} tone="green" />
            <Stat label="Không đổi" value={s.unchanged} />
            <Stat label="Đã có kết quả thi" value={s.locked} tone={s.locked ? 'amber' : ''} sub="giữ nguyên để bảo toàn minh chứng" />
            <Stat label="Lỗi (bỏ qua)" value={s.error} tone={s.error ? 'red' : ''} />
          </div>
          <div className="row gap wrap mb">
            {[['all', 'Tất cả'], ['update', `Cập nhật (${s.update})`], ['error', `Lỗi (${s.error})`], ['locked', `Đã có kết quả (${s.locked})`], ['unchanged', `Không đổi (${s.unchanged})`]].map(([k, l]) =>
              <button key={k} className={`chip ${show === k ? 'on' : ''}`} onClick={() => setShow(k)}>{l}</button>)}
          </div>
          <div className="scroll">
            <table className="tbl compact"><thead><tr><th>Dòng</th><th>ID</th><th>Trạng thái</th><th>Nội dung</th><th>Thay đổi / lỗi</th></tr></thead>
              <tbody>{rows.map((r, i) => <tr key={i}>
                <td>{r.row}</td><td>{r.id ?? '—'}</td><td><Badge tone={ST_T[r.status][0]}>{ST_T[r.status][1]}</Badge></td>
                <td className="clip">{r.content || '—'}</td>
                <td className="small">{r.changes.map(c => <div key={c}>{c}</div>)}{r.errors.map(e => <div key={e} className="bad-t">{e}</div>)}</td>
              </tr>)}</tbody></table>
          </div>
          <div className="row gap mt"><span className="grow" /><button className="btn" onClick={onClose}>Hủy</button>
            <ActionButton className="btn primary" disabled={!s.update || busy} onRun={() => run(file, false)}>Cập nhật {s.update} câu hỏi</ActionButton></div>
        </>}
      </>}
    </Modal>
  )
}
