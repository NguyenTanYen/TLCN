<?php
// Kiểm tra nút "Phân tích CĐR" từ dòng lệnh: phát vé SSO cho một giảng viên rồi gọi thử hệ thống phân tích.
//   php local/clo/cli/testsso.php --username=gv.son [--courseid=3]
define('CLI_SCRIPT', true);
require(__DIR__ . '/../../../config.php');
require_once($CFG->libdir . '/clilib.php');
require_once(__DIR__ . '/../lib.php');

[$o] = cli_get_params(['username' => 'gv.son', 'courseid' => 0]);
$user = $DB->get_record('user', ['username' => $o['username'], 'deleted' => 0], '*', MUST_EXIST);
$url = local_clo_appurl() . '/api/auth/moodle-sso?token=' . rawurlencode(\local_clo\sso::make_token($user, (int)$o['courseid']));
cli_writeln('Dia chi he thong: ' . local_clo_appurl());
$html = @file_get_contents($url, false, stream_context_create(['http' => ['ignore_errors' => true, 'timeout' => 10]]));
if ($html === false) {
    cli_writeln('KHONG KET NOI DUOC toi he thong phan tich - hay chay 5_CHAY_HE_THONG.bat');
    exit(1);
}
$status = $http_response_header[0] ?? '';
$text = trim(preg_replace('/\s+/', ' ', strip_tags(preg_replace('#<(script|style)[^>]*>.*?</\1>#s', '', $html))));
cli_writeln("HTTP: $status");
cli_writeln('Noi dung: ' . core_text::substr($text, 0, 200));
if (preg_match('/location\.replace\(("[^"]*")\)/', $html, $m)) {
    cli_writeln('DAT: SSO thanh cong, trinh duyet se vao ' . local_clo_appurl() . json_decode($m[1]));
}
