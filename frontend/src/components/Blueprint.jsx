// Sinh đề theo ma trận đề thi (UC-02): GV nhập số câu (hệ thống tự lập ma trận chương × mức Bloom, phủ đủ CLO)
// hoặc nhập ma trận chi tiết; hệ thống báo ô/CLO/mức thiếu câu. Kết quả đổ vào danh sách chọn để GV chỉnh tay.
import { useMemo, useState } from 'react'
import { api } from '../api'
import { ActionButton } from './ui'
import { useApi } from '../hooks'

const PRESET_VI = { balanced: 'Cân bằng (20/30/30/15/5)', basic: 'Cơ bản (35/40/20/5)', advanced: 'Nâng cao (10/20/35/25/10)', custom: 'Tùy chỉnh' }
const BLOOM_SHORT = ['', 'Nhớ', 'Hiểu', 'Vận dụng', 'Phân tích', 'Đánh giá', 'Sáng tạo']

export function MatrixTable({ chapters, cells, blooms, value, render }) {
  // bảng chương × mức Bloom; render(o, b) trả nội dung ô
  const usedBlooms = blooms.filter(b => cells.some(c => c.bloom_level_id === b) || (value && Object.keys(value).some(k => k.endsWith(`:${b}`))))
  return <div className="scroll"><table className="tbl compact matrix">
    <thead><tr><th>Chương / Mức Bloom</th>{usedBlooms.map(b => <th key={b} className="num-c">{BLOOM_SHORT[b]}</th>)}<th className="num-c">Cộng</th></tr></thead>
    <tbody>{chapters.map(c => <tr key={c.outline_id ?? 'x'}>
      <td>{c.outline_id ? `Chương ${c.chapter_number}` : 'Chưa gán chương'}{c.chapter_name && <small className="muted"> – {c.chapter_name}</small>}</td>
      {usedBlooms.map(b => <td key={b} className="num-c">{render(c.outline_id ?? null, b)}</td>)}
      <td className="num-c"><b>{render(c.outline_id ?? null, 'sum')}</b></td></tr>)}</tbody>
  </table></div>
}

