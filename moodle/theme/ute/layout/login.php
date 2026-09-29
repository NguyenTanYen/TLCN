<?php
defined('MOODLE_INTERNAL') || die();
// Trang đăng nhập hai cột: giới thiệu hệ thống (trái) – biểu mẫu đăng nhập Moodle (phải).
$cfg = get_config('theme_ute');
$templatecontext = [
    'sitename' => format_string($SITE->fullname, true, ['context' => context_course::instance(SITEID), 'escape' => false]),
    'shortname' => format_string($SITE->shortname, true, ['context' => context_course::instance(SITEID), 'escape' => false]),
    'output' => $OUTPUT,
    'bodyattributes' => $OUTPUT->body_attributes(['ute-login']),
    'logintitle' => format_string(!empty($cfg->logintitle) ? $cfg->logintitle : get_string('default_logintitle', 'theme_ute')),
    'bullets' => [
        ['text' => get_string('login_b1', 'theme_ute')],
        ['text' => get_string('login_b2', 'theme_ute')],
        ['text' => get_string('login_b3', 'theme_ute')],
    ],
    'year' => date('Y'),
];
echo $OUTPUT->render_from_template('theme_ute/login', $templatecontext);
