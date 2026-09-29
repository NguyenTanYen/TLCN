"""Đăng nhập một lần từ nút "Phân tích CĐR" trên Moodle (vé JWT HS256 do plugin local_clo ký)."""
import time, uuid

import jwt
import pytest

from app.config import settings

SECRET = "k" * 64


@pytest.fixture(autouse=True)
def sso_config(monkeypatch):
    monkeypatch.setattr(settings, "moodle_sso_secret", SECRET)
    monkeypatch.setattr(settings, "moodle_url", "http://moodle.test")


def ticket(sub, role="teacher", secret=SECRET, **kw):
    now = int(time.time())
    claims = {"iss": "http://moodle.test", "aud": "clo-analytics", "sub": sub, "uid": 5, "idnumber": "", "email": "",
              "name": sub, "role": role, "courseid": 0, "iat": now, "exp": now + 120, "jti": uuid.uuid4().hex, **kw}
    return jwt.encode(claims, secret, algorithm="HS256")


def test_teacher_sso_and_replay(client):
    t = ticket("gv.son")
    r = client.get("/api/auth/moodle-sso", params={"token": t})
    assert r.status_code == 200 and "tlcn_token" in r.text and "gv.son" in r.text
    assert client.get("/api/auth/moodle-sso", params={"token": t}).status_code == 403   # vé chỉ dùng một lần


def test_sso_rejects_bad_tickets(client):
    assert client.get("/api/auth/moodle-sso", params={"token": ticket("gv.son", secret="x" * 64)}).status_code == 403
    assert client.get("/api/auth/moodle-sso", params={"token": ticket("gv.son", exp=int(time.time()) - 600)}).status_code == 403
    assert client.get("/api/auth/moodle-sso", params={"token": ticket("gv.son", iss="http://evil")}).status_code == 403


def test_sso_never_escalates(client):
    # SV không vào được hệ thống; GV Moodle không lên được quyền quản trị
    assert client.get("/api/auth/moodle-sso", params={"token": ticket("22130001", role="student")}).status_code == 403
    assert client.get("/api/auth/moodle-sso", params={"token": ticket("admin", role="teacher")}).status_code == 403
    assert client.get("/api/auth/moodle-sso", params={"token": ticket("admin", role="admin")}).status_code == 200
    r = client.get("/api/auth/moodle-sso", params={"token": ticket("gv.khongco")})
    assert r.status_code == 403 and "chưa được bộ môn khai báo" in r.text


def test_sso_provisions_declared_lecturer(client):
    # GV có trong danh sách bộ môn (mã GV002 = idnumber trên Moodle) được tạo tài khoản ở lần vào đầu tiên
    r = client.get("/api/auth/moodle-sso", params={"token": ticket("chau.ltm", idnumber="GV002")})
    assert r.status_code == 200 and "Lê Thị Minh Châu" in r.text
    assert client.get("/api/auth/moodle-sso", params={"token": ticket("chau.ltm", idnumber="GV002")}).status_code == 200
