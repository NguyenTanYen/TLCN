import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

// Tải dữ liệu từ API kèm trạng thái loading/error và hàm tải lại
export function useApi(path, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const load = useCallback(() => {
    if (!path) { setLoading(false); return Promise.resolve() }
    setLoading(true); setError(null)
    return api.get(path).then(setData).catch(e => setError(e.message)).finally(() => setLoading(false))
  }, [path])
  useEffect(() => { load() }, [load, ...deps])
  return { data, error, loading, reload: load, setData }
}
