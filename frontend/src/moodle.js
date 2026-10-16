import { useEffect, useState } from 'react'

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
