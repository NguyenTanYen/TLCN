// Biểu đồ dùng chung theo quy ước trình bày khoa học: trục có tên và đơn vị, ghi cỡ mẫu n, chỉ tiêu là vạch riêng,
// tỷ lệ kèm khoảng tin cậy Wilson 95%, bảng màu an toàn cho người mù màu (Okabe–Ito) và không dựa vào màu đơn thuần.
import { Bar, Scatter } from 'react-chartjs-2'
import '../charts'

export const OK = { ok: '#0072B2', no: '#D55E00', warn: '#E69F00', neutral: '#56B4E9', ink: '#344054', target: '#101828' }

/** Khoảng tin cậy Wilson cho tỷ lệ k/n (%, 95%). */
export function wilson(k, n, z = 1.96) {
  if (!n) return [0, 0]
  const p = k / n, z2 = z * z, d = 1 + z2 / n
  const c = (p + z2 / (2 * n)) / d, h = (z * Math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / d
  return [Math.max(0, 100 * (c - h)), Math.min(100, 100 * (c + h))]
}

const grid = { color: 'rgba(16,24,40,.08)' }
const axisTitle = text => ({ display: true, text, color: OK.ink, font: { weight: '600' } })

// vạch chỉ tiêu (đoạn ngang đen trên từng cột) và khoảng tin cậy (râu), vẽ sau khi vẽ cột
const overlay = {
  id: 'overlay',
  afterDatasetsDraw(chart, _a, opts) {
    const { ctx, scales: { x, y } } = chart
    const meta = chart.getDatasetMeta(0)
    ctx.save()
    meta.data.forEach((bar, i) => {
      const w = bar.width || 30
      if (opts.ci?.[i]) {
        const [lo, hi] = opts.ci[i]
        ctx.strokeStyle = OK.ink; ctx.lineWidth = 1.5
        ctx.beginPath(); ctx.moveTo(bar.x, y.getPixelForValue(lo)); ctx.lineTo(bar.x, y.getPixelForValue(hi))
        ctx.moveTo(bar.x - 5, y.getPixelForValue(lo)); ctx.lineTo(bar.x + 5, y.getPixelForValue(lo))
        ctx.moveTo(bar.x - 5, y.getPixelForValue(hi)); ctx.lineTo(bar.x + 5, y.getPixelForValue(hi)); ctx.stroke()
      }
      if (opts.target?.[i] != null) {
        const ty = y.getPixelForValue(opts.target[i])
        ctx.strokeStyle = OK.target; ctx.lineWidth = 2.5; ctx.setLineDash([6, 3])
        ctx.beginPath(); ctx.moveTo(bar.x - w * 0.75, ty); ctx.lineTo(bar.x + w * 0.75, ty); ctx.stroke(); ctx.setLineDash([])
      }
      if (opts.labels?.[i]) {
        ctx.fillStyle = OK.ink; ctx.font = '600 12px Segoe UI, Roboto, Arial, sans-serif'; ctx.textAlign = 'center'
        const top = Math.min(bar.y, opts.ci?.[i] ? y.getPixelForValue(opts.ci[i][1]) : bar.y)
        ctx.fillText(opts.labels[i], bar.x, Math.max(top - 6, 12))
      }
    })
    ctx.restore()
  },
}

export function Legend({ items }) {
  return <ul className="chart-legend">{items.map(([k, label, kind]) => <li key={k}>
    <i className={`lg ${kind || 'box'}`} style={{ '--c': OK[k] || k }} />{label}</li>)}</ul>
}

/** Tỷ lệ đạt theo nhóm (CLO, PLO…). items: [{label, k, n, target}] – k = số đạt, n = số được đánh giá. */
export function AttainmentChart({ items, xTitle, yTitle = 'Tỷ lệ sinh viên đạt (%)', height = 300 }) {
  const pct = items.map(i => i.n ? 100 * i.k / i.n : 0)
  const reached = items.map((i, j) => i.n && pct[j] + 1e-9 >= i.target)
  const data = { labels: items.map(i => i.label), datasets: [{ label: 'Tỷ lệ đạt', data: pct.map(v => Math.round(v * 100) / 100),
    backgroundColor: reached.map(r => r ? OK.ok : OK.no), maxBarThickness: 64,
    // họa tiết gạch chéo cho cột chưa đạt để không chỉ dựa vào màu
    borderColor: reached.map(r => r ? OK.ok : OK.no), borderWidth: 1 }] }
  const options = { maintainAspectRatio: false, animation: false,
    layout: { padding: { top: 22 } },
    scales: { y: { min: 0, max: 100, grid, title: axisTitle(yTitle), ticks: { stepSize: 20, callback: v => `${v}` } },
      x: { grid: { display: false }, title: xTitle ? axisTitle(xTitle) : { display: false } } },
    plugins: { legend: { display: false },
      overlay: { ci: items.map(i => wilson(i.k, i.n)), target: items.map(i => i.target), labels: items.map((i, j) => i.n ? `${pct[j].toFixed(1)}%` : '') },
      tooltip: { callbacks: { label: c => { const i = items[c.dataIndex]; const [lo, hi] = wilson(i.k, i.n)
        return [`${i.k}/${i.n} SV đạt = ${pct[c.dataIndex].toFixed(1)}%`, `Khoảng tin cậy 95%: ${lo.toFixed(1)}–${hi.toFixed(1)}%`, `Chỉ tiêu: ${i.target}% · ${reached[c.dataIndex] ? 'đạt' : 'chưa đạt'}`] } } } } }
  return <figure className="chart-fig">
    <div className="chart" style={{ height }}><Bar data={data} options={options} plugins={[overlay]} /></div>
    <Legend items={[['ok', 'Đạt chỉ tiêu'], ['no', 'Chưa đạt chỉ tiêu'], ['target', 'Chỉ tiêu (vạch đứt)', 'dash'], ['ink', 'Khoảng tin cậy 95% (Wilson)', 'whisker']]} />
    <figcaption className="muted small">Số trên cột là tỷ lệ đạt. Râu là khoảng tin cậy 95%: càng dài thì số sinh viên được đánh giá càng ít, kết luận càng kém chắc chắn. Rê chuột vào cột để xem số sinh viên (n) và khoảng tin cậy.</figcaption>
  </figure>
}

/** Phổ điểm: cột liền nhau (histogram), trục có tên và đơn vị. */
export function Histogram({ labels, counts, xTitle = 'Khoảng điểm', yTitle = 'Số sinh viên', height = 260 }) {
  const n = counts.reduce((a, b) => a + b, 0)
  return <figure className="chart-fig">
    <div className="chart" style={{ height }}><Bar data={{ labels, datasets: [{ label: 'Số sinh viên', data: counts, backgroundColor: OK.neutral, borderColor: OK.ok, borderWidth: 1, categoryPercentage: 1, barPercentage: 1 }] }}
      options={{ maintainAspectRatio: false, animation: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${c.raw} SV (${n ? (100 * c.raw / n).toFixed(1) : 0}%)` } } },
        scales: { y: { beginAtZero: true, grid, ticks: { precision: 0 }, title: axisTitle(yTitle) }, x: { grid: { display: false }, title: axisTitle(xTitle) } } }} /></div>
    <figcaption className="muted small">n = {n} sinh viên dự thi.</figcaption>
  </figure>
}

const CLS = (p, di) => di == null ? 'none' : di < 0 ? 'neg' : di < 0.2 ? 'low' : p > 0.85 ? 'easy' : p < 0.25 ? 'hard' : 'good'
const CLS_STYLE = { neg: [OK.no, 'triangle', 'DI âm – kiểm tra đáp án'], low: [OK.warn, 'rectRot', 'DI thấp (< 0,2)'], easy: [OK.neutral, 'rect', 'Quá dễ (p > 0,85)'],
  hard: [OK.neutral, 'crossRot', 'Quá khó (p < 0,25)'], good: [OK.ok, 'circle', 'Tốt'], none: ['#98a2b3', 'circle', 'Chưa đủ dữ liệu'] }

// vùng chuẩn: p ∈ [0,25; 0,85], DI ≥ 0,3 (tốt), DI = 0,2 (ngưỡng chấp nhận)
const zones = {
  id: 'zones',
  beforeDatasetsDraw(chart) {
    const { ctx, scales: { x, y }, chartArea: a } = chart
    ctx.save()
    ctx.fillStyle = 'rgba(0,114,178,.07)'
    ctx.fillRect(x.getPixelForValue(0.25), y.getPixelForValue(1), x.getPixelForValue(0.85) - x.getPixelForValue(0.25), y.getPixelForValue(0.3) - y.getPixelForValue(1))
    ctx.strokeStyle = 'rgba(16,24,40,.45)'; ctx.setLineDash([5, 4]); ctx.lineWidth = 1
    for (const v of [0.2, 0.3]) { ctx.beginPath(); ctx.moveTo(a.left, y.getPixelForValue(v)); ctx.lineTo(a.right, y.getPixelForValue(v)); ctx.stroke() }
    for (const v of [0.25, 0.85]) { ctx.beginPath(); ctx.moveTo(x.getPixelForValue(v), a.top); ctx.lineTo(x.getPixelForValue(v), a.bottom); ctx.stroke() }
    ctx.setLineDash([]); ctx.strokeStyle = 'rgba(16,24,40,.8)'; ctx.beginPath(); ctx.moveTo(a.left, y.getPixelForValue(0)); ctx.lineTo(a.right, y.getPixelForValue(0)); ctx.stroke()
    ctx.restore()
  },
}

/** Phân tích câu hỏi: mỗi câu là một điểm (độ khó p, độ phân biệt DI), tô theo phân loại, kèm vùng chuẩn. data: [{order_index, p_value, di_value}] */
export function ItemScatter({ data, height = 360 }) {
  const pts = data.filter(d => d.p_value != null && d.di_value != null)
  const groups = Object.keys(CLS_STYLE).map(k => ({ k, rows: pts.filter(d => CLS(Number(d.p_value), Number(d.di_value)) === k) })).filter(g => g.rows.length)
  const ds = groups.map(g => ({ label: CLS_STYLE[g.k][2], data: g.rows.map(d => ({ x: Number(d.p_value), y: Number(d.di_value), q: d.order_index })),
    backgroundColor: CLS_STYLE[g.k][0], borderColor: '#fff', borderWidth: 1, pointStyle: CLS_STYLE[g.k][1], pointRadius: 7, pointHoverRadius: 9 }))
  return <figure className="chart-fig">
    <div className="chart" style={{ height }}><Scatter data={{ datasets: ds }} plugins={[zones]}
      options={{ maintainAspectRatio: false, animation: false,
        scales: { x: { min: 0, max: 1, grid, title: axisTitle('Độ khó p (tỷ lệ làm đúng; càng gần 1 càng dễ)') },
          y: { min: -1, max: 1, grid, title: axisTitle('Độ phân biệt DI') } },
        plugins: { legend: { position: 'bottom', labels: { usePointStyle: true } },
          tooltip: { callbacks: { label: c => `Câu ${c.raw.q}: p = ${c.raw.x}, DI = ${c.raw.y}` } } } }} /></div>
    <figcaption className="muted small">Mỗi điểm là một câu. Vùng xanh nhạt là vùng lý tưởng (p từ 0,25 đến 0,85 và DI ≥ 0,3). Các đường nét đứt ngang ở DI = 0,2 và 0,3. Câu nằm dưới 0 nghĩa là sinh viên giỏi làm sai nhiều hơn sinh viên yếu: nên kiểm tra lại đáp án.</figcaption>
  </figure>
}
