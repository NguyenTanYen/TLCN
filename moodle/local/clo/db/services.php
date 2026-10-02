<?php
defined('MOODLE_INTERNAL') || die();

$functions = [
    'local_clo_create_quiz' => [
        'classname'   => 'local_clo\external\create_quiz',
        'description' => 'Tạo Quiz (xáo trộn phương án) trong khóa học từ tệp Moodle XML do hệ thống phân tích CĐR sinh ra.',
        'type'        => 'write',
        'capabilities' => 'local/clo:manage, moodle/course:manageactivities, moodle/question:add',
    ],
    'local_clo_create_offlinequiz' => [
        'classname'   => 'local_clo\external\create_offlinequiz',
        'description' => 'Tạo bài thi giấy (Offline Quiz nhiều nhóm đề) từ tệp Moodle XML và sinh tệp đề, phiếu trả lời, đáp án để in.',
        'type'        => 'write',
        'capabilities' => 'local/clo:manage, moodle/course:manageactivities, moodle/question:add',
    ],
    'local_clo_get_offlinequiz' => [
        'classname'   => 'local_clo\external\get_offlinequiz',
        'description' => 'Trạng thái bài thi giấy: tệp đề/phiếu của từng nhóm và số bài Moodle đã chấm.',
        'type'        => 'read',
        'capabilities' => 'local/clo:manage',
    ],
    'local_clo_process_scans' => [
        'classname'   => 'local_clo\external\process_scans',
        'description' => 'Cho Offline Quiz nhận diện và chấm ngay các phiếu trả lời đã quét đang chờ trong hàng đợi.',
        'type'        => 'write',
        'capabilities' => 'local/clo:manage',
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
        'functions' => ['local_clo_create_quiz', 'local_clo_create_offlinequiz', 'local_clo_get_offlinequiz', 'local_clo_process_scans',
                        'local_clo_push_results', 'core_webservice_get_site_info'],
        'shortname' => 'local_clo',
        'restrictedusers' => 0,
        'enabled' => 1,
        'downloadfiles' => 1,   // tải tệp đề/phiếu Offline Quiz qua webservice/pluginfile.php
        'uploadfiles' => 0,
    ],
];
