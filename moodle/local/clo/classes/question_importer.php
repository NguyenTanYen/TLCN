<?php
namespace local_clo;

defined('MOODLE_INTERNAL') || die();

/**
 * Nhập tệp Moodle XML do hệ thống phân tích CĐR sinh ra (mỗi câu mang idnumber QB-n, phương án theo thứ tự gốc)
 * vào ngân hàng câu hỏi của khóa học. Dùng chung cho Quiz (thi online) và Offline Quiz (thi giấy).
 *
 * Câu đã có trong ngân hàng câu hỏi của khóa học (cùng idnumber QB-n) được DÙNG LẠI, không nhập trùng –
 * nếu nhập trùng, Moodle sẽ bỏ idnumber của bản sao và hệ thống không ánh xạ được bài làm về câu hỏi gốc.
 */
class question_importer {

    /**
     * @param \stdClass $course khóa học
     * @param string $xml nội dung Moodle XML
     * @return int[] id câu hỏi Moodle theo đúng thứ tự trong đề
     */
    public static function import(\stdClass $course, string $xml): array {
        $context = \context_course::instance($course->id);
        $order = self::idnumbers($xml);
        if (!$order) {   // tệp không do hệ thống sinh: không ánh xạ được bài làm về câu hỏi gốc
            throw new \moodle_exception('importnoidnumber', 'local_clo');
        }
        $existing = self::existing($context, $order);
        $missing = array_values(array_diff($order, array_keys($existing)));
        $imported = [];
        if ($missing) {
            self::run_import($course, $context, count($missing) === count($order) ? $xml : self::filter($xml, $missing));
            $imported = self::existing($context, $missing);
            if (count($imported) !== count($missing)) {
                throw new \moodle_exception('importnoidnumber', 'local_clo');
            }
        }
        $all = $existing + $imported;
        return array_map(fn($idn) => $all[$idn], $order);
    }

    /**
     * Điểm của từng câu trong đề (thẻ defaultgrade), theo thứ tự câu – dùng làm maxmark khi thêm vào Quiz/Offline Quiz,
     * vì câu dùng lại từ đề khác có thể mang điểm mặc định khác.
     * @return float[]
     */
    public static function marks(string $xml): array {
        $doc = new \DOMDocument();
        $doc->loadXML($xml);
        $out = [];
        foreach ($doc->getElementsByTagName('question') as $q) {
            if ($q->getAttribute('type') === 'category') {
                continue;
            }
            $g = $q->getElementsByTagName('defaultgrade')->item(0);
            $out[] = $g ? (float)$g->textContent : 1.0;
        }
        return $out;
    }

    /** Danh sách idnumber QB-n theo thứ tự câu trong tệp. */
    private static function idnumbers(string $xml): array {
        $doc = new \DOMDocument();
        $doc->loadXML($xml);
        $out = [];
        foreach ($doc->getElementsByTagName('question') as $q) {
            if ($q->getAttribute('type') === 'category') {
                continue;
            }
            $idn = $q->getElementsByTagName('idnumber')->item(0);
            if ($idn && preg_match('/^QB-\d+$/', trim($idn->textContent))) {
                $out[] = trim($idn->textContent);
            }
        }
        return $out;
    }

    /** idnumber => id câu hỏi (phiên bản mới nhất) đã có trong ngân hàng câu hỏi của khóa học. */
    private static function existing(\context $context, array $idnumbers): array {
        global $DB;
        if (!$idnumbers) {
            return [];
        }
        [$in, $params] = $DB->get_in_or_equal($idnumbers, SQL_PARAMS_NAMED);
        $params['ctx'] = $context->id;
        $rows = $DB->get_records_sql("
            SELECT qbe.idnumber, qv.questionid
              FROM {question_bank_entries} qbe
              JOIN {question_categories} qc ON qc.id = qbe.questioncategoryid AND qc.contextid = :ctx
              JOIN {question_versions} qv ON qv.questionbankentryid = qbe.id
             WHERE qbe.idnumber $in
               AND qv.version = (SELECT MAX(v2.version) FROM {question_versions} v2 WHERE v2.questionbankentryid = qbe.id)",
            $params);
        $out = [];
        foreach ($rows as $r) {
            $out[$r->idnumber] = (int)$r->questionid;
        }
        return $out;
    }

    /** Giữ lại câu danh mục + các câu có idnumber trong $keep. */
    private static function filter(string $xml, array $keep): string {
        $doc = new \DOMDocument();
        $doc->loadXML($xml);
        $remove = [];
        foreach ($doc->getElementsByTagName('question') as $q) {
            if ($q->getAttribute('type') === 'category') {
                continue;
            }
            $idn = $q->getElementsByTagName('idnumber')->item(0);
            if (!$idn || !in_array(trim($idn->textContent), $keep, true)) {
                $remove[] = $q;
            }
        }
        foreach ($remove as $q) {
            $q->parentNode->removeChild($q);
        }
        return $doc->saveXML();
    }

    private static function run_import(\stdClass $course, \context $context, string $xml): array {
        global $CFG;
        require_once($CFG->dirroot . '/question/editlib.php');
        require_once($CFG->dirroot . '/question/format/xml/format.php');
        $dir = make_request_directory();
        $file = $dir . '/exam.xml';
        file_put_contents($file, $xml);
        $contexts = new \core_question\local\bank\question_edit_contexts($context);
        $defaultcat = question_make_default_categories($contexts->all());
        $qformat = new \qformat_xml();
        $qformat->setCategory($defaultcat);
        $qformat->setContexts($contexts->having_one_edit_tab_cap('import'));
        $qformat->setCourse($course);
        $qformat->setFilename($file);
        $qformat->setRealfilename('exam.xml');
        $qformat->setMatchgrades('error');
        $qformat->setCatfromfile(true);
        $qformat->setContextfromfile(true);
        $qformat->setStoponerror(true);
        ob_start();
        $ok = $qformat->importpreprocess() && $qformat->importprocess() && $qformat->importpostprocess();
        $log = ob_get_clean();
        if (!$ok || empty($qformat->questionids)) {
            throw new \moodle_exception('importfailed', 'local_clo', '', null, trim(strip_tags($log)));
        }
        return array_values($qformat->questionids);
    }
}
