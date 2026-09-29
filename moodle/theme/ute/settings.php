<?php
defined('MOODLE_INTERNAL') || die();

if ($ADMIN->fulltree) {
    $settings = new theme_boost_admin_settingspage_tabs('themesettingute', get_string('configtitle', 'theme_ute'));
    $page = new admin_settingpage('theme_ute_general', get_string('generalsettings', 'theme_ute'));

    $s = new admin_setting_configcolourpicker('theme_ute/brandcolor', get_string('brandcolor', 'theme_ute'),
        get_string('brandcolor_desc', 'theme_ute'), '#0b3d91');
    $s->set_updatedcallback('theme_reset_all_caches'); $page->add($s);
    $s = new admin_setting_configcolourpicker('theme_ute/accentcolor', get_string('accentcolor', 'theme_ute'),
        get_string('accentcolor_desc', 'theme_ute'), '#f5a623');
    $s->set_updatedcallback('theme_reset_all_caches'); $page->add($s);
    $page->add(new admin_setting_configtext('theme_ute/herotitle', get_string('herotitle', 'theme_ute'), '', ''));
    $page->add(new admin_setting_confightmleditor('theme_ute/herotext', get_string('herotext', 'theme_ute'), '', ''));
    $page->add(new admin_setting_configtext('theme_ute/logintitle', get_string('logintitle', 'theme_ute'), '', ''));
    $s = new admin_setting_scsscode('theme_ute/scss', get_string('rawscss', 'theme_ute'), get_string('rawscss_desc', 'theme_ute'), '', PARAM_RAW);
    $s->set_updatedcallback('theme_reset_all_caches'); $page->add($s);

    $settings->add($page);
}
