<?php
// Kịch bản kiểm thử tích hợp với Moodle THẬT (chạy trong thư mục cài Moodle 4.x):
//   php moodle_build_quiz.php --spec=spec.json --xml=exam.xml
// - Tạo khóa học, tài khoản SV/GV, ghi danh.
// - NHẬP tệp Moodle XML do hệ thống xuất (giữ idnumber QB-n) vào ngân hàng câu hỏi của khóa học.
// - Tạo Quiz có xáo trộn phương án, thêm câu hỏi theo thứ tự đề.
// - Cho từng SV làm bài bằng API chấm điểm của Moodle (quiz_attempt::process_finish) – Moodle tự chấm sumgrades.
// In ra JSON {course_id, quiz_id, attempts}.
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

// 1. khóa học + người dùng + ghi danh
$course = $DB->get_record('course', ['shortname' => $spec['course']['shortname']]);
if ($course) { delete_course($course, false); }
$course = $gen->create_course(['fullname' => $spec['course']['fullname'], 'shortname' => $spec['course']['shortname']]);
$users = [];
foreach (array_merge($spec['students'], [$spec['teacher']]) as $u) {
    $rec = $DB->get_record('user', ['username' => $u['username']]) ?: $gen->create_user([
        'username' => $u['username'], 'idnumber' => $u['idnumber'] ?? '', 'firstname' => $u['firstname'],
        'lastname' => $u['lastname'], 'email' => $u['username'] . '@example.com',
        'password' => $u['password'] ?? 'Sv@123456']);   // để SV đăng nhập được cả Moodle lẫn hệ thống
    if (!empty($u['password'])) {
        update_internal_user_password($rec, $u['password']);   // đặt lại mật khẩu demo cho tài khoản đã có
    }
    $users[$u['username']] = $rec;
    $gen->enrol_user($rec->id, $course->id, $u['role'] ?? 'student');
}

// 2. nhập Moodle XML vào ngân hàng câu hỏi của khóa học
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

// 3. Quiz: xáo trộn phương án, phản hồi trì hoãn, không giới hạn số lượt
$quizgen = $gen->get_plugin_generator('mod_quiz');
$quiz = $quizgen->create_instance(['course' => $course->id, 'name' => $spec['quiz']['name'], 'grade' => $spec['quiz']['grade'],
    'sumgrades' => 0, 'shuffleanswers' => 1, 'preferredbehaviour' => 'deferredfeedback', 'attempts' => 0, 'questionsperpage' => 0]);
foreach ($qformat->questionids as $qid) {
    $maxmark = $DB->get_field('question', 'defaultmark', ['id' => $qid]);
    quiz_add_quiz_question($qid, $quiz, 0, $maxmark);
}
$quizobj = quiz_settings::create($quiz->id);
\mod_quiz\grade_calculator::create($quizobj)->recompute_quiz_sumgrades();

// 4. làm bài: responses = [{ "QB-5": vị trí phương án gốc (0-based) | null }]
$t0 = time();
$made = 0;
function take_attempt($quizid, $user, $answers, $time) {
    global $DB;
    \core\session\manager::set_user($user);
    $quizobj = quiz_settings::create($quizid, $user->id);
    $prev = quiz_get_user_attempts($quizid, $user->id, 'all', true);
    $last = $prev ? end($prev) : null;
    $attempt = quiz_prepare_and_start_new_attempt($quizobj, $last ? $last->attempt + 1 : 1, $last);
    $ao = quiz_attempt::create($attempt->id);
    $post = [];
    foreach ($ao->get_slots() as $slot) {
        $qa = $ao->get_question_attempt($slot);
        $q = $qa->get_question();
        $pos = $answers[$q->idnumber] ?? null;
        if ($pos === null) { continue; }               // bỏ trống
        $ids = array_keys($q->answers); sort($ids);      // thứ tự gốc = thứ tự id (theo XML)
        $field = array_search($ids[$pos], $q->get_order($qa)); // vị trí sau khi xáo trộn
        $post[$qa->get_control_field_name('sequencecheck')] = (string)$qa->get_sequence_check_count();
        $post[$qa->get_qt_field_name('answer')] = (string)$field;
    }
    $ao->process_submitted_actions($time, false, $post);
    $ao->process_finish(max($time, time()), false);
    return $attempt->id;
}
foreach ($spec['attempts'] as $i => $a) {
    take_attempt($quiz->id, $users[$a["username"]], $a["answers"], time());
    $made++;
}
// một lượt "xem trước" của giảng viên – phải bị hệ thống loại
take_attempt($quiz->id, $users[$spec['teacher']['username']], [], $t0);
echo json_encode(['course_id' => (int)$course->id, 'quiz_id' => (int)$quiz->id, 'attempts' => $made,
                  'questions' => count($qformat->questionids)]), "\n";
