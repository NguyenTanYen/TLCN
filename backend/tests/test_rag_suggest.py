"""Bước 8: SV làm sai câu nào → các trang học liệu của lớp nên đọc lại (gửi kèm kết quả về Moodle, GV xem trước)."""
from datetime import datetime

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models import MaterialPage, MaterialPassage, Question, SectionMaterial
from app.services import lms
from app.services.rag import search, suggest
from app.services.rag.search import Index

EXAM = 2                                   # "Thi cuối kỳ (Moodle)" của lớp gắn khóa Moodle 50 (dữ liệu mô phỏng)
PITR, INSTEAD_OF = 29, 14                  # câu point-in-time recovery / trigger INSTEAD OF – nhiều SV làm sai
URL = "http://moodle.test/pluginfile.php/1810/mod_resource/content/1/test_suggest.pdf"


def test_pages_of_groups_passages_by_page_keeping_best_rank():
    page = {1: "a", 2: "b", 3: "a", 4: "c"}
    assert suggest.pages_of([1, 2, 3, 4], page.get) == [("a", 1), ("b", 2), ("c", 4)]


def test_fuse_rrf_by_rank_with_weights():
    assert suggest.fuse([([1, 2, 3], 1.0), ([3, 9], 1.0)]) == [3, 1, 2, 9]             # có ở cả hai danh sách lên đầu
    assert suggest.fuse([([1, 2, 3], 1.0), ([9], 0.1)]) == [1, 2, 3, 9]                 # chỉ ở danh sách phụ: xếp sau
    # ... nhưng có ở CẢ HAI thì vẫn vượt lên dù trọng số phụ rất nhỏ – lý do RRF với phương án sai làm Hit@1 giảm
    assert suggest.fuse([([1, 2, 3], 1.0), ([3, 9], 0.1)])[0] == 3


def test_rank_uses_stem_and_correct_answer_wrong_option_off_by_default():
    ix = Index.build([(1, "Recovery model FULL cho phép phục hồi về một thời điểm (point-in-time)."),
                      (2, "Recovery model SIMPLE tự cắt nhật ký giao tác."),
                      (3, "Trigger INSTEAD OF thay thế thao tác INSERT.")])
    stem = "Để phục hồi CSDL về một thời điểm cụ thể, CSDL phải dùng recovery model:"
    assert suggest.rank_passages(ix, stem, ["FULL"])[0] == 1
    assert suggest.rank_passages(ix, stem, ["FULL"], "SIMPLE") == suggest.rank_passages(ix, stem, ["FULL"])


@pytest.fixture()
def material():
    db = SessionLocal()
    cs = db.execute(text("SELECT class_section_id FROM exams WHERE id = :e"), {"e": EXAM}).scalar()
    m = SectionMaterial(class_section_id=cs, source="moodle", title="Slide sao lưu và trigger", status="ready",
                        file_name="test_suggest.pdf", content_hash="5a" * 20, moodle_cmid=1810, moodle_file_url=URL,
                        indexed_at=datetime.now().replace(microsecond=0), n_pages=3)
    db.add(m)
    db.flush()
    for no, (title, body) in enumerate([
            ("Recovery model", "Recovery model FULL ghi đầy đủ nhật ký, cho phép phục hồi CSDL về một thời điểm cụ thể "
                               "(point-in-time recovery). SIMPLE và BULK_LOGGED không bảo đảm điều này."),
            ("Trigger INSTEAD OF", "Trigger INSTEAD OF thay thế thao tác INSERT/UPDATE/DELETE, thường dùng trên view."),
            ("Giới thiệu", "Nội dung học phần.")], 1):
        pg = MaterialPage(material_id=m.id, page_no=no, width=720, height=540)
        db.add(pg)
        db.flush()
        db.add(MaterialPassage(material_id=m.id, page_id=pg.id, seq=no, kind="text", title=title, breadcrumb=title,
                               body=body, bboxes=[[40, 80, 600, 200]]))
    db.commit()
    search.warm(db, cs)
    yield m.id, cs
    db.execute(text("DELETE FROM section_materials WHERE file_name = 'test_suggest.pdf'"))
    db.commit()
    db.close()


def _ours(pages, mid):
    """Chỉ trang của học liệu test này (dữ liệu gửi Moodle có tên học liệu, API GV có id)."""
    return [p for p in pages if p.get("material_id") == mid or p.get("material") == "Slide sao lưu và trigger"]


