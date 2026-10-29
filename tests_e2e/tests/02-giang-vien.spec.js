// VAI TRÒ GIẢNG VIÊN (gv.son) – 15 flow GV1..GV15, chạy sau tệp 01 (dùng học phần, lớp mà Bộ môn vừa tạo – .state.json).
// Trên học phần kiểm thử (lớp UIxxxxxx_01, chưa có khóa học Moodle): SV, ngân hàng câu hỏi, đề trực tuyến, đề giấy chấm trên
// hệ thống, bài nhập điểm, kết quả CLO, rubric.
// Các flow @moodle dùng môn demo DBMS330284 / lớp DBMS330284_01 (khóa học Moodle id 7): SSO, đồng bộ SV, đồng bộ câu hỏi
// 2 chiều, đồng bộ bài làm, phụ đạo (tạo Quiz + giới hạn SV), công bố kết quả.
const fs = require('fs')
const os = require('os')
const path = require('path')
const { execFileSync } = require('child_process')
const { test, expect } = require('@playwright/test')
const H = require('./helpers')
const { nav, modal, card, tab, field, pick, toast, see, goto, api } = H

// MSSV 8 chữ số như MSSV thật – phiếu trả lời giấy chỉ tô được chữ số
const STUDENTS = [['26990001', 'Nguyễn Văn An'], ['26990002', 'Trần Thị Bình'], ['26990003', 'Lê Văn Cường'],
  ['26990004', 'Phạm Thị Dung'], ['26990005', 'Hoàng Văn Em']]
const TMP = os.tmpdir()

test.describe.configure({ mode: 'serial' })
const S = H.loadState()

test.beforeEach(async ({ page }) => {
  test.skip(!S.cid || !S.cs, 'Chưa có học phần kiểm thử – chạy tệp 01-bo-mon trước')
  await H.login(page, H.GV)                    // mỗi test đăng nhập giảng viên gv.son
})
test.afterEach(() => H.saveState(S))

/** id môn và lớp demo DBMS330284 / DBMS330284_01 – lấy qua API của chính GV đang đăng nhập. */
async function demoIds(page) {
  const sections = await api(page, '/api/class-sections')
  const s = sections.find(x => x.section_code === H.DEMO.section)
  return { cid: s.course_id, cs: s.id }
}

/** Ngân hàng câu hỏi → "+ Thêm câu hỏi": nội dung, chương, Bloom, 4 phương án (A đúng), tích CLO → Lưu. */
async function addQuestion(page, content, chapter, bloom, clo) {
  await page.getByRole('button', { name: '+ Thêm câu hỏi' }).click()
  const m = modal(page)
  await m.getByLabel('Nội dung câu hỏi').fill(content)
  await pick(m.getByLabel('Chương (đề cương)'), `Chương ${chapter}.`)
  await pick(m.getByLabel('Mức Bloom'), bloom)
  const opts = await m.locator('.opt input.grow').all()                   // 4 ô phương án; A mặc định là đáp án đúng
  for (const [i, o] of opts.entries()) await o.fill(`Phương án ${'ABCD'[i]} – ${content.slice(0, 30)}`)
  await m.locator('.clo-w').filter({ has: page.locator('b', { hasText: clo }) }).locator('input[type=checkbox]').check()
  await m.getByRole('button', { name: 'Lưu' }).click()
  await toast(page, 'Đã lưu câu hỏi')
}

/** Lấy id bài KT từ địa chỉ trang /exams/<id>. */
const examIdFromUrl = page => Number(page.url().match(/\/exams\/(\d+)/)[1])

