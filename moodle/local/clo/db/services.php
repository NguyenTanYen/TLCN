<?php
defined('MOODLE_INTERNAL') || die();

$functions = [
    'local_clo_create_quiz' => [
        'classname'   => 'local_clo\external\create_quiz',
        'description' => 'Tạo Quiz (xáo trộn phương án) trong khóa học từ tệp Moodle XML do hệ thống phân tích CĐR sinh ra.',
        'type'        => 'write',
        'capabilities' => 'local/clo:manage, moodle/course:manageactivities, moodle/question:add',
    ],
    'local_clo_push_results' => [
        'classname'   => 'local_clo\external\push_results',
        'description' => 'Nhận kết quả phân tích CĐR (điểm, mức đạt CLO, lộ trình ôn tập) và trạng thái công bố của một bài kiểm tra.',
        'type'        => 'write',
        'capabilities' => 'local/clo:manage',
    ],
];

$services = [
    'Hệ thống phân tích CĐR' => [
        'functions' => ['local_clo_create_quiz', 'local_clo_push_results', 'core_webservice_get_site_info'],
        'shortname' => 'local_clo',
        'restrictedusers' => 0,
        'enabled' => 1,
        'downloadfiles' => 0,
        'uploadfiles' => 0,
    ],
];
