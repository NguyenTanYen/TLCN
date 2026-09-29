<?php
namespace local_clo;

defined('MOODLE_INTERNAL') || die();

/**
 * Nút "Phân tích CĐR" trên thanh điều hướng chính của Moodle – chỉ hiện với giảng viên / quản trị.
 */
class hook_callbacks {
    public static function primary_extend(\core\hook\navigation\primary_extend $hook): void {
        global $CFG;
        require_once($CFG->dirroot . '/local/clo/lib.php');
        if (during_initial_install() || !local_clo_can_launch()) {
            return;
        }
        $hook->get_primaryview()->add(get_string('menu', 'local_clo'), new \moodle_url('/local/clo/launch.php'),
            \navigation_node::TYPE_CUSTOM, null, 'local_clo_launch', new \pix_icon('i/stats', ''));
    }
}
