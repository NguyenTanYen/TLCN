import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'

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

export function useProgram() {
  const progs = useApi('/api/programs').data
  const [pid, setPidState] = useState(() => Number(localStorage.getItem('tlcn_program')) || null)
  useEffect(() => {
    if (progs?.length && !progs.some(p => p.id === pid)) setPidState(progs[0].id)
  }, [progs, pid])
  const setPid = v => { localStorage.setItem('tlcn_program', String(v)); setPidState(Number(v)) }
  return { programs: progs, pid, setPid, program: progs?.find(p => p.id === pid) }
}
