<?php
namespace local_clo\privacy;

defined('MOODLE_INTERNAL') || die();

use core_privacy\local\metadata\collection;
use core_privacy\local\request\approved_contextlist;
use core_privacy\local\request\approved_userlist;
use core_privacy\local\request\contextlist;
use core_privacy\local\request\userlist;
use core_privacy\local\request\writer;

/**
 * Quyền riêng tư (GDPR): khai báo dữ liệu cá nhân plugin lưu/gửi đi, cho phép xuất và xóa kết quả phân tích
 * của một sinh viên (bảng local_clo_result, nằm trong ngữ cảnh khóa học).
 */
class provider implements
        \core_privacy\local\metadata\provider,
        \core_privacy\local\request\plugin\provider,
        \core_privacy\local\request\core_userlist_provider {

    public static function get_metadata(collection $collection): collection {
        $collection->add_database_table('local_clo_result', [
            'userid' => 'privacy:metadata:local_clo_result:userid',
            'score' => 'privacy:metadata:local_clo_result:score',
            'data' => 'privacy:metadata:local_clo_result:data',
        ], 'privacy:metadata:local_clo_result');
        $collection->add_external_location_link('clo_analytics', [
            'username' => 'privacy:metadata:clo_analytics:username',
            'email' => 'privacy:metadata:clo_analytics:email',
            'fullname' => 'privacy:metadata:clo_analytics:fullname',
        ], 'privacy:metadata:clo_analytics');
        return $collection;
    }

    public static function get_contexts_for_userid(int $userid): contextlist {
        $sql = "SELECT ctx.id
                  FROM {local_clo_result} r
                  JOIN {local_clo_exam} e ON e.id = r.cloexamid
                  JOIN {context} ctx ON ctx.instanceid = e.courseid AND ctx.contextlevel = :lvl
                 WHERE r.userid = :userid";
        $list = new contextlist();
        $list->add_from_sql($sql, ['lvl' => CONTEXT_COURSE, 'userid' => $userid]);
        return $list;
    }

    public static function get_users_in_context(userlist $userlist) {
        $context = $userlist->get_context();
        if ($context->contextlevel != CONTEXT_COURSE) {
            return;
        }
        $sql = "SELECT r.userid FROM {local_clo_result} r JOIN {local_clo_exam} e ON e.id = r.cloexamid
                 WHERE e.courseid = :courseid";
        $userlist->add_from_sql('userid', $sql, ['courseid' => $context->instanceid]);
    }

    public static function export_user_data(approved_contextlist $contextlist) {
        global $DB;
        $userid = $contextlist->get_user()->id;
        foreach ($contextlist->get_contexts() as $context) {
            if ($context->contextlevel != CONTEXT_COURSE) {
                continue;
            }
            $rows = $DB->get_records_sql("SELECT r.*, e.title FROM {local_clo_result} r
                                            JOIN {local_clo_exam} e ON e.id = r.cloexamid
                                           WHERE e.courseid = ? AND r.userid = ?", [$context->instanceid, $userid]);
            $out = [];
            foreach ($rows as $r) {
                $out[] = (object)['exam' => format_string($r->title), 'status' => $r->status, 'score' => $r->score,
                    'maxscore' => $r->maxscore, 'analysis' => json_decode($r->data ?? 'null'),
                    'timemodified' => \core_privacy\local\request\transform::datetime($r->timemodified)];
            }
            if ($out) {
                writer::with_context($context)->export_data([get_string('pluginname', 'local_clo')], (object)['results' => $out]);
            }
        }
    }

    private static function exam_ids(int $courseid): array {
        global $DB;
        return $DB->get_fieldset_select('local_clo_exam', 'id', 'courseid = ?', [$courseid]);
    }

    public static function delete_data_for_all_users_in_context(\context $context) {
        global $DB;
        if ($context->contextlevel == CONTEXT_COURSE && ($ids = self::exam_ids($context->instanceid))) {
            $DB->delete_records_list('local_clo_result', 'cloexamid', $ids);
        }
    }

    public static function delete_data_for_user(approved_contextlist $contextlist) {
        global $DB;
        $userid = $contextlist->get_user()->id;
        foreach ($contextlist->get_contexts() as $context) {
            if ($context->contextlevel == CONTEXT_COURSE && ($ids = self::exam_ids($context->instanceid))) {
                [$in, $p] = $DB->get_in_or_equal($ids);
                $DB->delete_records_select('local_clo_result', "userid = ? AND cloexamid $in", array_merge([$userid], $p));
            }
        }
    }

    public static function delete_data_for_users(approved_userlist $userlist) {
        global $DB;
        $context = $userlist->get_context();
        if ($context->contextlevel != CONTEXT_COURSE || !($ids = self::exam_ids($context->instanceid)) || !$userlist->get_userids()) {
            return;
        }
        [$in1, $p1] = $DB->get_in_or_equal($ids);
        [$in2, $p2] = $DB->get_in_or_equal($userlist->get_userids());
        $DB->delete_records_select('local_clo_result', "cloexamid $in1 AND userid $in2", array_merge($p1, $p2));
    }
}
