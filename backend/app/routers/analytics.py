"""UC-04: Thống kê lớp học – tổng quan bài KT, chỉ số câu hỏi, kết quả CLO (BM6b) và minh chứng (BM6c)."""
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import check_section_access, get_exam_for, require
from ..models import CLOResult, User
from ..schemas import NarrativeIn
from ..services import analysis

router = APIRouter(prefix="/api", tags=["UC-04 Thống kê lớp học"])


def rows(db, sql, **p):
    return [dict(r) for r in db.execute(text(sql), p).mappings()]


def classify(p, di):
    """Phân loại câu hỏi theo p (0,3–0,7 phù hợp) và DI (Ebel & Frisbie, 1991)."""
    if p is None:
        return "Chưa đủ dữ liệu"
    p, di = float(p), (None if di is None else float(di))
    if di is not None and di < 0:
        return "Cần loại bỏ/kiểm tra đáp án"
    if di is not None and di < 0.2:
        return "Cần xem lại (DI thấp)"
    if p > 0.85:
        return "Quá dễ"
    if p < 0.25:
        return "Quá khó"
    return "Tốt" if di is None or di >= 0.3 else "Chấp nhận được"


@router.get("/exams/{exam_id}/overview")
def overview(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    raw_max = float(db.execute(text("SELECT COALESCE(SUM(points),0) FROM exam_questions WHERE exam_id=:e"), {"e": exam_id}).scalar() or 0)
    scores = [float(r[0]) for r in db.execute(text("SELECT total_score FROM exam_attempts WHERE exam_id=:e AND status='finished'"), {"e": exam_id})]
    scale = float(e.max_score) / raw_max if raw_max else 1
    conv = [round(s * scale, 2) for s in scores]
    bins = [0] * 10
    for s in conv:
        bins[min(9, int(s / float(e.max_score) * 10))] += 1
    n_abs = db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e AND status='absent'"), {"e": exam_id}).scalar()
    corr = pd.DataFrame(db.execute(text("""SELECT r.attempt_id, r.question_id, r.is_correct FROM item_level_results r
        JOIN exam_attempts a ON a.id = r.attempt_id JOIN question_bank q ON q.id = r.question_id
        WHERE a.exam_id = :e AND a.status = 'finished' AND q.is_cancelled = 0"""), {"e": exam_id}).fetchall(),
        columns=["attempt_id", "question_id", "is_correct"])
    if not corr.empty:
        corr["is_correct"] = corr.is_correct.astype(int)
    return {"n_students": len(conv), "n_absent": n_abs, "max_score": float(e.max_score), "kr20": analysis.kr20(corr),
            "mean": round(sum(conv) / len(conv), 2) if conv else None,
            "min": min(conv) if conv else None, "max": max(conv) if conv else None,
            "pass_rate": round(100 * sum(1 for s in conv if s >= float(e.max_score) / 2) / len(conv), 2) if conv else None,
            "histogram": [{"range": f"{i * float(e.max_score) / 10:g}–{(i + 1) * float(e.max_score) / 10:g}", "count": c} for i, c in enumerate(bins)],
            "status": e.status, "publish_flag": e.publish_flag}


@router.get("/exams/{exam_id}/item-stats")
def item_stats(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    get_exam_for(db, u, exam_id)
    data = rows(db, """
        SELECT eq.order_index, q.id AS question_id, LEFT(q.content, 160) AS content, q.is_cancelled, eq.points,
               st.n_students, st.p_value, st.di_value,
               (SELECT GROUP_CONCAT(c.clo_code ORDER BY c.clo_code) FROM question_clo_mapping m JOIN clos c ON c.id=m.clo_id
                 WHERE m.question_id=q.id) AS clos,
               (SELECT CONCAT('Chương ', o.chapter_number) FROM course_outlines o WHERE o.id=q.outline_id) AS chapter
        FROM exam_questions eq JOIN question_bank q ON q.id=eq.question_id
        LEFT JOIN item_statistics st ON st.exam_id=eq.exam_id AND st.question_id=eq.question_id
        WHERE eq.exam_id=:e ORDER BY eq.order_index""", e=exam_id)
    # phân bố lựa chọn: đủ mọi phương án (kể cả không ai chọn) + bỏ trống
    dist = rows(db, """
        SELECT o.question_id, o.opt_label AS label, o.is_correct,
               (SELECT COUNT(*) FROM item_level_results r JOIN exam_attempts a ON a.id=r.attempt_id
                 WHERE a.exam_id=:e AND a.status='finished' AND r.selected_option_id=o.id) AS n
        FROM question_options o JOIN exam_questions eq ON eq.question_id=o.question_id AND eq.exam_id=:e
        UNION ALL
        SELECT r.question_id, '(bỏ trống)', 0, COUNT(*) FROM item_level_results r JOIN exam_attempts a ON a.id=r.attempt_id
        WHERE a.exam_id=:e AND a.status='finished' AND r.response_status='blank' GROUP BY r.question_id
        ORDER BY label""", e=exam_id)
    for d in data:
        d["classification"] = classify(d["p_value"], d["di_value"])
        d["distribution"] = [{"label": x["label"], "n": x["n"], "is_correct": bool(x["is_correct"])} for x in dist if x["question_id"] == d["question_id"]]
    return data


@router.get("/exams/{exam_id}/students")
def exam_students(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    get_exam_for(db, u, exam_id)
    data = rows(db, """SELECT a.id AS attempt_id, s.id AS student_id, s.student_code, s.full_name, a.status, a.source, a.total_score,
                              (SELECT version_code FROM exam_versions v WHERE v.id=a.version_id) AS version_code
                       FROM exam_attempts a JOIN students s ON s.id=a.student_id WHERE a.exam_id=:e ORDER BY s.student_code""", e=exam_id)
    clo = rows(db, """SELECT r.attempt_id, c.clo_code, r.score_pct, r.is_achieved FROM attempt_clo_results r
                      JOIN clos c ON c.id=r.clo_id JOIN exam_attempts a ON a.id=r.attempt_id WHERE a.exam_id=:e""", e=exam_id)
    for d in data:
        d["clos"] = {x["clo_code"]: {"pct": float(x["score_pct"]), "ok": bool(x["is_achieved"])} for x in clo if x["attempt_id"] == d["attempt_id"]}
    return data


@router.get("/class-sections/{cs_id}/clo-results")
def clo_results(cs_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """BM6b – kết quả tổng hợp của từng CĐR môn học (E1: rỗng nếu chưa phân tích)."""
    cs = check_section_access(db, u, cs_id)
    data = rows(db, """
        SELECT c.id AS clo_id, c.clo_code, c.description, r.n_evaluated, r.n_achieved, r.achieved_pct,
               COALESCE(r.target_pct, p.target_pct, co.clo_target_pct) AS target_pct, r.is_achieved, r.analysis, r.improvement,
               COALESCE(p.pass_threshold_pct, :thr0) AS pass_threshold_pct, p.evidence_type,
               (SELECT GROUP_CONCAT(CONCAT(pl.plo_code, '(', m.level, ')') ORDER BY pl.plo_code) FROM clo_plo_mapping m
                 JOIN plos pl ON pl.id=m.plo_id WHERE m.clo_id=c.id) AS plos
        FROM clos c JOIN courses co ON co.id=c.course_id
        LEFT JOIN clo_results r ON r.clo_id=c.id AND r.class_section_id=:cs
        LEFT JOIN clo_assessment_plans p ON p.clo_id=c.id AND p.semester_id=:s
        WHERE c.course_id=:c ORDER BY c.clo_code""", cs=cs_id, s=cs.semester_id, c=cs.course_id,
        thr0=settings.default_pass_threshold)
    measured = [d for d in data if d["n_evaluated"]]
    ok = sum(d["n_achieved"] for d in measured); n = sum(d["n_evaluated"] for d in measured)
    target = float(cs.course.clo_target_pct)
    return {"class_section_id": cs_id, "course": f"{cs.course.course_code} – {cs.course.course_name}", "semester": cs.semester.name,
            "clos": data, "has_data": bool(measured),
            "course_result": {"n_achieved": ok, "n_evaluated": n, "achieved_pct": round(100 * ok / n, 2) if n else None,
                              "target_pct": target, "is_achieved": bool(n) and 100 * ok / n + 1e-9 >= target}}


@router.get("/class-sections/{cs_id}/clo-results/{clo_id}/evidence")
def clo_evidence(cs_id: int, clo_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """BM6c/6d – bảng minh chứng: điểm từng SV trên các câu thuộc CLO, theo từng bài KT; câu hỏi có DI thấp."""
    check_section_access(db, u, cs_id)
    ev = rows(db, """SELECT e.id AS exam_id, e.exam_title, e.assessment_type, s.student_code, s.full_name,
                            r.score_earned, r.score_max, r.score_pct, r.is_achieved
                     FROM attempt_clo_results r JOIN exam_attempts a ON a.id=r.attempt_id JOIN exams e ON e.id=a.exam_id
                     JOIN students s ON s.id=a.student_id
                     WHERE e.class_section_id=:cs AND r.clo_id=:c ORDER BY e.id, s.student_code""", cs=cs_id, c=clo_id)
    questions = rows(db, """SELECT e.exam_title, eq.order_index, q.id AS question_id, LEFT(q.content, 140) AS content,
                                   m.weight, st.p_value, st.di_value
                            FROM question_clo_mapping m JOIN question_bank q ON q.id=m.question_id
                            JOIN exam_questions eq ON eq.question_id=q.id JOIN exams e ON e.id=eq.exam_id
                            LEFT JOIN item_statistics st ON st.exam_id=e.id AND st.question_id=q.id
                            WHERE e.class_section_id=:cs AND m.clo_id=:c ORDER BY st.di_value IS NULL, st.di_value""", cs=cs_id, c=clo_id)
    for q in questions:
        q["classification"] = classify(q["p_value"], q["di_value"])
    return {"evidence": ev, "questions": questions}


@router.put("/class-sections/{cs_id}/clo-results/{clo_id}")
def clo_narrative(cs_id: int, clo_id: int, body: NarrativeIn, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    check_section_access(db, u, cs_id)
    r = db.get(CLOResult, (cs_id, clo_id))
    if not r:
        raise HTTPException(404, "CLO chưa có kết quả đo")
    r.analysis, r.improvement = body.analysis, body.improvement
    db.commit()
    return {"ok": True}
