<?php
namespace local_clo\external;

defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * Nhận kết quả phân tích CĐR của một bài kiểm tra từ hệ thống của nhóm (sau UC-03/UC-04) và trạng thái
 * công bố (publish_flag). Sinh viên xem tại local/clo/results.php; khi GV công bố, SV nhận thông báo.
 * Lần gửi sau thay thế toàn bộ kết quả của lần trước (đồng bộ lại không sinh bản ghi trùng).
 */
class push_results extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'examref' => new external_value(PARAM_INT, 'exams.id bên hệ thống phân tích'),
            'courseid' => new external_value(PARAM_INT, 'Khóa học Moodle'),
            'quizid' => new external_value(PARAM_INT, 'mdl_quiz.id (0 nếu thi giấy)', VALUE_DEFAULT, 0),
            'title' => new external_value(PARAM_TEXT, 'Tên bài kiểm tra'),
            'published' => new external_value(PARAM_BOOL, 'GV đã công bố kết quả'),
            'results' => new external_multiple_structure(new external_single_structure([
                'userid' => new external_value(PARAM_INT, 'mdl_user.id nếu đã biết', VALUE_DEFAULT, 0),
                'username' => new external_value(PARAM_RAW, 'Tên đăng nhập Moodle (MSSV)', VALUE_DEFAULT, ''),
                'status' => new external_value(PARAM_ALPHA, 'finished | absent'),
                'score' => new external_value(PARAM_FLOAT, 'Điểm theo thang', VALUE_DEFAULT, null),
                'maxscore' => new external_value(PARAM_FLOAT, 'Thang điểm', VALUE_DEFAULT, null),
                'data' => new external_value(PARAM_RAW, 'JSON: clos, summary, study_plan, items', VALUE_DEFAULT, '{}'),
            ]), 'Kết quả từng sinh viên', VALUE_DEFAULT, []),
        ]);
    }

    public static function execute($examref, $courseid, $quizid, $title, $published, $results = []): array {
        global $CFG, $DB;
        $p = self::validate_parameters(self::execute_parameters(),
            compact('examref', 'courseid', 'quizid', 'title', 'published', 'results'));
        $course = get_course($p['courseid']);
        $context = \context_course::instance($course->id);
        self::validate_context($context);
        require_capability('local/clo:manage', $context);

        $now = time();
        $exam = $DB->get_record('local_clo_exam', ['examref' => $p['examref']]);
        if (!$exam) {
            $exam = (object)['examref' => $p['examref'], 'timecreated' => $now];
        }
        $exam->courseid = $course->id;
        $exam->quizid = $p['quizid'] ?: ($exam->quizid ?? null);
        $exam->title = $p['title'];
        $exam->published = $p['published'] ? 1 : 0;
        $exam->timemodified = $now;
        if (empty($exam->id)) {
            $exam->id = $DB->insert_record('local_clo_exam', $exam);
        } else {
            $DB->update_record('local_clo_exam', $exam);
        }

        $saved = 0; $notfound = []; $keep = [];
        $transaction = $DB->start_delegated_transaction();
        foreach ($p['results'] as $r) {
            $user = null;
            if ($r['userid']) {
                $user = $DB->get_record('user', ['id' => $r['userid'], 'deleted' => 0]);
            }
            if (!$user && $r['username'] !== '') {
                $user = $DB->get_record('user', ['username' => \core_text::strtolower($r['username']),
                    'mnethostid' => $CFG->mnet_localhost_id, 'deleted' => 0]);
            }
            if (!$user || !is_enrolled($context, $user)) {
                $notfound[] = $r['username'] ?: (string)$r['userid'];
                continue;
            }
            $data = json_decode($r['data'] ?: '{}');
            if ($data === null) {
                throw new \invalid_parameter_exception('data phải là JSON hợp lệ (' . $r['username'] . ')');
            }
            $rec = $DB->get_record('local_clo_result', ['cloexamid' => $exam->id, 'userid' => $user->id]);
            $row = (object)['cloexamid' => $exam->id, 'userid' => $user->id,
                'status' => $r['status'] === 'absent' ? 'absent' : 'finished',
                'score' => $r['score'], 'maxscore' => $r['maxscore'], 'data' => json_encode($data, JSON_UNESCAPED_UNICODE),
                'timemodified' => $now];
            if ($rec) {
                $row->id = $rec->id;
                $DB->update_record('local_clo_result', $row);
            } else {
                $row->notified = 0;
                $row->id = $DB->insert_record('local_clo_result', $row);
            }
            $keep[] = $row->id;
            $saved++;
        }
        // Kết quả không còn trong lần gửi này (ví dụ SV rút khỏi lớp) bị loại bỏ.
        if ($p['results']) {
            [$notin, $params] = $DB->get_in_or_equal($keep ?: [0], SQL_PARAMS_NAMED, 'k', false);
            $DB->delete_records_select('local_clo_result', "cloexamid = :e AND id $notin", $params + ['e' => $exam->id]);
        }
        $transaction->allow_commit();

        $notified = $exam->published ? self::notify($exam, $course) : 0;
        return ['cloexamid' => (int)$exam->id, 'saved' => $saved, 'notfound' => $notfound, 'notified' => $notified];
    }

    /** Gửi thông báo "đã có kết quả phân tích" cho SV chưa được báo. */
    protected static function notify(\stdClass $exam, \stdClass $course): int {
        global $CFG, $DB;
        $n = 0;
        $url = new \moodle_url('/local/clo/results.php', ['id' => $course->id]);
        // Chỉ báo cho SV có bài làm được chấm (SV vắng thi không có kết quả để xem).
        foreach ($DB->get_records('local_clo_result', ['cloexamid' => $exam->id, 'notified' => 0, 'status' => 'finished']) as $r) {
            $msg = new \core\message\message();
            $msg->component = 'local_clo';
            $msg->name = 'resultpublished';
            $msg->userfrom = \core_user::get_noreply_user();
            $msg->userto = $r->userid;
            $msg->courseid = $course->id;
            // Thông báo theo ngôn ngữ của người nhận (không theo ngôn ngữ của tài khoản gọi Web Service).
            $lang = $DB->get_field('user', 'lang', ['id' => $r->userid]) ?: $CFG->lang;
            $sm = get_string_manager();
            $msg->subject = $sm->get_string('notify_subject', 'local_clo', format_string($exam->title), $lang);
            $msg->fullmessage = $sm->get_string('notify_body', 'local_clo', (object)['exam' => format_string($exam->title),
                'course' => format_string($course->fullname), 'url' => $url->out(false)], $lang);
            $msg->fullmessageformat = FORMAT_PLAIN;
            $msg->fullmessagehtml = '';
            $msg->smallmessage = $msg->subject;
            $msg->notification = 1;
            $msg->contexturl = $url->out(false);
            $msg->contexturlname = $sm->get_string('results', 'local_clo', null, $lang);
            try {
                message_send($msg);
                $DB->set_field('local_clo_result', 'notified', 1, ['id' => $r->id]);
                $n++;
            } catch (\Throwable $e) {
                debugging('local_clo: không gửi được thông báo: ' . $e->getMessage());
            }
        }
        return $n;
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'cloexamid' => new external_value(PARAM_INT, 'local_clo_exam.id'),
            'saved' => new external_value(PARAM_INT, 'số kết quả đã lưu'),
            'notfound' => new external_multiple_structure(new external_value(PARAM_RAW, 'tài khoản'),
                'SV không tìm thấy hoặc không ghi danh trong khóa học'),
            'notified' => new external_value(PARAM_INT, 'số thông báo đã gửi'),
        ]);
    }
}
