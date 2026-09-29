<?php
defined('MOODLE_INTERNAL') || die();

if ($hassiteconfig) {
    $settings = new admin_settingpage('local_clo', get_string('pluginname', 'local_clo'));
    $settings->add(new admin_setting_configtext('local_clo/appurl', get_string('appurl', 'local_clo'),
        get_string('appurl_desc', 'local_clo'), 'http://localhost:8000', PARAM_URL));
    $settings->add(new admin_setting_configpasswordunmask('local_clo/ssosecret', get_string('ssosecret', 'local_clo'),
        get_string('ssosecret_desc', 'local_clo'), ''));
    $ADMIN->add('localplugins', $settings);
}
