// VAI TRÒ BỘ MÔN (admin) – 9 flow AD1..AD9, chạy nối tiếp như người dùng thật.
// Kịch bản: Bộ môn mở một học phần mới từ đầu (mã UIddhhmm) trong CTĐT KTDL-2026 → giao PI → khai báo chương, CLO gắn PI
// → mở lớp cho gv.son → soạn và duyệt đề cương → lập kế hoạch đo PI → tổng hợp PLO, kết nối Moodle.
// Tệp 02 (giảng viên), 03 (sinh viên) dùng tiếp học phần này qua tệp .state.json.
const { test, expect } = require('@playwright/test')
const H = require('./helpers')
const { nav, modal, card, tab, field, pick, toast, see, goto } = H

const PI_A = 'PI6.2'      // PI của PLO6 trong CTĐT KTDL-2026
const PI_B = 'PI7.1'      // PI của PLO7
const pad = n => String(n).padStart(2, '0')

test.describe.configure({ mode: 'serial' })     // các flow phụ thuộc nhau → chạy lần lượt, flow trước lỗi thì dừng

const S = H.loadState()
const d = new Date()
S.newCode = `UI${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}`     // mã môn mới cho lần chạy này (AD3 dùng)

// Mỗi test dùng trang riêng do Playwright cấp (để --ui ghi ảnh/vết từng bước) → đăng nhập Bộ môn trước mỗi test
test.beforeEach(async ({ page }) => { await H.login(page, H.ADMIN) })
test.afterEach(() => H.saveState(S))

// ================================================================== AD1 – Đăng nhập
test('AD1 – Bộ môn đăng nhập; sai mật khẩu bị từ chối', async ({ page, browser }) => {
  await test.step('Bước 1: menu của Bộ môn có đủ các mục quản trị', async () => {
    for (const item of ['Chương trình đào tạo', 'Học phần', 'Lớp học phần', 'Kế hoạch đo PI', 'Tổng hợp PLO', 'Kết nối Moodle'])
      await expect(nav(page, item)).toBeVisible()
  })
  await test.step('Bước 2: phiên mới đăng nhập sai mật khẩu → báo lỗi, vẫn ở màn hình đăng nhập', async () => {
    const p = await H.newPage(browser)
    await p.goto(H.APP + '/')
    await p.getByLabel('Tên đăng nhập').fill('admin')
    await p.getByLabel('Mật khẩu').fill('sai-mat-khau')
    await p.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
    await toast(p, /Sai tên đăng nhập hoặc mật khẩu/)
    await expect(p.locator('nav.mainnav')).toHaveCount(0)
    await p.context().close()
  })
})

test('AD1b – SSO: admin Moodle bấm "Phân tích CĐR" → vào thẳng hệ thống @moodle', async ({ page, browser }) => {
  const p = await H.newPage(browser)
  await test.step('Bước 1: đăng nhập Moodle bằng tài khoản quản trị Moodle', async () => {
    await H.moodleLogin(p, H.MOODLE_ADMIN)
  })
  await test.step('Bước 2: mở liên kết "Phân tích CĐR" (launch.php) của khóa học demo – plugin cấp vé SSO', async () => {
    await p.goto(`${H.MOODLE}/local/clo/launch.php?courseid=${H.DEMO.moodleCourse}`)
  })
  await test.step('Bước 3: hệ thống nhận vé, tự đăng nhập và hiện menu của Bộ môn', async () => {
    await p.waitForURL(/localhost:8000/, { timeout: 20000 })
    await expect(nav(p, 'Kế hoạch đo PI')).toBeVisible()
  })
  await p.context().close()
})

