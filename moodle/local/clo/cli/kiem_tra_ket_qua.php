<?php
define('CLI_SCRIPT', true);
require(__DIR__ . '/../../../config.php');

$plugin = core_plugin_manager::instance()->get_plugin_info('local_clo');
echo "Plugin local_clo: " . $plugin->release . " (" . $plugin->versiondisk . ")\n";
$exams = $DB->get_records('local_clo_exam');
if (!$exams) {
    echo "Chua co bai kiem tra nao duoc day sang Moodle.\n";
    exit(0);
}
foreach ($exams as $e) {
    $rows = $DB->get_records('local_clo_result', ['cloexamid' => $e->id]);
    $n = ['clos' => 0, 'chapters' => 0, 'materials' => 0, 'wrong' => 0, 'items' => 0, 'review' => 0, 'scan' => 0];
    foreach ($rows as $r) {
        $d = json_decode($r->data ?? '{}');
        foreach ($n as $k => $v) {
            if (!empty($d->$k)) {
                $n[$k]++;
            }
        }
    }
    echo "Bai '{$e->title}' (examref {$e->examref}, quizid {$e->quizid}): cong bo=" . (int)$e->published .
        ", ket qua=" . count($rows) . ", co CLO=" . $n['clos'] . ", co chuong=" . $n['chapters'] .
        ", co hoc lieu=" . $n['materials'] . ", co cau sai=" . $n['wrong'] .
        ", co bai lam giay=" . $n['review'] . ", co anh phieu=" . $n['scan'] . "\n";
}
