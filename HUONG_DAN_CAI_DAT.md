# Hướng dẫn cài đặt trên máy Windows + XAMPP

Máy hiện có: MariaDB 11.4 chạy ở cổng 3306 (tài khoản `root` / `1234`, quản lý bằng HeidiSQL),
Apache của XAMPP chạy Moodle 4.5.14 tại `D:\xampp\htdocs\moodle` với CSDL `moodle_db`.
Hệ thống của nhóm đặt tại thư mục này (`D:\3. TLCN\HeThong`).

## Kiến trúc: hai hệ thống riêng, nói chuyện qua API

| | Moodle (LMS) | Hệ thống của nhóm (localhost:8000) |
|---|---|---|
| Ai dùng | Sinh viên, giảng viên | **Chỉ giảng viên / bộ môn** |
| Làm gì | SV làm Quiz online; **bài thi giấy: in đề + phiếu, nhận diện phiếu quét, chấm điểm** (Offline Quiz); SV xem **Kết quả phân tích CĐR** | Soạn ngân hàng câu hỏi gắn CLO, Bloom, chương; ra đề (online/giấy); kéo kết quả đã chấm về – phân tích – báo cáo BM2/BM3/BM6 |
| Giao diện | Theme **UTE LMS** (giao diện học tập trực tuyến) | React |

Các luồng tích hợp:

1. **Nút “Phân tích CĐR” trên Moodle** (chỉ hiện với giảng viên / quản trị) → đăng nhập một lần (SSO) sang hệ thống
   bằng tài khoản Moodle, vào thẳng lớp học phần tương ứng. Vé đăng nhập ký HMAC-SHA256, sống 120 giây, dùng 1 lần.
2. **Tạo Quiz qua API**: ở bài kiểm tra, bấm *Tạo Quiz trên Moodle* → Web Service `local_clo_create_quiz` nhập câu hỏi
   (idnumber `QB-<id>`) vào ngân hàng câu hỏi của khóa học, tạo Quiz bật xáo trộn phương án và tự liên kết.
   (Cách thủ công tải XML + nhập ID Quiz vẫn còn.)
3. **Bài thi giấy – Moodle chấm**: ở bài thi giấy, bấm *Tạo đề thi giấy trên Moodle* → Web Service `local_clo_create_offlinequiz`
   tạo **Offline Quiz** (plugin `mod_offlinequiz`) với N mã đề, Moodle sinh **đề in, phiếu trả lời, đáp án** từng mã đề;
   hệ thống chỉ chuyển tệp cho GV tải (từng tệp hoặc .zip). Sau khi thi: quét phiếu thành ảnh PNG/JPG/TIFF (hoặc .zip nhiều ảnh),
   tải lên trang Offline Quiz trên Moodle → **Moodle nhận diện MSSV, mã đề, ô đánh dấu và chấm**. Phiếu nhận diện lỗi được
   sửa ngay trên Moodle. (Tải tệp PDF quét cần ImageMagick trên máy chủ Moodle – nên quét ra ảnh.)
4. **Kéo bài làm về** (UC-03): *Đồng bộ & phân tích* đọc CSDL Moodle ở chế độ **chỉ đọc** qua cầu nối `sp_sync_exam`
   (Quiz: lượt được tính điểm; Offline Quiz: kết quả đã chấm, mã đề A/B/C…). Với bài giấy, hệ thống nhờ Moodle chấm ngay các phiếu
   đang chờ (`local_clo_process_scans`) vì XAMPP thường không bật cron của Moodle.
5. **Đẩy kết quả lên Moodle** (UC-04 A1 → UC-05): *Công bố kết quả lên Moodle* gửi kết quả từng SV qua Web Service
   `local_clo_push_results`. SV nhận thông báo (chuông) và xem tại *khóa học → Kết quả phân tích CĐR*.
   Chưa công bố → “Kết quả phân tích đang được bảo lưu” (E1); vắng thi → “Chưa đủ bằng chứng đánh giá” (E2).

