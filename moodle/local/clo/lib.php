<?php
defined('MOODLE_INTERNAL') || die();

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

function local_clo_appurl(): string {
    $url = trim((string)get_config('local_clo', 'appurl'));
    return rtrim($url !== '' ? $url : 'http://localhost:8000', '/');
}

function local_clo_search_form(int $courseid, string $q = ''): string {
    return html_writer::tag('form', html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'id', 'value' => $courseid]) .
        html_writer::empty_tag('input', ['type' => 'search', 'name' => 'q', 'value' => $q, 'class' => 'form-control',
            'placeholder' => get_string('searchplaceholder', 'local_clo'), 'maxlength' => 300, 'required' => 'required']) .
        html_writer::tag('button', get_string('search'), ['type' => 'submit', 'class' => 'btn btn-primary']),
        ['method' => 'get', 'action' => (new moodle_url('/local/clo/search.php'))->out(false), 'class' => 'local-clo-searchform']);
}

function local_clo_search_materials(int $courseid, string $q, string &$err): array {
    global $USER, $CFG;
    require_once($CFG->libdir . '/filelib.php');
    try {
        $token = \local_clo\sso::make_search_token($USER, $courseid);
    } catch (\Throwable $e) {
        $err = get_string('searchfail', 'local_clo');
        return [];
    }
    $curl = new curl(['ignoresecurity' => true]);
    $curl->setopt(['CURLOPT_TIMEOUT' => 25, 'CURLOPT_CONNECTTIMEOUT' => 5]);
    $body = $curl->get(local_clo_appurl() . '/api/lms/materials/search', ['token' => $token, 'q' => $q, 'k' => 8]);
    $code = (int)($curl->get_info()['http_code'] ?? 0);
    $data = $code === 200 ? json_decode((string)$body) : null;
    if (!is_array($data)) {
        $err = get_string('searchfail', 'local_clo');
        return [];
    }
    return $data;
}

function local_clo_extend_navigation_course(navigation_node $navigation, stdClass $course, context $context) {
    if ($course->id == SITEID) {
        return;
    }
    if (has_any_capability(['local/clo:viewown', 'local/clo:viewall'], $context)) {
        $navigation->add(get_string('results', 'local_clo'), new moodle_url('/local/clo/results.php', ['id' => $course->id]),
            navigation_node::TYPE_CUSTOM, null, 'local_clo_results', new pix_icon('i/report', ''));
    }
    if (has_any_capability(['local/clo:viewown', 'local/clo:viewall'], $context)) {
        $navigation->add(get_string('searchmaterials', 'local_clo'), new moodle_url('/local/clo/search.php', ['id' => $course->id]),
            navigation_node::TYPE_CUSTOM, null, 'local_clo_search', new pix_icon('i/search', ''));
    }
    if (local_clo_can_launch($course->id)) {
        $navigation->add(get_string('launch', 'local_clo'), new moodle_url('/local/clo/launch.php', ['courseid' => $course->id]),
            navigation_node::TYPE_CUSTOM, null, 'local_clo_launch', new pix_icon('i/stats', ''));
    }
}

function local_clo_file_url(?string $url): ?moodle_url {
    global $CFG;
    $at = strpos((string)$url, '/pluginfile.php/');
    return $at === false ? null : new moodle_url($CFG->wwwroot . substr($url, $at));
}

