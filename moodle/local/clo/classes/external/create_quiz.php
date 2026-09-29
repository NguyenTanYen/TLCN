<?php
namespace local_clo\external;

defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * UC-02 qua API: nhập tệp Moodle XML (mỗi câu mang idnumber QB-n, phương án đúng thứ tự, shuffleanswers=1)
 * vào ngân hàng câu hỏi của khóa học rồi tạo Quiz bật xáo trộn phương án, thêm câu theo đúng thứ tự đề.
 * Gọi lại nhiều lần với cùng examref không tạo Quiz trùng.
 */
class create_quiz extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'Khóa học Moodle'),
            'examref' => new external_value(PARAM_INT, 'Mã bài kiểm tra bên hệ thống phân tích (exams.id)'),
            'name' => new external_value(PARAM_TEXT, 'Tên Quiz'),
            'questionsxml' => new external_value(PARAM_RAW, 'Nội dung tệp Moodle XML'),
            'grade' => new external_value(PARAM_FLOAT, 'Thang điểm', VALUE_DEFAULT, 10),
            'timeopen' => new external_value(PARAM_INT, 'Thời điểm mở (unix)', VALUE_DEFAULT, 0),
            'timeclose' => new external_value(PARAM_INT, 'Thời điểm đóng (unix)', VALUE_DEFAULT, 0),
            'timelimit' => new external_value(PARAM_INT, 'Thời gian làm bài (giây)', VALUE_DEFAULT, 0),
        ]);
    }

    public static function execute($courseid, $examref, $name, $questionsxml, $grade = 10, $timeopen = 0, $timeclose = 0,
            $timelimit = 0): array {
        global $CFG, $DB;
        require_once($CFG->dirroot . '/course/modlib.php');
        require_once($CFG->dirroot . '/mod/quiz/locallib.php');
        require_once($CFG->dirroot . '/question/editlib.php');
        require_once($CFG->dirroot . '/question/format/xml/format.php');

        $p = self::validate_parameters(self::execute_parameters(), compact('courseid', 'examref', 'name', 'questionsxml',
            'grade', 'timeopen', 'timeclose', 'timelimit'));
        $course = get_course($p['courseid']);
        $context = \context_course::instance($course->id);
        self::validate_context($context);
        require_capability('local/clo:manage', $context);
        require_capability('moodle/course:manageactivities', $context);
        require_capability('moodle/question:add', $context);

        // Đã tạo trước đó -> trả lại Quiz cũ (idempotent).
        $exam = $DB->get_record('local_clo_exam', ['examref' => $p['examref']]);
        if ($exam && $exam->quizid && ($cm = get_coursemodule_from_instance('quiz', $exam->quizid, 0, false, IGNORE_MISSING))) {
            return ['quizid' => (int)$exam->quizid, 'cmid' => (int)$cm->id, 'courseid' => (int)$cm->course,
                'questions' => (int)$DB->count_records('quiz_slots', ['quizid' => $exam->quizid]), 'created' => false];
        }

        // 1. Nhập XML vào ngân hàng câu hỏi của khóa học (danh mục mang tên đề, lấy từ tệp XML).
        $dir = make_request_directory();
        $file = $dir . '/exam.xml';
        file_put_contents($file, $p['questionsxml']);
        $contexts = new \core_question\local\bank\question_edit_contexts($context);
        $defaultcat = question_make_default_categories($contexts->all());
        $qformat = new \qformat_xml();
        $qformat->setCategory($defaultcat);
        $qformat->setContexts($contexts->having_one_edit_tab_cap('import'));
        $qformat->setCourse($course);
        $qformat->setFilename($file);
        $qformat->setRealfilename('exam.xml');
        $qformat->setMatchgrades('error');
        $qformat->setCatfromfile(true);
        $qformat->setContextfromfile(true);
        $qformat->setStoponerror(true);
        ob_start();
        $ok = $qformat->importpreprocess() && $qformat->importprocess() && $qformat->importpostprocess();
        $log = ob_get_clean();
        if (!$ok || empty($qformat->questionids)) {
            throw new \moodle_exception('importfailed', 'local_clo', '', null, trim(strip_tags($log)));
        }

        // 2. Tạo Quiz: xáo trộn phương án, phản hồi trì hoãn, tính điểm lượt cao nhất (mặc định của Moodle).
        $quiz = (object)[
            'modulename' => 'quiz', 'course' => $course->id, 'section' => 0, 'visible' => 1,
            'name' => $p['name'], 'introeditor' => ['text' => '', 'format' => FORMAT_HTML, 'itemid' => 0],
            'timeopen' => $p['timeopen'], 'timeclose' => $p['timeclose'], 'timelimit' => $p['timelimit'],
            'overduehandling' => 'autosubmit', 'graceperiod' => 0,
            'preferredbehaviour' => 'deferredfeedback', 'canredoquestions' => 0,
            'attempts' => 1, 'attemptonlast' => 0, 'grademethod' => QUIZ_GRADEHIGHEST,
            'decimalpoints' => 2, 'questiondecimalpoints' => -1, 'questionsperpage' => 5,
            'navmethod' => QUIZ_NAVMETHOD_FREE, 'shuffleanswers' => 1,
            'sumgrades' => 0, 'grade' => $p['grade'], 'quizpassword' => '', 'subnet' => '', 'browsersecurity' => '-',
            'delay1' => 0, 'delay2' => 0, 'showuserpicture' => 0, 'showblocks' => 0,
        ];
        // Tùy chọn xem lại: SV xem điểm sau khi nộp; đáp án đúng chỉ hiện sau khi Quiz đóng.
        foreach (['during', 'immediately', 'open', 'closed'] as $when) {
            foreach (['attempt', 'correctness', 'maxmarks', 'marks', 'specificfeedback', 'generalfeedback',
                    'rightanswer', 'overallfeedback'] as $what) {
                $quiz->{$what . $when} = ($when === 'during') ? (int)in_array($what, ['attempt', 'maxmarks']) :
                    (int)($when === 'closed' || in_array($what, ['attempt', 'maxmarks', 'marks', 'overallfeedback']));
            }
        }
        $modinfo = create_module($quiz);
        $quizrec = $DB->get_record('quiz', ['id' => $modinfo->instance], '*', MUST_EXIST);
        foreach ($qformat->questionids as $qid) {
            quiz_add_quiz_question($qid, $quizrec, 0, $DB->get_field('question', 'defaultmark', ['id' => $qid]));
        }
        \mod_quiz\grade_calculator::create(\mod_quiz\quiz_settings::create($quizrec->id))->recompute_quiz_sumgrades();

        // 3. Ghi nhận liên kết bài KT <-> Quiz (kết quả ở trạng thái "bảo lưu" cho tới khi GV công bố).
        $now = time();
        if ($exam) {
            $exam->courseid = $course->id; $exam->quizid = $quizrec->id; $exam->title = $p['name']; $exam->timemodified = $now;
            $DB->update_record('local_clo_exam', $exam);
        } else {
            $DB->insert_record('local_clo_exam', (object)['examref' => $p['examref'], 'courseid' => $course->id,
                'quizid' => $quizrec->id, 'title' => $p['name'], 'published' => 0, 'timecreated' => $now, 'timemodified' => $now]);
        }
        return ['quizid' => (int)$quizrec->id, 'cmid' => (int)$modinfo->coursemodule, 'courseid' => (int)$course->id,
            'questions' => count($qformat->questionids), 'created' => true];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'quizid' => new external_value(PARAM_INT, 'mdl_quiz.id'),
            'cmid' => new external_value(PARAM_INT, 'course module id'),
            'courseid' => new external_value(PARAM_INT, 'khóa học'),
            'questions' => new external_value(PARAM_INT, 'số câu hỏi trong Quiz'),
            'created' => new external_value(PARAM_BOOL, 'true nếu vừa tạo mới'),
        ]);
    }
}
