<?php
namespace local_clo\external;

defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * Đồng bộ ngân hàng câu hỏi HAI CHIỀU – chiều hệ thống → Moodle (góp ý 15/10).
 *
 * Mỗi câu mang idnumber QB-n (n = question_bank.id bên hệ thống):
 *  - chưa có trong ngân hàng câu hỏi của khóa học  -> tạo mới (danh mục mặc định của khóa học);
 *  - đã có và nội dung/phương án khác bản mới nhất   -> tạo PHIÊN BẢN MỚI (cơ chế phiên bản câu hỏi của Moodle 4.x,
 *    lượt làm bài cũ giữ nguyên phiên bản cũ);
 *  - giống hệt                                       -> giữ nguyên.
 * Câu GV soạn trực tiếp trên Moodle (chưa có idnumber) được hệ thống nhập về rồi gắn idnumber QB-n tại đây
 * (moodlequestionid > 0, không gửi phương án) để từ đó hai bên nhận ra nhau.
 * Chiều Moodle → hệ thống: hệ thống đọc bản mới nhất qua cầu nối CSDL chỉ đọc (xem routers/qsync.py).
 */
class sync_questions extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'Khóa học Moodle'),
            'questions' => new external_multiple_structure(new external_single_structure([
                'idnumber' => new external_value(PARAM_ALPHANUMEXT, 'QB-n'),
                'moodlequestionid' => new external_value(PARAM_INT, 'Câu có sẵn trên Moodle cần gắn idnumber (0 = không)', VALUE_DEFAULT, 0),
                'name' => new external_value(PARAM_TEXT, 'Tên câu', VALUE_DEFAULT, ''),
                'questiontext' => new external_value(PARAM_RAW, 'Nội dung (HTML)', VALUE_DEFAULT, ''),
                'defaultmark' => new external_value(PARAM_FLOAT, 'Điểm mặc định', VALUE_DEFAULT, 1),
                'answers' => new external_multiple_structure(new external_single_structure([
                    'text' => new external_value(PARAM_RAW, 'Nội dung phương án'),
                    'fraction' => new external_value(PARAM_FLOAT, '1 = đúng, 0 = sai'),
                ]), 'Phương án theo thứ tự gốc', VALUE_DEFAULT, []),
            ])),
        ]);
    }

    public static function execute($courseid, $questions): array {
        global $CFG, $DB;
        require_once($CFG->libdir . '/questionlib.php');
        $p = self::validate_parameters(self::execute_parameters(), compact('courseid', 'questions'));
        $course = get_course($p['courseid']);
        $context = \context_course::instance($course->id);
        self::validate_context($context);
        require_capability('local/clo:manage', $context);
        require_capability('moodle/question:add', $context);

        $contexts = new \core_question\local\bank\question_edit_contexts($context);
        $defaultcat = question_make_default_categories($contexts->all());
        $catids = $DB->get_fieldset_select('question_categories', 'id', 'contextid = ?', [$context->id]);
        $qtype = \question_bank::get_qtype('multichoice');
        $out = [];
        $tx = $DB->start_delegated_transaction();
        foreach ($p['questions'] as $q) {
            if (!preg_match('/^QB-\d+$/', $q['idnumber'])) {
                throw new \invalid_parameter_exception('idnumber phải có dạng QB-n');
            }
            $entry = self::entry($catids, $q['idnumber']);
            if ($q['moodlequestionid'] && !$q['answers']) {
                $out[] = self::tag($catids, $q['moodlequestionid'], $q['idnumber'], $entry);
                continue;
            }
            if (count(array_filter($q['answers'], fn($a) => trim($a['text']) !== '')) < 2) {
                throw new \invalid_parameter_exception("{$q['idnumber']}: cần ít nhất 2 phương án");
            }
            $old = null;
            if ($entry) {
                $old = $DB->get_record('question', ['id' => $entry->questionid], '*', MUST_EXIST);
                if ($old->qtype === 'multichoice' && self::same($old, $q)) {
                    $out[] = ['idnumber' => $q['idnumber'], 'questionid' => (int)$old->id, 'version' => (int)$entry->version,
                        'action' => 'unchanged'];
                    continue;
                }
            }
            $form = self::form($q, $entry ? $entry->questioncategoryid : $defaultcat->id, $context->id);
            $question = $old ? clone $old : new \stdClass();
            $question->qtype = 'multichoice';
            $question->category = $form->category;
            $saved = $qtype->save_question($question, $form);
            $v = $DB->get_record('question_versions', ['questionid' => $saved->id], 'version', MUST_EXIST);
            $out[] = ['idnumber' => $q['idnumber'], 'questionid' => (int)$saved->id, 'version' => (int)$v->version,
                'action' => $old ? 'updated' : 'created'];
        }
        $tx->allow_commit();
        return ['results' => $out];
    }

    /** Bản mới nhất của câu mang idnumber trong các danh mục của khóa học. */
    private static function entry(array $catids, string $idnumber) {
        global $DB;
        if (!$catids) {
            return null;
        }
        [$in, $params] = $DB->get_in_or_equal($catids, SQL_PARAMS_NAMED);
        $params['idn'] = $idnumber;
        $rows = $DB->get_records_sql("
            SELECT qbe.id, qbe.questioncategoryid, qv.questionid, qv.version
              FROM {question_bank_entries} qbe
              JOIN {question_versions} qv ON qv.questionbankentryid = qbe.id
             WHERE qbe.idnumber = :idn AND qbe.questioncategoryid $in
          ORDER BY qv.version DESC", $params, 0, 1);
        return $rows ? reset($rows) : null;
    }

    private static function tag(array $catids, int $questionid, string $idnumber, $existing): array {
        global $DB;
        $entry = get_question_bank_entry($questionid);
        if (!$entry || !in_array($entry->questioncategoryid, $catids)) {
            throw new \invalid_parameter_exception("Câu Moodle $questionid không thuộc ngân hàng câu hỏi của khóa học");
        }
        if ($existing && (int)$existing->id !== (int)$entry->id) {
            throw new \invalid_parameter_exception("$idnumber đã gắn cho câu khác trong khóa học");
        }
        $DB->set_field('question_bank_entries', 'idnumber', $idnumber, ['id' => $entry->id]);
        $v = $DB->get_field_sql('SELECT MAX(version) FROM {question_versions} WHERE questionbankentryid = ?', [$entry->id]);
        return ['idnumber' => $idnumber, 'questionid' => $questionid, 'version' => (int)$v, 'action' => 'tagged'];
    }

    private static function norm(string $s): string {
        return trim(preg_replace('/\s+/u', ' ', html_entity_decode(strip_tags($s), ENT_QUOTES | ENT_HTML5, 'UTF-8')));
    }

    /** Nội dung, điểm và phương án (thứ tự, đúng/sai) giống bản mới nhất trên Moodle? */
    private static function same($old, array $q): bool {
        global $DB;
        if (self::norm($old->questiontext) !== self::norm($q['questiontext']) || abs((float)$old->defaultmark - $q['defaultmark']) > 1e-6) {
            return false;
        }
        $ans = array_values($DB->get_records('question_answers', ['question' => $old->id], 'id ASC'));
        $new = array_values(array_filter($q['answers'], fn($a) => trim($a['text']) !== ''));
        if (count($ans) !== count($new)) {
            return false;
        }
        foreach ($new as $i => $a) {
            if (self::norm($ans[$i]->answer) !== self::norm($a['text']) || abs((float)$ans[$i]->fraction - $a['fraction']) > 1e-6) {
                return false;
            }
        }
        return true;
    }

    /** Dữ liệu như biểu mẫu soạn câu Nhiều lựa chọn (một đáp án) của Moodle. */
    private static function form(array $q, int $categoryid, int $contextid): \stdClass {
        $f = new \stdClass();
        $f->category = $categoryid . ',' . $contextid;
        $f->name = $q['name'] !== '' ? $q['name'] : $q['idnumber'];
        $f->idnumber = $q['idnumber'];
        $f->questiontext = ['text' => $q['questiontext'], 'format' => FORMAT_HTML];
        $f->generalfeedback = ['text' => '', 'format' => FORMAT_HTML];
        $f->defaultmark = $q['defaultmark'];
        $f->penalty = 0;
        $f->single = 1;
        $f->shuffleanswers = 1;
        $f->answernumbering = 'abc';
        $f->showstandardinstruction = 0;
        $f->shownumcorrect = 0;
        foreach (['correctfeedback', 'partiallycorrectfeedback', 'incorrectfeedback'] as $k) {
            $f->$k = ['text' => '', 'format' => FORMAT_HTML];
        }
        $f->answer = $f->fraction = $f->feedback = [];
        foreach (array_values($q['answers']) as $i => $a) {
            $f->answer[$i] = ['text' => $a['text'], 'format' => FORMAT_HTML];
            $f->fraction[$i] = (float)$a['fraction'];
            $f->feedback[$i] = ['text' => '', 'format' => FORMAT_HTML];
        }
        $f->status = \core_question\local\bank\question_version_status::QUESTION_STATUS_READY;
        return $f;
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'results' => new external_multiple_structure(new external_single_structure([
                'idnumber' => new external_value(PARAM_ALPHANUMEXT, 'QB-n'),
                'questionid' => new external_value(PARAM_INT, 'id câu (phiên bản mới nhất) trên Moodle'),
                'version' => new external_value(PARAM_INT, 'Số phiên bản'),
                'action' => new external_value(PARAM_ALPHA, 'created | updated | unchanged | tagged'),
            ])),
        ]);
    }
}
