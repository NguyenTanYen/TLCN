<?php
namespace local_clo\privacy;

defined('MOODLE_INTERNAL') || die();

use core_privacy\local\metadata\collection;

/** Khai báo dữ liệu cá nhân plugin lưu và gửi đi (GDPR). */
class provider implements \core_privacy\local\metadata\provider {
    public static function get_metadata(collection $collection): collection {
        $collection->add_database_table('local_clo_result', [
            'userid' => 'privacy:metadata:local_clo_result:userid',
            'score' => 'privacy:metadata:local_clo_result:score',
            'data' => 'privacy:metadata:local_clo_result:data',
        ], 'privacy:metadata:local_clo_result');
        $collection->add_external_location_link('clo_analytics', [
            'username' => 'privacy:metadata:clo_analytics:username',
            'email' => 'privacy:metadata:clo_analytics:email',
            'fullname' => 'privacy:metadata:clo_analytics:fullname',
        ], 'privacy:metadata:clo_analytics');
        return $collection;
    }
}
