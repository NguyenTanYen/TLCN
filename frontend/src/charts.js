import { ArcElement, BarController, BarElement, CategoryScale, Chart, Filler, Legend, LinearScale, LineController, LineElement,
  PointElement, RadarController, RadialLinearScale, Tooltip } from 'chart.js'

Chart.register(ArcElement, BarController, BarElement, CategoryScale, Filler, Legend, LinearScale, LineController, LineElement,
  PointElement, RadarController, RadialLinearScale, Tooltip)
Chart.defaults.font.family = "'Segoe UI', Roboto, Arial, sans-serif"
Chart.defaults.color = '#475467'
export const C = { blue: '#1d4ed8', blueA: 'rgba(29,78,216,.25)', green: '#16a34a', red: '#dc2626', amber: '#d97706', gray: '#98a2b3', grayA: 'rgba(152,162,179,.25)' }

// Thang màu tuần tự một sắc độ (xanh nhạt → xanh đậm) cho bản đồ nhiệt mức đạt 0–100%
const LO = [239, 244, 255], HI = [29, 78, 216]
export function heat(pct) {
  const t = Math.max(0, Math.min(1, Number(pct) / 100))
  const c = LO.map((l, i) => Math.round(l + (HI[i] - l) * t))
  return { background: `rgb(${c.join(',')})`, color: t >= 0.55 ? '#fff' : '#101828' }
}
