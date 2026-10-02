import { useEffect, useState } from 'react'
import { api, auth } from '../api'

const DEMO = [['gv.son', 'Gv@123456', 'Giảng viên'], ['admin', 'Admin@123', 'Quản trị']]

export default function Login() {
  const [f, setF] = useState({ username: '', password: '' })
  const [err, setErr] = useState('')
  // Tài khoản minh họa chỉ hiện khi chạy bản phát triển hoặc khi máy chủ bật DEMO_MODE (không lộ trên bản triển khai thật)
  const [demo, setDemo] = useState(import.meta.env.DEV)
  useEffect(() => { fetch('/api/public-config').then(r => r.json()).then(d => d.demo_mode && setDemo(true)).catch(() => {}) }, [])
  const submit = async e => {
    e.preventDefault(); setErr('')
    try { const r = await api.post('/api/auth/login', f); auth.set(r.access_token, r.user); window.location.assign('/') }
    catch (ex) { setErr(ex.message) }
  }
  return (
    <div className="login-bg">
      <form className="login" onSubmit={submit}>
        <div className="brand dark"><div className="logo">UTE</div><div><b>Hệ thống hỗ trợ kiểm tra, đánh giá</b><small>và phân tích mức độ đạt chuẩn đầu ra</small></div></div>
        <label className="field"><span>Tên đăng nhập</span><input autoFocus value={f.username} onChange={e => setF({ ...f, username: e.target.value })} /></label>
        <label className="field"><span>Mật khẩu</span><input type="password" value={f.password} onChange={e => setF({ ...f, password: e.target.value })} /></label>
        {err && <div className="alert red">{err}</div>}
        <button className="btn primary block">Đăng nhập</button>
        <p className="muted hint">Dành cho <b>giảng viên / bộ môn</b>. Từ Moodle, bấm nút <b>Phân tích CĐR</b> để vào thẳng không cần đăng nhập lại.
          Sinh viên làm bài và xem kết quả phân tích trên Moodle.</p>
        {demo && <div className="demo">
          <small className="muted">Tài khoản minh họa:</small>
          {DEMO.map(([u, p, r]) => <button type="button" key={u} className="chip" onClick={() => setF({ username: u, password: p })}>{r}: {u}</button>)}
        </div>}
      </form>
    </div>
  )
}
