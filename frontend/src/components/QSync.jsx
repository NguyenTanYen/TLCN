// Đồng bộ ngân hàng câu hỏi hai chiều với Moodle: so sánh từng câu (QB-n ⇄ idnumber trên Moodle), đẩy lên / kéo về.
import { useEffect, useState } from 'react'
import { api } from '../api'
import { ActionButton, Badge, Field, Loading, Modal } from './ui'
import { useApi } from '../hooks'

const ST = {
  synced: ['Đã đồng bộ', 'green'], only_system: ['Chỉ có trên hệ thống', 'blue'], system_newer: ['Hệ thống mới hơn', 'blue'],
  moodle_newer: ['Moodle mới hơn', 'amber'], conflict: ['Hai bên khác nhau', 'red'], only_moodle: ['Soạn trên Moodle', 'amber'],
}

export default function QSync({ courseId, onClose, onDone }) {
  const t = useApi(`/api/courses/${courseId}/moodle-sync/targets`)
  const [mc, setMc] = useState(null)
  useEffect(() => { if (t.data?.targets.length && !mc) setMc(t.data.targets[0].moodle_course_id) }, [t.data])  // eslint-disable-line
  const cmp = useApi(mc ? `/api/courses/${courseId}/moodle-sync?moodle_course_id=${mc}` : null)
  const [act, setAct] = useState({})      // khóa -> 'push' | 'pull' | null
  const [flt, setFlt] = useState('todo')
  useEffect(() => { if (cmp.data) setAct(Object.fromEntries(cmp.data.rows.map(r => [key(r), r.action]))) }, [cmp.data])
  const key = r => r.question_id ? `q${r.question_id}` : `m${r.moodle_questionid}`
  const rows = (cmp.data?.rows || []).filter(r => flt === 'all' || r.state !== 'synced')
  const n = k => Object.values(act).filter(v => v === k).length
  const apply = async () => {
    const all = cmp.data.rows
    const body = { moodle_course_id: mc, push: all.filter(r => act[key(r)] === 'push' && r.question_id).map(r => r.question_id),
      pull: all.filter(r => act[key(r)] === 'pull' && r.question_id).map(r => r.question_id),
      import_new: all.filter(r => act[key(r)] === 'pull' && !r.question_id).map(r => r.moodle_questionid) }
    const r = await api.post(`/api/courses/${courseId}/moodle-sync`, body)
    cmp.reload(); onDone?.(); return r
  }
  return <Modal wide title="Đồng bộ ngân hàng câu hỏi hai chiều với Moodle" onClose={onClose}>
    <Loading {...t} />
    {t.data && !t.data.targets.length && <div className="alert amber">Môn chưa có lớp học phần nào (của bạn) gắn khóa học Moodle. Gắn lớp với Moodle ở trang lớp hoặc "Cập nhật lớp từ Moodle".</div>}
    {t.data && !t.data.ws_configured && <div className="alert amber">Chưa cấu hình Web Service Moodle – chỉ xem được so sánh, chưa đẩy/kéo được.</div>}
    {t.data?.targets.length > 0 && <div className="row gap wrap">
      <Field label="Khóa học Moodle"><select value={mc || ''} onChange={e => setMc(Number(e.target.value))}>
        {t.data.targets.map(x => <option key={x.moodle_course_id} value={x.moodle_course_id}>#{x.moodle_course_id} – lớp {x.sections}</option>)}</select></Field>
      <Field label="Hiển thị"><select value={flt} onChange={e => setFlt(e.target.value)}><option value="todo">Câu cần đồng bộ</option><option value="all">Tất cả</option></select></Field>
      {cmp.data && <div className="row gap wrap">{Object.entries(cmp.data.summary).filter(([, v]) => v).map(([k, v]) => <Badge key={k} tone={ST[k][1]}>{ST[k][0]}: {v}</Badge>)}</div>}
    </div>}
    <Loading {...cmp} />
    {cmp.data && <>
      <div className="scroll tall mt"><table className="tbl compact"><thead><tr><th>Câu (hệ thống)</th><th>Trên Moodle</th><th>Trạng thái</th><th>Hành động</th></tr></thead>
        <tbody>{rows.map(r => <tr key={key(r)}>
          <td className="wrap-cell">{r.question_id ? <><b>QB-{r.question_id}</b> {r.content}{r.is_cancelled && <Badge>Đã Hủy</Badge>}</> : <span className="muted">—</span>}</td>
          <td className="wrap-cell small">{r.moodle_questionid ? <>#{r.moodle_questionid} (phiên bản {r.moodle_version}){r.moodle_content !== r.content ? <div>{r.moodle_content}</div> : null}</> : <span className="muted">chưa có</span>}</td>
          <td><Badge tone={ST[r.state][1]}>{ST[r.state][0]}</Badge>{r.note && <div className="small muted">{r.note}</div>}</td>
          <td>{r.state === 'synced' ? '—' : <select value={act[key(r)] || ''} onChange={e => setAct({ ...act, [key(r)]: e.target.value || null })}>
            <option value="">Bỏ qua</option>
            {r.question_id && <option value="push">⇪ Đẩy lên Moodle{r.moodle_questionid ? ' (phiên bản mới)' : ''}</option>}
            {r.moodle_questionid && (!r.note || r.state === 'conflict') && <option value="pull">⇩ Lấy về hệ thống{r.question_id ? '' : ' (câu mới, gán CLO sau)'}</option>}
          </select>}</td></tr>)}</tbody></table></div>
      {!rows.length && <p className="ok-t">Ngân hàng câu hỏi của môn và khóa học Moodle đã khớp nhau.</p>}
      <div className="row gap mt"><span className="muted small">Đẩy lên: {n('push')} câu · Lấy về: {n('pull')} câu. Moodle lưu bản cũ thành phiên bản trước – bài làm đã có không bị ảnh hưởng.</span><span className="grow" />
        <ActionButton className="btn primary" disabled={!n('push') && !n('pull')} okMsg={r => `Đã đẩy ${r.pushed.length} câu, cập nhật ${r.updated.length}, nhập mới ${r.created.length} câu từ Moodle`} onRun={apply}>Đồng bộ</ActionButton></div>
    </>}
  </Modal>
}
