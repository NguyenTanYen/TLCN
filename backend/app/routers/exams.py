"""UC-02: Khởi tạo đề thi – xuất Moodle XML; liên kết Quiz; công bố kết quả. (Đề giấy do Moodle Offline Quiz sinh – xem routers/lms.py)"""
import math

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..http_utils import attachment
from ..deps import check_course_access, check_moodle_course, check_section_access, get_exam_for, require, lecturer_only
from ..models import ClassSection, Exam, ExamQuestion, Question, User
from ..schemas import BlueprintIn, ExamIn, LinkQuizIn, PublishIn
from ..services import blueprint as bp, lms, moodle, xml_export

router = APIRouter(prefix="/api", tags=["UC-02 Đề thi"])


def exam_dict(db: Session, e: Exam) -> dict:
    cs = e.class_section
    course = cs.course if cs else e.course
    return {"id": e.id, "exam_title": e.exam_title, "assessment_type": e.assessment_type, "exam_type": e.exam_type,
            "exam_date": e.exam_date, "duration_minutes": e.duration_minutes, "max_score": float(e.max_score),
            "moodle_quiz_id": e.moodle_quiz_id, "moodle_offlinequiz_id": e.moodle_offlinequiz_id, "status": e.status, "publish_flag": e.publish_flag,
            "last_synced_at": e.last_synced_at, "class_section_id": e.class_section_id, "section_code": cs.section_code if cs else None,
            "is_template": cs is None, "source_exam_id": e.source_exam_id,
            "counts_for_clo": e.counts_for_clo, "parent_exam_id": e.parent_exam_id, "target_students": e.target_students,
            "moodle_course_id": cs.moodle_course_id if cs else None,
            "course_id": course.id, "course_code": course.course_code, "course_name": course.course_name,
            "semester": cs.semester.name if cs else None,
            "deployments": deployments(db, e.id) if cs is None else None,
            "questions": [{"question_id": q.question_id, "order_index": q.order_index, "points": float(q.points),
                           "content": q.question.content, "is_cancelled": q.question.is_cancelled,
                           "question_type": q.question.question_type, "n_options": len(q.question.options),
                           "outline_id": q.question.outline_id, "bloom_level_id": q.question.bloom_level_id,
                           "chapter": q.question.outline.chapter_number if q.question.outline else None,
                           "bloom": q.question.bloom.name_vi if q.question.bloom else None,
                           "clos": ", ".join(c.clo.clo_code for c in q.question.clo_links)} for q in e.questions],
            "versions": [{"id": v.id, "version_code": v.version_code} for v in e.versions],
            "n_attempts": db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e AND status='finished'"), {"e": e.id}).scalar(),
            "n_absent": db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e AND status='absent'"), {"e": e.id}).scalar(),
            "n_enrolled": db.execute(text("SELECT COUNT(*) FROM enrollments WHERE class_section_id=:c AND status='active'"),
                                     {"c": e.class_section_id}).scalar() if cs else 0}


def deployments(db: Session, exam_id: int) -> list[dict]:
    """Các bài KT đã giao cho lớp HP từ một đề của môn."""
    return [dict(r) for r in db.execute(text("""
        SELECT e.id AS exam_id, e.class_section_id, cs.section_code, s.name AS semester, e.status, e.moodle_quiz_id,
               (SELECT COUNT(*) FROM exam_attempts a WHERE a.exam_id=e.id AND a.status='finished') AS n_attempts
        FROM exams e JOIN class_sections cs ON cs.id=e.class_section_id JOIN semesters s ON s.id=cs.semester_id
        WHERE e.source_exam_id=:e ORDER BY s.start_date DESC, cs.section_code"""), {"e": exam_id}).mappings()]


