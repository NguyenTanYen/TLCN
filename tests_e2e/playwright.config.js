// Cấu hình Playwright Test cho kiểm thử giao diện hệ thống phân tích CĐR (chạy trên hệ thống THẬT đang bật).
// Chuẩn bị: bật MariaDB, Apache (Moodle), chạy 5_CHAY_HE_THONG.bat, đã chạy bước 4 (dữ liệu demo trên Moodle).
// Chạy:  npx playwright test --ui                  (giao diện: chọn test, xem từng bước)
//        npx playwright test --grep-invert @moodle  (bỏ các flow cần Moodle thật)
const fs = require('fs')
const path = require('path')
const { defineConfig } = require('@playwright/test')

// Dùng Chromium đã có sẵn trong %LOCALAPPDATA%\ms-playwright nếu có (không bắt buộc tải thêm).
// Muốn dùng bản Chromium đúng phiên bản của Playwright: chạy "npx playwright install chromium" và đặt PW_DUNG_CHROMIUM_CHUAN=1.
function chromiumCoSan() {
  if (process.env.PW_DUNG_CHROMIUM_CHUAN) return undefined
  const base = path.join(process.env.LOCALAPPDATA || '', 'ms-playwright')
  if (!fs.existsSync(base)) return undefined
  const dirs = fs.readdirSync(base).filter(d => /^chromium-\d+$/.test(d)).sort((a, b) => Number(a.split('-')[1]) - Number(b.split('-')[1]))
  for (const d of dirs.reverse()) {
    const exe = path.join(base, d, 'chrome-win64', 'chrome.exe')
    if (fs.existsSync(exe)) return exe
  }
  return undefined
}

module.exports = defineConfig({
  testDir: './tests',
  // Các tệp chạy NỐI TIẾP theo thứ tự tên (01 Bộ môn → 02 Giảng viên → 03 Sinh viên) vì dùng chung dữ liệu
  fullyParallel: false,
  workers: 1,
  timeout: 5 * 60 * 1000,               // mỗi test là một flow dài (nhiều bước)
  expect: { timeout: 15000 },
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.UI_APP_URL || 'http://localhost:8000',
    browserName: 'chromium',
    launchOptions: { executablePath: chromiumCoSan() },
    viewport: { width: 1440, height: 900 },
    locale: 'vi-VN',
    acceptDownloads: true,
    actionTimeout: 15000,
    trace: 'on',                        // lưu vết từng thao tác để xem lại trong --ui / show-report
    screenshot: 'only-on-failure',
  },
})
