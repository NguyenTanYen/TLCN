<?php
namespace local_clo;

defined('MOODLE_INTERNAL') || die();

/**
 * Phát hành vé đăng nhập một lần (JWT HS256, hiệu lực 120 giây) để giảng viên chuyển từ Moodle
 * sang hệ thống phân tích CĐR mà không phải đăng nhập lại. Khóa bí mật dùng chung được lưu ở
 * local_clo/ssosecret (Moodle) và MOODLE_SSO_SECRET (hệ thống phân tích).
 */
class sso {
    /** Thời hạn của vé (giây). */
    const TTL = 120;

    public static function b64url(string $s): string {
        return rtrim(strtr(base64_encode($s), '+/', '-_'), '=');
    }

    public static function secret(): string {
        $secret = (string)get_config('local_clo', 'ssosecret');
        if (strlen($secret) < 32) {
            throw new \moodle_exception('nosecret', 'local_clo');
        }
        return $secret;
    }

    /** Vai trò mà hệ thống phân tích sẽ cấp: admin (quản trị Moodle) hoặc teacher. */
    public static function role_for(\stdClass $user): string {
        return is_siteadmin($user) ? 'admin' : 'teacher';
    }

    public static function make_token(\stdClass $user, int $courseid = 0): string {
        global $CFG;
        $now = time();
        $payload = [
            'iss' => $CFG->wwwroot,
            'aud' => 'clo-analytics',
            'sub' => $user->username,
            'uid' => (int)$user->id,
            'idnumber' => (string)$user->idnumber,
            'email' => (string)$user->email,
            'name' => fullname($user),
            'role' => self::role_for($user),
            'courseid' => $courseid,
            'iat' => $now,
            'exp' => $now + self::TTL,
            'jti' => random_string(24),
        ];
        $head = self::b64url(json_encode(['alg' => 'HS256', 'typ' => 'JWT']));
        $body = self::b64url(json_encode($payload, JSON_UNESCAPED_UNICODE));
        $sig = self::b64url(hash_hmac('sha256', "$head.$body", self::secret(), true));
        return "$head.$body.$sig";
    }
}
