<?php
defined('MOODLE_INTERNAL') || die();

$messageproviders = [
    // Thông báo cho sinh viên khi giảng viên công bố kết quả phân tích CĐR.
    'resultpublished' => [
        'defaults' => [
            'popup' => MESSAGE_PERMITTED + MESSAGE_DEFAULT_ENABLED,
            'email' => MESSAGE_PERMITTED,
        ],
    ],
];
