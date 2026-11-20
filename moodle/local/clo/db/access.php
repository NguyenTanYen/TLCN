<?php
defined('MOODLE_INTERNAL') || die();

$capabilities = [
    'local/clo:launch' => [
        'captype' => 'read',
        'contextlevel' => CONTEXT_COURSE,
        'archetypes' => ['editingteacher' => CAP_ALLOW, 'teacher' => CAP_ALLOW, 'manager' => CAP_ALLOW],
    ],
    'local/clo:viewown' => [
        'captype' => 'read',
        'contextlevel' => CONTEXT_COURSE,
        'archetypes' => ['student' => CAP_ALLOW],
    ],
    'local/clo:viewall' => [
        'captype' => 'read',
        'riskbitmask' => RISK_PERSONAL,
        'contextlevel' => CONTEXT_COURSE,
        'archetypes' => ['editingteacher' => CAP_ALLOW, 'teacher' => CAP_ALLOW, 'manager' => CAP_ALLOW],
    ],
    'local/clo:manage' => [
        'captype' => 'write',
        'riskbitmask' => RISK_PERSONAL | RISK_XSS,
        'contextlevel' => CONTEXT_COURSE,
        'archetypes' => ['manager' => CAP_ALLOW],
    ],
];
