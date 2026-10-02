"""Chụp màn hình giao diện (Playwright) phục vụ báo cáo + phát hiện lỗi console.
Chạy trên dữ liệu minh họa (sau 4_TAO_DU_LIEU_DEMO_TREN_MOODLE):  python tests/ui_screens.py [http://localhost:8000]
Các màn hình nhập câu hỏi / gán CLO thêm câu tạm vào ngân hàng rồi xóa lại; màn hình tạo đề giấy tạo bài KT tạm rồi xóa.
"""
import io
import sys
from pathlib import Path

import requests
from openpyxl import Workbook, load_workbook
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
OUT = Path(__file__).resolve().parents[2] / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
TMP = OUT / "_tmp"; TMP.mkdir(exist_ok=True)
errors = []


def login(page, u, p):
    page.goto(BASE + "/login"); page.evaluate("localStorage.clear()"); page.goto(BASE + "/login")
    page.fill("input >> nth=0", u); page.fill("input[type=password]", p); page.click("button.btn.primary")
    page.wait_for_selector(".side")


def shot(page, name, url=None, click=None, wait=".card", full=True):
    if url:
        page.goto(BASE + url)
    if click:
        page.click(click)
    page.wait_for_selector(wait); page.wait_for_timeout(900)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
    print("saved", name)


def api_token(u, p):
    return {"Authorization": "Bearer " + requests.post(BASE + "/api/auth/login", json={"username": u, "password": p}).json()["access_token"]}


def sample_questions() -> Path:
    """Tệp Excel minh họa: 5 câu chưa gán CLO/Bloom, 1 câu trùng, 1 câu thiếu đáp án."""
    wb = Workbook(); ws = wb.active
    ws.append(["STT", "Nội dung câu hỏi", "Phương án A", "Phương án B", "Phương án C", "Phương án D", "Đáp án đúng"])
    rows = [("Hàm nào trả về số dòng bị ảnh hưởng bởi câu lệnh gần nhất?", "@@ROWCOUNT", "@@ERROR", "@@IDENTITY", "SCOPE_IDENTITY()", "A"),
            ("Bảng ảo nào chứa dữ liệu mới trong trigger AFTER UPDATE?", "deleted", "inserted", "updated", "changed", "B"),
            ("Lệnh nào hoàn tác một giao tác đang thực hiện?", "COMMIT", "SAVE TRAN", "ROLLBACK", "END TRAN", "C"),
            ("Chỉ mục clustered quyết định điều gì của bảng?", "Thứ tự lưu vật lý của các dòng", "Quyền truy cập", "Kích thước cột", "Tên bảng", "A"),
            ("Quyền nào cho phép đọc dữ liệu của bảng?", "INSERT", "SELECT", "DELETE", "ALTER", "B"),
            ("Lệnh nào hoàn tác một giao tác đang thực hiện?", "COMMIT", "SAVE TRAN", "ROLLBACK", "END TRAN", "C"),
            ("Câu hỏi thiếu đáp án đúng", "X", "Y", "", "", "")]
    for i, r in enumerate(rows, 1):
        ws.append([i, *r])
    f = TMP / "cau_hoi_moi.xlsx"; wb.save(f)
    return f


