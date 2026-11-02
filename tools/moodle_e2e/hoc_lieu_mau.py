"""Bài giảng tóm tắt MẪU của môn demo (Hệ quản trị CSDL – DBMS330284) dạng slide PDF – tải lên khóa học Moodle demo để
có học liệu cho gợi ý "nên đọc lại ở đâu" (RAG). Tự viết theo 6 chương của bộ câu hỏi demo (demo_data.Q), không dùng
slide thật của giảng viên. Có một slide dạng THẺ (hộp màu + mũi tên) – bộ đọc PDF coi là hình, VLM (nếu bật) mô tả.

Dựng bằng PyMuPDF với phông có dấu tiếng Việt của máy (Arial trên Windows, DejaVu Sans / Liberation Sans trên Linux).
"""
from __future__ import annotations

import os
from pathlib import Path

import pymupdf

TITLE = "Bài giảng tóm tắt – Hệ quản trị cơ sở dữ liệu"
FILENAME = "bai_giang_tom_tat_hqtcsdl.pdf"
W, H = 960, 540
BLUE = (0.10, 0.25, 0.60)

SLIDES: list[tuple[str, str, list[str]]] = [
    ("Chương 1. Tổng quan hệ quản trị CSDL", "Kiến trúc hệ quản trị CSDL", [
        "Bộ xử lý truy vấn (query processor): phân tích cú pháp, tối ưu và lập kế hoạch thực thi câu lệnh SQL.",
        "Bộ quản lý lưu trữ (storage manager): quản lý tệp dữ liệu, bộ đệm và chỉ mục trên đĩa.",
        "Bộ quản lý giao tác: điều khiển đồng thời và phục hồi sau sự cố.",
        "Độc lập dữ liệu logic: thay đổi lược đồ khái niệm mà không phải sửa chương trình ứng dụng.",
        "Độc lập dữ liệu vật lý: thay đổi cách lưu trữ mà không ảnh hưởng lược đồ khái niệm."]),
    ("Chương 1. Tổng quan hệ quản trị CSDL", "CSDL hệ thống và tệp của SQL Server", [
        "master: cấu hình cấp máy chủ – logins, cấu hình hệ thống, danh sách các CSDL.",
        "model: khuôn mẫu cho mọi CSDL mới; msdb: lịch công việc của SQL Server Agent, lịch sử sao lưu.",
        "tempdb: bảng tạm, kết quả trung gian – tạo lại mỗi lần khởi động dịch vụ.",
        "Tệp dữ liệu .mdf / .ndf chứa dữ liệu; tệp nhật ký giao tác .ldf ghi mọi thay đổi để phục hồi CSDL về trạng thái nhất quán sau sự cố.",
        "Nhóm lệnh: DDL (CREATE, ALTER, DROP TABLE), DML (SELECT, INSERT, UPDATE, DELETE), DCL (GRANT, REVOKE)."]),
    ("Chương 2. Lập trình T-SQL", "Biến, điều khiển luồng và xử lý lỗi", [
        "Khai báo và gán giá trị đầu: DECLARE @Tong INT = 0;  gán lại bằng SET hoặc SELECT.",
        "Vòng lặp WHILE điều kiện BEGIN ... END – kiểm tra điều kiện TRƯỚC mỗi lần lặp.",
        "Rẽ nhánh IF ... ELSE; khối lệnh đặt trong BEGIN ... END.",
        "TRY...CATCH: lỗi trong khối TRY chuyển sang CATCH; ERROR_MESSAGE(), ERROR_NUMBER(), ERROR_LINE() cho biết thông điệp, mã và dòng gây lỗi."]),
    ("Chương 2. Lập trình T-SQL", "Thủ tục lưu trữ và hàm người dùng", [
        "Thủ tục (stored procedure): CREATE PROCEDURE; tham số OUTPUT trả giá trị về cho nơi gọi.",
        "Gọi thủ tục: EXEC ten_thu_tuc @a = 1, @kq = @bien OUTPUT.",
        "Hàm vô hướng (scalar function): trả về một giá trị, dùng trong biểu thức.",
        "Hàm trả về bảng (table-valued function): dùng được trong mệnh đề FROM như một bảng.",
        "Hàm không được thay đổi dữ liệu của bảng; thủ tục thì được."]),
    ("Chương 3. Ràng buộc toàn vẹn và trigger", "Trigger AFTER và bảng inserted / deleted", [
        "Trigger AFTER chạy SAU khi INSERT / UPDATE / DELETE đã thực hiện trên bảng.",
        "Bảng tạm inserted: các dòng MỚI; bảng tạm deleted: các dòng CŨ (trước khi cập nhật / xóa).",
        "UPDATE = deleted (giá trị cũ) + inserted (giá trị mới).",
        "Ràng buộc liên quan nhiều bảng (tồn kho không âm sau khi xuất hàng) → kiểm tra bằng trigger, vi phạm thì ROLLBACK TRANSACTION để hủy cả thao tác gây ra."]),
    ("Chương 3. Ràng buộc toàn vẹn và trigger", "Trigger INSTEAD OF và khóa ngoại", [
        "Trigger INSTEAD OF chạy THAY CHO thao tác INSERT / UPDATE / DELETE gây ra nó.",
        "Ứng dụng điển hình: cập nhật dữ liệu qua khung nhìn (view) gồm nhiều bảng.",
        "Khóa ngoại ON DELETE CASCADE: xóa dòng cha thì tự động xóa các dòng con tham chiếu.",
        "ON DELETE SET NULL: đặt khóa ngoại của dòng con về NULL; NO ACTION: từ chối xóa."]),
    ("Chương 4. Giao tác và điều khiển đồng thời", "Tính chất ACID", [
        "Atomicity (nguyên tố): hoặc tất cả thao tác được thực hiện, hoặc không thao tác nào.",
        "Consistency (nhất quán): đưa CSDL từ trạng thái đúng sang trạng thái đúng.",
        "Isolation (cô lập): các giao tác đồng thời không thấy kết quả dở dang của nhau.",
        "Durability (bền vững): đã COMMIT thì không mất, kể cả khi hệ thống gặp sự cố."]),
    ("Chương 4. Giao tác và điều khiển đồng thời", "Các vấn đề đồng thời và mức cô lập", [
        "Dirty read: đọc dữ liệu giao tác khác đã ghi nhưng CHƯA COMMIT.",
        "Non-repeatable read: đọc lại cùng dòng thấy giá trị khác do giao tác khác đã sửa.",
        "Phantom read: truy vấn lặp lại trả về thêm dòng MỚI thỏa điều kiện do giao tác khác chèn.",
        "READ UNCOMMITTED < READ COMMITTED (chặn dirty read) < REPEATABLE READ < SERIALIZABLE.",
        "Mặc định SQL Server dùng READ COMMITTED."]),
    ("Chương 4. Giao tác và điều khiển đồng thời", "Khóa hai pha và bế tắc", [
        "Giao thức khóa hai pha (2PL): pha xin khóa rồi pha nhả khóa – bảo đảm lịch khả tuần tự.",
        "Bế tắc (deadlock): T1 giữ A chờ B, T2 giữ B chờ A.",
        "SQL Server phát hiện chu trình chờ, chọn một giao tác làm nạn nhân (victim) và hủy nó (lỗi 1205).",
        "Giảm bế tắc: truy cập tài nguyên theo cùng thứ tự, giao tác ngắn."]),
    ("Chương 5. Chỉ mục và tối ưu truy vấn", "Chỉ mục clustered và nonclustered", [
        "Clustered: sắp xếp vật lý các dòng theo khóa chỉ mục – mỗi bảng tối đa MỘT chỉ mục clustered.",
        "Nonclustered: cấu trúc riêng trỏ tới dòng dữ liệu – một bảng có nhiều chỉ mục nonclustered.",
        "Chỉ mục phức hợp (MaKH, NgayLap): phục vụ truy vấn lọc theo MaKH rồi sắp xếp theo NgayLap.",
        "Nhiều chỉ mục: đọc nhanh hơn nhưng INSERT / UPDATE / DELETE chậm hơn và tốn dung lượng."]),
    ("Chương 5. Chỉ mục và tối ưu truy vấn", "Điều kiện tìm kiếm được (SARGable) và kế hoạch thực thi", [
        "Áp dụng hàm lên cột – WHERE YEAR(NgayLap) = 2024 – làm điều kiện không còn SARGable, SQL Server không dùng Index Seek được.",
        "Viết lại: NgayLap >= '2024-01-01' AND NgayLap < '2025-01-01'.",
        "Execution plan (kế hoạch thực thi) cho biết truy vấn dùng Index Seek, Index Scan hay Table Scan.",
        "Xem bằng Display Estimated / Include Actual Execution Plan trong SSMS."]),
    ("Chương 6. Bảo mật, sao lưu và phục hồi", "Phân quyền", [
        "Cấp quyền: GRANT SELECT ON SinhVien TO u1;  thu hồi: REVOKE;  cấm: DENY.",
        "Vai trò CSDL cố định: db_datareader (đọc mọi bảng người dùng), db_datawriter (ghi), db_owner (toàn quyền trên CSDL).",
        "Login (cấp máy chủ) ánh xạ tới user (cấp CSDL)."]),
    ("Chương 6. Bảo mật, sao lưu và phục hồi", "Mô hình phục hồi (recovery model)", [
        "FULL: ghi đầy đủ nhật ký; cùng các bản sao lưu nhật ký cho phép phục hồi về một thời điểm cụ thể (point-in-time recovery).",
        "BULK_LOGGED: ghi tối thiểu thao tác hàng loạt – không bảo đảm phục hồi tới mọi thời điểm.",
        "SIMPLE: nhật ký tự cắt sau checkpoint – chỉ phục hồi về bản sao lưu gần nhất."]),
]

