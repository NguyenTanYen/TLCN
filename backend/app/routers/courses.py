"""UC-12: Khai báo học phần – môn học, đề cương (chương), CLO và ánh xạ CLO–PLO, lớp học phần.

Để đưa một học phần mới vào hệ thống: (1) Bộ môn tạo môn học (nếu chưa có) và lớp học phần, gán GV phụ trách;
(2) GV/Bộ môn khai báo các chương của đề cương; (3) khai báo CLO, mức Bloom mục tiêu và mức đóng góp cho PLO (I/R/M);
(4) lập kế hoạch đánh giá CLO (BM6a – trang Kết quả CĐR); sau đó nhập câu hỏi và gán CLO (UC-01/UC-09), ra đề (UC-02).
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import check_course_access, check_section_access, require
from ..models import CLO, CLOPLOMapping, ClassSection, Course, CourseOutline, PLO, User

router = APIRouter(prefix="/api", tags=["UC-12 Học phần, chương, CLO, lớp học phần"])


class CourseIn(BaseModel):
    course_code: str = Field(min_length=2, max_length=20)
    course_name: str = Field(min_length=2, max_length=255)
    credits: int = Field(ge=1, le=20)
    clo_target_pct: float = Field(default=75, ge=0, le=100)


class CourseUpd(BaseModel):
    course_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    credits: Optional[int] = Field(default=None, ge=1, le=20)
    clo_target_pct: Optional[float] = Field(default=None, ge=0, le=100)


class OutlineIn(BaseModel):
    chapter_number: int = Field(ge=1, le=99)
    chapter_name: str = Field(min_length=1, max_length=255)


class PLOMapIn(BaseModel):
    plo_id: int
    level: Literal["I", "R", "M"] = "R"


class CLOUpd(BaseModel):
    clo_code: str = Field(min_length=1, max_length=10)
    description: str = Field(min_length=3)
    bloom_level_id: Optional[int] = Field(default=None, ge=1, le=6)
    plos: list[PLOMapIn] = []


class SectionIn(BaseModel):
    course_id: int
    semester_id: int
    lecturer_id: int
    section_code: str = Field(min_length=2, max_length=30)


def _course(db: Session, cid: int) -> Course:
    c = db.get(Course, cid)
    if not c:
        raise HTTPException(404, "Không tìm thấy môn học")
    return c


def _plos(db: Session, maps: list[PLOMapIn]):
    seen = set()
    for m in maps:
        if m.plo_id in seen:
            raise HTTPException(422, "Mỗi PLO chỉ được ánh xạ một lần")
        seen.add(m.plo_id)
        if not db.get(PLO, m.plo_id):
            raise HTTPException(422, f"PLO {m.plo_id} không tồn tại")


# ------------------------------------------------------------------ môn học
@router.post("/courses", status_code=201)
def create_course(body: CourseIn, db: Session = Depends(get_db), _=Depends(require("admin"))):
    if db.query(Course).filter_by(course_code=body.course_code.strip()).first():
        raise HTTPException(409, f"Đã có môn học mã {body.course_code}")
    c = Course(course_code=body.course_code.strip(), course_name=body.course_name.strip(), credits=body.credits,
               clo_target_pct=body.clo_target_pct)
    db.add(c); db.flush()
    db.execute(text("INSERT IGNORE INTO program_courses (program_id, course_id) SELECT id, :c FROM programs"), {"c": c.id})
    db.commit()
    return {"id": c.id}


@router.put("/courses/{cid}")
def update_course(cid: int, body: CourseUpd, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    c = _course(db, cid)
    check_course_access(db, u, cid)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    return {"ok": True}


@router.get("/courses/{cid}/setup")
def course_setup(cid: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    """Tình trạng khai báo của học phần: những bước đã xong / còn thiếu trước khi ra đề và đo CĐR."""
    _course(db, cid)
    check_course_access(db, u, cid)
    q = lambda sql: db.execute(text(sql), {"c": cid}).scalar()  # noqa: E731
    n_ch = q("SELECT COUNT(*) FROM course_outlines WHERE course_id=:c")
    n_clo = q("SELECT COUNT(*) FROM clos WHERE course_id=:c")
    n_clo_noplo = q("SELECT COUNT(*) FROM clos c WHERE c.course_id=:c AND NOT EXISTS (SELECT 1 FROM clo_plo_mapping m WHERE m.clo_id=c.id)")
    n_cs = q("SELECT COUNT(*) FROM class_sections WHERE course_id=:c")
    n_plan = q("""SELECT COUNT(DISTINCT p.clo_id) FROM clo_assessment_plans p JOIN clos c ON c.id=p.clo_id WHERE c.course_id=:c""")
    n_q = q("SELECT COUNT(*) FROM question_bank WHERE course_id=:c AND is_cancelled=0")
    n_tag = q("""SELECT COUNT(*) FROM question_bank q WHERE q.course_id=:c AND q.is_cancelled=0 AND q.bloom_level_id IS NOT NULL
                 AND EXISTS (SELECT 1 FROM question_clo_mapping m WHERE m.question_id=q.id)""")
    n_clo_noq = q("""SELECT COUNT(*) FROM clos c WHERE c.course_id=:c AND NOT EXISTS (SELECT 1 FROM question_clo_mapping m
                     JOIN question_bank b ON b.id=m.question_id AND b.is_cancelled=0 WHERE m.clo_id=c.id)""")
    steps = [
        {"key": "section", "label": "Lớp học phần và GV phụ trách", "ok": n_cs > 0, "detail": f"{n_cs} lớp HP"},
        {"key": "chapters", "label": "Đề cương: các chương", "ok": n_ch > 0, "detail": f"{n_ch} chương"},
        {"key": "clos", "label": "CLO và ánh xạ PLO (I/R/M)", "ok": n_clo > 0 and n_clo_noplo == 0,
         "detail": f"{n_clo} CLO" + (f", {n_clo_noplo} CLO chưa ánh xạ PLO" if n_clo_noplo else "")},
        {"key": "plans", "label": "Kế hoạch đánh giá CLO (BM6a)", "ok": n_clo > 0 and n_plan >= n_clo,
         "detail": f"{n_plan}/{n_clo} CLO có kế hoạch (thiếu thì dùng ngưỡng 60%, chỉ tiêu của môn)"},
        {"key": "questions", "label": "Ngân hàng câu hỏi đã gán CLO/Bloom", "ok": n_tag > 0 and n_clo_noq == 0,
         "detail": f"{n_tag}/{n_q} câu đã gán" + (f"; {n_clo_noq} CLO chưa có câu hỏi" if n_clo_noq else "")},
    ]
    return {"course_id": cid, "steps": steps, "ready": all(s["ok"] for s in steps if s["key"] != "plans")}


# ------------------------------------------------------------------ đề cương (chương)
@router.post("/courses/{cid}/outlines", status_code=201)
def create_outline(cid: int, body: OutlineIn, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    _course(db, cid)
    check_course_access(db, u, cid)
    if db.query(CourseOutline).filter_by(course_id=cid, chapter_number=body.chapter_number).first():
        raise HTTPException(409, f"Môn học đã có chương {body.chapter_number}")
    o = CourseOutline(course_id=cid, chapter_number=body.chapter_number, chapter_name=body.chapter_name.strip())
    db.add(o); db.commit()
    return {"id": o.id}


@router.put("/outlines/{oid}")
def update_outline(oid: int, body: OutlineIn, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    o = db.get(CourseOutline, oid)
    if not o:
        raise HTTPException(404, "Không tìm thấy chương")
    check_course_access(db, u, o.course_id)
    dup = db.query(CourseOutline).filter(CourseOutline.course_id == o.course_id, CourseOutline.chapter_number == body.chapter_number,
                                         CourseOutline.id != oid).first()
    if dup:
        raise HTTPException(409, f"Môn học đã có chương {body.chapter_number}")
    o.chapter_number, o.chapter_name = body.chapter_number, body.chapter_name.strip()
    db.commit()
    return {"ok": True}


@router.delete("/outlines/{oid}")
def delete_outline(oid: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    o = db.get(CourseOutline, oid)
    if not o:
        raise HTTPException(404, "Không tìm thấy chương")
    check_course_access(db, u, o.course_id)
    n = db.execute(text("SELECT COUNT(*) FROM question_bank WHERE outline_id=:o"), {"o": oid}).scalar()
    if n:
        raise HTTPException(409, f"Chương đang được {n} câu hỏi sử dụng – chuyển các câu sang chương khác trước khi xóa")
    db.delete(o); db.commit()
    return {"deleted": oid}


# ------------------------------------------------------------------ CLO
@router.put("/clos/{clo_id}")
def update_clo(clo_id: int, body: CLOUpd, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    clo = db.get(CLO, clo_id)
    if not clo:
        raise HTTPException(404, "Không tìm thấy CLO")
    check_course_access(db, u, clo.course_id)
    if db.query(CLO).filter(CLO.course_id == clo.course_id, CLO.clo_code == body.clo_code.strip(), CLO.id != clo_id).first():
        raise HTTPException(409, f"Môn học đã có {body.clo_code}")
    _plos(db, body.plos)
    clo.clo_code, clo.description, clo.bloom_level_id = body.clo_code.strip(), body.description.strip(), body.bloom_level_id
    db.query(CLOPLOMapping).filter_by(clo_id=clo_id).delete()
    for m in body.plos:
        db.add(CLOPLOMapping(clo_id=clo_id, plo_id=m.plo_id, level=m.level))
    db.commit()
    return {"ok": True}


@router.delete("/clos/{clo_id}")
def delete_clo(clo_id: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    clo = db.get(CLO, clo_id)
    if not clo:
        raise HTTPException(404, "Không tìm thấy CLO")
    check_course_access(db, u, clo.course_id)
    used = db.execute(text("""SELECT (SELECT COUNT(*) FROM question_clo_mapping WHERE clo_id=:c)
                                   + (SELECT COUNT(*) FROM attempt_clo_results WHERE clo_id=:c)
                                   + (SELECT COUNT(*) FROM pi_plan_clos WHERE clo_id=:c)"""), {"c": clo_id}).scalar()
    if used:
        raise HTTPException(409, "CLO đã được gán cho câu hỏi, có kết quả đo hoặc là minh chứng của kế hoạch PI – không xóa được (có thể sửa nội dung)")
    db.delete(clo); db.commit()
    return {"deleted": clo_id}


# ------------------------------------------------------------------ lớp học phần
@router.post("/class-sections", status_code=201)
def create_section(body: SectionIn, db: Session = Depends(get_db), _=Depends(require("admin"))):
    _course(db, body.course_id)
    for t, i, msg in (("semesters", body.semester_id, "Học kỳ"), ("lecturers", body.lecturer_id, "Giảng viên")):
        if not db.execute(text(f"SELECT 1 FROM {t} WHERE id=:i"), {"i": i}).scalar():
            raise HTTPException(422, f"{msg} không tồn tại")
    if db.query(ClassSection).filter_by(semester_id=body.semester_id, section_code=body.section_code.strip()).first():
        raise HTTPException(409, f"Học kỳ này đã có lớp {body.section_code}")
    cs = ClassSection(course_id=body.course_id, semester_id=body.semester_id, lecturer_id=body.lecturer_id,
                      section_code=body.section_code.strip())
    db.add(cs); db.commit()
    return {"id": cs.id}


@router.put("/class-sections/{cs_id}")
def update_section(cs_id: int, body: SectionIn, db: Session = Depends(get_db), u: User = Depends(require("admin"))):
    cs = check_section_access(db, u, cs_id)
    has_exams = db.execute(text("SELECT COUNT(*) FROM exams WHERE class_section_id=:c"), {"c": cs_id}).scalar()
    if has_exams and (body.course_id != cs.course_id or body.semester_id != cs.semester_id):
        raise HTTPException(409, "Lớp HP đã có bài kiểm tra – không đổi được môn học hoặc học kỳ")
    if db.query(ClassSection).filter(ClassSection.semester_id == body.semester_id, ClassSection.section_code == body.section_code.strip(),
                                     ClassSection.id != cs_id).first():
        raise HTTPException(409, f"Học kỳ này đã có lớp {body.section_code}")
    cs.course_id, cs.semester_id, cs.lecturer_id, cs.section_code = body.course_id, body.semester_id, body.lecturer_id, body.section_code.strip()
    db.commit()
    return {"ok": True}


@router.delete("/class-sections/{cs_id}")
def delete_section(cs_id: int, db: Session = Depends(get_db), u: User = Depends(require("admin"))):
    check_section_access(db, u, cs_id)
    if db.execute(text("SELECT COUNT(*) FROM exams WHERE class_section_id=:c"), {"c": cs_id}).scalar():
        raise HTTPException(409, "Lớp HP đã có bài kiểm tra – không xóa được")
    db.execute(text("DELETE FROM enrollments WHERE class_section_id=:c"), {"c": cs_id})
    db.execute(text("DELETE FROM class_sections WHERE id=:c"), {"c": cs_id})
    db.commit()
    return {"deleted": cs_id}


# ------------------------------------------------------------------ khóa học Moodle → lớp học phần
class NewSemesterIn(BaseModel):
    academic_year: str = Field(pattern=r"^[0-9]{4}-[0-9]{4}$")
    term: Literal[1, 2, 3]


class MoodleImportIn(BaseModel):
    course_id: int
    semester_id: Optional[int] = None
    new_semester: Optional[NewSemesterIn] = None   # học kỳ chưa có: tạo theo ngày bắt đầu của khóa học Moodle
    section_code: str = Field(min_length=2, max_length=30)
    lecturer_id: Optional[int] = None      # chỉ Bộ môn chọn; GV luôn là chính mình


TERM_VI = {1: "HKI", 2: "HKII", 3: "HK hè"}


def _norm(s) -> str:
    import unicodedata
    return " ".join(unicodedata.normalize("NFC", str(s or "")).lower().split())


def _semester_of(ts: int) -> dict:
    """Năm học/học kỳ chứa thời điểm ts theo lịch chuẩn: HKI 05/9–20/01, HKII 10/02–30/06, hè 01/7–31/8."""
    import datetime as dt
    d = dt.date.fromtimestamp(ts)
    y0 = d.year if d.month >= 8 else d.year - 1
    term = 1 if (d.month >= 8 or d.month == 1) else 2 if d.month <= 6 else 3
    return {"academic_year": f"{y0}-{y0 + 1}", "term": term, "name": f"{TERM_VI[term]} {str(y0)[2:]}-{str(y0 + 1)[2:]}"}


def _get_or_create_semester(db: Session, s: "NewSemesterIn") -> int:
    import datetime as dt
    sid = db.execute(text("SELECT id FROM semesters WHERE academic_year=:y AND term=:t"), {"y": s.academic_year, "t": s.term}).scalar()
    if sid:
        return sid
    y0, y1 = (int(x) for x in s.academic_year.split("-"))
    if y1 != y0 + 1:
        raise HTTPException(422, "Năm học phải có dạng YYYY-(YYYY+1)")
    start, end = {1: (dt.date(y0, 9, 5), dt.date(y1, 1, 20)), 2: (dt.date(y1, 2, 10), dt.date(y1, 6, 30)),
                  3: (dt.date(y1, 7, 1), dt.date(y1, 8, 31))}[s.term]
    return db.execute(text("INSERT INTO semesters (academic_year, term, name, start_date, end_date) VALUES (:y, :t, :n, :s, :e)"),
                      {"y": s.academic_year, "t": s.term, "n": f"{TERM_VI[s.term]} {str(y0)[2:]}-{str(y1)[2:]}", "s": start, "e": end}).lastrowid


def _sync_roster(db: Session, cs_id: int, moodle_course_id: int) -> int:
    """Đưa SV đang ghi danh trên Moodle vào danh sách lớp HP (cùng quy tắc với thủ tục đồng bộ: khớp mdl_user.id, rồi mã SV)."""
    from ..services import moodle
    n = 0
    for r in moodle.course_roster(db, moodle_course_id):
        sid = db.execute(text("SELECT id FROM students WHERE moodle_user_id=:m"), {"m": r["mdl_user_id"]}).scalar()
        if not sid:
            row = db.execute(text("SELECT id, moodle_user_id FROM students WHERE student_code=:c"), {"c": r["student_code"]}).first()
            if row:
                sid = row[0]
                if row[1] is None:
                    db.execute(text("UPDATE students SET moodle_user_id=:m WHERE id=:i"), {"m": r["mdl_user_id"], "i": sid})
            else:
                sid = db.execute(text("INSERT INTO students (student_code, full_name, moodle_user_id) VALUES (:c, :n, :m)"),
                                 {"c": r["student_code"][:100], "n": (r["full_name"] or r["student_code"])[:100], "m": r["mdl_user_id"]}).lastrowid
        n += db.execute(text("INSERT IGNORE INTO enrollments (class_section_id, student_id) VALUES (:cs, :s)"), {"cs": cs_id, "s": sid}).rowcount
    return n


def _need_moodle():
    from ..services import moodle
    if not moodle.moodle_available():
        raise HTTPException(502, "Lỗi kết nối LMS: không đọc được CSDL Moodle")
    return moodle


@router.get("/moodle/my-courses")
def my_moodle_courses(db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    """Khóa học trên Moodle của GV (Bộ môn: mọi khóa học) kèm lớp HP đã gắn, hoặc gợi ý môn học / học kỳ / GV để đưa vào hệ thống."""
    moodle = _need_moodle()
    rows = moodle.teacher_courses(db, None if u.role == "admin" else u.username)
    linked = {r[0]: r for r in db.execute(text("""SELECT cs.moodle_course_id, cs.id, cs.section_code, l.full_name FROM class_sections cs
                                                  JOIN lecturers l ON l.id=cs.lecturer_id WHERE cs.moodle_course_id IS NOT NULL"""))}
    courses = db.execute(text("SELECT id, course_code, course_name FROM courses")).all()
    sems = db.execute(text("SELECT id, UNIX_TIMESTAMP(start_date), UNIX_TIMESTAMP(end_date) FROM semesters ORDER BY start_date DESC")).all()
    lecs = db.execute(text("SELECT l.id, l.lecturer_code, u.username FROM lecturers l LEFT JOIN users u ON u.id=l.user_id")).all()
    out = []
    for r in rows:
        hay = " ".join(str(r[k] or "") for k in ("shortname", "idnumber", "fullname")).upper()
        sug_course = next((c[0] for c in sorted(courses, key=lambda c: -len(c[1])) if c[1].upper() in hay), None)
        if not sug_course:   # không có mã môn trong tên khóa: thử khớp đúng tên môn học
            full = _norm(r["fullname"])
            sug_course = next((c[0] for c in courses if _norm(c[2]) and (_norm(c[2]) == full or full.startswith(_norm(c[2]) + " "))), None)
        st = int(r["startdate"] or 0)
        sug_sem = next((s[0] for s in sems if st and s[1] and s[2] and s[1] - 30 * 86400 <= st <= s[2]), None)
        new_sem = None
        if not sug_sem and st > 0:
            new_sem = _semester_of(st)
            sug_sem = next((s[0] for s in db.execute(text("SELECT id FROM semesters WHERE academic_year=:y AND term=:t"),
                                                    {"y": new_sem["academic_year"], "t": new_sem["term"]})), None)
            new_sem = None if sug_sem else new_sem
        if not sug_sem and not new_sem and sems:
            sug_sem = sems[0][0]
        names = {t["username"] for t in r["teachers"]} | {t["idnumber"] for t in r["teachers"] if t["idnumber"]}
        sug_lec = next((l[0] for l in lecs if l[2] in names or l[1] in names), None)
        cs = linked.get(r["id"])
        out.append({"moodle_course_id": r["id"], "shortname": r["shortname"], "fullname": r["fullname"], "category": r["category"],
                    "visible": bool(r["visible"]), "teachers": r["teachers"], "n_students": r["n_students"],
                    "section": {"id": cs[1], "section_code": cs[2], "lecturer": cs[3]} if cs else None,
                    "suggest": {"course_id": sug_course, "semester_id": sug_sem, "new_semester": new_sem, "lecturer_id": sug_lec,
                                "section_code": (r["shortname"] or f"MOODLE_{r['id']}")[:30]}})
    return out


@router.post("/moodle/courses/{mid}/import", status_code=201)
def import_moodle_course(mid: int, body: MoodleImportIn, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    """Tạo lớp HP từ một khóa học Moodle và lấy danh sách SV đang ghi danh. GV chỉ đưa vào khóa học mình là giảng viên
    trên Moodle và chọn môn học đã có (môn học mới do Bộ môn tạo)."""
    moodle = _need_moodle()
    if not moodle.course_exists(db, mid):
        raise HTTPException(404, f"Không có khóa học Moodle id = {mid}")
    other = db.execute(text("SELECT section_code FROM class_sections WHERE moodle_course_id=:m"), {"m": mid}).scalar()
    if other:
        raise HTTPException(409, f"Khóa học Moodle {mid} đã gắn với lớp học phần {other}")
    if u.role == "admin":
        if not body.lecturer_id:
            raise HTTPException(422, "Chọn giảng viên phụ trách")
        lecturer_id = body.lecturer_id
    else:
        if not u.lecturer:
            raise HTTPException(403, "Tài khoản chưa được khai báo là giảng viên")
        if not moodle.is_course_teacher(db, u.username, mid):
            raise HTTPException(403, "Bạn không phải giảng viên của khóa học này trên Moodle")
        lecturer_id = u.lecturer.id
    _course(db, body.course_id)
    if body.semester_id is None and body.new_semester is None:
        raise HTTPException(422, "Chọn học kỳ")
    for t, i, msg in (("semesters", body.semester_id, "Học kỳ"), ("lecturers", lecturer_id, "Giảng viên")):
        if i is not None and not db.execute(text(f"SELECT 1 FROM {t} WHERE id=:i"), {"i": i}).scalar():
            raise HTTPException(422, f"{msg} không tồn tại")
    semester_id = body.semester_id or _get_or_create_semester(db, body.new_semester)
    if db.query(ClassSection).filter_by(semester_id=semester_id, section_code=body.section_code.strip()).first():
        raise HTTPException(409, f"Học kỳ này đã có lớp {body.section_code}")
    cs = ClassSection(course_id=body.course_id, semester_id=semester_id, lecturer_id=lecturer_id,
                      section_code=body.section_code.strip(), moodle_course_id=mid)
    db.add(cs); db.flush()
    n = _sync_roster(db, cs.id, mid)
    db.commit()
    return {"id": cs.id, "n_students": n}


@router.post("/class-sections/{cs_id}/moodle-roster")
def refresh_roster(cs_id: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    """Cập nhật danh sách SV của lớp HP theo ghi danh hiện tại của khóa học Moodle đã gắn (chỉ thêm, không xóa)."""
    cs = check_section_access(db, u, cs_id)
    if not cs.moodle_course_id:
        raise HTTPException(422, "Lớp học phần chưa gắn khóa học Moodle")
    _need_moodle()
    n = _sync_roster(db, cs.id, int(cs.moodle_course_id))
    db.commit()
    total = db.execute(text("SELECT COUNT(*) FROM enrollments WHERE class_section_id=:c AND status='active'"), {"c": cs_id}).scalar()
    return {"added": n, "n_students": total}
