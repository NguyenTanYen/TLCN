<?php
// Plugin cầu nối Moodle ⇄ Hệ thống hỗ trợ GV kiểm tra, đánh giá và phân tích CĐR (Tiểu luận chuyên ngành – Nhóm 01).
// - Nút "Phân tích CĐR" cho giảng viên: đăng nhập một lần (SSO) sang hệ thống của nhóm.
// - Web Service để hệ thống tạo Quiz từ đề đã soạn và đẩy kết quả phân tích về Moodle.
// - Trang "Kết quả phân tích CĐR" để sinh viên xem kết quả ngay trên Moodle (UC-05).
defined('MOODLE_INTERNAL') || die();

$plugin->component = 'local_clo';
$plugin->version   = 2026100102;
$plugin->release   = '1.2';
$plugin->requires  = 2024100700;   // Moodle 4.5
$plugin->maturity  = MATURITY_STABLE;