# slide dạng thẻ: ba loại bản sao lưu + thứ tự phục hồi
CARDS = ("Chương 6. Bảo mật, sao lưu và phục hồi", "Các loại bản sao lưu và thứ tự phục hồi", [
    ("FULL", "Toàn bộ dữ liệu tại thời điểm sao lưu", (0.85, 0.92, 1.0)),
    ("DIFFERENTIAL", "Các thay đổi kể từ bản FULL gần nhất", (0.88, 0.97, 0.88)),
    ("LOG", "Nhật ký giao tác kể từ lần sao lưu nhật ký trước", (1.0, 0.94, 0.82)),
], "Phục hồi: FULL → DIFFERENTIAL gần nhất → các bản LOG theo thứ tự (RESTORE ... WITH NORECOVERY, bản cuối WITH RECOVERY)")


def _font() -> tuple[str, str]:
    cands = [(r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
             ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
             ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")]
    windir = os.environ.get("WINDIR")
    if windir:
        cands.insert(0, (str(Path(windir) / "Fonts/arial.ttf"), str(Path(windir) / "Fonts/arialbd.ttf")))
    for reg, bold in cands:
        if os.path.exists(reg) and os.path.exists(bold):
            return reg, bold
    raise RuntimeError("Không tìm thấy phông có dấu tiếng Việt (Arial / DejaVu Sans / Liberation Sans) để dựng PDF mẫu")


def _head(page, reg, bold, chapter, title):
    page.insert_font(fontname="R", fontfile=reg)
    page.insert_font(fontname="B", fontfile=bold)
    page.insert_text((40, 34), chapter, fontname="R", fontsize=12, color=(0.4, 0.4, 0.4))
    page.insert_text((50, 92), title, fontname="B", fontsize=28, color=BLUE)


def _bullets(page, font: pymupdf.Font, lines: list[str], size: float = 17) -> None:
    """Mỗi ý một gạch đầu dòng, tự xuống dòng theo bề rộng chữ đo bằng phông thật."""
    y, x0, x1 = 140, 60, W - 50
    for ln in lines:
        words, cur, rows = ln.split(), "", []
        for w in words:
            t = f"{cur} {w}".strip()
            if cur and font.text_length("• " + t, fontsize=size) > x1 - x0:
                rows.append(cur); cur = w
            else:
                cur = t
        rows.append(cur)
        for k, row in enumerate(rows):
            page.insert_text((x0 if k == 0 else x0 + 16, y + 20), ("• " if k == 0 else "") + row, fontname="R", fontsize=size)
            y += size * 1.45
        y += 12


def build_pdf() -> bytes:
    reg, bold = _font()
    font = pymupdf.Font(fontfile=reg)
    doc = pymupdf.open()
    doc.set_metadata({"title": TITLE})
    for chapter, title, lines in SLIDES:
        page = doc.new_page(width=W, height=H)
        _head(page, reg, bold, chapter, title)
        _bullets(page, font, lines)
    # slide dạng thẻ: ngay sau slide mô hình phục hồi (cùng chương 6, trang cuối)
    chapter, title, cards, note = CARDS
    page = doc.new_page(width=W, height=H)
    _head(page, reg, bold, chapter, title)
    x, cw = 60, 260
    for k, (name, desc, fill) in enumerate(cards):
        r = pymupdf.Rect(x + k * (cw + 40), 150, x + k * (cw + 40) + cw, 330)
        page.draw_rect(r, color=BLUE, fill=fill, width=1.5, radius=0.08)
        page.insert_textbox(pymupdf.Rect(r.x0 + 14, r.y0 + 18, r.x1 - 14, r.y0 + 60), name, fontname="B", fontsize=20,
                            color=BLUE, align=1)
        page.insert_textbox(pymupdf.Rect(r.x0 + 14, r.y0 + 70, r.x1 - 14, r.y1 - 10), desc, fontname="R", fontsize=16,
                            align=1)
        if k < len(cards) - 1:                               # mũi tên sang thẻ kế tiếp
            page.draw_line((r.x1 + 6, 240), (r.x1 + 34, 240), color=BLUE, width=3)
            page.draw_polyline([(r.x1 + 26, 232), (r.x1 + 34, 240), (r.x1 + 26, 248)], color=BLUE, width=3)
    page.insert_textbox(pymupdf.Rect(60, 370, W - 60, 470), note, fontname="R", fontsize=16)
    return doc.tobytes(garbage=3, deflate=True)


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1] if len(sys.argv) > 1 else FILENAME)
    out.write_bytes(build_pdf())
    print(out.resolve())
