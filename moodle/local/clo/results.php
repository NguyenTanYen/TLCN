<?php
// UC-05 trên Moodle: sinh viên xem kết quả phân tích năng lực theo CLO (radar so với ngưỡng θk),
// nhận định và các chương cần ôn. Giảng viên xem được kết quả của cả lớp.
require_once(__DIR__ . '/../../config.php');
require_once(__DIR__ . '/lib.php');

$courseid = required_param('id', PARAM_INT);
$userid = optional_param('userid', 0, PARAM_INT);
$course = get_course($courseid);
require_login($course);
$context = context_course::instance($course->id);
$canall = has_capability('local/clo:viewall', $context);
if (!$canall) {
    require_capability('local/clo:viewown', $context);
    $userid = $USER->id;
}

$PAGE->set_url(new moodle_url('/local/clo/results.php', ['id' => $course->id, 'userid' => $userid ?: null]));
$PAGE->set_context($context);
$PAGE->set_pagelayout('incourse');
$PAGE->set_title(get_string('results', 'local_clo') . ' – ' . format_string($course->shortname));
$PAGE->set_heading(format_string($course->fullname));
$PAGE->navbar->add(get_string('results', 'local_clo'), new moodle_url('/local/clo/results.php', ['id' => $course->id]));

$exams = $DB->get_records('local_clo_exam', ['courseid' => $course->id], 'timecreated DESC, id DESC');

/** Khối kết quả của một SV cho một bài kiểm tra. */
function local_clo_render_result(stdClass $exam, ?stdClass $res): string {
    if (!$exam->published) {                               // E1 – GV chưa công bố
        return html_writer::div(get_string('reserved', 'local_clo'), 'alert alert-warning mb-0');
    }
    if (!$res || $res->status === 'absent') {              // E2 – không đủ bằng chứng
        return html_writer::div(get_string('insufficient', 'local_clo'), 'alert alert-secondary mb-0');
    }
    $d = json_decode($res->data ?? '{}') ?: new stdClass();
    $clos = $d->clos ?? [];
    $o = html_writer::start_div('local-clo-result');
    $o .= html_writer::start_div('local-clo-head');
    $o .= html_writer::div(html_writer::span(format_float($res->score, 2), 'local-clo-score') .
        html_writer::span(' / ' . format_float($res->maxscore, 0), 'local-clo-max'), 'local-clo-scorebox');
    $n = count($clos); $ok = count(array_filter($clos, fn($c) => !empty($c->achieved)));
    $o .= html_writer::div(get_string('clos_achieved', 'local_clo', (object)['ok' => $ok, 'n' => $n]), 'local-clo-sub');
    $o .= html_writer::end_div();
    $o .= html_writer::start_div('local-clo-grid');
    $radar = \local_clo\radar::svg($clos);
    if ($radar) {
        $legend = html_writer::tag('ul',
            html_writer::tag('li', html_writer::span('', 'sw me') . get_string('legend_me', 'local_clo')) .
            html_writer::tag('li', html_writer::span('', 'sw target') . get_string('legend_target', 'local_clo')) .
            html_writer::tag('li', html_writer::span('', 'sw avg') . get_string('legend_avg', 'local_clo')),
            ['class' => 'local-clo-legend']);
        $o .= html_writer::div($radar . $legend, 'local-clo-chart');
    }
    $table = new html_table();
    $table->attributes['class'] = 'generaltable local-clo-table';
    $table->head = [get_string('clo', 'local_clo'), get_string('yourscore', 'local_clo'), get_string('target', 'local_clo'),
        get_string('classavg', 'local_clo'), get_string('status')];
    foreach ($clos as $c) {
        $table->data[] = [
            html_writer::tag('strong', s($c->code)) . html_writer::div(s($c->description ?? ''), 'small text-muted'),
            format_float($c->pct, 1) . '%', format_float($c->threshold, 0) . '%',
            isset($c->class_avg) ? format_float($c->class_avg, 1) . '%' : '–',
            !empty($c->achieved) ? html_writer::span(get_string('achieved', 'local_clo'), 'badge bg-success') :
                html_writer::span(get_string('notachieved', 'local_clo'), 'badge bg-danger'),
        ];
    }
    $o .= html_writer::div(html_writer::table($table), 'local-clo-tablewrap');
    $o .= html_writer::end_div();
    if (!empty($d->summary)) {
        $o .= html_writer::tag('h4', get_string('summary', 'local_clo'), ['class' => 'h6 mt-3']);
        $o .= html_writer::tag('p', s($d->summary));
    }
    if (!empty($d->items)) {
        $o .= html_writer::tag('h4', get_string('studyplan', 'local_clo'), ['class' => 'h6 mt-3']);
        $li = '';
        foreach ($d->items as $it) {
            $chap = !empty($it->chapter) ? get_string('chapter', 'local_clo', s($it->chapter)) : '';
            $li .= html_writer::tag('li', html_writer::tag('strong', s($it->clo)) . ' – ' . s($it->clo_description ?? '') .
                ($chap ? html_writer::div($chap, 'small') : '') .
                html_writer::span(get_string('gap', 'local_clo', format_float($it->gap, 1)), 'badge bg-warning text-dark ms-1'));
        }
        $o .= html_writer::tag('ol', $li, ['class' => 'local-clo-plan']);
    } else if (!empty($d->study_plan)) {
        $o .= html_writer::tag('p', s($d->study_plan));
    }
    return $o . html_writer::end_div();
}

echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('results', 'local_clo'));
if ($canall && local_clo_can_launch($course->id)) {
    echo html_writer::div(html_writer::link(new moodle_url('/local/clo/launch.php', ['courseid' => $course->id]),
        get_string('launch', 'local_clo'), ['class' => 'btn btn-primary']), 'mb-3');
}
if (!$exams) {
    echo $OUTPUT->notification(get_string('noexams', 'local_clo'), 'info', false);
    echo $OUTPUT->footer();
    exit;
}

if ($canall && !$userid) {
    // Giảng viên: tổng quan từng bài kiểm tra.
    foreach ($exams as $exam) {
        $rows = $DB->get_records_sql("SELECT r.*, u.firstname, u.lastname, u.username
                                        FROM {local_clo_result} r JOIN {user} u ON u.id = r.userid
                                       WHERE r.cloexamid = ? ORDER BY u.username", [$exam->id]);
        echo html_writer::start_div('card mb-4');
        echo html_writer::div(html_writer::tag('h3', format_string($exam->title), ['class' => 'h5 mb-0']) .
            ($exam->published ? html_writer::span(get_string('published', 'local_clo'), 'badge bg-success') :
                html_writer::span(get_string('notpublished', 'local_clo'), 'badge bg-secondary')),
            'card-header d-flex justify-content-between align-items-center');
        $t = new html_table();
        $t->attributes['class'] = 'generaltable mb-0';
        $t->head = [get_string('username'), get_string('fullname'), get_string('score', 'local_clo'), get_string('clos', 'local_clo'), ''];
        foreach ($rows as $r) {
            $d = json_decode($r->data ?? '{}');
            $cl = $r->status === 'absent' ? html_writer::span(get_string('absent', 'local_clo'), 'badge bg-secondary') :
                implode(' ', array_map(fn($c) => html_writer::span(s($c->code), 'badge ' . (!empty($c->achieved) ? 'bg-success' : 'bg-danger')),
                    $d->clos ?? []));
            $t->data[] = [s($r->username), fullname($r), $r->status === 'absent' ? '–' : format_float($r->score, 2), $cl,
                html_writer::link(new moodle_url('/local/clo/results.php', ['id' => $course->id, 'userid' => $r->userid]),
                    get_string('view'))];
        }
        echo html_writer::div($rows ? html_writer::table($t) : get_string('noresults', 'local_clo'), 'card-body p-0 p-md-2');
        echo html_writer::end_div();
    }
} else {
    if ($userid != $USER->id) {
        $u = core_user::get_user($userid, '*', MUST_EXIST);
        echo html_writer::tag('p', html_writer::link(new moodle_url('/local/clo/results.php', ['id' => $course->id]), '← ' .
            get_string('back')) . ' · ' . html_writer::tag('strong', fullname($u) . ' (' . s($u->username) . ')'));
    }
    foreach ($exams as $exam) {
        $res = $DB->get_record('local_clo_result', ['cloexamid' => $exam->id, 'userid' => $userid]);
        if ($canall) {
            $exam = clone($exam); $exam->published = 1;   // GV luôn xem được để rà soát trước khi công bố
        }
        echo html_writer::start_div('card mb-4');
        echo html_writer::div(html_writer::tag('h3', format_string($exam->title), ['class' => 'h5 mb-0']), 'card-header');
        echo html_writer::div(local_clo_render_result($exam, $res ?: null), 'card-body');
        echo html_writer::end_div();
    }
}
echo $OUTPUT->footer();
