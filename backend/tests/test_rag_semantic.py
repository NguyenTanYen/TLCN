"""Cổng ngữ nghĩa của gợi ý học liệu: tài liệu của lớp không nói về câu hỏi → không gợi ý (semantic.py)."""
from datetime import datetime, timedelta

import numpy as np
import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models import MaterialPage, MaterialPassage, Question, QuestionOption, SectionMaterial
from app.services.rag import search, semantic, suggest

PITR = 29
real_model = pytest.mark.skipif(not semantic.enabled(), reason="chưa cài sentence-transformers (requirements-semantic.txt)")


def _vec(*xs) -> bytes:
    v = np.array(xs, dtype=np.float32)
    return semantic.pack(v / np.linalg.norm(v))


@pytest.fixture()
def fake_encoder(monkeypatch):
    calls = []

    def encode(texts):
        calls.append(texts)
        return np.array([[1.0, 0.0, 0.0]] * len(texts), dtype=np.float32)
    monkeypatch.setattr(semantic, "encode", encode)
    return calls


def test_related_keeps_suggestions_only_when_some_candidate_is_close(fake_encoder):
    near, far = _vec(0.9, 0.1, 0), _vec(0.1, 1, 0)
    assert semantic.related("Recovery model nào?", [far, near], 0.55)
    assert not semantic.related("Recovery model nào?", [far, far], 0.55)


def test_english_question_goes_through_the_gate_unaccented_vietnamese_does_not(fake_encoder):
    far = _vec(0.1, 1, 0)
    assert not semantic.related("Which HTML tag creates a hyperlink?", [far], 0.55)
    assert not semantic.related("What is a view in SQL?", [far], 0.55)
    assert semantic.related("Nut nao trong HDFS luu tru cac khoi du lieu?", [far], 0.55)
    assert semantic.related("Menh de where va group by dung de lam gi?", [far], 0.55)    # từ khóa SQL không phải tiếng Anh
    assert semantic.related("Define a primary key", [far], 0.55)                          # không nhận ra: như cũ, không chặn


def test_related_never_blocks_when_it_cannot_judge(fake_encoder, monkeypatch):
    far = _vec(0, 1, 0)
    assert semantic.related("Câu hỏi có dấu", [], 0.55)                       # không có ứng viên
    assert semantic.related("Câu hỏi có dấu", [far, None], 0.55)              # có đoạn chưa tính vector
    assert semantic.related("Câu hỏi có dấu", [semantic.pack(np.ones(5, np.float32))], 0.55)  # vector model khác
    assert semantic.related("cau hoi khong dau ve recovery model", [far], 0.55)  # MiniLM kém với chữ không dấu
    assert fake_encoder == [["Câu hỏi có dấu"]]                               # chỉ nạp model khi thật sự phải so
    monkeypatch.setattr(semantic, "encode", lambda texts: None)                 # cổng tắt (chưa cài thư viện)
    assert semantic.related("Câu hỏi có dấu", [far], 0.55)


def test_pack_float16_round_trip():
    v = np.random.default_rng(1).normal(size=384).astype(np.float32)
    b = semantic.pack(v)
    assert len(b) == 768 and np.allclose(semantic.unpack(b), v, atol=1e-2)


@pytest.fixture()
def material():
    db = SessionLocal()
    cs = db.execute(text("SELECT class_section_id FROM exams WHERE id = 2")).scalar()
    m = SectionMaterial(class_section_id=cs, source="moodle", title="Slide sao lưu", status="ready",
                        file_name="test_semantic.pdf", content_hash="5b" * 20, moodle_cmid=1811,
                        moodle_file_url="http://moodle.test/pluginfile.php/1811/test_semantic.pdf",
                        indexed_at=datetime.now().replace(microsecond=0), n_pages=1)
    db.add(m)
    db.flush()
    pg = MaterialPage(material_id=m.id, page_no=1, width=720, height=540)
    db.add(pg)
    db.flush()
    db.add(MaterialPassage(material_id=m.id, page_id=pg.id, seq=1, kind="text", title="Recovery model",
                           breadcrumb="Recovery model", bboxes=[[40, 80, 600, 200]],
                           body="Recovery model FULL ghi đầy đủ nhật ký giao tác, cho phép phục hồi CSDL về một thời "
                                "điểm cụ thể (point-in-time recovery). SIMPLE không bảo đảm điều này."))
    db.add(MaterialPassage(material_id=m.id, page_id=pg.id, seq=2, kind="text", title="Trigger INSTEAD OF",
                           breadcrumb="Trigger INSTEAD OF", bboxes=[[40, 220, 600, 300]],
                           body="Trigger INSTEAD OF thay thế thao tác INSERT/UPDATE/DELETE, thường dùng trên view."))
    db.commit()
    yield m.id, cs
    db.execute(text("DELETE FROM section_materials WHERE file_name = 'test_semantic.pdf'"))
    db.commit()
    db.close()


