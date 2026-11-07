<?php
namespace local_clo;

defined('MOODLE_INTERNAL') || die();

/**
 * Nút "Phân tích CĐR" trên thanh điều hướng chính của Moodle – chỉ hiện với giảng viên / quản trị;
 * gợi ý đọc dưới từng câu làm sai ở trang xem lại bài Quiz.
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

    public static function before_footer(\core\hook\output\before_footer_html_generation $hook): void {
        global $CFG, $PAGE;
        if (during_initial_install() || $PAGE->pagetype !== 'mod-quiz-review') {
            return;
        }
        require_once($CFG->dirroot . '/local/clo/lib.php');
        try {
            $hook->add_html(local_clo_review_readings((int)$PAGE->url->get_param('attempt')));
        } catch (\Throwable $e) {     // gợi ý đọc không được làm hỏng trang xem lại bài
            debugging('local_clo: ' . $e->getMessage(), DEBUG_DEVELOPER);
        }
    }
}