Hệ thống không bao giờ ghi thẳng vào CSDL Moodle: đọc qua view chỉ đọc, ghi qua Web Service chính thức của Moodle.

## Các bước (bấm đúp theo thứ tự)

| Bước | Tệp | Việc làm |
|---|---|---|
| 0 | `0_CAU_HINH.bat` | (Không cần chạy, không cần sửa) **tự dò** XAMPP (Registry, ổ đĩa chứa dự án, rồi `C:`…`F:\xampp`) và chọn XAMPP có **Moodle 4.5** trong `htdocs\moodle45` hoặc `htdocs\moodle` (bỏ qua Moodle cũ hơn); PHP = `<XAMPP>\php\php.exe`, cổng 8000; lần đầu tự tạo `backend\cau_hinh.env` từ `cau_hinh.env.example`. Moodle/XAMPP đặt ở chỗ khác: chép `0_CAU_HINH_MAY.example.bat` thành `0_CAU_HINH_MAY.bat` rồi khai báo `MOODLE_DIR`, `PHP_BIN`, `APP_PORT` (tệp này không đưa lên Git) |
| 1 | `1_CAI_DAT_PYTHON.bat` | Tạo `.venv`, cài thư viện Python (chạy 1 lần, cần Internet) |
| 2 | `2_KHOI_TAO_CSDL.bat` | Tạo CSDL `assessment_db` (39 bảng), dữ liệu minh họa, cài cầu nối đọc `moodle_db` |
| 3 | `3_CAI_GIAO_DIEN_MOODLE.bat` | Cài theme **UTE LMS** + plugin **local_clo** + plugin **Offline Quiz** (chấm bài giấy); bật Web Service, tạo token, khóa SSO, cấu hình phiếu (MSSV 8 số, nhãn tiếng Việt), ghi `backend\cau_hinh.env` |<br>Tạo tài khoản dịch vụ Moodle `clo_service` (thay cho token quản trị) và tài khoản CSDL `clo_app` **chỉ đọc CSDL Moodle**; tài khoản root được giữ ở dòng `DATABASE_ADMIN_URL` để dùng cho bước 2, 4, 6.
| 4 | `4_TAO_DU_LIEU_DEMO_TREN_MOODLE.bat` | *(Tùy chọn)* tạo khóa học + 40 SV; Quiz có bài làm thật; **bài giấy 2 mã đề: 38 phiếu tô sẵn được Moodle nhận diện & chấm**; đồng bộ, phân tích, công bố |
| 5 | `5_CHAY_HE_THONG.bat` | Chạy hệ thống tại http://localhost:8000 (giữ cửa sổ mở; chạy lại sau bước 3) |
| 6 | `6_CHAY_KIEM_THU.bat` | *(Tùy chọn)* chạy 77 ca kiểm thử tự động – kiểm thử **dựng lại `assessment_db`**, chạy xong hãy chạy lại bước 4 để có lại dữ liệu demo |
| 7 | `7_DON_DEP_GIT.bat` | *(Khi dùng GitHub)* bỏ `.venv`, `__pycache__`, `cau_hinh.env`, `0_CAU_HINH_MAY.bat` (mật khẩu, token, đường dẫn riêng) khỏi Git theo `.gitignore`, commit và đẩy lên |
| – | `tools\KIEM_TRA_DO_LUONG.bat` | *(Tùy chọn)* tính lại độc lập p, DI, mức đạt CLO, BM6b, PI, PLO, CTĐT từ dữ liệu bài làm và so với số liệu hệ thống (kết quả mong đợi: 0 sai lệch) |

Có thể làm bước 2 bằng HeidiSQL: chạy (F9) lần lượt `database\heidisql\1_tao_csdl_assessment_db.sql`
rồi `database\heidisql\2_cau_noi_moodle_db.sql`.

## Tài khoản

