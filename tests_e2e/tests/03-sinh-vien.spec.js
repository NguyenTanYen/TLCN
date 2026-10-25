// VAI TRÒ SINH VIÊN – 5 flow SV1..SV5. Sinh viên KHÔNG dùng hệ thống phân tích: làm bài và xem kết quả trên Moodle.
// Chạy sau tệp 02 (dùng bài phụ đạo GV14 đã tạo Quiz trên Moodle cho 2 SV). Lớp demo DBMS330284_01 – khóa học Moodle id 7.
// Moodle đang dùng giao diện tiếng Anh nên câu thông báo của plugin local_clo là tiếng Anh.
// Trong mỗi test: `page` = phiên giảng viên gv.son trên hệ thống (để công bố, đồng bộ); `sv` = phiên Moodle của sinh viên.
const { test, expect } = require('@playwright/test')
const H = require('./helpers')
const { card, toast, see, goto, api } = H

const SV_CO_KET_QUA = '22130011'      // SV có làm bài thi cuối kỳ (dữ liệu demo)
const SV_VANG = '22130004'            // SV vắng thi cuối kỳ
const RESULTS_URL = `${H.MOODLE}/local/clo/results.php?id=${H.DEMO.moodleCourse}`

test.describe.configure({ mode: 'serial' })
const S = H.loadState()

test.beforeEach(async ({ page }) => { await H.login(page, H.GV) })

/** Trang Quiz trên Moodle của một bài KT (mod/quiz/view.php?q=<id Quiz>). */
async function quizUrl(page, examId) {
  const e = await api(page, `/api/exams/${examId}`)
  return `${H.MOODLE}/mod/quiz/view.php?q=${e.moodle_quiz_id}`
}

/** id bài "Thi cuối kỳ (Moodle)" của lớp demo. */
async function finalExamId(page) {
  const sections = await api(page, '/api/class-sections')
  const cs = sections.find(x => x.section_code === H.DEMO.section).id
  return (await api(page, `/api/class-sections/${cs}/exams`)).find(e => e.exam_title === H.DEMO.finalExam).id
}

// ================================================================== SV1 – Không đăng nhập hệ thống phân tích
test('SV1 – SV đăng nhập hệ thống bằng MSSV → bị từ chối, hướng dẫn xem trên Moodle', async ({ browser }) => {
  const sv = await H.newPage(browser)
  await test.step('Bước 1: trang đăng nhập hệ thống → MSSV 22130017 / mật khẩu SV → Đăng nhập', async () => {
    await sv.goto(H.APP + '/')
    await sv.getByLabel('Tên đăng nhập').fill('22130017')
    await sv.getByLabel('Mật khẩu').fill(H.SV_PASS)
    await sv.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  })
  await test.step('Bước 2: thông báo từ chối có nhắc Moodle; không vào được trang trong', async () => {
    await toast(sv, /Moodle/)
    await expect(sv.locator('nav.mainnav')).toHaveCount(0)
  })
  await sv.context().close()
})

// ================================================================== SV3 – Chỉ SV được giao thấy Quiz phụ đạo
test('SV3 – Nhóm Moodle "Ôn tập" gồm đúng 2 SV; SV không được giao không làm được Quiz phụ đạo @moodle', async ({ page, browser }) => {
  test.skip(!S.remedialExam, 'Chưa có bài phụ đạo – chạy GV14 (tệp 02) trước')
  const url = await quizUrl(page, S.remedialExam)
  const sv = await H.newPage(browser)
  await test.step('Bước 1: admin Moodle → Nhóm của khóa học → nhóm "Ôn tập – …" có đúng 2 SV được giao', async () => {
    await H.moodleLogin(sv, H.MOODLE_ADMIN)
    await sv.goto(`${H.MOODLE}/group/overview.php?id=${H.DEMO.moodleCourse}`)
    const group = sv.locator('table').filter({ hasText: 'Ôn tập' }).last()
    for (const code of S.remedialStudents) await expect(group).toContainText(code)
  })
  await test.step('Bước 2: SV KHÔNG được giao đăng nhập Moodle, mở thẳng trang Quiz phụ đạo → không có nút làm bài', async () => {
    const other = ['22130040', '22130039', '22130038'].find(c => !S.remedialStudents.includes(c))
    await H.moodleLogin(sv, [other, H.SV_PASS])
    await sv.goto(url)
    await expect(sv.getByRole('button', { name: /Attempt quiz/ })).toHaveCount(0)
    await expect(sv.locator('body')).toContainText(/not available|restricted|belong|group/i)
  })
  await sv.context().close()
})

