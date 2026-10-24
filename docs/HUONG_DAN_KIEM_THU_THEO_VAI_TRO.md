# Hướng dẫn kiểm thử toàn bộ chức năng theo vai trò

Máy này: hệ thống tại **http://localhost:8000**, Moodle 4.5 tại **http://localhost:8081/moodle**.

| Vai trò | Ở đâu | Tài khoản |
|---|---|---|
| Bộ môn | Hệ thống | `admin` / `Admin@123` |
| Giảng viên | Hệ thống và Moodle | `gv.son` / `Gv@123456` (GV khác để thử phân quyền: `gv.binh` / `Gv@123456`) |
| Sinh viên | **Chỉ Moodle** | `22130001` … `22130040` / `Sv@123456` |
| Quản trị Moodle | Moodle | tài khoản admin Moodle của bạn |

Dữ liệu demo đáng chú ý (do bước 4 tạo):

- Lớp `DBMS330284_01`, 40 SV. Có bài *Thi cuối kỳ (Moodle)* (Quiz 20 câu, 38 bài làm) và bài giấy *Kiểm tra quá trình* (Offline Quiz 2 mã đề, 38 phiếu). Lớp `DBMS330284_02` có bài nhập điểm.
- SV vắng: 2 SV. SV chọn đại: `22130017`, `22130018`. SV để hết giờ: `22130006`, `22130023`.

---

## 0. Chuẩn bị

1. XAMPP Control Panel → **Start** Apache và MySQL.
2. Bấm đúp `5_CHAY_HE_THONG.bat` và giữ cửa sổ mở.
3. Dùng **hai cửa sổ trình duyệt**: cửa sổ thường cho hệ thống, cửa sổ **ẩn danh** cho Moodle. Hai phiên đăng nhập sẽ không lẫn nhau.
4. Muốn bắt đầu lại từ dữ liệu sạch: chạy `2_KHOI_TAO_CSDL.bat` rồi `4_TAO_DU_LIEU_DEMO_TREN_MOODLE.bat`.

Nên test theo thứ tự **Bộ môn → Giảng viên → Sinh viên**, vì phần sau dùng dữ liệu phần trước tạo ra. Mỗi dòng có ô ☐ để đánh dấu đạt/không đạt.

---

## A. Bộ môn (`admin`)

