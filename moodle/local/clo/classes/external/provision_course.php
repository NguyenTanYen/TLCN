<?php
namespace local_clo\external;

defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * Tạo khóa học trên Moodle cho một lớp học phần của hệ thống và ghi danh giảng viên + sinh viên.
 * - Tìm khóa học theo idnumber (mã lớp) rồi theo shortname; chưa có thì tạo mới. Gọi lại thì chỉ bổ sung người còn thiếu.
 * - Người dùng chưa có tài khoản Moodle (theo tên đăng nhập) được tạo mới, phương thức đăng nhập "manual";
 *   mật khẩu ban đầu do hệ thống truyền sang (người dùng đã có thì không đổi mật khẩu).
 * - Ghi danh bằng phương thức "manual": giảng viên = editingteacher, sinh viên = student.
 * Trả về id khóa học và id người dùng Moodle của từng tên đăng nhập để hệ thống lưu lại (mdl_user.id).
 */
class provision_course extends external_api {

    private static function person_structure(): external_single_structure {
        return new external_single_structure([
            'username' => new external_value(PARAM_RAW, 'Tên đăng nhập (MSSV / mã GV)'),
            'firstname' => new external_value(PARAM_TEXT, 'Tên'),
            'lastname' => new external_value(PARAM_TEXT, 'Họ và tên đệm'),
            'email' => new external_value(PARAM_RAW, 'Thư điện tử', VALUE_DEFAULT, ''),
            'idnumber' => new external_value(PARAM_RAW, 'Mã số (MSSV)', VALUE_DEFAULT, ''),
        ]);
    }

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'shortname' => new external_value(PARAM_TEXT, 'Tên rút gọn khóa học = mã lớp học phần'),
            'fullname' => new external_value(PARAM_TEXT, 'Tên đầy đủ khóa học'),
            'idnumber' => new external_value(PARAM_RAW, 'Mã khóa học (idnumber) = mã lớp học phần', VALUE_DEFAULT, ''),
            'categoryid' => new external_value(PARAM_INT, 'Danh mục khóa học (0 = danh mục mặc định)', VALUE_DEFAULT, 0),
            'startdate' => new external_value(PARAM_INT, 'Ngày bắt đầu (unix, 0 = hôm nay)', VALUE_DEFAULT, 0),
            'newuserpassword' => new external_value(PARAM_RAW, 'Mật khẩu ban đầu cho tài khoản mới tạo', VALUE_DEFAULT, ''),
            'teachers' => new external_multiple_structure(self::person_structure(), 'Giảng viên', VALUE_DEFAULT, []),
            'students' => new external_multiple_structure(self::person_structure(), 'Sinh viên', VALUE_DEFAULT, []),
        ]);
    }

    private static function ensure_user(array $p, string $password, int &$created): int {
        global $DB, $CFG;
        require_once($CFG->dirroot . '/user/lib.php');
        $username = \core_text::strtolower(trim($p['username']));
        if ($username === '') {
            return 0;
        }
        $u = $DB->get_record('user', ['username' => $username, 'mnethostid' => $CFG->mnet_localhost_id, 'deleted' => 0]);
        if ($u) {
            return (int)$u->id;
        }
        $email = trim($p['email']);
        if ($email === '' || !validate_email($email) || $DB->record_exists('user', ['email' => $email, 'deleted' => 0])) {
            $email = preg_replace('/[^a-z0-9._-]/', '', $username) . '@example.com';   // email là bắt buộc; GV/SV đổi sau
        }
        $user = (object)[
            'username' => $username, 'auth' => 'manual', 'confirmed' => 1, 'mnethostid' => $CFG->mnet_localhost_id,
            'firstname' => $p['firstname'] !== '' ? $p['firstname'] : $username, 'lastname' => $p['lastname'] !== '' ? $p['lastname'] : '-',
            'email' => $email, 'idnumber' => trim($p['idnumber']), 'lang' => $CFG->lang,
            'password' => $password !== '' ? $password : random_string(20) . 'Aa1!',
        ];
        $id = user_create_user($user, true, false);
        $created++;
        return (int)$id;
    }

    public static function execute($shortname, $fullname, $idnumber = '', $categoryid = 0, $startdate = 0,
                                   $newuserpassword = '', $teachers = [], $students = []): array {
        global $CFG, $DB;
        require_once($CFG->dirroot . '/course/lib.php');
        require_once($CFG->libdir . '/enrollib.php');
        $p = self::validate_parameters(self::execute_parameters(), compact('shortname', 'fullname', 'idnumber', 'categoryid',
            'startdate', 'newuserpassword', 'teachers', 'students'));
        $sys = \context_system::instance();
        self::validate_context($sys);
        require_capability('local/clo:manage', $sys);
        require_capability('moodle/course:create', $sys);
        require_capability('moodle/user:create', $sys);

        $course = null;
        if ($p['idnumber'] !== '') {
            $course = $DB->get_record('course', ['idnumber' => $p['idnumber']]);
        }
        if (!$course) {
            $course = $DB->get_record('course', ['shortname' => $p['shortname']]);
        }
        $createdcourse = false;
        if (!$course) {
            $cat = $p['categoryid'] ?: (int)$DB->get_field_select('course_categories', 'MIN(id)', 'parent = 0');
            $data = (object)['fullname' => $p['fullname'], 'shortname' => $p['shortname'], 'idnumber' => $p['idnumber'],
                'category' => $cat, 'format' => 'topics', 'numsections' => 8, 'visible' => 1,
                'startdate' => $p['startdate'] ?: time(), 'summary' => '', 'summaryformat' => FORMAT_HTML];
            $course = create_course($data);
            $createdcourse = true;
        }
        $context = \context_course::instance($course->id);
        $manual = enrol_get_plugin('manual');
        $instance = $DB->get_record('enrol', ['courseid' => $course->id, 'enrol' => 'manual'], '*', IGNORE_MULTIPLE);
        if (!$instance) {
            $manual->add_default_instance($course);
            $instance = $DB->get_record('enrol', ['courseid' => $course->id, 'enrol' => 'manual'], '*', MUST_EXIST);
        }
        $roleids = [
            'editingteacher' => (int)$DB->get_field('role', 'id', ['shortname' => 'editingteacher'], MUST_EXIST),
            'student' => (int)$DB->get_field('role', 'id', ['shortname' => 'student'], MUST_EXIST),
        ];
        $usersmade = 0;
        $enrolled = 0;
        $map = [];
        foreach (['editingteacher' => $p['teachers'], 'student' => $p['students']] as $role => $people) {
            foreach ($people as $person) {
                $uid = self::ensure_user($person, $p['newuserpassword'], $usersmade);
                if (!$uid) {
                    continue;
                }
                if (!is_enrolled($context, $uid)) {
                    $manual->enrol_user($instance, $uid, $roleids[$role]);
                    $enrolled++;
                } else if (!user_has_role_assignment($uid, $roleids[$role], $context->id)) {
                    role_assign($roleids[$role], $uid, $context->id);
                }
                $map[] = ['username' => \core_text::strtolower(trim($person['username'])), 'userid' => $uid];
            }
        }
        return ['courseid' => (int)$course->id, 'created' => $createdcourse, 'usersmade' => $usersmade,
                'enrolled' => $enrolled, 'users' => $map];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'courseid' => new external_value(PARAM_INT, 'mdl_course.id'),
            'created' => new external_value(PARAM_BOOL, 'Khóa học vừa được tạo mới'),
            'usersmade' => new external_value(PARAM_INT, 'Số tài khoản Moodle mới tạo'),
            'enrolled' => new external_value(PARAM_INT, 'Số lượt ghi danh mới'),
            'users' => new external_multiple_structure(new external_single_structure([
                'username' => new external_value(PARAM_RAW, 'Tên đăng nhập'),
                'userid' => new external_value(PARAM_INT, 'mdl_user.id'),
            ])),
        ]);
    }
}
