# Hệ thống hỗ trợ Giảng viên triển khai kiểm tra, đánh giá và phân tích mức độ đạt CĐR

Tiểu luận chuyên ngành – Nhóm 01 · Nguyễn Trần Quốc Thi (23110331) · Nguyễn Tấn Yên (23110369) · GVHD: ThS. Trần Trọng Bình

Hệ thống giúp giảng viên **biên soạn câu hỏi trắc nghiệm gắn CLO**, **tổ chức kiểm tra trực tuyến (Moodle Quiz) và trên giấy (Moodle Offline Quiz: in đề nhiều mã đề, quét phiếu, Moodle chấm)**,
**kéo bài làm đã chấm từ Moodle về**, **phân tích chất lượng câu hỏi (p, DI)** và **đo lường mức độ đạt CĐR** theo đúng các biểu mẫu của HCMUTE:
BM6a–6d (CĐR môn học, cả BM6c riêng từng bài kiểm tra) và BM2a–2b (Excel + Word), BM3b–3c, bảng phân công đánh giá PIs (CĐR chương trình đào tạo, PI), kèm **lộ trình ôn tập cá nhân hóa** cho sinh viên.

Hệ thống dành cho **giảng viên / bộ môn**; sinh viên làm bài và xem kết quả phân tích trên **Moodle**. Hai hệ thống nối với nhau qua plugin Moodle `local_clo` (nút *Phân tích CĐR* đăng nhập một lần, Web Service tạo Quiz / Offline Quiz và nhận kết quả) và cầu nối CSDL chỉ đọc để kéo bài làm – xem `HUONG_DAN_CAI_DAT.md`.

> **Cài trên Windows + XAMPP:** xem `HUONG_DAN_CAI_DAT.md` (các tệp `.bat` 0–8). Sau khi cập nhật bản 15/10 cần chạy lại **1_CAI_DAT_PYTHON.bat**
> (thư viện mới: reportlab, opencv-python-headless) và chép lại plugin `moodle/local/clo` (phiên bản 1.3.1 – Web Service đồng bộ câu hỏi; Quiz tạo mới đặt 1 câu/trang để lấy thời gian từng câu), sau đó vào Moodle → Quản trị trang để nâng cấp.
> Bài trực tuyến đã đồng bộ trước bản thời gian làm bài: bấm **Đồng bộ lại** để lấy thời điểm trả lời từng câu.

### Bổ sung theo góp ý 15/10

