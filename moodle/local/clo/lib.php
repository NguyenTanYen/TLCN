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

/**
 * Gợi ý đọc gửi từ hệ thống phân tích ([{question, pages: [{material, page, heading, url}]}]) gom theo trang.
 * Liên kết chỉ nhận tệp của CHÍNH Moodle này (pluginfile.php) – địa chỉ Moodle mà hệ thống phân tích dùng có thể khác
 * wwwroot (localhost / 127.0.0.1...), nên dựng lại từ phần /pluginfile.php/...; liên kết khác bị bỏ, chỉ hiện tên.
 */
function local_clo_reading_pages(array $materials): array {
    global $CFG;
    $out = [];
    foreach ($materials as $m) {
        foreach ($m->pages ?? [] as $p) {
            $url = null;
            $at = strpos((string)($p->url ?? ''), '/pluginfile.php/');
            if ($at !== false) {
                $url = new moodle_url($CFG->wwwroot . substr($p->url, $at));
            }
            // khóa gom: liên kết tệp + trang (hai học liệu có thể trùng TÊN – tên lấy từ hoạt động Moodle);
            // không có liên kết thì mới dùng tên + trang
            $key = $url ? $url->out(false) : ($p->material ?? '') . '#' . (int)($p->page ?? 0);
            if (!isset($out[$key])) {
                $out[$key] = (object)['material' => (string)($p->material ?? ''), 'page' => (int)($p->page ?? 0),
                    'heading' => (string)($p->heading ?? ''), 'url' => $url, 'questions' => [], 'first' => count($out)];
            }
            $out[$key]->questions[] = (int)$m->question;
        }
    }
    foreach ($out as $p) {
        $p->questions = array_values(array_unique($p->questions));
        sort($p->questions);
    }
    usort($out, fn($a, $b) => [count($b->questions), $a->first] <=> [count($a->questions), $b->first]);
    return $out;
}

/** Một dòng gợi ý đọc: liên kết "tên học liệu – trang N" và đề mục của trang. */
function local_clo_reading_line(stdClass $p): string {
    $name = get_string('readings_page', 'local_clo', (object)['material' => s($p->material), 'page' => $p->page]);
    $name = $p->url ? html_writer::link($p->url, $name, ['target' => '_blank', 'rel' => 'noopener']) : $name;
    $line = html_writer::tag('strong', $name);
    return $p->heading !== '' ? $line . ' – ' . s($p->heading) : $line;
}

/**
 * Gợi ý đọc đặt ngay dưới từng câu làm sai ở trang xem lại bài Quiz (mod/quiz/review.php) của một lượt làm. Khớp câu
 * theo idnumber QB-n (giữ đúng khi GV đổi thứ tự câu trong Quiz); kết quả gửi từ bản cũ chưa có question_id thì theo số
 * câu = slot. Lượt khác lượt đã phân tích có thể đúng câu này nên xét lại điểm của câu trong chính lượt đang xem.
 */
function local_clo_review_readings(int $attemptid): string {
    global $CFG, $DB, $PAGE, $USER;
    $attempt = $DB->get_record('quiz_attempts', ['id' => $attemptid]);
    if (!$attempt || $attempt->preview || $attempt->state !== 'finished') {
        return '';
    }
    if ($attempt->userid != $USER->id && !has_capability('mod/quiz:viewreports', $PAGE->context)) {
        return '';
    }
    $exam = $DB->get_record('local_clo_exam', ['quizid' => $attempt->quiz, 'published' => 1], 'id', IGNORE_MULTIPLE);
    $res = $exam ? $DB->get_record('local_clo_result', ['cloexamid' => $exam->id, 'userid' => $attempt->userid]) : null;
    $materials = $res ? (json_decode($res->data ?? '{}')->materials ?? []) : [];
    if (!$materials) {
        return '';
    }
    require_once($CFG->dirroot . '/question/engine/lib.php');
    $quba = question_engine::load_questions_usage_by_activity($attempt->uniqueid);
    $byidnumber = [];
    foreach ($quba->get_slots() as $slot) {
        $byidnumber[(string)$quba->get_question($slot, false)->idnumber] = $slot;
    }
    $o = '';
    foreach ($materials as $m) {
        $slot = isset($m->question_id) ? ($byidnumber['QB-' . (int)$m->question_id] ?? 0) : (int)$m->question;
        if (!in_array($slot, $quba->get_slots())) {
            continue;
        }
        $qa = $quba->get_question_attempt($slot);
        $fraction = $qa->get_fraction();
        $pages = local_clo_reading_pages([$m]);
        if (!$pages || ($fraction !== null && $fraction >= 0.9999)) {
            continue;
        }
        $li = '';
        foreach ($pages as $p) {
            $li .= html_writer::tag('li', local_clo_reading_line($p));
        }
        $o .= html_writer::div(html_writer::div(get_string('review_readings', 'local_clo'), 'local-clo-review-title') .
            html_writer::tag('ul', $li), 'local-clo-review-readings',
            ['hidden' => 'hidden', 'data-local-clo-que' => $qa->get_outer_question_div_unique_id()]);
    }
    if ($o === '') {
        return '';
    }
    // Khối dựng ở cuối trang rồi chuyển vào đúng câu; câu không có trên trang này (Quiz 1 câu/trang) thì bỏ.
    return $o . html_writer::script("document.querySelectorAll('[data-local-clo-que]').forEach(function(el) {
        var que = document.getElementById(el.getAttribute('data-local-clo-que'));
        var content = que && que.querySelector('.content');
        if (content) { content.appendChild(el); el.hidden = false; } else { el.remove(); }
    });");
}