| Nơi | Vai trò | Đăng nhập |
|---|---|---|
| Hệ thống (localhost:8000) | Bộ môn / quản trị | `admin` / `Admin@123` (hoặc bấm “Phân tích CĐR” từ tài khoản admin Moodle) |
| Hệ thống | Giảng viên | `gv.son` / `Gv@123456` (hoặc bấm “Phân tích CĐR” từ Moodle) |
| Moodle (sau bước 4) | Giảng viên | `gv.son` / `Gv@123456` |
| Moodle (sau bước 4) | Sinh viên | `22130001` … `22130040` / `Sv@123456` |

Trang đăng nhập của hệ thống chỉ hiện nút điền nhanh tài khoản minh họa khi `backend\cau_hinh.env` có `DEMO_MODE=true`
(bước 4 tự thêm dòng này; khi triển khai thật hãy xóa dòng đó rồi chạy lại bước 5).

Phân quyền: giảng viên chỉ thao tác trên lớp học phần mình phụ trách và ngân hàng câu hỏi của môn mình dạy; khi gắn
khóa học / Quiz / Offline Quiz của Moodle, hệ thống kiểm tra tài khoản Moodle cùng tên là *giảng viên* của khóa học đó.

Giảng viên đăng nhập bằng nút trên Moodle lần đầu sẽ được tạo tài khoản nếu **mã giảng viên** trong danh sách bộ môn
trùng tên đăng nhập hoặc *ID number* của họ trên Moodle. Sinh viên không đăng nhập vào hệ thống của nhóm.

## Luồng demo
0. **Ra đề theo ma trận:** Lớp học phần → *+ Tạo bài kiểm tra* → khung *Sinh đề tự động theo ma trận*: nhập số câu
   (vd 20), chọn phạm vi chương (bấm vài chương = kiểm tra chương) và phân bố mức Bloom → **Sinh đề theo ma trận**.
   Hệ thống tự chọn câu phủ đủ chương, mức độ, CLO; ô/CLO thiếu câu được báo cụ thể. Có thể tích *Nhập ma trận chi tiết*
   để tự đặt số câu từng ô (số nhỏ cạnh ô là số câu ngân hàng đang có), rồi chỉnh tay trong danh sách câu bên dưới.
1. Moodle (giảng viên `gv.son`): menu trên cùng **Phân tích CĐR** → tự vào hệ thống.
2. Hệ thống: Lớp học phần → Bài kiểm tra → *Thi cuối kỳ (Moodle)* → **Đồng bộ & phân tích** → xem Phân tích câu hỏi,
   Kết quả CĐR (BM6) → **Công bố kết quả lên Moodle**.
   Xuất biểu mẫu: **Xuất bộ BM6 của lớp** (BM6a, BM6b, minh chứng từng CLO theo đúng loại bài KT trong kế hoạch BM6a) hoặc **Xuất theo từng bài KT** → tệp BM6c riêng của bài đó (cũng có nút *Xuất BM6c bài KT này* ở trang bài kiểm tra).
   Bộ môn: *Tổng hợp PLO* → **Xuất BM2/BM3 (.xlsx)** hoặc **Xuất BM2 (.docx)**; *Kế hoạch đo PI* → **Xuất bảng phân công** đánh giá PIs của học kỳ.
3. Moodle (sinh viên `22130001`): chuông thông báo → khóa học → **Kết quả phân tích CĐR**: radar CLO so với ngưỡng
   và trung bình lớp, nhận định, lộ trình ôn tập theo chương.
4. Bài giấy *Kiểm tra quá trình (giấy)*: tải đề/phiếu/đáp án 2 mã đề (Moodle sinh) → trên Moodle mở Offline Quiz để xem 38 phiếu
   đã quét, được nhận diện và chấm → trong hệ thống *Đồng bộ & phân tích*.

   **Trang quét phiếu trên Moodle ở đâu?** Khóa *Hệ quản trị cơ sở dữ liệu – DBMS330284_01* → hoạt động
   *Kiểm tra quá trình (giấy)* → tab **Kết quả & quét phiếu** →
   - **Tải phiếu quét lên**: chọn ảnh/.zip phiếu đã quét rồi bấm *Nhận diện & chấm*;
   - **Sửa phiếu lỗi**: phiếu Moodle chưa đọc được (MSSV mờ, tô 2 ô…);
   - **Kết quả**: điểm và mã đề từng SV (dòng *Đã chấm: 38*).
   Trong hệ thống, trang bài giấy có nút **Tải phiếu đã quét lên Moodle ↗** dẫn thẳng tới trang này
   (`http://localhost/moodle/mod/offlinequiz/report.php?mode=rimport&q=<id>`).
