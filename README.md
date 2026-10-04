# Hệ thống hỗ trợ Giảng viên triển khai kiểm tra, đánh giá và phân tích mức độ đạt CĐR

Tiểu luận chuyên ngành – Nhóm 01 · Nguyễn Trần Quốc Thi (23110331) · Nguyễn Tấn Yên (23110369) · GVHD: ThS. Trần Trọng Bình

Hệ thống giúp giảng viên **biên soạn câu hỏi trắc nghiệm gắn CLO**, **tổ chức kiểm tra trực tuyến (Moodle Quiz) và trên giấy (Moodle Offline Quiz: in đề nhiều mã đề, quét phiếu, Moodle chấm)**,
**kéo bài làm đã chấm từ Moodle về**, **phân tích chất lượng câu hỏi (p, DI)** và **đo lường mức độ đạt CĐR** theo đúng các biểu mẫu của HCMUTE:
BM6a–6d (CĐR môn học, cả BM6c riêng từng bài kiểm tra) và BM2a–2b (Excel + Word), BM3b–3c, bảng phân công đánh giá PIs (CĐR chương trình đào tạo, PI), kèm **lộ trình ôn tập cá nhân hóa** cho sinh viên.

Hệ thống dành cho **giảng viên / bộ môn**; sinh viên làm bài và xem kết quả phân tích trên **Moodle**. Hai hệ thống nối với nhau qua plugin Moodle `local_clo` (nút *Phân tích CĐR* đăng nhập một lần, Web Service tạo Quiz / Offline Quiz và nhận kết quả) và cầu nối CSDL chỉ đọc để kéo bài làm – xem `HUONG_DAN_CAI_DAT.md`.

> **Cài trên Windows + XAMPP:** xem `HUONG_DAN_CAI_DAT.md` (các tệp `.bat` 0–6).

## Cấu trúc thư mục

| Thư mục | Nội dung |
|---|---|
| `moodle/local/clo` | Plugin Moodle: nút SSO, Web Service tạo Quiz / Offline Quiz, nhận kết quả, trang kết quả cho SV |
| `moodle/mod/offlinequiz_v4.5.4.zip` | Plugin Offline Quiz (GPL v3, mã gốc): in đề + phiếu, nhận diện phiếu quét, chấm bài thi giấy |
| `moodle/theme/ute` | Giao diện UTE LMS cho Moodle |
| `database/01_schema.sql` | CSDL `assessment_db` – 39 bảng, 4 view (MySQL 8) |
| `database/02_moodle_bridge.sql` | Cầu nối **chỉ đọc** tới CSDL Moodle 4.x: view + thủ tục `sp_sync_exam` (Reverse Shuffle) |
| `database/03_seed_reference.sql` | Dữ liệu tham chiếu trích từ biểu mẫu BM2 và bảng phân công đánh giá PIs (sinh bởi `gen_seed_reference.py`) |
| `database/00_moodle_subset_for_test.sql` | 22 bảng Moodle 4.4 (từ install.xml) – chỉ dùng cho kiểm thử tự động |
| `backend/` | FastAPI + SQLAlchemy 2 + Pandas (Analysis Engine), xuất Excel/Word |
| `frontend/` | React 19 + Vite + Chart.js |
| `tools/moodle_e2e/` | Kiểm thử đầu-cuối với **Moodle 4.5 thật** |
| `docker-compose.yml`, `docker/` | MySQL 8.0 + Moodle 4.5 + hệ thống |
| `moodle/theme/ute/` | Giao diện Moodle "UTE – Khảo thí & CĐR" (kế thừa Boost) |
| `database/heidisql/` | Tệp SQL chạy trực tiếp trong HeidiSQL (MariaDB 10.4+) |
| `.gitignore`, `backend/cau_hinh.env.example`, `0_CAU_HINH_MAY.example.bat` | Không đưa `.venv`, `__pycache__`, cấu hình có mật khẩu/token lên Git; máy mới tự tạo `cau_hinh.env` từ tệp mẫu; đường dẫn Moodle/PHP riêng từng máy khai báo trong `0_CAU_HINH_MAY.bat` (nếu cần) |

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
2. *Lớp học phần → DBMS330284_01 → Tạo bài kiểm tra*: chọn câu theo CLO/chương, xem độ phủ điểm theo CLO.
3. Bài **online**: *Tải Moodle XML* → nhập vào Moodle, tạo Quiz → *Liên kết* ID quiz → *Đồng bộ & phân tích*.
   Bài **giấy**: *Tạo đề thi giấy trên Moodle* (số mã đề, xáo câu/phương án) → tải đề, phiếu trả lời, đáp án từng mã đề (PDF/Word, .zip) để in
   → SV làm bài, ghi MSSV trên phiếu → quét phiếu, tải ảnh lên Moodle → **Moodle nhận diện & chấm** → *Đồng bộ & phân tích*.
