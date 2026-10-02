<?php
namespace local_clo\external;

defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * Trạng thái Offline Quiz của một bài kiểm tra: các tệp đề/phiếu/đáp án từng nhóm và số bài Moodle đã chấm xong.
 */
class get_offlinequiz extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'examref' => new external_value(PARAM_INT, 'exams.id bên hệ thống phân tích'),
        ]);
    }

    public static function execute($examref): array {
        global $DB;
        $p = self::validate_parameters(self::execute_parameters(), ['examref' => $examref]);
        $exam = $DB->get_record('local_clo_exam', ['examref' => $p['examref']]);
        if (!$exam || empty($exam->offlinequizid) ||
                !($cm = get_coursemodule_from_instance('offlinequiz', $exam->offlinequizid, 0, false, IGNORE_MISSING))) {
            throw new \moodle_exception('nooq', 'local_clo');
        }
        $context = \context_course::instance($cm->course);
        self::validate_context($context);
        require_capability('local/clo:manage', $context);
        return create_offlinequiz::describe($exam->offlinequizid, $cm, false);
    }

    public static function execute_returns(): external_single_structure {
        return create_offlinequiz::describe_returns();
    }
}