5. Hệ thống: Lớp học phần → **Thống kê lớp & từng SV**: chỉ số chung, tỷ lệ SV đạt từng CLO so với mục tiêu, chương cần ôn,
   phân bố số CLO đạt, kết quả theo mức Bloom, bản đồ nhiệt SV × CLO, danh sách SV cần hỗ trợ. Bấm một SV để xem
   hồ sơ: điểm, xếp hạng, radar CLO, chẩn đoán, **các chương cần học lại** và từng câu trả lời đúng/sai.
6. Tạo đề mới trong hệ thống → **Tạo Quiz trên Moodle** → Quiz xuất hiện ngay trong khóa học.

## Khai báo một học phần mới (môn khác) và gán CLO

**Khóa học đã tạo sẵn trên Moodle** (cách nhanh nhất): quản trị Moodle tạo khóa học và ghi danh GV với vai trò
*Teacher*. GV mở hệ thống → trang **Lớp học phần** hiện khung *"Khóa học trên Moodle chưa có trong hệ thống"* →
**Đưa vào hệ thống** → chọn môn học (tự gợi ý nếu tên khóa chứa mã môn), học kỳ (gợi ý theo ngày bắt đầu khóa học,
tự tạo học kỳ mới nếu chưa có), mã lớp → hệ thống tạo lớp HP do GV phụ trách, gắn khóa học và lấy danh sách SV.
Bấm nút *Phân tích CĐR* trong khóa học đó trên Moodle cũng mở thẳng hộp thoại này. Môn học chưa có thì Bộ môn
(`admin`) làm thao tác trên (chọn GV, tạo môn mới ngay trong hộp thoại). SV ghi danh thêm sau: nút **↻ SV**.

Trang **Học phần & CLO** (menu trái) có *bảng kiểm tra 5 bước*; làm lần lượt đến khi hiện "Học phần đã sẵn sàng".

| Bước | Ai làm | Làm ở đâu |
|---|---|---|
| 1. Môn học (nếu chưa có): mã, tên, số tín chỉ, chỉ tiêu đạt CĐR môn | **Bộ môn** (`admin`) | Học phần & CLO → *+ Môn học mới* |
| 2. Lớp học phần: học kỳ, mã lớp, **GV phụ trách** | **Bộ môn** | Học phần & CLO → *+ Lớp HP* |
| 3. Các chương của đề cương (thêm từng chương hoặc dán nhiều dòng "1. Tên chương") | GV phụ trách hoặc Bộ môn | Học phần & CLO → *Đề cương* |
| 4. CLO: mã, nội dung, mức Bloom mục tiêu, PLO đóng góp + mức I/R/M | GV phụ trách hoặc Bộ môn | Học phần & CLO → *+ CLO* |
| 5. Kế hoạch BM6a (ngưỡng đạt, chỉ tiêu, loại minh chứng) – không bắt buộc | GV | nút *BM6a* của lớp |
| 6. Câu hỏi + gán chương/Bloom/CLO (file mẫu, cột CLO dạng `CLO2:0.6; CLO4:0.4`) | GV | Ngân hàng câu hỏi |
| 7. Ra đề theo ma trận → nhập **ID khóa học Moodle** khi tạo Quiz/đề giấy lần đầu | GV | Lớp học phần → Tạo bài kiểm tra |

