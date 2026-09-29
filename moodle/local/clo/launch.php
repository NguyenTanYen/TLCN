<?php
// Nút "Phân tích CĐR": kiểm tra quyền giảng viên rồi chuyển sang hệ thống phân tích kèm vé SSO.
require_once(__DIR__ . '/../../config.php');
require_once(__DIR__ . '/lib.php');

$courseid = optional_param('courseid', 0, PARAM_INT);
if ($courseid) {
    $course = get_course($courseid);
    require_login($course);
} else {
    require_login();
}
$PAGE->set_url(new moodle_url('/local/clo/launch.php', ['courseid' => $courseid]));
$PAGE->set_context($courseid ? context_course::instance($courseid) : context_system::instance());

if (!local_clo_can_launch($courseid ?: null)) {
    throw new required_capability_exception($PAGE->context, 'local/clo:launch', 'nopermissions', '');
}
// Kiểm tra hệ thống phân tích có đang chạy không để báo lỗi dễ hiểu thay vì trang trắng của trình duyệt.
$app = parse_url(local_clo_appurl());
$host = $app['host'] ?? 'localhost';
$port = $app['port'] ?? ((($app['scheme'] ?? 'http') === 'https') ? 443 : 80);
$sock = @fsockopen($host === 'localhost' ? '127.0.0.1' : $host, $port, $errno, $errstr, 2);
if (!$sock) {
    $PAGE->set_title(get_string('launch', 'local_clo'));
    $PAGE->set_heading(get_string('launch', 'local_clo'));
    echo $OUTPUT->header();
    echo $OUTPUT->notification(get_string('appdown', 'local_clo', local_clo_appurl()), 'error', false);
    echo $OUTPUT->single_button(new moodle_url('/local/clo/launch.php', ['courseid' => $courseid]), get_string('retry', 'local_clo'));
    echo $OUTPUT->footer();
    exit;
}
fclose($sock);
$token = \local_clo\sso::make_token($USER, $courseid);
$target = local_clo_appurl() . '/api/auth/moodle-sso?token=' . rawurlencode($token);
redirect(new moodle_url($target));
