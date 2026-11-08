"""Hủy câu sau khi bài KT đã phân tích → minh chứng CLO được tính lại ngay (không chờ GV bấm "Phân tích lại")."""
from sqlalchemy import text

from app.database import SessionLocal
from app.services import qsync, results


def _pick(db):
    """Một câu (có gắn CLO) trong bài KT đã phân tích, có bài làm, của lớp do gv.son dạy."""
    return db.execute(text("""
        SELECT eq.question_id, e.id FROM exams e
        JOIN exam_questions eq ON eq.exam_id = e.id
        JOIN question_bank q ON q.id = eq.question_id AND q.is_cancelled = 0
        JOIN question_clo_mapping m ON m.question_id = q.id
        JOIN class_sections cs ON cs.id = e.class_section_id
        JOIN lecturers l ON l.id = cs.lecturer_id JOIN users u ON u.id = l.user_id
        WHERE e.status = 'Analyzed' AND u.username = 'gv.son'
          AND EXISTS (SELECT 1 FROM exam_attempts a WHERE a.exam_id = e.id)
        ORDER BY e.id, eq.order_index LIMIT 1""")).one()


def _score_max(db, exam_id):
    return db.execute(text("""SELECT SUM(r.score_max) FROM attempt_clo_results r JOIN exam_attempts a ON a.id = r.attempt_id
                              WHERE a.exam_id = :e"""), {"e": exam_id}).scalar()


def test_cancel_question_reanalyzes_exam(client, gv):
    db = SessionLocal()
    qid, exam_id = _pick(db)
    before = _score_max(db, exam_id)
    try:
        r = client.patch(f"/api/questions/{qid}/cancel", headers=gv, json={"reason": "Phúc khảo: đề sai"})
        assert r.status_code == 200 and exam_id in r.json()["reanalyzed_exams"] and r.json()["reanalyze_failed"] == []
        db.rollback()
        assert _score_max(db, exam_id) < before
    finally:
        db.execute(text("UPDATE question_bank SET is_cancelled = 0, cancel_reason = NULL WHERE id = :q"), {"q": qid})
        db.commit()
        results.analyze_exam(db, exam_id)
        db.rollback()
        assert _score_max(db, exam_id) == before
        db.close()


def test_cancel_question_isolates_reanalyze_failure(client, gv, monkeypatch):
    db = SessionLocal()
    qid, exam_id = _pick(db)

    def boom(_db, _exam_id):
        raise ZeroDivisionError("giả lập lỗi khi phân tích lại")

    monkeypatch.setattr(results, "analyze_exam", boom)
    try:
        r = client.patch(f"/api/questions/{qid}/cancel", headers=gv, json={"reason": "Phúc khảo: đề sai"})
        assert r.status_code == 200
        assert r.json()["reanalyze_failed"] == [exam_id] and r.json()["reanalyzed_exams"] == []
        db.rollback()
        assert db.execute(text("SELECT is_cancelled FROM question_bank WHERE id=:q"), {"q": qid}).scalar() == 1
    finally:
        monkeypatch.undo()
        db.execute(text("UPDATE question_bank SET is_cancelled = 0, cancel_reason = NULL WHERE id = :q"), {"q": qid})
        db.commit()
        db.close()


def test_sync_hash_has_no_concatenation_collision():
    a = qsync._fingerprint("Câu hỏi", [("12", True), ("3", False)])
    b = qsync._fingerprint("Câu hỏi", [("1", True), ("23", False)])
    assert a != b
    assert qsync._fingerprint("Câu hỏi", [("12", True), ("3", False)]) == a
