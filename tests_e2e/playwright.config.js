const fs = require('fs')
const path = require('path')
const { defineConfig } = require('@playwright/test')

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
  fullyParallel: false,
  workers: 1,
  timeout: 5 * 60 * 1000,
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
    trace: 'on',
    screenshot: 'only-on-failure',
  },
})
