import { useMemo, useState } from 'react'
import { Bar } from 'react-chartjs-2'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { fmtNum } from '../api'
import { C, heat } from '../charts'
import { Badge, Card, Loading, Stat } from '../components/ui'
import { useApi } from '../hooks'

const pctAxis = { min: 0, max: 100, ticks: { callback: v => `${v}%` } }

export default function ClassStats() {
  const { id } = useParams()
  const [sp, setSp] = useSearchParams()
  const examId = sp.get('exam')
  const cs = useApi('/api/class-sections').data?.find(x => String(x.id) === id)
  const { data: d, ...st } = useApi(`/api/class-sections/${id}/stats${examId ? `?exam_id=${examId}` : ''}`)
  const [onlyRisk, setOnlyRisk] = useState(false)
  const [sort, setSort] = useState('score')
  const nav = useNavigate()
  const heatRows = useMemo(() => {
    if (!d?.heatmap) return []
    const r = onlyRisk ? d.at_risk : d.heatmap
    return [...r].sort(sort === 'code' ? (a, b) => a.student_code.localeCompare(b.student_code) : (a, b) => a.score - b.score)
  }, [d, onlyRisk, sort])

  const head = (
    <div className="page-h">
      <div><div className="crumb"><Link to="/">Lớp học phần</Link> / <Link to={`/sections/${id}`}>{cs?.section_code}</Link> / Thống kê lớp</div>
        <h1>Thống kê kết quả lớp học phần</h1><p className="muted">{cs?.course_code} – {cs?.course_name} · {cs?.semester}</p></div>
      <div className="row gap"><Link className="btn" to={`/sections/${id}/clo`}>Kết quả CĐR (BM6)</Link></div>
    </div>)
  if (!d) return <>{head}<Loading {...st} /></>
  if (!d.exam) return <>{head}<div className="alert amber">Lớp chưa có bài kiểm tra nào được phân tích. Hãy đồng bộ &amp; phân tích bài kiểm tra trước.</div></>
  const k = d.kpi
  const e = d.exam
  const codes = d.clos.map(c => c.code)

  return (
    <>
      {head}
      <div className="row gap wrap mb"><b>Bài kiểm tra:</b>
        {d.exams.map(x => <button key={x.id} className={`chip ${x.id === e.id ? 'on' : ''}`} onClick={() => setSp({ exam: x.id })}>{x.exam_title}</button>)}
        <span className="grow" /><Link className="btn sm" to={`/exams/${e.id}`}>Mở bài kiểm tra →</Link>
      </div>
      <div className="stats">
        <Stat label="SV dự thi" value={`${k.n_finished}/${k.n_students}`} sub={`${k.n_absent} vắng`} />
        <Stat label="Điểm trung bình" value={fmtNum(k.mean)} sub={`/ ${e.max_score} · ${k.pass_rate}% SV ≥ ${e.max_score / 2}`} />
        <Stat label="Đạt đủ mọi CLO" value={k.n_all_clo} sub={`${k.n_finished ? Math.round(100 * k.n_all_clo / k.n_finished) : 0}% SV dự thi · ${k.n_clos} CLO`} tone="green" />
        <Stat label="SV cần hỗ trợ" value={k.n_at_risk} sub="điểm < 50% hoặc đạt < ½ số CLO" tone={k.n_at_risk ? 'red' : ''} />
        <Stat label="Chương cần ôn nhiều nhất" value={d.chapters[0] ? d.chapters[0].chapter.split('.')[0] : '—'}
          sub={d.chapters[0] ? `${d.chapters[0].n_students} SV (${d.chapters[0].pct_students}%)` : 'không có'} tone="amber" />
      </div>

      <div className="grid2">
        <Card title="Tỷ lệ SV đạt từng CLO so với mục tiêu">
          <div className="chart"><Bar data={{ labels: codes, datasets: [
            { type: 'bar', label: 'SV đạt ngưỡng (%)', data: d.clos.map(c => c.achieved_pct), backgroundColor: C.blue, borderRadius: 4, order: 2 },
            { type: 'line', label: 'Mục tiêu (%)', data: d.clos.map(c => c.target), borderColor: C.amber, backgroundColor: C.amber, borderWidth: 3, pointRadius: 26, pointHoverRadius: 28, pointStyle: 'line', showLine: false, order: 1 }] }}
            options={{ maintainAspectRatio: false, scales: { y: pctAxis },
              plugins: { legend: { labels: { usePointStyle: true } }, tooltip: { callbacks: { afterBody: it => { const c = d.clos[it[0].dataIndex]; return [`${c.n_achieved}/${c.n} SV đạt · điểm TB ${c.avg_pct}%`, `Ngưỡng θ = ${c.threshold}%`, c.description] } } } } }} /></div>
          <table className="tbl compact mt"><thead><tr><th>CLO</th><th>SV đạt</th><th>Mục tiêu</th><th>Điểm TB</th><th /></tr></thead>
            <tbody>{d.clos.map(c => <tr key={c.code}><td><b>{c.code}</b></td><td>{c.n_achieved}/{c.n} ({c.achieved_pct}%)</td><td>{c.target}%</td><td>{c.avg_pct}%</td>
              <td>{c.achieved_pct >= c.target ? <Badge tone="green">Đạt mục tiêu</Badge> : <Badge tone="red">Chưa đạt mục tiêu</Badge>}</td></tr>)}</tbody></table>
        </Card>

        <Card title="Chương cần ôn tập (số SV có trong lộ trình)">
          {d.chapters.length === 0 ? <div className="alert green">Không SV nào cần ôn lại – tất cả CLO đều đạt ngưỡng.</div> : <>
            <div className="chart" style={{ height: Math.max(200, 44 * d.chapters.length + 40) }}><Bar data={{ labels: d.chapters.map(c => c.chapter.length > 30 ? c.chapter.slice(0, 29) + '…' : c.chapter), datasets: [
              { label: 'Số SV cần ôn', data: d.chapters.map(c => c.n_students), backgroundColor: C.amber, borderRadius: 4 }] }}
              options={{ indexAxis: 'y', maintainAspectRatio: false, plugins: { legend: { display: false },
                tooltip: { callbacks: { title: it => d.chapters[it[0].dataIndex].chapter,
                  afterLabel: it => { const c = d.chapters[it.dataIndex]; return [`${c.pct_students}% SV dự thi`, `Thiếu hụt TB ${c.avg_gap}% so với ngưỡng`, `CLO: ${c.clos.join(', ')}`] } } } },
                scales: { x: { ticks: { precision: 0 }, title: { display: true, text: 'Số SV' } } } }} /></div>
            <p className="muted small">Theo lộ trình học tập cá nhân hóa sinh ra khi phân tích (mỗi CLO chưa đạt → các chương có câu hỏi thuộc CLO đó).</p></>}
        </Card>

        <Card title="Số CLO đạt trên mỗi sinh viên">
          <div className="chart"><Bar data={{ labels: d.clo_count_hist.map(h => `${h.k}/${k.n_clos} CLO`), datasets: [
            { label: 'Số SV', data: d.clo_count_hist.map(h => h.n), backgroundColor: d.clo_count_hist.map(h => h.k === k.n_clos ? C.green : C.blue), borderRadius: 4 }] }}
            options={{ maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: it => `${it.raw} SV đạt ${d.clo_count_hist[it.dataIndex].k}/${k.n_clos} CLO` } } },
              scales: { y: { ticks: { precision: 0 }, title: { display: true, text: 'Số SV' } } } }} /></div>
          <p className="muted small">Cột xanh lá: SV đạt đủ mọi CLO của bài kiểm tra.</p>
        </Card>

        <Card title="Tỷ lệ trả lời đúng theo mức Bloom">
          <div className="chart"><Bar data={{ labels: d.bloom.map(b => b.level), datasets: [
            { label: 'Trả lời đúng (%)', data: d.bloom.map(b => b.pct_correct), backgroundColor: C.blue, borderRadius: 4 }] }}
            options={{ maintainAspectRatio: false, scales: { y: pctAxis }, plugins: { legend: { display: false },
              tooltip: { callbacks: { label: it => `${it.raw}% câu trả lời đúng · ${d.bloom[it.dataIndex].n_items} câu hỏi` } } } }} /></div>
          <p className="muted small">Mức nhận thức càng cao thường tỷ lệ đúng càng thấp; mức nào tụt mạnh gợi ý cần tăng bài tập ở mức đó.</p>
        </Card>
      </div>

      <Card title="Phổ điểm">
        <div className="chart"><Bar data={{ labels: d.score_hist.map(h => h.range), datasets: [{ label: 'Số SV', data: d.score_hist.map(h => h.count), backgroundColor: C.blue, borderRadius: 4 }] }}
          options={{ maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { ticks: { precision: 0 }, title: { display: true, text: 'Số SV' } }, x: { title: { display: true, text: 'Khoảng điểm' } } } }} /></div>
      </Card>

      <Card title="Sinh viên cần hỗ trợ" actions={<span className="muted">{d.at_risk.length} SV · bấm để xem chi tiết</span>}>
        {d.at_risk.length === 0 ? <div className="alert green">Không có SV nào dưới ngưỡng cảnh báo.</div> :
          <table className="tbl"><thead><tr><th>MSSV</th><th>Họ tên</th><th>Điểm</th><th>CLO đạt</th><th>CLO chưa đạt</th><th>Số chương cần ôn</th><th /></tr></thead>
            <tbody>{d.at_risk.map(s => <tr key={s.student_code} className="click" onClick={() => nav(`/sections/${id}/students/${s.student_id}?exam=${e.id}`)}>
              <td>{s.student_code}</td><td><b>{s.full_name}</b></td><td className={s.score < e.max_score / 2 ? 'bad-t' : ''}>{s.score}</td>
              <td>{s.n_achieved}/{k.n_clos}</td><td>{Object.entries(s.clos).filter(([, v]) => !v.ok).map(([c]) => c).join(', ') || '—'}</td>
              <td>{s.n_review}</td><td><Link className="btn sm" to={`/sections/${id}/students/${s.student_id}?exam=${e.id}`} onClick={ev => ev.stopPropagation()}>Hồ sơ</Link></td></tr>)}</tbody></table>}
        {d.absent.length > 0 && <p className="muted mt">Vắng thi (chưa đủ bằng chứng đánh giá): {d.absent.map((s, i) => <span key={s.student_code}>{i ? ', ' : ''}
          <Link to={`/sections/${id}/students/${s.student_id}`}>{s.student_code} {s.full_name}</Link></span>)}</p>}
      </Card>

      <Card title="Bản đồ mức đạt CLO của từng sinh viên" actions={<>
        <label className="row gap small"><input type="checkbox" checked={onlyRisk} onChange={ev => setOnlyRisk(ev.target.checked)} /> Chỉ SV cần hỗ trợ</label>
        <select value={sort} onChange={ev => setSort(ev.target.value)}><option value="score">Xếp theo điểm tăng dần</option><option value="code">Xếp theo MSSV</option></select></>}>
        <div className="row gap wrap small mb"><span className="muted">Mức đạt (%):</span>
          {[0, 25, 50, 75, 100].map(v => <span key={v} className="heat-key" style={heat(v)}>{v}</span>)}
          <span className="muted">· ✗ = dưới ngưỡng θ của CLO</span></div>
        <div className="scroll tall">
          <table className="tbl heat"><thead><tr><th>MSSV</th><th>Họ tên</th><th>Điểm</th>{codes.map(c => <th key={c} className="c">{c}</th>)}<th className="c">Đạt</th></tr></thead>
            <tbody>{heatRows.map(s => <tr key={s.student_code} className="click" onClick={() => nav(`/sections/${id}/students/${s.student_id}?exam=${e.id}`)}>
              <td>{s.student_code}</td><td>{s.full_name}</td><td>{s.score}</td>
              {codes.map(c => { const v = s.clos[c]; return <td key={c} className="c cell" style={v ? heat(v.pct) : {}}
                title={v ? `${s.full_name} · ${c}: ${v.pct}% (${v.ok ? 'đạt' : 'chưa đạt'})` : ''}>{v ? `${Math.round(v.pct)}${v.ok ? '' : ' ✗'}` : '—'}</td> })}
              <td className="c">{s.n_achieved}/{k.n_clos}</td></tr>)}</tbody></table>
        </div>
      </Card>
    </>
  )
}