export default function Blueprint({ cs, maxScore, picked, onApply }) {
  const [n, setN] = useState(20)
  const [scope, setScope] = useState([])            // outline_id đã chọn; rỗng = mọi chương
  const [preset, setPreset] = useState('balanced')
  const [mix, setMix] = useState({ 1: 20, 2: 30, 3: 30, 4: 15, 5: 5, 6: 0 })
  const [useMatrix, setUseMatrix] = useState(false)
  const [mat, setMat] = useState({})                // "outline:bloom" -> số câu
  const [keepPicked, setKeepPicked] = useState(false)
  const [res, setRes] = useState(null)
  const [seed, setSeed] = useState(1)
  const pool = useApi(`/api/class-sections/${cs.id}/exam-blueprint/pool${scope.length ? `?outline_ids=${scope.join(',')}` : ''}`)
  const allCh = useApi(`/api/class-sections/${cs.id}/exam-blueprint/pool`).data?.chapters || []
  const p = pool.data
  const avail = useMemo(() => Object.fromEntries((p?.cells || []).map(c => [`${c.outline_id}:${c.bloom_level_id}`, c.available])), [p])
  const matTotal = Object.values(mat).reduce((a, b) => a + (Number(b) || 0), 0)

  const run = async (nextSeed = seed) => {
    const body = { total_points: Number(maxScore) || 10, outline_ids: scope, bloom_preset: preset, seed: nextSeed,
      bloom_mix: preset === 'custom' ? mix : {}, fixed_ids: keepPicked ? Object.keys(picked).map(Number) : [] }
    if (useMatrix) body.matrix = Object.entries(mat).filter(([, v]) => Number(v) > 0)
      .map(([k, v]) => { const [o, b] = k.split(':'); return { outline_id: o === 'null' ? null : Number(o), bloom_level_id: Number(b), n: Number(v) } })
    else body.n_questions = Number(n)
    const r = await api.post(`/api/class-sections/${cs.id}/exam-blueprint`, body)
    setRes(r)
    if (r.items.length) onApply(r.items)
    return r
  }
  const toMatrix = () => {   // chép ma trận vừa sinh để GV chỉnh từng ô
    setMat(Object.fromEntries((res?.matrix || []).filter(m => m.target).map(m => [`${m.outline_id}:${m.bloom_level_id}`, m.target]))); setUseMatrix(true)
  }
  const chapters = (p?.chapters || [])
  const blooms = [1, 2, 3, 4, 5, 6]
  const resMap = Object.fromEntries((res?.matrix || []).map(m => [`${m.outline_id}:${m.bloom_level_id}`, m]))

  return (
    <div className="blueprint">
      <div className="row gap wrap">
        <label className="field"><span>Số câu</span>
          <input className="num" type="number" min="1" max="200" value={n} disabled={useMatrix} onChange={e => setN(e.target.value)} /></label>
        <label className="field"><span>Phân bố mức độ (Bloom)</span>
          <select value={preset} disabled={useMatrix} onChange={e => setPreset(e.target.value)}>
            {Object.entries(PRESET_VI).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        {preset === 'custom' && !useMatrix && <div className="row gap wrap">{blooms.map(b => <label key={b} className="field"><span>{BLOOM_SHORT[b]} %</span>
          <input className="num" type="number" min="0" max="100" value={mix[b]} onChange={e => setMix({ ...mix, [b]: Number(e.target.value) })} /></label>)}</div>}
      </div>
      <div className="row gap wrap mt"><b>Phạm vi:</b>
        <button type="button" className={`chip ${!scope.length ? 'on' : ''}`} onClick={() => { setScope([]); setMat({}) }}>Tất cả chương</button>
        {allCh.map(c => <button type="button" key={c.outline_id} title={c.chapter_name}
          className={`chip ${scope.includes(c.outline_id) ? 'on' : ''}`}
          onClick={() => { setMat({}); setScope(s => s.includes(c.outline_id) ? s.filter(x => x !== c.outline_id) : [...s, c.outline_id]) }}>
          Chương {c.chapter_number} <small>({c.available})</small></button>)}
        {scope.length > 0 && <span className="pill blue">Kiểm tra chương</span>}
      </div>
      <div className="row gap wrap mt">
        <label className="row gap check"><input type="checkbox" checked={useMatrix} onChange={e => setUseMatrix(e.target.checked)} /> Nhập ma trận chi tiết</label>
        <label className="row gap check"><input type="checkbox" checked={keepPicked} onChange={e => setKeepPicked(e.target.checked)} /> Giữ các câu đã chọn tay</label>
        <span className="muted small">Ngân hàng trong phạm vi: <b>{p?.pool_size ?? '…'}</b> câu dùng được{p?.untagged ? ` · ${p.untagged} câu chưa gán CLO/Bloom` : ''}</span>
      </div>
      {useMatrix && p && <>
        <p className="muted small mt">Nhập số câu mỗi ô (chương × mức Bloom); số nhỏ là số câu ngân hàng đang có. Tổng: <b>{matTotal}</b> câu.</p>
        <MatrixTable chapters={chapters} cells={p.cells} blooms={blooms} value={mat} render={(o, b) => {
          if (b === 'sum') return Object.entries(mat).filter(([k]) => k.startsWith(`${o}:`)).reduce((a, [, v]) => a + (Number(v) || 0), 0) || ''
          const k = `${o}:${b}`; const a = avail[k] || 0
          return <span className="row gap" style={{ justifyContent: 'center' }}>
            <input className={`num tiny ${Number(mat[k] || 0) > a ? 'bad' : ''}`} type="number" min="0" value={mat[k] ?? ''} placeholder="0"
              onChange={e => setMat({ ...mat, [k]: e.target.value })} /><small className="muted">/{a}</small></span>
        }} />
      </>}
      <div className="row gap mt wrap">
        <ActionButton className="btn primary" disabled={useMatrix ? !matTotal : !(Number(n) > 0)} onRun={() => run(seed)}>⚙ Sinh đề theo ma trận</ActionButton>
        {res && <ActionButton className="btn" onRun={() => { const s = seed + 1; setSeed(s); return run(s) }}>↻ Sinh đề khác</ActionButton>}
        {res && !useMatrix && <button type="button" className="btn ghost" onClick={toMatrix}>Chỉnh ma trận này</button>}
      </div>
      {res && <div className="mt">
        {res.errors.map((e, i) => <div key={'e' + i} className="alert red">✗ {e}</div>)}
        {res.warnings.map((e, i) => <div key={'w' + i} className="alert amber">⚠ {e}</div>)}
        {res.info.map((e, i) => <div key={'i' + i} className="alert">ℹ {e}</div>)}
        {res.ok && <div className="alert green">✓ Đã chọn {res.n_questions} câu, tổng {res.total_points} điểm – các câu được đánh dấu trong danh sách bên dưới, có thể bỏ/thêm/đổi điểm thủ công.</div>}
        <div className="grid2 mt">
          <div><h4>Ma trận đề (đã chọn / mục tiêu)</h4>
            <MatrixTable chapters={res.chapters} cells={res.matrix} blooms={blooms} render={(o, b) => {
              if (b === 'sum') return res.matrix.filter(m => m.outline_id === o).reduce((a, m) => a + m.selected, 0) || ''
              const m = resMap[`${o}:${b}`]; if (!m || (!m.selected && !m.target)) return ''
              return <span className={m.selected < m.target ? 'bad-t' : ''}>{m.selected}{m.target !== m.selected ? `/${m.target}` : ''}</span>
            }} /></div>
          <div><h4>Độ phủ CLO</h4>
            <table className="tbl compact"><thead><tr><th>CLO</th><th className="num-c">Số câu</th><th className="num-c">Điểm</th><th className="num-c">Ngân hàng</th></tr></thead>
              <tbody>{res.clos.map(c => <tr key={c.clo_id} className={c.in_scope ? '' : 'dim'}>
                <td><b>{c.clo_code}</b>{!c.in_scope && <small className="muted"> – không đo trong bài</small>}</td>
                <td className={`num-c ${c.in_scope && !c.selected ? 'bad-t' : ''}`}>{c.selected}</td><td className="num-c">{c.points}</td><td className="num-c">{c.available}</td></tr>)}</tbody></table>
          </div>
        </div>
      </div>}
    </div>
  )
}
