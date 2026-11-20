<?php
require_once(__DIR__ . '/../../config.php');
require_once(__DIR__ . '/lib.php');
require_once($CFG->libdir . '/filelib.php');

$courseid = required_param('id', PARAM_INT);
$q = trim(optional_param('q', '', PARAM_TEXT));
$course = get_course($courseid);
require_login($course);
$context = context_course::instance($course->id);
if (!has_any_capability(['local/clo:viewown', 'local/clo:viewall'], $context)) {
    throw new required_capability_exception($context, 'local/clo:viewown', 'nopermissions', '');
}

$PAGE->set_url(new moodle_url('/local/clo/search.php', ['id' => $course->id, 'q' => $q]));
$PAGE->set_context($context);
$PAGE->set_pagelayout('incourse');
$PAGE->set_title(get_string('searchmaterials', 'local_clo') . ' – ' . format_string($course->shortname));
$PAGE->set_heading(format_string($course->fullname));

echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('searchmaterials', 'local_clo'));
echo local_clo_search_form($course->id, $q);
if ($q !== '') {
    $err = '';
    $hits = local_clo_search_materials($course->id, $q, $err);
    if ($err !== '') {
        echo $OUTPUT->notification($err, 'error', false);
    } else if (!$hits) {
        echo $OUTPUT->notification(get_string('searchnone', 'local_clo'), 'info', false);
    } else {
        $o = '';
        foreach ($hits as $h) {
            $page = (int)($h->page ?? 0);
            $url = null;
            $at = strpos((string)($h->url ?? ''), '/pluginfile.php/');
            if ($at !== false) {
                $url = new moodle_url($CFG->wwwroot . substr($h->url, $at), null, $page > 0 ? 'page=' . $page : null);
            }
            $title = get_string('readings_page', 'local_clo', (object)['material' => s($h->material), 'page' => $page]);
            $title = $url ? html_writer::link($url, $title, ['target' => '_blank', 'rel' => 'noopener']) : $title;
            $o .= html_writer::div(html_writer::div(html_writer::tag('strong', $title) .
                (!empty($h->heading) ? ' – ' . s($h->heading) : ''), 'local-clo-hit-title') .
                (!empty($h->snippet) ? html_writer::div(s(shorten_text(strip_tags($h->snippet), 320)), 'local-clo-hit-snippet') : ''),
                'local-clo-hit');
        }
        echo html_writer::div(html_writer::tag('p', get_string('searchresults', 'local_clo', count($hits)), ['class' => 'small text-muted']) . $o,
            'local-clo-card');
    }
}
echo $OUTPUT->footer();
