<?php
// Cấu hình kết nối Moodle ⇄ hệ thống phân tích CĐR (chạy một lần sau khi cài plugin):
//   php local/clo/cli/setup.php --appurl=http://localhost:8000 --envfile="D:\3. TLCN\HeThong\backend\cau_hinh.env"
// 1. Bật Web Service + giao thức REST, bật dịch vụ "local_clo" và cấp token cho tài khoản quản trị.
// 2. Sinh khóa bí mật SSO (nếu chưa có), đặt địa chỉ hệ thống phân tích.
// 3. Ghi MOODLE_URL / MOODLE_WS_TOKEN / MOODLE_SSO_SECRET vào tệp cấu hình của hệ thống phân tích.
define('CLI_SCRIPT', true);
require(__DIR__ . '/../../../config.php');
require_once($CFG->libdir . '/clilib.php');

[$options, $unrecognized] = cli_get_params(['appurl' => 'http://localhost:8000', 'envfile' => '', 'help' => false], ['h' => 'help']);
if ($options['help']) {
    echo "php local/clo/cli/setup.php --appurl=http://localhost:8000 [--envfile=/duong/dan/cau_hinh.env]\n";
    exit(0);
}
\core\session\manager::set_user(get_admin());

set_config('appurl', rtrim($options['appurl'], '/'), 'local_clo');
$secret = (string)get_config('local_clo', 'ssosecret');
if (strlen($secret) < 32) {
    $secret = bin2hex(random_bytes(32));
    set_config('ssosecret', $secret, 'local_clo');
}

// Web Service + REST.
set_config('enablewebservices', 1);
$protocols = array_filter(explode(',', (string)get_config('core', 'webserviceprotocols')));
if (!in_array('rest', $protocols)) {
    $protocols[] = 'rest';
    set_config('webserviceprotocols', implode(',', $protocols));
}
$service = $DB->get_record('external_services', ['shortname' => 'local_clo'], '*', MUST_EXIST);
if (!$service->enabled) {
    $DB->set_field('external_services', 'enabled', 1, ['id' => $service->id]);
}
$admin = get_admin();
$token = $DB->get_field_select('external_tokens', 'token',
    'externalserviceid = ? AND userid = ? AND tokentype = ? AND (validuntil = 0 OR validuntil > ?)',
    [$service->id, $admin->id, EXTERNAL_TOKEN_PERMANENT, time()], IGNORE_MULTIPLE);
if (!$token) {
    $token = \core_external\util::generate_token(EXTERNAL_TOKEN_PERMANENT, $service, $admin->id,
        context_system::instance(), 0, '', 'He thong phan tich CDR');
}

// Theme cũ (phiên bản trước) từng thêm mục menu trỏ thẳng tới hệ thống – nay đã thay bằng nút có SSO.
$menu = (string)get_config('core', 'custommenuitems');
if (strpos($menu, 'Phân tích CĐR|http') !== false) {
    $lines = array_filter(preg_split('/\R/', $menu), fn($l) => strpos($l, 'Phân tích CĐR|http') !== 0);
    set_config('custommenuitems', implode("\n", $lines));
}

$values = ['MOODLE_URL' => $CFG->wwwroot, 'MOODLE_WS_TOKEN' => $token, 'MOODLE_SSO_SECRET' => $secret];
if ($options['envfile'] !== '') {
    $file = $options['envfile'];
    $lines = file_exists($file) ? preg_split('/\R/', rtrim(file_get_contents($file))) : [];
    foreach ($values as $k => $v) {
        $found = false;
        foreach ($lines as $i => $l) {
            if (strpos($l, $k . '=') === 0) {
                $lines[$i] = "$k=$v";
                $found = true;
            }
        }
        if (!$found) {
            $lines[] = "$k=$v";
        }
    }
    file_put_contents($file, implode(PHP_EOL, $lines) . PHP_EOL);
    cli_writeln("Da ghi cau hinh vao: $file");
}
purge_caches();
cli_writeln('MOODLE_URL=' . $CFG->wwwroot);
cli_writeln('MOODLE_WS_TOKEN=' . $token);
cli_writeln('MOODLE_SSO_SECRET=' . substr($secret, 0, 6) . '... (' . strlen($secret) . ' ky tu)');
cli_writeln('Dia chi he thong phan tich: ' . get_config('local_clo', 'appurl'));
