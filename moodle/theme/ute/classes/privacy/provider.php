<?php
namespace theme_ute\privacy;

defined('MOODLE_INTERNAL') || die();

/** Giao diện UTE không lưu dữ liệu cá nhân. */
class provider implements \core_privacy\local\metadata\null_provider {
    public static function get_reason(): string {
        return 'privacy:metadata';
    }
}
