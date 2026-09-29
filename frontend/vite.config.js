import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Trong môi trường dev, mọi lời gọi /api được chuyển tới FastAPI (cổng 8000)
export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 800 },
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
})
