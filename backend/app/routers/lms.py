"""Tích hợp hai chiều với Moodle qua Web Service (plugin local_clo).

- UC-02 (A2): tạo Quiz trên Moodle trực tiếp từ đề đã soạn – không cần tải XML và import thủ công.
- UC-02 bài thi giấy: tạo Offline Quiz – Moodle sinh đề in, phiếu trả lời và đáp án theo từng mã đề;
  hệ thống chỉ chuyển tệp cho giảng viên tải/in. Nhận diện phiếu quét và chấm điểm do Moodle thực hiện.
- UC-04 (A1) → UC-05: đẩy kết quả phân tích từng SV và trạng thái công bố về Moodle; SV xem kết quả tại Moodle.
"""
import io
import re
import zipfile
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..http_utils import attachment
from ..deps import check_moodle_course, check_section_access, get_exam_for, require
from ..models import User
from ..services import lms

router = APIRouter(prefix="/api", tags=["Tích hợp Moodle (Web Service)"])


class CreateQuizIn(BaseModel):
    moodle_course_id: Optional[int] = None


class CreateOfflineQuizIn(BaseModel):
    moodle_course_id: Optional[int] = None
    numgroups: int = Field(2, ge=1, le=6, description="Số mã đề (nhóm A, B, C…)")
    shuffle_questions: bool = True
    shuffle_answers: bool = True
    file_format: Literal["pdf", "docx"] = "pdf"
    intro: str = Field("", max_length=2000, description="Lời dặn in ở đầu đề")


class MoodleCourseIn(BaseModel):
    moodle_course_id: int


@router.patch("/class-sections/{cs_id}/moodle-course")
def set_moodle_course(cs_id: int, body: MoodleCourseIn, u: User = Depends(require("admin", "lecturer")),
                      db: Session = Depends(get_db)):
    cs = check_section_access(db, u, cs_id)
    cs_old, cs.moodle_course_id = cs.moodle_course_id, None
    if cs_old and cs_old != body.moodle_course_id and db.execute(
            text("SELECT 1 FROM exams WHERE class_section_id=:c AND (moodle_quiz_id IS NOT NULL OR moodle_offlinequiz_id IS NOT NULL)"),
            {"c": cs.id}).scalar():
        db.rollback()
        raise HTTPException(409, "Lớp HP đã có bài KT gắn hoạt động Moodle – không đổi được khóa học Moodle")
    check_moodle_course(db, u, cs, body.moodle_course_id)
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
    check_moodle_course(db, u, cs, course_id)
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


# ------------------------------------------------------------------ bài thi giấy (Offline Quiz)
KIND_VI = {"question": "de_thi", "answer": "phieu_tra_loi", "correction": "dap_an"}


def _oq_view(exam_id: int, oq: dict) -> dict:
    """Ẩn URL/token Moodle: giao diện tải tệp qua hệ thống (proxy)."""
    for g in oq["groups"]:
        for f in g["files"]:
            f["download"] = f"/api/exams/{exam_id}/moodle/offlinequiz/files/{f['filename']}"
            f.pop("url", None)
    oq["zip"] = f"/api/exams/{exam_id}/moodle/offlinequiz/files.zip"
    return oq


@router.post("/exams/{exam_id}/moodle/create-offlinequiz")
def create_offlinequiz(exam_id: int, body: CreateOfflineQuizIn, u: User = Depends(require("admin", "lecturer")),
                       db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    if e.exam_type != "paper":
        raise HTTPException(422, "Chỉ bài thi giấy mới tạo Offline Quiz")
    if not e.questions:
        raise HTTPException(422, "Vui lòng chọn ít nhất 1 câu hỏi")
    if e.moodle_offlinequiz_id:
        raise HTTPException(409, f"Bài KT đã được liên kết với Offline Quiz {e.moodle_offlinequiz_id}")
    cs = e.class_section
    course_id = body.moodle_course_id or cs.moodle_course_id
    if not course_id:
        raise HTTPException(422, "Hãy nhập mã khóa học Moodle (id) của lớp học phần")
    check_moodle_course(db, u, cs, course_id)
    try:
        res = lms.create_offlinequiz(e, course_id, body.numgroups, body.shuffle_questions, body.shuffle_answers,
                                     body.file_format == "docx", body.intro)
    except lms.MoodleWSError as ex:
        raise HTTPException(502, str(ex))
    other = db.execute(text("SELECT id FROM exams WHERE moodle_offlinequiz_id=:q AND id<>:e"),
                       {"q": res["offlinequizid"], "e": e.id}).scalar()
    if other:
        raise HTTPException(409, f"Offline Quiz {res['offlinequizid']} đã được gắn với bài KT #{other}")
    cs.moodle_course_id = course_id
    e.moodle_offlinequiz_id = res["offlinequizid"]
    if e.status == "Draft":
        e.status = "Published"
    db.commit()
    return _oq_view(e.id, res)


def _paper_exam(db, u, exam_id):
    e = get_exam_for(db, u, exam_id)
    if e.exam_type != "paper" or not e.moodle_offlinequiz_id:
        raise HTTPException(404, "Bài KT chưa có Offline Quiz trên Moodle")
    return e


@router.get("/exams/{exam_id}/moodle/offlinequiz")
def offlinequiz_status(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = _paper_exam(db, u, exam_id)
    try:
        return _oq_view(e.id, lms.get_offlinequiz(e))
    except lms.MoodleWSError as ex:
        raise HTTPException(502, str(ex))


@router.post("/exams/{exam_id}/moodle/process-scans")
def process_scans(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = _paper_exam(db, u, exam_id)
    try:
        return _oq_view(e.id, lms.process_scans(e))
    except lms.MoodleWSError as ex:
        raise HTTPException(502, str(ex))


def _oq_files(e):
    try:
        oq = lms.get_offlinequiz(e)
    except lms.MoodleWSError as ex:
        raise HTTPException(502, str(ex))
    return {f["filename"]: (g["letter"], f) for g in oq["groups"] for f in g["files"]}


@router.get("/exams/{exam_id}/moodle/offlinequiz/files/{filename}")
def offlinequiz_file(exam_id: int, filename: str, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = _paper_exam(db, u, exam_id)
    files = _oq_files(e)
    if filename not in files:
        raise HTTPException(404, "Không có tệp này trong Offline Quiz của bài KT")
    letter, f = files[filename]
    try:
        data, ctype = lms.download(f["url"])
    except lms.MoodleWSError as ex:
        raise HTTPException(502, str(ex))
    ext = filename.rsplit(".", 1)[-1]
    name = f"{KIND_VI.get(f['kind'], f['kind'])}_ma_de_{letter}_bai_{e.id}.{ext}"
    return Response(data, media_type=ctype, headers=attachment(f"{name}"))


@router.get("/exams/{exam_id}/moodle/offlinequiz/files.zip")
def offlinequiz_zip(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = _paper_exam(db, u, exam_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for filename, (letter, f) in _oq_files(e).items():
            try:
                data, _ = lms.download(f["url"])
            except lms.MoodleWSError as ex:
                raise HTTPException(502, str(ex))
            z.writestr(f"ma_de_{letter}/{KIND_VI.get(f['kind'], f['kind'])}_{letter}.{filename.rsplit('.', 1)[-1]}", data)
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", e.class_section.section_code)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers=attachment(f"de_thi_giay_{safe}_bai_{e.id}.zip"))


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
