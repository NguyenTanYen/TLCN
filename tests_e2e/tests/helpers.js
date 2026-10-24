// Hàm tiện ích dùng chung cho các kịch bản giao diện.
const fs = require('fs')
const path = require('path')
const { expect } = require('@playwright/test')

const APP = process.env.UI_APP_URL || 'http://localhost:8000'
const MOODLE = process.env.UI_MOODLE_URL || 'http://localhost:8081/moodle45'
const ROOT = path.resolve(__dirname, '..', '..')                 // thư mục dự án

// Tài khoản demo (dữ liệu mẫu của dự án – bước 2 và bước 4)
const ADMIN = ['admin', 'Admin@123']
const GV = ['gv.son', 'Gv@123456']
const GV_KHAC = ['gv.binh', 'Gv@123456']
const MOODLE_ADMIN = ['admin', 'Moodle@123456']
const SV_PASS = 'Sv@123456'
const DEMO = { code: 'DBMS330284', section: 'DBMS330284_01', moodleCourse: 7, finalExam: 'Thi cuối kỳ (Moodle)' }

// ---------------------------------------------------------------- dữ liệu dùng chung giữa các tệp (mã môn, id lớp…)
const STATE_FILE = path.join(__dirname, '..', '.state.json')
const loadState = () => (fs.existsSync(STATE_FILE) ? JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')) : {})
const saveState = s => fs.writeFileSync(STATE_FILE, JSON.stringify(s, null, 1))

// ---------------------------------------------------------------- phiên đăng nhập theo vai trò
async function newPage(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'vi-VN', acceptDownloads: true })
  return ctx.newPage()
}

/** Đăng nhập hệ thống qua màn hình đăng nhập: nhập tên, mật khẩu, bấm Đăng nhập, chờ thanh menu xuất hiện. */
async function login(page, [user, pass]) {
  await page.goto(APP + '/')
  await page.getByLabel('Tên đăng nhập').fill(user)
  await page.getByLabel('Mật khẩu').fill(pass)
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await page.locator('nav.mainnav').waitFor()
}

/** Đăng xuất Moodle (nếu đang đăng nhập) rồi đăng nhập Moodle bằng tài khoản khác. */
async function moodleLogin(page, [user, pass]) {
  await page.goto(MOODLE + '/login/logout.php')
  const btn = page.locator("form[action*='logout.php'] button[type=submit], form[action*='logout.php'] input[type=submit]")
  if (await btn.count()) await btn.first().click()
  await page.goto(MOODLE + '/login/index.php')
  await page.fill('#username', user)
  await page.fill('#password', pass)
  await page.click('#loginbtn')
  await page.waitForLoadState('domcontentloaded')
}

// ---------------------------------------------------------------- tìm phần tử
const nav = (page, name) => page.locator('nav.mainnav').getByRole('link', { name, exact: true })     // menu chính
const modal = page => page.locator('.modal').last()                                                   // hộp thoại trên cùng
const card = (page, title) => page.locator('section.card').filter({ has: page.locator('.card-h h3', { hasText: title }) }).first()
const tab = (page, name) => page.getByRole('tab', { name: new RegExp('^' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) })

/** Ô nhập / ô chọn theo ĐÚNG chữ nhãn (nhãn ngắn như "PI" bị trùng khi tìm bằng getByLabel). */
function field(scope, label) {
  const span = scope.page().locator('span', { hasText: new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`) })
  return scope.locator('label.field').filter({ has: span }).locator('input, select, textarea').first()
}

/** Chọn option có chứa chuỗi con (nhãn option thường kèm mã, VD "Nguyễn Thành Sơn (GV001)"); chờ danh sách tải xong. */
async function pick(select, text) {
  for (let i = 0; i < 40; i++) {
    const opts = await select.locator('option').evaluateAll(os => os.map(o => [o.value, o.textContent]))
    const hit = opts.find(([, t]) => t.includes(text))
    if (hit) return select.selectOption(hit[0])
    await select.page().waitForTimeout(250)
  }
  throw new Error(`Không có lựa chọn "${text}"`)
}

/** Chờ thông báo (toast) hoặc dòng chữ xuất hiện. */
const toast = (page, text, timeout = 15000) => expect(page.getByText(text).first()).toBeVisible({ timeout })
/** Khẳng định thấy nội dung trong một phạm vi (trang, khung, dòng bảng). */
const see = (scope, text, timeout = 10000) => expect(scope.getByText(text).first()).toBeVisible({ timeout })

/** Đóng mọi hộp thoại còn mở (Esc). */
async function closeModals(page) {
  for (let i = 0; i < 3 && await page.locator('.modal').count(); i++) await page.keyboard.press('Escape')
}

/** Mở một trang của hệ thống (đường dẫn tương đối), đóng hộp thoại cũ nếu có. */
async function goto(page, p) {
  await closeModals(page)
  await page.goto(APP + p)
}

/** Gọi API của hệ thống bằng phiên đang đăng nhập (chỉ để LẤY id cần cho bước sau, không thay cho kiểm tra giao diện). */
async function api(page, p) {
  return page.evaluate(async url => {
    const r = await fetch(url, { headers: { Authorization: 'Bearer ' + localStorage.getItem('tlcn_token') } })
    if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`)
    return r.json()
  }, p)
}

module.exports = { APP, MOODLE, ROOT, ADMIN, GV, GV_KHAC, MOODLE_ADMIN, SV_PASS, DEMO, loadState, saveState, newPage, login,
  moodleLogin, nav, modal, card, tab, field, pick, toast, see, closeModals, goto, api }