| Góp ý | Đã làm |
|---|---|
| Quản lý theo CTĐT, đề cương chi tiết | Nạp tự động 2 CTĐT **CNTT 2026** và **KTDL 2026** từ file PDF (`tools/ctdt_2026/doc_ctdt.py` → `database/04_ctdt_2026.sql`): 7 PLO, 17 PI (trình độ năng lực), 79/57 học phần (tín chỉ LT/TH, cấu trúc, tiên quyết, khối kiến thức, học kỳ, mô tả), ma trận học phần – PI. Trang *Chương trình đào tạo* và **Đề cương chi tiết** từng học phần (in được). |
| GV không sửa học phần, CLO | Học phần, chương, CLO, ma trận PI do **Bộ môn** quản lý; GV chỉ xem (API trả 403). |
| Giao diện | Thanh điều hướng trên cùng, tên GV góc phải; luồng **Môn học → các lớp GV dạy → bài KT**; bấm môn xem đề cương, lớp, kết quả CĐR của môn. |
| Lớp ⇄ Moodle | Tự gắn lớp với khóa học Moodle **trùng mã lớp** (một nút cho cả môn, kèm cập nhật SV); liên kết mở khóa học Moodle từ lớp; nút *Phân tích CĐR* trên Moodle mở đúng lớp. **Dùng một đề cho nhiều lớp** cùng môn và tạo Quiz cho từng lớp. |
| Câu hỏi 2 chiều với Moodle | Web Service `local_clo_sync_questions` + đọc ngân hàng câu hỏi Moodle: đẩy câu mới/sửa (Moodle tạo phiên bản mới), lấy câu sửa trên Moodle về, nhập câu GV soạn trên Moodle và gắn mã QB-n. |
| Nhập điểm thủ công / Excel | Bài KT **nhập điểm** (câu/ý chấm tay gắn CLO): lưới nhập điểm, bảng điểm mẫu Excel, hoặc tạo bài từ **file Excel bất kỳ** (bài làm ngoài hệ thống). Độ khó/độ phân biệt nhiều mức điểm, Cronbach's alpha. |
| Gộp 2–3 bài để đánh giá CĐR | Chọn bài làm minh chứng BM6; **Phân tích gộp** (cộng điểm theo SV hoặc cộng dồn lượt) → CLO và đóng góp PLO/PI từng CTĐT, xuất Excel. |
| Phụ đạo | Mỗi SV sai bao nhiêu câu, bấm SV xem danh sách câu sai (đã chọn – đáp án đúng – CLO – chương), **tạo bài phụ đạo** (câu đã sai + câu tương tự cùng CLO). |
| Đề & phiếu giấy, chấm phiếu | **Hệ thống tự sinh mã đề**, xem trước đề (1 cột hoặc **chia 2 cột**) và **phiếu trả lời** ngay trên màn hình, sửa câu tại chỗ, xuất PDF/Word/đáp án; mỗi câu 2–6 phương án, phiếu in đúng số ô. **Chấm phiếu bằng ảnh quét hoặc ảnh chụp điện thoại** (OpenCV: 4 ô định vị, nắn phối cảnh), soát/sửa rồi lưu. Vẫn giữ lựa chọn Moodle Offline Quiz. |
| Tạo bài KT ở môn học, chọn lớp khi xuất | Nút **+ Tạo bài KT** ngay trên thẻ môn; đề lưu ở môn (*đề của môn*), khi xuất bấm **Giao cho lớp HP / Xuất** chọn các lớp – mỗi lớp nhận bài riêng (kèm Quiz Moodle). Hộp chọn hình thức dạng thẻ, hộp thoại chuẩn hóa cỡ, không tràn ngang trên màn hình hẹp. |
| Thời gian trả lời từng câu, cảnh báo GV | Lấy thời điểm SV chọn đáp án từng câu từ Moodle (`question_attempt_steps`, chỉ đọc) → thời gian từng câu, thẻ **Thời gian làm bài**: cảnh báo SV **chọn đại rồi nộp** (vd. 50 câu/5 phút), **chọn xong không nộp chờ hết giờ**, bỏ dở; ngưỡng chỉnh được, diễn biến từng SV, xuất Excel; số cảnh báo hiện ở danh sách bài KT. Nên đặt Quiz 1 câu/trang. |

## Cấu trúc thư mục

| Thư mục | Nội dung |
|---|---|
| `moodle/local/clo` | Plugin Moodle: nút SSO, Web Service tạo Quiz / Offline Quiz, nhận kết quả, trang kết quả cho SV |
| `moodle/mod/offlinequiz_v4.5.4.zip` | Plugin Offline Quiz (GPL v3, mã gốc): in đề + phiếu, nhận diện phiếu quét, chấm bài thi giấy |
| `moodle/theme/ute` | Giao diện UTE LMS cho Moodle |
| `database/01_schema.sql` | CSDL `assessment_db` – 39 bảng, 4 view (MySQL 8) |
| `database/02_moodle_bridge.sql` | Cầu nối **chỉ đọc** tới CSDL Moodle 4.x: view + thủ tục `sp_sync_exam` (Reverse Shuffle) |
| `database/03_seed_reference.sql` | Dữ liệu tham chiếu trích từ biểu mẫu BM2 và bảng phân công đánh giá PIs (sinh bởi `gen_seed_reference.py`) |
| `database/04_ctdt_2026.sql` | CTĐT CNTT 2026, KTDL 2026 đọc từ PDF (sinh bởi `tools/ctdt_2026/doc_ctdt.py`) |
| `database/00_moodle_subset_for_test.sql` | 22 bảng Moodle 4.4 (từ install.xml) – chỉ dùng cho kiểm thử tự động |
| `backend/` | FastAPI + SQLAlchemy 2 + Pandas (Analysis Engine), xuất Excel/Word |
| `frontend/` | React 19 + Vite + Chart.js |
| `tools/moodle_e2e/` | Kiểm thử đầu-cuối với **Moodle 4.5 thật** |
| `docker-compose.yml`, `docker/` | MySQL 8.0 + Moodle 4.5 + hệ thống |
| `moodle/theme/ute/` | Giao diện Moodle "UTE – Khảo thí & CĐR" (kế thừa Boost) |
| `database/heidisql/` | Tệp SQL chạy trực tiếp trong HeidiSQL (MariaDB 10.4+) |
| `.gitignore`, `.gitattributes`, `backend/cau_hinh.env.example`, `0_CAU_HINH_MAY.example.bat` | Không đưa `.venv`, `__pycache__`, cấu hình có mật khẩu/token lên Git; máy mới tự tạo `cau_hinh.env` từ tệp mẫu; đường dẫn Moodle/PHP riêng từng máy khai báo trong `0_CAU_HINH_MAY.bat` (nếu cần); tệp `.bat` luôn được lấy về với xuống dòng CRLF; `8_CAP_NHAT_TU_GITHUB.bat` lấy bản mới từ GitHub về, `7_DON_DEP_GIT.bat` đẩy lên |

