import { useState } from 'react'
import { Radar } from 'react-chartjs-2'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { C } from '../charts'
import { Badge, Card, Loading, Stat } from '../components/ui'
import { useApi } from '../hooks'

// Hồ sơ một SV (góp ý 21/10): SV được đánh giá bằng ĐIỂM; mức CLO của SV chỉ để tham khảo khi ôn tập (không gắn nhãn Đạt/Không đạt –
// kết luận đạt CLO chỉ có ở cấp lớp, BM6b). Phần chính: điểm từng bài, nội dung cần ôn, chi tiết câu trả lời.
const RES = { correct: ['Đúng', 'ans-ok', '✓'], wrong: ['Sai', 'ans-bad', '✗'], blank: ['Bỏ trống', 'ans-blank', '–'] }

export default function StudentProfile() {
  const { cs, sid } = useParams()
  const [sp, setSp] = useSearchParams()
  const nav = useNavigate()
  const section = useApi('/api/class-sections').data?.find(x => String(x.id) === cs)
  const { data: d, ...st } = useApi(`/api/class-sections/${cs}/students/${sid}/profile`)
  if (!d) return <Loading {...st} />
  const s = d.student
  const exams = d.exams
  const cur = exams.find(e => String(e.id) === sp.get('exam')) || exams[exams.length - 1]
  const go = id => nav(`/sections/${cs}/students/${id}${cur ? `?exam=${cur.id}` : ''}`)

  return (
    <>
      <div className="page-h">
        <div><div className="crumb"><Link to="/">Lớp học phần</Link> / <Link to={`/sections/${cs}`}>{section?.section_code}</Link> / <Link to={`/sections/${cs}/stats${cur ? `?exam=${cur.id}` : ''}`}>Thống kê lớp</Link> / {s.student_code}</div>
          <h1>{s.full_name}</h1>
          <p className="muted">MSSV {s.student_code} · lớp {s.class_name || '—'} · {section?.course_code} – {section?.course_name}
            {s.status !== 'active' && <> · <Badge tone="amber">Đã rút học phần</Badge></>}</p></div>
        <div className="nav-sv">
          <button className="btn" disabled={!d.prev_id} onClick={() => go(d.prev_id)}>← SV trước</button>
          <span className="muted">{d.position}/{d.n_students}</span>
          <button className="btn" disabled={!d.next_id} onClick={() => go(d.next_id)}>SV sau →</button>
        </div>
      </div>

      {exams.length === 0 ? <div className="alert amber">Lớp chưa có bài kiểm tra nào được phân tích.</div> : <>
        <div className="grid2">
          <Card title="Điểm các bài kiểm tra">
            <table className="tbl"><thead><tr><th>Bài kiểm tra</th><th className="num-c">Điểm</th><th className="num-c">TB lớp</th><th className="num-c">Xếp hạng</th></tr></thead>
              <tbody>{exams.map(x => <tr key={x.id} className={`click ${x.id === cur.id ? 'sel' : ''}`} onClick={() => setSp({ exam: x.id })}><td><b>{x.exam_title}</b></td>
                {x.status === 'finished' ? <><td className="num-c"><b>{x.score}</b> / {x.max_score}</td><td className="num-c">{x.class_mean}</td><td className="num-c">{x.rank}/{x.n_finished}</td></>
                  : <td colSpan={3} className="muted">Vắng thi</td>}</tr>)}</tbody></table>
          </Card>
          <Card title="Cần ôn lại những phần nào">
            {d.review.length === 0 ? <div className="alert green">Không có chương nào cần ôn lại – điểm các nội dung đều đạt mức yêu cầu.</div> :
              <div className="review">{d.review.map((r, i) => <div key={r.chapter}>
                <div className="row gap wrap"><span className="prio">Ưu tiên {i + 1}</span><b>{r.chapter}</b></div>
                <div className="muted small">Liên quan {r.clos.join(', ')} · điểm còn thiếu tối đa {r.max_gap}% so với mức yêu cầu · từ bài: {r.exams.join('; ')}</div>
              </div>)}</div>}
          </Card>
        </div>
        {d.overall_clos.length > 0 && <details className="adv mb"><summary>Tỷ lệ điểm theo nội dung (CLO), gộp mọi bài – tham khảo</summary>
          <table className="tbl compact mt"><thead><tr><th>CLO</th><th className="num-c">Tỷ lệ điểm của SV</th></tr></thead>
            <tbody>{d.overall_clos.map(c => <tr key={c.code}><td><b>{c.code}</b> <span className="muted small">{c.description}</span></td><td className="num-c">{c.pct}%</td></tr>)}</tbody></table>
          <p className="muted small">Chỉ dùng để gợi ý ôn tập. Kết luận đạt chuẩn đầu ra (CLO) được tính cho cả lớp ở trang Kết quả CĐR (BM6).</p>
        </details>}

        <div className="row gap wrap mb"><b>Chi tiết theo bài kiểm tra:</b>
          {exams.map(x => <button key={x.id} className={`chip ${x.id === cur.id ? 'on' : ''}`} onClick={() => setSp({ exam: x.id })}>{x.exam_title}</button>)}
        </div>
        <ExamBlock e={cur} />
      </>}
    </>
  )
}

