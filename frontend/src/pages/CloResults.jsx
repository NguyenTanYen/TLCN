import { useState } from 'react'
import { Bar } from 'react-chartjs-2'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api, fmtPct } from '../api'
import { C } from '../charts'
import { Achieved, ActionButton, Badge, Card, Field, Loading, Modal, Stat, diClass } from '../components/ui'
import { useApi } from '../hooks'

const EVID = { process: 'Quá trình', final: 'Cuối kỳ', any: 'Quá trình + Cuối kỳ' }

export default function CloResults() {
  const { id } = useParams()
  const res = useApi(`/api/class-sections/${id}/clo-results`)
  const cs = useApi('/api/class-sections').data?.find(x => String(x.id) === id)
  const course = useApi(cs ? `/api/courses/${cs.course_id}?semester_id=${cs.semester_id}` : null)
  const [sp] = useSearchParams()
  const [tab, setTab] = useState(sp.get('tab') === 'bm6a' ? 'bm6a' : 'bm6b')
  const [evid, setEvid] = useState(null)
  const [plan, setPlan] = useState(null)
  const r = res.data
  if (!r) return <Loading {...res} />
  const cr = r.course_result
  return (
    <>
      <div className="page-h">
        <div><div className="crumb"><Link to="/">Lớp học phần</Link> / <Link to={`/sections/${id}`}>{cs?.section_code}</Link> / Kết quả CĐR</div>
          <h1>Đo lường CĐR môn học</h1><p className="muted">{r.course} · {r.semester} · GV {cs?.lecturer}</p></div>
        <ActionButton className="btn primary" onRun={() => api.download(`/api/reports/class-sections/${id}/bm6.xlsx`, 'BM6.xlsx')}>⬇ Xuất biểu mẫu BM6 (.xlsx)</ActionButton>
      </div>
      {!r.has_data && <div className="alert amber">Lớp chưa có bài kiểm tra nào được phân tích – kết quả CĐR sẽ xuất hiện sau khi đồng bộ/nhập phiếu và phân tích.</div>}
      <div className="stats">
        <Stat label="Số CLO" value={r.clos.length} sub={`${r.clos.filter(c => c.is_achieved).length} đạt`} />
        <Stat label="Lượt SV được đánh giá" value={cr.n_evaluated} sub={`${cr.n_achieved} lượt đạt`} />
        <Stat label="Tỷ lệ đạt CĐR môn học" value={fmtPct(cr.achieved_pct)} sub={`chỉ tiêu ${cr.target_pct}%`} tone={cr.is_achieved ? 'green' : 'red'} />
        <Stat label="Kết luận" value={cr.n_evaluated ? (cr.is_achieved ? 'Đạt' : 'Không đạt') : '—'} tone={cr.is_achieved ? 'green' : 'red'} />
      </div>
      <div className="tabs">
        <button className={tab === 'bm6a' ? 'on' : ''} onClick={() => setTab('bm6a')}>BM6a – Kế hoạch đánh giá</button>
        <button className={tab === 'bm6b' ? 'on' : ''} onClick={() => setTab('bm6b')}>BM6b – Kết quả tổng hợp</button>
      </div>
      {tab === 'bm6a' && <Card title="Bảng kế hoạch kiểm tra, đánh giá mức độ đạt cho từng CĐR môn học">
        <table className="tbl"><thead><tr><th>CĐR</th><th>Nội dung</th><th>PLO (mức)</th><th>Bài KT có CĐR</th><th>Bài KT lấy minh chứng</th><th>Phương pháp</th><th>Chu kỳ</th><th>Ngưỡng đạt / SV</th><th>Chỉ tiêu</th><th /></tr></thead>
          <tbody>{course.data?.clos.map(c => <tr key={c.id}><td><b>{c.clo_code}</b></td><td className="clip">{c.description}</td>
            <td>{c.plos.map(p => `${p.plo_code}(${p.level})`).join(', ')}</td><td>{c.plan?.assessments_text || '—'}</td><td>{EVID[c.plan?.evidence_type] || '—'}</td>
            <td>{c.plan?.method}</td><td>{c.plan?.cycle}</td><td>{c.plan ? `${c.plan.pass_threshold_pct}% điểm tối đa` : '—'}</td><td>{c.plan ? `${c.plan.target_pct}%` : '—'}</td>
            <td><button className="btn sm" onClick={() => setPlan({ clo: c, semester_id: cs.semester_id })}>Sửa</button></td></tr>)}</tbody></table>
        <p className="muted mt">Chỉ tiêu mong muốn đạt CĐR môn học: <b>{course.data?.clo_target_pct}%</b>. Mỗi SV được tính “đạt” một CLO khi tổng điểm các câu hỏi thuộc CLO ≥ ngưỡng % điểm tối đa của các câu đó.</p>
      </Card>}
      {tab === 'bm6b' && <>
        <Card title="Tỷ lệ SV đạt từng CLO so với chỉ tiêu">
          <div className="chart"><Bar data={{ labels: r.clos.map(c => c.clo_code), datasets: [
            { label: 'Tỷ lệ % SV đạt', data: r.clos.map(c => c.achieved_pct), backgroundColor: r.clos.map(c => c.is_achieved ? C.green : C.red), borderRadius: 4 },
            { label: 'Chỉ tiêu mong muốn', data: r.clos.map(c => c.target_pct), backgroundColor: C.grayA, borderColor: C.gray, borderWidth: 1, borderRadius: 4 }] }}
            options={{ maintainAspectRatio: false, scales: { y: { min: 0, max: 100, title: { display: true, text: '%' } } } }} /></div>
        </Card>
        <Card title="Kết quả tổng hợp của từng CĐR môn học (BM6b)">
          <table className="tbl"><thead><tr><th>CĐR</th><th>Nội dung</th><th>PLO</th><th>Minh chứng</th><th>SV đạt</th><th>SV đánh giá</th><th>Tỷ lệ</th><th>Chỉ tiêu</th><th>Kết quả</th><th /></tr></thead>
            <tbody>{r.clos.map(c => <tr key={c.clo_id}><td><b>{c.clo_code}</b></td><td className="clip">{c.description}</td><td>{c.plos}</td><td>{EVID[c.evidence_type] || '—'}</td>
              <td>{c.n_achieved ?? '—'}</td><td>{c.n_evaluated ?? '—'}</td><td><b>{fmtPct(c.achieved_pct)}</b></td><td>{c.target_pct}%</td>
              <td><Achieved ok={c.n_evaluated ? !!c.is_achieved : null} /></td>
              <td><button className="btn sm" disabled={!c.n_evaluated} onClick={() => setEvid(c)}>Minh chứng</button></td></tr>)}
              <tr className="total"><td colSpan={4}>KẾT QUẢ ĐẠT ĐƯỢC CĐR MÔN HỌC</td><td>{cr.n_achieved}</td><td>{cr.n_evaluated}</td><td>{fmtPct(cr.achieved_pct)}</td><td>{cr.target_pct}%</td><td><Achieved ok={cr.n_evaluated ? cr.is_achieved : null} /></td><td /></tr>
            </tbody></table>
        </Card>
      </>}
      {evid && <Evidence cs={id} clo={evid} onClose={() => { setEvid(null); res.reload() }} />}
      {plan && <PlanForm {...plan} onClose={() => setPlan(null)} onSaved={() => { setPlan(null); course.reload(); res.reload() }} />}
    </>
  )
}