| # | Thao tác | Kết quả mong đợi | ☐ |
|---|---|---|---|
| BM1 | Đăng nhập `admin`. Sau đó đăng xuất (menu tên góc phải) và thử sai mật khẩu | Menu: Chương trình đào tạo, Học phần, Lớp học phần, Câu hỏi, Kế hoạch đo PI, Tổng hợp PLO, Kết nối Moodle. Sai mật khẩu → báo lỗi, vẫn ở trang đăng nhập | ☐ |
| BM2 | Moodle (admin Moodle) → vào khóa DBMS330284_01 → **Phân tích CĐR** | Tự vào hệ thống, không hỏi mật khẩu, menu của Bộ môn (SSO) | ☐ |
| BM3 | **Chương trình đào tạo** → KTDL-2026 | Thẻ Chuẩn đầu ra có 7 PLO và các PI. Các thẻ Học phần (theo học kỳ, khối kiến thức), Ma trận học phần – PI và Mục tiêu mở được | ☐ |
| BM4 | **Học phần** → **+ Học phần mới**: mã `TEST001`, tên, tín chỉ, tích KTDL-2026 → Lưu. Tạo lại cùng mã | Tạo xong thì tự mở thẻ Thiết lập. Trùng mã → báo trùng, không tạo | ☐ |
| BM5 | Trong học phần mới: khung Thông tin → nhập mô tả → Lưu. Khung Thuộc CTĐT → học kỳ 5, khối kiến thức → Lưu | Lưu thành công | ☐ |
| BM6 | CTĐT KTDL-2026 → Ma trận học phần – PI → dòng TEST001: chọn mức cho 1–2 ô PI | Đề cương mục 5 hiện các PI đó, tô đỏ "Chưa có CLO" | ☐ |
| BM7 | Thẻ Thiết lập: gõ tên chương vào ô "Tên chương mới…" → **Enter** (làm 2 chương). Bấm **Chi tiết** một chương → số tiết LT/TH, chọn CLO → Lưu | Chương được lưu, cột tóm tắt hiện số tiết và CLO | ☐ |
| BM8 | **+ CLO**: CLO1 (Bloom 2), tích một PI mức R. Thêm CLO2 (Bloom 3), PI khác mức M | Bảng CLO hiện "PLOx › PIx.y (R/M)". Đề cương mục 5 hết tô đỏ | ☐ |
| BM9 | Thẻ Lớp học phần → **+ Lớp HP**: HKII 24-25, mã lớp `TEST001_01`, GV **Nguyễn Thành Sơn** → Lưu. Thử ô lọc **Học kỳ** | Lớp mới có trong danh sách, lọc theo học kỳ đúng | ☐ |
| BM10 | **⟳ Đồng bộ các lớp với Moodle** | Báo kết quả từng lớp: lớp mới chưa có khóa Moodle trùng mã thì báo chưa có, không lỗi | ☐ |
| BM11 | Đề cương → **+ Soạn đề cương**. Sửa mục 1, 3, 7. Mục 8 nhập 40% + 50% | Tổng 90% → dòng tổng đỏ, nút Lưu bị khóa | ☐ |
| BM12 | Sửa thành 40% + 60% → Lưu. Mục 10 thêm giáo trình → **Duyệt** | "Phiên bản 1: Đang áp dụng", hết nút Sửa. Thẻ Thiết lập có ✓ ở bước "Đề cương đã duyệt" | ☐ |
| BM13 | **Tạo phiên bản mới**. Dùng ô chọn phiên bản để xem lại bản 1. Bấm In (Ctrl+P) | Bản nháp 2 chép nội dung bản 1. Bản in không có nút bấm | ☐ |
| BM14 | Thử xóa chương/CLO đã có câu hỏi (dùng môn DBMS330284) | Bị chặn (409), báo đang được sử dụng | ☐ |
| BM15 | **Kế hoạch đo PI** → KTDL-2026 → **+ Thêm kế hoạch**: PI, môn, HKII 24-25, phương pháp, chỉ tiêu 70, GV, **không tích CLO** → Lưu | Kế hoạch có trong bảng năm học 2024-2025 | ☐ |
| BM16 | **+ Phân công**: học kỳ, môn, GV (hoặc "Tất cả thầy/cô có hướng dẫn"), ghi chú → Lưu. Thử tạo trùng. Bấm **Xuất bảng phân công** | Có dòng phân công. Trùng → báo lỗi. Tải được Excel | ☐ |
| BM17 | **Tổng hợp PLO** → CTĐT KTDL → năm 2024-2025 → **Tính lại**. Bấm **Nhận xét** một PLO → nhập → Lưu | Bảng PLO có tỷ lệ đạt / Đạt–Không đạt. Nhận xét được lưu | ☐ |
| BM18 | **⬇ Xuất BM2/BM3 (.xlsx)** và **⬇ Xuất BM2 (.docx)** | Tải được 2 tệp, mở ra đúng bố cục biểu mẫu | ☐ |
| BM19 | **Kết nối Moodle** | Cầu nối CSDL OK. Web Service kết nối được, thấy 7 hàm `local_clo_*` (có `local_clo_restrict_users`). SSO đã cấu hình | ☐ |
| BM20 | Học phần DBMS330284 → **Kết quả CĐR của môn** → chọn học kỳ | Kết quả CLO của môn, gộp mọi lớp | ☐ |

---

## B. Giảng viên (`gv.son`)

### B1. Đăng nhập, môn học, phân quyền

