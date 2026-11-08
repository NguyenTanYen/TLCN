"""Góp ý F5: bài phụ đạo chỉ giao cho SV được chọn (giới hạn trên Moodle) và theo dõi tiến bộ trước → sau."""
import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.database import SessionLocal, engine
from app.models import Exam
from app.routers.remedial import target_moodle_users


def _q(sql, **kw):
    with engine.connect() as c:
        return c.execute(text(sql), kw).all()


@pytest.fixture(scope="module")
def remedial(client, gv):
    cs, ex = _q("SELECT class_section_id, id FROM exams WHERE status='Analyzed' AND target_students IS NULL ORDER BY id LIMIT 1")[0]
    sid, code = _q("""SELECT s.id, s.student_code FROM item_level_results r JOIN exam_attempts a ON a.id=r.attempt_id
                      JOIN students s ON s.id=a.student_id JOIN question_bank q ON q.id=r.question_id
                      WHERE a.exam_id=:e AND a.status='finished' AND r.is_correct=0 AND q.question_type='multichoice' AND q.is_cancelled=0
                      GROUP BY s.id, s.student_code ORDER BY COUNT(*) DESC LIMIT 1""", e=ex)[0]
    r = client.post(f"/api/class-sections/{cs}/remedial-exams", headers=gv,
                    json={"student_ids": [sid], "exam_ids": [ex], "similar_per_question": 0, "include_wrong": True})
    assert r.status_code == 201, r.text
    return {"cs": cs, "exam": r.json()["id"], "sid": sid, "code": code, "n": r.json()["n_questions"]}


def test_progress_before_attempt(client, gv, remedial):
    lst = client.get(f"/api/class-sections/{remedial['cs']}/remedial-exams", headers=gv).json()
    x = next(e for e in lst if e["exam_id"] == remedial["exam"])
    assert x["n_targets"] == 1 and x["n_done"] == 0 and x["avg_gain"] is None
    s = x["students"][0]
    assert s["student_code"] == remedial["code"] and s["status"] == "not_started"
    assert s["n_reused"] == remedial["n"] and s["before_pct"] is not None and s["before_pct"] < 100
    assert s["after_pct"] is None and s["gain"] is None


def test_progress_after_attempt(client, gv, remedial):
    qs = _q("""SELECT eq.question_id, eq.points, (SELECT id FROM question_options o WHERE o.question_id=eq.question_id AND o.is_correct LIMIT 1)
               FROM exam_questions eq WHERE eq.exam_id=:e""", e=remedial["exam"])
    with engine.begin() as c:
        c.execute(text("""INSERT INTO exam_attempts (exam_id, student_id, source, started_at, finished_at, status, total_score)
                          VALUES (:e, :s, 'moodle', NOW(), NOW(), 'finished', :t)"""),
                  {"e": remedial["exam"], "s": remedial["sid"], "t": sum(float(p) for _, p, _ in qs)})
        att = c.execute(text("SELECT id FROM exam_attempts WHERE exam_id=:e AND student_id=:s"), {"e": remedial["exam"], "s": remedial["sid"]}).scalar()
        for qid, pts, opt in qs:
            c.execute(text("""INSERT INTO item_level_results (attempt_id, question_id, selected_option_id, response_status, is_correct, score_earned)
                              VALUES (:a, :q, :o, 'answered', 1, :p)"""), {"a": att, "q": qid, "o": opt, "p": pts})
    lst = client.get(f"/api/class-sections/{remedial['cs']}/remedial-exams", headers=gv).json()
    x = next(e for e in lst if e["exam_id"] == remedial["exam"])
    s = x["students"][0]
    assert s["status"] == "finished" and s["after_same_pct"] == 100 and s["after_pct"] == 100
    assert s["gain"] == round(100 - s["before_pct"], 1) > 0 and x["n_done"] == 1 and x["avg_gain"] == s["gain"]


