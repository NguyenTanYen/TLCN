<?php
define('CLI_SCRIPT', true);
$opts = getopt('', ['spec:', 'xml:', 'moodle:']);
require($opts['moodle'] . '/config.php');
require_once($CFG->libdir . '/testing/generator/lib.php');
require_once($CFG->dirroot . '/mod/quiz/locallib.php');
require_once($CFG->dirroot . '/question/format/xml/format.php');
require_once($CFG->dirroot . '/question/editlib.php');

use mod_quiz\quiz_attempt;
use mod_quiz\quiz_settings;

$spec = json_decode(file_get_contents($opts['spec']), true);
\core\session\manager::set_user(get_admin());
$gen = new testing_data_generator();

$course = $DB->get_record('course', ['shortname' => $spec['course']['shortname']]);
if ($course) { delete_course($course, false); }
$course = $gen->create_course(['fullname' => $spec['course']['fullname'], 'shortname' => $spec['course']['shortname']]);
$users = [];
foreach (array_merge($spec['students'], [$spec['teacher']]) as $u) {
    $rec = $DB->get_record('user', ['username' => $u['username']]) ?: $gen->create_user([
        'username' => $u['username'], 'idnumber' => $u['idnumber'] ?? '', 'firstname' => $u['firstname'],
        'lastname' => $u['lastname'], 'email' => $u['username'] . '@example.com',
        'password' => $u['password'] ?? 'Sv@123456']);
    if (!empty($u['password'])) {
        update_internal_user_password($rec, $u['password']);
    }
    $users[$u['username']] = $rec;
    $gen->enrol_user($rec->id, $course->id, $u['role'] ?? 'student');
}

$ctx = context_course::instance($course->id);
$contexts = new core_question\local\bank\question_edit_contexts($ctx);
$defaultcat = question_make_default_categories($contexts->all());
$qformat = new qformat_xml();
$qformat->setCategory($defaultcat);
$qformat->setContexts($contexts->having_one_edit_tab_cap('import'));
$qformat->setCourse($course);
$qformat->setFilename($opts['xml']);
$qformat->setRealfilename(basename($opts['xml']));
$qformat->setMatchgrades('error');
$qformat->setCatfromfile(true);
$qformat->setContextfromfile(true);
$qformat->setStoponerror(true);
ob_start();
$ok = $qformat->importpreprocess() && $qformat->importprocess() && $qformat->importpostprocess();
$log = ob_get_clean();
if (!$ok) { fwrite(STDERR, $log); exit(1); }

$quizgen = $gen->get_plugin_generator('mod_quiz');
$quiz = $quizgen->create_instance(['course' => $course->id, 'name' => $spec['quiz']['name'], 'grade' => $spec['quiz']['grade'],
    'sumgrades' => 0, 'shuffleanswers' => 1, 'preferredbehaviour' => 'deferredfeedback', 'attempts' => 0, 'questionsperpage' => 1,
    'timelimit' => (int)($spec['quiz']['timelimit'] ?? 0), 'overduehandling' => 'autosubmit']);
foreach ($qformat->questionids as $qid) {
    $maxmark = $DB->get_field('question', 'defaultmark', ['id' => $qid]);
    quiz_add_quiz_question($qid, $quiz, 0, $maxmark);
}
$quizobj = quiz_settings::create($quiz->id);
\mod_quiz\grade_calculator::create($quizobj)->recompute_quiz_sumgrades();

$t0 = time();
$made = 0;
function take_attempt($quizid, $user, $answers, $time, $timing = null) {
    global $DB;
    \core\session\manager::set_user($user);
    $quizobj = quiz_settings::create($quizid, $user->id);
    $prev = quiz_get_user_attempts($quizid, $user->id, 'all', true);
    $last = $prev ? end($prev) : null;
    $attempt = quiz_prepare_and_start_new_attempt($quizobj, $last ? $last->attempt + 1 : 1, $last);
    $tstart = $time;
    if ($timing) {
        $tstart = time() - (int)$timing['finish'] - 120;
        $DB->set_field('quiz_attempts', 'timestart', $tstart, ['id' => $attempt->id]);
    }
    $ao = quiz_attempt::create($attempt->id);
    $post = []; $each = [];
    foreach ($ao->get_slots() as $slot) {
        $qa = $ao->get_question_attempt($slot);
        $q = $qa->get_question();
        $pos = $answers[$q->idnumber] ?? null;
        if ($pos === null) { continue; }
        $ids = array_keys($q->answers); sort($ids);
        $field = array_search($ids[$pos], $q->get_order($qa));
        $one = [$qa->get_control_field_name('sequencecheck') => (string)$qa->get_sequence_check_count(),
                $qa->get_qt_field_name('answer') => (string)$field];
        $post += $one;
        $each[] = [(int)($timing['offsets'][$q->idnumber] ?? 0), $slot, $one];
    }
    if (!$timing) {
        $ao->process_submitted_actions($time, false, $post);
        $ao->process_finish(max($time, time()), false);
        return $attempt->id;
    }
    usort($each, fn($a, $b) => $a[0] <=> $b[0]);
    foreach ($each as [$off, $slot, $one]) {
        $ao->process_submitted_actions($tstart + $off, false, $one + ['slots' => (string)$slot]);
        $ao = quiz_attempt::create($attempt->id);
    }
    $ao->process_finish($tstart + (int)$timing['finish'], false);
    return $attempt->id;
}
foreach ($spec['attempts'] as $i => $a) {
    take_attempt($quiz->id, $users[$a["username"]], $a["answers"], time(), $a["timing"] ?? null);
    $made++;
}
take_attempt($quiz->id, $users[$spec['teacher']['username']], [], $t0);
echo json_encode(['course_id' => (int)$course->id, 'quiz_id' => (int)$quiz->id, 'attempts' => $made,
                  'questions' => count($qformat->questionids)]), "\n";
