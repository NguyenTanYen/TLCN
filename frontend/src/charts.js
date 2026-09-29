import { ArcElement, BarElement, CategoryScale, Chart, Filler, Legend, LinearScale, LineElement,
  PointElement, RadialLinearScale, Tooltip } from 'chart.js'

Chart.register(ArcElement, BarElement, CategoryScale, Filler, Legend, LinearScale, LineElement, PointElement, RadialLinearScale, Tooltip)
Chart.defaults.font.family = "'Segoe UI', Roboto, Arial, sans-serif"
Chart.defaults.color = '#475467'
export const C = { blue: '#1d4ed8', blueA: 'rgba(29,78,216,.25)', green: '#16a34a', red: '#dc2626', amber: '#d97706', gray: '#98a2b3', grayA: 'rgba(152,162,179,.25)' }
