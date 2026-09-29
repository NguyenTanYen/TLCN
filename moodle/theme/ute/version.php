<?php
// Giao diện "UTE LMS" cho Moodle 4.5 (kế thừa Boost) – giao diện học tập trực tuyến cho sinh viên và giảng viên.
// Tiểu luận chuyên ngành – Nhóm 01 (Nguyễn Trần Quốc Thi, Nguyễn Tấn Yên).
defined('MOODLE_INTERNAL') || die();

$plugin->component = 'theme_ute';
$plugin->version   = 2026092900;
$plugin->release   = '1.1';
$plugin->requires  = 2024100700;          // Moodle 4.5
$plugin->maturity  = MATURITY_STABLE;
$plugin->dependencies = ['theme_boost' => 2024100700];