function ExamBlock({ e }) {
  const [filter, setFilter] = useState('all')
  if (e.status !== 'finished') return <div className="alert amber"><b>{e.exam_title}:</b> SV vắng thi – không có điểm bài này.</div>
  const ans = e.answers.filter(a => filter === 'all' || a.result === filter)
  const cnt = r => e.answers.filter(a => a.result === r).length
  const groups = Object.values((e.items || []).reduce((m, i) => { (m[i.priority] ||= { ...i, chapters: [] }).chapters.push(i.chapter); return m }, {}))
  return (
    <>
      <div className="stats">
        <Stat label="Điểm" value={`${e.score} / ${e.max_score}`} sub={`TB lớp ${e.class_mean}`} tone={e.score >= e.max_score / 2 ? 'green' : 'red'} />
        <Stat label="Xếp hạng trong lớp" value={`${e.rank}/${e.n_finished}`} sub="theo điểm, SV dự thi" />
        <Stat label="Trả lời" value={`${cnt('correct')} đúng`} sub={`${cnt('wrong')} sai · ${cnt('blank')} bỏ trống`} />
        <Stat label="Hiển thị cho SV trên Moodle" value={e.publish_flag ? 'Đã công bố' : 'Đang bảo lưu'} sub={e.source === 'paper' ? 'bài làm trên giấy' : 'bài làm Moodle'} tone={e.publish_flag ? 'green' : ''} />
      </div>
      <div className="grid2">
        <Card title="Tỷ lệ điểm theo nội dung (CLO) so với trung bình lớp – tham khảo">
          <div className="chart tall"><Radar data={{ labels: e.clos.map(c => c.code), datasets: [
            { label: 'Sinh viên (%)', data: e.clos.map(c => c.pct), borderColor: C.blue, backgroundColor: C.blueA, pointBackgroundColor: C.blue, pointRadius: 4, borderWidth: 2 },
            { label: 'Trung bình lớp (%)', data: e.clos.map(c => c.class_avg), borderColor: C.gray, backgroundColor: 'transparent', borderDash: [4, 4], pointRadius: 3, borderWidth: 2 }] }}
            options={{ maintainAspectRatio: false, scales: { r: { min: 0, max: 100, ticks: { stepSize: 20, backdropColor: 'transparent' } } },
              plugins: { tooltip: { callbacks: { label: it => `${it.dataset.label}: ${it.raw}%` } } } }} /></div>
        </Card>
        <Card title="Chẩn đoán & lộ trình ôn tập">
          <table className="tbl"><thead><tr><th>Nội dung (CLO)</th><th className="num-c">SV</th><th className="num-c">TB lớp</th></tr></thead>
            <tbody>{e.clos.map(c => <tr key={c.code}><td><b>{c.code}</b><div className="muted small">{c.description}</div></td>
              <td className="num-c"><b>{c.pct}%</b></td><td className="num-c">{c.class_avg}%</td></tr>)}</tbody></table>
          {e.summary && <p className="mt"><b>Chẩn đoán:</b> {e.summary}</p>}
          <h4>Lộ trình ôn tập của bài này</h4>
          {groups.length === 0 ? <div className="alert green">Không có nội dung nào cần ôn lại ở bài này.</div> :
            <ol className="path">{groups.map(g => <li key={g.priority}><div className="row gap wrap"><span className="prio">Ưu tiên {g.priority}</span>
              <span className="muted">liên quan {g.clo} · điểm còn thiếu {g.gap}% so với mức yêu cầu</span></div>
              <ul>{g.chapters.map(c => <li key={c || 'x'}>Ôn lại <b>{c || `nội dung của ${g.clo} (chưa gắn chương)`}</b></li>)}</ul></li>)}</ol>}
        </Card>
      </div>
      <Card title="Chi tiết từng câu trả lời" actions={[['all', `Tất cả (${e.answers.length})`], ['wrong', `Sai (${cnt('wrong')})`], ['blank', `Bỏ trống (${cnt('blank')})`], ['correct', `Đúng (${cnt('correct')})`]].map(([k, l]) =>
        <button key={k} className={`chip ${filter === k ? 'on' : ''}`} onClick={() => setFilter(k)}>{l}</button>)}>
        <table className="tbl"><thead><tr><th>#</th><th>Câu hỏi</th><th>Chương</th><th>CLO</th><th>Bloom</th><th>SV chọn</th><th>Đáp án</th><th>Kết quả</th><th>Điểm</th><th>Tỷ lệ lớp đúng</th></tr></thead>
          <tbody>{ans.map(a => { const [t, cls, ic] = RES[a.result]; return <tr key={a.question_id}>
            <td>{a.order_index}</td><td className="clip" title={a.content}>{a.content}</td><td>{a.chapter || '—'}</td><td>{a.clos}</td><td>{a.bloom}</td>
            <td>{a.chosen || '—'}</td><td>{a.correct}</td><td className={cls}>{ic} {t}</td><td>{a.score_earned}/{a.points}</td>
            <td>{a.p_value === null ? '—' : `${Math.round(a.p_value * 100)}%`}</td></tr> })}</tbody></table>
        {e.source === 'paper' && <p className="muted small mt">Bài trên giấy: nhãn phương án là nhãn gốc trong ngân hàng câu hỏi (đã quy đổi từ mã đề).</p>}
      </Card>
    </>
  )
}
