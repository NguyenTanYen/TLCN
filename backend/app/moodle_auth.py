"""Xác thực bằng tài khoản Moodle (chỉ đọc bảng mdl_user).

Moodle 4.5 lưu mật khẩu dạng SHA-512 crypt: $6$rounds=10000$<salt>$<hash> (hàm hash_internal_user_password).
Module `crypt` của Python không có trên Windows nên thuật toán SHA-crypt (U. Drepper) được cài đặt thuần Python.
Bản cũ của Moodle dùng bcrypt ($2y$) – hỗ trợ nếu cài gói `bcrypt`.
"""
from __future__ import annotations

import hashlib
import hmac

from sqlalchemy import text

_ITOA = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_PERM = [(0, 21, 42), (22, 43, 1), (44, 2, 23), (3, 24, 45), (25, 46, 4), (47, 5, 26), (6, 27, 48), (28, 49, 7),
         (50, 8, 29), (9, 30, 51), (31, 52, 10), (53, 11, 32), (12, 33, 54), (34, 55, 13), (56, 14, 35), (15, 36, 57),
         (37, 58, 16), (59, 17, 38), (18, 39, 60), (40, 61, 19), (62, 20, 41)]


def _b64(b2: int, b1: int, b0: int, n: int) -> str:
    w = (b2 << 16) | (b1 << 8) | b0
    out = []
    for _ in range(n):
        out.append(_ITOA[w & 0x3F]); w >>= 6
    return "".join(out)


def sha512_crypt(password: str, setting: str) -> str:
    """Tính lại chuỗi băm theo 'setting' dạng $6$[rounds=N$]salt[$...]."""
    pw = password.encode("utf-8")
    parts = setting.split("$")
    if len(parts) < 3 or parts[1] != "6":
        raise ValueError("không phải SHA-512 crypt")
    rounds, custom = 5000, False
    idx = 2
    if parts[2].startswith("rounds="):
        rounds = max(1000, min(999_999_999, int(parts[2][7:]))); custom = True; idx = 3
    salt = parts[idx][:16].encode()
    h = hashlib.sha512
    b = h(pw + salt + pw).digest()
    a = h()
    a.update(pw + salt)
    n = len(pw)
    while n > 64:
        a.update(b); n -= 64
    a.update(b[:n])
    n = len(pw)
    while n:
        a.update(b if n & 1 else pw); n >>= 1
    a = a.digest()
    dp = h(pw * len(pw)).digest()
    p = (dp * (len(pw) // 64 + 1))[:len(pw)]
    ds = h(salt * (16 + a[0])).digest()
    s = (ds * (len(salt) // 64 + 1))[:len(salt)]
    c = a
    for i in range(rounds):
        d = h()
        d.update(p if i & 1 else c)
        if i % 3:
            d.update(s)
        if i % 7:
            d.update(p)
        d.update(c if i & 1 else p)
        c = d.digest()
    enc = "".join(_b64(c[x], c[y], c[z], 4) for x, y, z in _PERM) + _b64(0, 0, c[63], 2)
    head = f"$6$rounds={rounds}$" if custom else "$6$"
    return f"{head}{salt.decode()}${enc}"


def verify_moodle_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        if stored.startswith("$6$"):
            return hmac.compare_digest(sha512_crypt(password, stored), stored)
        if stored.startswith(("$2y$", "$2a$", "$2b$")):
            import bcrypt  # tùy chọn
            return bcrypt.checkpw(password.encode(), stored.replace("$2y$", "$2b$", 1).encode())
        if len(stored) == 32:  # MD5 rất cũ (không có salt site)
            return hmac.compare_digest(hashlib.md5(password.encode()).hexdigest(), stored)
    except Exception:
        return False
    return False


def find_moodle_user(db, username: str):
    from .config import settings
    t = f"`{settings.moodle_db_name}`.`{settings.moodle_prefix}user`"
    try:
        return db.execute(text(f"""SELECT id, username, idnumber, firstname, lastname, email, password, auth
                                    FROM {t} WHERE username = :u AND deleted = 0 AND suspended = 0"""),
                          {"u": username.strip().lower()}).mappings().first()
    except Exception:
        return None  # chưa có CSDL Moodle hoặc không có quyền đọc
