import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { ActionButton, Badge, Card, Loading, useToast } from './ui'
import { useApi } from '../hooks'
import { openMoodle } from '../moodle'

// Thẻ "Học liệu" của lớp học phần (RAG): tệp PDF trong khóa học Moodle của lớp được tự lấy làm học liệu, nạp ở nền;
// khi SV làm sai câu hỏi, hệ thống gợi ý các trang học liệu nên đọc lại. GV bỏ chọn tệp không muốn dùng, sửa tên / loại,
// nạp lại; Bộ môn chỉ xem.
const STATUS = {
  pending: ['Chờ nạp', 'gray'], indexing: ['Đang nạp…', 'blue'], ready: ['Đã nạp', 'green'], failed: ['Lỗi', 'red'],
  excluded: ['Đã bỏ chọn', 'gray'], missing: ['Không còn trên Moodle', 'amber'],
}
const TYPE_VI = { slide: 'Slide bài giảng', reference: 'Tài liệu tham khảo' }
const BUSY = ['pending', 'indexing']
const POLL_MS = 4000

const fmtSize = b => (b == null ? '' : b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`)
const fmtTime = t => (t ? new Date(t).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' }) : '')

// Mở tệp trên Moodle (đăng nhập bằng tài khoản đang dùng); page: mở đúng trang của PDF
function openFile(url, page) {
  const at = (url || '').indexOf('/pluginfile.php/')
  if (at < 0) return
  openMoodle(url.slice(at).split('#')[0] + (page ? `#page=${page}` : ''))
}

