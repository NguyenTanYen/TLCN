"""Kiểm thử xác thực bằng mật khẩu Moodle (SHA-512 crypt cài đặt thuần Python, chạy được trên Windows)."""
from app.moodle_auth import sha512_crypt, verify_moodle_password

# Vector tham chiếu sinh bằng crypt(3) của glibc – cùng định dạng Moodle 4.5 lưu trong mdl_user.password
VEC = "$6$rounds=10000$abcdefghijklmnop$iWj8RNtPPzdGH.vSE6JQd2O8xmwB05CWv8kigAmxOUvhM4qFG3rWwGqO7IHf9DpvPNhH6LAUsQO/AbTrFfDo3."


def test_sha512_crypt_matches_glibc():
    assert sha512_crypt("Sv@123456", VEC) == VEC


def test_verify_moodle_password():
    assert verify_moodle_password("Sv@123456", VEC)
    assert not verify_moodle_password("sai-mat-khau", VEC)
    assert not verify_moodle_password("Sv@123456", "")
    assert not verify_moodle_password("x", None)


def test_default_rounds_and_short_salt():
    # "$6$saltstring" (5000 vòng mặc định) – vector chuẩn trong đặc tả SHA-crypt của U. Drepper
    ref = "$6$saltstring$svn8UoSVapNtMuq1ukKS4tPQd8iKwSMHWjl/O817G3uBnIFNjnQJuesI68u4OTLiBFdcbYEdFCoEOfaS35inz1"
    assert sha512_crypt("Hello world!", "$6$saltstring") == ref