function Evidence({ cs, clo, onClose }) {
  const { data, ...st } = useApi(`/api/class-sections/${cs}/clo-results/${clo.clo_id}/evidence`)
  const [n, setN] = useState({ analysis: clo.analysis || '', improvement: clo.improvement || '' })
  const exams = data ? [...new Map(data.evidence.map(e => [e.exam_id, e])).values()] : []
  return (
    <Modal title={`Minh chứng ${clo.clo_code} (BM6c/6d)`} onClose={onClose} wide>
      <Loading {...st} />
      {data && <>
        <div className="grid2">
          {exams.map(ex => {
            const rows = data.evidence.filter(e => e.exam_id === ex.exam_id)
            const ok = rows.filter(e => e.is_achieved).length
            return <Card key={ex.exam_id} title={`${ex.exam_title} (${ex.assessment_type === 'final' ? 'Cuối kỳ' : 'Quá trình'})`}
              actions={<Badge tone="blue">{ok}/{rows.length} đạt · {(100 * ok / rows.length).toFixed(2)}%</Badge>}>
              <div className="scroll short"><table className="tbl compact"><thead><tr><th>TT</th><th>MSSV</th><th>Điểm câu hỏi</th><th>Tối đa</th><th>%</th><th /></tr></thead>
                <tbody>{rows.map((e, i) => <tr key={e.student_code}><td>{i + 1}</td><td>{e.student_code}</td><td>{Number(e.score_earned).toFixed(2)}</td><td>{Number(e.score_max).toFixed(2)}</td>
                  <td>{e.score_pct}</td><td className={e.is_achieved ? 'ok-t' : 'bad-t'}>{e.is_achieved ? '✓' : '✗'}</td></tr>)}</tbody></table></div>
            </Card>
          })}
        </div>
        <Card title="Câu hỏi đo CLO này (sắp theo DI tăng dần – câu kém lên đầu)">
          <table className="tbl compact"><thead><tr><th>Bài KT</th><th>Câu</th><th>Nội dung</th><th>Trọng số</th><th>p</th><th>DI</th><th>Phân loại</th></tr></thead>
            <tbody>{data.questions.map(q => <tr key={`${q.exam_title}-${q.question_id}`}><td>{q.exam_title}</td><td>{q.order_index}</td><td className="clip">{q.content}</td><td>{q.weight}</td>
              <td>{q.p_value}</td><td className={`num-c ${diClass(q.di_value)}`}>{q.di_value}</td><td>{q.classification}</td></tr>)}</tbody></table>
        </Card>
        <div className="grid2">
          <Field label="Đánh giá kết quả của số liệu tổng hợp"><textarea rows={4} value={n.analysis} onChange={e => setN({ ...n, analysis: e.target.value })} /></Field>
          <Field label="Những hành động cải tiến"><textarea rows={4} value={n.improvement} onChange={e => setN({ ...n, improvement: e.target.value })} /></Field>
        </div>
        <div className="row"><span className="grow" /><ActionButton className="btn primary" okMsg="Đã lưu nhận xét (sẽ xuất vào BM6b)"
          onRun={() => api.put(`/api/class-sections/${cs}/clo-results/${clo.clo_id}`, n)}>Lưu nhận xét</ActionButton></div>
      </>}
    </Modal>
  )
}

