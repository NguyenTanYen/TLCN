<?php
// DEMO bài thi giấy: đưa các ảnh phiếu trả lời "đã quét" vào hàng đợi nhận diện của Offline Quiz – giống hệt thao tác
// giảng viên bấm "Tải lên" ảnh quét trên trang Offline Quiz (report.php?mode=rimport). Việc nhận diện MSSV, mã đề,
// các ô đánh dấu và chấm điểm vẫn do chính plugin Offline Quiz thực hiện (hệ thống gọi local_clo_process_scans).
//   php moodle_enqueue_scans.php --moodle=D:\xampp\htdocs\moodle --oq=<offlinequizid> <anh1.png> <anh2.png> ...
// In ra JSON {queueid, files}.
define('CLI_SCRIPT', true);
$opts = getopt('', ['moodle:', 'oq:'], $rest);
require($opts['moodle'] . '/config.php');
$files = array_slice($argv, $rest);
$oqid = (int)$opts['oq'];
$DB->get_record('offlinequiz', ['id' => $oqid], 'id', MUST_EXIST);
\core\session\manager::set_user(get_admin());

$dir = "{$CFG->tempdir}/offlinequiz/import/" . str_replace('.', '', microtime(true)) . random_int(0, 100000);
check_dir_exists($dir, true, true);
$job = (object)['offlinequizid' => $oqid, 'importuserid' => get_admin()->id, 'timecreated' => time(),
    'timestart' => 0, 'timefinish' => 0, 'status' => 'uploading'];
$job->id = $DB->insert_record('offlinequiz_queue', $job);
foreach ($files as $f) {
    $target = $dir . '/' . basename($f);
    copy($f, $target);
    $DB->insert_record('offlinequiz_queue_data', (object)['queueid' => $job->id, 'filename' => $target, 'status' => 'new']);
}
$DB->set_field('offlinequiz_queue', 'status', 'new', ['id' => $job->id]);
echo json_encode(['queueid' => (int)$job->id, 'files' => count($files)]), "\n";
