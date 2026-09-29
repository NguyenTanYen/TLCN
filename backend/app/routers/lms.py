"""Tích hợp hai chiều với Moodle qua Web Service (plugin local_clo).

- UC-02 (A2): tạo Quiz trên Moodle trực tiếp từ đề đã soạn – không cần tải XML và import thủ công.
- UC-04 (A1) → UC-05: đẩy kết quả phân tích từng SV và trạng thái công bố về Moodle; SV xem kết quả tại Moodle.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import check_section_access, get_exam_for, require
from ..models import User
from ..services import lms

router = APIRouter(prefix="/api", tags=["Tích hợp Moodle (Web Service)"])


class CreateQuizIn(BaseModel):
    moodle_course_id: Optional[int] = None


class MoodleCourseIn(BaseModel):
    moodle_course_id: int


@router.patch("/class-sections/{cs_id}/moodle-course")
def set_moodle_course(cs_id: int, body: MoodleCourseIn, u: User = Depends(require("admin", "lecturer")),
                      db: Session = Depends(get_db)):
    cs = check_section_access(db, u, cs_id)
    cs.moodle_course_id = body.moodle_course_id
    db.commit()
    return {"id": cs.id, "moodle_course_id": cs.moodle_course_id}


@router.post("/exams/{exam_id}/moodle/create-quiz")
def create_quiz(exam_id: int, body: CreateQuizIn, u: User = Depends(require("admin", "lecturer")),
                db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    if e.exam_type != "online":
        raise HTTPException(422, "Chỉ bài KT trực tuyến mới tạo Quiz trên Moodle")
    if not e.questions:
        raise HTTPException(422, "Vui lòng chọn ít nhất 1 câu hỏi")
    if e.moodle_quiz_id:
        raise HTTPException(409, f"Bài KT đã được liên kết với Quiz {e.moodle_quiz_id}")
    cs = e.class_section
    course_id = body.moodle_course_id or cs.moodle_course_id
    if not course_id:
        raise HTTPException(422, "Hãy nhập mã khóa học Moodle (id) của lớp học phần")
    try:
        res = lms.create_quiz(db, e, course_id)
    except lms.MoodleWSError as ex:
        raise HTTPException(502, str(ex))
    other = db.execute(text("SELECT id FROM exams WHERE moodle_quiz_id=:q AND id<>:e"), {"q": res["quizid"], "e": e.id}).scalar()
    if other:
        raise HTTPException(409, f"Quiz {res['quizid']} đã được gắn với bài KT #{other}")
    cs.moodle_course_id = course_id
    e.moodle_quiz_id = res["quizid"]
    if e.status == "Draft":
        e.status = "Published"
    db.commit()
    return {**res, "quiz_url": f"{settings.moodle_url.rstrip('/')}/mod/quiz/view.php?id={res['cmid']}"}


@router.get("/exams/{exam_id}/moodle/results-preview")
def results_preview(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    get_exam_for(db, u, exam_id)
    return lms.student_results(db, exam_id)


@router.post("/exams/{exam_id}/moodle/push-results")
def push_results(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    if e.status != "Analyzed":
        raise HTTPException(409, "Chưa có dữ liệu phân tích – hãy đồng bộ và phân tích trước")
    try:
        return lms.push_results(db, e)
    except lms.MoodleWSError as ex:
        raise HTTPException(502, str(ex))


@router.get("/system/lms-status")
def lms_status(_=Depends(require("admin", "lecturer"))):
    out = {"moodle_url": settings.moodle_url, "ws_configured": lms.configured(),
           "sso_configured": len(settings.moodle_sso_secret) >= 32, "ws_ok": False, "site": None, "error": None}
    if out["ws_configured"]:
        try:
            info = lms.site_info()
            out["ws_ok"] = True
            out["site"] = {"sitename": info.get("sitename"), "username": info.get("username"), "release": info.get("release"),
                           "functions": sorted(f["name"] for f in info.get("functions", []))}
        except lms.MoodleWSError as ex:
            out["error"] = str(ex)
    return out
