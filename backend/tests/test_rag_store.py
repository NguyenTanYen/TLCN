"""Bảng học liệu theo lớp học phần (section_materials, material_pages, material_passages) + ghi kết quả chunking."""
import os

import pymupdf
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from app import migrate
from app.database import SessionLocal, engine
from app.models import MaterialPage, MaterialPassage, SectionMaterial
from app.services.rag import chunk, ingest, store

FONT = os.path.join(os.path.dirname(__file__), "..", "app", "assets", "fonts", "DejaVuSans.ttf")


def _pdf() -> bytes:
    doc = pymupdf.open()
    for title, body in [("Chương 3: Ràng buộc", "Ràng buộc toàn vẹn bảo đảm dữ liệu hợp lệ."),
                        ("Khóa ngoại", "Khóa ngoại tham chiếu tới khóa chính của bảng khác.")]:
        pg = doc.new_page(width=720, height=540)
        pg.insert_text((40, 90), title, fontsize=28, fontfile=FONT, fontname="dv")
        pg.insert_text((60, 160), body, fontsize=18, fontfile=FONT, fontname="dv")
    for r, row in enumerate([["Cột", "Ràng buộc"], ["MaSV", "PRIMARY KEY"], ["MaLop", "FOREIGN KEY"]]):
        for c, s in enumerate(row):
            rc = pymupdf.Rect(60 + 200 * c, 220 + 30 * r, 260 + 200 * c, 250 + 30 * r)
            doc[1].draw_rect(rc); doc[1].insert_text((rc.x0 + 5, rc.y0 + 20), s, fontsize=14, fontfile=FONT, fontname="dv")
    return doc.tobytes()


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.execute(text("DELETE FROM section_materials WHERE file_name LIKE 'test_rag_%'"))
    s.commit(); s.close()


def _section(db) -> int:
    return db.execute(text("SELECT MIN(id) FROM class_sections")).scalar()


def _material(db, name="test_rag_ch3.pdf", h="a" * 40, **kw) -> SectionMaterial:
    m = SectionMaterial(class_section_id=_section(db), title="Slide Chương 3", file_name=name, content_hash=h, **kw)
    db.add(m); db.flush()
    return m


def test_save_document_pages_passages_and_status(db):
    m = _material(db)
    src = _pdf()
    pages = ingest.read_pdf(src)
    passages = chunk.build_passages(pages)
    store.save_document(db, m, pages, passages)
    db.commit()

    assert (m.status, m.n_pages) == ("ready", 2) and m.indexed_at is not None
    rows = db.query(MaterialPassage).filter_by(material_id=m.id).order_by(MaterialPassage.seq).all()
    assert [r.seq for r in rows] == list(range(1, len(passages) + 1))
    assert [(r.page.page_no, r.kind, r.breadcrumb) for r in rows] == [
        (1, "text", "Chương 3: Ràng buộc"),
        (2, "text", "Chương 3: Ràng buộc > Khóa ngoại"),
        (2, "table", "Chương 3: Ràng buộc > Khóa ngoại")]
    assert rows[2].body.startswith("|Cột|Ràng buộc|") and rows[2].is_code is False
    assert rows[1].bboxes == [list(b) for b in passages[1].bboxes]       # JSON khung tô đọc lại đúng
    pg = db.query(MaterialPage).filter_by(material_id=m.id, page_no=2).one()
    assert (float(pg.width), float(pg.height), pg.is_scanned) == (720.0, 540.0, False)


def test_reindex_replaces_old_rows(db):
    m = _material(db)
    pages = ingest.read_pdf(_pdf())
    passages = chunk.build_passages(pages)
    store.save_document(db, m, pages, passages)
    store.save_document(db, m, pages, passages)                          # GV sửa tệp → nạp lại
    db.commit()
    assert db.query(MaterialPage).filter_by(material_id=m.id).count() == 2
    assert db.query(MaterialPassage).filter_by(material_id=m.id).count() == len(passages)


def test_same_file_twice_in_one_section_rejected(db):
    _material(db, "test_rag_a.pdf", "b" * 40)
    db.commit()
    with pytest.raises(IntegrityError):
        _material(db, "test_rag_b.pdf", "b" * 40)                        # cùng nội dung (SHA-1), khác tên tệp


@pytest.mark.parametrize("kw", [dict(source="moodle"),                    # tệp Moodle phải có moodle_cmid
                                dict(material_type="exam"),              # chỉ slide / reference
                                dict(status="done")])
def test_material_checks(db, kw):
    with pytest.raises((IntegrityError, OperationalError)):
        _material(db, h="c" * 40, **kw)


def test_passage_kind_and_bboxes_checks(db):
    m = _material(db, h="d" * 40)
    page = MaterialPage(material_id=m.id, page_no=1, width=100, height=100)
    db.add(page); db.flush()
    for bad in (dict(kind="image", bboxes=[[0, 0, 1, 1]]), dict(kind="text", bboxes=[])):
        with db.begin_nested(), pytest.raises((IntegrityError, OperationalError)):
            db.add(MaterialPassage(material_id=m.id, page_id=page.id, seq=1, body="x", **bad)); db.flush()


def test_delete_material_cascades(db):
    m = _material(db, h="e" * 40)
    pages = ingest.read_pdf(_pdf())
    store.save_document(db, m, pages, chunk.build_passages(pages))
    db.commit()
    mid = m.id
    db.execute(text("DELETE FROM section_materials WHERE id=:i"), {"i": mid}); db.commit()
    assert db.query(MaterialPage).filter_by(material_id=mid).count() == 0
    assert db.query(MaterialPassage).filter_by(material_id=mid).count() == 0


def test_upgrade_creates_rag_tables_on_old_database():
    with engine.begin() as c:
        c.execute(text("DROP TABLE material_passages, material_pages, section_materials"))
    done = migrate.upgrade_schema()
    assert {"bảng section_materials", "bảng material_pages", "bảng material_passages"} <= set(done)
    with engine.begin() as c:
        n = c.execute(text("""SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()
                              AND TABLE_NAME IN ('section_materials','material_pages','material_passages')""")).scalar()
    assert n == 3
