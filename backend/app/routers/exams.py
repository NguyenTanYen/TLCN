"""UC-02: Khởi tạo đề thi – xuất Moodle XML / sinh mã đề giấy; liên kết Quiz; công bố kết quả."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import check_section_access, get_exam_for, require
from ..models import Exam, ExamQuestion, Question, User
from ..schemas import ExamIn, LinkQuizIn, PublishIn, VersionsIn
from ..services import lms, paper, xml_export

router = APIRouter(prefix="/api", tags=["UC-02 Đề thi"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def exam_dict(db: Session, e: Exam) -> dict:
    cs = e.class_section
    return {"id": e.id, "exam_title": e.exam_title, "assessment_type": e.assessment_type, "exam_type": e.exam_type,
            "exam_date": e.exam_date, "duration_minutes": e.duration_minutes, "max_score": float(e.max_score),
            "moodle_quiz_id": e.moodle_quiz_id, "status": e.status, "publish_flag": e.publish_flag,
            "last_synced_at": e.last_synced_at, "class_section_id": e.class_section_id, "section_code": cs.section_code,
            "moodle_course_id": cs.moodle_course_id,
            "course_id": cs.course_id, "course_code": cs.course.course_code, "course_name": cs.course.course_name,
            "semester": cs.semester.name,
            "questions": [{"question_id": q.question_id, "order_index": q.order_index, "points": float(q.points),
                           "content": q.question.content, "is_cancelled": q.question.is_cancelled,
                           "clos": ", ".join(c.clo.clo_code for c in q.question.clo_links)} for q in e.questions],
            "versions": [{"id": v.id, "version_code": v.version_code} for v in e.versions],
            "n_attempts": db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e AND status='finished'"), {"e": e.id}).scalar(),
            "n_absent": db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e AND status='absent'"), {"e": e.id}).scalar()}


@router.get("/class-sections/{cs_id}/exams")
def list_exams(cs_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    check_section_access(db, u, cs_id)
    return [exam_dict(db, e) for e in db.query(Exam).filter_by(class_section_id=cs_id).order_by(Exam.id).all()]


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
        raise HTTPException(422, "Chỉ bài KT online mới xuất Moodle XML")
    xml = xml_export.exam_to_moodle_xml(e)
    if e.status == "Draft":
        e.status = "Published"; db.commit()
    return Response(xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="exam_{exam_id}_moodle.xml"'})


@router.patch("/exams/{exam_id}/link-quiz")
def link_quiz(exam_id: int, body: LinkQuizIn, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    other = db.execute(text("SELECT id FROM exams WHERE moodle_quiz_id=:q AND id<>:e"), {"q": body.moodle_quiz_id, "e": exam_id}).scalar()
    if other:
        raise HTTPException(409, f"Quiz {body.moodle_quiz_id} đã được gắn với bài KT #{other}")
    e.moodle_quiz_id = body.moodle_quiz_id
    db.commit()
    return {"id": exam_id, "moodle_quiz_id": body.moodle_quiz_id}


@router.post("/exams/{exam_id}/versions")
def make_versions(exam_id: int, body: VersionsIn, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    if e.exam_type != "paper":
        raise HTTPException(422, "Chỉ bài thi giấy mới sinh mã đề")
    try:
        vs = paper.generate_versions(db, e, [str(body.start_code + i) for i in range(body.count)], body.seed)
    except ValueError as ex:
        raise HTTPException(409, str(ex))
    if e.status == "Draft":
        e.status = "Published"
    db.commit()
    return [{"id": v.id, "version_code": v.version_code} for v in vs]


@router.get("/exams/{exam_id}/versions/{version_id}/paper.docx")
def paper_docx(exam_id: int, version_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    v = next((v for v in e.versions if v.id == version_id), None)
    if not v:
        raise HTTPException(404, "Không tìm thấy mã đề")
    return Response(paper.exam_paper_docx(db, e, v), media_type=DOCX,
                    headers={"Content-Disposition": f'attachment; filename="de_{e.id}_ma_{v.version_code}.docx"'})


@router.get("/exams/{exam_id}/answer-key.xlsx")
def answer_key(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    return Response(paper.answer_key_xlsx(db, e), media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="dap_an_de_{e.id}.xlsx"'})


@router.patch("/exams/{exam_id}/publish")
def publish(exam_id: int, body: PublishIn, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    if body.publish and e.status != "Analyzed":
        raise HTTPException(409, "Chỉ công bố được bài KT đã phân tích")
    e.publish_flag = body.publish
    db.commit()
    out = {"id": exam_id, "publish_flag": e.publish_flag}
    # Công bố / thu hồi được đồng bộ ngay sang Moodle – nơi SV xem kết quả (UC-05)
    if lms.configured() and e.class_section.moodle_course_id and e.status == "Analyzed":
        try:
            out["moodle"] = lms.push_results(db, e)
        except lms.MoodleWSError as ex:
            out["moodle_error"] = str(ex)
    return out
