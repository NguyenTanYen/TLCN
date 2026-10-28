<?php
// Đích của nút "Mở Moodle" trong hệ thống phân tích CĐR: kiểm tra vé một lần rồi đăng nhập Moodle bằng đúng tài khoản
// đang dùng ở hệ thống (thay phiên Moodle cũ nếu đang đăng nhập tài khoản khác).
require_once(__DIR__ . '/../../config.php');
require_once(__DIR__ . '/lib.php');

$token = required_param('token', PARAM_RAW_TRIMMED);
$next = optional_param('next', '/', PARAM_LOCALURL);
$PAGE->set_url(new moodle_url('/local/clo/sso_in.php'));
$PAGE->set_context(context_system::instance());

$claims = \local_clo\sso::verify_incoming($token, \local_clo\sso::secret());

// Vé chỉ dùng được một lần.
$cache = \cache::make_from_params(\cache_store::MODE_APPLICATION, 'local_clo', 'ssojti', [], ['simplekeys' => true, 'ttl' => 300]);
$key = substr(hash('sha256', $claims['jti']), 0, 40);
if ($cache->get($key)) {
    throw new \moodle_exception('ssoused', 'local_clo');
}
$cache->set($key, 1);

$user = $DB->get_record('user', ['username' => core_text::strtolower($claims['sub']), 'mnethostid' => $CFG->mnet_localhost_id,
    'deleted' => 0, 'suspended' => 0]);
if (!$user || isguestuser($user) || $user->auth === 'nologin') {
    throw new \moodle_exception('ssonouser', 'local_clo', '', s($claims['sub']));
}
// Không bao giờ cấp quyền cao hơn vai trò hệ thống xác nhận: tài khoản quản trị Moodle chỉ vào được từ tài khoản quản trị của hệ thống.
if (is_siteadmin($user) && $claims['role'] !== 'admin') {
    throw new \moodle_exception('ssoadmin', 'local_clo');
}
if ($USER && !empty($USER->id) && (int)$USER->id !== (int)$user->id) {
    require_logout();
}
$user = get_complete_user_data('id', $user->id);
complete_user_login($user);
redirect(new moodle_url($next === '' ? '/' : $next));
