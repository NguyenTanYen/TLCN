<?php
namespace local_clo\external;

defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

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

        $p = self::validate_parameters(self::execute_parameters(), compact('courseid', 'examref', 'name', 'questionsxml',
            'grade', 'timeopen', 'timeclose', 'timelimit'));
        $course = get_course($p['courseid']);
        $context = \context_course::instance($course->id);
        self::validate_context($context);
        require_capability('local/clo:manage', $context);
        require_capability('moodle/course:manageactivities', $context);
        require_capability('moodle/question:add', $context);

        $exam = $DB->get_record('local_clo_exam', ['examref' => $p['examref']]);
        if ($exam && $exam->quizid && ($cm = get_coursemodule_from_instance('quiz', $exam->quizid, 0, false, IGNORE_MISSING))) {
            return ['quizid' => (int)$exam->quizid, 'cmid' => (int)$cm->id, 'courseid' => (int)$cm->course,
                'questions' => (int)$DB->count_records('quiz_slots', ['quizid' => $exam->quizid]), 'created' => false];
        }

        $tx = $DB->start_delegated_transaction();
        $questionids = \local_clo\question_importer::import($course, $p['questionsxml']);

        $quiz = (object)[
            'modulename' => 'quiz', 'course' => $course->id, 'section' => 0, 'visible' => 1,
            'name' => $p['name'], 'introeditor' => ['text' => '', 'format' => FORMAT_HTML, 'itemid' => 0],
            'timeopen' => $p['timeopen'], 'timeclose' => $p['timeclose'], 'timelimit' => $p['timelimit'],
            'overduehandling' => 'autosubmit', 'graceperiod' => 0,
            'preferredbehaviour' => 'deferredfeedback', 'canredoquestions' => 0,
            'attempts' => 1, 'attemptonlast' => 0, 'grademethod' => QUIZ_GRADEHIGHEST,
            'decimalpoints' => 2, 'questiondecimalpoints' => -1, 'questionsperpage' => 1,
            'navmethod' => QUIZ_NAVMETHOD_FREE, 'shuffleanswers' => 1,
            'sumgrades' => 0, 'grade' => $p['grade'], 'quizpassword' => '', 'subnet' => '', 'browsersecurity' => '-',
            'delay1' => 0, 'delay2' => 0, 'showuserpicture' => 0, 'showblocks' => 0,
        ];
        foreach (['during', 'immediately', 'open', 'closed'] as $when) {
            foreach (['attempt', 'correctness', 'maxmarks', 'marks', 'specificfeedback', 'generalfeedback',
                    'rightanswer', 'overallfeedback'] as $what) {
                $quiz->{$what . $when} = ($when === 'during') ? (int)in_array($what, ['attempt', 'maxmarks']) :
                    (int)($when === 'closed' || in_array($what, ['attempt', 'maxmarks', 'marks', 'overallfeedback']));
            }
        }
        $modinfo = create_module($quiz);
        $quizrec = $DB->get_record('quiz', ['id' => $modinfo->instance], '*', MUST_EXIST);
        $marks = \local_clo\question_importer::marks($p['questionsxml']);
        foreach ($questionids as $i => $qid) {
            quiz_add_quiz_question($qid, $quizrec, 0, $marks[$i] ?? $DB->get_field('question', 'defaultmark', ['id' => $qid]));
        }
        \mod_quiz\grade_calculator::create(\mod_quiz\quiz_settings::create($quizrec->id))->recompute_quiz_sumgrades();

        $now = time();
        if ($exam) {
            $exam->courseid = $course->id; $exam->quizid = $quizrec->id; $exam->title = $p['name']; $exam->timemodified = $now;
            $DB->update_record('local_clo_exam', $exam);
        } else {
            $DB->insert_record('local_clo_exam', (object)['examref' => $p['examref'], 'courseid' => $course->id,
                'quizid' => $quizrec->id, 'title' => $p['name'], 'published' => 0, 'timecreated' => $now, 'timemodified' => $now]);
        }
        $tx->allow_commit();
        return ['quizid' => (int)$quizrec->id, 'cmid' => (int)$modinfo->coursemodule, 'courseid' => (int)$course->id,
            'questions' => count($questionids), 'created' => true];
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
