// Trang Tổng quan: người mới vào biết ngay việc cần làm tiếp theo, bấm là tới đúng trang.
import { Link } from 'react-router-dom'
import { Loading, Stat } from '../components/ui'
import { useApi } from '../hooks'
import { auth } from '../api'

const STEP = { 1: 'Tạo bài', 2: 'Phân tích', 3: 'Công bố', 4: 'Cải tiến', 5: 'Quá hạn' }
const STEP_TONE = { 1: 'blue', 2: 'blue', 3: 'amber', 4: 'red', 5: 'red' }

function Todo({ t }) {
  return <Link to={t.to} className="todo">
    <span className={`todo-tag ${STEP_TONE[t.step]}`}>{STEP[t.step]}</span>
    <span className="todo-main"><b>{t.title}</b><small>{t.where}</small></span>
    <span className="todo-go">Làm ngay →</span>
  </Link>
}

function Lecturer({ d }) {
  const s = d.stats
  return <>
    <div className="stats">
      <Stat label="Lớp học phần phụ trách" value={s.sections} />
      <Stat label="Bài kiểm tra" value={s.exams} sub={`${s.analyzed} đã phân tích`} />
      <Stat label="Đã công bố cho sinh viên" value={s.published} tone={s.published ? 'green' : ''} />
      <Stat label="Việc đang chờ bạn" value={d.todos.length} tone={d.todos.length ? 'red' : 'green'} />
    </div>
    <section className="card home-card">
      <div className="card-h"><h3>Việc cần làm</h3></div>
      <div className="card-b">
        {d.todos.length === 0
          ? <div className="empty-state"><b>Không còn việc tồn đọng.</b><p className="muted">Muốn bắt đầu bài mới: vào <Link to="/courses">Môn học của tôi</Link> → "Mở lớp" → "+ Tạo bài kiểm tra".</p></div>
          : <div className="todo-list">{d.todos.map((t, i) => <Todo key={i} t={t} />)}</div>}
      </div>
    </section>
    <section className="card home-card">
      <div className="card-h"><h3>Quy trình một bài kiểm tra</h3></div>
      <div className="card-b"><ol className="flow-line">
        <li><b>1. Tạo bài</b><small>Chọn câu hỏi gắn CLO, tạo đề</small></li>
        <li><b>2. Tổ chức thi</b><small>Trực tuyến trên Moodle, hoặc in phiếu rồi quét</small></li>
        <li><b>3. Phân tích</b><small>Lấy bài làm, chấm, tính mức đạt từng CLO</small></li>
        <li><b>4. Công bố</b><small>Sinh viên xem kết quả của mình trên Moodle</small></li>
        <li><b>5. Cải tiến</b><small>CLO chưa đạt: ghi hành động, kiểm chứng ở kỳ sau</small></li>
      </ol></div>
    </section>
  </>
}

function Admin({ d }) {
  const done = d.checks.filter(c => c.done).length
  const next = d.checks.find(c => !c.done)
  return <>
    <div className="stats">
      <Stat label="Chương trình đào tạo" value={d.stats.programs} />
      <Stat label="Học phần" value={d.stats.courses} />
      <Stat label="Lớp học phần" value={d.stats.sections} />
      <Stat label="Bài đã phân tích" value={d.stats.analyzed} />
    </div>
    <section className="card home-card">
      <div className="card-h"><h3>Tình trạng thiết lập · {done}/{d.checks.length} mục hoàn tất</h3></div>
      <div className="card-b">
        <div className="progress" role="progressbar" aria-valuenow={done} aria-valuemax={d.checks.length}><i style={{ width: `${100 * done / d.checks.length}%` }} /></div>
        <div className="todo-list">{d.checks.map((c, i) => <Link key={c.key} to={c.to} className={`todo check ${c.done ? 'done' : ''} ${next === c ? 'next' : ''}`}>
          <span className={`check-ico ${c.done ? 'ok' : ''}`}>{c.done ? '✓' : i + 1}</span>
          <span className="todo-main"><b>{c.title}</b><small>{c.done ? 'Đã đủ · ' : `${c.pending}${c.total != null ? `/${c.total}` : ''} mục chưa xong · `}{c.hint}</small></span>
          <span className="todo-go">{c.done ? 'Xem' : next === c ? 'Làm tiếp →' : 'Mở →'}</span>
        </Link>)}</div>
      </div>
    </section>
  </>
}

export default function Home() {
  const { data, ...st } = useApi('/api/dashboard')
  const u = auth.user()
  return <>
    <div className="page-h"><div><h1>Xin chào, {u?.full_name}</h1>
      <p className="muted">{u?.role === 'admin' ? 'Theo dõi mức hoàn thiện của chương trình và những việc còn thiếu.' : 'Những việc cần làm tiếp theo cho các lớp bạn phụ trách.'}</p></div></div>
    {!data ? <Loading {...st} /> : data.role === 'lecturer' ? <Lecturer d={data} /> : <Admin d={data} />}
  </>
}
