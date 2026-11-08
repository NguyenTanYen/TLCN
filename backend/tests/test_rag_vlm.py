"""Mô tả hình trong học liệu bằng VLM (vlm.py) – Ollama được giả lập, không gọi model thật."""
from datetime import datetime, timedelta

import pymupdf
import pytest
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.models import MaterialPage, MaterialPassage, SectionMaterial
from app.services.rag import search, vlm

_real_describe = vlm.describe


def _pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=720, height=540)
    page.draw_rect(pymupdf.Rect(60, 120, 340, 420), color=(0, 0, 1), fill=(0.9, 0.9, 1))
    page.insert_text((80, 160), "STATIC CAPTURE", fontsize=18)
    return doc.tobytes()


@pytest.fixture()
def material():
    db = SessionLocal()
    cs = db.execute(text("SELECT class_section_id FROM exams WHERE id = 2")).scalar()
    m = SectionMaterial(class_section_id=cs, source="moodle", title="Slide ETL thử", status="ready",
                        file_name="test_vlm.pdf", content_hash="7c" * 20, moodle_cmid=1812,
                        moodle_file_url="http://moodle.test/pluginfile.php/1812/test_vlm.pdf",
                        indexed_at=datetime.now().replace(microsecond=0), n_pages=1, embed_model="mini")
    db.add(m)
    db.flush()
    pg = MaterialPage(material_id=m.id, page_no=1, width=720, height=540)
    db.add(pg)
    db.flush()
    db.add(MaterialPassage(material_id=m.id, page_id=pg.id, seq=1, kind="text", title="Thu dữ liệu",
                           breadcrumb="ETL > Thu dữ liệu", bboxes=[[40, 20, 600, 80]], body="Hai cách thu dữ liệu nguồn.",
                           embedding=b"\x00" * 768))
    db.add(MaterialPassage(material_id=m.id, page_id=pg.id, seq=2, kind="figure", title="Thu dữ liệu",
                           breadcrumb="ETL > Thu dữ liệu", bboxes=[[60, 120, 340, 420], [80, 140, 300, 170]],
                           body="STATIC CAPTURE ẢNH CHỤP TĨNH", embedding=b"\x00" * 768))
    db.commit()
    yield m.id, cs
    db.execute(text("DELETE FROM section_materials WHERE file_name = 'test_vlm.pdf'"))
    db.commit()
    db.close()


@pytest.fixture()
def fake_vlm(monkeypatch):
    calls = []

    def describe(png, prompt):
        assert png.startswith(b"\x89PNG")
        calls.append(prompt)
        return "Hai thẻ so sánh chụp toàn bộ một lần với thu gia tăng (zebrafish) theo lịch."
    monkeypatch.setattr(settings, "rag_vlm_model", "fake-vlm")
    monkeypatch.setattr(vlm, "available", lambda: True)
    monkeypatch.setattr(vlm, "describe", describe)
    return calls


def _rows(db, mid):
    return db.execute(text("SELECT kind, vlm_desc, embedding IS NULL FROM material_passages WHERE material_id = :m "
                           "ORDER BY seq"), {"m": mid}).fetchall()


def test_prompt_carries_pdf_text_and_context():
    p = vlm.prompt_for("Kho dữ liệu", True, "ETL > Thu dữ liệu", "STATIC   CAPTURE " + "x " * 500)
    assert 'môn "Kho dữ liệu"' in p and 'phần "ETL > Thu dữ liệu"' in p and "slide bài giảng" in p
    assert "STATIC CAPTURE" in p and "…" in p and len(p) < 1500
    assert "Chữ đọc được" not in vlm.prompt_for("Kho dữ liệu", False, "", "")


def test_describes_only_figures_then_marks_material(material, fake_vlm):
    mid, cs = material
    db = SessionLocal()
    try:
        assert vlm.describe_missing(db, cs, fetcher=lambda m: _pdf()) == 1
        rows = _rows(db, mid)
        assert rows[0] == ("text", None, 0)
        assert rows[1][0] == "figure" and "zebrafish" in rows[1][1] and rows[1][2] == 1
        assert "STATIC CAPTURE" in fake_vlm[0]
        m = db.get(SectionMaterial, mid)
        assert m.vlm_model == "fake-vlm" and m.embed_model is None
        db.rollback()
        assert vlm.describe_missing(db, cs, fetcher=lambda m: _pdf()) == 0
        assert len(fake_vlm) == 1
    finally:
        db.close()


