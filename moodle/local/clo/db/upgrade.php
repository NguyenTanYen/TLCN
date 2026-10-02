<?php
defined('MOODLE_INTERNAL') || die();

/**
 * Nâng cấp local_clo: 2026100100 – thêm liên kết bài thi giấy (Offline Quiz).
 */
function xmldb_local_clo_upgrade($oldversion) {
    global $DB;
    $dbman = $DB->get_manager();
    if ($oldversion < 2026100100) {
        $table = new xmldb_table('local_clo_exam');
        $field = new xmldb_field('offlinequizid', XMLDB_TYPE_INTEGER, '10', null, null, null, null, 'quizid');
        if (!$dbman->field_exists($table, $field)) {
            $dbman->add_field($table, $field);
        }
        upgrade_plugin_savepoint(true, 2026100100, 'local', 'clo');
    }
    return true;
}