@router.get("/courses/{course_id}/exams")
def course_exams(course_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """Đề của môn (tạo ở trang môn học, chưa gắn lớp) kèm các lớp đã giao; và các lớp HP của người dùng để giao đề."""
    check_course_access(db, u, course_id)
    exams = db.query(Exam).filter(Exam.course_id == course_id, Exam.class_section_id.is_(None)).order_by(Exam.id.desc()).all()
    q = db.query(ClassSection).filter(ClassSection.course_id == course_id)
    if u.role == "lecturer":
        q = q.filter(ClassSection.lecturer_id == (u.lecturer.id if u.lecturer else -1))
    secs = sorted(q.all(), key=lambda c: (c.semester.start_date, c.section_code), reverse=True)
    return {"exams": [exam_dict(db, e) for e in exams],
            "sections": [{"id": c.id, "section_code": c.section_code, "semester": c.semester.name, "moodle_course_id": c.moodle_course_id,
                          "n_students": db.execute(text("SELECT COUNT(*) FROM enrollments WHERE class_section_id=:c AND status='active'"),
                                                   {"c": c.id}).scalar()} for c in secs]}


@router.get("/class-sections/{cs_id}/exams")
def list_exams(cs_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    check_section_access(db, u, cs_id)
    from ..services.timing import alerts_for_exams
    exams = db.query(Exam).filter_by(class_section_id=cs_id).order_by(Exam.id).all()
    alerts = alerts_for_exams(db, [e.id for e in exams if e.exam_type == "online"])
    return [{**exam_dict(db, e), "timing_alerts": alerts.get(e.id)} for e in exams]


# ------------------------------------------------------------------ ma trận đề & sinh đề tự động
def _pool(db: Session, course_id: int, outline_ids: list[int]):
    """Các câu dùng được để ra đề (đã gán Bloom và CLO, chưa Hủy) kèm chỉ số p, DI trung bình và số lần dùng."""
    rows = db.execute(text("""
        SELECT q.id, q.outline_id, q.bloom_level_id,
               (SELECT AVG(p_value) FROM item_statistics s WHERE s.question_id=q.id) AS avg_p,
               (SELECT AVG(di_value) FROM item_statistics s WHERE s.question_id=q.id) AS avg_di,
               (SELECT COUNT(*) FROM exam_questions eq JOIN exams x ON x.id=eq.exam_id WHERE eq.question_id=q.id AND x.class_section_id IS NOT NULL) AS n_exams
        FROM question_bank q WHERE q.course_id=:c AND q.question_type='multichoice' AND q.is_cancelled=0 AND q.bloom_level_id IS NOT NULL"""),
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
    untagged = db.execute(text("""SELECT COUNT(*) FROM question_bank q WHERE q.course_id=:c AND q.question_type='multichoice' AND q.is_cancelled=0 AND
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
    return _blueprint_pool(db, check_section_access(db, u, cs_id).course_id, outline_ids)


@router.get("/courses/{course_id}/exam-blueprint/pool")
def course_blueprint_pool(course_id: int, outline_ids: str = "", u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """Như trên, cho đề của môn (tạo ở trang môn học)."""
    check_course_access(db, u, course_id)
    return _blueprint_pool(db, course_id, outline_ids)


def _blueprint_pool(db: Session, course_id: int, outline_ids: str):
    ids = [int(x) for x in outline_ids.split(",") if x.strip().isdigit()]
    pool, untagged = _pool(db, course_id, ids)
    chapters, blooms, clos = _refs(db, course_id)
    if ids:
        chapters = [c for c in chapters if c["outline_id"] in ids]
    return {**_avail_view(pool, chapters, blooms, clos), "untagged": untagged, "presets": bp.PRESETS}


@router.post("/class-sections/{cs_id}/exam-blueprint")
def blueprint_generate(cs_id: int, body: BlueprintIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    """Sinh đề theo ma trận: trả về danh sách câu + điểm, ma trận mục tiêu/đạt được, độ phủ CLO, lỗi thiếu câu và cảnh báo.
    Không ghi CSDL – GV xem, chỉnh tay rồi mới lưu bài kiểm tra (POST /api/exams)."""
    return _blueprint_generate(db, check_section_access(db, u, cs_id).course_id, body)


@router.post("/courses/{course_id}/exam-blueprint")
def course_blueprint_generate(course_id: int, body: BlueprintIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    """Như trên, cho đề của môn (tạo ở trang môn học)."""
    check_course_access(db, u, course_id)
    return _blueprint_generate(db, course_id, body)


def _blueprint_generate(db: Session, course_id: int, body: BlueprintIn):
    chapters_all, blooms, clos = _refs(db, course_id)
    valid_ch = {c["outline_id"] for c in chapters_all}
    if any(o not in valid_ch for o in body.outline_ids):
        raise HTTPException(422, "Chương không thuộc môn học của lớp")
    if any(c not in {x["clo_id"] for x in clos} for c in body.clo_ids):
        raise HTTPException(422, "CLO không thuộc môn học của lớp")
    pool, untagged = _pool(db, course_id, body.outline_ids)
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
def create_exam(body: ExamIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    """Bài KT của một lớp HP, hoặc đề của môn (course_id) – giao cho các lớp HP khi xuất (POST /exams/{id}/copy)."""
    if body.class_section_id is not None:
        cs = check_section_access(db, u, body.class_section_id); course_id = cs.course_id
    else:
        check_course_access(db, u, body.course_id); cs = None; course_id = body.course_id
    e = Exam(class_section_id=cs.id if cs else None, course_id=None if cs else course_id, exam_title=body.exam_title, assessment_type=body.assessment_type, exam_type=body.exam_type,
             exam_date=body.exam_date, duration_minutes=body.duration_minutes, max_score=body.max_score, created_by=u.id)
    for i, it in enumerate(body.items, 1):
        q = db.get(Question, it.question_id)
        if not q or q.course_id != course_id:
            raise HTTPException(422, f"Câu hỏi {it.question_id} không thuộc môn học" + (" của lớp" if cs else ""))
        if q.is_cancelled:
            raise HTTPException(422, f"Câu hỏi {it.question_id} đã bị Hủy, không được đưa vào đề mới")
        if q.bloom_level_id is None or not q.clo_links:
            raise HTTPException(422, f"Câu hỏi {it.question_id} chưa gán đủ CLO và mức Bloom – hãy gán trước khi đưa vào đề")
        e.questions.append(ExamQuestion(question_id=q.id, order_index=i, points=it.points))
    db.add(e); db.commit(); db.refresh(e)
    return exam_dict(db, e)


@router.get("/exams/{exam_id}")
def get_exam(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    from ..services.timing import alerts_for_exams
    e = get_exam_for(db, u, exam_id, allow_template=True)
    return {**exam_dict(db, e), "timing_alerts": alerts_for_exams(db, [e.id]).get(e.id) if e.exam_type == "online" else None}


@router.delete("/exams/{exam_id}")
def delete_exam(exam_id: int, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    """Xóa bài KT chưa có kết quả. Xóa đề của môn không ảnh hưởng các bài đã giao cho lớp."""
    e = get_exam_for(db, u, exam_id, allow_template=True)
    if db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e"), {"e": exam_id}).scalar():
        raise HTTPException(409, "Bài KT đã có kết quả thi, không thể xóa")
    db.delete(e); db.commit()
    return {"deleted": exam_id}


@router.get("/exams/{exam_id}/moodle-xml")
def moodle_xml(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id, allow_template=True)
    if e.exam_type != "online":
        raise HTTPException(422, "Chỉ bài KT trực tuyến mới xuất Moodle XML")
    xml = xml_export.exam_to_moodle_xml(e)
    if e.status == "Draft" and e.class_section_id is not None:
        e.status = "Published"; db.commit()
    return Response(xml, media_type="application/xml",
                    headers=attachment(f"exam_{exam_id}_moodle.xml"))


@router.patch("/exams/{exam_id}/link-quiz")
def link_quiz(exam_id: int, body: LinkQuizIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
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


# ------------------------------------------------------------------ dùng một đề cho nhiều lớp HP cùng môn
class CopyIn(BaseModel):
    class_section_ids: list[int] = Field(min_length=1, max_length=30)
    create_moodle: bool = True      # bài trực tuyến: tạo luôn Quiz trên khóa học Moodle đã gắn của từng lớp


@router.post("/exams/{exam_id}/copy")
def copy_exam(exam_id: int, body: CopyIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    """Giao đề cho lớp HP: đề của môn (tạo ở trang môn học) được giao khi xuất cho các lớp GV chọn; bài của một lớp được
    dùng lại cho các lớp khác cùng môn. Mỗi lớp nhận một bài KT riêng (câu hỏi, điểm, cấu hình, câu/ý nhập điểm) và –
    với bài trực tuyến – Quiz trên khóa học Moodle đã gắn của lớp."""
    e = get_exam_for(db, u, exam_id, allow_template=True)
    src_cs = e.class_section
    src_course = src_cs.course_id if src_cs else e.course_id
    out = []
    for cs_id in dict.fromkeys(body.class_section_ids):
        if src_cs and cs_id == src_cs.id:
            continue
        cs = check_section_access(db, u, cs_id)
        if cs.course_id != src_course:
            raise HTTPException(422, f"Lớp {cs.section_code} không cùng môn học với đề gốc")
        dup = db.execute(text("SELECT id FROM exams WHERE source_exam_id=:e AND class_section_id=:c"), {"e": e.id, "c": cs.id}).scalar()
        if dup:
            out.append({"class_section_id": cs.id, "section_code": cs.section_code, "exam_id": dup, "skipped": True,
                        "moodle": f"lớp đã được giao đề này (bài #{dup}) – không tạo thêm"})
            continue
        n = Exam(class_section_id=cs.id, exam_title=e.exam_title, assessment_type=e.assessment_type, exam_type=e.exam_type,
                 exam_date=e.exam_date, duration_minutes=e.duration_minutes, max_score=e.max_score, counts_for_clo=e.counts_for_clo,
                 paper_settings=e.paper_settings, status="Published" if e.exam_type == "manual" else "Draft", created_by=u.id,
                 source_exam_id=e.id)
        for q in e.questions:
            n.questions.append(ExamQuestion(question_id=q.question_id, order_index=q.order_index, points=q.points))
        db.add(n); db.commit(); db.refresh(n)
        r = {"class_section_id": cs.id, "section_code": cs.section_code, "exam_id": n.id, "moodle": None}
        if body.create_moodle and e.exam_type == "online":
            if not cs.moodle_course_id:
                r["moodle"] = "lớp chưa gắn khóa học Moodle – tạo Quiz sau"
            elif not lms.configured():
                r["moodle"] = "chưa cấu hình Web Service Moodle"
            else:
                try:
                    check_moodle_course(db, u, cs, int(cs.moodle_course_id))
                    res = lms.create_quiz(db, n, int(cs.moodle_course_id))
                    n.moodle_quiz_id = res["quizid"]; n.status = "Published"; db.commit()
                    r["moodle"] = f"đã tạo Quiz {res['quizid']}"
                except (lms.MoodleWSError, HTTPException) as ex:
                    db.rollback()
                    r["moodle"] = f"chưa tạo được Quiz: {getattr(ex, 'detail', None) or ex}"
        out.append(r)
    return {"copies": out}