// ================================================================== AD2 – Chương trình đào tạo
test('AD2 – Xem CTĐT KTDL-2026: PLO/PI, học phần, ma trận học phần – PI, mục tiêu', async ({ page }) => {
  await test.step('Bước 1: menu Chương trình đào tạo → bấm vào mã CTĐT KTDL-2026', async () => {
    await nav(page, 'Chương trình đào tạo').click()
    await page.getByRole('link', { name: 'KTDL-2026', exact: true }).click()
    await page.waitForURL(/\/programs\/\d+/)
    S.pid = Number(page.url().match(/\/programs\/(\d+)/)[1])
  })
  await test.step('Bước 2: thẻ "Chuẩn đầu ra" hiện 7 PLO, có PI6.2 và PI7.1', async () => {
    await expect(tab(page, 'Chuẩn đầu ra')).toContainText('7 PLO')
    await see(page, PI_A)
    await see(page, PI_B)
  })
  await test.step('Bước 3: mở lần lượt thẻ Học phần, Ma trận học phần – PI, Mục tiêu', async () => {
    await tab(page, 'Học phần').click()
    await expect(page.locator('table').first()).toBeVisible()
    await tab(page, 'Ma trận học phần – PI').click()
    await see(page, 'Ma trận học phần đáp ứng PI (Phụ lục II)')
    await tab(page, 'Mục tiêu').click()
    await see(page, 'Mục tiêu chung')
  })
})

// ================================================================== AD3 – Tạo học phần, gán CTĐT, giao PI
test('AD3 – Tạo học phần mới trong KTDL-2026, chặn trùng mã, mô tả, học kỳ/khối kiến thức, giao PI', async ({ page }) => {
  S.code = S.newCode
  await test.step('Bước 1: Học phần → "+ Học phần mới" → mã, tên, tín chỉ, tích KTDL-2026 → Lưu → tự mở tab Khai báo', async () => {
    await nav(page, 'Học phần').click()
    await page.getByRole('button', { name: '+ Học phần mới' }).click()
    const m = modal(page)
    await m.getByLabel('Mã môn').fill(S.code)
    await m.getByLabel('Tên môn học').fill('Khai phá dữ liệu (kiểm thử UI)')
    await m.getByLabel('Số tín chỉ').fill('3')
    await m.getByLabel('KTDL-2026 –').check()
    await m.getByRole('button', { name: 'Lưu' }).click()
    await page.waitForURL(/\/courses\/\d+\?tab=setup/)
    S.cid = Number(page.url().match(/courses\/(\d+)/)[1])
    await see(page, `Thông tin học phần ${S.code}`)
  })
  await test.step('Bước 2: tạo lại môn cùng mã → báo trùng, không tạo; đóng hộp thoại', async () => {
    await nav(page, 'Học phần').click()
    await page.getByRole('button', { name: '+ Học phần mới' }).click()
    const m = modal(page)
    await m.getByLabel('Mã môn').fill(S.code)
    await m.getByLabel('Tên môn học').fill('Môn trùng mã')
    await m.getByRole('button', { name: 'Lưu' }).click()
    await toast(page, /trùng|đã có|Duplicate/i)
    await m.getByRole('button', { name: 'Đóng' }).click()
  })
  await test.step('Bước 3: khung Thông tin học phần → nhập mô tả vắn tắt (bắt buộc khi duyệt đề cương) → Lưu', async () => {
    await goto(page, `/courses/${S.cid}?tab=setup`)
    const info = card(page, `Thông tin học phần ${S.code}`)
    await info.getByLabel('Mô tả vắn tắt học phần').fill('Học phần giới thiệu quy trình khai phá dữ liệu: tiền xử lý, luật kết hợp, phân lớp và gom cụm.')
    await info.getByRole('button', { name: 'Lưu' }).click()
    await toast(page, 'Đã lưu thông tin học phần')
  })
  await test.step('Bước 4: khung Thuộc chương trình đào tạo, dòng KTDL-2026 → học kỳ 5, khối kiến thức → Lưu', async () => {
    const row = card(page, 'Thuộc chương trình đào tạo').locator('tr').filter({ hasText: 'KTDL-2026' })
    await row.locator('input[type=number]').fill('5')
    await row.getByPlaceholder('VD Cơ sở ngành').fill('Kiến thức chuyên ngành')
    await row.getByRole('button', { name: 'Lưu' }).click()
    await toast(page, 'Đã lưu')
  })
  await test.step('Bước 5: CTĐT → Ma trận học phần – PI → dòng của môn: ô PI6.2 chọn 3, ô PI7.1 chọn 4', async () => {
    await goto(page, `/programs/${S.pid}?tab=matrix`)
    const head = page.locator('table.mx thead tr').nth(1)
    await expect(head.locator('th', { hasText: PI_A })).toBeVisible()            // chờ bảng tải xong
    const row = page.locator('table.mx tbody tr').filter({ has: page.getByRole('link', { name: S.code, exact: true }) })
    for (const [pi, level] of [[PI_A, '3'], [PI_B, '4']]) {
      const idx = await head.locator('th').evaluateAll((ths, c) => ths.findIndex(t => t.textContent.trim() === c), pi)
      await row.locator('td').nth(idx).click()                                   // bấm ô → hộp chọn mức
      await modal(page).getByRole('button', { name: level, exact: true }).click()
      await expect(page.locator('.modal')).toHaveCount(0)
      await expect(row.locator('td').nth(idx)).toHaveText(level)                // ô hiện mức vừa chọn
    }
  })
  await test.step('Bước 6: đề cương mục 5 có 2 PI, đều tô đỏ "Chưa có CLO" (chưa khai báo CLO)', async () => {
    await goto(page, `/courses/${S.cid}?tab=syllabus`)
    for (const pi of [PI_A, PI_B]) {
      const r = page.locator('tr.warn-row').filter({ hasText: pi })
      await expect(r).toBeVisible()
      await see(r, 'Chưa có CLO')
    }
  })
})

