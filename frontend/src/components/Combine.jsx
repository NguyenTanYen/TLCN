// Gộp 2, 3… bài kiểm tra (cùng môn, có thể khác lớp) để đánh giá CĐR môn học (CLO) và CĐR CTĐT (PLO/PI); chọn bài làm minh chứng BM6.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtPct } from '../api'
import { Achieved, ActionButton, Badge, Card, Loading } from './ui'
import { useApi } from '../hooks'

const TYPE = { online: 'Moodle', paper: 'Giấy', manual: 'Nhập điểm' }
const short = (t = '', n = 24) => (t.length > n ? t.slice(0, n - 1).trimEnd() + '…' : t)

export default function Combine({ courseId, sectionId }) {
  const ex = useApi(`/api/courses/${courseId}/analyzed-exams`)
  const list = (ex.data || []).filter(e => !sectionId || e.class_section_id === sectionId)
  const [sel, setSel] = useState([])
  const [mode, setMode] = useState('merge')
  const [res, setRes] = useState(null)
  const [showStud, setShowStud] = useState(false)
  useEffect(() => { if (ex.data && !sel.length) setSel(list.filter(e => e.counts_for_clo && !e.parent_exam_id).map(e => e.id).slice(0, 3)) }, [ex.data])  // eslint-disable-line
  const sections = [...new Map(list.map(e => [e.class_section_id, `${e.section_code} (${e.semester})`])).entries()]
  const toggle = id => setSel(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id])
  return <>
    <Card title="1. Chọn các bài kiểm tra cần gộp" actions={<span className="muted small">Chỉ hiện bài đã phân tích của lớp bạn phụ trách</span>}>
      <Loading {...ex} />
      {sections.map(([cs, label]) => <div key={cs} className="mb">
        <div className="small"><b>Lớp {label}</b></div>
        <table className="tbl compact"><thead><tr><th style={{ width: 36 }} /><th>Bài kiểm tra</th><th>Hình thức</th><th>Loại</th><th>Ngày</th><th className="num-c">SV</th>
          <th title="Bài được gộp vào kết quả CLO của lớp (BM6, PI, PLO)">Minh chứng BM6</th></tr></thead>
          <tbody>{list.filter(e => e.class_section_id === cs).map(e => <tr key={e.id} className={sel.includes(e.id) ? 'sel' : ''}>
            <td><input type="checkbox" aria-label={`Chọn ${e.exam_title}`} checked={sel.includes(e.id)} onChange={() => toggle(e.id)} /></td>
            <td><Link to={`/exams/${e.id}`}>{e.exam_title}</Link>{e.parent_exam_id && <Badge tone="amber">Phụ đạo</Badge>}</td>
            <td>{TYPE[e.exam_type]}</td><td>{e.assessment_type === 'final' ? 'Cuối kỳ' : 'Quá trình'}</td><td>{e.exam_date || '—'}</td><td className="num-c">{e.n_students}</td>
            <td><ActionButton className={`btn sm ${e.counts_for_clo ? '' : 'ghost'}`} okMsg={r => r.counts_for_clo ? 'Đã đưa vào minh chứng – BM6 của lớp được tính lại' : 'Đã bỏ khỏi minh chứng – BM6 của lớp được tính lại'}
              onRun={async () => { const r = await api.patch(`/api/exams/${e.id}/evidence`, { counts_for_clo: !e.counts_for_clo }); ex.reload(); return r }}>
              {e.counts_for_clo ? '✓ Có gộp' : 'Không gộp'}</ActionButton></td></tr>)}</tbody></table>
      </div>)}
      {!list.length && ex.data && <p className="muted">Chưa có bài kiểm tra nào đã phân tích.</p>}
      <div className="row gap wrap mt">
        <span>Đã chọn <b>{sel.length}</b> bài</span>
        <select value={mode} onChange={e => setMode(e.target.value)} aria-label="Cách gộp">
          <option value="merge">Cộng điểm các câu đo CLO của từng SV trên mọi bài (mỗi SV đếm 1 lần)</option>
          <option value="cumulative">Cộng dồn lượt đánh giá qua các bài (BM6d – mỗi bài một lượt)</option>
        </select>
        <span className="grow" />
        <ActionButton className="btn primary" disabled={!sel.length} onRun={async () => setRes(await api.post('/api/combined-analysis', { exam_ids: sel, mode }))}>Phân tích gộp</ActionButton>
        <ActionButton className="btn" disabled={!sel.length} onRun={() => api.download(`/api/combined-analysis.xlsx?ids=${sel.join(',')}&mode=${mode}`, 'DanhGiaGop.xlsx')}>⬇ Xuất Excel</ActionButton>
      </div>
    </Card>
    {res && <>
      <Card title="2. Mức đạt CĐR môn học (CLO)">
        <table className="tbl"><thead><tr><th>CLO</th><th>Nội dung</th><th className="num-c">Ngưỡng đạt</th><th className="num-c">{mode === 'merge' ? 'SV đánh giá' : 'Lượt đánh giá'}</th>
          <th className="num-c">Đạt</th><th className="num-c">Tỷ lệ đạt</th><th className="num-c">Chỉ tiêu</th><th>Kết luận</th><th>Theo từng bài (đạt/đánh giá)</th></tr></thead>
          <tbody>{res.clos.map(c => <tr key={c.clo_id}><td><b>{c.clo_code}</b></td><td className="clip" title={c.description}>{c.description}</td><td className="num-c">{c.threshold}%</td>
            <td className="num-c">{c.n_evaluated}</td><td className="num-c">{c.n_achieved}</td><td className="num-c">{fmtPct(c.achieved_pct)}</td><td className="num-c">{c.target}%</td>
            <td><Achieved ok={c.is_achieved} /></td>
            <td className="small">{c.by_exam.filter(b => b.n).map(b => `${short(res.exams.find(e => e.id === b.exam_id)?.exam_title)}: ${b.ok}/${b.n}`).join(' · ') || '—'}</td></tr>)}</tbody></table>
      </Card>
      {res.programs.map(p => <Card key={p.program_id} title={`3. Đóng góp cho CĐR CTĐT – ${p.code} ${p.name}`}>
        <table className="tbl"><thead><tr><th>PLO</th><th>Nội dung</th><th>CLO đóng góp</th><th className="num-c">Lượt đánh giá</th><th className="num-c">Đạt</th>
          <th className="num-c">Tỷ lệ</th><th className="num-c">Chỉ tiêu</th><th>Kết luận</th><th>PI học phần đáp ứng</th></tr></thead>
          <tbody>{p.plos.map(x => <tr key={x.plo_id}><td><b>{x.plo_code}</b></td><td className="clip" title={x.description}>{x.description}</td><td>{x.clos.join(', ')}</td>
            <td className="num-c">{x.n_evaluated}</td><td className="num-c">{x.n_achieved}</td><td className="num-c">{fmtPct(x.achieved_pct)}</td><td className="num-c">{x.target}%</td>
            <td><Achieved ok={x.is_achieved} /></td><td className="small">{x.pis.map(pi => `${pi.pi_code}${pi.level ? ` (${pi.level})` : ''}`).join(', ') || '—'}</td></tr>)}</tbody></table>
      </Card>)}
      {!res.programs.length && <div className="alert amber">CLO của môn chưa ánh xạ PLO nào – chưa tính được đóng góp cho CĐR CTĐT.</div>}
      <Card title={`4. Từng sinh viên (${res.students.length})`} actions={<button className="btn sm" onClick={() => setShowStud(x => !x)}>{showStud ? 'Thu gọn' : 'Xem bảng'}</button>}>
        {showStud ? <div className="scroll tall"><table className="tbl compact"><thead><tr><th>MSSV</th><th>Họ tên</th>
          {res.exams.map(e => <th key={e.id} title={`${e.exam_title} – ${e.section_code}`}>{short(e.exam_title)}</th>)}{res.clos.map(c => <th key={c.clo_id}>{c.clo_code}</th>)}<th>CLO đạt</th></tr></thead>
          <tbody>{res.students.map(st => <tr key={st.student_id}><td>{st.student_code}</td><td>{st.full_name}</td>
            {res.exams.map(e => <td key={e.id} className="num-c">{st.scores[e.id] ?? '—'}</td>)}
            {res.clos.map(c => { const v = st.clos[c.clo_code]; return <td key={c.clo_id} className={v ? (v.ok ? 'ok-t' : 'bad-t') : ''}>{v ? `${v.pct}%` : '—'}</td> })}
            <td>{st.n_ok}/{st.n_clo}</td></tr>)}</tbody></table></div>
          : <p className="muted small">{res.students.filter(x => x.n_ok < x.n_clo).length} SV chưa đạt ít nhất một CLO – xem bảng hoặc mở trang Phụ đạo của lớp để tạo bài phụ đạo.</p>}
      </Card>
    </>}
  </>
}
