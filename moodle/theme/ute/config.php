<?php
defined('MOODLE_INTERNAL') || die();
require_once(__DIR__ . '/lib.php');

$THEME->name = 'ute';
$THEME->parents = ['boost'];
$THEME->sheets = [];
$THEME->editor_sheets = [];
$THEME->editor_scss = ['editor'];
$THEME->usefallback = true;
$THEME->scss = function($theme) {
    return theme_ute_get_main_scss_content($theme);
};
$THEME->prescsscallback = 'theme_ute_get_pre_scss';
$THEME->extrascsscallback = 'theme_ute_get_extra_scss';

$drawer = ['file' => 'drawers.php', 'regions' => ['side-pre'], 'defaultregion' => 'side-pre'];
$THEME->layouts = [
    'base' => ['file' => 'drawers.php', 'regions' => []],
    'standard' => $drawer,
    'course' => $drawer + ['options' => ['langmenu' => true]],
    'coursecategory' => $drawer,
    'incourse' => $drawer,
    // Trang chủ: có banner giới thiệu hệ thống và số liệu thống kê.
    'frontpage' => ['file' => 'frontpage.php', 'regions' => ['side-pre'], 'defaultregion' => 'side-pre',
        'options' => ['nonavbar' => true]],
    'admin' => $drawer,
    'mycourses' => $drawer + ['options' => ['nonavbar' => true]],
    // Bảng điều khiển: thêm dải lối tắt tới hệ thống phân tích CĐR.
    'mydashboard' => ['file' => 'frontpage.php', 'regions' => ['side-pre'], 'defaultregion' => 'side-pre',
        'options' => ['nonavbar' => true, 'langmenu' => true]],
    'mypublic' => $drawer,
    // Trang đăng nhập hai cột.
    'login' => ['file' => 'login.php', 'regions' => [], 'options' => ['langmenu' => true]],
    'popup' => ['file' => 'columns1.php', 'regions' => [], 'options' => ['nofooter' => true, 'nonavbar' => true,
        'activityheader' => ['notitle' => true, 'nocompletion' => true, 'nodescription' => true]]],
    'frametop' => ['file' => 'columns1.php', 'regions' => [], 'options' => ['nofooter' => true, 'nocoursefooter' => true,
        'activityheader' => ['nocompletion' => true]]],
    'embedded' => ['file' => 'embedded.php', 'regions' => ['side-pre'], 'defaultregion' => 'side-pre'],
    'maintenance' => ['file' => 'maintenance.php', 'regions' => []],
    'print' => ['file' => 'columns1.php', 'regions' => [], 'options' => ['nofooter' => true, 'nonavbar' => false, 'noactivityheader' => true]],
    'redirect' => ['file' => 'embedded.php', 'regions' => []],
    'report' => $drawer,
    'secure' => ['file' => 'secure.php', 'regions' => ['side-pre'], 'defaultregion' => 'side-pre'],
];

$THEME->rendererfactory = 'theme_overridden_renderer_factory';
$THEME->requiredblocks = '';
$THEME->addblockposition = BLOCK_ADDBLOCK_POSITION_FLATNAV;
$THEME->iconsystem = \core\output\icon_system::FONTAWESOME;
$THEME->haseditswitch = true;
$THEME->usescourseindex = true;
$THEME->activityheaderconfig = ['notitle' => true];