with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    page = ctx.new_page()
    page.on("console", lambda m: m.type == "error" and errors.append(f"{page.url}: {m.text}"))
    page.on("pageerror", lambda e: errors.append(f"{page.url}: {e}"))
    page.goto(BASE + "/login"); page.wait_for_selector(".login"); page.screenshot(path=str(OUT / "01_login.png")); print("saved login")
    login(page, "gv.son", "Gv@123456")
    gv = api_token("gv.son", "Gv@123456")
    shot(page, "02_lop_hoc_phan", "/")
    shot(page, "03_bai_kiem_tra", "/sections/1")
    shot(page, "04_ngan_hang_cau_hoi", "/questions", wait=".tbl tbody tr")
    page.click("text=Chi tiết >> nth=23"); page.wait_for_selector(".modal"); page.wait_for_timeout(400)
    page.screenshot(path=str(OUT / "05_cau_hoi_bi_khoa.png")); page.keyboard.press("Escape"); page.goto(BASE + "/questions"); page.wait_for_selector(".tbl tbody tr")
    page.click("text=+ Thêm câu hỏi"); page.wait_for_selector(".modal"); page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "06_them_cau_hoi.png"))
    page.goto(BASE + "/sections/1"); page.wait_for_selector(".card"); page.click("text=+ Tạo bài kiểm tra"); page.wait_for_selector(".modal tbody tr")
    page.click(".modal button.chip:has-text('CLO2')"); page.click("text=Chọn tất cả đang lọc"); page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "07_tao_bai_kt.png"))
    shot(page, "08_quy_trinh_online", "/exams/2")
    shot(page, "09_quy_trinh_giay", "/exams/1", wait="text=Bài đã chấm trên Moodle")
    shot(page, "10_tong_quan_diem", "/exams/2", click="text=Tổng quan điểm", wait="canvas")
    page.goto(BASE + "/exams/2"); page.click("text=Phân tích câu hỏi"); page.wait_for_selector("canvas")
    page.click("tr:has-text('YEAR(NgayLap)') >> text=Phương án"); page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / "11_phan_tich_cau_hoi.png"), full_page=True); print("saved items")
    shot(page, "12_ket_qua_sinh_vien", "/exams/2", click="text=Kết quả sinh viên", wait=".tbl tbody tr")
    shot(page, "13_nhat_ky_dong_bo", "/exams/2", click="text=Nhật ký đồng bộ", wait=".tbl tbody tr")
    shot(page, "14_bm6b", "/sections/1/clo", wait="canvas")
    shot(page, "15_bm6a", "/sections/1/clo", click="text=BM6a – Kế hoạch đánh giá", wait=".tbl tbody tr")
    page.goto(BASE + "/sections/1/clo"); page.wait_for_selector("canvas"); page.click("text=Minh chứng >> nth=1"); page.wait_for_selector(".modal .tbl tbody tr"); page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "16_minh_chung_bm6c.png")); print("saved evidence")
    # thống kê lớp và hồ sơ từng sinh viên
    shot(page, "21_thong_ke_lop", "/sections/1/stats?exam=2", wait="canvas")
    sid = requests.get(BASE + "/api/class-sections/1/students", headers=gv).json()[0]["id"]
    shot(page, "22_ho_so_sinh_vien", f"/sections/1/students/{sid}?exam=2", wait="canvas")
    # bài thi giấy mới: màn hình tạo đề trên Moodle (bài KT tạm, xóa sau khi chụp)
    tmp_exam = requests.post(BASE + "/api/exams", headers=gv, json={"class_section_id": 1, "exam_title": "Kiểm tra giữa kỳ (giấy)", "exam_type": "paper",
                             "assessment_type": "process", "max_score": 10, "duration_minutes": 30,
                             "items": [{"question_id": q, "points": 1} for q in (2, 3, 6, 7, 9, 11, 12, 13, 16, 17)]}).json()["id"]
    shot(page, "25_tao_de_giay", f"/exams/{tmp_exam}", wait="text=Tạo đề thi giấy trên Moodle", full=False)
    requests.delete(BASE + f"/api/exams/{tmp_exam}", headers=gv)
    # nhập câu hỏi hàng loạt rồi gán CLO từ file (thêm câu tạm, xóa ở cuối)
    f = sample_questions()
    page.goto(BASE + "/questions"); page.wait_for_selector(".tbl tbody tr")
    page.click("text=Nhập câu hỏi từ file"); page.wait_for_selector(".modal")
    page.set_input_files(".modal input[type=file]", str(f)); page.wait_for_selector(".modal .stats"); page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "23_nhap_cau_hoi.png")); print("saved import")
    page.click(".modal button.primary:has-text('Nhập')"); page.wait_for_selector(".modal .alert.green"); page.wait_for_timeout(300)
    page.goto(BASE + "/questions"); page.wait_for_selector(".alert.amber"); page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / "04b_ngan_hang_chua_gan.png")); print("saved untagged")
    tpl = requests.get(BASE + "/api/questions/tagging-template?course_id=5&only_untagged=true", headers=gv).content
    wb = load_workbook(io.BytesIO(tpl)); ws = wb["GanCLO"]
    fill = [(2, "3 - Vận dụng", "CLO2"), (3, "2 - Hiểu", "CLO2:0.6; CLO4:0.4"), (4, "Vận dụng", "CLO3"), (5, "4 - Phân tích", "CLO4; CLO9"), (6, "2 - Hiểu", "CLO4")]
    new_ids = []
    for row, (ch, bl, clo) in zip(ws.iter_rows(min_row=2), fill):
        row[3].value, row[4].value, row[5].value = ch, bl, clo; new_ids.append(row[0].value)
    tagged = TMP / "gan_clo_da_dien.xlsx"; wb.save(tagged)
    page.click("button:has-text('Gán CLO/Bloom từ file') >> nth=0"); page.wait_for_selector(".modal")
    page.set_input_files(".modal input[type=file]", str(tagged)); page.wait_for_selector(".modal .stats"); page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "24_gan_clo_tu_file.png")); print("saved tagging")
    for q in new_ids:
        requests.delete(BASE + f"/api/questions/{q}", headers=gv)
    login(page, "admin", "Admin@123")
    shot(page, "17_ctdt_plo_pi", "/program")
    shot(page, "18_ke_hoach_pi_bm3b", "/pi-plans", wait=".tbl tbody tr")
    shot(page, "19_tong_hop_plo", "/plo-summary", wait="canvas")
    shot(page, "20_ket_noi_moodle", "/system", wait=".tbl")
    b.close()

print("\nConsole errors:" if errors else "\nKhông có lỗi console.")
for e in errors:
    print(" -", e)