// ================================================================== SV2 – SV làm Quiz, GV thấy tiến bộ
test('SV2 – SV được giao làm Quiz phụ đạo trên Moodle; GV đồng bộ → thời gian làm bài và bảng tiến bộ @moodle', async ({ page, browser }) => {
  test.skip(!S.remedialExam, 'Chưa có bài phụ đạo – chạy GV14 (tệp 02) trước')
  const url = await quizUrl(page, S.remedialExam)
  const code = S.remedialStudents[0]
  const sv = await H.newPage(browser)
  await test.step('Bước 1: SV được giao đăng nhập Moodle → mở Quiz phụ đạo → "Attempt quiz" (xác nhận nếu Moodle hỏi)', async () => {
    await H.moodleLogin(sv, [code, H.SV_PASS])
    await sv.goto(url)
    await sv.getByRole('button', { name: /Attempt quiz|Continue your attempt/ }).click()
    const start = sv.locator('#id_submitbutton, .modal-footer button.btn-primary')
    if (await start.count() && await start.first().isVisible()) await start.first().click()
  })
  await test.step('Bước 2: mỗi trang 1 câu → chọn phương án đầu tiên → "Next page" … tới trang tổng kết', async () => {
    for (let i = 0; i < 60 && !sv.url().includes('summary.php'); i++) {
      await sv.waitForLoadState('domcontentloaded')
      const radios = sv.locator('.answer input[type=radio]')
      if (await radios.count()) await radios.first().check()
      await sv.locator('#mod_quiz-next-nav').click()
    }
    expect(sv.url()).toContain('summary.php')
  })
  await test.step('Bước 3: "Submit all and finish" → xác nhận → bài được nộp (trang xem lại bài)', async () => {
    await sv.getByRole('button', { name: 'Submit all and finish' }).first().click()
    await sv.locator('.modal-dialog').getByRole('button', { name: 'Submit all and finish' }).click()
    await sv.waitForURL(/review\.php/, { timeout: 30000 })
  })
  await sv.context().close()
  await test.step('Bước 4: GV mở bài phụ đạo trên hệ thống → "⟳ Lấy bài làm & phân tích" → đọc được bài làm', async () => {
    await goto(page, `/exams/${S.remedialExam}`)
    await page.getByRole('button', { name: /Lấy bài làm & phân tích/ }).click()
    await toast(page, /Đồng bộ \d+ bài làm/, 60000)
  })
  await test.step('Bước 5: thẻ "Thời gian làm bài" có dữ liệu của SV (Quiz 1 câu/trang → thời gian từng câu)', async () => {
    await page.getByRole('button', { name: /Thời gian làm bài/ }).click()
    await see(page, code, 15000)
  })
  await test.step('Bước 6: trang Phụ đạo → khung tiến bộ: SV "Đã nộp", cột "Thay đổi" có số (sau – trước)', async () => {
    const e = await api(page, `/api/exams/${S.remedialExam}`)
    await goto(page, `/sections/${e.class_section_id}/remedial`)
    const box = card(page, 'Bài ôn tập đã giao').locator('details').filter({ has: page.locator(`a[href='/exams/${S.remedialExam}']`) })
    await box.locator('summary').click()
    const row = box.locator('tr').filter({ hasText: code })
    await see(row, 'Đã nộp')
    await expect(row.locator('td').nth(6)).not.toHaveText('—')
  })
})

// ================================================================== SV4 + SV5 – Xem kết quả, thông báo
test('SV4 + SV5 – Trang "Learning outcome results": công bố / vắng thi / thu hồi; thông báo khi GV công bố @moodle', async ({ page, browser }) => {
  const eid = await finalExamId(page)
  const sv = await H.newPage(browser)
  const gvToggle = async published => {           // GV bấm Công bố / Thu hồi cho tới trạng thái mong muốn
    await goto(page, `/exams/${eid}`)
    const name = published ? 'Công bố kết quả lên Moodle' : 'Thu hồi công bố'
    await expect(page.getByRole('button', { name: /Thu hồi công bố|Công bố kết quả lên Moodle/ }).first()).toBeVisible()
    if (await page.getByRole('button', { name }).count()) {
      await page.getByRole('button', { name }).first().click()
      await toast(page, /Moodle đã nhận/, 60000)
    }
  }
  await test.step('Bước 1: GV đảm bảo bài thi cuối kỳ đang được công bố', async () => { await gvToggle(true) })
  await test.step('Bước 2: SV có làm bài → Moodle → "Learning outcome results" → thấy bài thi, không bị bảo lưu', async () => {
    await H.moodleLogin(sv, [SV_CO_KET_QUA, H.SV_PASS])
    await sv.goto(RESULTS_URL)
    await see(sv, H.DEMO.finalExam)
    await expect(sv.getByText('withheld')).toHaveCount(0)
  })
  await test.step('Bước 3 (SV5): trang thông báo của SV có "Learning outcome results available: …"', async () => {
    await sv.goto(`${H.MOODLE}/message/output/popup/notifications.php`)
    await see(sv, 'Learning outcome results available', 15000)
  })
  await test.step('Bước 4: SV vắng thi → "Not enough evidence to assess"', async () => {
    await H.moodleLogin(sv, [SV_VANG, H.SV_PASS])
    await sv.goto(RESULTS_URL)
    await see(sv, 'Not enough evidence to assess')
  })
  await test.step('Bước 5: GV thu hồi công bố → SV có làm bài tải lại trang → "results are withheld"', async () => {
    await gvToggle(false)
    await H.moodleLogin(sv, [SV_CO_KET_QUA, H.SV_PASS])
    await sv.goto(RESULTS_URL)
    await see(sv, 'withheld')
  })
  await test.step('Bước 6: GV công bố lại (trả dữ liệu demo như cũ) → SV xem lại được kết quả', async () => {
    await gvToggle(true)
    await sv.reload()
    await expect(sv.getByText('withheld')).toHaveCount(0)
  })
  await sv.context().close()
})
