<?php
namespace local_clo\external;

defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * Bài thi GIẤY qua API: hệ thống phân tích chỉ soạn đề; Moodle (plugin Offline Quiz – mod_offlinequiz) sinh đề in,
 * phiếu trả lời, nhận diện phiếu quét và chấm điểm. Hàm này:
 *  1. nhập đề (Moodle XML, idnumber QB-n) vào ngân hàng câu hỏi của khóa học;
 *  2. tạo Offline Quiz với N nhóm đề (A, B, C…), xáo trộn câu và/hoặc phương án theo từng nhóm;
 *  3. sinh sẵn tệp đề thi, phiếu trả lời và đáp án của từng nhóm để hệ thống tải về cho giảng viên in.
 * Gọi lại với cùng examref trả về Offline Quiz đã tạo (không tạo trùng).
 */
class create_offlinequiz extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'Khóa học Moodle'),
            'examref' => new external_value(PARAM_INT, 'Mã bài kiểm tra bên hệ thống phân tích (exams.id)'),
            'name' => new external_value(PARAM_TEXT, 'Tên bài thi'),
            'questionsxml' => new external_value(PARAM_RAW, 'Nội dung tệp Moodle XML'),
            'grade' => new external_value(PARAM_FLOAT, 'Thang điểm', VALUE_DEFAULT, 10),
            'numgroups' => new external_value(PARAM_INT, 'Số nhóm đề (mã đề) 1–6', VALUE_DEFAULT, 2),
            'shufflequestions' => new external_value(PARAM_BOOL, 'Xáo trộn thứ tự câu giữa các nhóm', VALUE_DEFAULT, true),
            'shuffleanswers' => new external_value(PARAM_BOOL, 'Xáo trộn phương án', VALUE_DEFAULT, true),
            'examdate' => new external_value(PARAM_INT, 'Ngày thi (unix, 0 = không ghi)', VALUE_DEFAULT, 0),
            'fileformat' => new external_value(PARAM_INT, 'Định dạng đề: 0 = PDF, 1 = DOCX', VALUE_DEFAULT, 0),
            'pdfintro' => new external_value(PARAM_RAW, 'Lời dặn in đầu đề thi (HTML)', VALUE_DEFAULT, ''),
        ]);
    }

    public static function execute($courseid, $examref, $name, $questionsxml, $grade = 10, $numgroups = 2,
            $shufflequestions = true, $shuffleanswers = true, $examdate = 0, $fileformat = 0, $pdfintro = ''): array {
        global $CFG, $DB;
        require_once($CFG->dirroot . '/course/modlib.php');

        $p = self::validate_parameters(self::execute_parameters(), compact('courseid', 'examref', 'name', 'questionsxml',
            'grade', 'numgroups', 'shufflequestions', 'shuffleanswers', 'examdate', 'fileformat', 'pdfintro'));
        if (!\core_component::get_component_directory('mod_offlinequiz')) {
            throw new \moodle_exception('nooffline', 'local_clo');
        }
        require_once($CFG->dirroot . '/mod/offlinequiz/locallib.php');
        require_once($CFG->dirroot . '/mod/offlinequiz/pdflib.php');

        $course = get_course($p['courseid']);
        $context = \context_course::instance($course->id);
        self::validate_context($context);
        require_capability('local/clo:manage', $context);
        require_capability('moodle/course:manageactivities', $context);
        require_capability('moodle/question:add', $context);
        if ($p['numgroups'] < 1 || $p['numgroups'] > 6) {
            throw new \invalid_parameter_exception('numgroups phải từ 1 đến 6');
        }

        // Đã tạo trước đó -> trả lại (idempotent).
        $exam = $DB->get_record('local_clo_exam', ['examref' => $p['examref']]);
        if ($exam && !empty($exam->offlinequizid) &&
                ($cm = get_coursemodule_from_instance('offlinequiz', $exam->offlinequizid, 0, false, IGNORE_MISSING))) {
            return self::describe($exam->offlinequizid, $cm, false);
        }

        // Mọi bước trong một giao dịch: lỗi giữa chừng không để lại Offline Quiz dở dang.
        $tx = $DB->start_delegated_transaction();

        // 1. Nhập câu hỏi.
        $questionids = \local_clo\question_importer::import($course, $p['questionsxml']);

        // 2. Tạo Offline Quiz.
        $config = get_config('offlinequiz');
        $mod = (object)[
            'modulename' => 'offlinequiz', 'course' => $course->id, 'section' => 0, 'visible' => 1,
            'name' => $p['name'], 'introeditor' => ['text' => '', 'format' => FORMAT_HTML, 'itemid' => 0],
            'pdfintro' => $p['pdfintro'],
            'time' => $p['examdate'], 'timeopen' => 0, 'timeclose' => 0,
            'numgroups' => $p['numgroups'], 'shufflequestions' => (int)$p['shufflequestions'],
            'shuffleanswers' => (int)$p['shuffleanswers'], 'participantsusage' => 0, 'showtutorial' => 0,
            'decimalpoints' => 2, 'questionsperpage' => 0, 'experimentalevaluation' => 0,
            'pdffont' => offlinequiz_get_pdffont(), 'papergray' => $config->papergray ?? 650,
            'printstudycodefield' => 1, 'fontsize' => $config->defaultpdffontsize ?? 10,
            'fileformat' => $p['fileformat'] ? 1 : 0, 'showgrades' => 0, 'showquestioninfo' => 0,
            'disableimgnewlines' => 0, 'grade' => $p['grade'],
            // SV xem điểm và phiếu đã chấm trên Moodle sau khi GV cho phép xem lại.
            'attemptclosed' => 1, 'marksclosed' => 1, 'correctnessclosed' => 1, 'gradedsheetclosed' => 1,
        ];
        $modinfo = create_module($mod);
        $oq = $DB->get_record('offlinequiz', ['id' => $modinfo->instance], '*', MUST_EXIST);
        $oq->cmid = $modinfo->coursemodule;
        offlinequiz_set_grade($p['grade'], $oq);

        // 3. Thêm cùng bộ câu hỏi vào mọi nhóm (mỗi nhóm được Moodle xáo trộn riêng khi sinh đề).
        $marks = \local_clo\question_importer::marks($p['questionsxml']);
        $maxmarks = [];
        foreach ($questionids as $i => $qid) {
            $maxmarks[$qid] = $marks[$i] ?? $DB->get_field('question', 'defaultmark', ['id' => $qid]);
        }
        $groups = $DB->get_records('offlinequiz_groups', ['offlinequizid' => $oq->id], 'groupnumber');
        foreach ($groups as $g) {
            offlinequiz_add_questionlist_to_group($questionids, $oq, $g, null, $maxmarks);
            offlinequiz_update_sumgrades($oq, $g->id);
        }

        // 4. Sinh tệp đề thi, phiếu trả lời, đáp án của từng nhóm (như trang "Tạo biểu mẫu" của Offline Quiz).
        self::create_documents($oq, $course);

        // 5. Ghi nhận liên kết bài KT <-> Offline Quiz.
        $now = time();
        if ($exam) {
            $exam->courseid = $course->id; $exam->offlinequizid = $oq->id; $exam->title = $p['name'];
            $exam->timemodified = $now;
            $DB->update_record('local_clo_exam', $exam);
        } else {
            $DB->insert_record('local_clo_exam', (object)['examref' => $p['examref'], 'courseid' => $course->id,
                'offlinequizid' => $oq->id, 'title' => $p['name'], 'published' => 0,
                'timecreated' => $now, 'timemodified' => $now]);
        }
        $tx->allow_commit();
        return self::describe($oq->id, get_coursemodule_from_id('offlinequiz', $modinfo->coursemodule), true);
    }

    /** Sinh tệp PDF/DOCX cho mọi nhóm (một lần). */
    public static function create_documents(\stdClass $oq, \stdClass $course): void {
        global $CFG, $DB;
        $cm = get_coursemodule_from_instance('offlinequiz', $oq->id, $course->id, false, MUST_EXIST);
        $context = \context_module::instance($cm->id);
        $oq->cmid = $cm->id;
        if ($oq->docscreated) {
            return;
        }
        $DB->set_field('offlinequiz', 'id_digits', get_config('offlinequiz', 'ID_digits'), ['id' => $oq->id]);
        // Đề/phiếu in theo ngôn ngữ mặc định của site (tiếng Việt), không theo ngôn ngữ của tài khoản gọi API.
        $lang = get_string_manager()->translation_exists($CFG->lang) ? $CFG->lang : 'en';
        force_current_language($lang);
        foreach ($DB->get_records('offlinequiz_groups', ['offlinequizid' => $oq->id], 'groupnumber') as $group) {
            $usage = offlinequiz_get_group_template_usage($oq, $group, $context);
            if ($oq->fileformat == OFFLINEQUIZ_DOCX_FORMAT) {
                require_once($CFG->dirroot . '/mod/offlinequiz/docxlib.php');
                $qfile = offlinequiz_create_docx_question($usage, $oq, $group, $course->id, $context);
            } else {
                $qfile = offlinequiz_create_pdf_question($usage, $oq, $group, $course->id, $context);
            }
            $afile = offlinequiz_create_pdf_answer(offlinequiz_get_maxanswers($oq, [$group]), $usage, $oq, $group,
                $course->id, $context);
            $cfile = offlinequiz_create_pdf_question($usage, $oq, $group, $course->id, $context, true);
            $group->questionfilename = $qfile ? $qfile->get_filename() : null;
            $group->answerfilename = $afile ? $afile->get_filename() : null;
            $group->correctionfilename = $cfile ? $cfile->get_filename() : null;
            $DB->update_record('offlinequiz_groups', $group);
        }
        $DB->set_field('offlinequiz', 'docscreated', 1, ['id' => $oq->id]);
        force_current_language('');
    }

    /** Thông tin Offline Quiz + đường dẫn tải tệp qua webservice/pluginfile.php (cần token). */
    public static function describe(int $oqid, \stdClass $cm, bool $created): array {
        global $DB, $CFG;
        $context = \context_module::instance($cm->id);
        $fs = get_file_storage();
        $letters = 'ABCDEFGHIJKL';
        $groups = [];
        foreach ($DB->get_records('offlinequiz_groups', ['offlinequizid' => $oqid], 'groupnumber') as $g) {
            $files = [];
            foreach (['question' => $g->questionfilename, 'answer' => $g->answerfilename,
                    'correction' => $g->correctionfilename] as $kind => $fname) {
                if ($fname && ($f = $fs->get_file($context->id, 'mod_offlinequiz', 'pdfs', 0, '/', $fname))) {
                    $files[] = ['kind' => $kind, 'filename' => $fname, 'filesize' => (int)$f->get_filesize(),
                        'mimetype' => $f->get_mimetype(),
                        'url' => $CFG->wwwroot . '/webservice/pluginfile.php/' . $context->id . '/mod_offlinequiz/pdfs/0/' .
                            rawurlencode($fname)];
                }
            }
            $groups[] = ['letter' => $letters[$g->groupnumber - 1], 'groupnumber' => (int)$g->groupnumber,
                'questions' => (int)$DB->count_records('offlinequiz_group_questions', ['offlinegroupid' => $g->id]),
                'files' => $files];
        }
        return ['offlinequizid' => $oqid, 'cmid' => (int)$cm->id, 'courseid' => (int)$cm->course,
            'url' => (new \moodle_url('/mod/offlinequiz/view.php', ['id' => $cm->id]))->out(false),
            'created' => $created, 'groups' => $groups,
            'results' => (int)$DB->count_records('offlinequiz_results', ['offlinequizid' => $oqid, 'status' => 'complete']),
            'pending' => (int)$DB->count_records_sql("SELECT COUNT(*) FROM {offlinequiz_queue_data} d
                    JOIN {offlinequiz_queue} q ON q.id = d.queueid WHERE q.offlinequizid = ? AND q.status IN ('new', 'processing')",
                    [$oqid]),
            'errorpages' => (int)$DB->count_records_select('offlinequiz_scanned_pages',
                    "offlinequizid = ? AND status IN ('error', 'suspended')", [$oqid]),
            'correcturl' => (new \moodle_url('/mod/offlinequiz/report.php', ['id' => $cm->id, 'mode' => 'correct']))->out(false),
            'uploadurl' => (new \moodle_url('/mod/offlinequiz/report.php', ['id' => $cm->id, 'mode' => 'rimport']))->out(false)];
    }

    public static function execute_returns(): external_single_structure {
        return self::describe_returns();
    }

    public static function describe_returns(): external_single_structure {
        return new external_single_structure([
            'offlinequizid' => new external_value(PARAM_INT, 'mdl_offlinequiz.id'),
            'cmid' => new external_value(PARAM_INT, 'course module id'),
            'courseid' => new external_value(PARAM_INT, 'khóa học'),
            'url' => new external_value(PARAM_URL, 'trang Offline Quiz trên Moodle'),
            'created' => new external_value(PARAM_BOOL, 'true nếu vừa tạo mới'),
            'results' => new external_value(PARAM_INT, 'số bài đã chấm xong trên Moodle'),
            'pending' => new external_value(PARAM_INT, 'số ảnh phiếu đang chờ chấm'),
            'errorpages' => new external_value(PARAM_INT, 'số phiếu Moodle chưa nhận diện được, cần GV sửa'),
            'correcturl' => new external_value(PARAM_URL, 'trang sửa lỗi phiếu trên Moodle'),
            'uploadurl' => new external_value(PARAM_URL, 'trang tải lên ảnh phiếu đã quét'),
            'groups' => new external_multiple_structure(new external_single_structure([
                'letter' => new external_value(PARAM_ALPHA, 'nhóm đề A, B, C…'),
                'groupnumber' => new external_value(PARAM_INT, 'số thứ tự nhóm'),
                'questions' => new external_value(PARAM_INT, 'số câu của nhóm'),
                'files' => new external_multiple_structure(new external_single_structure([
                    'kind' => new external_value(PARAM_ALPHA, 'question | answer | correction'),
                    'filename' => new external_value(PARAM_FILE, 'tên tệp'),
                    'filesize' => new external_value(PARAM_INT, 'kích thước'),
                    'mimetype' => new external_value(PARAM_RAW, 'kiểu tệp'),
                    'url' => new external_value(PARAM_URL, 'tải qua webservice/pluginfile.php?token=…'),
                ])),
            ])),
        ]);
    }
}