// ================================================================== AD4 – Chương và CLO gắn PI
test('AD4 – Thêm chương (Enter để lưu), CLO gắn PI, chi tiết chương; mục 5 hết tô đỏ', async ({ page }) => {
  await goto(page, `/courses/${S.cid}?tab=setup`)
  const box = card(page, 'Đề cương – các chương')
  await test.step('Bước 1: ô "Tên chương mới…" → gõ tên → thấy nhắc "Chưa lưu" → nhấn Enter → chương được lưu', async () => {
    for (const [k, name] of [[1, 'Tiền xử lý dữ liệu'], [2, 'Luật kết hợp và phân lớp']]) {
      const inp = box.getByPlaceholder(/Tên chương mới/)
      await inp.fill(name)
      await expect(box.getByText('Chưa lưu')).toBeVisible()
      await inp.press('Enter')
      await expect(box.locator('.card-h h3')).toHaveText(`Đề cương – các chương (${k})`)
    }
  })
  const addClo = async (code, desc, bloom, pi, level, badge) => {
    await card(page, 'CĐR môn học – CLO').getByRole('button', { name: '+ CLO' }).click()
    const m = modal(page)
    await m.getByLabel('Mã CLO').fill(code)
    await pick(m.getByLabel('Mức Bloom mục tiêu'), bloom)
    await m.getByLabel('Nội dung CLO').fill(desc)
    const row = m.locator('.clo-w').filter({ has: page.locator('b', { hasText: new RegExp(`^${pi.replace('.', '\\.')}$`) }) })
    await expect(row.locator('.pill.green')).toHaveText(badge)                  // "CTĐT giao: …" lấy từ ma trận ở AD3
    await row.locator('input[type=checkbox]').check()
    await row.locator('select').selectOption(level)
    await m.getByRole('button', { name: 'Lưu' }).click()
    await toast(page, 'Đã lưu CLO')
  }
  await test.step('Bước 2: + CLO → CLO1 (Bloom 2. Hiểu) tích PI6.2 mức R; form có nhãn "CTĐT giao: 3"', async () => {
    await addClo('CLO1', 'Trình bày được quy trình khai phá và tiền xử lý dữ liệu', '2. Hiểu', PI_A, 'R', 'CTĐT giao: 3')
  })
  await test.step('Bước 3: + CLO → CLO2 (Bloom 3. Vận dụng) tích PI7.1 mức M; form có nhãn "CTĐT giao: 4"', async () => {
    await addClo('CLO2', 'Áp dụng được thuật toán luật kết hợp và phân lớp', '3. Vận dụng', PI_B, 'M', 'CTĐT giao: 4')
  })
  await test.step('Bước 4: bảng CLO hiện "PLO6 › PI6.2 (R)" và "PLO7 › PI7.1 (M)" (CLO – PLO tự suy ra từ PI)', async () => {
    const c = card(page, 'CĐR môn học – CLO')
    await see(c, 'PLO6 › PI6.2 (R)')
    await see(c, 'PLO7 › PI7.1 (M)')
  })
  await test.step('Bước 5: nút "Chi tiết" từng chương → nội dung, LT 10, TH 5, tích CLO của chương → Lưu', async () => {
    for (const [i, clo] of [[0, 'CLO1'], [1, 'CLO2']]) {
      await box.locator('tbody tr').nth(i).getByRole('button', { name: 'Chi tiết' }).click()
      const m = modal(page)
      await m.getByLabel('Nội dung chi tiết').fill(`Nội dung chi tiết chương ${i + 1}`)
      await m.getByLabel('Số tiết lý thuyết').fill('10')
      await m.getByLabel('Số tiết thực hành').fill('5')
      await m.locator('label.chk', { hasText: clo }).locator('input').check()
      await m.getByRole('button', { name: 'Lưu' }).click()
      await toast(page, 'Đã lưu chương')
    }
    await see(box.locator('tbody tr').nth(0), '10/5 · CLO1')
    await see(box.locator('tbody tr').nth(1), '10/5 · CLO2')
  })
  await test.step('Bước 6: đề cương mục 5 hết tô đỏ: PI6.2 có CLO1 (R), PI7.1 có CLO2 (M)', async () => {
    await tab(page, 'Đề cương chi tiết').click()
    await page.locator('h4', { hasText: '5. Học phần đáp ứng' }).waitFor()
    await expect(page.locator('tr.warn-row')).toHaveCount(0)
    await see(page.locator('tr').filter({ hasText: PI_A }).last(), 'CLO1 (R)')
    await see(page.locator('tr').filter({ hasText: PI_B }).last(), 'CLO2 (M)')
  })
})