def test_description_is_searchable_after_describe(material, fake_vlm):
    mid, cs = material
    db = SessionLocal()
    try:
        search.warm(db, cs)
        assert not any(h.material_id == mid for h in search.search(db, cs, "zebrafish"))
        vlm.describe_missing(db, cs, fetcher=lambda m: _pdf())
        db.rollback()
        search.warm(db, cs)
        assert any(h.material_id == mid and h.kind == "figure" for h in search.search(db, cs, "zebrafish"))
    finally:
        db.close()


def test_result_dropped_when_material_reindexed_meanwhile(material, fake_vlm, monkeypatch):
    mid, cs = material

    def describe_while_reindexed(png, prompt):
        with SessionLocal() as other:
            other.execute(text("UPDATE section_materials SET indexed_at = :t WHERE id = :m"),
                          {"t": datetime.now() + timedelta(seconds=5), "m": mid})
            other.commit()
        return "mô tả cũ"
    monkeypatch.setattr(vlm, "describe", describe_while_reindexed)
    db = SessionLocal()
    try:
        assert vlm.describe_missing(db, cs, fetcher=lambda m: _pdf()) == 0
        assert [r[1] for r in _rows(db, mid)] == [None, None]
        assert db.get(SectionMaterial, mid).vlm_model is None
    finally:
        db.close()


def test_stops_without_writing_when_vlm_fails(material, fake_vlm, monkeypatch):
    mid, cs = material
    import httpx

    def down(png, prompt):
        raise httpx.ConnectError("Ollama tắt")
    monkeypatch.setattr(vlm, "describe", down)
    db = SessionLocal()
    try:
        assert vlm.describe_missing(db, cs, fetcher=lambda m: _pdf()) == 0
        assert db.get(SectionMaterial, mid).vlm_model is None
        assert [r[2] for r in _rows(db, mid)] == [0, 0]
    finally:
        db.close()


def test_figure_refused_by_ollama_is_skipped_not_blocking(material, fake_vlm, monkeypatch):
    """Ollama trả HTTP 500 cho riêng một hình (vd."""
    mid, cs = material
    import httpx

    def refused(url, **kw):
        assert kw["json"]["options"]["repeat_penalty"] > 1
        return httpx.Response(500, json={"error": "prediction aborted, token repeat limit reached"},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(vlm, "describe", _real_describe)
    monkeypatch.setattr(httpx, "post", refused)
    db = SessionLocal()
    try:
        assert vlm.describe_missing(db, cs, fetcher=lambda m: _pdf()) == 0
        assert [r[1:] for r in _rows(db, mid)] == [(None, 0), (None, 0)]
        m = db.get(SectionMaterial, mid)
        assert m.vlm_model == "fake-vlm" and m.embed_model == "mini"
    finally:
        db.close()


def test_describe_raises_on_connection_error(monkeypatch):
    import httpx

    def down(url, **kw):
        raise httpx.ConnectError("Ollama tắt")
    monkeypatch.setattr(httpx, "post", down)
    with pytest.raises(httpx.TransportError):
        vlm.describe(b"png", "p")


def test_skipped_when_disabled_or_ollama_missing(material, monkeypatch):
    mid, cs = material
    db = SessionLocal()
    try:
        assert settings.rag_vlm_model == ""
        assert vlm.describe_missing(db, cs, fetcher=lambda m: pytest.fail("không được tải tệp")) == 0
        monkeypatch.setattr(settings, "rag_vlm_model", "fake-vlm")
        monkeypatch.setattr(settings, "rag_vlm_url", "http://127.0.0.1:9")
        assert not vlm.available()
        assert vlm.describe_missing(db, cs, fetcher=lambda m: pytest.fail("không được tải tệp")) == 0
        assert db.get(SectionMaterial, mid).vlm_model is None
    finally:
        db.close()