def _embedding(db, mid):
    return db.execute(text("SELECT embedding FROM material_passages WHERE material_id = :m ORDER BY seq"),
                      {"m": mid}).scalar()


@real_model
def test_embed_missing_stores_vectors_once(material):
    mid, cs = material
    db = SessionLocal()
    try:
        before = db.execute(text("SELECT id, seq, body FROM material_passages WHERE material_id = :m ORDER BY seq"),
                            {"m": mid}).fetchall()
        assert semantic.embed_missing(db, cs) >= 2
        rows = db.execute(text("SELECT id, seq, body, embedding FROM material_passages WHERE material_id = :m "
                               "ORDER BY seq"), {"m": mid}).fetchall()
        assert [r[:3] for r in rows] == [tuple(r) for r in before]               # cập nhật hàng loạt theo khóa chính:
        want = semantic.encode([search._doc_text(t, t, None, b, None) for t, b in      # mỗi đoạn đúng vector của nó
                                db.execute(text("SELECT title, body FROM material_passages WHERE material_id = :m "
                                                "ORDER BY seq"), {"m": mid})])
        for r, w in zip(rows, want):
            assert len(r[3]) == 768 and np.allclose(semantic.unpack(r[3]), w, atol=1e-2)
        assert db.get(SectionMaterial, mid).embed_model == semantic.model_name()
        db.rollback()
        assert semantic.embed_missing(db, cs) == 0                              # đã có vector: không tính lại
    finally:
        db.close()


@real_model
def test_embed_missing_drops_result_when_material_reindexed_meanwhile(material, monkeypatch):
    mid, cs = material
    real = semantic.encode

    def encode_while_reindexed(texts):
        with SessionLocal() as other:                                           # bên khác nạp lại trong lúc tính
            other.execute(text("UPDATE section_materials SET indexed_at = :t WHERE id = :m"),
                          {"t": datetime.now() + timedelta(seconds=5), "m": mid})
            other.commit()
        return real(texts)
    db = SessionLocal()
    try:
        semantic.embed_missing(db, cs)                                          # các học liệu khác của lớp: tính trước
        db.execute(text("UPDATE section_materials SET embed_model = NULL WHERE id = :m"), {"m": mid})
        db.execute(text("UPDATE material_passages SET embedding = NULL WHERE material_id = :m"), {"m": mid})
        db.commit()
        monkeypatch.setattr(semantic, "encode", encode_while_reindexed)
        assert semantic.embed_missing(db, cs) == 0
        assert _embedding(db, mid) is None and db.get(SectionMaterial, mid).embed_model is None
    finally:
        db.close()


@real_model
def test_embed_missing_tolerates_passages_deleted_meanwhile(material, monkeypatch):
    mid, cs = material
    real = semantic.encode

    def encode_while_deleted(texts):
        with SessionLocal() as other:                                           # nạp lại: đoạn cũ bị xóa, ghi lại
            other.execute(text("DELETE FROM material_passages WHERE material_id = :m AND seq = 2"), {"m": mid})
            other.execute(text("UPDATE section_materials SET indexed_at = :t WHERE id = :m"),
                          {"t": datetime.now() + timedelta(seconds=5), "m": mid})
            other.commit()
        return real(texts)
    db = SessionLocal()
    try:
        semantic.embed_missing(db, cs)
        db.execute(text("UPDATE section_materials SET embed_model = NULL WHERE id = :m"), {"m": mid})
        db.commit()
        monkeypatch.setattr(semantic, "encode", encode_while_deleted)
        assert semantic.embed_missing(db, cs) == 0                              # không ném lỗi, bỏ kết quả
        assert db.get(SectionMaterial, mid).embed_model is None
    finally:
        db.close()


@real_model
def test_unrelated_question_gets_no_pages_related_one_does(material):
    mid, cs = material
    db = SessionLocal()
    try:
        semantic.embed_missing(db, cs)
        search.warm(db, cs)
        pitr = db.get(Question, PITR)
        assert any(p.material_id == mid for p in suggest.for_question(db, cs, pitr))
        off = Question(content="Mô hình nào dự báo thời tiết cho một thời điểm cụ thể trong ngày?",
                       options=[QuestionOption(content="Mô hình khí tượng số", is_correct=True),
                                QuestionOption(content="Mô hình hồi quy", is_correct=False)])
        assert suggest.rank_passages(search.section_index(db, cs), off.content, ["Mô hình khí tượng số"])  # BM25 có
        assert suggest.for_question(db, cs, off) == []                          # ... nhưng cổng chặn
    finally:
        db.close()