| # | Thao tác | Kết quả mong đợi | ☐ |
|---|---|---|---|
| GV1 | Đăng nhập `gv.son` | Menu chỉ có: Môn học của tôi, Ngân hàng câu hỏi, Chương trình đào tạo. Tên GV ở góc phải | ☐ |
| GV2 | Moodle (ẩn danh) đăng nhập `gv.son` → khóa DBMS330284_01 → **Phân tích CĐR** | Vào thẳng hệ thống, đúng lớp DBMS330284_01 | ☐ |
| GV3 | **Môn học của tôi** | Thấy DBMS330284 (2 lớp) và TEST001 (lớp Bộ môn giao ở BM9) | ☐ |
| GV4 | Mở môn TEST001 → **Đề cương** | Chỉ xem: "Phiên bản 1: Đang áp dụng" (không phải nháp 2), không có nút Sửa, không có thẻ Thiết lập | ☐ |
| GV5 | Đăng nhập `gv.binh`, dán URL lớp của gv.son (ví dụ `/sections/1`) | Không thấy môn, mở thẳng URL → báo không có quyền | ☐ |

### B2. Danh sách SV và ngân hàng câu hỏi

| # | Thao tác | Kết quả mong đợi | ☐ |
|---|---|---|---|
| GV6 | Lớp TEST001_01 → thẻ **Danh sách SV** → **Nhập CSV…**. Tệp UTF-8 với cột `student_code,full_name,class_name`, 5 dòng MSSV 8 số | Báo đã thêm 5 SV, thẻ hiện "Danh sách SV (5)" | ☐ |
| GV7 | **Ngân hàng câu hỏi** → môn TEST001 → **+ Thêm câu hỏi**: 3 câu (chương 1, Hiểu, CLO1) và 3 câu (chương 2, Vận dụng, CLO2) | Lưu được. Thử 2 đáp án đúng, hoặc tổng trọng số CLO khác 1 → bị từ chối | ☐ |
| GV8 | Cây **Theo chuẩn đầu ra** → bấm một PI → bấm "Tất cả" | Lọc đúng số câu của PI đó, mỗi câu có chuỗi "PLOx › PIx.y" | ☐ |
| GV9 | Thêm 1 câu → Chi tiết → nhập lý do → **Hủy câu hỏi** | Câu bị Hủy, không còn trong danh sách dùng được | ☐ |
| GV10 | **⬆ Nhập câu hỏi từ file** → chọn `docs\mau_nhap_cau_hoi\mau_aiken.txt` (thử thêm `mau_excel_DBMS330284.xlsx`, `mau_moodle.xml`, `mau_aiken_word.docx`) | Bản xem trước có câu hợp lệ / trùng / lỗi theo dòng → Nhập → câu ở trạng thái **Chưa gán** | ☐ |
| GV11 | **Gán CLO/Bloom từ file** → tải "Các câu chưa gán" → điền Chương, Bloom, CLO (`CLO2` hoặc `CLO1:0.6; CLO2:0.4`) → tải lên → Cập nhật | Hết cảnh báo "chưa gán", số câu trong cây PI tăng | ☐ |
| GV12 | Môn DBMS330284 → **⇅ Đồng bộ với Moodle**. Soạn 1 câu mới → mở Đồng bộ | Câu mới "Chỉ có trên hệ thống" → Đồng bộ → mở lại thấy "Đã đồng bộ" | ☐ |
| GV13 | Sửa câu đó trên hệ thống, đồng thời sửa cùng câu trên Moodle (admin Moodle → Ngân hàng câu hỏi khóa học → câu `QB-n`) → mở Đồng bộ | "Hai bên khác nhau" (xung đột), mặc định Bỏ qua → chọn **⇩ Lấy về hệ thống** → nội dung thành bản Moodle | ☐ |
| GV14 | Một câu đã có kết quả thi (môn DBMS330284) → thử sửa | Bị khóa, chỉ còn Hủy | ☐ |

### B3. Tạo bài kiểm tra (3 hình thức)