**Phân quyền:** GV *không* tạo được môn học, *không* tạo tay lớp HP (403) – chỉ được đưa vào khóa học Moodle mà mình là giảng viên, gắn với môn đã có. GV chỉ sửa chương/CLO của môn mình
có lớp phụ trách. **Khóa học Moodle** do quản trị Moodle tạo và ghi danh GV với vai trò *Teacher/Non-editing teacher*;
hệ thống chỉ cho GV gắn lớp HP với khóa học Moodle mà GV đó là giảng viên (tên đăng nhập Moodle trùng tên đăng nhập hệ thống),
mỗi khóa học chỉ gắn một lớp HP. Chương/CLO đã có câu hỏi hoặc kết quả, lớp HP đã có bài KT thì không xóa được (409).

## Nhập câu hỏi hàng loạt rồi gán CLO từ file
Ngân hàng câu hỏi → **⬆ Nhập câu hỏi từ file**: chọn file Excel/CSV (tải *file mẫu Excel* ngay trong hộp thoại),
Aiken (.txt hoặc Word .docx: câu hỏi, các dòng `A. …`, dòng `ANSWER: B`) hoặc Moodle XML. Hệ thống cho xem trước:
câu hợp lệ, câu trùng (bỏ qua), câu lỗi (ghi rõ dòng và lý do) rồi mới nhập. Chương/Bloom/CLO để trống được –
câu sẽ ở trạng thái **Chưa gán** (chưa đưa được vào đề).

Sau đó **Gán CLO/Bloom từ file**: tải file Excel các câu chưa gán (mỗi dòng: ID, nội dung, đáp án), điền cột
Chương (số), Bloom (chọn 1–6), CLO (`CLO2`, `CLO1; CLO3` chia đều, hoặc `CLO1:0.6; CLO3:0.4`), tải lên → xem trước
thay đổi → Cập nhật. Câu đã có kết quả thi không bị đổi CLO để giữ nguyên minh chứng. File mẫu: `docs\mau_nhap_cau_hoi`.

## Plugin Moodle `local_clo`
- Thư mục `moodle\local\clo`. Cấu hình: *Quản trị hệ thống → Plugin → Plugin cục bộ → Kết nối hệ thống phân tích CĐR*
  (địa chỉ hệ thống, khóa SSO). Dịch vụ Web Service: `local_clo` (hàm `local_clo_create_quiz`, `local_clo_push_results`).
- Quyền: `local/clo:launch` (GV, quản lý), `local/clo:viewown` (SV), `local/clo:viewall` (GV), `local/clo:manage` (tài khoản token).
- Có thể chạy lại cấu hình bất cứ lúc nào: `php local\clo\cli\setup.php --appurl=http://localhost:8000 --envfile="...\backend\cau_hinh.env"`.

## Lỗi thường gặp
- Bài giấy báo *Moodle chưa cài plugin Offline Quiz* → chạy lại bước 3 rồi bước 5.
- Tải ảnh quét lên Moodle nhưng *Moodle chưa chấm phiếu nào* → bấm *Cho Moodle chấm phiếu đang chờ* trong hệ thống;
  phiếu lỗi (MSSV sai/mờ) sửa tại trang *Sửa lỗi phiếu* của Offline Quiz rồi đồng bộ lại.
- `Access denied for user 'root'` → sửa mật khẩu trong `backend\cau_hinh.env` (dòng `DATABASE_URL`).
- Nút “Tạo Quiz”/“Công bố” báo *Chưa cấu hình kết nối Moodle* → chạy lại bước 3 rồi bước 5.
- Bấm “Phân tích CĐR” báo *chưa được bộ môn khai báo là giảng viên* → thêm giảng viên (mã GV = tên đăng nhập Moodle).
- Cổng 8000 bận → đặt `set "APP_PORT=8010"` trong `0_CAU_HINH_MAY.bat`, chạy lại bước 3 và 5.
- Bước 3/4 báo *Chưa xác định được thư mục Moodle 4.5 / php.exe* → khai báo `MOODLE_DIR`, `PHP_BIN` trong `0_CAU_HINH_MAY.bat`.
