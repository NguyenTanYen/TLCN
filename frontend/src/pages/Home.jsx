import { Link } from 'react-router-dom'
import { Loading, Stat } from '../components/ui'
import { useApi } from '../hooks'
import { auth } from '../api'

const STEP = { 1: 'Tạo bài', 2: 'Phân tích', 3: 'Công bố', 4: 'Cải tiến', 5: 'Quá hạn' }

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
          : <table className="tbl">
            <thead><tr><th>Việc cần làm</th><th>Lớp / bài</th><th>Loại</th><th></th></tr></thead>
            <tbody>{d.todos.map((t, i) => <tr key={i}><td><b>{t.title}</b></td><td>{t.where}</td><td>{STEP[t.step]}</td><td><Link to={t.to}>Mở</Link></td></tr>)}</tbody>
          </table>}
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
        <table className="tbl setup">
          <thead><tr><th>STT</th><th>Hạng mục</th><th>Tình trạng</th><th>Ghi chú</th><th>Thao tác</th></tr></thead>
          <tbody>{d.checks.map((c, i) => <tr key={c.key} className={c.done ? 'dim' : ''}>
            <td>{i + 1}</td><td><b>{c.title}</b></td>
            <td>{c.done ? <span className="pill green">Đã xong</span> : <span className="pill amber">{`Còn ${c.pending}${c.total != null ? `/${c.total}` : ''} mục`}</span>}</td>
            <td>{c.hint}</td><td><Link className={`btn sm${c.done ? '' : ' primary'}`} to={c.to}>{c.done ? 'Xem' : 'Mở'}</Link></td>
          </tr>)}</tbody>
        </table>
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
