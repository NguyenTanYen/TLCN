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

## Các bước

Mọi tệp chạy nằm trong thư mục `scripts\` (bấm đúp, theo thứ tự):

| Tệp | Việc làm |
|---|---|
| `cai_dat.bat` | Tạo `.venv` và cài thư viện, tạo CSDL `assessment_db` + dữ liệu minh họa + cầu nối đọc `moodle_db`, chép giao diện và plugin vào Moodle 4.5, nâng cấp Moodle, ghi cấu hình kết nối vào `backend\cau_hinh.env`. Chạy lại được bất cứ lúc nào (ví dụ sau khi cập nhật plugin). Cần bật MySQL/MariaDB và Internet. |
| `tao_du_lieu_demo.bat` | *(Tùy chọn)* tạo khóa học và 40 SV trên Moodle, Quiz có bài làm thật, bài giấy 2 mã đề (38 phiếu được Moodle nhận diện và chấm), đồng bộ, phân tích, công bố. |
| `chay.bat` | Chạy hệ thống tại http://localhost:8000 (giữ cửa sổ mở). |
| `kiem_thu.bat` | *(Tùy chọn)* kiểm thử toàn bộ chức năng, xuất `docs\kiem_thu\KET_QUA_KIEM_THU.xlsx`. Dựng lại CSDL nên chạy xong cần chạy lại `tao_du_lieu_demo.bat`. |
| `cau_hinh.bat` | Không cần chạy: các tệp trên tự gọi để dò XAMPP, PHP, Moodle 4.5. |

Tính lại độc lập các độ đo để đối chiếu với hệ thống: `.venv\Scripts\python.exe tools\kiem_tra_do_luong.py`.

Có thể tạo CSDL bằng HeidiSQL: chạy (F9) lần lượt `database\heidisql\1_tao_csdl_assessment_db.sql`
rồi `database\heidisql\2_cau_noi_moodle_db.sql`.

## Tài khoản

| Nơi | Vai trò | Đăng nhập |
|---|---|---|
| Hệ thống (localhost:8000) | Bộ môn / quản trị | `admin` / `Admin@123` (hoặc bấm “Phân tích CĐR” từ tài khoản admin Moodle) |
| Hệ thống | Giảng viên | `gv.son` / `Gv@123456` (hoặc bấm “Phân tích CĐR” từ Moodle) |
| Moodle (sau khi tạo dữ liệu demo) | Giảng viên | `gv.son` / `Gv@123456` |
| Moodle (sau khi tạo dữ liệu demo) | Sinh viên | `22130001` … `22130040` / `Sv@123456` |

Trang đăng nhập của hệ thống chỉ hiện nút điền nhanh tài khoản minh họa khi `backend\cau_hinh.env` có `DEMO_MODE=true`
(`tao_du_lieu_demo.bat` tự thêm dòng này; khi triển khai thật hãy xóa dòng đó rồi chạy lại `chay.bat`).

Phân quyền: giảng viên chỉ thao tác trên lớp học phần mình phụ trách và ngân hàng câu hỏi của môn mình dạy; khi gắn
khóa học / Quiz / Offline Quiz của Moodle, hệ thống kiểm tra tài khoản Moodle cùng tên là *giảng viên* của khóa học đó.

Giảng viên đăng nhập bằng nút trên Moodle lần đầu sẽ được tạo tài khoản nếu **mã giảng viên** trong danh sách bộ môn
trùng tên đăng nhập hoặc *ID number* của họ trên Moodle. Sinh viên không đăng nhập vào hệ thống của nhóm.

## Luồng demo
0. **Tạo bài kiểm tra ở môn học, chọn lớp khi xuất:** *Môn học của tôi* → thẻ môn DBMS330284 → **+ Tạo bài KT** (hoặc trang môn → **+ Tạo bài kiểm tra**)
   → chọn hình thức (trực tuyến / trên giấy / nhập điểm) → soạn đề → **Lưu đề của môn**. Đề nằm ở thẻ *Đề kiểm tra* của môn, chưa gắn lớp.
   Khi xuất: bấm **Giao cho lớp HP / Xuất** → tích các lớp (VD DBMS330284_01, _02) → mỗi lớp có một bài riêng (bài trực tuyến tạo luôn Quiz
   trên khóa học Moodle đã gắn của lớp). Vẫn có thể tạo bài cho riêng một lớp ở trang lớp.
   **Ra đề theo ma trận:** trong hộp soạn đề → khung *Sinh đề tự động theo ma trận*: nhập số câu
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

## Chức năng mới theo góp ý 15/10

1. **Chương trình đào tạo** (menu trên): CNTT 2026, KTDL 2026 – PLO/PI, học phần theo học kỳ, ma trận học phần – PI.
   Bấm một học phần → **Đề cương chi tiết** (thông tin chung, mô tả, tiên quyết, CLO – PLO, PI đáp ứng, chương, kế hoạch BM6a); nút *In đề cương*.
2. **Môn học của tôi** (trang chính của GV): mỗi môn hiện các lớp GV dạy; *⟳ Đồng bộ các lớp với Moodle* tự gắn lớp với khóa học Moodle
   **trùng mã lớp** và cập nhật SV. Trong lớp: *Khóa học Moodle #… ↗* mở thẳng Moodle; trên Moodle nút *Phân tích CĐR* mở đúng lớp.
3. Bài kiểm tra → **⧉ Dùng đề cho lớp khác**: sao đề sang các lớp khác cùng môn và tạo Quiz trên Moodle cho từng lớp.
4. **Nhập điểm**: Môn học hoặc Lớp → *+ Tạo bài kiểm tra* → *Nhập điểm* → khai báo câu/ý, điểm tối đa, CLO → nhập trên lưới, hoặc *Bảng điểm mẫu (Excel)* → điền → *Nhập từ Excel*.
   Bài làm ngoài hệ thống: tab *Tạo từ file Excel có sẵn* (tiêu đề cột kiểu `Bài 1 (5đ) [CLO3]`; thiếu điểm/CLO thì chọn ở bước xem trước).
5. **Gộp bài KT**: trang môn học → *Gộp bài KT đánh giá CĐR* → chọn 2–3 bài (có thể khác lớp) → *Phân tích gộp* → CLO, PLO/PI từng CTĐT → *Xuất Excel*.
   Cột *Minh chứng BM6* chọn bài nào được tính vào BM6/PI/PLO của lớp.
6. **Phụ đạo**: Lớp → *Phụ đạo (câu sai)* → số câu sai từng SV → bấm SV xem câu sai → *Tạo bài phụ đạo* (câu đã sai + câu tương tự cùng CLO).
7. **Đề giấy trên hệ thống**: bài *Trên giấy* → *In và chấm ngay trên hệ thống* → (1) sinh mã đề → (2) xem trước đề **1 cột hoặc chia 2 cột**,
   sửa câu tại chỗ (✎), xuất PDF/Word/đáp án/trọn bộ .zip → (3) xem trước và chỉnh **phiếu trả lời** (số chữ số MSSV, phần tự luận) → in →
   (4) *Chấm phiếu*: tải ảnh quét/PDF hoặc **chụp bằng điện thoại** → soát MSSV, mã đề, đáp án (ô vàng: tô 2 ô/bỏ trống) → *Lưu & phân tích*.
   Vẫn có thể chọn *Dùng Moodle Offline Quiz* như trước.
8. **Ngân hàng câu hỏi → ⇅ Đồng bộ với Moodle**: so sánh từng câu (QB-n) với ngân hàng câu hỏi khóa học Moodle → đẩy lên (Moodle tạo phiên bản mới),
   lấy về câu sửa trên Moodle, nhập câu GV soạn trên Moodle.
9. **Thời gian làm bài & cảnh báo** (bài trực tuyến đã đồng bộ): bài KT → thẻ **Thời gian làm bài**. Hệ thống lấy thời điểm SV chọn đáp án từng câu
   từ Moodle và cảnh báo:
   - **Làm quá nhanh – nghi chọn đại**: trung bình < 6 giây/câu, hoặc ≥ 25% số câu trả lời "chớp nhoáng" (dưới 3 giây hoặc dưới 10% thời gian
     trung vị của câu, tối đa 10 giây). Ví dụ 50 câu trong 5 phút = 6 giây/câu.
   - **Chọn xong không nộp – để hết giờ**: Moodle tự nộp khi hết giờ và trước đó SV không thao tác ≥ 10 phút và ≥ 30% thời gian làm bài.
   - **Bỏ dở**: bỏ trống từ một nửa số câu rồi nộp. *Lưu ý* (mức nhẹ): để lâu mới tự nộp; dồn nhiều đáp án vào 60 giây cuối.

   Các ngưỡng sửa ngay trên trang (*Áp dụng ngưỡng*), *Diễn biến* xem từng câu của một SV, *Xuất Excel*. Danh sách bài KT của lớp hiện **⚠ N cảnh báo**.
   Đây là **dấu hiệu để xem lại**, không phải kết luận gian lận.
   - Để có thời gian **từng câu**, đặt Quiz **1 câu mỗi trang** (Quiz tạo bằng nút *Tạo Quiz trên Moodle* đã đặt sẵn) và bật *Khi hết giờ: tự nộp bài*.
     Nếu nhiều câu một trang, Moodle chỉ lưu khi chuyển trang nên thời gian chỉ chính xác tới từng trang (trang có thông báo).
   - Bài đã đồng bộ trước bản cập nhật này: bấm **Đồng bộ lại** để lấy thời gian. Dữ liệu demo (bat 4) có 2 SV chọn đại (22130017, 22130018)
     và 2 SV chọn xong để hết giờ (22130006, 22130023).
10. **Tạo bài KT ở môn học**: nút **+ Tạo bài KT** ngay trên thẻ môn; đề lưu ở môn (thẻ *Đề kiểm tra*), khi xuất mới **Giao cho lớp HP**
   (chọn một hoặc nhiều lớp; lớp đã giao được đánh dấu, không tạo trùng). Thao tác cần danh sách SV (tạo Quiz, in đề, nhập điểm) làm ở bài của lớp.

## Khai báo một học phần mới (môn khác) và gán CLO

**Khóa học đã tạo sẵn trên Moodle** (cách nhanh nhất): quản trị Moodle tạo khóa học và ghi danh GV với vai trò
*Teacher*. GV mở hệ thống → trang **Lớp học phần** hiện khung *"Khóa học trên Moodle chưa có trong hệ thống"* →
**Đưa vào hệ thống** → chọn môn học (tự gợi ý nếu tên khóa chứa mã môn), học kỳ (gợi ý theo ngày bắt đầu khóa học,
tự tạo học kỳ mới nếu chưa có), mã lớp → hệ thống tạo lớp HP do GV phụ trách, gắn khóa học và lấy danh sách SV.
Bấm nút *Phân tích CĐR* trong khóa học đó trên Moodle cũng mở thẳng hộp thoại này. Môn học chưa có thì Bộ môn
(`admin`) làm thao tác trên (chọn GV, tạo môn mới ngay trong hộp thoại). SV ghi danh thêm sau: nút **↻ SV**.

Trang học phần, tab **Khai báo (Bộ môn)** có *bảng kiểm tra 5 bước*; làm lần lượt đến khi hiện "Học phần đã sẵn sàng".

| Bước | Ai làm | Làm ở đâu |
|---|---|---|
| 1. Môn học (nếu chưa có): mã, tên, số tín chỉ, chỉ tiêu đạt CĐR môn | **Bộ môn** (`admin`) | Học phần & đề cương → *+ Học phần mới* |
| 2. Lớp học phần: học kỳ, mã lớp, **GV phụ trách** | **Bộ môn** | trang học phần → tab *Lớp học phần* → *+ Lớp HP* |
| 3. Các chương của đề cương (thêm từng chương hoặc dán nhiều dòng "1. Tên chương") | **Bộ môn** | Học phần & đề cương → học phần → *Khai báo (Bộ môn)* |
| 4. CLO: mã, nội dung, mức Bloom mục tiêu, PLO đóng góp (theo các CTĐT có học phần) + mức I/R/M | **Bộ môn** | như trên → *+ CLO* |
| 5. Kế hoạch BM6a (ngưỡng đạt, chỉ tiêu, loại minh chứng) – không bắt buộc | GV | nút *BM6a* của lớp |
| 6. Câu hỏi + gán chương/Bloom/CLO (file mẫu, cột CLO dạng `CLO2:0.6; CLO4:0.4`) | GV | Ngân hàng câu hỏi |
| 7. Ra đề theo ma trận → nhập **ID khóa học Moodle** khi tạo Quiz/đề giấy lần đầu | GV | Môn học → + Tạo bài kiểm tra → Giao cho lớp HP / Xuất (hoặc Lớp học phần → Tạo bài kiểm tra) |

**Phân quyền:** GV *không* tạo được môn học, *không* tạo tay lớp HP (403) – chỉ được đưa vào khóa học Moodle mà mình là giảng viên, gắn với môn đã có. Chương, CLO, thông tin học phần do **Bộ môn** quản lý theo CTĐT – GV chỉ xem (góp ý 15/10). **Khóa học Moodle** do quản trị Moodle tạo và ghi danh GV với vai trò *Teacher/Non-editing teacher*;
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
- Bài giấy báo *Moodle chưa cài plugin Offline Quiz* → chạy lại `scripts\cai_dat.bat`.
- Tải ảnh quét lên Moodle nhưng *Moodle chưa chấm phiếu nào* → bấm *Cho Moodle chấm phiếu đang chờ* trong hệ thống;
  phiếu lỗi (MSSV sai/mờ) sửa tại trang *Sửa lỗi phiếu* của Offline Quiz rồi đồng bộ lại.
- `Access denied for user 'root'` → sửa mật khẩu trong `backend\cau_hinh.env` (dòng `DATABASE_URL`).
- Nút “Tạo Quiz”/“Công bố” báo *Chưa cấu hình kết nối Moodle* → chạy lại `scripts\cai_dat.bat`.
- Bấm “Phân tích CĐR” báo *chưa được bộ môn khai báo là giảng viên* → thêm giảng viên (mã GV = tên đăng nhập Moodle).
- Cổng 8000 bận → đặt `set "APP_PORT=8010"` trong `scripts\cau_hinh_may.bat`, chạy lại `scripts\cai_dat.bat` và `scripts\chay.bat`.
- `cai_dat.bat` / `tao_du_lieu_demo.bat` báo *Chưa xác định được thư mục Moodle 4.5 / php.exe* → khai báo `MOODLE_DIR`, `PHP_BIN` trong `scripts\cau_hinh_may.bat`.
