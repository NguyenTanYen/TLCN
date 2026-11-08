import { useEffect, useState } from 'react'
import { api } from './api'

let cache = null
export function useMoodleBase() {
  const [url, setUrl] = useState(cache || '')
  useEffect(() => {
    if (cache !== null) return
    fetch('/api/public-config').then(r => r.json()).then(d => { cache = (d.moodle_url || '').replace(/\/$/, ''); setUrl(cache) }).catch(() => {})
  }, [])
  return url
}

export function openMoodle(path = '/') {
  const w = window.open('', '_blank')
  const go = u => { if (w) w.location.href = u; else window.location.assign(u) }
  api.post('/api/auth/moodle-ticket', { next: path }).then(r => go(r.url)).catch(() => go((cache || '') + path))
}
