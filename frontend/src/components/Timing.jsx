// Thời gian làm bài trên Moodle Quiz: cảnh báo SV chọn đại rồi nộp, chọn xong không nộp để hết giờ… (dấu hiệu để GV xem lại)
import { useState } from 'react'
import { Bar, Scatter } from 'react-chartjs-2'
import { api } from '../api'
import { C } from '../charts'
import { ActionButton, Badge, Card, Loading, Modal, Stat } from './ui'
import { useApi } from '../hooks'

const DEF = { min_sec_per_q: 6, rapid_sec: 3, rapid_share: 25, idle_min: 10, idle_share: 30 }
// miền hợp lệ của từng ngưỡng (đơn vị trên giao diện; khớp kiểm tra ở API)
const RANGE = { min_sec_per_q: [0, 600, 'Giây/câu'], rapid_sec: [0, 60, 'Ngưỡng chớp nhoáng (giây)'], rapid_share: [0, 100, 'Tỷ lệ câu chớp nhoáng (%)'],
  idle_min: [0, 600, 'Số phút không thao tác'], idle_share: [0, 100, 'Tỷ lệ thời gian không thao tác (%)'] }
function checked(form) {
  const t = {}
  for (const [k, [lo, hi, label]] of Object.entries(RANGE)) {
    const v = String(form[k]).trim() === '' ? NaN : Number(form[k])
    if (!Number.isFinite(v) || v < lo || v > hi) throw new Error(`${label} phải là số từ ${lo} đến ${hi}`)
    t[k] = v
  }
  return t
}
const LEVEL = { canh_bao: ['red', 'Cảnh báo'], luu_y: ['amber', 'Lưu ý'] }
const qs = t => `min_sec_per_q=${t.min_sec_per_q}&rapid_sec=${t.rapid_sec}&rapid_share=${t.rapid_share / 100}&idle_min=${t.idle_min}&idle_share=${t.idle_share / 100}`