def test_restrict_requires_moodle_accounts(client, gv, remedial):
    assert client.post(f"/api/exams/{remedial['exam']}/moodle/restrict", headers=gv).status_code == 409
    regular = _q("SELECT id FROM exams WHERE class_section_id=:c AND target_students IS NULL LIMIT 1", c=remedial["cs"])[0][0]
    assert client.post(f"/api/exams/{regular}/moodle/restrict", headers=gv).status_code == 422
    old = _q("SELECT moodle_user_id FROM students WHERE id=:s", s=remedial["sid"])[0][0]
    db = SessionLocal()
    try:
        e = db.get(Exam, remedial["exam"])
        with engine.begin() as c:
            c.execute(text("UPDATE students SET moodle_user_id=NULL WHERE id=:s"), {"s": remedial["sid"]})
        db.rollback()
        with pytest.raises(HTTPException) as ex:
            target_moodle_users(db, e)
        assert ex.value.status_code == 422 and remedial["code"] in ex.value.detail
        with engine.begin() as c:
            c.execute(text("UPDATE students SET moodle_user_id=987654 WHERE id=:s"), {"s": remedial["sid"]})
        db.rollback()
        assert target_moodle_users(db, e) == [987654]
    finally:
        db.close()
        with engine.begin() as c:
            c.execute(text("UPDATE students SET moodle_user_id=:m WHERE id=:s"), {"m": old, "s": remedial["sid"]})


def test_overview_theo_chuong_va_loc_chuong(client, gv, remedial):
    """Nhóm SV yếu gom theo chương (không theo CLO từng SV); tạo bài ôn có thể giới hạn theo chương."""
    ov = client.get(f"/api/class-sections/{remedial['cs']}/remedial", headers=gv).json()
    assert ov["chapters"] and all({"label", "n_students", "student_ids", "n_wrong"} <= set(c) for c in ov["chapters"])
    assert all("weak_chapters" in s and "weak_clos" not in s for s in ov["students"])
    ch = next((c for c in ov["chapters"] if c.get("outline_id")), None)
    if ch:
        r = client.post(f"/api/class-sections/{remedial['cs']}/remedial-exams", headers=gv,
                        json={"student_ids": ch["student_ids"][:3], "exam_ids": [], "similar_per_question": 0,
                              "include_wrong": True, "outline_ids": [ch["outline_id"]]})
        assert r.status_code in (201, 400, 422), r.text


def test_restrict_thanh_cong_va_loi_moodle(client, gv, remedial, monkeypatch):
    from app.services import lms
    old = _q("SELECT moodle_user_id FROM students WHERE id=:s", s=remedial["sid"])[0][0]
    cs_old = _q("SELECT moodle_course_id FROM class_sections WHERE id=:c", c=remedial["cs"])[0][0]
    with engine.begin() as c:
        c.execute(text("UPDATE students SET moodle_user_id=987654 WHERE id=:s"), {"s": remedial["sid"]})
        c.execute(text("UPDATE class_sections SET moodle_course_id=7 WHERE id=:c"), {"c": remedial["cs"]})
        c.execute(text("UPDATE exams SET moodle_quiz_id=321 WHERE id=:e"), {"e": remedial["exam"]})
    seen = {}

    def ok(course, quiz, name, users, cmid=0):
        seen.update(course=course, quiz=quiz, users=users)
        return {"group": name, "users": len(users)}

    def fail(*a, **k):
        raise lms.MoodleWSError("Moodle từ chối")

    try:
        monkeypatch.setattr(lms, "restrict_users", ok)
        r = client.post(f"/api/exams/{remedial['exam']}/moodle/restrict", headers=gv)
        assert r.status_code == 200 and seen == {"course": 7, "quiz": 321, "users": [987654]}
        monkeypatch.setattr(lms, "restrict_users", fail)
        assert client.post(f"/api/exams/{remedial['exam']}/moodle/restrict", headers=gv).status_code == 502
    finally:
        with engine.begin() as c:
            c.execute(text("UPDATE students SET moodle_user_id=:m WHERE id=:s"), {"m": old, "s": remedial["sid"]})
            c.execute(text("UPDATE class_sections SET moodle_course_id=:m WHERE id=:c"), {"m": cs_old, "c": remedial["cs"]})
            c.execute(text("UPDATE exams SET moodle_quiz_id=NULL WHERE id=:e"), {"e": remedial["exam"]})
