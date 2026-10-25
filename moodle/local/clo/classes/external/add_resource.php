<?php
namespace local_clo\external;

defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * Đẩy một học liệu (PDF, PPTX, DOCX…) từ hệ thống phân tích lên khóa học Moodle thành hoạt động "Tệp" (mod_resource),
 * để sinh viên xem trên Moodle và hệ thống chỉ gợi ý dựa trên đúng những gì đã đưa lên khóa học.
 * Gọi lại với cùng tên tệp trong cùng chủ đề thì không tạo trùng (trả về hoạt động đã có).
 */
class add_resource extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'Khóa học Moodle'),
            'name' => new external_value(PARAM_TEXT, 'Tên hiển thị của tài nguyên'),
            'filename' => new external_value(PARAM_FILE, 'Tên tệp, ví dụ slide_chuong_3.pptx'),
            'content' => new external_value(PARAM_RAW, 'Nội dung tệp mã hóa base64'),
            'section' => new external_value(PARAM_INT, 'Số thứ tự chủ đề (tuần) trong khóa học; 0 = chủ đề đầu', VALUE_DEFAULT, 0),
            'intro' => new external_value(PARAM_RAW, 'Mô tả ngắn (HTML)', VALUE_DEFAULT, ''),
        ]);
    }

    public static function execute($courseid, $name, $filename, $content, $section = 0, $intro = ''): array {
        global $CFG, $DB, $USER;
        require_once($CFG->dirroot . '/course/modlib.php');
        require_once($CFG->dirroot . '/mod/resource/lib.php');
        require_once($CFG->dirroot . '/lib/resourcelib.php');

        $p = self::validate_parameters(self::execute_parameters(), compact('courseid', 'name', 'filename', 'content', 'section', 'intro'));
        $course = get_course($p['courseid']);
        $context = \context_course::instance($course->id);
        self::validate_context($context);
        require_capability('local/clo:manage', $context);
        require_capability('moodle/course:manageactivities', $context);

        $bytes = base64_decode($p['content'], true);
        if ($bytes === false || $bytes === '') {
            throw new \invalid_parameter_exception('content phải là base64 hợp lệ và không rỗng');
        }
        $filename = clean_param($p['filename'], PARAM_FILE);

        // Đã có tài nguyên cùng tên tệp trong khóa học → không tạo trùng.
        $sql = "SELECT cm.id FROM {course_modules} cm
                  JOIN {modules} m ON m.id = cm.module AND m.name = 'resource'
                  JOIN {context} ctx ON ctx.instanceid = cm.id AND ctx.contextlevel = :lvl
                  JOIN {files} f ON f.contextid = ctx.id AND f.component = 'mod_resource' AND f.filearea = 'content'
                       AND f.filename = :fn AND f.filesize > 0
                 WHERE cm.course = :cid AND cm.deletioninprogress = 0";
        $exist = $DB->get_record_sql($sql, ['lvl' => CONTEXT_MODULE, 'fn' => $filename, 'cid' => $course->id], IGNORE_MULTIPLE);
        if ($exist) {
            return ['cmid' => (int)$exist->id, 'created' => false,
                    'url' => (new \moodle_url('/mod/resource/view.php', ['id' => $exist->id]))->out(false)];
        }

        // Tệp nháp trong khu vực của tài khoản dịch vụ, rồi tạo hoạt động từ tệp nháp đó.
        $usercontext = \context_user::instance($USER->id);
        $draftid = file_get_unused_draft_itemid();
        get_file_storage()->create_file_from_string([
            'contextid' => $usercontext->id, 'component' => 'user', 'filearea' => 'draft',
            'itemid' => $draftid, 'filepath' => '/', 'filename' => $filename], $bytes);

        $mi = new \stdClass();
        $mi->modulename = 'resource';
        $mi->module = $DB->get_field('modules', 'id', ['name' => 'resource'], MUST_EXIST);
        $mi->course = $course->id;
        $mi->section = max(0, (int)$p['section']);
        $mi->visible = 1;
        $mi->visibleoncoursepage = 1;
        $mi->name = $p['name'];
        $mi->introeditor = ['text' => $p['intro'], 'format' => FORMAT_HTML, 'itemid' => 0];
        $mi->showdescription = 0;
        $mi->files = $draftid;
        $mi->display = RESOURCELIB_DISPLAY_AUTO;
        $mi->showsize = 0;
        $mi->showtype = 0;
        $mi->showdate = 0;
        $mi->popupwidth = 620;
        $mi->popupheight = 450;
        $mi->filterfiles = 0;
        $mi->printintro = 0;
        $mi->cmidnumber = '';
        $mi = create_module($mi);
        return ['cmid' => (int)$mi->coursemodule, 'created' => true,
                'url' => (new \moodle_url('/mod/resource/view.php', ['id' => $mi->coursemodule]))->out(false)];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'cmid' => new external_value(PARAM_INT, 'course module id của Tài nguyên'),
            'created' => new external_value(PARAM_BOOL, 'true = vừa tạo mới, false = đã có sẵn'),
            'url' => new external_value(PARAM_RAW, 'Địa chỉ xem tài nguyên trên Moodle'),
        ]);
    }
}