4. Xem *Phân tích câu hỏi* (p, DI Kelley 27%, phân bố phương án), *Kết quả sinh viên* theo CLO.
5. *Kết quả CĐR (BM6)*: BM6a kế hoạch, BM6b tổng hợp, minh chứng BM6c/6d từng CLO, nhập nhận xét → **Xuất bộ BM6 của lớp (.xlsx)** hoặc **Xuất theo từng bài KT** (tệp BM6c riêng cho một bài kiểm tra, kèm MSSV – họ tên; cũng có nút ở trang bài KT).
6. *Công bố kết quả lên Moodle* → đăng nhập Moodle bằng SV `22130001` → khóa học → *Kết quả phân tích CĐR*: radar CLO và lộ trình ôn tập.
0. Khóa học mới tạo trên Moodle (GV là Teacher) hiện ở trang *Lớp học phần* → **Đưa vào hệ thống**.
7. **Bộ môn** `admin`: *Học phần & CLO* (thêm môn, lớp HP + GV phụ trách; GV khai báo chương, CLO–PLO – xem HUONG_DAN_CAI_DAT.md), *CTĐT – PLO/PI*, *Kế hoạch đo PI (BM3b)*, *Tổng hợp PLO (BM2/BM3c)* → **Xuất BM2/BM3 (.xlsx)** (BM2a kế hoạch, BM2b tổng kết, BM3b/BM3c từng CĐR) hoặc **Xuất BM2 (.docx)** đúng mẫu văn bản Word; trang Kế hoạch đo PI có nút **Xuất bảng phân công** đánh giá PIs theo học kỳ.

## Kiểm thử

```bash
cd backend && python -m pytest tests -q        # 77 ca: Analysis Engine, BM6c/6d, xuất biểu mẫu BM2/BM3/BM6 (Excel + Word) và phân công, API, phân quyền môn học & khóa học Moodle, sinh đề theo ma trận, SSO, nhập câu hỏi/gán CLO từ file, bài giấy từ Offline Quiz, nâng cấp CSDL
python tests/ui_screens.py                     # Playwright: chụp 22 màn hình, bắt lỗi console
python ../tools/moodle_e2e/run_real_moodle_e2e.py /duong/dan/moodle   # E2E với Moodle 4.5 thật
```

Kiểm thử tự động dùng CSDL Moodle **mô phỏng** riêng (`moodle_sim`) và từ chối xóa một CSDL Moodle thật.
Kịch bản E2E dùng chính API của Moodle 4.5.14 để nhập tệp XML do hệ thống xuất, tạo Quiz xáo trộn phương án và cho 38 SV làm bài;
kết quả đồng bộ khớp 100% với điểm Moodle tự chấm (760/760 câu trả lời, 38/38 tổng điểm) ở cả 3 cách tính điểm của quiz
(điểm cao nhất, lượt đầu, lượt cuối).

## Dữ liệu minh họa

Danh sách PLO/PI, kế hoạch đo và phân công lấy từ biểu mẫu BM2 và bảng phân công đánh giá PIs của Bộ môn.
Nội dung CLO, câu hỏi, danh sách sinh viên và bài làm của môn DBMS330284 là **dữ liệu giả lập** để minh họa
(năng lực SV sinh theo mô hình IRT 1 tham số; câu 24 được cố ý làm "câu bẫy" để thấy DI âm).