// ================================================================== AD5 – Lớp học phần
test('AD5 – Mở lớp HP cho giảng viên Nguyễn Thành Sơn (HKII 24-25)', async ({ page }) => {
  await test.step('Bước 1: trang môn → thẻ Lớp học phần → "+ Lớp HP"', async () => {
    await goto(page, `/courses/${S.cid}?tab=sections`)
    await page.getByRole('button', { name: '+ Lớp HP' }).click()
  })
  await test.step('Bước 2: chọn HKII 24-25, nhập mã lớp, chọn GV phụ trách → Lưu', async () => {
    // HKII: PI7.1 đã được đo ở môn demo trong HKI, mà CSDL chỉ cho mỗi PI một kế hoạch đo/học kỳ (dùng ở AD7)
    const m = modal(page)
    await pick(m.getByLabel('Học kỳ'), 'HKII 24-25')
    await m.getByLabel('Mã lớp học phần').fill(`${S.code}_01`)
    await pick(m.getByLabel('Giảng viên phụ trách'), 'Nguyễn Thành Sơn')
    await m.getByRole('button', { name: 'Lưu' }).click()
    await expect(page.locator('.modal')).toHaveCount(0)
  })
  await test.step('Bước 3: lớp mới có trong danh sách; ghi lại id lớp cho các bước của giảng viên', async () => {
    const link = page.getByRole('link', { name: `${S.code}_01` }).first()
    await expect(link).toBeVisible()
    S.cs = Number((await link.getAttribute('href')).match(/\/sections\/(\d+)/)[1])
  })
})

test('AD5b – "Đồng bộ các lớp với Moodle": lớp mới chưa có khóa Moodle trùng mã → báo kết quả, không lỗi @moodle', async ({ page }) => {
  await test.step('Bước 1: thẻ Lớp học phần → "⟳ Đồng bộ các lớp với Moodle" → thông báo kết quả theo từng lớp', async () => {
    await goto(page, `/courses/${S.cid}?tab=sections`)
    await page.getByRole('button', { name: /Đồng bộ các lớp với Moodle/ }).click()
    await toast(page, new RegExp(`${S.code}_01`), 30000)
  })
})

