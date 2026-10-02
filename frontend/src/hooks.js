import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'

// Tải dữ liệu từ API kèm trạng thái loading/error và hàm tải lại.
// Khi đường dẫn đổi: xóa dữ liệu cũ ngay và bỏ qua phản hồi đến muộn của yêu cầu trước (tránh hiển thị nhầm lớp/bài KT).
export function useApi(path, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const seq = useRef(0)
  const load = useCallback(() => {
    const my = ++seq.current
    if (!path) { setData(null); setLoading(false); return Promise.resolve() }
    setLoading(true); setError(null)
    return api.get(path)
      .then(d => { if (my === seq.current) setData(d) })
      .catch(e => { if (my === seq.current) setError(e.message) })
      .finally(() => { if (my === seq.current) setLoading(false) })
  }, [path])
  useEffect(() => { setData(null) }, [path])
  useEffect(() => { load() }, [load, ...deps])
  return { data, error, loading, reload: load, setData }
}

// Năm học mặc định = năm học của lớp HP mới nhất (không cố định trong mã nguồn)
export function useDefaultYear() {
  const sems = useApi('/api/semesters').data
  const secs = useApi('/api/class-sections').data
  const years = useMemo(() => [...new Set((sems || []).map(s => s.academic_year))], [sems])
  const [year, setYear] = useState(null)
  useEffect(() => {
    if (year || !sems || !secs) return
    setYear(secs[0]?.academic_year || years[0] || null)
  }, [sems, secs, years, year])
  return { sems, years, year, setYear, latestSemesterId: secs?.[0]?.semester_id || sems?.[0]?.id }
}
