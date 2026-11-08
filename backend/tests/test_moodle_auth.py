"""Kiểm thử xác thực bằng mật khẩu Moodle (SHA-512 crypt cài đặt thuần Python, chạy được trên Windows)."""
from app.moodle_auth import sha512_crypt, verify_moodle_password

VEC = "$6$rounds=10000$abcdefghijklmnop$iWj8RNtPPzdGH.vSE6JQd2O8xmwB05CWv8kigAmxOUvhM4qFG3rWwGqO7IHf9DpvPNhH6LAUsQO/AbTrFfDo3."


def test_sha512_crypt_matches_glibc():
    assert sha512_crypt("Sv@123456", VEC) == VEC


def test_verify_moodle_password():
    assert verify_moodle_password("Sv@123456", VEC)
    assert not verify_moodle_password("sai-mat-khau", VEC)
    assert not verify_moodle_password("Sv@123456", "")
    assert not verify_moodle_password("x", None)


def test_default_rounds_and_short_salt():
    ref = "$6$saltstring$svn8UoSVapNtMuq1ukKS4tPQd8iKwSMHWjl/O817G3uBnIFNjnQJuesI68u4OTLiBFdcbYEdFCoEOfaS35inz1"
    assert sha512_crypt("Hello world!", "$6$saltstring") == ref
