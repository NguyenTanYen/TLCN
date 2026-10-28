import { useEffect, useState } from 'react'
import { api } from './api'

let cache = null
// Địa chỉ Moodle (để tạo liên kết lớp HP ⇄ khóa học Moodle)
export function useMoodleBase() {
  const [url, setUrl] = useState(cache || '')
  useEffect(() => {
    if (cache !== null) return
    fetch('/api/public-config').then(r => r.json()).then(d => { cache = (d.moodle_url || '').replace(/\/$/, ''); setUrl(cache) }).catch(() => {})
  }, [])
  return url
}

// Mở Moodle bằng đúng tài khoản đang dùng ở hệ thống (vé SSO 120 giây); lỗi thì mở địa chỉ Moodle thường.
export function openMoodle(path = '/') {
  const w = window.open('', '_blank')              // mở trước để trình duyệt không chặn cửa sổ bật lên
  const go = u => { if (w) w.location.href = u; else window.location.assign(u) }
  api.post('/api/auth/moodle-ticket', { next: path }).then(r => go(r.url)).catch(() => go((cache || '') + path))
}
