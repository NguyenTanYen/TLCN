import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models import MaterialPage, MaterialPassage, SectionMaterial
from app.services.rag import relevance

COURSE = 5


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def cs(db):
    return db.execute(text("SELECT id FROM class_sections WHERE course_id = :c ORDER BY id LIMIT 1"), {"c": COURSE}).scalar()


def test_level_thresholds():
    assert relevance.level(None) is None
    assert relevance.level(0.5) == "ok"
    assert relevance.level(0.1) == "low"
    assert relevance.level(0.0) == "off"


def test_share_counts_pages_with_enough_distinct_terms():
    terms = frozenset({"commit", "rollback", "deadlock"})
    pages = [{"commit", "rollback"}, {"commit"}, {"dimension", "fact"}, set()]
    assert relevance.share_of(pages, terms) == 0.25
    assert relevance.share_of([], terms) is None


def test_upload_of_unrelated_file_is_rejected_before_publishing(db, cs):
    etl = ["Data warehouse lưu dữ liệu lịch sử phục vụ phân tích, khác với hệ thống tác nghiệp.",
           "Bảng fact và dimension trong mô hình hình sao, staging area, quy trình extract transform load."] * 6
    reason = relevance.check_upload(db, cs, etl)
    assert reason and "không thuộc môn" in reason and "chưa được đăng lên Moodle" in reason


def test_upload_of_course_content_is_accepted(db, cs):
    slides = ["Trigger INSTEAD OF thay thế INSERT UPDATE DELETE trên view.",
              "Giao tác: atomicity, isolation, durability; ROLLBACK khi lỗi.",
              "Deadlock và mức cô lập READ COMMITTED, SERIALIZABLE.",
              "Clustered index và execution plan.", "Giới thiệu môn học."]
    assert relevance.check_upload(db, cs, slides) is None


def test_indexed_unrelated_material_is_rejected_and_can_be_accepted(db, cs, client, gv):
    m = SectionMaterial(class_section_id=cs, source="moodle", title="ETL", status="ready", file_name="test_rel.pdf",
                        content_hash="7c" * 20, n_pages=4, moodle_cmid=9901)
    db.add(m)
    db.flush()
    for no in range(1, 5):
        pg = MaterialPage(material_id=m.id, page_no=no, width=720, height=540)
        db.add(pg)
        db.flush()
        db.add(MaterialPassage(material_id=m.id, page_id=pg.id, seq=no, kind="text", title="Kho dữ liệu",
                               breadcrumb="", body="Data warehouse, bảng fact, dimension, staging area.", bboxes=[[40, 80, 600, 200]]))
    db.commit()
    try:
        reason = relevance.verdict(db, m)
        assert reason and "Vẫn dùng" in reason
        assert relevance.assess(db, cs)[m.id]["level"] == "off"
        assert relevance.off_topic_ids(db, cs) == {m.id}
        m.status, m.error = "rejected", reason
        db.commit()
        r = client.post(f"/api/class-sections/{cs}/materials/{m.id}/accept", headers=gv)
        assert r.status_code == 200 and r.json()["status"] == "ready"
        assert client.post(f"/api/class-sections/{cs}/materials/{m.id}/accept", headers=gv).status_code == 409
    finally:
        db.execute(text("DELETE FROM section_materials WHERE file_name = 'test_rel.pdf'"))
        db.commit()
