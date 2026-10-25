"""Lớp học phần ⇄ Moodle: Bộ môn tạo/phân công lớp thì khóa học Moodle được tạo và GV/SV được ghi danh (không để lệch luồng)."""
import pytest
from sqlalchemy import bindparam, text

from app.config import settings
from app.database import engine
from app.services import lms

from .test_z_toan_bo_chuc_nang import FakeMoodle


@pytest.fixture()
def fake(monkeypatch):
    f = FakeMoodle()
    monkeypatch.setattr(settings, "moodle_url", "http://moodle.test")
    monkeypatch.setattr(settings, "moodle_ws_token", "token-gia-lap")
    monkeypatch.setattr(lms, "call", f)
    return f


def _new_section(client, admin, code):
    body = {"course_id": 1, "semester_id": 1, "lecturer_id": 1, "section_code": code}
    r = client.post("/api/class-sections", json=body, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()


def _cleanup(cs_id):
    with engine.begin() as c:
        c.execute(text("DELETE FROM enrollments WHERE class_section_id=:c"), {"c": cs_id})
        c.execute(text("DELETE FROM class_sections WHERE id=:c"), {"c": cs_id})


def test_tao_lop_tu_tao_khoa_hoc_moodle(client, admin, fake):
    r = _new_section(client, admin, "TKH_AUTO_01")
    try:
        assert r["moodle"]["status"] == "ok" and r["moodle"]["moodle_course_id"]
        fn, params = fake.calls[-1]
        assert fn == "local_clo_provision_course" and params["shortname"] == "TKH_AUTO_01" and params["idnumber"] == "TKH_AUTO_01"
        assert len(params["teachers"]) == 1 and params["teachers"][0]["username"]
        with engine.connect() as c:
            assert c.execute(text("SELECT moodle_course_id FROM class_sections WHERE id=:i"), {"i": r["id"]}).scalar() == r["moodle"]["moodle_course_id"]
    finally:
        _cleanup(r["id"])


def test_tao_lop_khi_chua_cau_hinh_moodle_van_thanh_cong(client, admin, monkeypatch):
    monkeypatch.setattr(settings, "moodle_ws_token", "")
    r = _new_section(client, admin, "TKH_AUTO_02")
    try:
        assert r["moodle"]["status"] == "skipped"
    finally:
        _cleanup(r["id"])


def test_loi_moodle_khong_lam_hong_viec_tao_lop(client, admin, monkeypatch):
    def boom(*a, **k):
        raise lms.MoodleWSError("Lỗi kết nối LMS: giả lập")
    monkeypatch.setattr(settings, "moodle_url", "http://moodle.test")
    monkeypatch.setattr(settings, "moodle_ws_token", "t")
    monkeypatch.setattr(lms, "call", boom)
    r = _new_section(client, admin, "TKH_AUTO_03")
    try:
        assert r["moodle"]["status"] == "error" and "giả lập" in r["moodle"]["message"]
        assert client.post(f"/api/class-sections/{r['id']}/moodle-provision", headers=admin).status_code == 502
    finally:
        _cleanup(r["id"])


def test_nut_tao_khoa_hoc_ghi_danh_sv_va_luu_mdl_user_id(client, admin, monkeypatch, fake):
    monkeypatch.setattr(settings, "moodle_ws_token", "")           # tạo lớp trước, chưa nối Moodle
    r = _new_section(client, admin, "TKH_AUTO_04")
    monkeypatch.setattr(settings, "moodle_ws_token", "token-gia-lap")
    sel = text("SELECT id FROM students ORDER BY id DESC LIMIT 3")
    with engine.begin() as c:
        sids = [x[0] for x in c.execute(sel)]
        old = {x[0]: x[1] for x in c.execute(text("SELECT id, moodle_user_id FROM students WHERE id IN :s").bindparams(
            bindparam("s", expanding=True)), {"s": sids})}
        c.execute(text("UPDATE students SET moodle_user_id=NULL WHERE id IN :s").bindparams(bindparam("s", expanding=True)), {"s": sids})
        for s in sids:
            c.execute(text("INSERT IGNORE INTO enrollments (class_section_id, student_id) VALUES (:c, :s)"), {"c": r["id"], "s": s})
    try:
        out = client.post(f"/api/class-sections/{r['id']}/moodle-provision", headers=admin).json()
        assert out["n_students"] == 3 and out["moodle_course_id"]
        students = fake.calls[-1][1]["students"]
        assert len(students) == 3 and all(x["firstname"] and x["lastname"] for x in students)
        with engine.connect() as c:
            n = c.execute(text("SELECT COUNT(*) FROM students WHERE id IN :s AND moodle_user_id IS NOT NULL").bindparams(
                bindparam("s", expanding=True)), {"s": sids}).scalar()
        assert n == 3
        assert client.post(f"/api/class-sections/{r['id']}/moodle-provision", headers=admin).status_code == 200   # gọi lại vẫn ổn
    finally:
        with engine.begin() as c:
            for sid, mid in old.items():
                c.execute(text("UPDATE students SET moodle_user_id=:m WHERE id=:i"), {"m": mid, "i": sid})
        _cleanup(r["id"])


def test_gv_khac_khong_tao_duoc_khoa_hoc_cua_lop_nguoi_khac(client, gv_other, admin, fake):
    r = _new_section(client, admin, "TKH_AUTO_05")
    try:
        with engine.begin() as c:
            lec = c.execute(text("SELECT lecturer_id FROM class_sections WHERE id=:i"), {"i": r["id"]}).scalar()
            other = c.execute(text("SELECT l.id FROM lecturers l JOIN users u ON u.id=l.user_id WHERE u.username='gv.binh'")).scalar()
        if lec != other:
            assert client.post(f"/api/class-sections/{r['id']}/moodle-provision", headers=gv_other).status_code == 403
    finally:
        _cleanup(r["id"])
