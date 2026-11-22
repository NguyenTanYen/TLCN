<?php
define('CLI_SCRIPT', true);
require(__DIR__ . '/../../../config.php');
require_once($CFG->libdir . '/clilib.php');

$lang = 'vi';
if (!get_string_manager()->translation_exists($lang)) {
    echo "Chua co goi ngon ngu {$lang}.\n";
    exit(1);
}

set_config('lang', $lang);
set_config('autolang', 0);
set_config('langmenu', 0);

$users = $DB->execute("UPDATE {user} SET lang = :l WHERE deleted = 0 AND lang <> :l2 AND username <> 'guest'", ['l' => $lang, 'l2' => $lang]);
$DB->execute("UPDATE {course} SET lang = '' WHERE lang <> ''");

$targets = [
    'quiz' => ['intro'],
    'offlinequiz' => ['intro'],
    'label' => ['intro'],
    'page' => ['intro', 'content'],
    'resource' => ['intro'],
    'course' => ['summary'],
    'course_sections' => ['summary'],
];
$cleared = 0;
$manager = $DB->get_manager();
foreach ($targets as $table => $fields) {
    if (!$manager->table_exists($table)) {
        continue;
    }
    foreach ($fields as $field) {
        $like = $DB->sql_like($field, ':p', false);
        $n = $DB->count_records_select($table, $like, ['p' => '%lorem ipsum%']);
        if ($n) {
            $DB->execute("UPDATE {{$table}} SET {$field} = '' WHERE " . $like, ['p' => '%lorem ipsum%']);
            $cleared += $n;
        }
    }
}
$custom = [
    'quiz' => ['summaryofattemptscaption' => 'Tóm tắt lần làm {$a}'],
    'qtype_multichoice' => ['selectone' => 'Chọn một đáp án:', 'correctansweris' => 'Đáp án đúng là: {$a}'],
];
$dir = $CFG->dataroot . '/lang/vi_local';
if (!is_dir($dir)) {
    mkdir($dir, 0775, true);
}
foreach ($custom as $component => $strings) {
    $body = "<?php\n";
    foreach ($strings as $key => $text) {
        $body .= '$string[' . var_export($key, true) . '] = ' . var_export($text, true) . ";\n";
    }
    file_put_contents("$dir/$component.php", $body);
}
purge_all_caches();
echo "Da dat tieng Viet cho nguoi dung va xoa {$cleared} doan noi dung mau (lorem ipsum).\n";