| # | Thao tác | Kết quả mong đợi | ☐ |
|---|---|---|---|
| GV15 | Lớp DBMS330284_01 → **+ Tạo bài kiểm tra** → **Trắc nghiệm trực tuyến** → ① tên bài, minh chứng Quá trình → ② **Sinh đề tự động**: 20 câu, Cân bằng → **⚙ Sinh đề theo ma trận** | Ma trận chương × Bloom, dòng Độ phủ CLO. Thử "Tùy chỉnh nâng cao" → nhập ma trận vượt số câu → báo ô thiếu câu | ☐ |
| GV16 | ③ **Tiếp: kiểm tra đề** → Chia đều 10 điểm → **Lưu bài kiểm tra** | Bài ở trạng thái Nháp, khung "Câu hỏi → CLO → BM6" hiện đúng | ☐ |
| GV17 | Bước **Phát hành lên Moodle** → **⇪ Tạo Quiz trên Moodle**. Thử thêm **Cách thủ công… → ⬇ Tải Moodle XML** | Quiz xuất hiện trong khóa Moodle. Tệp XML có `idnumber` dạng `QB-n` | ☐ |
| GV18 | Trang môn DBMS330284 → **+ Tạo bài KT** (đề của môn, chưa có lớp) → Lưu → **Giao cho lớp HP / Xuất** → tích 2 lớp | Mỗi lớp nhận một bài riêng. Giao lại lớp đã nhận thì bị bỏ qua | ☐ |
| GV19 | Bài trực tuyến → **⧉ Dùng đề cho lớp khác** | Bản sao ở lớp DBMS330284_02 | ☐ |
| GV20 | **+ Tạo bài kiểm tra** → **Trắc nghiệm trên giấy** → chọn câu → Lưu → **In và chấm ngay trên hệ thống** → 2 mã đề → **Sinh mã đề** | Có mã đề 01, 02 | ☐ |
| GV21 | Thẻ **2. Xem trước & xuất đề**: đổi 1 cột / 2 cột, bấm ✎ sửa câu. Tải PDF, Word, đáp án, .zip | Bản xem trước A4 đổi theo, tải được tệp, sửa câu áp dụng cho mọi mã đề | ☐ |
| GV22 | Thẻ **3. Phiếu trả lời**: đổi số chữ số MSSV, phần tự luận → tải PDF phiếu | Phiếu có 4 ô định vị, vùng MSSV, mã đề, số ô đúng số phương án | ☐ |
| GV23 | Thẻ **4. Chấm phiếu** → **⬆ Tải ảnh phiếu…**. Ảnh: in phiếu, tô rồi chụp điện thoại, hoặc sinh ảnh tô sẵn (xem cuối mục B) | Đọc được MSSV, mã đề, đáp án. Ô xanh = 1 ô, đỏ = nhiều ô, có cảnh báo. Sửa → **Lưu kết quả & phân tích** | ☐ |
| GV24 | Bài giấy demo *Kiểm tra quá trình* (Offline Quiz): tải đề/phiếu Moodle sinh → **Tải phiếu đã quét lên Moodle ↗** → **⟳ Đồng bộ & phân tích** | 38 bài, mã đề A/B, 2 vắng | ☐ |
| GV25 | **+ Tạo bài kiểm tra** → **Nhập điểm**: Câu 1 = 4đ CLO1, Câu 2 = 6đ CLO2 → Tạo. Nhập 5 cho Câu 1 | Ô đỏ, nút Lưu bị khóa | ☐ |
| GV26 | Nhập điểm hợp lệ, 1 SV đánh dấu **Vắng** → **Lưu & phân tích**. Thử **Bảng điểm mẫu (Excel)** → điền → **Nhập từ Excel**, và **Tạo từ file Excel có sẵn** | Lưu được, SV vắng không tính. Nhập Excel có xem trước lỗi | ☐ |

### B4. Thu bài, phân tích, kết quả

