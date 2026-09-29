"""Dữ liệu minh họa cho môn DBMS330284 – Hệ quản trị cơ sở dữ liệu (HKI 2024-2025).

Mã môn, tên môn và GV lấy từ bảng "Phân công đánh giá PIs HKI 2023-2024"; PLO/PI lấy từ BM2 (KTDL).
Nội dung chương, CLO, câu hỏi và sinh viên là DỮ LIỆU MINH HỌA do nhóm soạn để chạy thử hệ thống.
"""

CHAPTERS = [
    (1, "Tổng quan hệ quản trị CSDL và SQL Server"),
    (2, "Lập trình T-SQL: biến, thủ tục, hàm"),
    (3, "Trigger và ràng buộc toàn vẹn"),
    (4, "Giao tác và điều khiển đồng thời"),
    (5, "Chỉ mục và tối ưu hóa truy vấn"),
    (6, "Bảo mật, phân quyền, sao lưu và phục hồi"),
]

# (mã, mô tả, bloom, [(plo_code, level)])
CLOS = [
    ("CLO1", "Trình bày được kiến trúc, các thành phần và chức năng của một hệ quản trị CSDL", 2, [("1.3", "R")]),
    ("CLO2", "Viết được thủ tục, hàm và trigger bằng T-SQL để hiện thực ràng buộc và nghiệp vụ", 3, [("1.3", "M"), ("4.3", "R")]),
    ("CLO3", "Phân tích được các vấn đề của giao tác đồng thời và chọn mức cô lập phù hợp", 4, [("4.3", "R")]),
    ("CLO4", "Áp dụng chỉ mục, tối ưu truy vấn và cơ chế bảo mật cho một CSDL cụ thể", 3, [("4.3", "M")]),
]

# Kế hoạch KT-ĐG CLO HKI 24-25 (BM6a): (clo, các bài KT, bài KT lấy minh chứng, phương pháp, ngưỡng %, chỉ tiêu %)
CLO_PLANS = [
    ("CLO1", "KT quá trình, Thi cuối kỳ", "any", "Bài KT trắc nghiệm", 60, 80),
    ("CLO2", "KT quá trình, Thi cuối kỳ", "final", "Bài KT trắc nghiệm", 60, 75),
    ("CLO3", "Thi cuối kỳ", "final", "Bài KT trắc nghiệm", 60, 70),
    ("CLO4", "Thi cuối kỳ", "final", "Bài KT trắc nghiệm", 60, 70),
]

