<?php
defined('MOODLE_INTERNAL') || die();

$capabilities = [
    // Mở hệ thống phân tích CĐR (SSO) – chỉ giảng viên / quản lý.
    'local/clo:launch' => [
        'captype' => 'read',
        'contextlevel' => CONTEXT_COURSE,
        'archetypes' => ['editingteacher' => CAP_ALLOW, 'teacher' => CAP_ALLOW, 'manager' => CAP_ALLOW],
    ],
    // Xem kết quả phân tích của chính mình (sinh viên).
    'local/clo:viewown' => [
        'captype' => 'read',
        'contextlevel' => CONTEXT_COURSE,
        'archetypes' => ['student' => CAP_ALLOW],
    ],
    // Xem kết quả phân tích của cả lớp (giảng viên).
    'local/clo:viewall' => [
        'captype' => 'read',
        'riskbitmask' => RISK_PERSONAL,
        'contextlevel' => CONTEXT_COURSE,
        'archetypes' => ['editingteacher' => CAP_ALLOW, 'teacher' => CAP_ALLOW, 'manager' => CAP_ALLOW],
    ],
    // Được hệ thống phân tích gọi qua Web Service (tạo Quiz, đẩy kết quả).
    'local/clo:manage' => [
        'captype' => 'write',
        'riskbitmask' => RISK_PERSONAL | RISK_XSS,
        'contextlevel' => CONTEXT_COURSE,
        'archetypes' => ['manager' => CAP_ALLOW],
    ],
];
