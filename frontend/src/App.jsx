import { useEffect, useState } from 'react'
import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { auth } from './api'
import Login from './pages/Login'
import Sections from './pages/Sections'
import SectionDetail from './pages/SectionDetail'
import QuestionBank from './pages/QuestionBank'
import ExamDetail from './pages/ExamDetail'
import CloResults from './pages/CloResults'
import Program from './pages/Program'
import PiPlans from './pages/PiPlans'
import PloSummary from './pages/PloSummary'
import SystemPage from './pages/SystemPage'
import ClassStats from './pages/ClassStats'
import StudentProfile from './pages/StudentProfile'
import Courses from './pages/Courses'

const MENUS = {
  lecturer: [['/', 'Lớp học phần'], ['/courses', 'Học phần & CLO'], ['/questions', 'Ngân hàng câu hỏi']],
  admin: [['/', 'Lớp học phần'], ['/courses', 'Học phần & CLO'], ['/questions', 'Ngân hàng câu hỏi'], ['/program', 'CTĐT – PLO/PI'], ['/pi-plans', 'Kế hoạch đo PI (BM3b)'],
    ['/plo-summary', 'Tổng hợp PLO (BM2/BM3c)'], ['/system', 'Kết nối Moodle']],
}
const ROLE_VI = { admin: 'Quản trị / Bộ môn', lecturer: 'Giảng viên' }

function useMoodleUrl() {
  const [url, setUrl] = useState('')
  useEffect(() => { fetch('/api/public-config').then(r => r.json()).then(d => setUrl(d.moodle_url || '')).catch(() => {}) }, [])
  return url
}

function Shell({ user, children }) {
  const moodle = useMoodleUrl()
  return (
    <div className="shell">
      <aside className="side"><div className="side-in">
        <div className="brand"><div className="logo">UTE</div><div><b>Khảo thí &amp; CĐR</b><small>Đo lường theo OBE</small></div></div>
        <nav>{MENUS[user.role].map(([to, label]) => <NavLink key={to} to={to} end={to === '/'}>{label}</NavLink>)}</nav>
        <div className="side-foot">
          {moodle && <a className="btn ghost light block" href={moodle}>← Về Moodle</a>}
          <div className="who"><b>{user.full_name}</b><small>{ROLE_VI[user.role]}</small></div>
          <button className="btn ghost light" onClick={() => { auth.clear(); window.location.assign('/login') }}>Đăng xuất</button>
        </div>
      </div></aside>
      <main className="main">{children}</main>
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
  return <Shell user={user}><Routes>
    <Route path="/" element={<Sections />} />
    <Route path="/sections/:id" element={<SectionDetail />} />
    <Route path="/sections/:id/clo" element={<CloResults />} />
    <Route path="/sections/:id/stats" element={<ClassStats />} />
    <Route path="/sections/:cs/students/:sid" element={<StudentProfile />} />
    <Route path="/courses" element={<Courses />} />
    <Route path="/questions" element={<QuestionBank />} />
    <Route path="/exams/:id" element={<ExamDetail />} />
    {user.role === 'admin' && <>
      <Route path="/program" element={<Program />} />
      <Route path="/pi-plans" element={<PiPlans />} />
      <Route path="/plo-summary" element={<PloSummary />} />
      <Route path="/system" element={<SystemPage />} />
    </>}
    <Route path="*" element={<Navigate to="/" />} />
  </Routes></Shell>
}