## Chạy bằng Docker

```bash
docker compose up -d --build
```

- Hệ thống: http://localhost:8000 — `gv.son / Gv@123456` (giảng viên), `admin / Admin@123` (bộ môn); sinh viên `22130001 / Sv@123456` đăng nhập **Moodle**
- Moodle: http://localhost:8080 — `admin / Moodle@123456` (lần đầu tự cài bằng CLI, mất vài phút)
- Nếu hệ thống khởi động trước khi Moodle cài xong: vào **Kết nối Moodle → Cài đặt cầu nối** (hoặc `docker compose restart app`).
- Tài khoản MySQL `tlcn` của hệ thống chỉ có quyền **SELECT** trên schema `moodle`.

> Ghi chú trung thực: môi trường phát triển của nhóm không kéo được image từ Docker Hub nên `docker compose` chưa được chạy thử
> trọn vẹn; từng thành phần đã được kiểm chứng riêng (xem mục Kiểm thử), gồm cả quá trình khởi động với đúng bộ quyền MySQL trong `docker/mysql/init.sql`.

## Chạy thủ công (không Docker)

```bash
# 1) CSDL (MySQL 8.0+) – tạo user có quyền trên assessment_db và SELECT trên moodle
cd backend && pip install -r requirements.txt
echo 'DATABASE_URL=mysql+pymysql://USER:PASS@127.0.0.1:3306/assessment_db?charset=utf8mb4' > .env
python -m app.cli init-db          # 39 bảng + dữ liệu tham chiếu
python -m app.cli seed-demo        # tài khoản, môn DBMS330284, 4 CLO, 30 câu hỏi, lớp HP 40 SV, 2 bài KT
python -m app.cli install-bridge   # khi đã có CSDL Moodle trên cùng server

# 2) Giao diện
cd ../frontend && npm install && npm run build     # backend tự phục vụ frontend/dist
cd ../backend && uvicorn app.main:app --port 8000  # tài liệu API: http://localhost:8000/docs
```

Phát triển giao diện: `npm run dev` (cổng 5173, tự chuyển `/api` sang cổng 8000).

## Quy trình demo

1. **GV** `gv.son` → *Ngân hàng câu hỏi*: xem/sửa câu hỏi, gắn CLO có trọng số; câu đã có kết quả thi bị khóa, chỉ được *Hủy*.
2. *Môn học của tôi → DBMS330284 → + Tạo bài KT*: chọn hình thức, chọn câu theo CLO/chương (hoặc sinh đề theo ma trận), xem độ phủ điểm theo CLO → *Lưu đề của môn* → **Giao cho lớp HP / Xuất** chọn lớp (mỗi lớp một bài, tạo luôn Quiz Moodle).
3. Bài **online**: *Tải Moodle XML* → nhập vào Moodle, tạo Quiz → *Liên kết* ID quiz → *Đồng bộ & phân tích*.
   Bài **giấy**: *Tạo đề thi giấy trên Moodle* (số mã đề, xáo câu/phương án) → tải đề, phiếu trả lời, đáp án từng mã đề (PDF/Word, .zip) để in
   → SV làm bài, ghi MSSV trên phiếu → quét phiếu, tải ảnh lên Moodle → **Moodle nhận diện & chấm** → *Đồng bộ & phân tích*.