// ================================================================== AD6 – Đề cương có phiên bản
test('AD6 – Soạn đề cương, chặn tỷ trọng ≠ 100%, duyệt, tạo phiên bản mới, bản in không có nút', async ({ page }) => {
  await goto(page, `/courses/${S.cid}?tab=syllabus`)
  const checklist = page.locator('ul.checklist')
  const edit = n => page.locator('.syl h4', { hasText: new RegExp(`^${n}\\.`) }).getByRole('button', { name: 'Sửa' })
  await test.step('Bước 1: "+ Soạn đề cương" → khung kiểm tra có mục ✕, nút Duyệt bị khóa', async () => {
    await page.getByRole('button', { name: '+ Soạn đề cương' }).click()
    await see(page, 'Kiểm tra trước khi duyệt – bản nháp phiên bản 1')
    await expect(checklist.locator('li.bad').first()).toBeVisible()
    await expect(page.getByRole('button', { name: '✓ Duyệt đề cương' })).toBeDisabled()
  })
  await test.step('Bước 2: mục 1 → Sửa: tên tiếng Anh, 90 giờ tự học, áp dụng HKI 24-25 → Lưu', async () => {
    await edit(1).click()
    const m = modal(page)
    await m.getByLabel('Tên học phần tiếng Anh').fill('Data Mining')
    await m.getByLabel('Số giờ tự học').fill('90')
    await pick(m.getByLabel('Áp dụng từ học kỳ'), 'HKI 24-25')
    await m.getByRole('button', { name: 'Lưu' }).click()
    await see(page, 'Data Mining')
  })
  await test.step('Bước 3: mục 3 (mục tiêu) và mục 7 (phương pháp giảng dạy) → nhập nội dung → Lưu', async () => {
    for (const [n, text] of [[3, 'Nắm vững quy trình khai phá dữ liệu và vận dụng các thuật toán cơ bản.'],
                             [7, 'Thuyết giảng, thực hành trên máy, đồ án nhóm.']]) {
      await edit(n).click()
      await modal(page).locator('textarea').fill(text)
      await modal(page).getByRole('button', { name: 'Lưu' }).click()
      await see(page, text)
    }
    await expect(page.locator('.syl tr', { hasText: 'Tổng số tiết' })).toContainText('20')   // chương đã nhập ở AD4
  })
  await test.step('Bước 4: mục 8 → 40% + 50% = 90% → dòng tổng đỏ, nút Lưu bị KHÓA', async () => {
    await edit(8).click()
    const m = modal(page)
    for (const [i, [name, method, w]] of [['Bài tập lớn', 'Tự luận', '40'], ['Thi cuối kỳ', 'Trắc nghiệm', '50']].entries()) {
      await m.getByRole('button', { name: '+ Thành phần' }).click()
      const r = m.locator('tbody tr').nth(i)
      await r.getByPlaceholder('VD Kiểm tra giữa kỳ').fill(name)
      await r.getByPlaceholder('Trắc nghiệm, tự luận…').fill(method)
      await r.locator('input[type=number]').fill(w)
      for (const c of ['CLO1', 'CLO2']) await r.locator('label.chk', { hasText: c }).locator('input').check()
    }
    await see(m, 'Tổng: 90%')
    await see(m, 'tổng tỷ trọng phải bằng 100% mới lưu được')
    await expect(m.getByRole('button', { name: 'Lưu' })).toBeDisabled()
  })
  await test.step('Bước 5: sửa thành phần 2 thành 60% → tổng 100% → Lưu → mục "Tổng tỷ trọng = 100%" thành ✓', async () => {
    const m = modal(page)
    await m.locator('tbody tr').nth(1).locator('input[type=number]').fill('60')
    await see(m, 'Tổng: 100%')
    await m.getByRole('button', { name: 'Lưu' }).click()
    await toast(page, 'Đã lưu đánh giá học phần')
    await expect(checklist.locator('li.ok', { hasText: 'Tổng tỷ trọng đánh giá = 100%' })).toBeVisible()
  })
  await test.step('Bước 6: mục 10 → thêm 1 giáo trình chính → Lưu', async () => {
    await edit(10).click()
    const m = modal(page)
    await m.getByRole('button', { name: '+ Tài liệu' }).click()
    await m.getByPlaceholder('Tác giả – Tên tài liệu, NXB, năm').fill('Han, Kamber, Pei – Data Mining: Concepts and Techniques, 2011')
    await m.getByRole('button', { name: 'Lưu' }).click()
    await see(page, 'Han, Kamber, Pei')
  })
  await test.step('Bước 7: mọi mục bắt buộc đạt → Duyệt → "Phiên bản 1: Đang áp dụng", hết nút Sửa', async () => {
    await expect(checklist.locator('li.bad')).toHaveCount(0)
    await page.getByRole('button', { name: '✓ Duyệt đề cương' }).click()
    await see(page, 'Phiên bản 1: Đang áp dụng')
    await see(page, 'Đề cương đã duyệt không sửa trực tiếp')
    await expect(page.locator('.syl h4').getByRole('button', { name: 'Sửa' })).toHaveCount(0)
  })
  await test.step('Bước 8: thẻ Thiết lập học phần → bước "Đề cương chi tiết đã được Bộ môn duyệt" có ✓', async () => {
    await tab(page, 'Thiết lập học phần').click()
    await expect(page.locator('ol.setup li.ok', { hasText: 'Đề cương chi tiết đã được Bộ môn duyệt' })).toBeVisible()
  })
  await test.step('Bước 9: "Tạo phiên bản mới" → bản nháp 2 chép nội dung bản 1; ô chọn xem lại được bản 1', async () => {
    await tab(page, 'Đề cương chi tiết').click()
    await page.getByRole('button', { name: 'Tạo phiên bản mới' }).click()
    await see(page, 'Phiên bản 2: Bản nháp')
    await see(page, 'Nắm vững quy trình khai phá dữ liệu')
    await pick(page.getByLabel('Xem phiên bản'), 'Phiên bản 1')
    await see(page, 'Phiên bản 1: Đang áp dụng')
  })
  await test.step('Bước 10: giả lập chế độ in → mọi phần "no-print" (nút bấm, khung kiểm tra) bị ẩn', async () => {
    await page.emulateMedia({ media: 'print' })
    const shown = await page.locator('.no-print').evaluateAll(els => els.filter(e => getComputedStyle(e).display !== 'none').length)
    await page.emulateMedia({ media: 'screen' })
    expect(shown).toBe(0)
  })
})

