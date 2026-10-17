<?php
namespace local_clo\external;

defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * Bài phụ đạo (góp ý F5): chỉ các sinh viên được giao mới thấy và làm được Quiz. Tạo/cập nhật nhóm "Phụ đạo – …" gồm đúng
 * các SV đó và đặt điều kiện truy cập "thuộc nhóm" cho hoạt động (ẩn hẳn với SV khác). Gọi lại thì đồng bộ lại thành viên.
 * Xác định hoạt động bằng cmid, hoặc bằng quizid khi hệ thống chỉ lưu id Quiz.
 */
class restrict_users extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'Khóa học Moodle'),
            'cmid' => new external_value(PARAM_INT, 'course module của hoạt động (0 = tìm theo quizid)', VALUE_DEFAULT, 0),
            'quizid' => new external_value(PARAM_INT, 'mdl_quiz.id khi không có cmid', VALUE_DEFAULT, 0),
            'groupname' => new external_value(PARAM_TEXT, 'Tên nhóm'),
            'userids' => new external_multiple_structure(new external_value(PARAM_INT, 'mdl_user.id')),
        ]);
    }

    public static function execute($courseid, $cmid, $quizid, $groupname, $userids): array {
        global $DB, $CFG;
        require_once($CFG->dirroot . '/group/lib.php');
        require_once($CFG->dirroot . '/course/lib.php');
        $p = self::validate_parameters(self::execute_parameters(), compact('courseid', 'cmid', 'quizid', 'groupname', 'userids'));
        $course = get_course($p['courseid']);
        $context = \context_course::instance($course->id);
        self::validate_context($context);
        require_capability('local/clo:manage', $context);
        require_capability('moodle/course:managegroups', $context);
        $cm = $p['cmid'] ? get_coursemodule_from_id('', $p['cmid'], $course->id, false, MUST_EXIST)
                         : get_coursemodule_from_instance('quiz', $p['quizid'], $course->id, false, MUST_EXIST);
        $idnumber = 'clo_remedial_' . $cm->id;
        $group = $DB->get_record('groups', ['courseid' => $course->id, 'idnumber' => $idnumber]);
        $gid = $group ? (int)$group->id : (int)groups_create_group((object)['courseid' => $course->id, 'idnumber' => $idnumber,
            'name' => shorten_text($p['groupname'], 250), 'description' => 'Tạo bởi hệ thống phân tích CĐR (bài phụ đạo)']);
        $want = array_map('intval', $p['userids']);
        $added = [];
        $skipped = [];
        foreach ($want as $uid) {
            if (is_enrolled($context, $uid)) {
                groups_add_member($gid, $uid);
                $added[] = $uid;
            } else {
                $skipped[] = $uid;
            }
        }
        foreach (groups_get_members($gid, 'u.id') as $m) {
            if (!in_array((int)$m->id, $want, true)) {
                groups_remove_member($gid, $m->id);
            }
        }
        $availability = json_encode(['op' => '&', 'c' => [['type' => 'group', 'id' => $gid]], 'showc' => [false]]);
        $DB->set_field('course_modules', 'availability', $availability, ['id' => $cm->id]);
        rebuild_course_cache($course->id, true);
        return ['groupid' => $gid, 'cmid' => (int)$cm->id, 'added' => $added, 'skipped' => $skipped];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'groupid' => new external_value(PARAM_INT, 'mdl_groups.id'),
            'cmid' => new external_value(PARAM_INT, 'course module của hoạt động'),
            'added' => new external_multiple_structure(new external_value(PARAM_INT, 'SV trong nhóm')),
            'skipped' => new external_multiple_structure(new external_value(PARAM_INT, 'SV không ghi danh khóa học')),
        ]);
    }
}
