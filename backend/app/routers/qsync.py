"""Đồng bộ ngân hàng câu hỏi hai chiều với Moodle (xem services/qsync.py)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import check_course_access, require
from ..models import User
from ..services import lms, moodle, qsync

router = APIRouter(prefix="/api", tags=["Đồng bộ ngân hàng câu hỏi với Moodle"])


class SyncIn(BaseModel):
    moodle_course_id: int
    push: list[int] = []          # question_bank.id cần đẩy lên Moodle
    pull: list[int] = []          # question_bank.id cần cập nhật từ bản mới trên Moodle
    import_new: list[int] = []    # mdl_question.id soạn trên Moodle cần nhập về


def _targets(db: Session, u: User, course_id: int) -> list[dict]:
    lid = u.lecturer.id if u.role == "lecturer" and u.lecturer else (0 if u.role == "lecturer" else None)
    return [dict(r) for r in db.execute(text("""SELECT cs.moodle_course_id, GROUP_CONCAT(cs.section_code ORDER BY cs.section_code SEPARATOR ', ') AS sections
                                                FROM class_sections cs WHERE cs.course_id=:c AND cs.moodle_course_id IS NOT NULL
                                                  AND (:l IS NULL OR cs.lecturer_id=:l)
                                                GROUP BY cs.moodle_course_id ORDER BY cs.moodle_course_id DESC"""),
                                       {"c": course_id, "l": lid}).mappings()]


def _check(db: Session, u: User, course_id: int, moodle_course_id: int) -> None:
    check_course_access(db, u, course_id)
    if not moodle.moodle_available():
        raise HTTPException(502, "Lỗi kết nối LMS: không đọc được CSDL Moodle")
    if moodle_course_id not in {t["moodle_course_id"] for t in _targets(db, u, course_id)}:
        raise HTTPException(403, "Khóa học Moodle này không gắn với lớp học phần nào của môn mà bạn phụ trách")


@router.get("/courses/{course_id}/moodle-sync/targets")
def targets(course_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    check_course_access(db, u, course_id)
    return {"targets": _targets(db, u, course_id), "ws_configured": lms.configured(), "moodle_available": moodle.moodle_available()}


@router.get("/courses/{course_id}/moodle-sync")
def compare(course_id: int, moodle_course_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    _check(db, u, course_id, moodle_course_id)
    return qsync.compare(db, course_id, moodle_course_id)


@router.post("/courses/{course_id}/moodle-sync")
def apply(course_id: int, body: SyncIn, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    _check(db, u, course_id, body.moodle_course_id)
    if not lms.configured():
        raise HTTPException(502, "Chưa cấu hình Web Service Moodle (MOODLE_URL, MOODLE_WS_TOKEN)")
    if set(body.push) & set(body.pull):
        raise HTTPException(422, "Một câu không thể vừa đẩy lên vừa kéo về")
    try:
        out = {"pushed": qsync.push(db, course_id, body.moodle_course_id, body.push, lms.call) if body.push else []}
        out.update(qsync.pull(db, course_id, body.moodle_course_id, body.pull, body.import_new, u.id, lms.call)
                   if body.pull or body.import_new else {"updated": [], "created": [], "tagged": 0})
    except ValueError as ex:
        db.rollback(); raise HTTPException(422, str(ex))
    except lms.MoodleWSError as ex:
        db.rollback(); raise HTTPException(502, str(ex))
    out["after"] = qsync.compare(db, course_id, body.moodle_course_id)["summary"]
    return out