function local_clo_answers_visible(stdClass $exam, int $userid, int $attemptid = 0): bool {
    global $DB;
    if (empty($exam->quizid)) {
        return true;
    }
    if (!$attemptid) {
        $attemptid = (int)$DB->get_field_sql("SELECT id FROM {quiz_attempts}
                                               WHERE quiz = ? AND userid = ? AND preview = 0 AND state = 'finished'
                                            ORDER BY attempt DESC", [$exam->quizid, $userid], IGNORE_MULTIPLE);
    }
    if (!$attemptid) {
        return false;
    }
    try {
        return (bool)\mod_quiz\quiz_attempt::create($attemptid)->get_display_options(true)->rightanswer;
    } catch (\Throwable $e) {
        return false;
    }
}

function local_clo_explanation_html(stdClass $m): string {
    if (empty($m->explanation->text)) {
        return '';
    }
    $sources = $m->explanation->sources ?? [];
    $parts = preg_split('/\[Nguồn (\d+)\]/u', (string)$m->explanation->text, -1, PREG_SPLIT_DELIM_CAPTURE);
    $html = '';
    foreach ($parts as $i => $part) {
        if ($i % 2 === 0) {
            $html .= s($part);
            continue;
        }
        $src = $sources[(int)$part - 1] ?? null;
        if (!$src) {
            continue;
        }
        $name = get_string('readings_page', 'local_clo', (object)['material' => s($src->material ?? ''), 'page' => (int)($src->page ?? 0)]);
        $url = local_clo_file_url($src->url ?? null);
        $html .= ' (' . ($url ? html_writer::link($url, $name, ['target' => '_blank', 'rel' => 'noopener']) : $name) . ')';
    }
    return html_writer::div(html_writer::div(get_string('explanation', 'local_clo'), 'local-clo-review-title') .
        html_writer::tag('p', trim($html), ['class' => 'mb-1']) .
        html_writer::div(get_string('explanation_note', 'local_clo'), 'small text-muted'), 'local-clo-explanation');
}

function local_clo_reading_pages(array $materials): array {
    $out = [];
    foreach ($materials as $m) {
        foreach ($m->pages ?? [] as $p) {
            $url = local_clo_file_url($p->url ?? null);
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

function local_clo_reading_line(stdClass $p): string {
    $name = get_string('readings_page', 'local_clo', (object)['material' => s($p->material), 'page' => $p->page]);
    $name = $p->url ? html_writer::link($p->url, $name, ['target' => '_blank', 'rel' => 'noopener']) : $name;
    $line = html_writer::tag('strong', $name);
    return $p->heading !== '' ? $line . ' – ' . s($p->heading) : $line;
}

function local_clo_review_readings(int $attemptid): string {
    global $CFG, $DB, $PAGE, $USER;
    $attempt = $DB->get_record('quiz_attempts', ['id' => $attemptid]);
    if (!$attempt || $attempt->preview || $attempt->state !== 'finished') {
        return '';
    }
    if ($attempt->userid != $USER->id && !has_capability('mod/quiz:viewreports', $PAGE->context)) {
        return '';
    }
    $exam = $DB->get_record('local_clo_exam', ['quizid' => $attempt->quiz, 'published' => 1], 'id, quizid', IGNORE_MULTIPLE);
    $res = $exam ? $DB->get_record('local_clo_result', ['cloexamid' => $exam->id, 'userid' => $attempt->userid]) : null;
    $rdata = $res ? json_decode($res->data ?? '{}') : null;
    $materials = $rdata->materials ?? [];
    if (!$materials) {
        return '';
    }
    require_once($CFG->dirroot . '/question/engine/lib.php');
    $quba = question_engine::load_questions_usage_by_activity($attempt->uniqueid);
    $byidnumber = [];
    foreach ($quba->get_slots() as $slot) {
        $byidnumber[(string)$quba->get_question($slot, false)->idnumber] = $slot;
    }
    $showwhy = empty($rdata->hide_answers) && local_clo_answers_visible($exam, (int)$attempt->userid, (int)$attempt->id);
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
            html_writer::tag('ul', $li) . ($showwhy ? local_clo_explanation_html($m) : ''), 'local-clo-review-readings',
            ['hidden' => 'hidden', 'data-local-clo-que' => $qa->get_outer_question_div_unique_id()]);
    }
    if ($o === '') {
        return '';
    }
    return $o . html_writer::script("document.querySelectorAll('[data-local-clo-que]').forEach(function(el) {
        var que = document.getElementById(el.getAttribute('data-local-clo-que'));
        var content = que && que.querySelector('.content');
        if (content) { content.appendChild(el); el.hidden = false; } else { el.remove(); }
    });");
}
