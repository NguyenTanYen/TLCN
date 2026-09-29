import { Radar } from 'react-chartjs-2'
import { Link, useParams } from 'react-router-dom'
import { C } from '../charts'
import { Achieved, Card, Loading, Stat } from '../components/ui'
import { useApi } from '../hooks'

export default function LearningPath() {
  const { id } = useParams()
  const { data: d, ...st } = useApi(`/api/me/exams/${id}/learning-path`)
  if (!d) return <Loading {...st} />
  if (d.insufficient_evidence) return <><div className="crumb"><Link to="/">Kết quả của tôi</Link></div><h1>{d.exam_title}</h1><div className="alert amber">{d.message}</div></>
  const ok = d.radar.filter(r => r.is_achieved).length
  return (
    <>
      <div className="page-h"><div><div className="crumb"><Link to="/">Kết quả của tôi</Link> / {d.exam_title}</div><h1>{d.exam_title}</h1></div></div>
      <div className="stats">
        <Stat label="Điểm" value={`${d.score} / ${d.max_score}`} />
        <Stat label="CĐR đạt" value={`${ok}/${d.radar.length}`} tone={ok === d.radar.length ? 'green' : 'amber'} />
      </div>
      <div className="grid2">
        <Card title="Mức độ đạt từng CĐR môn học">
          <div className="chart tall"><Radar data={{ labels: d.radar.map(r => r.clo_code), datasets: [
            { label: 'Của bạn (%)', data: d.radar.map(r => r.score_pct), borderColor: C.blue, backgroundColor: C.blueA, pointBackgroundColor: C.blue },
            { label: 'Trung bình lớp (%)', data: d.radar.map(r => r.class_avg), borderColor: C.gray, backgroundColor: 'transparent', borderDash: [4, 4] },
            { label: 'Ngưỡng đạt (%)', data: d.radar.map(r => r.pass_threshold_pct), borderColor: C.red, backgroundColor: 'transparent', pointRadius: 0, borderWidth: 1 }] }}
            options={{ maintainAspectRatio: false, scales: { r: { min: 0, max: 100, ticks: { stepSize: 20 } } } }} /></div>
        </Card>
        <Card title="Chi tiết">
          <table className="tbl"><thead><tr><th>CĐR</th><th>Nội dung</th><th>Của bạn</th><th>TB lớp</th><th /></tr></thead>
            <tbody>{d.radar.map(r => <tr key={r.clo_code}><td><b>{r.clo_code}</b></td><td className="wrap-cell">{r.description}</td><td>{r.score_pct}%</td><td>{r.class_avg}%</td><td><Achieved ok={!!r.is_achieved} /></td></tr>)}</tbody></table>
          {d.summary && <p className="mt"><b>Chẩn đoán:</b> {d.summary}</p>}
        </Card>
      </div>
      <Card title="Lộ trình ôn tập đề xuất">
        {d.items.length === 0 ? <div className="alert green">Bạn đã đạt tất cả CĐR của bài kiểm tra này. Hãy duy trì!</div> :
          <ol className="path">{Object.values(d.items.reduce((m, i) => { (m[i.priority] ||= { ...i, chapters: [] }).chapters.push(i); return m }, {})).map(g =>
            <li key={g.priority}><div className="row gap"><span className="prio">Ưu tiên {g.priority}</span><b>{g.clo_code}</b><span className="muted">thiếu {g.gap_pct}% so với ngưỡng</span></div>
              <div className="muted">{g.clo_description}</div>
              <ul>{g.chapters.map(c => <li key={c.chapter_number ?? 'x'}>Ôn lại <b>Chương {c.chapter_number}: {c.chapter_name}</b></li>)}</ul></li>)}</ol>}
      </Card>
    </>
  )
}
