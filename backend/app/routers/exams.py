"""UC-02: Khởi tạo đề thi – xuất Moodle XML; liên kết Quiz; công bố kết quả. (Đề giấy do Moodle Offline Quiz sinh – xem routers/lms.py)"""
import math

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..http_utils import attachment
from ..deps import check_moodle_course, check_section_access, get_exam_for, require
from ..models import Exam, ExamQuestion, Question, User
from ..schemas import BlueprintIn, ExamIn, LinkQuizIn, PublishIn
from ..services import blueprint as bp, lms, moodle, xml_export

router = APIRouter(prefix="/api", tags=["UC-02 Đề thi"])


def exam_dict(db: Session, e: Exam) -> dict:
    cs = e.class_section
    return {"id": e.id, "exam_title": e.exam_title, "assessment_type": e.assessment_type, "exam_type": e.exam_type,
            "exam_date": e.exam_date, "duration_minutes": e.duration_minutes, "max_score": float(e.max_score),
            "moodle_quiz_id": e.moodle_quiz_id, "moodle_offlinequiz_id": e.moodle_offlinequiz_id, "status": e.status, "publish_flag": e.publish_flag,
            "last_synced_at": e.last_synced_at, "class_section_id": e.class_section_id, "section_code": cs.section_code,
            "moodle_course_id": cs.moodle_course_id,
            "course_id": cs.course_id, "course_code": cs.course.course_code, "course_name": cs.course.course_name,
            "semester": cs.semester.name,
            "questions": [{"question_id": q.question_id, "order_index": q.order_index, "points": float(q.points),
                           "content": q.question.content, "is_cancelled": q.question.is_cancelled,
                           "outline_id": q.question.outline_id, "bloom_level_id": q.question.bloom_level_id,
                           "chapter": q.question.outline.chapter_number if q.question.outline else None,
                           "bloom": q.question.bloom.name_vi if q.question.bloom else None,
                           "clos": ", ".join(c.clo.clo_code for c in q.question.clo_links)} for q in e.questions],
            "versions": [{"id": v.id, "version_code": v.version_code} for v in e.versions],
            "n_attempts": db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e AND status='finished'"), {"e": e.id}).scalar(),
            "n_absent": db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e AND status='absent'"), {"e": e.id}).scalar()}


@router.get("/class-sections/{cs_id}/exams")
def list_exams(cs_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    check_section_access(db, u, cs_id)
    return [exam_dict(db, e) for e in db.query(Exam).filter_by(class_section_id=cs_id).order_by(Exam.id).all()]


# ------------------------------------------------------------------ ma trận đề & sinh đề tự động
def _pool(db: Session, course_id: int, outline_ids: list[int]):
    """Các câu dùng được để ra đề (đã gán Bloom và CLO, chưa Hủy) kèm chỉ số p, DI trung bình và số lần dùng."""
    rows = db.execute(text("""
        SELECT q.id, q.outline_id, q.bloom_level_id,
               (SELECT AVG(p_value) FROM item_statistics s WHERE s.question_id=q.id) AS avg_p,
               (SELECT AVG(di_value) FROM item_statistics s WHERE s.question_id=q.id) AS avg_di,
               (SELECT COUNT(*) FROM exam_questions eq WHERE eq.question_id=q.id) AS n_exams
        FROM question_bank q WHERE q.course_id=:c AND q.is_cancelled=0 AND q.bloom_level_id IS NOT NULL"""),
                      {"c": course_id}).mappings().all()
    links = {}
    for qid, cid, w in db.execute(text("""SELECT m.question_id, m.clo_id, m.weight FROM question_clo_mapping m
                                          JOIN question_bank q ON q.id=m.question_id WHERE q.course_id=:c"""), {"c": course_id}):
        links.setdefault(qid, {})[cid] = float(w)
    pool = [bp.Q(id=r["id"], outline_id=r["outline_id"], bloom=r["bloom_level_id"], clos=links[r["id"]],
                 avg_p=None if r["avg_p"] is None else float(r["avg_p"]), avg_di=None if r["avg_di"] is None else float(r["avg_di"]),
                 n_exams=int(r["n_exams"])) for r in rows if r["id"] in links]
    if outline_ids:
        pool = [q for q in pool if q.outline_id in outline_ids]
    untagged = db.execute(text("""SELECT COUNT(*) FROM question_bank q WHERE q.course_id=:c AND q.is_cancelled=0 AND
             (q.bloom_level_id IS NULL OR NOT EXISTS (SELECT 1 FROM question_clo_mapping m WHERE m.question_id=q.id))"""),
                          {"c": course_id}).scalar()
    return pool, int(untagged)


def _refs(db: Session, course_id: int):
    chapters = [dict(r) for r in db.execute(text("""SELECT id AS outline_id, chapter_number, chapter_name FROM course_outlines
                                                    WHERE course_id=:c ORDER BY chapter_number"""), {"c": course_id}).mappings()]
    blooms = [dict(r) for r in db.execute(text("SELECT id AS bloom_level_id, name_vi FROM bloom_levels ORDER BY id")).mappings()]
    clos = [dict(r) for r in db.execute(text("SELECT id AS clo_id, clo_code, description FROM clos WHERE course_id=:c ORDER BY clo_code"),
                                        {"c": course_id}).mappings()]
    return chapters, blooms, clos


def _avail_view(pool, chapters, blooms, clos):
    cell = {}
    for q in pool:
        cell[(q.outline_id, q.bloom)] = cell.get((q.outline_id, q.bloom), 0) + 1
    return {"cells": [{"outline_id": o, "bloom_level_id": b, "available": n} for (o, b), n in sorted(cell.items(), key=lambda x: (x[0][0] or 0, x[0][1]))],
            "chapters": [{**c, "available": sum(1 for q in pool if q.outline_id == c["outline_id"])} for c in chapters],
            "blooms": [{**b, "available": sum(1 for q in pool if q.bloom == b["bloom_level_id"])} for b in blooms],
            "clos": [{**c, "available": sum(1 for q in pool if c["clo_id"] in q.clos)} for c in clos],
            "pool_size": len(pool)}


@router.get("/class-sections/{cs_id}/exam-blueprint/pool")
def blueprint_pool(cs_id: int, outline_ids: str = "", u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """Số câu sẵn có theo từng ô ma trận (chương × mức Bloom) và theo CLO – để GV lập ma trận đề."""
    cs = check_section_access(db, u, cs_id)
    ids = [int(x) for x in outline_ids.split(",") if x.strip().isdigit()]
    pool, untagged = _pool(db, cs.course_id, ids)
    chapters, blooms, clos = _refs(db, cs.course_id)
    if ids:
        chapters = [c for c in chapters if c["outline_id"] in ids]
    return {**_avail_view(pool, chapters, blooms, clos), "untagged": untagged, "presets": bp.PRESETS}


@router.post("/class-sections/{cs_id}/exam-blueprint")
def blueprint_generate(cs_id: int, body: BlueprintIn, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """Sinh đề theo ma trận: trả về danh sách câu + điểm, ma trận mục tiêu/đạt được, độ phủ CLO, lỗi thiếu câu và cảnh báo.
    Không ghi CSDL – GV xem, chỉnh tay rồi mới lưu bài kiểm tra (POST /api/exams)."""
    cs = check_section_access(db, u, cs_id)
    chapters_all, blooms, clos = _refs(db, cs.course_id)
    valid_ch = {c["outline_id"] for c in chapters_all}
    if any(o not in valid_ch for o in body.outline_ids):
        raise HTTPException(422, "Chương không thuộc môn học của lớp")
    if any(c not in {x["clo_id"] for x in clos} for c in body.clo_ids):
        raise HTTPException(422, "CLO không thuộc môn học của lớp")
    pool, untagged = _pool(db, cs.course_id, body.outline_ids)
    chapters = [c for c in chapters_all if not body.outline_ids or c["outline_id"] in body.outline_ids]
    ch_label = {c["outline_id"]: f"chương {c['chapter_number']}" for c in chapters_all}
    bl_label = {b["bloom_level_id"]: b["name_vi"] for b in blooms}
    clo_label = {c["clo_id"]: c["clo_code"] for c in clos}
    names = {"chapter": lambda o: ch_label.get(o, "câu chưa gán chương"), "bloom": lambda b: bl_label.get(b, str(b)),
             "clo": lambda c: clo_label.get(c, str(c))}
    mix = {int(k): float(v) for k, v in body.bloom_mix.items()} if body.bloom_preset == "custom" else bp.PRESETS[body.bloom_preset]
    matrix = {(c.outline_id, c.bloom_level_id): c.n for c in body.matrix if c.n > 0}
    if matrix and body.outline_ids and any(k[0] not in body.outline_ids for k in matrix):
        raise HTTPException(422, "Ma trận có ô thuộc chương ngoài phạm vi bài kiểm tra")
    scope = body.clo_ids or [c["clo_id"] for c in clos]
    r = bp.generate(pool, n=body.n_questions, matrix=matrix or None, scope_clos=scope, bloom_mix=mix, min_per_clo=body.min_per_clo,
                    fixed=body.fixed_ids, prefer_unused=body.prefer_unused, seed=body.seed, names=names)
    if untagged:
        r.info.append(f"{untagged} câu trong ngân hàng chưa gán đủ CLO/Bloom nên không được dùng để ra đề")
    if body.outline_ids:
        r.info.append("Kiểm tra theo chương: chỉ lấy câu thuộc " + ", ".join(ch_label[o] for o in body.outline_ids))
    n = len(r.items)
    pts = []
    if n:
        base = math.floor(body.total_points / n * 100) / 100
        pts = [base] * n
        pts[-1] = round(body.total_points - base * (n - 1), 2)
    by_id = {q.id: q for q in pool}
    sel = {}
    for qid in r.items:
        k = (by_id[qid].outline_id, by_id[qid].bloom)
        sel[k] = sel.get(k, 0) + 1
    keys = sorted(set(sel) | set(r.target) | set(matrix), key=lambda k: (k[0] or 0, k[1]))
    view = _avail_view(pool, chapters, blooms, clos)
    av = {(c["outline_id"], c["bloom_level_id"]): c["available"] for c in view["cells"]}
    clo_cov = []
    for c in clos:
        qs = [qid for qid in r.items if c["clo_id"] in by_id[qid].clos]
        p = sum(pts[i] * by_id[qid].clos[c["clo_id"]] for i, qid in enumerate(r.items) if c["clo_id"] in by_id[qid].clos)
        clo_cov.append({**c, "available": sum(1 for q in pool if c["clo_id"] in q.clos), "selected": len(qs), "points": round(p, 2),
                        "in_scope": c["clo_id"] in scope and any(c["clo_id"] in q.clos for q in pool)})
    return {"ok": not r.errors, "errors": r.errors, "warnings": r.warnings, "info": r.info,
            "n_questions": n, "total_points": round(sum(pts), 2),
            "items": [{"question_id": qid, "points": pts[i]} for i, qid in enumerate(r.items)],
            "matrix": [{"outline_id": k[0], "bloom_level_id": k[1], "available": av.get(k, 0), "target": matrix.get(k, r.target.get(k, 0)),
                        "selected": sel.get(k, 0)} for k in keys],
            "chapters": view["chapters"], "blooms": view["blooms"], "clos": clo_cov, "pool_size": len(pool)}


@router.post("/exams", status_code=201)
def create_exam(body: ExamIn, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    cs = check_section_access(db, u, body.class_section_id)
    e = Exam(class_section_id=cs.id, exam_title=body.exam_title, assessment_type=body.assessment_type, exam_type=body.exam_type,
             exam_date=body.exam_date, duration_minutes=body.duration_minutes, max_score=body.max_score, created_by=u.id)
    for i, it in enumerate(body.items, 1):
        q = db.get(Question, it.question_id)
        if not q or q.course_id != cs.course_id:
            raise HTTPException(422, f"Câu hỏi {it.question_id} không thuộc môn học của lớp")
        if q.is_cancelled:
            raise HTTPException(422, f"Câu hỏi {it.question_id} đã bị Hủy, không được đưa vào đề mới")
        if q.bloom_level_id is None or not q.clo_links:
            raise HTTPException(422, f"Câu hỏi {it.question_id} chưa gán đủ CLO và mức Bloom – hãy gán trước khi đưa vào đề")
        e.questions.append(ExamQuestion(question_id=q.id, order_index=i, points=it.points))
    db.add(e); db.commit(); db.refresh(e)
    return exam_dict(db, e)


@router.get("/exams/{exam_id}")
def get_exam(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    return exam_dict(db, get_exam_for(db, u, exam_id))


@router.delete("/exams/{exam_id}")
def delete_exam(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    if db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e"), {"e": exam_id}).scalar():
        raise HTTPException(409, "Bài KT đã có kết quả thi, không thể xóa")
    db.delete(e); db.commit()
    return {"deleted": exam_id}


@router.get("/exams/{exam_id}/moodle-xml")
def moodle_xml(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    if e.exam_type != "online":
        raise HTTPException(422, "Chỉ bài KT trực tuyến mới xuất Moodle XML")
    xml = xml_export.exam_to_moodle_xml(e)
    if e.status == "Draft":
        e.status = "Published"; db.commit()
    return Response(xml, media_type="application/xml",
                    headers=attachment(f"exam_{exam_id}_moodle.xml"))


@router.patch("/exams/{exam_id}/link-quiz")
def link_quiz(exam_id: int, body: LinkQuizIn, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    if e.exam_type != "online":
        raise HTTPException(422, "Chỉ bài KT trực tuyến mới liên kết Moodle Quiz (bài giấy dùng Offline Quiz)")
    other = db.execute(text("SELECT id FROM exams WHERE moodle_quiz_id=:q AND id<>:e"), {"q": body.moodle_quiz_id, "e": exam_id}).scalar()
    if other:
        raise HTTPException(409, f"Quiz {body.moodle_quiz_id} đã được gắn với bài KT #{other}")
    course = moodle.activity_course(db, "quiz", body.moodle_quiz_id) if moodle.moodle_available() else None
    if not course:
        raise HTTPException(404, f"Không có Quiz id = {body.moodle_quiz_id} trên Moodle")
    cs = e.class_section
    check_moodle_course(db, u, cs, course)   # Quiz phải thuộc khóa học Moodle của lớp HP và GV phụ trách
    cs.moodle_course_id = course
    e.moodle_quiz_id = body.moodle_quiz_id
    db.commit()
    return {"id": exam_id, "moodle_quiz_id": body.moodle_quiz_id}


@router.patch("/exams/{exam_id}/publish")
def publish(exam_id: int, body: PublishIn, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    if body.publish and e.status != "Analyzed":
        raise HTTPException(409, "Chỉ công bố được bài KT đã phân tích")
    e.publish_flag = body.publish
    db.commit()
    out = {"id": exam_id, "publish_flag": e.publish_flag}
    # Công bố / thu hồi được đồng bộ ngay sang Moodle – nơi SV xem kết quả (UC-05)
    if not lms.configured():
        out["moodle_error"] = "chưa cấu hình Web Service Moodle (MOODLE_URL, MOODLE_WS_TOKEN)"
    elif not e.class_section.moodle_course_id:
        out["moodle_error"] = "lớp học phần chưa gắn khóa học Moodle"
    elif e.status == "Analyzed":
        try:
            out["moodle"] = lms.push_results(db, e)
        except lms.MoodleWSError as ex:
            out["moodle_error"] = str(ex)
    return out
