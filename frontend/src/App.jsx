import { useEffect, useRef, useState } from 'react'
import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { auth } from './api'
import Login from './pages/Login'
import Sections from './pages/Sections'
import SectionDetail from './pages/SectionDetail'
import QuestionBank from './pages/QuestionBank'
import ExamDetail from './pages/ExamDetail'
import CloResults from './pages/CloResults'
import PiPlans from './pages/PiPlans'
import PloSummary from './pages/PloSummary'
import SystemPage from './pages/SystemPage'
import ClassStats from './pages/ClassStats'
import StudentProfile from './pages/StudentProfile'
import MyCourses from './pages/MyCourses'
import CourseHome from './pages/CourseHome'
import CourseList from './pages/CourseList'
import { ProgramDetail, ProgramList } from './pages/Programs'
import Remedial from './pages/Remedial'
import Guide from './components/Help'

// Điều hướng theo vai trò: GV làm việc theo Môn học → các lớp → bài kiểm tra; Bộ môn quản lý theo CTĐT → học phần → CLO
const MENUS = {
  lecturer: [['/', 'Môn học của tôi', ['/courses', '/sections', '/exams']], ['/questions', 'Ngân hàng câu hỏi'], ['/programs', 'Chương trình đào tạo'], ['/huong-dan', 'Hướng dẫn sử dụng']],
  admin: [['/programs', 'Chương trình đào tạo'], ['/courses', 'Học phần'], ['/sections', 'Lớp học phần', ['/exams']], ['/questions', 'Ngân hàng câu hỏi'],
    ['/pi-plans', 'Kế hoạch đo chỉ báo (PI)'], ['/plo-summary', 'Kết quả chương trình (PLO)'], ['/system', 'Kết nối Moodle'], ['/huong-dan', 'Hướng dẫn sử dụng']],
}
const ROLE_VI = { admin: 'Bộ môn / Quản trị', lecturer: 'Giảng viên' }

function useMoodleUrl() {
  const [url, setUrl] = useState('')
  useEffect(() => { fetch('/api/public-config').then(r => r.json()).then(d => setUrl(d.moodle_url || '')).catch(() => {}) }, [])
  return url
}

function UserMenu({ user, moodle }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    const close = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  const initials = (user.full_name || user.username).split(' ').filter(Boolean).slice(-2).map(w => w[0]).join('').toUpperCase()
  return <div className="usermenu" ref={ref}>
    <button className="userchip" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(o => !o)}>
      <span className="avatar">{initials}</span>
      <span className="uname"><b>{user.full_name}</b><small>{ROLE_VI[user.role]}</small></span>
      <span aria-hidden="true">▾</span>
    </button>
    {open && <div className="menu-pop" role="menu">
      <div className="menu-h"><b>{user.full_name}</b><small>{user.username} · {ROLE_VI[user.role]}</small></div>
      {moodle && <a role="menuitem" href={moodle}>↗ Mở Moodle</a>}
      <button role="menuitem" onClick={() => { auth.clear(); window.location.assign('/login') }}>Đăng xuất</button>
    </div>}
  </div>
}

function Shell({ user, children }) {
  const moodle = useMoodleUrl()
  const loc = useLocation()
  const active = ([to, , also]) => (to === '/' ? loc.pathname === '/' : loc.pathname.startsWith(to)) || (also || []).some(p => loc.pathname.startsWith(p))
  return (
    <div className="app">

      <header className="topbar">
        <div className="topbar-in">
          <NavLink to="/" className="brand"><span className="logo">UTE</span><span><b>Đánh giá chuẩn đầu ra</b><small>Hỗ trợ giảng viên và Bộ môn</small></span></NavLink>
          <nav className="mainnav" aria-label="Chức năng">
            {MENUS[user.role].map(m => <NavLink key={m[0]} to={m[0]} className={() => (active(m) ? 'active' : '')} end={m[0] === '/'}>{m[1]}</NavLink>)}
          </nav>
          <div className="topbar-r">
            <UserMenu user={user} moodle={moodle} />
          </div>
        </div>
      </header>
      <main className="main">{children}</main>
      <footer className="sitefoot"><div className="sitefoot-in"><span>Hệ thống đánh giá chuẩn đầu ra học phần · Khoa Công nghệ Thông tin, Trường Đại học Công nghệ Kỹ thuật TP.HCM</span><NavLink to="/huong-dan">Hướng dẫn sử dụng</NavLink></div></footer>
    </div>
  )
}

export default function App() {
  const user = auth.user()
  if (!auth.token || !user) return <Routes><Route path="*" element={<Login />} /></Routes>
  if (!MENUS[user.role]) {  // sinh viên: xem kết quả trên Moodle
    auth.clear()
    return <Routes><Route path="*" element={<Login />} /></Routes>
  }
  const admin = user.role === 'admin'
  return <Shell user={user}><Routes>
    <Route path="/" element={admin ? <Navigate to="/programs" replace /> : <MyCourses />} />
    <Route path="/courses" element={admin ? <CourseList /> : <MyCourses />} />
    <Route path="/courses/:id" element={<CourseHome />} />
    <Route path="/programs" element={<ProgramList />} />
    <Route path="/programs/:id" element={<ProgramDetail />} />
    <Route path="/sections" element={<Sections />} />
    <Route path="/sections/:id" element={<SectionDetail />} />
    <Route path="/sections/:id/clo" element={<CloResults />} />
    <Route path="/sections/:id/stats" element={<ClassStats />} />
    <Route path="/sections/:id/remedial" element={<Remedial />} />
    <Route path="/sections/:cs/students/:sid" element={<StudentProfile />} />
    <Route path="/questions" element={<QuestionBank />} />
    <Route path="/huong-dan" element={<Guide />} />
    <Route path="/exams/:id" element={<ExamDetail />} />
    {admin && <>
      <Route path="/pi-plans" element={<PiPlans />} />
      <Route path="/plo-summary" element={<PloSummary />} />
      <Route path="/system" element={<SystemPage />} />
    </>}
    <Route path="*" element={<Navigate to="/" />} />
  </Routes></Shell>
}
