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
    $o = html_writer::start_div('local-clo-result');
    $o .= html_writer::start_div('local-clo-head');
    $o .= html_writer::div(html_writer::span(format_float($res->score, 2), 'local-clo-score') .
        html_writer::span(' / ' . format_float($res->maxscore, 0), 'local-clo-max'), 'local-clo-scorebox');
    $o .= html_writer::div(get_string('reference', 'local_clo'), 'local-clo-sub');   // điểm là kết quả của SV; không đánh giá CLO riêng cho từng SV
    $o .= html_writer::end_div();
    if (!empty($d->summary)) {
        $o .= html_writer::tag('h4', get_string('summary', 'local_clo'), ['class' => 'h6 mt-3']);
        $o .= html_writer::tag('p', s($d->summary));
    }
    if (!empty($d->items)) {
        $o .= html_writer::tag('h4', get_string('studyplan', 'local_clo'), ['class' => 'h6 mt-3']);
        $li = '';
        foreach ($d->items as $it) {
            // gợi ý ôn tập theo chương
            $chap = !empty($it->chapter) ? get_string('chapter', 'local_clo', s($it->chapter)) : get_string('chapterunknown', 'local_clo');
            $li .= html_writer::tag('li', html_writer::tag('strong', $chap) . ' ' .
                html_writer::span(get_string('gap', 'local_clo', format_float($it->gap, 1)), 'badge bg-warning text-dark'));
        }
        $o .= html_writer::tag('ol', $li, ['class' => 'local-clo-plan']);
    } else if (!empty($d->study_plan)) {
        $o .= html_writer::tag('p', s($d->study_plan));
    }
    // Gợi ý đọc: câu làm sai → trang/slide cụ thể trong học liệu của khóa học (do hệ thống phân tích tìm theo nội dung câu hỏi)
    if (!empty($d->readings)) {
        $o .= html_writer::tag('h4', get_string('readings', 'local_clo'), ['class' => 'h6 mt-3']);
        $o .= html_writer::tag('p', get_string('readings_help', 'local_clo'), ['class' => 'small text-muted']);
        $li = '';
        foreach ($d->readings as $r) {
            $name = s($r->material);
            if (!empty($r->moodle_cmid)) {      // tệp đã nằm trong khóa học → bấm để mở ngay
                $name = html_writer::link(new moodle_url('/mod/resource/view.php', ['id' => (int)$r->moodle_cmid]), $name,
                    ['target' => '_blank', 'rel' => 'noopener']);
            }
            $where = html_writer::tag('strong', $name) . ' ' .
                html_writer::span(s($r->unit) . ' ' . (int)$r->page, 'badge bg-info text-dark');
            if (!empty($r->heading)) {
                $where .= ' – ' . s($r->heading);
            }
            if (!empty($r->chapter)) {
                $where .= html_writer::span(' (' . s($r->chapter) . ')', 'text-muted small');
            }
            $li .= html_writer::tag('li', $where . html_writer::div(s($r->snippet), 'small text-muted'));
        }
        $o .= html_writer::tag('ol', $li, ['class' => 'local-clo-plan']);
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
        $namesql = \core_user\fields::for_name()->get_sql('u', false, '', '', false)->selects;   // đủ các trường họ tên cho fullname()
        $rows = $DB->get_records_sql("SELECT r.*, u.username, $namesql
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
                implode(' ', array_map(fn($c) => html_writer::span(s($c->code) . ' ' . format_float($c->pct ?? 0, 0) . '%', 'badge bg-light text-dark'),
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
        if (!is_enrolled($context, $u)) {          // chỉ xem SV thuộc khóa học này
            throw new moodle_exception('notenrolledprofile');
        }
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
