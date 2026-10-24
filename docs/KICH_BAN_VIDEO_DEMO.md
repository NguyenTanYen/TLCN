# Kịch bản quay video demo (khoảng 12–15 phút)

Quay theo đúng luồng chính: **Bộ môn thiết lập → GV tạo bài → SV làm trên Moodle → phân tích → BM6 → ôn tập**.
Mỗi cảnh ghi rõ *bấm gì* và *nói gì*. Thời lượng chỉ là gợi ý.

## 0. Chuẩn bị (trước khi quay)

1. Bật MariaDB (`E:\TLCN_MoiTruong\1_BAT_MARIADB.bat`) và Apache/Moodle (`E:\hoc\xampp\apache_start.bat`).
2. Nếu dữ liệu đã bị kiểm thử làm thay đổi: chạy lại `4_TAO_DU_LIEU_DEMO_TREN_MOODLE.bat`.
3. Chạy script bổ sung dữ liệu cho video (chạy lại không tạo trùng):
   ```
   .venv\Scripts\python tools\demo\chuan_bi_video.py
   ```
   Script in ra mã các bài. Với dữ liệu hiện tại:
   - Bài thi cuối kỳ (Moodle) đã phân tích: `/exams/2`.
   - Bài giấy để demo chấm phiếu: `/exams/4`. Ảnh phiếu đã tô của 8 SV nằm ở `demo_video\phieu_da_to\`.
   - Bài ôn tập giao cho 2 SV (22130017, 22130018), đã có Quiz trên Moodle: `/exams/5`.
4. Chạy hệ thống: `5_CHAY_HE_THONG.bat` → http://localhost:8000.
5. Mở sẵn 2 cửa sổ trình duyệt: **(A)** hệ thống, **(B)** cửa sổ ẩn danh cho Moodle của sinh viên (http://localhost:8081/moodle45).
6. Tài khoản:
   - Bộ môn: `admin` / `Admin@123`.
   - Giảng viên: `gv.son` / `Gv@123456`.
   - Sinh viên (Moodle): `22130017`, `22130040` / `Sv@123456`.

> Lưu ý: cảnh 5 (chấm phiếu) và cảnh 3 ghi dữ liệu thật vào CSDL. Muốn quay lại từ đầu thì làm lại bước 2–3.

---

## Cảnh 1 – Bộ môn thiết lập học phần (2 phút)

Đăng nhập **admin** → menu **Học phần** → **DBMS330284 – Hệ quản trị cơ sở dữ liệu**.

| Bấm | Nói |
|---|---|
| Chỉ vào thanh bước trên đầu trang | "Trang học phần đi theo 4 bước của Bộ môn; bước đã xong có dấu ✓." |
| **① Thiết lập học phần** | "Bộ môn khai báo chương, CLO và ánh xạ CLO → PI → PLO của CTĐT." Cuộn qua bảng CLO. |
| **② Đề cương chi tiết** | "Đề cương có phiên bản; chọn phiên bản ở góc phải, bản đã duyệt không sửa trực tiếp." Cuộn mục 4 (CLO – PI) và mục 9 (kế hoạch BM6a). |
| **③ Lớp học phần** → ô **Học kỳ** | "Lọc lớp theo học kỳ; Bộ môn mở lớp và gán giảng viên." |
| **④ Kết quả CĐR của môn** → chọn học kỳ | "Kết quả CLO của môn theo học kỳ, gộp mọi lớp – BM6b cấp môn." |

## Cảnh 2 – Giảng viên tạo bài kiểm tra (2,5 phút)

Đăng xuất → đăng nhập **gv.son** → **Môn học của tôi** → bấm tên môn. Trang mở sẵn bước **Lớp học phần** → **Mở lớp** DBMS330284_01.

| Bấm | Nói |
|---|---|
| Chỉ vào thanh 4 bước của lớp | "Việc của giảng viên ở một lớp: tạo bài → thu bài & phân tích → BM6 → ôn tập. Mỗi bài có nút *Bước tiếp theo*." |
| **+ Tạo bài kiểm tra** → **Trắc nghiệm trực tuyến** | "Ba hình thức: trực tuyến qua Moodle, trên giấy, hoặc nhập điểm." |
| ① Thông tin bài: tên "Kiểm tra demo", minh chứng **Quá trình** → **Tiếp** | |
| ② **Sinh đề tự động** → 20 câu, **Cân bằng** → **⚙ Sinh đề theo ma trận** | "Chỉ cần số câu và độ khó; hệ thống tự lập ma trận chương × mức Bloom và phủ đủ CLO." Chỉ vào dòng *Độ phủ CLO*. |
| Mở **Tùy chỉnh nâng cao** rồi đóng lại | "Ai cần thì chỉnh tỷ lệ Bloom hoặc nhập ma trận chi tiết." |
| **Tiếp: kiểm tra đề** → **Chia đều 10 điểm** → **Lưu bài kiểm tra** | |
| Trang bài KT: bước **Đề thi** → khung **Câu hỏi → CLO → BM6** | "Ngay khi ra đề đã thấy mỗi CLO gồm những câu nào, bao nhiêu điểm." |
| **Phát hành lên Moodle** → **⇪ Tạo Quiz trên Moodle** | "Hệ thống tạo Quiz trên khóa học Moodle, xáo trộn phương án." |

## Cảnh 3 – Sinh viên làm bài trên Moodle (1,5 phút)

Cửa sổ **(B)**: đăng nhập Moodle bằng **22130040** → khóa học DBMS330284_01 → Quiz "Kiểm tra demo" → **Attempt quiz** → chọn vài đáp án → **Submit all and finish**.

Nói: "Sinh viên chỉ làm bài trên Moodle, không cần tài khoản hệ thống phân tích."

## Cảnh 4 – Thu bài, phân tích, xem kết quả, công bố (3 phút)

Cửa sổ **(A)**: mở bài **Thi cuối kỳ (Moodle)** (`/exams/2` – 38 bài làm, giàu số liệu hơn).

| Bấm | Nói |
|---|---|
| **③ Thu bài & phân tích** → **⟳ Đồng bộ & phân tích** | "Đọc trực tiếp bài làm từ CSDL Moodle, giải mã xáo trộn, ghi nhận SV vắng, rồi phân tích." Trang tự chuyển sang bước Kết quả. |
| **Kết quả → Câu hỏi → CLO → BM6** | **Cảnh quan trọng:** "Đường đi minh chứng: câu hỏi → CLO → tỷ lệ SV đạt trong bài → kết quả CLO của lớp trong BM6." Chỉ CLO2 *Không đạt*. |
| **Tổng quan điểm** | Phổ điểm, độ tin cậy KR-20. |
| **Phân tích câu hỏi** → mở *Phương án ▼* của 1 câu | "p, DI theo Kelley 27%; câu DI âm cần kiểm tra đáp án." |
| **Thời gian làm bài** | "Phát hiện SV làm quá nhanh hoặc để hết giờ." |
| Ô **Công bố cho SV** ở đầu trang → **Công bố kết quả lên Moodle** | |
| Cửa sổ (B): đăng nhập SV **22130017** → khóa học → **Learning outcome results** | "Sinh viên xem radar CLO và phần cần ôn ngay trên Moodle." |

## Cảnh 5 – Bài thi giấy: in đề và chấm phiếu bằng ảnh (2 phút)

Mở bài **Kiểm tra giữa kỳ (giấy – chấm trên hệ thống)** (`/exams/4`). Bước **In đề & chấm phiếu** mở sẵn.

| Bấm | Nói |
|---|---|
| **2. Xem trước & xuất đề** | "2 mã đề xáo trộn; đề in 1 hoặc 2 cột; phiếu trả lời có ô định vị để chấm bằng ảnh chụp." |
| **4. Chấm phiếu** → **Tải ảnh phiếu…** → chọn cả 8 ảnh trong `demo_video\phieu_da_to\` | "Ảnh quét hoặc ảnh chụp điện thoại; hệ thống đọc MSSV, mã đề và các ô đã tô." |
| Soát bảng kết quả → **Lưu kết quả 8 phiếu & phân tích** | "Điểm từ 1 đến 10 tùy SV; hệ thống phân tích ngay." |
| Bước **Kết quả** → **Câu hỏi → CLO → BM6** | "Bài giấy cũng đi vào cùng một chuỗi CLO → BM6." |

## Cảnh 6 – Kết quả CĐR của lớp (BM6) (1,5 phút)

Về trang lớp → bước **Kết quả CĐR (BM6)**.

| Bấm | Nói |
|---|---|
| **BM6a – Kế hoạch đánh giá** | "Ngưỡng đạt và chỉ tiêu từng CLO; sửa ở đây thì hệ thống tự phân tích lại." |
| **BM6b – Kết quả tổng hợp** | Biểu đồ tỷ lệ đạt so với chỉ tiêu, kết luận đạt CĐR môn học. |
| **BM6c/6d – Minh chứng** → **Xem minh chứng** CLO2 | Điểm từng SV trên các câu thuộc CLO, câu có DI thấp; ghi nhận xét cải tiến. |
| **⬇ Xuất bộ BM6 của lớp (.xlsx)** | Mở file Excel cho thấy đúng các biểu mẫu. |

## Cảnh 7 – Ôn tập cho sinh viên làm sai (2 phút)

Trang lớp → bước **Ôn tập**.

| Bấm | Nói |
|---|---|
| Bảng *Số câu sai của từng sinh viên* → **Câu sai ›** của 1 SV | "Mỗi SV sai bao nhiêu câu, CLO nào chưa đạt." |
| Khung **Bài ôn tập đã giao** → bài cho 22130017, 22130018 | "Bài ôn tập gồm câu đã sai và câu tương tự cùng CLO; chỉ SV được giao mới thấy trên Moodle." |
| Cửa sổ (B): SV **22130040** → không có nút *Attempt quiz* ở Quiz ôn tập | Chứng minh giới hạn SV. |
| Cửa sổ (B): SV **22130017** → làm Quiz ôn tập và nộp | |
| (A) mở bài ôn tập → **Thu bài & phân tích** → **⟳ Đồng bộ & phân tích** → quay lại trang Ôn tập, mở khung tiến bộ | "Cột *Thay đổi* cho thấy SV tiến bộ trên chính các câu từng làm sai." |

## Cảnh 8 – Kết (30 giây)

Đăng nhập **admin** → **Tổng hợp PLO** (hoặc trang môn → **Kết quả CĐR của môn**).
Nói: "Từ câu hỏi → CLO → PI → PLO, Bộ môn có số liệu đo chuẩn đầu ra theo học kỳ cho cả chương trình."