export default function Timing({ examId, sectionCode }) {
  const [th, setTh] = useState(DEF)
  const [form, setForm] = useState(DEF)
  const [all, setAll] = useState(false)
  const [open, setOpen] = useState(null)
  const r = useApi(`/api/exams/${examId}/timing?${qs(th)}`)
  const d = r.data
  if (!d) return <Loading {...r} />
  if (!d.available) return <Card title="Thời gian làm bài"><div className="alert blue">{d.reason}</div></Card>
  const s = d.summary
  const hot = q => q.n_rapid >= Math.max(3, 0.1 * s.n_attempts)
  const rows = all ? d.attempts : d.attempts.filter(a => a.level)
  const pt = (code) => d.attempts.filter(a => a.flags.some(f => f.code === code)).map(a => ({ x: a.active_min, y: a.duration_min, label: a.student_code }))
  const normal = d.attempts.filter(a => !a.level).map(a => ({ x: a.active_min, y: a.duration_min, label: a.student_code }))
  const num = (k, step = 1) => <input className="num tiny" type="number" min={RANGE[k][0]} max={RANGE[k][1]} step={step} title={RANGE[k][2]} value={form[k]} onChange={e => setForm(f => ({ ...f, [k]: e.target.value }))} />
  return <>
    <div className="stats">
      <Stat label="SV làm bài" value={s.n_attempts} sub={`${d.n_questions} câu · giới hạn ${d.time_limit_min ? `${d.time_limit_min} phút` : 'không giới hạn'}`} />
      <Stat label="Thời gian làm (trung vị)" value={`${s.median_duration_min} phút`} sub={`nhanh nhất ${s.min_duration_min} – lâu nhất ${s.max_duration_min} phút`} />
      <Stat label="Nộp do hết giờ" value={s.n_timeout} sub="Moodle tự nộp" />
      <Stat label="Cảnh báo" value={s.n_warning} tone={s.n_warning ? 'red' : 'green'} sub={`làm quá nhanh ${s.flags.LAM_NHANH} · treo máy ${s.flags.TREO_MAY} · bỏ dở ${s.flags.BO_DO}`} />
      <Stat label="Lưu ý" value={s.n_notice} tone={s.n_notice ? 'amber' : ''} sub={`để lâu mới nộp ${s.flags.NOP_MUON} · dồn phút cuối ${s.flags.DON_CUOI}`} />
    </div>
    {d.page_resolution && <div className="alert amber">Quiz đặt nhiều câu trên một trang nên Moodle lưu đáp án theo trang: thời gian từng câu là ước lượng (chia đều thời gian của trang).
      Muốn đo chính xác từng câu, đặt Quiz “Mỗi trang 1 câu” (Layout → New page: Every question).</div>}
    <div className="grid2">
      <Card title="Thời điểm chọn đáp án cuối và lúc nộp bài">
        <div style={{ height: 300 }}>
          <Scatter data={{ datasets: [
            { label: 'Bình thường', data: normal, backgroundColor: C.blueA, borderColor: C.blue, pointRadius: 5 },
            { label: 'Làm quá nhanh / chọn đại', data: pt('LAM_NHANH'), backgroundColor: C.red, pointRadius: 7, pointStyle: 'triangle' },
            { label: 'Treo máy chờ hết giờ', data: pt('TREO_MAY'), backgroundColor: C.amber, pointRadius: 7, pointStyle: 'rectRot' },
            { label: 'Bỏ dở', data: pt('BO_DO'), backgroundColor: '#7c3aed', pointRadius: 7, pointStyle: 'rect' }] }}
            options={{ maintainAspectRatio: false, plugins: { tooltip: { callbacks: { label: c => `${c.raw.label}: chọn cuối phút ${c.raw.x}, nộp phút ${c.raw.y}` } } },
              scales: { x: { title: { display: true, text: 'Lần chọn đáp án cuối (phút kể từ lúc bắt đầu)' }, min: 0 },
                        y: { title: { display: true, text: 'Nộp bài (phút)' }, min: 0, suggestedMax: d.time_limit_min || undefined } } }} />
        </div>
        <p className="muted small">Điểm nằm trên đường chéo: nộp ngay sau khi chọn xong. Góc dưới-trái: làm rất nhanh. Góc trên-trái: chọn xong sớm nhưng để tới hết giờ.</p>
      </Card>
      <Card title="Cách hệ thống cảnh báo" actions={<ActionButton className="btn sm" onRun={() => api.download(`/api/exams/${examId}/timing.xlsx?${qs(th)}`, `ThoiGianLamBai_${sectionCode}.xlsx`)}>⬇ Xuất Excel</ActionButton>}>
        <ul className="small tight">
          <li><Badge tone="red">Làm quá nhanh – nghi chọn đại</Badge> trung bình dưới {num('min_sec_per_q', 0.5)} giây/câu, hoặc từ {num('rapid_share', 5)}% số câu trở lên trả lời “chớp nhoáng”
            (dưới {num('rapid_sec', 0.5)} giây, hoặc dưới 10% thời gian trung vị của câu đó trong lớp, tối đa 10 giây).</li>
          <li><Badge tone="red">Chọn xong không nộp – để hết giờ</Badge> Moodle tự nộp khi hết giờ và trước đó không thao tác từ {num('idle_min')} phút, chiếm từ {num('idle_share', 5)}% thời gian làm bài.</li>
          <li><Badge tone="red">Bỏ dở</Badge> bỏ trống từ một nửa số câu rồi tự nộp (không chờ hết giờ).</li>
          <li><Badge tone="amber">Lưu ý</Badge> để lâu không thao tác rồi mới tự nộp; dồn nhiều đáp án vào 60 giây cuối.</li>
        </ul>
        <div className="row gap">
          <ActionButton className="btn sm primary" onRun={async () => setTh(checked(form))}>Áp dụng ngưỡng</ActionButton>
          <button className="btn sm ghost" onClick={() => { setForm(DEF); setTh(DEF) }}>Mặc định</button>
        </div>
        <p className="muted small mt">Đây là <b>dấu hiệu để xem lại</b> (đối chiếu nhật ký Moodle, quan sát phòng thi), không phải kết luận gian lận. Thời điểm lấy từ các lần Moodle lưu đáp án của SV.</p>
      </Card>
    </div>
    <Card title={`Sinh viên ${all ? '' : 'có dấu hiệu bất thường '}(${rows.length})`}
      actions={<label className="small"><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)} /> Hiện tất cả SV</label>}>
      {!rows.length ? <p className="muted">Không có lượt làm bài nào có dấu hiệu bất thường theo ngưỡng hiện tại.</p> :
        <div className="scroll"><table className="tbl compact">
          <thead><tr><th>MSSV</th><th>Họ tên</th><th className="num-c">Thời gian làm</th><th className="num-c">Chọn cuối lúc</th><th className="num-c">Không thao tác cuối</th>
            <th className="num-c">Giây/câu</th><th className="num-c">Chớp nhoáng</th><th className="num-c">Đổi đáp án</th><th>Nộp</th><th className="num-c">Điểm</th><th>Dấu hiệu</th><th /></tr></thead>
          <tbody>{rows.map(a => <tr key={a.attempt_id}>
            <td>{a.student_code}</td><td><b>{a.full_name}</b></td><td className="num-c">{a.duration_min}′</td><td className="num-c">phút {a.active_min}</td>
            <td className={`num-c ${a.idle_min >= th.idle_min ? 'bad-t' : ''}`}>{a.idle_min}′</td>
            <td className={`num-c ${a.sec_per_q < th.min_sec_per_q ? 'bad-t' : ''}`}>{a.sec_per_q}</td>
            <td className="num-c">{a.n_rapid}/{a.n_answered}</td><td className="num-c">{a.n_changes}</td>
            <td>{a.finished_by_timeout ? <Badge tone="amber">Hết giờ tự nộp</Badge> : 'Tự nộp'}</td><td className="num-c">{a.score10}</td>
            <td>{a.flags.length ? a.flags.map(f => <div key={f.code} className="small"><Badge tone={LEVEL[f.level][0]}>{f.label}</Badge> <span className="muted">{f.detail}</span></div>) : <span className="ok-t small">Bình thường</span>}</td>
            <td><button className="btn sm" onClick={() => setOpen(a)}>Diễn biến</button></td></tr>)}</tbody></table></div>}
    </Card>
    {/* câu "nóng": từ 10% số SV (tối thiểu 3 SV) trả lời chớp nhoáng – có thể quá dễ, đã lộ đáp án */}
    <Card title="Thời gian trả lời từng câu (trung vị của lớp)">
      <div style={{ height: 220 }}>
        <Bar data={{ labels: d.questions.map(x => `Câu ${x.order_index}`), datasets: [{ label: 'Trung vị (giây)', data: d.questions.map(x => x.median_sec),
            backgroundColor: d.questions.map(x => hot(x) ? C.red : C.blueA), borderColor: d.questions.map(x => hot(x) ? C.red : C.blue), borderWidth: 1, borderRadius: 4 }] }}
          options={{ maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: {
              afterLabel: c => { const q = d.questions[c.dataIndex]; return [`Ngưỡng chớp nhoáng: ${q.rapid_threshold} giây`, `SV trả lời chớp nhoáng: ${q.n_rapid}`] } } } },
            scales: { y: { title: { display: true, text: 'giây (trung vị của lớp)' } } } }} />
      </div>
      <p className="muted small">Cột đỏ: câu có từ 10% số SV (tối thiểu 3 SV) trả lời chớp nhoáng; rê chuột để xem số SV và ngưỡng của từng câu. Câu có thời gian trung vị rất ngắn so với độ dài đề có thể quá dễ hoặc đã lộ; câu nhiều SV trả lời chớp nhoáng cần xem lại cùng chỉ số p, DI.</p>
    </Card>
    {open && <Timeline examId={examId} a={open} onClose={() => setOpen(null)} />}
  </>
}