# Câu hỏi: (chương, bloom, CLO, nội dung, [phương án], chỉ số đáp án đúng, độ khó mô phỏng b)
Q = [
    (1, 1, "CLO1", "Thành phần nào của hệ quản trị CSDL chịu trách nhiệm phân tích và tối ưu câu lệnh SQL trước khi thực thi?",
     ["Bộ quản lý bộ đệm (Buffer manager)", "Bộ xử lý truy vấn (Query processor)", "Bộ quản lý tệp (File manager)", "Bộ quản lý nhật ký (Log manager)"], 1, -1.2),
    (1, 2, "CLO1", "Tính độc lập dữ liệu logic (logical data independence) nghĩa là:",
     ["Thay đổi lược đồ khái niệm không làm ảnh hưởng các chương trình ứng dụng/khung nhìn",
      "Thay đổi cách lưu trữ vật lý không ảnh hưởng lược đồ khái niệm", "Dữ liệu không phụ thuộc hệ điều hành", "Mỗi người dùng có một bản sao dữ liệu riêng"], 0, -0.3),
    (1, 1, "CLO1", "Trong SQL Server, cơ sở dữ liệu hệ thống lưu thông tin cấu hình cấp máy chủ (logins, cấu hình) là:",
     ["tempdb", "model", "master", "msdb"], 2, -0.8),
    (1, 2, "CLO1", "Tệp nhật ký giao tác (.ldf) trong SQL Server được dùng chủ yếu để:",
     ["Lưu dữ liệu của các bảng", "Phục hồi CSDL về trạng thái nhất quán sau sự cố", "Lưu kế hoạch thực thi", "Lưu chỉ mục"], 1, -0.5),
    (1, 2, "CLO1", "Câu lệnh nào thuộc nhóm ngôn ngữ định nghĩa dữ liệu (DDL)?",
     ["SELECT", "UPDATE", "ALTER TABLE", "GRANT"], 2, -1.5),
    (2, 3, "CLO2", "Để khai báo biến @Tong kiểu số nguyên và gán giá trị 0 trong T-SQL, câu lệnh đúng là:",
     ["DECLARE @Tong INT = 0", "VAR @Tong INT := 0", "SET INT @Tong = 0", "DIM @Tong AS INT = 0"], 0, -1.0),
    (2, 3, "CLO2", "Tham số của thủ tục được khai báo với từ khóa OUTPUT dùng để:",
     ["Chỉ nhận giá trị đầu vào", "Trả giá trị từ thủ tục về cho nơi gọi", "Khai báo biến toàn cục", "Trả về một bảng"], 1, -0.2),
    (2, 3, "CLO2", "Hàm do người dùng định nghĩa loại nào trả về một bảng và có thể dùng trong mệnh đề FROM?",
     ["Scalar function", "Aggregate function", "Table-valued function", "System function"], 2, 0.1),
    (2, 4, "CLO2", "Đoạn lệnh: WHILE @i < 5 BEGIN SET @i = @i + 2 END với @i khởi tạo = 0. Sau khi kết thúc, @i bằng:",
     ["4", "5", "6", "8"], 2, 0.4),
    (2, 3, "CLO2", "Khối TRY...CATCH trong T-SQL: hàm nào trả về thông điệp lỗi trong khối CATCH?",
     ["@@ERROR", "ERROR_MESSAGE()", "RAISERROR()", "THROW"], 1, 0.0),
    (3, 3, "CLO2", "Trong trigger AFTER UPDATE, bảng tạm nào chứa giá trị CŨ của các dòng bị cập nhật?",
     ["inserted", "deleted", "updated", "old"], 1, 0.3),
    (3, 4, "CLO2", "Ràng buộc 'tổng số lượng tồn kho không âm sau mỗi lần xuất hàng' liên quan nhiều bảng nên nên được hiện thực bằng:",
     ["CHECK trên một cột", "DEFAULT", "Trigger", "UNIQUE"], 2, 0.2),
    (3, 3, "CLO2", "Lệnh nào hủy bỏ thao tác gây vi phạm ràng buộc bên trong trigger?",
     ["ROLLBACK TRANSACTION", "COMMIT", "RETURN 0", "BREAK"], 0, 0.5),
    (3, 2, "CLO2", "Trigger INSTEAD OF thường được dùng để:",
     ["Chạy sau khi lệnh đã ghi dữ liệu", "Thay thế thao tác INSERT/UPDATE/DELETE, ví dụ cập nhật qua khung nhìn", "Tạo chỉ mục", "Sao lưu dữ liệu"], 1, 0.6),
    (3, 2, "CLO2", "Khóa ngoại khai báo ON DELETE CASCADE sẽ:",
     ["Chặn xóa dòng cha", "Tự động xóa các dòng con tham chiếu", "Gán NULL cho dòng con", "Không có tác dụng"], 1, -0.9),
    (4, 2, "CLO3", "Tính chất nào của giao tác bảo đảm 'hoặc tất cả thao tác được thực hiện, hoặc không thao tác nào'?",
     ["Consistency", "Isolation", "Atomicity", "Durability"], 2, -1.1),
    (4, 4, "CLO3", "Hiện tượng một giao tác đọc dữ liệu do giao tác khác ghi nhưng CHƯA COMMIT được gọi là:",
     ["Lost update", "Dirty read", "Phantom read", "Non-repeatable read"], 1, 0.0),
    (4, 4, "CLO3", "Mức cô lập thấp nhất ngăn được dirty read nhưng vẫn có thể xảy ra non-repeatable read là:",
     ["READ UNCOMMITTED", "READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"], 1, 0.7),
    (4, 4, "CLO3", "Hai giao tác T1 giữ khóa A chờ B, T2 giữ khóa B chờ A. Hệ quản trị xử lý tình huống này bằng cách:",
     ["Chờ vô hạn", "Chọn một giao tác làm nạn nhân (victim) và hủy", "Commit cả hai", "Tăng mức cô lập"], 1, 0.2),
    (4, 5, "CLO3", "Giao thức khóa hai pha (2PL) bảo đảm lịch thao tác:",
     ["Khả tuần tự (serializable)", "Không có deadlock", "Không cần nhật ký", "Có thể đọc dữ liệu chưa commit"], 0, 1.0),
    (4, 4, "CLO3", "Phantom read xảy ra khi:",
     ["Một dòng bị xóa hai lần", "Truy vấn lặp lại trả về thêm các dòng mới thỏa điều kiện do giao tác khác chèn",
      "Đọc dữ liệu chưa commit", "Hai giao tác cùng cập nhật một dòng"], 1, 0.8),
    (5, 2, "CLO4", "Mỗi bảng trong SQL Server có tối đa bao nhiêu chỉ mục clustered?",
     ["0", "1", "2", "Không giới hạn"], 1, -0.7),
    (5, 3, "CLO4", "Truy vấn thường xuyên lọc theo cột MaKH và sắp xếp theo NgayLap. Chỉ mục phù hợp nhất là:",
     ["Chỉ mục trên (NgayLap)", "Chỉ mục phức hợp (MaKH, NgayLap)", "Chỉ mục trên (TongTien)", "Không cần chỉ mục"], 1, 0.3),
    (5, 4, "CLO4", "Điều kiện WHERE YEAR(NgayLap) = 2024 thường KHÔNG tận dụng được chỉ mục trên NgayLap vì:",
     ["Hàm YEAR chỉ chạy trên máy khách", "Áp dụng hàm lên cột làm điều kiện không còn dạng tìm kiếm được (non-SARGable)",
      "Chỉ mục không hỗ trợ kiểu ngày", "Năm 2024 là năm nhuận"], 1, -1.2),
    (5, 3, "CLO4", "Công cụ nào của SQL Server cho biết truy vấn dùng Index Seek hay Table Scan?",
     ["Execution plan", "SQL Server Agent", "Database Mail", "Import/Export Wizard"], 0, -0.4),
    (5, 4, "CLO4", "Nhược điểm chính khi tạo quá nhiều chỉ mục trên một bảng là:",
     ["Truy vấn SELECT chậm hơn", "Thao tác INSERT/UPDATE/DELETE chậm hơn và tốn dung lượng", "Không thể tạo khóa chính", "Mất dữ liệu"], 1, 0.1),
    (6, 3, "CLO4", "Câu lệnh cấp quyền SELECT trên bảng SinhVien cho người dùng u1 là:",
     ["GRANT SELECT ON SinhVien TO u1", "ALLOW SELECT SinhVien u1", "PERMIT u1 SELECT SinhVien", "SET SELECT ON SinhVien = u1"], 0, -0.8),
    (6, 2, "CLO4", "Bản sao lưu differential chứa:",
     ["Toàn bộ CSDL", "Các thay đổi kể từ bản sao lưu FULL gần nhất", "Chỉ nhật ký giao tác", "Chỉ cấu trúc bảng"], 1, 0.4),
    (6, 4, "CLO4", "Để phục hồi CSDL về một thời điểm cụ thể (point-in-time), CSDL phải dùng recovery model:",
     ["SIMPLE", "FULL", "BULK_LOGGED hoặc SIMPLE", "Không cần"], 1, 1.3),
    (6, 3, "CLO4", "Vai trò (role) cơ sở dữ liệu nào cho phép người dùng đọc dữ liệu mọi bảng người dùng?",
     ["db_owner", "db_datareader", "db_datawriter", "public"], 1, -0.2),
]
# Câu 24 (non-SARGable) mô phỏng "câu có vấn đề": SV giỏi hay chọn nhầm phương án A -> DI âm/thấp
TRAP_QUESTION_INDEX = 23

LAST = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý"]
MID = ["Văn", "Thị", "Minh", "Ngọc", "Quốc", "Thanh", "Hoàng", "Gia", "Anh", "Đức", "Thu", "Bảo"]
FIRST = ["An", "Bình", "Châu", "Dũng", "Duy", "Giang", "Hà", "Hải", "Hiếu", "Hòa", "Huy", "Khang", "Khoa", "Linh", "Long",
         "Mai", "Nam", "Nga", "Nhân", "Nhi", "Phát", "Phúc", "Quân", "Quyên", "Sơn", "Tâm", "Thảo", "Thắng", "Tiến", "Trang",
         "Trí", "Trung", "Tú", "Tuấn", "Uyên", "Vy", "Việt", "Yến", "Khánh", "Lộc"]


def student_list(n: int = 40) -> list[tuple[str, str]]:
    out = []
    for i in range(n):
        name = f"{LAST[(i * 7) % len(LAST)]} {MID[(i * 5) % len(MID)]} {FIRST[i % len(FIRST)]}"
        out.append((f"2213{i + 1:04d}", name))
    return out
