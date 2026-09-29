<?php
defined('MOODLE_INTERNAL') || die();

/** SCSS chính = preset mặc định của Boost + phần tùy biến của UTE. */
function theme_ute_get_main_scss_content($theme) {
    global $CFG;
    $scss = file_get_contents($CFG->dirroot . '/theme/boost/scss/preset/default.scss');
    $scss .= "\n" . file_get_contents(__DIR__ . '/scss/ute.scss');
    return $scss;
}

/** Biến SCSS đặt trước (màu chủ đạo, phông chữ, bo góc). */
function theme_ute_get_pre_scss($theme) {
    $brand = !empty($theme->settings->brandcolor) ? $theme->settings->brandcolor : '#0b3d91';
    $accent = !empty($theme->settings->accentcolor) ? $theme->settings->accentcolor : '#f5a623';
    $scss  = "\$primary: {$brand};\n\$ute-accent: {$accent};\n";
    $scss .= "\$font-family-sans-serif: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;\n";
    $scss .= "\$border-radius: .5rem;\n\$border-radius-lg: .75rem;\n\$card-border-radius: .75rem;\n";
    $scss .= "\$body-bg: #f4f6fb;\n\$navbar-height: 64px;\n";
    return $scss;
}

/** SCSS bổ sung do quản trị nhập (Quản trị > Giao diện > UTE). */
function theme_ute_get_extra_scss($theme) {
    return !empty($theme->settings->scss) ? $theme->settings->scss : '';
}

/** Dữ liệu dùng chung cho banner trang chủ / dải chào mừng ở bảng điều khiển. */
function theme_ute_hero_context(): array {
    global $DB, $USER;
    $cfg = get_config('theme_ute');
    $stats = [];
    try {
        $stats = [
            ['value' => $DB->count_records_select('course', 'id <> ? AND visible = 1', [SITEID]), 'label' => get_string('stat_courses', 'theme_ute')],
            ['value' => $DB->count_records_select('user', 'deleted = 0 AND suspended = 0 AND id > 2'), 'label' => get_string('stat_users', 'theme_ute')],
            ['value' => $DB->count_records_select('course_modules', 'visible = 1 AND deletioninprogress = 0'), 'label' => get_string('stat_activities', 'theme_ute')],
            ['value' => $DB->count_records('quiz'), 'label' => get_string('stat_quizzes', 'theme_ute')],
        ];
    } catch (\Throwable $e) {
        $stats = [];
    }
    return [
        'herotitle' => format_string(!empty($cfg->herotitle) ? $cfg->herotitle : get_string('default_herotitle', 'theme_ute')),
        'herotext' => format_text(!empty($cfg->herotext) ? $cfg->herotext : get_string('default_herotext', 'theme_ute'), FORMAT_HTML),
        'mycoursesurl' => (new moodle_url('/my/courses.php'))->out(false),
        'allcoursesurl' => (new moodle_url('/course/index.php'))->out(false),
        'calendarurl' => (new moodle_url('/calendar/view.php', ['view' => 'upcoming']))->out(false),
        'loginurl' => (new moodle_url('/login/index.php'))->out(false),
        'loggedin' => isloggedin() && !isguestuser(),
        'firstname' => isloggedin() && !isguestuser() ? $USER->firstname : '',
        'stats' => $stats,
        'hasstats' => !empty($stats),
        'features' => [
            ['icon' => 'fa-book', 'title' => get_string('feat1_title', 'theme_ute'), 'text' => get_string('feat1_text', 'theme_ute')],
            ['icon' => 'fa-pencil-square-o', 'title' => get_string('feat2_title', 'theme_ute'), 'text' => get_string('feat2_text', 'theme_ute')],
            ['icon' => 'fa-comments', 'title' => get_string('feat3_title', 'theme_ute'), 'text' => get_string('feat3_text', 'theme_ute')],
        ],
    ];
}
