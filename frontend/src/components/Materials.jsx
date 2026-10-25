// Học liệu của học phần (giáo trình, slide, tài liệu tham khảo) – nguồn để gợi ý SV cần đọc đúng trang/slide nào (RAG theo từng học phần)
import { useRef, useState } from 'react'
import { api } from '../api'
import { Badge, Card, Field, Loading } from './ui'
import { useApi } from '../hooks'

const TYPES = { slide: 'Slide bài giảng', textbook: 'Giáo trình', reference: 'Tài liệu tham khảo', other: 'Khác' }

export default function Materials({ courseId, outlines = [] }) {
  const list = useApi(`/api/courses/${courseId}/materials`)
  const file = useRef(null)
  const [form, setForm] = useState({ title: '', material_type: 'slide', outline_id: '' })
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [q, setQ] = useState('')
  const [hits, setHits] = useState(null)
  const set = k => e => setForm({ ...form, [k]: e.target.value })

  const upload = async () => {
    const f = file.current?.files?.[0]
    if (!f) { setMsg({ err: true, t: 'Chọn một tệp PDF, PPTX, DOCX, TXT hoặc MD trước.' }); return }
    setBusy(true); setMsg(null)
    try {
      const r = await api.upload(`/api/courses/${courseId}/materials`, f, form)
      setMsg({ t: `Đã lập chỉ mục ${r.n_pages} trang/slide.` })
      file.current.value = ''; setForm({ ...form, title: '' }); list.reload()
    } catch (e) { setMsg({ err: true, t: e.message }) } finally { setBusy(false) }
  }
  const remove = async m => {
    if (!window.confirm(`Xóa học liệu "${m.title}"? Các gợi ý đọc đã tạo từ tài liệu này sẽ mất.`)) return
    try { await api.del(`/api/materials/${m.id}`); list.reload() } catch (e) { setMsg({ err: true, t: e.message }) }
  }
  const syncMoodle = async () => {
    setBusy(true); setMsg(null)
    try {
      const r = await api.post(`/api/courses/${courseId}/materials/sync-moodle`, {})
      setMsg({ err: r.errors.length > 0, t: `Moodle: thêm ${r.added}, cập nhật ${r.updated}, bỏ qua ${r.skipped}${r.errors.length ? ` · lỗi: ${r.errors.join('; ')}` : ''}` }); list.reload()
    } catch (e) { setMsg({ err: true, t: e.message }) } finally { setBusy(false) }
  }
  const pushMoodle = async m => {
    try { const r = await api.post(`/api/materials/${m.id}/push-moodle`, {}); setMsg({ t: r.created ? `Đã đưa "${m.title}" lên khóa học Moodle.` : 'Tệp này đã có trên Moodle.' }); list.reload() } catch (e) { setMsg({ err: true, t: e.message }) }
  }
  const search = async () => {
    if (q.trim().length < 2) return
    try { setHits((await api.get(`/api/courses/${courseId}/materials/search?q=${encodeURIComponent(q)}&k=5`)).hits) } catch (e) { setMsg({ err: true, t: e.message }) }
  }

  const ms = list.data || []
  return <>
    <Card title="Học liệu của học phần">
      <p className="muted">Tải giáo trình, slide bài giảng, tài liệu tham khảo của <b>môn này</b>. Khi phân tích bài kiểm tra, mỗi sinh viên làm sai câu nào sẽ được gợi ý
        <b> đọc đúng trang/slide nào</b> – chỉ lấy từ học liệu của môn này, không lấy từ môn khác.</p>
      <div className="grid2">
        <Field label="Tệp (PDF, PPTX, DOCX, TXT, MD – tối đa 60 MB)"><input type="file" ref={file} accept=".pdf,.pptx,.docx,.txt,.md" /></Field>
        <Field label="Tên hiển thị" hint="Để trống = lấy tên tệp"><input value={form.title} onChange={set('title')} placeholder="Slide chương 3 – Trigger" /></Field>
        <Field label="Loại"><select value={form.material_type} onChange={set('material_type')}>{Object.entries(TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        <Field label="Thuộc chương" hint="Tùy chọn – giúp ưu tiên đúng chương khi gợi ý"><select value={form.outline_id} onChange={set('outline_id')}>
          <option value="">— không gắn chương —</option>{outlines.map(o => <option key={o.id} value={o.id}>Chương {o.chapter_number}. {o.chapter_name}</option>)}</select></Field>
      </div>
      <div className="row gap wrap"><button className="btn primary" disabled={busy} onClick={upload}>{busy ? 'Đang đọc và lập chỉ mục…' : '⭱ Tải lên và lập chỉ mục'}</button>
        <button className="btn" disabled={busy} onClick={syncMoodle} title="Lấy các tệp PDF/PPTX/DOCX đã có trong khóa học Moodle của môn về lập chỉ mục">⭳ Lấy từ khóa học Moodle</button>
        {msg && <span className={msg.err ? 'bad' : 'good'}>{msg.t}</span>}</div>
    </Card>
    <Card title={`Danh sách học liệu (${ms.length})`}>
      <Loading {...list} />
      {ms.length === 0 && !list.loading ? <p className="muted">Chưa có học liệu. Tải tệp ở trên để bắt đầu.</p> :
        <table className="tbl"><thead><tr><th>Tên</th><th>Loại</th><th>Chương</th><th className="num-c">Trang/slide</th><th>Nguồn</th><th /></tr></thead>
          <tbody>{ms.map(m => <tr key={m.id}><td><b>{m.title}</b><div className="muted small">{m.file_name}</div></td><td>{TYPES[m.material_type]}</td>
            <td>{m.chapter || '—'}</td><td className="num-c">{m.n_pages}{m.n_vlm > 0 && <Badge tone="blue" title="Có trang do mô hình thị giác (VLM) mô tả"> VLM {m.n_vlm}</Badge>}</td>
            <td>{m.source === 'moodle' ? 'Từ Moodle' : m.moodle_cmid ? 'Đã đưa lên Moodle' : 'Tải lên'}</td>
            <td><a className="btn sm ghost" href={`/api/materials/${m.id}/file`} onClick={async e => { e.preventDefault(); const { blob, name } = await api.blob(`/api/materials/${m.id}/file`, m.file_name); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click() }}>Tải về</a>
              {m.source !== 'moodle' && !m.moodle_cmid && <button className="btn sm ghost" onClick={() => pushMoodle(m)} title="Đưa tệp lên khóa học Moodle thành hoạt động Tệp">Đưa lên Moodle</button>}
              <button className="btn sm ghost" onClick={() => remove(m)}>Xóa</button></td></tr>)}</tbody></table>}
    </Card>
    <Card title="Thử gợi ý: gõ câu hỏi hoặc thuật ngữ → tìm trang/slide cần đọc">
      <div className="row gap"><input style={{ flex: 1 }} value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && search()}
        placeholder="Ví dụ: hiện tượng dirty read là gì" /><button className="btn" onClick={search}>Tìm</button></div>
      {hits && (hits.length === 0 ? <div className="alert amber mt">Không có đoạn nào của học liệu môn này đủ liên quan.</div> :
        <ol className="path mt">{hits.map(h => <li key={h.chunk_id}><div className="row gap wrap"><b>{h.material}</b><Badge tone="green">{h.unit} {h.page}</Badge>
          <span className="muted">{h.heading}</span><span className="muted small">độ khớp {Math.round(h.score * 100)}%</span></div><div className="muted small">{h.snippet}</div></li>)}</ol>)}
    </Card>
  </>
}
