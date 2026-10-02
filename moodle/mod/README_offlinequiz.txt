Plugin Offline Quiz (mod_offlinequiz) v4.5.4 cho Moodle 4.5 – bài thi GIẤY
Nguồn: https://github.com/academic-moodle-cooperation/moodle-mod_offlinequiz (thẻ v4.5.4), giấy phép GNU GPL v3.
Giữ nguyên mã nguồn gốc, không chỉnh sửa. Đóng gói trong offlinequiz_v4.5.4.zip; 3_CAI_GIAO_DIEN_MOODLE.bat giải nén rồi chép vào <Moodle>\mod\offlinequiz.

Vai trò trong hệ thống: Moodle sinh đề in + phiếu trả lời + đáp án cho từng mã đề, nhận diện phiếu đã quét (MSSV, mã đề,
các ô đánh dấu) và chấm điểm. Hệ thống phân tích CĐR chỉ gửi đề (Web Service local_clo_create_offlinequiz) và kéo kết quả
đã chấm về (đọc chỉ-đọc mdl_offlinequiz_results) để phân tích.
Nhãn tiếng Việt trên đề/phiếu: local/clo/offlinequiz_lang (chép vào <moodledata>\lang\vi_local khi chạy setup.php).
