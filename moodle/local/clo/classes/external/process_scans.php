<?php
namespace local_clo\external;

defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * Cho Moodle nhận diện & chấm ngay các phiếu trả lời đã tải lên (đang chờ trong hàng đợi của Offline Quiz),
 * không phải đợi tác vụ định kỳ (cron) – hữu ích khi Moodle chạy trên XAMPP không bật cron.
 * Việc nhận diện và chấm vẫn do chính plugin Offline Quiz thực hiện (offlinequiz_evaluation_cron).
 */
class process_scans extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'examref' => new external_value(PARAM_INT, 'exams.id bên hệ thống phân tích'),
        ]);
    }

    public static function execute($examref): array {
        global $CFG, $DB;
        $p = self::validate_parameters(self::execute_parameters(), ['examref' => $examref]);
        $exam = $DB->get_record('local_clo_exam', ['examref' => $p['examref']]);
        if (!$exam || empty($exam->offlinequizid) ||
                !($cm = get_coursemodule_from_instance('offlinequiz', $exam->offlinequizid, 0, false, IGNORE_MISSING))) {
            throw new \moodle_exception('nooq', 'local_clo');
        }
        $context = \context_course::instance($cm->course);
        self::validate_context($context);
        require_capability('local/clo:manage', $context);
        require_once($CFG->dirroot . '/mod/offlinequiz/cron.php');
        \core_php_time_limit::raise(600);

        $jobs = $DB->get_records('offlinequiz_queue', ['offlinequizid' => $exam->offlinequizid, 'status' => 'new'], 'id', 'id');
        ob_start();
        foreach ($jobs as $job) {
            offlinequiz_evaluation_cron($job->id);
        }
        ob_end_clean();
        $out = create_offlinequiz::describe($exam->offlinequizid, $cm, false);
        $out['processedjobs'] = count($jobs);
        return $out;
    }

    public static function execute_returns(): external_single_structure {
        $s = create_offlinequiz::describe_returns();
        $s->keys['processedjobs'] = new external_value(PARAM_INT, 'số lượt tải phiếu vừa được chấm');
        return $s;
    }
}
