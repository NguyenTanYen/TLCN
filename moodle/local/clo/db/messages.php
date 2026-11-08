<?php
defined('MOODLE_INTERNAL') || die();

$messageproviders = [
    'resultpublished' => [
        'defaults' => [
            'popup' => MESSAGE_PERMITTED + MESSAGE_DEFAULT_ENABLED,
            'email' => MESSAGE_PERMITTED,
        ],
    ],
];