4. Xem *Phân tích câu hỏi* (p, DI Kelley 27%, phân bố phương án), *Kết quả sinh viên* theo CLO.
5. *Kết quả CĐR (BM6)*: BM6a kế hoạch, BM6b tổng hợp, minh chứng BM6c/6d từng CLO, nhập nhận xét → **Xuất bộ BM6 của lớp (.xlsx)** hoặc **Xuất theo từng bài KT** (tệp BM6c riêng cho một bài kiểm tra, kèm MSSV – họ tên; cũng có nút ở trang bài KT).
6. *Công bố kết quả lên Moodle* → đăng nhập Moodle bằng SV `22130001` → khóa học → *Kết quả phân tích CĐR*: radar CLO và lộ trình ôn tập.
0. Khóa học mới tạo trên Moodle (GV là Teacher) hiện ở trang *Lớp học phần* → **Đưa vào hệ thống**.
7. **Bộ môn** `admin`: *Chương trình đào tạo*, *Học phần & đề cương* (thêm học phần, lớp HP + GV phụ trách; khai báo chương, CLO–PLO – xem HUONG_DAN_CAI_DAT.md), *Kế hoạch đo PI (BM3b)*, *Tổng hợp PLO (BM2/BM3c)* → **Xuất BM2/BM3 (.xlsx)** (BM2a kế hoạch, BM2b tổng kết, BM3b/BM3c từng CĐR) hoặc **Xuất BM2 (.docx)** đúng mẫu văn bản Word; trang Kế hoạch đo PI có nút **Xuất bảng phân công** đánh giá PIs theo học kỳ.

## Kiểm thử

```bash
python tools/kiem_thu/chay_kiem_thu_toan_bo.py --omr   # kiểm thử TOÀN BỘ: 99 ca + độ phủ 133/133 API + bảng kết quả docs/kiem_thu/KET_QUA_KIEM_THU.xlsx
cd backend && python -m pytest tests -q        # 99 ca: Analysis Engine, BM6c/6d, xuất biểu mẫu BM2/BM3/BM6 (Excel + Word) và phân công, API, phân quyền môn học & khóa học Moodle, sinh đề theo ma trận, SSO, nhập câu hỏi/gán CLO từ file, bài giấy từ Offline Quiz, CTĐT 2026 & đề cương, phân quyền GV chỉ xem CLO, nhập điểm/Excel, gộp bài, phụ đạo, đề giấy + chấm phiếu ảnh (OMR, cả phiếu gạch chéo và nét bút đè ô định vị), thời gian làm bài & cảnh báo, nâng cấp CSDL
python ../tools/omr/kiem_tra_omr.py          # độ bền bộ chấm phiếu: 6 điều kiện ảnh × 30 phiếu, 7 kiểu tô
python tests/ui_screens.py                     # Playwright: chụp 47 màn hình, bắt lỗi console
python ../tools/moodle_e2e/run_real_moodle_e2e.py /duong/dan/moodle   # E2E với Moodle 4.5 thật
python ../tools/moodle_e2e/kiem_tra_dong_bo_cau_hoi.py http://localhost:8000 gv.son Gv@123456 <id môn> <id khóa học Moodle>   # đồng bộ câu hỏi 2 chiều
```

Kiểm thử tự động dùng CSDL Moodle **mô phỏng** riêng (`moodle_sim`) và từ chối xóa một CSDL Moodle thật.
Kịch bản E2E dùng chính API của Moodle 4.5.14 để nhập tệp XML do hệ thống xuất, tạo Quiz xáo trộn phương án và cho 38 SV làm bài;
kết quả đồng bộ khớp 100% với điểm Moodle tự chấm (760/760 câu trả lời, 38/38 tổng điểm) ở cả 3 cách tính điểm của quiz
(điểm cao nhất, lượt đầu, lượt cuối).

## Dữ liệu minh họa

Danh sách PLO/PI, kế hoạch đo và phân công lấy từ biểu mẫu BM2 và bảng phân công đánh giá PIs của Bộ môn.
Hai CTĐT 2026 (CNTT, KTDL) được đọc từ văn bản chương trình đào tạo chính thức (PDF). Lớp `DBMS330284_02` (cùng GV) có bài tự luận nhập điểm để minh họa gộp bài và nhập điểm.
Nội dung CLO, câu hỏi, danh sách sinh viên và bài làm của môn DBMS330284 là **dữ liệu giả lập** để minh họa
(năng lực SV sinh theo mô hình IRT 1 tham số; câu 24 được cố ý làm "câu bẫy" để thấy DI âm).