// ================================================================== AD7 – Kế hoạch đo PI, phân công
test('AD7 – Kế hoạch đo PI7.1 tại môn (không chọn CLO → lấy CLO gắn đúng PI); phân công đánh giá PI', async ({ page }) => {
  await test.step('Bước 1: menu Kế hoạch đo PI → chọn CTĐT KTDL-2026', async () => {
    await nav(page, 'Kế hoạch đo PI').click()
    await pick(page.getByLabel('Chương trình đào tạo').first(), 'KTDL-2026')
  })
  await test.step('Bước 2: xóa kế hoạch PI7.1 cũ của các lần kiểm thử trước (môn mã UI…) – mỗi PI chỉ 1 kế hoạch/học kỳ', async () => {
    const plans = card(page, 'Kế hoạch năm học')
    await expect(plans.locator('tbody tr').first()).toBeVisible()               // chờ bảng kế hoạch tải xong
    const old = plans.locator('tbody tr').filter({ hasText: PI_B }).filter({ hasText: /UI\d{6}/ })
    while (await old.count()) {
      page.once('dialog', d => d.accept())                                       // xác nhận xóa của trình duyệt
      await old.first().getByRole('button', { name: '✕' }).click()
      await toast(page, 'Đã xóa')
      await page.waitForTimeout(500)
    }
  })
  await test.step('Bước 3: "+ Thêm kế hoạch" → PI7.1, môn kiểm thử, HKII 24-25, phương pháp, chỉ tiêu 70, GV; KHÔNG tích CLO → Lưu', async () => {
    await page.getByRole('button', { name: '+ Thêm kế hoạch' }).click()
    const m = modal(page)
    await pick(field(m, 'PI'), PI_B)
    await pick(field(m, 'Môn học lấy minh chứng'), S.code)
    await pick(field(m, 'Học kỳ'), 'HKII 24-25')
    await field(m, 'Phương pháp').fill('Bài tập lớn + thi cuối kỳ')
    await field(m, 'Chỉ tiêu (%)').fill('70')
    await pick(field(m, 'GV phụ trách'), 'Nguyễn Thành Sơn')
    await see(m, 'gắn với chính PI này')                                         // gợi ý: không chọn CLO = dùng CLO gắn PI
    await m.getByRole('button', { name: 'Lưu' }).click()
    await toast(page, 'Đã lưu kế hoạch')
  })
  await test.step('Bước 4: kế hoạch mới có trong bảng năm học 2024-2025', async () => {
    await expect(page.locator('tr').filter({ hasText: S.code }).filter({ hasText: PI_B })).toBeVisible()
  })
  await test.step('Bước 5: "+ Phân công" → HKII 24-25, môn, GV, ghi chú → Lưu', async () => {
    await card(page, 'Phân công đánh giá PI theo học kỳ').getByRole('button', { name: '+ Phân công' }).click()
    const m = modal(page)
    await pick(field(m, 'Học kỳ'), 'HKII 24-25')
    await pick(field(m, 'Môn học'), S.code)
    await pick(field(m, 'Giảng viên'), 'Nguyễn Thành Sơn')
    await field(m, 'Ghi chú').fill('Đánh giá theo 2 CĐR môn học')
    await m.getByRole('button', { name: 'Lưu' }).click()
    await toast(page, 'Đã lưu phân công')
  })
})

