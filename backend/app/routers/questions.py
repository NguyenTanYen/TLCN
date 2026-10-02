"""UC-01: Quản lý câu hỏi & gán CLO."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import check_course_access, require
from ..models import CLO, Question, QuestionCLO, QuestionOption, User
from ..schemas import CancelIn, QuestionIn

router = APIRouter(prefix="/api/questions", tags=["UC-01 Ngân hàng câu hỏi"])
LABELS = "ABCDEFGHIJ"


def to_dict(q: Question, stats: dict | None = None) -> dict:
    return {"id": q.id, "course_id": q.course_id, "outline_id": q.outline_id, "bloom_level_id": q.bloom_level_id,
            "bloom": q.bloom.name_vi if q.bloom else None, "content": q.content, "is_cancelled": q.is_cancelled,
            "cancel_reason": q.cancel_reason, "moodle_question_id": q.moodle_question_id,
            "chapter": f"Chương {q.outline.chapter_number}" if q.outline else None,
            "options": [{"id": o.id, "label": o.opt_label, "content": o.content, "is_correct": o.is_correct} for o in q.options],
            "clos": [{"clo_id": c.clo_id, "clo_code": c.clo.clo_code, "weight": float(c.weight)} for c in q.clo_links],
            "tagged": bool(q.clo_links) and q.bloom_level_id is not None,
            "usage": stats or {}}


def _get_q(db: Session, u: User, qid: int) -> Question:
    q = db.get(Question, qid)
    if not q:
        raise HTTPException(404, "Không tìm thấy câu hỏi")
    check_course_access(db, u, q.course_id)
    return q


def _validate(db: Session, body: QuestionIn):
    for c in body.clos:
        clo = db.get(CLO, c.clo_id)
        if not clo or clo.course_id != body.course_id:
            raise HTTPException(422, f"CLO {c.clo_id} không thuộc môn học")
    if body.outline_id:
        ok = db.execute(text("SELECT 1 FROM course_outlines WHERE id=:o AND course_id=:c"),
                        {"o": body.outline_id, "c": body.course_id}).scalar()
        if not ok:
            raise HTTPException(422, "Chương không thuộc môn học")


def _usage(db: Session, qid: int) -> dict:
    r = db.execute(text("""SELECT (SELECT COUNT(*) FROM exam_questions WHERE question_id=:q) AS n_exams,
                                  (SELECT COUNT(*) FROM item_level_results WHERE question_id=:q) AS n_results,
                                  (SELECT ROUND(AVG(p_value),3) FROM item_statistics WHERE question_id=:q) AS avg_p,
                                  (SELECT ROUND(AVG(di_value),3) FROM item_statistics WHERE question_id=:q) AS avg_di"""),
                   {"q": qid}).mappings().one()
    return {k: (float(v) if v is not None and k.startswith("avg") else v) for k, v in r.items()}


@router.get("")
def list_questions(course_id: int, clo_id: int | None = None, bloom_level_id: int | None = None, outline_id: int | None = None,
                   include_cancelled: bool = False, untagged: bool = False, q: str | None = None, db: Session = Depends(get_db),
                   u: User = Depends(require("admin", "lecturer"))):
    check_course_access(db, u, course_id)
    query = db.query(Question).filter(Question.course_id == course_id)
    if not include_cancelled:
        query = query.filter(Question.is_cancelled.is_(False))
    if bloom_level_id:
        query = query.filter(Question.bloom_level_id == bloom_level_id)
    if outline_id:
        query = query.filter(Question.outline_id == outline_id)
    if clo_id:
        query = query.filter(Question.clo_links.any(QuestionCLO.clo_id == clo_id))
    if q:
        query = query.filter(Question.content.like(f"%{q}%"))
    if untagged:   # câu nhập hàng loạt chưa gán đủ Bloom + CLO
        query = query.filter((Question.bloom_level_id.is_(None)) | ~Question.clo_links.any())
    return [to_dict(x, _usage(db, x.id)) for x in query.order_by(Question.id).all()]


@router.get("/{qid}")
def get_question(qid: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    q = _get_q(db, u, qid)
    return to_dict(q, _usage(db, qid))


@router.post("", status_code=201)
def create_question(body: QuestionIn, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    check_course_access(db, u, body.course_id)
    _validate(db, body)
    q = Question(course_id=body.course_id, outline_id=body.outline_id, bloom_level_id=body.bloom_level_id,
                 content=body.content, created_by=u.id)
    for i, o in enumerate(body.options):
        q.options.append(QuestionOption(position=i + 1, opt_label=LABELS[i], content=o.content, is_correct=o.is_correct))
    for c in body.clos:
        q.clo_links.append(QuestionCLO(clo_id=c.clo_id, weight=c.weight))
    db.add(q); db.commit(); db.refresh(q)
    return to_dict(q)


@router.put("/{qid}")
def update_question(qid: int, body: QuestionIn, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    q = _get_q(db, u, qid)
    if body.course_id != q.course_id:
        raise HTTPException(422, "Không được chuyển câu hỏi sang môn học khác")
    if _usage(db, qid)["n_results"]:
        raise HTTPException(409, "Câu hỏi đã có kết quả thi – không được sửa nội dung/đáp án; hãy Hủy và tạo câu mới")
    same_body = q.content == body.content and [(o.content, bool(o.is_correct)) for o in q.options] == \
        [(o.content, bool(o.is_correct)) for o in body.options]
    on_moodle = db.execute(text("""SELECT 1 FROM exam_questions eq JOIN exams e ON e.id=eq.exam_id WHERE eq.question_id=:q
                                   AND (e.moodle_quiz_id IS NOT NULL OR e.moodle_offlinequiz_id IS NOT NULL) LIMIT 1"""),
                           {"q": qid}).scalar()
    if on_moodle and not same_body:
        raise HTTPException(409, "Câu hỏi đã nằm trong đề trên Moodle – chỉ được sửa CLO/Bloom/chương; "
                                 "muốn sửa nội dung/đáp án hãy Hủy và tạo câu mới")
    _validate(db, body)
    q.outline_id, q.bloom_level_id, q.content = body.outline_id, body.bloom_level_id, body.content
    q.options.clear(); q.clo_links.clear(); db.flush()
    for i, o in enumerate(body.options):
        q.options.append(QuestionOption(position=i + 1, opt_label=LABELS[i], content=o.content, is_correct=o.is_correct))
    for c in body.clos:
        q.clo_links.append(QuestionCLO(clo_id=c.clo_id, weight=c.weight))
    db.commit(); db.refresh(q)
    return to_dict(q)


@router.patch("/{qid}/cancel")
def cancel_question(qid: int, body: CancelIn, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    q = _get_q(db, u, qid)
    q.is_cancelled, q.cancel_reason = True, body.reason
    db.commit()
    return {"id": qid, "is_cancelled": True}


@router.delete("/{qid}")
def delete_question(qid: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    q = _get_q(db, u, qid)
    if _usage(db, qid)["n_exams"]:
        raise HTTPException(409, "Câu hỏi đã được dùng trong đề – chỉ được Hủy, không được xóa")
    db.delete(q); db.commit()
    return {"deleted": qid}