| # | Thao tác | Kết quả mong đợi | ☐ |
|---|---|---|---|
| GV27 | Bài **Thi cuối kỳ (Moodle)** → **Thu bài & phân tích** → **⟳ Đồng bộ & phân tích** | Đồng bộ 38 bài, 2 vắng, tự chuyển sang Kết quả | ☐ |
| GV28 | Kết quả → **Câu hỏi → CLO → BM6** | Mỗi CLO: các câu, tỷ lệ SV đạt, Đạt/Không đạt | ☐ |
| GV29 | **Tổng quan điểm** | Phổ điểm, điểm trung bình, KR-20 | ☐ |
| GV30 | **Phân tích câu hỏi** → mở *Phương án ▼* một câu | p, DI tô màu theo thang. Có câu "Cần loại bỏ" (DI âm – câu bẫy của dữ liệu demo) | ☐ |
| GV31 | **Kết quả sinh viên** | Danh sách SV và điểm | ☐ |
| GV32 | **Thời gian làm bài**: đổi ngưỡng → Áp dụng. Bấm **Diễn biến** của 22130017. **Xuất Excel** | Cảnh báo cho 22130017/18 (quá nhanh) và 22130006/23 (để hết giờ). Danh sách bài của lớp có nhãn ⚠ N cảnh báo | ☐ |
| GV33 | Đầu trang bài: **Công bố kết quả lên Moodle**, sau đó **Thu hồi công bố**, rồi công bố lại | Nhãn đổi "SV đã xem được kết quả" ↔ "Đang bảo lưu kết quả" | ☐ |
| GV34 | Lớp → **Thống kê lớp**. Bấm **Hồ sơ** một SV | Chỉ số lớp, chương cần ôn, phổ điểm, SV cần hỗ trợ. Hồ sơ: điểm các bài, thứ hạng, gợi ý ôn tập, từng câu đúng/sai | ☐ |

### B5. BM6, gộp bài, ôn tập

| # | Thao tác | Kết quả mong đợi | ☐ |
|---|---|---|---|
| GV35 | Lớp → **Kết quả CĐR (BM6)** → **BM6a** → Sửa kế hoạch một CLO (ngưỡng 60%, chỉ tiêu 75%) → Lưu | Kết quả tự tính lại theo ngưỡng mới | ☐ |
| GV36 | **BM6b** và **BM6c/6d → Xem minh chứng** một CLO → nhập nhận xét cải tiến | Biểu đồ tỷ lệ đạt so với chỉ tiêu. Minh chứng điểm từng SV. Lưu được nhận xét | ☐ |
| GV37 | **⬇ Xuất bộ BM6 của lớp (.xlsx)**. Ở trang bài KT: **Xuất BM6c bài KT này** | Excel có trang BM6a, BM6b, minh chứng từng CLO, công thức COUNTIF | ☐ |
| GV38 | Trang môn → **Gộp bài KT đánh giá CĐR** → tích 2–3 bài (có thể khác lớp) → thử cả 2 cách gộp → **Phân tích gộp** → **⬇ Xuất Excel**. Bỏ tích cột "Minh chứng BM6" của một bài | Có mức đạt CLO và đóng góp PLO/PI theo CTĐT. BM6 của lớp tính lại | ☐ |
| GV39 | Lớp → **Ôn tập** → chỉ tích bài Thi cuối kỳ → **Câu sai ›** của một SV | Số câu sai từng SV. Từng câu: đã chọn gì, đáp án đúng, CLO, chương | ☐ |
| GV40 | Tích 2 SV (ví dụ 22130017, 22130018) → **Tạo bài ôn tập cho 2 SV đã chọn** (1 câu tương tự) → mở bài → **⇪ Tạo Quiz trên Moodle** | Báo "chỉ 2 SV được giao làm được". Có nút **Giới hạn SV trên Moodle**. Khung tiến bộ hiện 2 SV "Chưa làm" | ☐ |

**Sinh ảnh phiếu đã tô để thử GV23** (khi không có máy in). Chạy trong PowerShell tại thư mục `TLCN`. `<id_bai>` là số trong URL `/exams/<id>`, `<MSSV>` là SV có trong lớp:

```powershell
.venv\Scripts\python.exe tests_e2e\tools\tao_phieu_da_to.py <id_bai> <MSSV> phieu_test.png
```

---

## C. Sinh viên (chỉ dùng Moodle, cửa sổ ẩn danh)