// ================================================================== AD8 – Tổng hợp PLO
test('AD8 – Tổng hợp PLO: Tính lại, mở nhận xét PLO, xuất BM2/BM3 (.xlsx) và BM2 (.docx)', async ({ page }) => {
  await test.step('Bước 1: menu Tổng hợp PLO → CTĐT KTDL (có kết quả demo) → năm 2024-2025 → Tính lại', async () => {
    await nav(page, 'Tổng hợp PLO').click()
    await pick(page.getByLabel('Chương trình đào tạo').first(), 'KTDL –')
    await pick(page.getByLabel('Năm học'), '2024-2025')
    await page.getByRole('button', { name: 'Tính lại' }).click()
    await toast(page, 'Đã tính lại')
  })
  await test.step('Bước 2: bấm "Nhận xét" của PLO đầu tiên → hộp thoại nhận xét mở → đóng', async () => {
    await card(page, 'Kết quả đo lường các CĐR').getByRole('button', { name: 'Nhận xét' }).first().click()
    await expect(modal(page)).toBeVisible()
    await modal(page).getByRole('button', { name: 'Đóng' }).click()
  })
  await test.step('Bước 3: "⬇ Xuất BM2/BM3 (.xlsx)" và "⬇ Xuất BM2 (.docx)" → tải được tệp', async () => {
    let dl = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Xuất BM2/BM3 (.xlsx)' }).click()
    expect((await dl).suggestedFilename()).toMatch(/\.xlsx$/)
    dl = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Xuất BM2 (.docx)' }).click()
    expect((await dl).suggestedFilename()).toMatch(/\.docx$/)
  })
})

// ================================================================== AD9 – Kết nối Moodle
test('AD9 – Trang Kết nối Moodle: trạng thái Web Service, hàm của plugin 1.4.0 @moodle', async ({ page }) => {
  await test.step('Bước 1: menu Kết nối Moodle → có khung Trạng thái và khung Web Service & đăng nhập một lần', async () => {
    await nav(page, 'Kết nối Moodle').click()
    await expect(card(page, 'Trạng thái')).toBeVisible()
    await expect(card(page, 'Web Service & đăng nhập một lần')).toBeVisible()
  })
  await test.step('Bước 2: Web Service kết nối được → thấy hàm local_clo_restrict_users (plugin 1.4.0)', async () => {
    await see(page, 'local_clo_restrict_users', 20000)
  })
})
