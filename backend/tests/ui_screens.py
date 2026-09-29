"""Chụp màn hình giao diện (Playwright) phục vụ báo cáo + phát hiện lỗi console. Chạy: python tests/ui_screens.py"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
OUT = Path(__file__).resolve().parents[2] / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
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
    page.wait_for_selector(wait); page.wait_for_timeout(700)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
    print("saved", name)


with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    page = ctx.new_page()
    page.on("console", lambda m: m.type == "error" and errors.append(f"{page.url}: {m.text}"))
    page.on("pageerror", lambda e: errors.append(f"{page.url}: {e}"))
    page.goto(BASE + "/login"); page.wait_for_selector(".login"); page.screenshot(path=str(OUT / "01_login.png")); print("saved login")
    login(page, "gv.son", "Gv@123456")
    shot(page, "02_lop_hoc_phan", "/")
    shot(page, "03_bai_kiem_tra", "/sections/1")
    shot(page, "04_ngan_hang_cau_hoi", "/questions", wait=".tbl tbody tr")
    page.click("text=Chi tiết >> nth=23"); page.wait_for_selector(".modal"); page.wait_for_timeout(400)
    page.screenshot(path=str(OUT / "05_cau_hoi_bi_khoa.png")); page.keyboard.press("Escape"); page.goto(BASE + "/questions"); page.wait_for_selector(".tbl tbody tr")
    page.click("text=+ Thêm câu hỏi"); page.wait_for_selector(".modal"); page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "06_them_cau_hoi.png"))
    page.goto(BASE + "/sections/1"); page.wait_for_selector(".card"); page.click("text=+ Tạo bài kiểm tra"); page.wait_for_selector(".modal tbody tr")
    page.click("text=CLO2"); page.click("text=Chọn tất cả đang lọc"); page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "07_tao_bai_kt.png"))
    shot(page, "08_quy_trinh_online", "/exams/2")
    shot(page, "09_quy_trinh_giay", "/exams/1")
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
    login(page, "admin", "Admin@123")
    shot(page, "17_ctdt_plo_pi", "/program")
    shot(page, "18_ke_hoach_pi_bm3b", "/pi-plans", wait=".tbl tbody tr")
    shot(page, "19_tong_hop_plo", "/plo-summary", wait="canvas")
    shot(page, "20_ket_noi_moodle", "/system", wait=".tbl")
    login(page, "22130001", "Sv@123456")
    shot(page, "21_sv_danh_sach", "/")
    shot(page, "22_sv_lo_trinh", "/me/exams/2", wait="canvas")
    b.close()

print("\nConsole errors:" if errors else "\nKhông có lỗi console.")
for e in errors:
    print(" -", e)