| # | Thao tác | Kết quả mong đợi | ☐ |
|---|---|---|---|
| SV1 | Trang hệ thống localhost:8000 → đăng nhập `22130017` / `Sv@123456` | Bị từ chối, hướng dẫn xem kết quả trên Moodle | ☐ |
| SV2 | Moodle: đăng nhập `22130040` → khóa DBMS330284_01 → Quiz tạo ở GV17 → **Attempt quiz** → chọn đáp án → **Submit all and finish** | Nộp bài được. Quiz hiện 1 câu/trang, phương án bị xáo. Sau đó GV đồng bộ bài này → có thêm bài làm và có thời gian từng câu | ☐ |
| SV3 | `22130001` → khóa học → **Kết quả phân tích CĐR** (*Learning outcome results*). Xem chuông thông báo | Thấy kết quả bài đã công bố (điểm, gợi ý ôn tập). Có thông báo "có kết quả" | ☐ |
| SV4 | Đăng nhập một SV vắng thi cuối kỳ (tìm trong thẻ Kết quả sinh viên của GV) → trang kết quả | "Chưa đủ bằng chứng đánh giá" | ☐ |
| SV5 | GV thu hồi công bố (GV33) → SV tải lại trang → GV công bố lại | "Kết quả đang được bảo lưu" → rồi xem lại được | ☐ |
| SV6 | `22130040` (không được giao) mở Quiz ôn tập ở GV40 | Không có nút làm bài | ☐ |
| SV7 | `22130017` (được giao) làm và nộp Quiz ôn tập → GV mở bài ôn tập → **⟳ Đồng bộ & phân tích** → trang Ôn tập, khung tiến bộ | SV "Đã nộp", cột Thay đổi (sau − trước) có số | ☐ |
| SV8 | Admin Moodle → khóa học → Nhóm | Nhóm "Ôn tập – …" có đúng 2 SV được giao | ☐ |

---

## D. Kiểm thử tự động (tùy chọn)

### D1. Playwright: tự bấm giao diện theo vai trò (29 flow: Bộ môn AD1–AD9, GV1–GV15, SV1–SV5)

Chạy trên hệ thống thật đang bật. Mỗi lần chạy tạo một học phần mới mã `UIddhhmm`, không xóa CSDL. Cần Node.js (máy đã có 22.18).

1. Lấy id khóa học Moodle của lớp demo. Trong HeidiSQL, hoặc chạy lệnh sau:

```powershell
E:\hoc\xampp\mysql\bin\mariadb.exe -uroot -e "SELECT id FROM moodle.mdl_course WHERE shortname='DBMS330284_01'"
```

2. Cài một lần:

```powershell
cd E:\hoc\TLCN\TLCN\tests_e2e; npm install
```

3. Đặt biến môi trường. Thay `<id>` và mật khẩu admin Moodle của bạn:

```powershell
$env:UI_MOODLE_URL='http://localhost:8081/moodle'; $env:UI_MOODLE_COURSE='<id>'; $env:UI_MOODLE_ADMIN_PASS='<mat_khau_admin_moodle>'
```

4. Chạy, trong cùng cửa sổ PowerShell đó:

```powershell
npx playwright test --ui
```

- Chế độ `--ui` cho chọn từng flow và xem từng bước.
- Bỏ các flow cần Moodle: `npm run khong-moodle`.
- Xem báo cáo sau khi chạy: `npm run bao-cao`.

### D2. Kiểm thử API và Analysis Engine (pytest, khoảng 110 ca): `6_CHAY_KIEM_THU.bat`

- **Dựng lại `assessment_db`** và tạo CSDL `moodle_sim` riêng (không đụng Moodle thật).
- Xuất bảng kết quả `docs\kiem_thu\KET_QUA_KIEM_THU.xlsx`.
- **Chạy xong phải chạy lại `2_KHOI_TAO_CSDL.bat` và `4_TAO_DU_LIEU_DEMO_TREN_MOODLE.bat`** để có lại dữ liệu demo.
- Vì vậy hãy chạy D2 **sau cùng**, khi đã test tay xong.

### D3. Tính lại độc lập các độ đo: `tools\KIEM_TRA_DO_LUONG.bat`

Tính lại p, DI, CLO, BM6b, PI, PLO, CTĐT từ dữ liệu bài làm và so với số liệu của hệ thống. Mong đợi: **0 sai lệch**. Không sửa dữ liệu.
