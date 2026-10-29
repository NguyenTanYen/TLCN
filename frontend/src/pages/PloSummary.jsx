import { useState } from 'react'
import { PageHelp } from '../components/Help'
import { AttainmentChart } from '../components/ChartKit'
import { api, fmtPct } from '../api'
import { C } from '../charts'
import { Achieved, ActionButton, Card, Field, Loading, Modal, Stat } from '../components/ui'
import { useApi, useDefaultYear, useProgram } from '../hooks'
import { ProgramPicker } from '../components/ui'

export default function PloSummary() {
  const { years, year, setYear } = useDefaultYear()
  const pg = useProgram()
  const sum = useApi(year && pg.pid ? `/api/reports/programs/${pg.pid}/plo-summary?academic_year=${year}` : null)
  const [edit, setEdit] = useState(null)
  const s = sum.data
  const measured = s?.plos.filter(p => p.n_evaluated) || []
  return (
    <>
      <div className="page-h"><div><h1>Kết quả chuẩn đầu ra của chương trình đào tạo</h1><p className="muted">Kết quả từng chuẩn đầu ra chương trình (PLO) được cộng dồn từ các chỉ báo (PI) – biểu mẫu BM3c – và tổng kết toàn chương trình – biểu mẫu BM2.</p></div>
        <div className="row gap wrap">
          <ProgramPicker {...pg} />
          <Field label="Năm học"><select value={year || ''} onChange={e => setYear(e.target.value)}>{years.map(y => <option key={y}>{y}</option>)}</select></Field>
          <ActionButton className="btn" okMsg="Đã tính lại" onRun={async () => { await api.post(`/api/reports/programs/${pg.pid}/recompute`); sum.reload() }}>Tính lại</ActionButton>
          <ActionButton className="btn primary" disabled={!year} onRun={() => api.download(`/api/reports/programs/${pg.pid}/bm3.xlsx?academic_year=${year}`, 'BM2_BM3.xlsx')}>⬇ Xuất BM2/BM3 (.xlsx)</ActionButton>
          <ActionButton className="btn" disabled={!year} onRun={() => api.download(`/api/reports/programs/${pg.pid}/bm2.docx?academic_year=${year}`, `BM2_${year}.docx`)}>⬇ Xuất BM2 (.docx)</ActionButton>
        </div></div>
      <PageHelp id="plosummary"><p>Chọn chương trình đào tạo và năm học, bấm <b>Tính lại</b> để cập nhật. Bảng cho biết tỷ lệ đạt từng chuẩn đầu ra chương trình (PLO) so với chỉ tiêu. Dùng nút Xuất để tải biểu mẫu BM2, BM3.</p></PageHelp>
      <Loading {...sum} />
      {s && <>
        <div className="stats">
          <Stat label="CĐR được đo trong năm" value={`${measured.length}/${s.plos.length}`} />
          <Stat label="CĐR đạt chỉ tiêu" value={measured.filter(p => p.is_achieved).length} tone="green" />
          <Stat label="Tỷ lệ đạt toàn chương trình" value={fmtPct(s.program_result.achieved_pct)} sub={`${s.program_result.n_achieved}/${s.program_result.n_evaluated} · chỉ tiêu ${s.program_result.target_pct}%`}
            tone={s.program_result.is_achieved ? 'green' : 'red'} />
          <Stat label="Kết luận" value={s.program_result.n_evaluated ? (s.program_result.is_achieved ? 'Đạt' : 'Không đạt') : '—'} tone={s.program_result.is_achieved ? 'green' : 'red'} />
        </div>
        {measured.length > 0 && <Card title="Tỷ lệ đạt các CĐR được đo so với chỉ tiêu">
          <AttainmentChart xTitle="Chuẩn đầu ra của chương trình (PLO)" items={measured.map(p => ({ label: `CĐR ${p.plo_code}`, k: p.n_achieved, n: p.n_evaluated, target: Number(p.target_pct) }))} />
        </Card>}
        <Card title={`Kết quả đo lường các CĐR – năm học ${year}`}>
          <table className="tbl"><thead><tr><th>CĐR</th><th>Nội dung</th><th>Số KH đo</th><th>SV đạt</th><th>SV đánh giá</th><th>Tỷ lệ</th><th>Chỉ tiêu</th><th>Kết quả</th><th /></tr></thead>
            <tbody>{s.plos.map(p => <tr key={p.plo_id} className={p.n_evaluated ? '' : 'dim'}>
              <td><b>{p.plo_code}</b></td><td className="clip">{p.description}</td><td>{p.n_plans}</td><td>{p.n_achieved ?? '—'}</td><td>{p.n_evaluated ?? '—'}</td>
              <td>{fmtPct(p.achieved_pct)}</td><td>{(p.target_pct ?? p.plo_target)}%</td><td><Achieved ok={p.n_evaluated ? !!p.is_achieved : null} /></td>
              <td>{p.n_evaluated ? <button className="btn sm" onClick={() => setEdit(p)}>Nhận xét</button> : null}</td></tr>)}</tbody></table>
        </Card>
      </>}
      {edit && <Narr plo={edit} year={year} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); sum.reload() }} />}
    </>
  )
}

function Narr({ plo, year, onClose, onSaved }) {
  const [f, setF] = useState({ analysis: plo.analysis || '', improvement_actions: plo.improvement_actions || '', improvement_results: plo.improvement_results || '', evidence_tools: plo.evidence_tools || '' })
  const L = [['analysis', 'Đánh giá kết quả của số liệu tổng hợp'], ['improvement_actions', 'Những hành động cải tiến'], ['improvement_results', 'Kết quả của các cải tiến đã thực hiện'], ['evidence_tools', 'Công cụ đánh giá']]
  return <Modal title={`CĐR ${plo.plo_code} – năm học ${year}`} onClose={onClose} wide>
    <div className="alert">Tổng hợp dữ liệu: {plo.data_summary}</div>
    <div className="grid2">{L.map(([k, l]) => <Field key={k} label={l}><textarea rows={4} value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })} /></Field>)}</div>
    <div className="row"><span className="grow" /><ActionButton className="btn primary" okMsg="Đã lưu" onRun={async () => { await api.put(`/api/reports/plo-results/${plo.plo_id}/${year}`, f); onSaved() }}>Lưu</ActionButton></div>
  </Modal>
}
