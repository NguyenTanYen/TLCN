"""UC-05: Sinh viên xem kết quả và lộ trình cá nhân hóa."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require
from ..models import User

router = APIRouter(prefix="/api/me", tags=["UC-05 Lộ trình cá nhân"])


def _student_id(u: User) -> int:
    if not u.student:
        raise HTTPException(403, "Tài khoản chưa gắn với sinh viên")
    return u.student.id


@router.get("/exams")
def my_exams(u: User = Depends(require("student")), db: Session = Depends(get_db)):
    sid = _student_id(u)
    return [dict(r) for r in db.execute(text("""
        SELECT e.id, e.exam_title, e.exam_type, e.assessment_type, e.status, e.publish_flag, c.course_code, c.course_name,
               cs.section_code, s.name AS semester, a.status AS attempt_status
        FROM enrollments en JOIN class_sections cs ON cs.id=en.class_section_id
        JOIN exams e ON e.class_section_id=cs.id JOIN courses c ON c.id=cs.course_id JOIN semesters s ON s.id=cs.semester_id
        LEFT JOIN exam_attempts a ON a.exam_id=e.id AND a.student_id=en.student_id
        WHERE en.student_id=:s ORDER BY s.academic_year DESC, s.term DESC, e.id DESC"""), {"s": sid}).mappings()]


@router.get("/exams/{exam_id}/learning-path")
def learning_path(exam_id: int, u: User = Depends(require("student")), db: Session = Depends(get_db)):
    sid = _student_id(u)
    e = db.execute(text("""SELECT e.id, e.exam_title, e.status, e.publish_flag, e.max_score, e.class_section_id,
                                  (SELECT SUM(points) FROM exam_questions WHERE exam_id=e.id) AS raw_max
                           FROM exams e JOIN enrollments en ON en.class_section_id=e.class_section_id AND en.student_id=:s
                           WHERE e.id=:e"""), {"e": exam_id, "s": sid}).mappings().first()
    if not e:
        raise HTTPException(404, "Không tìm thấy bài kiểm tra của bạn")
    if not e["publish_flag"]:  # E1
        raise HTTPException(403, "Kết quả phân tích đang được bảo lưu")
    att = db.execute(text("SELECT id, status, total_score FROM exam_attempts WHERE exam_id=:e AND student_id=:s"),
                     {"e": exam_id, "s": sid}).mappings().first()
    if not att or att["status"] == "absent":  # E2
        return {"exam_title": e["exam_title"], "insufficient_evidence": True,
                "message": "Chưa đủ bằng chứng đánh giá (bạn vắng thi hoặc chưa có bài làm)"}
    radar = [dict(r) for r in db.execute(text("""
        SELECT v.clo_code, c.description, v.score_pct, v.is_achieved, v.pass_threshold_pct,
               (SELECT ROUND(AVG(r2.score_pct),2) FROM attempt_clo_results r2 JOIN exam_attempts a2 ON a2.id=r2.attempt_id
                 WHERE a2.exam_id=v.exam_id AND r2.clo_id=c.id) AS class_avg
        FROM v_student_clo_radar v JOIN clos c ON c.clo_code=v.clo_code
             AND c.course_id=(SELECT cs.course_id FROM class_sections cs WHERE cs.id=:cs)
        WHERE v.attempt_id=:a ORDER BY v.clo_code"""), {"a": att["id"], "cs": e["class_section_id"]}).mappings()]
    path = db.execute(text("SELECT id, diagnostic_summary, recommended_study_plan FROM personalized_learning_paths WHERE attempt_id=:a"),
                      {"a": att["id"]}).mappings().first()
    items = []
    if path:
        items = [dict(r) for r in db.execute(text("""
            SELECT i.priority, c.clo_code, c.description AS clo_description, i.gap_pct,
                   o.chapter_number, o.chapter_name
            FROM learning_path_items i JOIN clos c ON c.id=i.clo_id LEFT JOIN course_outlines o ON o.id=i.outline_id
            WHERE i.path_id=:p ORDER BY i.priority, o.chapter_number"""), {"p": path["id"]}).mappings()]
    raw_max = float(e["raw_max"] or 1)
    return {"exam_title": e["exam_title"], "insufficient_evidence": False,
            "score": round(float(att["total_score"]) * float(e["max_score"]) / raw_max, 2), "max_score": float(e["max_score"]),
            "radar": radar, "summary": path["diagnostic_summary"] if path else None,
            "study_plan": path["recommended_study_plan"] if path else None, "items": items}