function Timeline({ examId, a, onClose }) {
  const t = useApi(`/api/exams/${examId}/timing/students/${a.student_id}`)
  const d = t.data
  const color = i => i.response_status === 'blank' ? C.gray : i.is_correct ? C.green : C.red
  return <Modal title={`Diễn biến làm bài – ${a.full_name} (${a.student_code})`} onClose={onClose} wide>
    <Loading {...t} />
    {d && <>
      <p>Bắt đầu {String(d.started_at).replace('T', ' ')} · chọn đáp án cuối cùng ở <b>phút {d.last_answer_min ?? '—'}</b> · nộp ở <b>phút {d.duration_min}</b>
        {d.time_limit_min ? ` / ${d.time_limit_min} phút cho phép` : ''} {d.finished_by_timeout && <Badge tone="amber">Moodle tự nộp khi hết giờ</Badge>}</p>
      {a.flags.map(f => <div key={f.code} className={`alert ${f.level === 'canh_bao' ? 'red' : 'amber'} small`}><b>{f.label}:</b> {f.detail}</div>)}
      <div style={{ height: 230 }}>
        <Bar data={{ labels: d.items.map(i => `Câu ${i.order_index}`), datasets: [{ label: 'Thời gian trả lời (giây)', data: d.items.map(i => i.response_time_sec ?? 0), backgroundColor: d.items.map(color) }] }}
          options={{ maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { afterLabel: c => { const i = d.items[c.dataIndex]; return i.response_status === 'blank' ? 'bỏ trống' : `chọn ${i.chosen} (đáp án ${i.answer}) · lần đầu phút ${i.first_min}` } } } },
            scales: { y: { title: { display: true, text: 'giây' } } } }} />
      </div>
      <p className="muted small">Xanh: đúng · đỏ: sai · xám: bỏ trống.</p>
      <div className="scroll"><table className="tbl compact">
        <thead><tr><th>Câu</th><th>Nội dung</th><th>Chọn</th><th>Đáp án</th><th className="num-c">Thời gian trả lời</th><th className="num-c">Chọn lần đầu</th><th className="num-c">Chọn lần cuối</th><th className="num-c">Số lần lưu</th></tr></thead>
        <tbody>{d.items.map(i => <tr key={i.question_id}><td>{i.order_index}</td><td className="clip">{i.content}</td>
          <td className={i.response_status === 'blank' ? 'muted' : i.is_correct ? 'ok-t' : 'bad-t'}>{i.chosen || 'bỏ trống'}</td><td>{i.answer}</td>
          <td className="num-c">{i.response_time_sec != null ? `${i.response_time_sec} giây` : '—'}</td><td className="num-c">{i.first_min != null ? `phút ${i.first_min}` : '—'}</td>
          <td className="num-c">{i.last_min != null ? `phút ${i.last_min}` : '—'}</td><td className="num-c">{i.n_answer_saves ?? '—'}</td></tr>)}</tbody></table></div>
    </>}
  </Modal>
}