function PlanForm({ clo, semester_id, onClose, onSaved }) {
  const p = clo.plan || {}
  const [f, setF] = useState({ assessments_text: p.assessments_text || '', evidence_type: p.evidence_type || 'final', method: p.method || 'Bài KT trắc nghiệm',
    cycle: p.cycle || '1 lần/HK', pass_threshold_pct: p.pass_threshold_pct ?? 60, target_pct: p.target_pct ?? 70 })
  const set = k => e => setF({ ...f, [k]: e.target.value })
  return (
    <Modal title={`Kế hoạch đánh giá ${clo.clo_code} (BM6a)`} onClose={onClose}>
      <Field label="Các bài KT có CĐR"><input value={f.assessments_text} onChange={set('assessments_text')} /></Field>
      <Field label="Bài KT lấy minh chứng"><select value={f.evidence_type} onChange={set('evidence_type')}>
        {Object.entries(EVID).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
      <div className="grid2">
        <Field label="Phương pháp"><input value={f.method} onChange={set('method')} /></Field>
        <Field label="Chu kỳ"><input value={f.cycle} onChange={set('cycle')} /></Field>
        <Field label="Ngưỡng đạt của SV (% điểm tối đa)"><input type="number" min="0" max="100" value={f.pass_threshold_pct} onChange={set('pass_threshold_pct')} /></Field>
        <Field label="Chỉ tiêu mong muốn (% SV đạt)"><input type="number" min="0" max="100" value={f.target_pct} onChange={set('target_pct')} /></Field>
      </div>
      <p className="muted">Khi lưu, hệ thống tự phân tích lại các bài KT đã phân tích của môn trong học kỳ để kết quả CLO – PI – PLO áp dụng ngưỡng/chỉ tiêu mới.</p>
      <div className="row"><span className="grow" /><ActionButton className="btn primary"
        disabled={!(Number(f.pass_threshold_pct) >= 0 && Number(f.pass_threshold_pct) <= 100 && Number(f.target_pct) >= 0 && Number(f.target_pct) <= 100) || !f.method.trim() || !f.cycle.trim()}
        okMsg={r => `Đã lưu kế hoạch${r?.reanalyzed_exams ? ` · phân tích lại ${r.reanalyzed_exams} bài KT` : ''}`}
        onRun={async () => { const r = await api.put('/api/clo-plans', { ...f, clo_id: clo.id, semester_id, pass_threshold_pct: Number(f.pass_threshold_pct), target_pct: Number(f.target_pct) }); onSaved(); return r }}>Lưu</ActionButton></div>
    </Modal>
  )
}