export default function SectionMaterials({ cs, canEdit }) {
  const id = cs.id
  const toast = useToast()
  const list = useApi(`/api/class-sections/${id}/materials`)
  const [syncing, setSyncing] = useState(false)
  const synced = useRef(null)

  // GV mở thẻ → đồng bộ với khóa học Moodle (tệp mới / đổi / bị xóa) rồi nạp ở nền các tệp chờ
  useEffect(() => {
    if (!canEdit || !cs.moodle_course_id || synced.current === id) return
    synced.current = id
    setSyncing(true)
    api.post(`/api/class-sections/${id}/materials/sync`).then(() => list.reload())
      .catch(e => toast(`Không đồng bộ được học liệu từ Moodle: ${e.message}`, 'red')).finally(() => setSyncing(false))
  }, [id, canEdit, cs.moodle_course_id]) // eslint-disable-line react-hooks/exhaustive-deps

  const mats = list.data?.materials || []
  const busy = mats.some(m => BUSY.includes(m.status))
  useEffect(() => {                                  // đang nạp: tải lại định kỳ để thấy trạng thái mới
    if (!busy) return
    const t = setInterval(() => list.reload(), POLL_MS)
    return () => clearInterval(t)
  }, [busy]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!cs.moodle_course_id) return <Card><div className="empty"><p>Lớp chưa gắn với khóa học Moodle.</p>
    <p className="muted small">Học liệu được lấy từ các tệp PDF trong khóa học Moodle của lớp – hãy tạo hoặc gắn khóa học Moodle ở đầu trang.</p></div></Card>

  const files = list.data?.moodle_files || []
  const fileOf = m => files.find(f => f.content_hash === m.content_hash)
  const others = files.filter(f => !f.material_id)
  const shown = mats.filter(m => m.status !== 'excluded')
  const excluded = mats.filter(m => m.status === 'excluded')

  const patch = async (m, body) => { await api.patch(`/api/class-sections/${id}/materials/${m.id}`, body); list.reload() }
  const rename = async m => {
    const t = window.prompt('Tên hiển thị của học liệu (SV thấy tên này trong gợi ý đọc):', m.title)
    if (t === null || !t.trim() || t.trim() === m.title) return
    try { await patch(m, { title: t.trim() }); toast('Đã đổi tên học liệu') } catch (e) { toast(e.message, 'red') }
  }
  const pick = async (f, type = 'slide') => {
    await api.post(`/api/class-sections/${id}/materials/moodle`, { cmid: f.cmid, content_hash: f.content_hash, material_type: type })
    list.reload()
  }

  return <>
    <Card title="Học liệu của lớp" actions={canEdit && <ActionButton className="btn sm" disabled={syncing}
      title="Lấy lại danh sách tệp từ khóa học Moodle (tệp mới, tệp đã thay, tệp đã xóa) và nạp các tệp chờ"
      okMsg={r => `Đã đồng bộ: ${r.added.length} tệp mới, ${r.replaced.length} tệp thay đổi, ${r.missing.length} tệp không còn trên Moodle`}
      onRun={async () => { const r = await api.post(`/api/class-sections/${id}/materials/sync`); list.reload(); return r }}>
      {syncing ? 'Đang đồng bộ…' : 'Đồng bộ từ Moodle'}</ActionButton>}>
      <p className="muted small mt0">Các tệp PDF sinh viên xem được trong khóa học Moodle #{cs.moodle_course_id} được tự lấy làm học liệu.
        Khi SV làm sai một câu, trang kết quả trên Moodle gợi ý các <b>trang</b> học liệu nên đọc lại.
        {canEdit && ' Bỏ chọn tệp không phải học liệu (đề cũ, đáp án…) – lần đồng bộ sau không lấy lại.'}</p>
      <Loading {...list} />
      {list.data && !shown.length ? <div className="empty"><p>Chưa có học liệu.</p>
        <p className="muted small">Tải slide / giáo trình dạng PDF lên khóa học Moodle của lớp{canEdit ? ' rồi bấm "Đồng bộ từ Moodle"' : ''}.</p></div>
      : shown.length > 0 && <table className="tbl">
        <thead><tr><th>Học liệu</th><th>Loại</th><th>Trạng thái</th><th className="num-c">Số trang</th>{canEdit && <th />}</tr></thead>
        <tbody>{shown.map(m => { const [label, tone] = STATUS[m.status] || [m.status, 'gray']
          return <tr key={m.id}>
            <td><b>{m.title}</b>{canEdit && <button className="btn sm ghost" title="Đổi tên hiển thị" aria-label={`Đổi tên ${m.title}`} onClick={() => rename(m)}>✎</button>}
              <div className="muted small">{m.moodle_file_url ? <a href="#" onClick={e => { e.preventDefault(); openFile(m.moodle_file_url) }}>{m.file_name} ↗</a> : m.file_name}
                {m.file_size ? ` · ${fmtSize(m.file_size)}` : ''}{fileOf(m)?.section ? ` · ${fileOf(m).section}` : ''}</div></td>
            <td>{canEdit ? <select aria-label={`Loại học liệu ${m.title}`} value={m.material_type}
              onChange={e => patch(m, { material_type: e.target.value }).catch(er => toast(er.message, 'red'))}>
              {Object.entries(TYPE_VI).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select> : TYPE_VI[m.material_type]}</td>
            <td><Badge tone={tone}>{label}</Badge>
              {m.status === 'ready' && m.indexed_at && <div className="muted small">{fmtTime(m.indexed_at)}</div>}
              {m.error && <div className="small neg" title={m.error}>{m.error.length > 140 ? `${m.error.slice(0, 140)}…` : m.error}</div>}</td>
            <td className="num-c">{m.n_pages ?? '—'}</td>
            {canEdit && <td className="row gap">
              {['ready', 'failed'].includes(m.status) && m.source === 'moodle' && <ActionButton className="btn sm" title="Nạp lại (sau khi sửa tệp trên Moodle hoặc khi nạp bị lỗi)"
                okMsg="Đã xếp vào hàng đợi nạp" onRun={async () => { await api.post(`/api/class-sections/${id}/materials/${m.id}/reindex`); list.reload() }}>Nạp lại</ActionButton>}
              {m.status !== 'missing' && <ActionButton className="btn sm ghost" okMsg="Đã bỏ chọn học liệu"
                confirm={`Bỏ chọn "${m.title}"? Hệ thống sẽ không gợi ý trang của tệp này nữa (chọn lại được).`}
                onRun={async () => { await api.del(`/api/class-sections/${id}/materials/${m.id}`); list.reload() }}>Bỏ chọn</ActionButton>}</td>}
          </tr> })}</tbody>
      </table>}
    </Card>

    {(others.length > 0 || excluded.length > 0) && <Card title="Tệp khác trong khóa học Moodle">
      <table className="tbl">
        <thead><tr><th>Tệp</th><th>Hoạt động</th><th>Ghi chú</th>{canEdit && <th />}</tr></thead>
        <tbody>
          {excluded.map(m => { const f = fileOf(m)
            return <tr key={`m${m.id}`} className="dim"><td>{m.title}<div className="muted small">{m.file_name}</div></td><td>{f?.activity || '—'}</td>
              <td><Badge>Đã bỏ chọn</Badge></td>
              {canEdit && <td>{f && <ActionButton className="btn sm" okMsg="Đã chọn lại, đang nạp" onRun={() => pick(f, m.material_type)}>Chọn lại</ActionButton>}</td>}</tr> })}
          {others.map(f => <tr key={`f${f.cmid}-${f.content_hash}`}><td>{f.file_name}<div className="muted small">{fmtSize(f.file_size)}{f.section ? ` · ${f.section}` : ''}</div></td>
            <td>{f.activity}</td>
            <td className="muted small">{f.supported ? 'Chưa là học liệu' : 'Chỉ nạp được PDF – xuất PowerPoint/Word sang PDF rồi tải lên Moodle'}</td>
            {canEdit && <td>{f.supported && <ActionButton className="btn sm" okMsg="Đã chọn, đang nạp" onRun={() => pick(f)}>Chọn làm học liệu</ActionButton>}</td>}</tr>)}
        </tbody>
      </table>
    </Card>}

    {shown.some(m => m.status === 'ready') && <MaterialSearch id={id} />}
  </>
}

// Thử tìm trong học liệu đã nạp – để GV kiểm tra hệ thống tìm đúng trang trước khi SV dùng gợi ý
function MaterialSearch({ id }) {
  const [q, setQ] = useState('')
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const run = async e => {
    e.preventDefault()
    if (!q.trim()) return
    setBusy(true)
    try { setRes({ q: q.trim(), hits: await api.get(`/api/class-sections/${id}/materials/search?k=8&q=${encodeURIComponent(q.trim())}`) }) }
    catch (er) { toast(er.message, 'red') } finally { setBusy(false) }
  }
  return <Card title="Thử tìm trong học liệu">
    <form className="row gap" onSubmit={run}>
      <input style={{ flex: 1 }} value={q} onChange={e => setQ(e.target.value)} maxLength={2000} aria-label="Nội dung cần tìm"
        placeholder="Gõ câu hỏi hoặc từ khóa, ví dụ: recovery model nào cho phép phục hồi về một thời điểm" />
      <button className="btn primary" disabled={busy || !q.trim()}>{busy ? 'Đang tìm…' : 'Tìm'}</button>
    </form>
    {res && (!res.hits.length ? <p className="muted">Không tìm thấy đoạn nào khớp "{res.q}".</p>
      : <ol className="mb0">{res.hits.map(h => <li key={h.passage_id} className="mt0" style={{ marginBottom: 10 }}>
        <div><b>{h.moodle_file_url ? <a href="#" onClick={e => { e.preventDefault(); openFile(h.moodle_file_url, h.page_no) }}>{h.material_title} – trang {h.page_no} ↗</a>
          : `${h.material_title} – trang ${h.page_no}`}</b>{h.breadcrumb && <span className="muted"> · {h.breadcrumb}</span>}
          {h.kind !== 'text' && <> <Badge>{h.kind === 'table' ? 'Bảng' : 'Hình'}</Badge></>}</div>
        <div className="small prewrap">{h.snippet}</div>
      </li>)}</ol>)}
  </Card>
}
