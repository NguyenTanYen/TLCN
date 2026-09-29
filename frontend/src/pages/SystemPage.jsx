import { api } from '../api'
import { ActionButton, Badge, Card, Loading } from '../components/ui'
import { useApi } from '../hooks'

export default function SystemPage() {
  const st = useApi('/api/system/moodle-status')
  const ws = useApi('/api/system/lms-status')
  const s = st.data, w = ws.data
  return (
    <>
      <div className="page-h"><div><h1>Kết nối Moodle</h1><p className="muted">Chiều đọc: bài làm của SV lấy trực tiếp từ CSDL Moodle (chỉ đọc) qua các view và thủ tục “cầu nối”.
        Chiều ghi: tạo Quiz, gửi kết quả phân tích qua Web Service chính thức của Moodle (plugin <code>local_clo</code>).</p></div></div>
      <Loading {...st} />
      {s && <Card title="Trạng thái">
        <table className="tbl"><tbody>
          <tr><td>CSDL Moodle</td><td><code>{s.moodle_db}</code></td><td>{s.moodle_available ? <Badge tone="green">Truy cập được</Badge> : <Badge tone="red">Không tìm thấy bảng quiz_attempts</Badge>}</td></tr>
          <tr><td>Cầu nối (view + <code>sp_sync_exam</code>)</td><td /><td>{s.bridge_installed ? <Badge tone="green">Đã cài</Badge> : <Badge tone="amber">Chưa cài</Badge>}</td></tr>
        </tbody></table>
        <ActionButton className="btn primary mt" disabled={!s.moodle_available} okMsg={r => `Đã cài ${r.statements} câu lệnh`}
          onRun={async () => { const r = await api.post('/api/system/install-bridge'); st.reload(); return r }}>Cài đặt / cập nhật cầu nối</ActionButton>
      </Card>}
      {w && <Card title="Web Service & đăng nhập một lần (plugin local_clo)">
        <table className="tbl"><tbody>
          <tr><td>Địa chỉ Moodle</td><td><code>{w.moodle_url || '—'}</code></td><td>{w.ws_ok ? <Badge tone="green">Kết nối được</Badge> : w.ws_configured ? <Badge tone="red">Lỗi</Badge> : <Badge tone="amber">Chưa cấu hình</Badge>}</td></tr>
          <tr><td>Dịch vụ</td><td colSpan="2">{w.site ? <>{w.site.sitename} · Moodle {w.site.release} · <code>{w.site.functions.join(', ')}</code></> : (w.error || 'Chạy 3_CAI_GIAO_DIEN_MOODLE.bat để cấu hình')}</td></tr>
          <tr><td>SSO từ nút “Phân tích CĐR”</td><td /><td>{w.sso_configured ? <Badge tone="green">Đã cấu hình</Badge> : <Badge tone="amber">Chưa cấu hình</Badge>}</td></tr>
        </tbody></table>
      </Card>}
    </>
  )
}