def test_wrong_answers_get_material_pages_in_results_sent_to_moodle(material):
    mid, _ = material
    db = SessionLocal()
    try:
        wrong = {(a, q): no for a, q, no in lms.wrong_items(db, EXAM)}
        rows = lms.student_results(db, EXAM)
        attempts = {a for a, _ in wrong}
        no_pitr = {wrong[(a, q)] for a, q in wrong if q == PITR}
        assert len(no_pitr) == 1                                   # một mã đề: cùng số câu cho mọi SV
        n_with, n_without = 0, 0
        ids = dict(db.execute(text("SELECT s.student_code, a.id FROM exam_attempts a JOIN students s "
                                   "ON s.id = a.student_id WHERE a.exam_id = :e"), {"e": EXAM}).fetchall())
        for r in rows:
            att = ids[r["student_code"]]
            mats = {m["question"]: m["pages"] for m in r["data"].get("materials", [])}
            if (att, PITR) in wrong:
                pages = _ours(mats[wrong[(att, PITR)]], mid)
                assert PITR in {m["question_id"] for m in r["data"]["materials"]}     # plugin khớp câu theo QB-n
                assert pages[0]["page"] == 1 and pages[0]["url"] == URL + "#page=1"
                assert pages[0]["heading"] == "Recovery model"
                n_with += 1
            elif att in attempts:
                assert next(iter(no_pitr)) not in mats                # làm đúng câu đó: không gợi ý câu đó
                n_without += 1
        assert n_with == 25 and n_without > 0
        assert all("clos" not in lms.public_data(r["data"]) for r in rows)
        assert any(lms.public_data(r["data"]).get("materials") for r in rows)  # gợi ý được gửi cho SV
    finally:
        db.close()


def test_suggestion_failure_does_not_block_sending_results(material, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("chỉ mục hỏng")
    monkeypatch.setattr(suggest, "for_questions", boom)
    db = SessionLocal()
    try:
        rows = lms.student_results(db, EXAM)
        assert rows and all(not r["data"].get("materials") for r in rows)
    finally:
        db.close()


def test_lecturer_previews_suggestions_per_question(client, gv, gv_other, material):
    mid, _ = material
    r = client.get(f"/api/exams/{EXAM}/material-suggestions", headers=gv)
    assert r.status_code == 200, r.text
    by_q = {x["question_id"]: x for x in r.json()}
    assert by_q[PITR]["n_wrong"] == 25 and by_q[INSTEAD_OF]["n_wrong"] == 22
    assert _ours(by_q[PITR]["pages"], mid)[0]["page_no"] == 1
    assert _ours(by_q[INSTEAD_OF]["pages"], mid)[0]["page_no"] == 2
    assert client.get(f"/api/exams/{EXAM}/material-suggestions", headers=gv_other).status_code == 403


def test_close_pages_drops_pages_far_below_the_closest():
    pages = [("a", 0.60), ("b", 0.70), ("c", 0.56), ("d", 0.40)]
    assert suggest.close_pages(pages, 0.15) == ["a", "b", "c"]                  # giữ thứ tự gợi ý, bỏ d (0,70 − 0,40)
    assert suggest.close_pages(pages, None, 0.58) == ["a", "b"]
    assert suggest.close_pages([("x", 0.1)], 0.15) == ["x"]                     # trang gần nhất luôn được giữ
    assert suggest.close_pages([], 0.15) == []


def test_weak_pages_are_trimmed_after_the_gate(material, monkeypatch):
    from app.services.rag import semantic
    _, cs = material
    db = SessionLocal()
    try:
        q = db.get(Question, PITR)
        full = suggest.for_question(db, cs, q)
        assert len(full) >= 2
        # đoạn đứng đầu rất gần câu hỏi, các đoạn khác kém xa → chỉ còn trang của đoạn đầu
        monkeypatch.setattr(semantic, "scores", lambda query, embs: [0.8] + [0.5] * (len(embs) - 1))
        trimmed = suggest.for_question(db, cs, q)
        assert [(p.material_id, p.page_no) for p in trimmed] == [(full[0].material_id, full[0].page_no)]
        monkeypatch.setattr(semantic, "scores", lambda query, embs: [0.4] * len(embs))   # dưới cổng: không gợi ý
        assert suggest.for_question(db, cs, q) == []
    finally:
        db.close()
