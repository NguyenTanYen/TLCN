# Hướng dẫn cài đặt trên máy Windows + XAMPP

Máy hiện có: MariaDB 11.4 chạy ở cổng 3306 (tài khoản `root` / `1234`, quản lý bằng HeidiSQL),
Apache của XAMPP chạy Moodle 4.5.14 tại `D:\xampp\htdocs\moodle` với CSDL `moodle_db`.
Hệ thống của nhóm đặt tại thư mục này (`D:\3. TLCN\HeThong`).

## Kiến trúc: hai hệ thống riêng, nói chuyện qua API

| | Moodle (LMS) | Hệ thống của nhóm (localhost:8000) |
|---|---|---|
| Ai dùng | Sinh viên, giảng viên | **Chỉ giảng viên / bộ môn** |
| Làm gì | SV làm bài kiểm tra; xem **Kết quả phân tích CĐR** (radar CLO, nhận định, chương cần ôn) | Soạn ngân hàng câu hỏi gắn CLO, Bloom, chương; tạo đề; đồng bộ – phân tích – báo cáo BM2/BM3/BM6 |
| Giao diện | Theme **UTE LMS** (giao diện học tập trực tuyến) | React |

Các luồng tích hợp:

1. **Nút “Phân tích CĐR” trên Moodle** (chỉ hiện với giảng viên / quản trị) → đăng nhập một lần (SSO) sang hệ thống
   bằng tài khoản Moodle, vào thẳng lớp học phần tương ứng. Vé đăng nhập ký HMAC-SHA256, sống 120 giây, dùng 1 lần.
2. **Tạo Quiz qua API**: ở bài kiểm tra, bấm *Tạo Quiz trên Moodle* → Web Service `local_clo_create_quiz` nhập câu hỏi
   (idnumber `QB-<id>`) vào ngân hàng câu hỏi của khóa học, tạo Quiz bật xáo trộn phương án và tự liên kết.
   (Cách thủ công tải XML + nhập ID Quiz vẫn còn.)
3. **Kéo bài làm về** (UC-03): *Đồng bộ & phân tích* đọc CSDL Moodle ở chế độ **chỉ đọc** qua cầu nối `sp_sync_exam`.
4. **Đẩy kết quả lên Moodle** (UC-04 A1 → UC-05): *Công bố kết quả lên Moodle* gửi kết quả từng SV qua Web Service
   `local_clo_push_results`. SV nhận thông báo (chuông) và xem tại *khóa học → Kết quả phân tích CĐR*.
   Chưa công bố → “Kết quả phân tích đang được bảo lưu” (E1); vắng thi → “Chưa đủ bằng chứng đánh giá” (E2).

Hệ thống không bao giờ ghi thẳng vào CSDL Moodle: đọc qua view chỉ đọc, ghi qua Web Service chính thức của Moodle.

## Các bước (bấm đúp theo thứ tự)

| Bước | Tệp | Việc làm |
|---|---|---|
| 0 | `0_CAU_HINH.bat` | (Chỉ sửa nếu đường dẫn khác) thư mục Moodle, `php.exe` của XAMPP, cổng hệ thống |
| 1 | `1_CAI_DAT_PYTHON.bat` | Tạo `.venv`, cài thư viện Python (chạy 1 lần, cần Internet) |
| 2 | `2_KHOI_TAO_CSDL.bat` | Tạo CSDL `assessment_db` (39 bảng), dữ liệu minh họa, cài cầu nối đọc `moodle_db` |
| 3 | `3_CAI_GIAO_DIEN_MOODLE.bat` | Cài theme **UTE LMS** + plugin **local_clo**; bật Web Service, tạo token và khóa SSO, ghi vào `backend\cau_hinh.env` |
| 4 | `4_TAO_DU_LIEU_DEMO_TREN_MOODLE.bat` | *(Tùy chọn)* tạo khóa học + 40 SV + Quiz có bài làm thật trên Moodle, đồng bộ, phân tích, công bố lên Moodle |
| 5 | `5_CHAY_HE_THONG.bat` | Chạy hệ thống tại http://localhost:8000 (giữ cửa sổ mở; chạy lại sau bước 3) |
| 6 | `6_CHAY_KIEM_THU.bat` | *(Tùy chọn)* chạy 44 ca kiểm thử tự động |

Có thể làm bước 2 bằng HeidiSQL: chạy (F9) lần lượt `database\heidisql\1_tao_csdl_assessment_db.sql`
rồi `database\heidisql\2_cau_noi_moodle_db.sql`.

## Tài khoản

| Nơi | Vai trò | Đăng nhập |
|---|---|---|
| Hệ thống (localhost:8000) | Bộ môn / quản trị | `admin` / `Admin@123` (hoặc bấm “Phân tích CĐR” từ tài khoản admin Moodle) |
| Hệ thống | Giảng viên | `gv.son` / `Gv@123456` (hoặc bấm “Phân tích CĐR” từ Moodle) |
| Moodle (sau bước 4) | Giảng viên | `gv.son` / `Gv@123456` |
| Moodle (sau bước 4) | Sinh viên | `22130001` … `22130040` / `Sv@123456` |

Giảng viên đăng nhập bằng nút trên Moodle lần đầu sẽ được tạo tài khoản nếu **mã giảng viên** trong danh sách bộ môn
trùng tên đăng nhập hoặc *ID number* của họ trên Moodle. Sinh viên không đăng nhập vào hệ thống của nhóm.

## Luồng demo
1. Moodle (giảng viên `gv.son`): menu trên cùng **Phân tích CĐR** → tự vào hệ thống.
2. Hệ thống: Lớp học phần → Bài kiểm tra → *Thi cuối kỳ (Moodle)* → **Đồng bộ & phân tích** → xem Phân tích câu hỏi,
   Kết quả CĐR (BM6) → **Công bố kết quả lên Moodle**.
3. Moodle (sinh viên `22130001`): chuông thông báo → khóa học → **Kết quả phân tích CĐR**: radar CLO so với ngưỡng
   và trung bình lớp, nhận định, lộ trình ôn tập theo chương.
4. Tạo đề mới trong hệ thống → **Tạo Quiz trên Moodle** → Quiz xuất hiện ngay trong khóa học.

## Plugin Moodle `local_clo`
- Thư mục `moodle\local\clo`. Cấu hình: *Quản trị hệ thống → Plugin → Plugin cục bộ → Kết nối hệ thống phân tích CĐR*
  (địa chỉ hệ thống, khóa SSO). Dịch vụ Web Service: `local_clo` (hàm `local_clo_create_quiz`, `local_clo_push_results`).
- Quyền: `local/clo:launch` (GV, quản lý), `local/clo:viewown` (SV), `local/clo:viewall` (GV), `local/clo:manage` (tài khoản token).
- Có thể chạy lại cấu hình bất cứ lúc nào: `php local\clo\cli\setup.php --appurl=http://localhost:8000 --envfile="...\backend\cau_hinh.env"`.

## Lỗi thường gặp
- `Access denied for user 'root'` → sửa mật khẩu trong `backend\cau_hinh.env` (dòng `DATABASE_URL`).
- Nút “Tạo Quiz”/“Công bố” báo *Chưa cấu hình kết nối Moodle* → chạy lại bước 3 rồi bước 5.
- Bấm “Phân tích CĐR” báo *chưa được bộ môn khai báo là giảng viên* → thêm giảng viên (mã GV = tên đăng nhập Moodle).
- Cổng 8000 bận → đổi `APP_PORT` trong `0_CAU_HINH.bat`, chạy lại bước 3 và 5.