// ================================================================== GV1 – Đăng nhập
test('GV1 – Giảng viên đăng nhập: menu chỉ có mục của GV', async ({ page }) => {
  await test.step('Bước 1: có Môn học của tôi, Ngân hàng câu hỏi, Chương trình đào tạo', async () => {
    for (const item of ['Tổng quan', 'Môn học của tôi', 'Ngân hàng câu hỏi', 'Chương trình đào tạo']) await expect(nav(page, item)).toBeVisible()
  })
  await test.step('Bước 1b: trang chủ là Tổng quan, có "Việc cần làm" và "Làm ngay" dẫn đến đúng trang', async () => {
    await goto(page, '/')
    await see(page, 'Việc cần làm')
    await see(page, 'Quy trình một bài kiểm tra')
    const first = page.locator('a.todo').first()
    await expect(first).toBeVisible()
    await first.click()
    await page.waitForURL(/\/(exams|sections)\//)
  })
  await test.step('Bước 2: không có mục quản trị của Bộ môn (Kế hoạch đo PI, Tổng hợp PLO, Kết nối Moodle)', async () => {
    for (const item of ['Kế hoạch đo chỉ báo (PI)', 'Kết quả chương trình (PLO)', 'Kết nối Moodle']) await expect(nav(page, item)).toHaveCount(0)
  })
})

test('GV1b – SSO: gv.son bấm "Phân tích CĐR" trên Moodle → vào thẳng hệ thống @moodle', async ({ browser }) => {
  const p = await H.newPage(browser)
  await test.step('Bước 1: đăng nhập Moodle bằng tài khoản gv.son (trùng tên với hệ thống)', async () => {
    await H.moodleLogin(p, H.GV)
  })
  await test.step('Bước 2: mở "Phân tích CĐR" (launch.php) của khóa học demo → hệ thống tự đăng nhập vai trò GV', async () => {
    await p.goto(`${H.MOODLE}/local/clo/launch.php?courseid=${H.DEMO.moodleCourse}`)
    await p.waitForURL(/localhost:8000/, { timeout: 20000 })
    await expect(nav(p, 'Môn học của tôi')).toBeVisible()
  })
  await p.context().close()
})

// ================================================================== GV2 – Môn của tôi, chỉ xem đề cương, phân quyền
test('GV2 – Thấy môn mình phụ trách, chỉ xem đề cương bản đang áp dụng; GV khác bị chặn', async ({ page, browser }) => {
  await test.step('Bước 1: Môn học của tôi → có môn kiểm thử (được phân công ở AD5) và môn demo', async () => {
    await goto(page, '/courses')
    await see(page, S.code)
    await see(page, H.DEMO.code)
  })
  await test.step('Bước 2: mở môn kiểm thử → không có thẻ "Thiết lập học phần"', async () => {
    await goto(page, `/courses/${S.cid}`)
    await expect(tab(page, 'Đề cương chi tiết')).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Thiết lập học phần' })).toHaveCount(0)
  })
  await test.step('Bước 3: đề cương hiện "Phiên bản 1: Đang áp dụng" (không phải bản nháp 2), không có nút Sửa', async () => {
    await tab(page, 'Đề cương chi tiết').click()                    // trang môn mở sẵn bước "Lớp học phần" – chuyển sang đề cương
    await see(page, 'Phiên bản 1: Đang áp dụng')
    await see(page, 'Bộ môn quản lý – giảng viên chỉ xem')
    await expect(page.locator('.syl h4').getByRole('button', { name: 'Sửa' })).toHaveCount(0)
  })
  await test.step('Bước 4: GV khác (gv.binh) không thấy môn; mở thẳng trang lớp → báo không có quyền', async () => {
    const p = await H.newPage(browser)
    await H.login(p, H.GV_KHAC)
    await expect(p.getByText(S.code)).toHaveCount(0)
    await p.goto(`${H.APP}/sections/${S.cs}`)
    await toast(p, /không có quyền|không phụ trách|403|Không tìm thấy/i)
    await p.context().close()
  })
})

// ================================================================== GV3 – Danh sách sinh viên
test('GV3 – Nhập danh sách 5 SV vào lớp từ tệp CSV', async ({ page }) => {
  const csv = path.join(TMP, 'ds_sv_kiem_thu.csv')
  await test.step('Bước 1: tạo tệp ds.csv (UTF-8): student_code, full_name, class_name', async () => {
    fs.writeFileSync(csv, 'student_code,full_name,class_name\n' + STUDENTS.map(([c, n]) => `${c},${n},22KTDL`).join('\n'), 'utf8')
  })
  await test.step('Bước 2: mở lớp → thẻ "Danh sách SV" → "Nhập CSV …" → chọn tệp', async () => {
    await goto(page, `/sections/${S.cs}`)
    await page.getByRole('button', { name: /^Danh sách SV/ }).click()
    const chooser = page.waitForEvent('filechooser')
    await page.getByRole('button', { name: /Nhập CSV/ }).click()
    await (await chooser).setFiles(csv)
  })
  await test.step('Bước 3: thông báo đã thêm 5 SV, thẻ hiện "Danh sách SV (5)"', async () => {
    await toast(page, 'Đã thêm 5 SV vào lớp')
    await expect(page.getByRole('button', { name: 'Danh sách SV (5)' })).toBeVisible()
    await see(page, 'Hoàng Văn Em')
  })
})

test('GV3b – Môn demo: "Cập nhật lớp từ Moodle" cập nhật SV đang ghi danh trên Moodle @moodle', async ({ page }) => {
  await test.step('Bước 1: trang môn demo → thẻ Lớp học phần → "⟳ Cập nhật lớp từ Moodle" → kết quả theo từng lớp', async () => {
    const { cid } = await demoIds(page)
    await goto(page, `/courses/${cid}?tab=sections`)
    await page.getByRole('button', { name: /Cập nhật lớp từ Moodle/ }).click()
    await toast(page, new RegExp(H.DEMO.section), 30000)
  })
})

// ================================================================== GV4 – Ngân hàng câu hỏi
test('GV4 – Soạn câu hỏi, cây PLO → PI → CLO, lọc theo PI, Hủy câu', async ({ page }) => {
  const tree = page.locator('.otree')
  await test.step('Bước 1: Ngân hàng câu hỏi → mở môn kiểm thử', async () => {
    await goto(page, `/questions?course=${S.cid}`)
    await see(page, 'Theo chuẩn đầu ra')
  })
  await test.step('Bước 2: soạn 3 câu (chương 1, Hiểu, CLO1) và 3 câu (chương 2, Vận dụng, CLO2)', async () => {
    for (let i = 1; i <= 3; i++) await addQuestion(page, `Câu hỏi tiền xử lý số ${i}: bước nào làm sạch dữ liệu?`, 1, '2. Hiểu', 'CLO1')
    for (let i = 1; i <= 3; i++) await addQuestion(page, `Câu hỏi luật kết hợp số ${i}: độ hỗ trợ được tính thế nào?`, 2, '3. Vận dụng', 'CLO2')
  })
  await test.step('Bước 3: cây "Theo chuẩn đầu ra": Tất cả 6; PLO6 › PI6.2 = 3; PLO7 › PI7.1 = 3', async () => {
    await expect(tree.locator('.node').filter({ hasText: 'Tất cả' })).toContainText('6')
    for (const label of ['PLO6', 'PI6.2', 'PLO7', 'PI7.1']) await expect(tree.locator('.node').filter({ hasText: label }).first()).toContainText('3')
  })
  await test.step('Bước 4: bấm nút PI7.1 → còn 3 câu, mỗi câu có chuỗi "PLO7 › PI7.1"', async () => {
    await tree.locator('.node').filter({ hasText: 'PI7.1' }).first().click()
    await expect(page.getByText(/^3 câu hỏi$/)).toBeVisible()
    await expect(page.locator('.chain').filter({ hasText: 'PLO7 › PI7.1' })).toHaveCount(3)
  })
  await test.step('Bước 5: bấm "Tất cả" → trở lại 6 câu', async () => {
    await tree.locator('.node').filter({ hasText: 'Tất cả' }).click()
    await expect(page.getByText(/^6 câu hỏi$/)).toBeVisible()
  })
  await test.step('Bước 6: thêm 1 câu soạn nhầm → Chi tiết → nhập lý do → "Hủy câu hỏi" (xác nhận) → còn 6 câu', async () => {
    await addQuestion(page, 'Câu hỏi soạn nhầm cần Hủy?', 1, '2. Hiểu', 'CLO1')
    await page.locator('tr').filter({ hasText: 'Câu hỏi soạn nhầm cần Hủy' }).getByRole('button', { name: 'Chi tiết' }).click()
    const m = modal(page)
    await m.getByPlaceholder('Lý do Hủy câu hỏi…').fill('Đáp án sai, soạn lại')
    page.once('dialog', d => d.accept())                                   // hộp xác nhận của trình duyệt
    await m.getByRole('button', { name: /Hủy câu hỏi/ }).click()
    await toast(page, 'Đã Hủy câu hỏi')
    await H.closeModals(page)
    await expect(page.getByText(/^6 câu hỏi$/)).toBeVisible()
  })
})

// ================================================================== GV5 – Nhập câu hỏi từ file, gán CLO từ file
test('GV5 – Nhập 2 câu từ tệp Aiken → "chưa gán"; gán Chương/Bloom/CLO bằng tệp Excel', async ({ page }) => {
  const aiken = path.join(TMP, 'cau_hoi_aiken.txt')
  const xlsx = path.join(TMP, 'gan_clo_kiem_thu.xlsx')
  await goto(page, `/questions?course=${S.cid}`)
  await test.step('Bước 1: tạo tệp Aiken 2 câu (câu hỏi, các dòng "A. …", dòng "ANSWER: X")', async () => {
    fs.writeFileSync(aiken, 'Thuật toán Apriori dùng để làm gì?\nA. Tìm tập phổ biến\nB. Phân cụm\nC. Hồi quy\nD. Giảm chiều\nANSWER: A\n\n' +
      'Độ tin cậy của luật X→Y là gì?\nA. P(Y|X)\nB. P(X)\nC. P(X,Y)\nD. P(X|Y)\nANSWER: A\n', 'utf8')
  })
  await test.step('Bước 2: "⬆ Nhập câu hỏi từ file" → chọn tệp → xem trước → "Nhập 2 câu hỏi" → đã thêm 2 câu chưa gán', async () => {
    await page.getByRole('button', { name: /Nhập câu hỏi từ file/ }).click()
    const m = modal(page)
    const chooser = page.waitForEvent('filechooser')
    await m.getByRole('button', { name: /Chọn file câu hỏi/ }).click()
    await (await chooser).setFiles(aiken)
    await m.getByRole('button', { name: 'Nhập 2 câu hỏi' }).click()
    await see(m, 'Đã thêm 2 câu hỏi vào ngân hàng')
    await m.getByRole('button', { name: 'Đóng', exact: true }).last().click()
    await see(page, /Có 2 câu hỏi chưa gán/)
  })
  await test.step('Bước 3: "Gán CLO, mức độ nhận thức từ file" → tải "Các câu chưa gán (2)" → điền Chương=2, Bloom=3, CLO=CLO2', async () => {
    await page.getByRole('button', { name: 'Gán CLO, mức độ nhận thức từ file' }).click()
    const dl = page.waitForEvent('download')
    await modal(page).getByRole('button', { name: /Các câu chưa gán \(2\)/ }).click()
    await (await dl).saveAs(xlsx)
    // điền tệp Excel bằng Python (openpyxl có sẵn trong .venv): cột D = Chương, E = Bloom, F = CLO
    const py = path.join(H.ROOT, '.venv', 'Scripts', 'python.exe')
    execFileSync(py, ['-c', `import openpyxl,sys\nwb=openpyxl.load_workbook(sys.argv[1]);ws=wb['GanCLO']\nfor r in range(2,ws.max_row+1):\n ws.cell(r,4).value,ws.cell(r,5).value,ws.cell(r,6).value=2,3,'CLO2'\nwb.save(sys.argv[1])`, xlsx])
  })
  await test.step('Bước 4: chọn tệp đã điền → "Cập nhật 2 câu hỏi" → hết cảnh báo; cây PI7.1 = 5 câu', async () => {
    const m = modal(page)
    const chooser = page.waitForEvent('filechooser')
    await m.getByRole('button', { name: /Chọn file đã điền/ }).click()
    await (await chooser).setFiles(xlsx)
    await m.getByRole('button', { name: 'Cập nhật 2 câu hỏi' }).click()
    await see(m, /Đã cập nhật|đã cập nhật/)
    await H.closeModals(page)
    await expect(page.getByText(/câu hỏi chưa gán/)).toHaveCount(0)
    await expect(page.locator('.otree .node').filter({ hasText: 'PI7.1' }).first()).toContainText('5')
  })
})

// ================================================================== GV6 – Đồng bộ câu hỏi 2 chiều (môn demo)
test('GV6 – Đồng bộ câu hỏi 2 chiều: đẩy lên; sửa cả hai bên → "Hai bên khác nhau"; lấy bản Moodle; "Hệ thống mới hơn" @moodle', async ({ page, browser }) => {
  const { cid } = await demoIds(page)
  const content = `Lệnh nào xóa toàn bộ dữ liệu của bảng nhưng giữ cấu trúc? (${S.code})`
  let qid
  const openSync = async () => {
    await page.getByRole('button', { name: /Đồng bộ với Moodle/ }).click()
    const m = modal(page)
    await pick(m.getByLabel('Hiển thị'), 'Tất cả')
    return { m, row: m.locator('tr').filter({ hasText: `QB-${qid}` }) }
  }
  await test.step('Bước 1: ngân hàng câu hỏi môn demo → soạn câu mới (đáp án đúng A)', async () => {
    await goto(page, `/questions?course=${cid}`)
    await addQuestion(page, content, 1, '2. Hiểu', 'CLO1')
    const list = await api(page, `/api/questions?course_id=${cid}&q=${encodeURIComponent(S.code)}`)
    qid = list.find(x => x.content === content).id
  })
  await test.step('Bước 2: "⇅ Đồng bộ với Moodle" → câu mới "Chỉ có trên hệ thống" → Đồng bộ (đẩy lên)', async () => {
    const { m, row } = await openSync()
    await see(row, 'Chỉ có trên hệ thống')
    await m.getByRole('button', { name: 'Đồng bộ', exact: true }).click()
    await toast(page, /Đã đẩy 1 câu/, 60000)
    await page.keyboard.press('Escape')
  })
  await test.step('Bước 3: mở lại → câu "Đã đồng bộ" (hệ thống ghi mốc dấu vân tay)', async () => {
    const { row } = await openSync()
    await see(row, 'Đã đồng bộ')
    await page.keyboard.press('Escape')
  })
  await test.step('Bước 4: sửa câu trên HỆ THỐNG: Chi tiết → đổi nội dung → Lưu', async () => {
    await page.locator('tr').filter({ hasText: content }).getByRole('button', { name: 'Chi tiết' }).click()
    await modal(page).getByLabel('Nội dung câu hỏi').fill(content + ' – sửa ở hệ thống')
    await modal(page).getByRole('button', { name: 'Lưu' }).click()
    await toast(page, 'Đã lưu câu hỏi')
  })
  await test.step('Bước 5: sửa CÙNG câu trên MOODLE (admin Moodle): form sửa câu QB-n → đổi nội dung → Lưu (phiên bản 2)', async () => {
    const cmp = await api(page, `/api/courses/${cid}/moodle-sync?moodle_course_id=${H.DEMO.moodleCourse}`)
    const mq = cmp.rows.find(r => r.question_id === qid).moodle_questionid       // id câu trên Moodle (bảng so sánh)
    const p = await H.newPage(browser)
    await H.moodleLogin(p, H.MOODLE_ADMIN)
    await p.goto(`${H.MOODLE}/question/bank/editquestion/question.php?courseid=${H.DEMO.moodleCourse}&id=${mq}`)
    await p.waitForFunction(() => window.tinymce && window.tinymce.get('id_questiontext'))
    await p.evaluate(() => window.tinymce.get('id_questiontext').setContent('<p>Lệnh nào xóa dữ liệu bảng – sửa trên Moodle?</p>'))
    await p.click('#id_submitbutton')
    await p.waitForLoadState('domcontentloaded')
    await p.context().close()
  })
  await test.step('Bước 6: mở Đồng bộ → "Hai bên khác nhau", mặc định Bỏ qua, có ghi chú cả hai bên đã sửa', async () => {
    const { row } = await openSync()
    await see(row, 'Hai bên khác nhau')
    await see(row, 'Cả hệ thống và Moodle đều đã sửa')
    await expect(row.locator('select')).toHaveValue('')
  })
  await test.step('Bước 7: chọn "⇩ Lấy về hệ thống" → Đồng bộ → câu "Đã đồng bộ", nội dung là bản sửa trên Moodle', async () => {
    const m = modal(page)
    await m.locator('tr').filter({ hasText: `QB-${qid}` }).locator('select').selectOption('pull')
    await m.getByRole('button', { name: 'Đồng bộ', exact: true }).click()
    await toast(page, /cập nhật 1/, 60000)
    await page.keyboard.press('Escape')
    const { row } = await openSync()
    await see(row, 'Đã đồng bộ')
    await page.keyboard.press('Escape')
    await see(page, 'sửa trên Moodle')
  })
  await test.step('Bước 8: chỉ sửa ở hệ thống → mở Đồng bộ → "Hệ thống mới hơn", mặc định Đẩy lên Moodle', async () => {
    await page.locator('tr').filter({ hasText: 'sửa trên Moodle' }).getByRole('button', { name: 'Chi tiết' }).click()
    await modal(page).getByLabel('Nội dung câu hỏi').fill('Lệnh nào xóa dữ liệu bảng – chỉ sửa ở hệ thống?')
    await modal(page).getByRole('button', { name: 'Lưu' }).click()
    await toast(page, 'Đã lưu câu hỏi')
    const { row } = await openSync()
    await see(row, 'Hệ thống mới hơn')
    await expect(row.locator('select')).toHaveValue('push')
  })
})

// ================================================================== GV7 – Ra đề trực tuyến
test('GV7 – Ra đề trực tuyến cho lớp; tải Moodle XML có idnumber QB-n', async ({ page }) => {
  await test.step('Bước 1: mở lớp → "+ Tạo bài kiểm tra" → "Trắc nghiệm trực tuyến"', async () => {
    await goto(page, `/sections/${S.cs}`)
    await page.getByRole('button', { name: '+ Tạo bài kiểm tra' }).click()
    await modal(page).getByRole('button', { name: /Trắc nghiệm trực tuyến/ }).click()
  })
  await test.step('Bước 2 (1. Thông tin bài): tên bài, minh chứng Cuối kỳ → "Tiếp: chọn câu hỏi"', async () => {
    const m = modal(page)
    await m.getByLabel('Tên bài kiểm tra').fill('Thi cuối kỳ (kiểm thử UI)')
    await pick(m.getByLabel('Loại đánh giá của bài'), 'Cuối kỳ')
    await m.getByRole('button', { name: /Tiếp: chọn câu hỏi/ }).click()
  })
  await test.step('Bước 3 (2. Chọn câu hỏi): "Tự chọn câu từ ngân hàng" → chờ danh sách câu → "Chọn tất cả đang lọc"', async () => {
    const m = modal(page)
    await m.getByRole('button', { name: /Tự chọn câu từ ngân hàng/ }).click()
    await expect(m.locator('tbody input[type=checkbox]').first()).toBeVisible()
    await m.getByRole('button', { name: 'Chọn tất cả đang lọc' }).click()
    await see(m, /Đã chọn [1-9]\d* câu/)
  })
  await test.step('Bước 4 (3. Kiểm tra & lưu): "Tiếp: kiểm tra đề" → "Lưu bài kiểm tra" → trang bài ở trạng thái Nháp, có đề', async () => {
    await modal(page).getByRole('button', { name: /Tiếp: kiểm tra đề/ }).click()
    await modal(page).getByRole('button', { name: 'Lưu bài kiểm tra' }).click()
    await page.waitForURL(/\/exams\/\d+/)
    S.onlineExam = examIdFromUrl(page)
    await see(page, 'Đề thi')                                                     // trang bài mở ở bước đưa bài cho sinh viên (bài mới ở trạng thái nháp)
    await tab(page, 'Đề thi').click()                                            // trang bài KT chia bước; bước "Đề thi"
    await expect(card(page, 'Đề thi').locator('tbody tr').first()).toBeVisible()
  })
  await test.step('Bước 5: bước "Đưa bài lên Moodle" → "Cách thủ công…"', async () => {
    await tab(page, 'Đưa bài lên Moodle').click()
  })
  await test.step('Bước 6: "Cách thủ công…" → "⬇ Tải file câu hỏi Moodle XML" → tệp có <quiz> và idnumber QB-n', async () => {
    await page.getByText('Cách thủ công: tải XML, tự import và nhập ID Quiz').click()
    const dl = page.waitForEvent('download')
    await page.getByRole('button', { name: /Tải file câu hỏi Moodle XML/ }).click()
    const xml = fs.readFileSync(await (await dl).path(), 'utf8')
    expect(xml).toContain('<quiz>')
    expect(xml).toContain('<idnumber>QB-')
  })
})

// ================================================================== GV8 – Đề giấy chấm trên hệ thống
test('GV8 – Đề giấy: sinh 2 mã đề, tải đề/đáp án, tải ảnh phiếu đã tô → hệ thống đọc và chấm', async ({ page }) => {
  let eid
  await test.step('Bước 1: lớp → "+ Tạo bài kiểm tra" → "Trắc nghiệm trên giấy" → thông tin → tự chọn tất cả câu → kiểm tra → Lưu', async () => {
    await goto(page, `/sections/${S.cs}`)
    await page.getByRole('button', { name: '+ Tạo bài kiểm tra' }).click()
    await modal(page).getByRole('button', { name: /Trắc nghiệm trên giấy/ }).click()
    const m = modal(page)
    await m.getByLabel('Tên bài kiểm tra').fill('Kiểm tra giữa kỳ trên giấy (kiểm thử UI)')
    await m.getByRole('button', { name: /Tiếp: chọn câu hỏi/ }).click()
    await m.getByRole('button', { name: /Tự chọn câu từ ngân hàng/ }).click()
    await expect(m.locator('tbody input[type=checkbox]').first()).toBeVisible()
    await m.getByRole('button', { name: 'Chọn tất cả đang lọc' }).click()
    await see(m, /Đã chọn [1-9]\d* câu/)
    await m.getByRole('button', { name: /Tiếp: kiểm tra đề/ }).click()
    await m.getByRole('button', { name: 'Lưu bài kiểm tra' }).click()
    await page.waitForURL(/\/exams\/\d+/)
    eid = examIdFromUrl(page)
  })
  await test.step('Bước 2: "In và chấm ngay trên hệ thống" → 2 mã đề → "Sinh mã đề"', async () => {
    await page.getByRole('button', { name: /In và chấm ngay trên hệ thống/ }).click()
    await pick(page.getByLabel('Số mã đề'), '2 mã đề')
    await page.getByRole('button', { name: 'Sinh mã đề' }).click()
    await toast(page, 'Đã sinh 2 mã đề')
  })
  await test.step('Bước 3: thẻ "2. Xem trước & xuất đề" → tải PDF tất cả mã đề và đáp án', async () => {
    await page.getByRole('button', { name: '2. Xem trước & xuất đề' }).click()
    for (const label of ['⬇ PDF tất cả mã đề', '⬇ Đáp án']) {
      const dl = page.waitForEvent('download')
      await page.getByRole('button', { name: label }).click()
      expect((await dl).suggestedFilename()).toMatch(/\.pdf$/)
    }
  })
  const png = path.join(TMP, `phieu_${STUDENTS[0][0]}.png`)
  await test.step('Bước 4: tạo ảnh phiếu đã tô cho SV 26990001 (mã đề 01, tô A mọi câu) bằng bộ vẽ phiếu của hệ thống', async () => {
    const py = path.join(H.ROOT, '.venv', 'Scripts', 'python.exe')
    execFileSync(py, [path.join(__dirname, '..', 'tools', 'tao_phieu_da_to.py'), String(eid), STUDENTS[0][0], png], { env: { ...process.env, PYTHONUTF8: '1' } })
  })
  await test.step('Bước 5: thẻ "4. Chấm phiếu" → "⬆ Tải ảnh phiếu / PDF đã quét" → hệ thống đọc, chấm và lưu ngay (không cần bấm lưu)', async () => {
    await page.getByRole('button', { name: '4. Chấm phiếu' }).click()
    const chooser = page.waitForEvent('filechooser')
    await page.getByRole('button', { name: /Tải ảnh phiếu/ }).click()
    await (await chooser).setFiles(png)
    await toast(page, /Đã chấm & lưu 1 phiếu/, 30000)
    await see(page, 'Đã chấm vào kết quả lớp')
    await page.getByRole('button', { name: /Tất cả phiếu/ }).click()
    await see(page, STUDENTS[0][0], 30000)
  })
  await test.step('Bước 6: "Hoàn tất: tính vắng & phân tích" → đã hoàn tất 1 bài', async () => {
    await page.getByRole('button', { name: /Hoàn tất: tính vắng/ }).click()
    await toast(page, /Đã hoàn tất: 1 bài/, 30000)
  })
})

// ================================================================== GV9 – Bài nhập điểm
test('GV9 – Bài nhập điểm: 2 câu gắn CLO, chặn điểm vượt tối đa, lưu & phân tích, kết quả từng SV', async ({ page }) => {
  const grid = page.locator('table.grade-grid')
  const cell = (code, q) => grid.getByLabel(`${code} câu ${q}`)
  await test.step('Bước 1: lớp → "+ Tạo bài kiểm tra" → "Nhập điểm"', async () => {
    await goto(page, `/sections/${S.cs}`)
    await page.getByRole('button', { name: '+ Tạo bài kiểm tra' }).click()
    await modal(page).getByRole('button', { name: /Nhập điểm/ }).click()
  })
  await test.step('Bước 2: tên bài; xóa dòng thứ 3; Câu 1: 4 điểm CLO1; Câu 2: 6 điểm CLO2 → "Tạo bài và nhập điểm"', async () => {
    const m = modal(page)
    await m.getByLabel('Tên bài').fill('Bài tập lớn (kiểm thử UI)')
    await m.getByRole('button', { name: 'Xóa dòng' }).nth(2).click()
    const rows = m.locator('tbody tr')
    for (const [i, [title, pts, clo]] of [['Câu 1 – Tiền xử lý', '4', 'CLO1'], ['Câu 2 – Luật kết hợp', '6', 'CLO2']].entries()) {
      await rows.nth(i).locator('input').nth(0).fill(title)
      await rows.nth(i).locator('input[type=number]').fill(pts)
      await rows.nth(i).locator('label', { hasText: clo }).locator('input').check()
    }
    await m.getByRole('button', { name: 'Tạo bài và nhập điểm' }).click()
    await page.waitForURL(/\/exams\/\d+/)
    S.manualExam = examIdFromUrl(page)
    await grid.waitFor()
  })
  await test.step('Bước 3: nhập 5 điểm cho Câu 1 (tối đa 4) → ô tô đỏ, nút Lưu bị khóa', async () => {
    await cell(STUDENTS[0][0], 1).fill('5')
    await expect(cell(STUDENTS[0][0], 1)).toHaveClass(/bad/)
    await expect(page.getByRole('button', { name: /Lưu .*phân tích/ })).toBeDisabled()
  })
  await test.step('Bước 4: nhập bảng điểm đúng; SV thứ 5 đánh dấu Vắng', async () => {
    const marks = [['4', '6'], ['3', '5'], ['1', '2'], ['2', '6']]
    for (const [i, [c1, c2]] of marks.entries()) {
      await cell(STUDENTS[i][0], 1).fill(c1)
      await cell(STUDENTS[i][0], 2).fill(c2)
    }
    await grid.locator('tr').filter({ hasText: STUDENTS[4][0] }).getByLabel('Vắng').check()
  })
  await test.step('Bước 5: "Lưu (5 SV) & phân tích" → 4 SV có điểm, 1 vắng, đã phân tích', async () => {
    await page.getByRole('button', { name: /Lưu .*phân tích/ }).click()
    await toast(page, /Đã lưu 4 SV có điểm, 1 vắng/, 30000)
  })
  await test.step('Bước 6: bước "Kết quả" → "Kết quả sinh viên": có điểm từng SV nhưng KHÔNG có kết quả CLO riêng của SV (không cột %)', async () => {
    await tab(page, 'Kết quả').click()
    await page.getByRole('button', { name: 'Kết quả sinh viên' }).click()
    await see(page.locator('tr').filter({ hasText: STUDENTS[2][0] }), STUDENTS[2][0])
    await see(page.locator('tr').filter({ hasText: STUDENTS[0][0] }), STUDENTS[0][0])
    await expect(page.locator('tr').filter({ hasText: STUDENTS[2][0] }).getByText('%')).toHaveCount(0)
  })
})

// ================================================================== GV10 – Lấy bài làm & phân tích bài Moodle (môn demo)
test('GV10 – Bài thi cuối kỳ demo: "⟳ Lấy bài làm & phân tích" đọc lại bài làm từ CSDL Moodle @moodle', async ({ page }) => {
  await test.step('Bước 1: mở bài "Thi cuối kỳ (Moodle)" của lớp demo → "⟳ Lấy bài làm & phân tích" → đồng bộ N bài làm', async () => {
    const { cs } = await demoIds(page)
    const exams = await api(page, `/api/class-sections/${cs}/exams`)
    await goto(page, `/exams/${exams.find(e => e.exam_title === H.DEMO.finalExam).id}`)
    await tab(page, 'Lấy bài làm & phân tích').click()                              // bài đã phân tích mở sẵn bước "Kết quả"
    await page.getByRole('button', { name: /Lấy bài làm & phân tích/ }).click()
    await toast(page, /Đồng bộ \d+ bài làm/, 60000)
  })
})

// ================================================================== GV11 – Xem phân tích (môn demo)
test('GV11 – Tổng quan điểm, phân tích câu hỏi, kết quả SV, thời gian làm bài; thống kê lớp; hồ sơ SV', async ({ page }) => {
  const { cs } = await demoIds(page)
  await test.step('Bước 1: mở bài "Thi cuối kỳ (Moodle)" → thẻ "Tổng quan điểm": SV dự thi, điểm trung bình', async () => {
    const exams = await api(page, `/api/class-sections/${cs}/exams`)
    await goto(page, `/exams/${exams.find(e => e.exam_title === H.DEMO.finalExam).id}`)
    await page.getByRole('button', { name: 'Tổng quan điểm' }).click()
    await see(page, 'SV dự thi')
    await see(page, 'Điểm trung bình')
  })
  await test.step('Bước 2: thẻ "Phân tích câu hỏi" → phân loại câu theo p, DI', async () => {
    await page.getByRole('button', { name: 'Phân tích câu hỏi' }).click()
    await see(page, 'Câu tốt / chấp nhận')
  })
  await test.step('Bước 3: thẻ "Kết quả sinh viên" → có SV 22130011', async () => {
    await page.getByRole('button', { name: 'Kết quả sinh viên' }).click()
    await see(page, '22130011')
  })
  await test.step('Bước 4: thẻ "Thời gian làm bài" mở được', async () => {
    await page.getByRole('button', { name: /Thời gian làm bài/ }).click()
    await see(page, /thời gian/i)
  })
  await test.step('Bước 5: thống kê lớp → bản đồ điểm theo chương; bấm "Hồ sơ" một SV → điểm các bài, chẩn đoán & lộ trình ôn tập (không có nhãn Đạt/Không đạt theo CLO)', async () => {
    await goto(page, `/sections/${cs}/stats`)
    await page.getByText('Xem thêm biểu đồ và bảng chi tiết').click()
    await see(page, 'Bản đồ điểm theo chương của từng sinh viên')
    await page.getByRole('link', { name: 'Hồ sơ' }).first().click()
    await see(page, 'Điểm các bài kiểm tra')
    await see(page, 'Chẩn đoán & lộ trình ôn tập')
    await expect(page.getByText('Không đạt', { exact: true })).toHaveCount(0)
  })
})

// ================================================================== GV12 – Kết quả CLO, kế hoạch đánh giá, xuất biểu mẫu
test('GV12 – Lớp kiểm thử: lập kế hoạch đánh giá cho CLO1, xem kết quả cả lớp, xuất biểu mẫu Excel', async ({ page }) => {
  await test.step('Bước 1: trang Kết quả chuẩn đầu ra của lớp → thẻ Kế hoạch đánh giá → "Sửa" kế hoạch của CLO1', async () => {
    await goto(page, `/sections/${S.cs}/clo?tab=bm6a`)
    await page.locator('tr').filter({ hasText: 'CLO1' }).getByRole('button', { name: 'Sửa' }).first().click()
  })
  await test.step('Bước 2: phương pháp, ngưỡng đạt 60%, chỉ tiêu 75% → Lưu', async () => {
    const m = modal(page)
    await m.getByLabel('Phương pháp').fill('Bài tập lớn tự luận')
    await m.getByLabel('Ngưỡng đạt của SV (% điểm tối đa)').fill('60')
    await m.getByLabel('Chỉ tiêu mong muốn (% SV đạt)').fill('75')
    await m.getByRole('button', { name: 'Lưu' }).click()
    await expect(page.locator('.modal')).toHaveCount(0)
  })
  await test.step('Bước 3: thẻ Kết quả cả lớp → CLO1 có tỷ lệ đạt 75% (3/4 SV)', async () => {
    await tab(page, '2. Kết quả cả lớp').click()
    await see(page.locator('tr').filter({ hasText: 'CLO1' }).first(), '75')
  })
  await test.step('Bước 4: "⬇ Xuất biểu mẫu kết quả của lớp (.xlsx)" → tải được tệp Excel', async () => {
    const dl = page.waitForEvent('download')
    await page.getByRole('button', { name: /Xuất biểu mẫu kết quả của lớp/ }).click()
    expect((await dl).suggestedFilename()).toMatch(/\.xlsx$/)
  })
})

// ================================================================== GV13 – Gộp nhiều bài KT (môn demo)
test('GV13 – Môn demo: gộp 2 bài KT → mức đạt CLO; xuất Excel', async ({ page }) => {
  await test.step('Bước 1: trang môn demo → thẻ "Chọn bài tính vào kết quả" → tích 2 bài', async () => {
    const { cid } = await demoIds(page)
    await goto(page, `/courses/${cid}?tab=combine`)
    const checks = card(page, '1. Chọn các bài kiểm tra cần gộp').locator('input[type=checkbox]')
    await checks.first().waitFor()
    for (let i = 0; i < 2; i++) await checks.nth(i).check()
  })
  await test.step('Bước 2: "Phân tích gộp" → khung "2. Mức đạt CĐR môn học (CLO)"', async () => {
    await page.getByRole('button', { name: 'Phân tích gộp' }).click()
    await expect(card(page, '2. Mức đạt CĐR môn học (CLO)')).toBeVisible({ timeout: 30000 })
  })
  await test.step('Bước 3: "⬇ Xuất Excel" → tải được tệp', async () => {
    const dl = page.waitForEvent('download')
    await page.getByRole('button', { name: '⬇ Xuất Excel' }).click()
    expect((await dl).suggestedFilename()).toMatch(/\.xlsx$/)
  })
})

// ================================================================== GV14 – Phụ đạo (môn demo, Moodle)
test('GV14 – Phụ đạo: xem câu sai, tạo bài cho 2 SV, tạo Quiz chỉ 2 SV đó làm được @moodle', async ({ page }) => {
  const { cs } = await demoIds(page)
  let first, second
  await test.step('Bước 1: trang Phụ đạo lớp demo → chỉ tích bài "Thi cuối kỳ (Moodle)"', async () => {
    await goto(page, `/sections/${cs}/remedial`)
    const box = card(page, 'Bài kiểm tra dùng để tính')
    await box.locator('label').first().waitFor()
    for (const lab of await box.locator('label').all()) {
      const cb = lab.locator('input[type=checkbox]')
      if ((await lab.innerText()).includes(H.DEMO.finalExam)) await cb.check(); else await cb.uncheck()
    }
  })
  await test.step('Bước 2: 2 SV sai nhiều nhất ở đầu bảng; "Câu sai ›" của SV đầu → thấy đáp án đúng', async () => {
    const rows = card(page, 'Số câu sai của từng sinh viên').locator('tbody tr')
    first = rows.nth(0); second = rows.nth(1)
    S.remedialStudents = [(await first.locator('td').nth(1).innerText()).trim(), (await second.locator('td').nth(1).innerText()).trim()]
    await first.getByRole('button', { name: 'Câu sai ›' }).click()
    await see(modal(page), 'Đáp án đúng')
    await page.keyboard.press('Escape')
  })
  await test.step('Bước 3: tích 2 SV → "Tạo bài ôn tập cho 2 SV đã chọn" → câu tương tự 0 → "Tạo bài"', async () => {
    await first.locator('input[type=checkbox]').check()
    await second.locator('input[type=checkbox]').check()
    await page.getByRole('button', { name: 'Tạo bài ôn tập cho 2 SV đã chọn' }).click()
    const m = modal(page)
    await pick(m.getByLabel('Câu tương tự / câu sai'), '0')
    await m.getByRole('button', { name: 'Tạo bài' }).click()
    await page.waitForURL(/\/exams\/\d+/)
    S.remedialExam = examIdFromUrl(page)
  })
  await test.step('Bước 4: "⇪ Tạo bài trắc nghiệm trên Moodle" → "chỉ 2 SV được giao làm được"; có nút "Giới hạn SV trên Moodle"', async () => {
    await page.getByRole('button', { name: /Tạo bài trắc nghiệm trên Moodle/ }).click()
    await toast(page, /chỉ 2 SV được giao làm được/, 60000)
    await see(page, 'Bài ôn tập: chỉ 2 SV được giao')
    await expect(page.getByRole('button', { name: 'Giới hạn SV trên Moodle' })).toBeVisible()
  })
  await test.step('Bước 5: trang Phụ đạo → khung tiến bộ có bài vừa tạo, 2 SV "Chưa làm" (SV làm bài ở tệp 03)', async () => {
    await goto(page, `/sections/${cs}/remedial`)
    const box = card(page, 'Bài ôn tập đã giao').locator('details').filter({ has: page.locator(`a[href='/exams/${S.remedialExam}']`) })
    await box.locator('summary').click()
    await expect(box.getByText('Chưa làm').first()).toBeVisible()
  })
})

// ================================================================== GV15 – Công bố / thu hồi (môn demo, Moodle)
test('GV15 – Bài thi cuối kỳ demo: thu hồi công bố rồi công bố lại @moodle', async ({ page }) => {
  await test.step('Bước 1: mở bài "Thi cuối kỳ (Moodle)" của lớp demo', async () => {
    const { cs } = await demoIds(page)
    const exams = await api(page, `/api/class-sections/${cs}/exams`)
    await goto(page, `/exams/${exams.find(e => e.exam_title === H.DEMO.finalExam).id}`)
    await expect(page.getByRole('button', { name: /Thu hồi công bố|Công bố kết quả lên Moodle/ }).first()).toBeVisible()
  })
  await test.step('Bước 2: nếu đang công bố → "Thu hồi công bố" → Moodle nhận kết quả, nhãn "Đang bảo lưu kết quả"', async () => {
    if (await page.getByRole('button', { name: 'Thu hồi công bố' }).count()) {
      await page.getByRole('button', { name: 'Thu hồi công bố' }).first().click()
      await toast(page, /Đã thu hồi – Moodle đã nhận \d+ kết quả/, 60000)
      await see(page, 'Đang bảo lưu kết quả')
    }
  })
  await test.step('Bước 3: "Công bố kết quả lên Moodle" → nhãn "SV đã xem được kết quả"', async () => {
    await page.getByRole('button', { name: 'Công bố kết quả lên Moodle' }).first().click()
    await toast(page, /Đã công bố cho SV – Moodle đã nhận \d+ kết quả/, 60000)
    await see(page, 'SV đã xem được kết quả')
  })
})

// ================================================================== Bộ môn kiểm tra lại PI/PLO sau khi GV nhập điểm
test('AD8b – Sau GV8 + GV9: kế hoạch đo PI7.1 của môn kiểm thử = 4/5 = 80% → Đạt (chỉ tiêu 70%)', async ({ browser }) => {
  const p = await H.newPage(browser)
  await H.login(p, H.ADMIN)
  await test.step('Bước 1: Bộ môn → Tổng hợp PLO → KTDL-2026, năm 2024-2025 → Tính lại', async () => {
    await nav(p, 'Kết quả chương trình (PLO)').click()
    await pick(p.getByLabel('Chương trình đào tạo').first(), 'KTDL-2026')
    await pick(p.getByLabel('Năm học'), '2024-2025')
    await p.getByRole('button', { name: 'Tính lại' }).click()
    await toast(p, 'Đã tính lại')
  })
  await test.step('Bước 2: Kế hoạch đo PI → dòng PI7.1 của môn kiểm thử: 4/5 = 80%, Đạt (gộp bài giấy GV8 và bài nhập điểm GV9; tự lấy CLO2 gắn PI7.1)', async () => {
    await nav(p, 'Kế hoạch đo chỉ báo (PI)').click()
    await pick(p.getByLabel('Chương trình đào tạo').first(), 'KTDL-2026')
    const row = card(p, 'Kế hoạch năm học').locator('tbody tr').filter({ hasText: S.code }).filter({ hasText: 'PI7.1' })
    await see(row, '4/5')
    await see(row, '80')
    await see(row, 'Đạt')
  })
  await p.context().close()
})

// ================================================================== GV16 – Vòng cải tiến
test('GV16 – Kết quả CLO: so sánh qua các học kỳ; ghi hành động cải tiến, đổi trạng thái, xóa', async ({ page }) => {
  await test.step('Bước 1: mở Kết quả cả lớp của lớp → thấy bảng "Xu hướng đạt CLO qua các học kỳ" và khung "Hành động cải tiến"', async () => {
    await goto(page, `/sections/${S.cs}/clo?tab=bm6b`)
    await see(page, 'Xu hướng đạt CLO qua các học kỳ')
    await see(page, 'Hành động cải tiến (đóng vòng đánh giá)')
  })
  const ac = () => card(page, 'Hành động cải tiến')
  await test.step('Bước 2: nhập hành động, người phụ trách → "+ Thêm hành động" → hiện trong bảng', async () => {
    await ac().getByPlaceholder(/Thêm 2 buổi/).fill('Bổ sung bài tập truy vấn lồng (kiểm thử UI)')
    await field(ac(), 'Người phụ trách').fill('ThS. Sơn')
    await ac().getByRole('button', { name: '+ Thêm hành động' }).click()
    await see(ac(), 'Bổ sung bài tập truy vấn lồng (kiểm thử UI)')
  })
  await test.step('Bước 3: đổi trạng thái sang "Đang làm" → giữ nguyên sau khi tải lại trang', async () => {
    const row = ac().locator('tr', { hasText: 'kiểm thử UI' })
    await row.locator('select').selectOption('doing')
    await page.waitForTimeout(600)
    await page.reload()
    await expect(ac().locator('tr', { hasText: 'kiểm thử UI' }).locator('select')).toHaveValue('doing')
  })
  await test.step('Bước 4: "Xóa" → hành động biến mất', async () => {
    page.once('dialog', d => d.accept())
    await ac().locator('tr', { hasText: 'kiểm thử UI' }).getByRole('button', { name: 'Xóa' }).click()
    await expect(ac().locator('tr', { hasText: 'kiểm thử UI' })).toHaveCount(0)
  })
})

// ================================================================== GV17 – Rubric
test('GV17 – Rubric: tạo rubric của môn, tạo bài chấm theo rubric, chọn mức từng SV, lưu và phân tích', async ({ page }) => {
  await test.step('Bước 1: trang môn → thẻ "Rubric chấm điểm" → "+ Tạo rubric"', async () => {
    await goto(page, `/courses/${S.cid}?tab=rubrics`)
    await see(page, 'Rubric chấm điểm')
    await page.getByRole('button', { name: '+ Tạo rubric' }).first().click()
  })
  await test.step('Bước 2: tên rubric, tiêu chí "Nội dung" 6 điểm đo CLO đầu tiên → "Lưu rubric"', async () => {
    const m = modal(page)
    await field(m, 'Tên rubric').fill('Rubric báo cáo (kiểm thử UI)')
    await m.getByPlaceholder(/Nội dung chuyên môn/).fill('Nội dung chuyên môn')
    await field(m, 'Điểm tối đa').fill('6')
    await m.getByRole('button', { name: '+ Thêm tiêu chí' }).click()
    await m.getByPlaceholder(/Nội dung chuyên môn/).nth(1).fill('Trình bày')
    await m.getByRole('button', { name: 'Lưu rubric' }).click()
    await expect(page.locator('.modal')).toHaveCount(0)
    await see(page, 'Rubric báo cáo (kiểm thử UI)')
  })
  await test.step('Bước 3: lớp → "+ Tạo bài kiểm tra" → "Chấm theo rubric" → tên bài → "Tạo bài và bắt đầu chấm"', async () => {
    await goto(page, `/sections/${S.cs}`)
    await page.getByRole('button', { name: '+ Tạo bài kiểm tra' }).click()
    await modal(page).getByRole('button', { name: /Chấm theo rubric/ }).click()
    const m = modal(page)
    await pick(m.getByLabel('Rubric dùng để chấm'), 'Rubric báo cáo (kiểm thử UI)')
    await m.getByLabel('Tên bài kiểm tra').fill('Báo cáo (rubric, kiểm thử UI)')
    await m.getByRole('button', { name: 'Tạo bài và bắt đầu chấm' }).click()
    await page.waitForURL(/\/exams\/\d+/)
    await see(page, 'Chấm theo rubric: Rubric báo cáo (kiểm thử UI)')
  })
  await test.step('Bước 4: chọn mức cho SV đầu tiên (cả hai tiêu chí) → điểm tổng hiện đủ; chọn thiếu thì không lưu được', async () => {
    const row = page.locator('table.rub-grid tbody tr').first()
    const sels = row.locator('select')
    await sels.nth(0).selectOption({ index: 1 })
    await expect(page.getByText(/chỉ chọn một phần|mới chọn một phần/)).toBeVisible()
    await expect(page.getByRole('button', { name: /Lưu và phân tích/ })).toBeDisabled()
    await sels.nth(1).selectOption({ index: 1 })
    await expect(row.locator('td').last()).toHaveText('10.00')
    await expect(page.getByRole('button', { name: /Lưu và phân tích/ })).toBeEnabled()
  })
  await test.step('Bước 5: "Lưu và phân tích" → thông báo đã lưu; tải lại vẫn giữ mức đã chọn', async () => {
    await page.getByRole('button', { name: /Lưu và phân tích/ }).click()
    await toast(page, /Đã lưu điểm và phân tích/)
    await page.reload()
    await page.getByText('Câu/ý & nhập điểm').first().click()
    await expect(page.locator('table.rub-grid tbody tr').first().locator('td').last()).toHaveText('10.00')
  })
})
