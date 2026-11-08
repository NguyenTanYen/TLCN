"""Tải học liệu lên từ hệ thống: đăng lên khóa Moodle của nhiều lớp cùng môn, sao chép từ lớp khác (Moodle giả lập)."""
import hashlib

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models import ClassSection, SectionMaterial
from app.services import lms
from app.services.rag import index, moodle_files, publish

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n" + b"x" * 300
HASH = hashlib.sha1(PDF).hexdigest()


@pytest.fixture(scope="module")
def sections():
    """Lớp nguồn (khóa 50) + hai lớp cùng môn: một gắn Moodle (khóa 951), một chưa gắn."""
    db = SessionLocal()
    src = db.query(ClassSection).filter(ClassSection.moodle_course_id == 50).first()
    ids = [src.id]
    for code, mc in (("PUB_A", 951), ("PUB_B", None)):
        c = ClassSection(course_id=src.course_id, semester_id=src.semester_id, lecturer_id=src.lecturer_id,
                         section_code=code, moodle_course_id=mc)
        db.add(c); db.commit(); ids.append(c.id)
    db.close()
    yield ids
    db = SessionLocal()
    db.execute(text("DELETE FROM section_materials WHERE class_section_id IN :i").bindparams(__import__("sqlalchemy").bindparam("i", expanding=True)), {"i": ids})
    db.execute(text("DELETE FROM class_sections WHERE id IN :i").bindparams(__import__("sqlalchemy").bindparam("i", expanding=True)), {"i": ids[1:]})
    db.commit(); db.close()


@pytest.fixture(autouse=True)
def fake_moodle(monkeypatch):
    posted = {}                                   # moodle_course_id -> [(name, filename, size, section)]

    def add_resource(cid, name, filename, data, section=0):
        posted.setdefault(cid, []).append((name, filename, len(data), section))
        return {"cmid": 7000 + cid, "created": True}

    def list_files(db, cid):
        return [{"cmid": 7000 + cid, "module": "resource", "activity": n, "section": "", "path": "/", "file_name": fn,
                 "mimetype": "application/pdf", "file_size": sz, "content_hash": HASH, "timemodified": 1,
                 "url": f"http://moodle.test/pluginfile.php/1/mod_resource/content/1/{fn}", "supported": True}
                for (n, fn, sz, _) in posted.get(cid, [])]

    monkeypatch.setattr(lms, "add_resource", add_resource)
    monkeypatch.setattr(lms, "configured", lambda: True)
    monkeypatch.setattr(moodle_files, "list_course_files", list_files)
    monkeypatch.setattr(index, "enqueue", lambda *a, **k: None)
    monkeypatch.setattr(publish, "fetch_bytes", lambda m: PDF)
    return posted


def _up(client, gv, cs, ids="", data=PDF, name="giao_trinh.pdf", **f):
    return client.post(f"/api/class-sections/{cs}/materials/upload", headers=gv,
                       files={"file": (name, data, "application/pdf")}, data={"class_section_ids": ids, **f})


def test_upload_to_selected_classes(client, gv, sections, fake_moodle):
    src, a, b = sections
    r = _up(client, gv, src, f"{a},{b}", title="Giáo trình CSDL", material_type="reference")
    assert r.status_code == 200, r.text
    res = {x["section_code"]: x for x in r.json()["results"]}
    assert res["PUB_A"]["ok"] and res["PUB_A"]["material_id"]
    assert not res["PUB_B"]["ok"] and "chưa gắn khóa học Moodle" in res["PUB_B"]["message"]
    assert fake_moodle[951] == [("Giáo trình CSDL", "giao_trinh.pdf", len(PDF), 0)]
    db = SessionLocal()
    m = db.query(SectionMaterial).filter_by(class_section_id=a).one()
    assert (m.title, m.material_type, m.status, m.title_custom) == ("Giáo trình CSDL", "reference", "pending", True)
    db.close()


def test_upload_twice_is_reported_not_duplicated(client, gv, sections):
    src, a, _ = sections
    r = _up(client, gv, a)
    assert r.status_code == 200
    assert not r.json()["results"][0]["ok"] and "đã có học liệu" in r.json()["results"][0]["message"]


def test_upload_rejects_non_pdf_and_foreign_course(client, gv, sections):
    src, a, _ = sections
    assert _up(client, gv, a, data=b"PK\x03\x04zip", name="x.pdf").status_code == 422
    other = SessionLocal().execute(text("SELECT id FROM class_sections WHERE course_id <> (SELECT course_id FROM class_sections WHERE id=:s) LIMIT 1"), {"s": a}).scalar()
    if other:
        assert _up(client, gv, a, ids=str(other)).status_code in (403, 422)


def test_share_material_to_other_class_and_copy_from(client, gv, sections, fake_moodle):
    src, a, b = sections
    db = SessionLocal()
    m = db.query(SectionMaterial).filter_by(class_section_id=a).one()
    mid = m.id
    db.close()
    r = client.post(f"/api/class-sections/{a}/materials/{mid}/copy", headers=gv, json={"class_section_ids": [src]})
    assert r.status_code == 200, r.text
    assert r.json()["results"][0]["section_code"] and r.json()["results"][0]["ok"] is False   # lớp nguồn (khóa 50) không có hoạt động giả → chưa thấy tệp
    r = client.post(f"/api/class-sections/{b}/materials/copy-from/{a}", headers=gv)
    assert r.status_code == 200 and r.json()["results"][0]["ok"] is False                       # lớp B chưa gắn Moodle


def test_lecturer_only_and_course_check(client, gv_other, sections):
    src, a, _ = sections
    assert _up(client, gv_other, src).status_code == 403
