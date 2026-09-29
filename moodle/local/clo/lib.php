<?php
defined('MOODLE_INTERNAL') || die();

/**
 * Người dùng hiện tại có được mở hệ thống phân tích CĐR không (quản trị hoặc GV của ít nhất một khóa học).
 */
function local_clo_can_launch(?int $courseid = null): bool {
    static $cache = [];
    if (!isloggedin() || isguestuser()) {
        return false;
    }
    if (is_siteadmin()) {
        return true;
    }
    $key = (int)$courseid;
    if (!array_key_exists($key, $cache)) {
        if ($courseid) {
            $cache[$key] = has_capability('local/clo:launch', context_course::instance($courseid));
        } else {
            $cache[$key] = has_capability('local/clo:launch', context_system::instance())
                || !empty(get_user_capability_course('local/clo:launch', null, false, '', '', 1));
        }
    }
    return $cache[$key];
}

/** Địa chỉ hệ thống phân tích CĐR. */
function local_clo_appurl(): string {
    $url = trim((string)get_config('local_clo', 'appurl'));
    return rtrim($url !== '' ? $url : 'http://localhost:8000', '/');
}

/**
 * Thêm vào menu khóa học: "Kết quả phân tích CĐR" (SV + GV) và "Mở hệ thống phân tích CĐR" (chỉ GV).
 */
function local_clo_extend_navigation_course(navigation_node $navigation, stdClass $course, context $context) {
    if ($course->id == SITEID) {
        return;
    }
    if (has_any_capability(['local/clo:viewown', 'local/clo:viewall'], $context)) {
        $navigation->add(get_string('results', 'local_clo'), new moodle_url('/local/clo/results.php', ['id' => $course->id]),
            navigation_node::TYPE_CUSTOM, null, 'local_clo_results', new pix_icon('i/report', ''));
    }
    if (local_clo_can_launch($course->id)) {
        $navigation->add(get_string('launch', 'local_clo'), new moodle_url('/local/clo/launch.php', ['courseid' => $course->id]),
            navigation_node::TYPE_CUSTOM, null, 'local_clo_launch', new pix_icon('i/stats', ''));
    }
}
