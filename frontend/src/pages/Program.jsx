import { useState } from 'react'
import { api } from '../api'
import { ActionButton, Card, Field, Loading, Modal } from '../components/ui'
import { useApi } from '../hooks'

export default function Program() {
  const progs = useApi('/api/programs').data
  const pid = progs?.[0]?.id
  const prog = useApi(pid ? `/api/programs/${pid}` : null)
  const [edit, setEdit] = useState(null)
  const p = prog.data
  if (!p) return <Loading {...prog} />
  const groups = [...new Set(p.plos.map(x => x.group_no))]
  return (
    <>
      <div className="page-h"><div><h1>Chương trình đào tạo {p.name} ({p.code})</h1>
        <p className="muted">UC-06 · {p.department} · Chỉ tiêu chung: {p.target_pct}% · Danh sách CĐR (PLO), chỉ số đo lường (PI) và kế hoạch đo theo BM2 (chu kỳ 2 năm).</p></div></div>
      {groups.map(g => <Card key={g} title={`Nhóm CĐR ${g}`}>
        <table className="tbl"><thead><tr><th>CĐR</th><th>Nội dung</th><th>Chỉ tiêu</th><th>Năm đo lần 1</th><th>Năm đo lần 2</th><th>Chỉ số PI</th><th /></tr></thead>
          <tbody>{p.plos.filter(x => x.group_no === g).map(x => <tr key={x.id}>
            <td><b>{x.plo_code}</b></td><td className="wrap-cell">{x.description}</td><td>{x.target_pct}%</td>
            <td>{x.measurement_plans.find(m => m.round_no === 1)?.academic_year || '—'}</td>
            <td>{x.measurement_plans.find(m => m.round_no === 2)?.academic_year || '—'}</td>
            <td className="wrap-cell">{x.pis.length ? x.pis.map(pi => <div key={pi.id}><b>{pi.pi_code}</b>: {pi.description}</div>) : <span className="muted">Do Khoa khác quản lý / chưa khai báo</span>}</td>
            <td><button className="btn sm" onClick={() => setEdit(x)}>Sửa</button></td>
          </tr>)}</tbody></table>
      </Card>)}
      {edit && <PloForm plo={edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); prog.reload() }} />}
    </>
  )
}

function PloForm({ plo, onClose, onSaved }) {
  const [f, setF] = useState({ description: plo.description, target_pct: plo.target_pct })
  return <Modal title={`CĐR ${plo.plo_code}`} onClose={onClose}>
    <Field label="Nội dung"><textarea rows={4} value={f.description} onChange={e => setF({ ...f, description: e.target.value })} /></Field>
    <Field label="Chỉ tiêu (%)"><input type="number" value={f.target_pct} onChange={e => setF({ ...f, target_pct: e.target.value })} /></Field>
    <div className="row"><span className="grow" /><ActionButton className="btn primary" okMsg="Đã lưu"
      onRun={async () => { await api.put(`/api/plos/${plo.id}`, { description: f.description, target_pct: Number(f.target_pct) }); onSaved() }}>Lưu</ActionButton></div>
  </Modal>
}
