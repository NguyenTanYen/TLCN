<?php
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

function local_clo_card(string $title, string $body, string $extra = ''): string {
    return html_writer::div(html_writer::tag('h4', $title, ['class' => 'local-clo-card-title']) . $body, 'local-clo-card ' . $extra);
}

function local_clo_stat(string $label, string $value, string $sub = '', string $tone = ''): string {
    return html_writer::div(html_writer::div($label, 'local-clo-stat-l') . html_writer::div($value, 'local-clo-stat-v') .
        ($sub !== '' ? html_writer::div($sub, 'local-clo-stat-s') : ''), 'local-clo-stat ' . $tone);
}

function local_clo_render_result(stdClass $exam, ?stdClass $res): string {
    global $DB;
    if (!$exam->published) {
        return html_writer::div(get_string('reserved', 'local_clo'), 'alert alert-warning mb-0');
    }
    if (!$res || $res->status === 'absent') {
        return html_writer::div(get_string('insufficient', 'local_clo'), 'alert alert-secondary mb-0');
    }
    $d = json_decode($res->data ?? '{}') ?: new stdClass();
    $clos = $d->clos ?? [];
    $chapters = $d->chapters ?? [];
    $o = html_writer::start_div('local-clo-result');

    $score = (float)$res->score;
    $max = (float)$res->maxscore;
    $stats = local_clo_stat(get_string('scorelabel', 'local_clo'), format_float($score, 2) . ' / ' . format_float($max, 0), '',
        $max > 0 && $score >= $max / 2 ? 'good' : 'bad');
    if (isset($d->class_mean)) {
        $stats .= local_clo_stat(get_string('classavg', 'local_clo'), format_float($d->class_mean, 2), get_string('classmean_sub', 'local_clo'));
    }
    if (!empty($d->counts)) {
        $stats .= local_clo_stat(get_string('answers', 'local_clo'), get_string('n_correct', 'local_clo', (int)$d->counts->correct),
            get_string('n_wrongblank', 'local_clo', (object)['w' => (int)$d->counts->wrong, 'b' => (int)$d->counts->blank]));
    }
    if ($clos) {
        $ok = count(array_filter($clos, fn($c) => !empty($c->achieved)));
        $stats .= local_clo_stat(get_string('clo', 'local_clo'), $ok . '/' . count($clos), get_string('clos_short', 'local_clo'),
            $ok == count($clos) ? 'good' : 'bad');
    }
    $o .= html_writer::div($stats, 'local-clo-stats');

    $views = [];
    if (count($clos) >= 3) {
        $views['clo'] = ['label' => get_string('byclo', 'local_clo'), 'svg' => \local_clo\radar::svg($clos)];
    }
    if (count($chapters) >= 3) {
        $rows = array_map(fn($c) => (object)['code' => $c->name, 'pct' => $c->pct], $chapters);
        $views['chap'] = ['label' => get_string('bychapter', 'local_clo'), 'svg' => \local_clo\radar::svg($rows)];
    }
    if ($views) {
        $id = 'localclo' . $exam->id;
        $tabs = '';
        $panes = '';
        $first = true;
        foreach ($views as $k => $v) {
            $tabs .= html_writer::tag('button', $v['label'], ['type' => 'button', 'class' => 'local-clo-tab' . ($first ? ' on' : ''),
                'data-pane' => "$id-$k"]);
            $panes .= html_writer::div($v['svg'], 'local-clo-pane', ['id' => "$id-$k"] + ($first ? [] : ['hidden' => 'hidden']));
            $first = false;
        }
        $body = html_writer::tag('p', get_string('radar_help', 'local_clo'), ['class' => 'small text-muted']);
        $body .= html_writer::div($tabs, 'local-clo-tabs') . html_writer::div($panes, 'local-clo-chart');
        $body .= html_writer::script("document.querySelectorAll('#$id-wrap .local-clo-tab').forEach(function(b){b.addEventListener('click',function(){" .
            "document.querySelectorAll('#$id-wrap .local-clo-tab').forEach(function(x){x.classList.toggle('on',x===b)});" .
            "document.querySelectorAll('#$id-wrap .local-clo-pane').forEach(function(p){p.hidden=p.id!==b.dataset.pane})})});");
        $o .= html_writer::div(local_clo_card(get_string('radar', 'local_clo'), $body), '', ['id' => "$id-wrap"]);
    }
    if ($clos) {
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
        $o .= local_clo_card(get_string('closresult', 'local_clo'), html_writer::div(html_writer::table($table), 'local-clo-tablewrap'));
    }
    if ($chapters) {
        $t = new html_table();
        $t->attributes['class'] = 'generaltable local-clo-table';
        $t->head = [get_string('chaptercol', 'local_clo'), get_string('nquestions', 'local_clo'), get_string('ncorrect', 'local_clo'),
            get_string('pctcorrect', 'local_clo'), get_string('comment', 'local_clo')];
        foreach ($chapters as $c) {
            $badge = $c->pct < 50 ? html_writer::span(get_string('review_now', 'local_clo'), 'badge bg-danger') :
                ($c->pct < 70 ? html_writer::span(get_string('review_more', 'local_clo'), 'badge bg-warning text-dark') :
                html_writer::span(get_string('good', 'local_clo'), 'badge bg-success'));
            $t->data[] = [html_writer::tag('strong', s($c->name)), (int)$c->n, (int)$c->ok, (int)$c->pct . '%', $badge];
        }
        $o .= local_clo_card(get_string('chapterresult', 'local_clo'), html_writer::div(html_writer::table($t), 'local-clo-tablewrap'));
    }

    $plan = '';
    if (!empty($d->summary)) {
        $plan .= html_writer::tag('p', html_writer::tag('strong', get_string('summary', 'local_clo') . ': ') . s($d->summary));
    }
    if (!empty($d->items)) {
        $groups = [];
        foreach ($d->items as $it) {
            $groups[(int)$it->priority][] = $it;
        }
        ksort($groups);
        $li = '';
        foreach ($groups as $pr => $its) {
            $inner = '';
            foreach ($its as $it) {
                $chap = !empty($it->chapter) ? s($it->chapter) : get_string('chapterunknown', 'local_clo');
                $inner .= html_writer::tag('li', get_string('reviewagain', 'local_clo') . ' ' . html_writer::tag('strong', $chap));
            }
            $li .= html_writer::tag('li', html_writer::span(get_string('priority', 'local_clo', $pr), 'badge bg-warning text-dark') . ' ' .
                html_writer::span(get_string('gap', 'local_clo', format_float($its[0]->gap, 1)), 'small text-muted') .
                html_writer::tag('ul', $inner));
        }
        $plan .= html_writer::tag('ol', $li, ['class' => 'local-clo-plan']);
    } else if (!empty($d->study_plan)) {
        $plan .= html_writer::tag('p', s($d->study_plan));
    }
    if ($plan !== '') {
        $o .= local_clo_card(get_string('studyplan', 'local_clo'), $plan);
    }

    $attemptid = 0;
    if (!empty($exam->quizid)) {
        $attemptid = (int)$DB->get_field_sql("SELECT id FROM {quiz_attempts}
                                               WHERE quiz = ? AND userid = ? AND preview = 0 AND state = 'finished'
                                            ORDER BY attempt DESC", [$exam->quizid, $res->userid], IGNORE_MULTIPLE);
    }
    $wrongrows = [];
    if ($attemptid) {
        $uniqueid = (int)$DB->get_field('quiz_attempts', 'uniqueid', ['id' => $attemptid]);
        $frac = [];
        $steps = $DB->get_records_sql("SELECT s.id, s.questionattemptid, s.fraction
                                         FROM {question_attempt_steps} s
                                         JOIN {question_attempts} qa ON qa.id = s.questionattemptid
                                        WHERE qa.questionusageid = ? AND s.fraction IS NOT NULL
                                     ORDER BY s.sequencenumber", [$uniqueid]);
        foreach ($steps as $st) {
            $frac[$st->questionattemptid] = (float)$st->fraction;
        }
        foreach ($DB->get_records('question_attempts', ['questionusageid' => $uniqueid], 'slot') as $qa) {
            if (isset($frac[$qa->id]) && $frac[$qa->id] >= 0.999) {
                continue;
            }
            $wrongrows[(int)$qa->slot] = [trim((string)$qa->questionsummary), trim((string)$qa->responsesummary),
                trim((string)$qa->rightanswer)];
        }
    }
    $mats = $d->materials ?? [];
    $bynum = [];
    foreach ($mats as $m) {
        $bynum[(int)$m->question] = $m;
    }
    $nums = $wrongrows ? array_keys($wrongrows) : array_values(array_unique(array_map('intval', $d->wrong ?? [])));
    sort($nums);
    if ($nums) {
        $t = new html_table();
        $t->attributes['class'] = 'generaltable local-clo-table local-clo-wrong';
        $t->head = [get_string('wrongquestion_short', 'local_clo'), get_string('questiontext', 'local_clo'),
            get_string('youranswer', 'local_clo'), get_string('rightanswer', 'local_clo'), get_string('readpages', 'local_clo')];
        foreach ($nums as $n) {
            $w = $wrongrows[$n] ?? ['', '', ''];
            $label = get_string('question_no', 'local_clo', $n);
            if ($attemptid) {
                $label = html_writer::link(new moodle_url('/mod/quiz/review.php', ['attempt' => $attemptid, 'page' => $n - 1],
                    'question-' . $attemptid . '-' . $n), $label);
            }
            $pages = '';
            if (isset($bynum[$n])) {
                foreach (local_clo_reading_pages([$bynum[$n]]) as $p) {
                    $pages .= html_writer::tag('li', local_clo_reading_line($p));
                }
            }
            $t->data[] = [html_writer::tag('strong', $label, ['class' => 'text-nowrap']), s(shorten_text($w[0], 200)),
                $w[1] !== '' ? s($w[1]) : html_writer::span(get_string('notanswered', 'local_clo'), 'text-muted'),
                html_writer::span(s($w[2]), 'text-success'),
                $pages !== '' ? html_writer::tag('ul', $pages, ['class' => 'mb-0 ps-3']) : '–'];
        }
        $body = html_writer::tag('p', get_string('readings_help', 'local_clo'), ['class' => 'small text-muted']) .
            html_writer::div(html_writer::table($t), 'local-clo-tablewrap');
        if ($attemptid) {
            $body .= html_writer::div(html_writer::link(new moodle_url('/mod/quiz/review.php', ['attempt' => $attemptid]),
                get_string('reviewattempt', 'local_clo'), ['class' => 'btn btn-primary']), 'mt-2');
        }
        $o .= local_clo_card(get_string('wronglist', 'local_clo') . ' (' . count($nums) . ')', $body);
        if (!$mats) {
            $mods = '';
            foreach (get_fast_modinfo($exam->courseid)->get_cms() as $cm) {
                if (in_array($cm->modname, ['resource', 'url', 'page', 'folder', 'book']) && $cm->uservisible && $cm->url) {
                    $mods .= html_writer::tag('li', html_writer::link($cm->url, format_string($cm->name)));
                }
            }
            if ($mods !== '') {
                $o .= local_clo_card(get_string('coursematerials', 'local_clo'),
                    html_writer::tag('p', get_string('coursematerials_help', 'local_clo'), ['class' => 'small text-muted']) .
                    html_writer::tag('ul', $mods));
            }
        }
    }
    $ans = $d->answers ?? [];
    if ($ans) {
        usort($ans, fn($x, $y) => (int)$x->no <=> (int)$y->no);
        $icons = ['correct' => ['✓', 'text-success', 'ans_correct'], 'wrong' => ['✗', 'text-danger', 'ans_wrong'],
            'blank' => ['–', 'text-muted', 'ans_blank']];
        $cnt = ['correct' => 0, 'wrong' => 0, 'blank' => 0];
        $t = new html_table();
        $t->attributes['class'] = 'generaltable local-clo-table local-clo-answers';
        $t->head = [get_string('wrongquestion_short', 'local_clo'), get_string('chaptercol', 'local_clo'), get_string('clo', 'local_clo'),
            get_string('level', 'local_clo'), get_string('result', 'local_clo'), get_string('score', 'local_clo'),
            get_string('classcorrect', 'local_clo')];
        foreach ($ans as $x) {
            $cnt[$x->result]++;
            $label = get_string('question_no', 'local_clo', (int)$x->no);
            if ($attemptid) {
                $label = html_writer::link(new moodle_url('/mod/quiz/review.php', ['attempt' => $attemptid, 'page' => (int)$x->no - 1],
                    'question-' . $attemptid . '-' . (int)$x->no), $label);
            }
            [$ic, $cls, $str] = $icons[$x->result] ?? $icons['blank'];
            $row = new html_table_row([html_writer::tag('strong', $label), s($x->chapter ?? '–'), s($x->clos ?? '–'), s($x->bloom ?? '–'),
                html_writer::span($ic . ' ' . get_string($str, 'local_clo'), $cls),
                format_float($x->score, 2) . '/' . format_float($x->points, 2), isset($x->p) ? (int)$x->p . '%' : '–']);
            $row->attributes['data-result'] = $x->result;
            $t->data[] = $row;
        }
        $id = 'localcloans' . $exam->id;
        $btns = html_writer::tag('button', get_string('all') . ' (' . count($ans) . ')', ['type' => 'button',
            'class' => 'local-clo-tab on', 'data-f' => 'all']);
        foreach (['wrong', 'blank', 'correct'] as $k) {
            $btns .= html_writer::tag('button', get_string('ans_' . $k, 'local_clo') . ' (' . $cnt[$k] . ')',
                ['type' => 'button', 'class' => 'local-clo-tab', 'data-f' => $k]);
        }
        $body = html_writer::div($btns, 'local-clo-tabs justify-content-start') .
            html_writer::div(html_writer::table($t), 'local-clo-tablewrap');
        $body .= html_writer::script("(function(){var w=document.getElementById('$id');if(!w){return;}" .
            "w.querySelectorAll('.local-clo-tab').forEach(function(b){b.addEventListener('click',function(){" .
            "w.querySelectorAll('.local-clo-tab').forEach(function(x){x.classList.toggle('on',x===b)});" .
            "w.querySelectorAll('tbody tr').forEach(function(r){r.hidden=b.dataset.f!=='all'&&r.dataset.result!==b.dataset.f})})});})();");
        $o .= html_writer::tag('details', html_writer::tag('summary', get_string('answerdetail', 'local_clo'),
            ['class' => 'local-clo-summary']) . html_writer::div($body, '', ['id' => $id]), ['class' => 'local-clo-card']);
    }
    return $o . html_writer::end_div();
}

echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('results', 'local_clo'));
if ($canall && local_clo_can_launch($course->id)) {
    echo html_writer::div(html_writer::link(new moodle_url('/local/clo/launch.php', ['courseid' => $course->id]),
        get_string('launch', 'local_clo'), ['class' => 'btn btn-primary']), 'mb-3');
}
echo html_writer::div(html_writer::tag('h4', get_string('searchmaterials', 'local_clo'), ['class' => 'local-clo-card-title']) .
    local_clo_search_form($course->id), 'local-clo-card');
if (!$exams) {
    echo $OUTPUT->notification(get_string('noexams', 'local_clo'), 'info', false);
    echo $OUTPUT->footer();
    exit;
}

if ($canall && !$userid) {
    foreach ($exams as $exam) {
        $namesql = \core_user\fields::for_name()->get_sql('u', false, '', '', false)->selects;
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
        if (!is_enrolled($context, $u)) {
            throw new moodle_exception('notenrolledprofile');
        }
        echo html_writer::tag('p', html_writer::link(new moodle_url('/local/clo/results.php', ['id' => $course->id]), '← ' .
            get_string('back')) . ' · ' . html_writer::tag('strong', fullname($u) . ' (' . s($u->username) . ')'));
    }
    foreach ($exams as $exam) {
        $res = $DB->get_record('local_clo_result', ['cloexamid' => $exam->id, 'userid' => $userid]);
        if ($canall) {
            $exam = clone($exam); $exam->published = 1;
        }
        echo html_writer::start_div('card mb-4');
        echo html_writer::div(html_writer::tag('h3', format_string($exam->title), ['class' => 'h5 mb-0']), 'card-header');
        echo html_writer::div(local_clo_render_result($exam, $res ?: null), 'card-body');
        echo html_writer::end_div();
    }
}
echo $OUTPUT->footer();
