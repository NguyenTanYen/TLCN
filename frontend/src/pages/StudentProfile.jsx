import { useState } from 'react'
import { Radar } from 'react-chartjs-2'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { C } from '../charts'
import { Achieved, Badge, Card, Loading, Stat } from '../components/ui'
import { useApi } from '../hooks'

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
  const nOk = d.overall_clos.filter(c => c.achieved).length

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
          <Card title="Tổng hợp mức đạt CLO (mọi bài kiểm tra đã phân tích)">
            {d.overall_clos.length === 0 ? <div className="alert amber">Chưa đủ bằng chứng đánh giá (SV vắng tất cả bài kiểm tra).</div> :
              <table className="tbl"><thead><tr><th>CLO</th><th>Mức đạt</th><th>Ngưỡng θ</th><th>Số bài đạt</th><th /></tr></thead>
                <tbody>{d.overall_clos.map(c => <tr key={c.code}><td><b>{c.code}</b><div className="muted small">{c.description}</div></td>
                  <td className={c.achieved ? 'ok-t' : 'bad-t'}><b>{c.pct}%</b></td><td>{c.threshold}%</td><td>{c.n_achieved}/{c.n_exams}</td><td><Achieved ok={c.achieved} /></td></tr>)}</tbody></table>}
            {d.overall_clos.length > 0 && <p className="mt">Đạt <b>{nOk}/{d.overall_clos.length}</b> CLO khi gộp các bài kiểm tra (tổng điểm đạt / tổng điểm tối đa của các câu thuộc CLO).</p>}
          </Card>
          <Card title="Cần học lại những phần nào">
            {d.review.length === 0 ? <div className="alert green">SV đạt ngưỡng ở mọi CLO – không có chương nào cần học lại.</div> :
              <div className="review">{d.review.map((r, i) => <div key={r.chapter}>
                <div className="row gap wrap"><span className="prio">Ưu tiên {i + 1}</span><b>{r.chapter}</b></div>
                <div className="muted small">CLO chưa đạt: {r.clos.join(', ')} · thiếu tối đa {r.max_gap}% so với ngưỡng · từ bài: {r.exams.join('; ')}</div>
              </div>)}</div>}
          </Card>
        </div>

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
  if (e.status !== 'finished') return <div className="alert amber"><b>{e.exam_title}:</b> SV vắng thi – chưa đủ bằng chứng đánh giá (E2), không tính vào CLO của bài này.</div>
  const ok = e.clos.filter(c => c.achieved).length
  const ans = e.answers.filter(a => filter === 'all' || a.result === filter)
  const cnt = r => e.answers.filter(a => a.result === r).length
  const groups = Object.values((e.items || []).reduce((m, i) => { (m[i.priority] ||= { ...i, chapters: [] }).chapters.push(i.chapter); return m }, {}))
  return (
    <>
      <div className="stats">
        <Stat label="Điểm" value={`${e.score} / ${e.max_score}`} sub={`TB lớp ${e.class_mean}`} tone={e.score >= e.max_score / 2 ? 'green' : 'red'} />
        <Stat label="Xếp hạng trong lớp" value={`${e.rank}/${e.n_finished}`} sub="theo điểm, SV dự thi" />
        <Stat label="CLO đạt" value={`${ok}/${e.clos.length}`} tone={ok === e.clos.length ? 'green' : 'amber'} />
        <Stat label="Trả lời" value={`${cnt('correct')} đúng`} sub={`${cnt('wrong')} sai · ${cnt('blank')} bỏ trống`} />
        <Stat label="Hiển thị cho SV trên Moodle" value={e.publish_flag ? 'Đã công bố' : 'Đang bảo lưu'} sub={e.source === 'paper' ? 'bài làm trên giấy' : 'bài làm Moodle'} tone={e.publish_flag ? 'green' : ''} />
      </div>
      <div className="grid2">
        <Card title="Mức đạt từng CLO so với ngưỡng và trung bình lớp">
          <div className="chart tall"><Radar data={{ labels: e.clos.map(c => c.code), datasets: [
            { label: 'Sinh viên (%)', data: e.clos.map(c => c.pct), borderColor: C.blue, backgroundColor: C.blueA, pointBackgroundColor: C.blue, pointRadius: 4, borderWidth: 2 },
            { label: 'Trung bình lớp (%)', data: e.clos.map(c => c.class_avg), borderColor: C.gray, backgroundColor: 'transparent', borderDash: [4, 4], pointRadius: 3, borderWidth: 2 },
            { label: 'Ngưỡng đạt θ (%)', data: e.clos.map(c => c.threshold), borderColor: C.amber, backgroundColor: 'transparent', pointRadius: 0, borderWidth: 2 }] }}
            options={{ maintainAspectRatio: false, scales: { r: { min: 0, max: 100, ticks: { stepSize: 20, backdropColor: 'transparent' } } },
              plugins: { tooltip: { callbacks: { label: it => `${it.dataset.label}: ${it.raw}%` } } } }} /></div>
        </Card>
        <Card title="Kết quả CLO & chẩn đoán">
          <table className="tbl"><thead><tr><th>CLO</th><th>SV</th><th>TB lớp</th><th>Ngưỡng</th><th /></tr></thead>
            <tbody>{e.clos.map(c => <tr key={c.code}><td><b>{c.code}</b><div className="muted small">{c.description}</div></td>
              <td className={c.achieved ? 'ok-t' : 'bad-t'}><b>{c.pct}%</b></td><td>{c.class_avg}%</td><td>{c.threshold}%</td><td><Achieved ok={c.achieved} /></td></tr>)}</tbody></table>
          {e.summary && <p className="mt"><b>Chẩn đoán:</b> {e.summary}</p>}
          <h4>Lộ trình ôn tập của bài này</h4>
          {groups.length === 0 ? <div className="alert green">Đạt mọi CLO của bài kiểm tra.</div> :
            <ol className="path">{groups.map(g => <li key={g.priority}><div className="row gap wrap"><span className="prio">Ưu tiên {g.priority}</span><b>{g.clo}</b>
              <span className="muted">thiếu {g.gap}% so với ngưỡng</span></div>
              <ul>{g.chapters.map(c => <li key={c || 'x'}>Ôn lại <b>{c || 'nội dung của CLO (chưa gắn chương)'}</b></li>)}</ul></li>)}</ol>}
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
