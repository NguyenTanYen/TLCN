"""Quản lý theo chương trình đào tạo: CTĐT → học phần (học kỳ, khối kiến thức, ma trận PI) → đề cương chi tiết.

Bộ môn (admin) khai báo/chỉnh CTĐT, gán học phần vào CTĐT và ma trận học phần – PI; giảng viên chỉ xem.
Đề cương chi tiết của một học phần tổng hợp: thông tin chung, mô tả, CTĐT chứa học phần (học kỳ, khối, tự chọn),
học phần tiên quyết, CLO (Bloom, đóng góp PLO), PI mà học phần đáp ứng, các chương, kế hoạch đánh giá CLO, các lớp HP.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user, require
from ..models import Course, Program, User
from . import syllabi

router = APIRouter(prefix="/api", tags=["Chương trình đào tạo & đề cương học phần"])


def rows(db: Session, sql: str, **p) -> list[dict]:
    return [dict(r) for r in db.execute(text(sql), p).mappings()]


class ProgramIn(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=255)
    name_en: Optional[str] = Field(default=None, max_length=255)
    faculty: Optional[str] = Field(default=None, max_length=150)
    department: Optional[str] = Field(default=None, max_length=150)
    major_code: Optional[str] = Field(default=None, max_length=20)
    cohort_year: Optional[int] = Field(default=None, ge=2000, le=2100)
    total_credits: Optional[int] = Field(default=None, ge=1, le=400)
    decision_no: Optional[str] = Field(default=None, max_length=100)
    objective: Optional[str] = None
    target_pct: float = Field(default=75, ge=0, le=100)


class ProgramCourseIn(BaseModel):
    course_id: int
    semester_no: Optional[int] = Field(default=None, ge=1, le=12)
    knowledge_block: Optional[str] = Field(default=None, max_length=150)
    is_elective: bool = False


class PICourseIn(BaseModel):
    pi_id: int
    level: Optional[str] = Field(default=None, max_length=2, description="I, R, M hoặc trình độ 1–6; để trống = bỏ ánh xạ")


@router.get("/programs")
def programs(db: Session = Depends(get_db), _=Depends(current_user)):
    return rows(db, """SELECT p.*, (SELECT COUNT(*) FROM plos WHERE program_id=p.id) AS n_plos,
                              (SELECT COUNT(*) FROM performance_indicators pi JOIN plos pl ON pl.id=pi.plo_id WHERE pl.program_id=p.id) AS n_pis,
                              (SELECT COUNT(*) FROM program_courses WHERE program_id=p.id) AS n_courses
                       FROM programs p ORDER BY p.cohort_year IS NULL, p.cohort_year DESC, p.code""")


@router.post("/programs", status_code=201)
def create_program(body: ProgramIn, db: Session = Depends(get_db), _=Depends(require("admin"))):
    if db.query(Program).filter_by(code=body.code.strip()).first():
        raise HTTPException(409, f"Đã có CTĐT mã {body.code}")
    p = Program(**{**body.model_dump(), "code": body.code.strip(), "name": body.name.strip()})
    db.add(p); db.commit()
    return {"id": p.id}


@router.put("/programs/{pid}")
def update_program(pid: int, body: ProgramIn, db: Session = Depends(get_db), _=Depends(require("admin"))):
    p = db.get(Program, pid)
    if not p:
        raise HTTPException(404, "Không tìm thấy CTĐT")
    if db.query(Program).filter(Program.code == body.code.strip(), Program.id != pid).first():
        raise HTTPException(409, f"Đã có CTĐT mã {body.code}")
    for k, v in body.model_dump().items():
        setattr(p, k, v.strip() if isinstance(v, str) else v)
    db.commit()
    return {"ok": True}


@router.get("/programs/{pid}")
def program_detail(pid: int, db: Session = Depends(get_db), _=Depends(current_user)):
    prog = db.get(Program, pid)
    if not prog:
        raise HTTPException(404, "Không tìm thấy CTĐT")
    plos = rows(db, "SELECT * FROM plos WHERE program_id=:p ORDER BY LENGTH(plo_code), plo_code", p=pid)
    pis = rows(db, """SELECT pi.*, (SELECT GROUP_CONCAT(c.course_code ORDER BY c.course_code) FROM pi_courses pc JOIN courses c ON c.id=pc.course_id
                                     WHERE pc.pi_id=pi.id) AS courses
                      FROM performance_indicators pi JOIN plos p ON p.id=pi.plo_id WHERE p.program_id=:p
                      ORDER BY LENGTH(pi.pi_code), pi.pi_code""", p=pid)
    mplans = rows(db, "SELECT m.* FROM plo_measurement_plans m JOIN plos p ON p.id=m.plo_id WHERE p.program_id=:p", p=pid)
    for p in plos:
        p["pis"] = [x for x in pis if x["plo_id"] == p["id"]]
        p["measurement_plans"] = sorted([m for m in mplans if m["plo_id"] == p["id"]], key=lambda m: m["round_no"])
    courses = rows(db, """SELECT c.id, c.course_code, c.course_name, c.credits, c.credits_theory, c.credits_practice, c.course_structure,
                                 c.prerequisites, pc.semester_no, pc.knowledge_block, pc.is_elective,
                                 (SELECT COUNT(*) FROM clos WHERE course_id=c.id) AS n_clos,
                                 (SELECT COUNT(*) FROM class_sections WHERE course_id=c.id) AS n_sections,
                                 c.description IS NOT NULL AS has_description
                          FROM program_courses pc JOIN courses c ON c.id=pc.course_id WHERE pc.program_id=:p
                          ORDER BY pc.semester_no IS NULL, pc.semester_no, pc.is_elective, c.course_code""", p=pid)
    matrix = rows(db, """SELECT pc.course_id, pc.pi_id, pc.level FROM pi_courses pc JOIN performance_indicators pi ON pi.id=pc.pi_id
                         JOIN plos p ON p.id=pi.plo_id WHERE p.program_id=:p""", p=pid)
    d = {k: getattr(prog, k) for k in ("id", "code", "name", "name_en", "level", "department", "faculty", "major_code", "cohort_year",
                                       "total_credits", "decision_no", "objective")}
    return {**d, "target_pct": float(prog.target_pct), "plos": plos, "courses": courses, "pi_matrix": matrix}


@router.put("/programs/{pid}/courses")
def upsert_program_course(pid: int, body: ProgramCourseIn, db: Session = Depends(get_db), _=Depends(require("admin"))):
    if not db.get(Program, pid) or not db.get(Course, body.course_id):
        raise HTTPException(404, "Không tìm thấy CTĐT hoặc học phần")
    db.execute(text("""INSERT INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective)
                       VALUES (:p, :c, :s, :b, :e) ON DUPLICATE KEY UPDATE semester_no=VALUES(semester_no),
                       knowledge_block=VALUES(knowledge_block), is_elective=VALUES(is_elective)"""),
               {"p": pid, "c": body.course_id, "s": body.semester_no, "b": (body.knowledge_block or "").strip() or None, "e": body.is_elective})
    db.commit()
    return {"ok": True}


@router.delete("/programs/{pid}/courses/{cid}")
def remove_program_course(pid: int, cid: int, db: Session = Depends(get_db), _=Depends(require("admin"))):
    n = db.execute(text("DELETE FROM program_courses WHERE program_id=:p AND course_id=:c"), {"p": pid, "c": cid}).rowcount
    db.execute(text("""DELETE pc FROM pi_courses pc JOIN performance_indicators pi ON pi.id=pc.pi_id JOIN plos p ON p.id=pi.plo_id
                       WHERE p.program_id=:p AND pc.course_id=:c"""), {"p": pid, "c": cid})
    db.commit()
    if not n:
        raise HTTPException(404, "Học phần không thuộc CTĐT")
    return {"deleted": cid}


@router.put("/courses/{cid}/pi-levels")
def set_pi_level(cid: int, body: PICourseIn, db: Session = Depends(get_db), _=Depends(require("admin"))):
    """Ma trận học phần – PI (Phụ lục II): đặt hoặc bỏ mức đáp ứng của học phần với một PI."""
    if not db.get(Course, cid):
        raise HTTPException(404, "Không tìm thấy học phần")
    if not db.execute(text("SELECT 1 FROM performance_indicators WHERE id=:i"), {"i": body.pi_id}).scalar():
        raise HTTPException(422, "PI không tồn tại")
    lv = (body.level or "").strip().upper()
    if lv and lv not in ("I", "R", "M", "1", "2", "3", "4", "5", "6"):
        raise HTTPException(422, "Mức đáp ứng là I, R, M hoặc trình độ năng lực 1–6")
    if lv:
        db.execute(text("""INSERT INTO pi_courses (pi_id, course_id, level) VALUES (:p, :c, :l)
                           ON DUPLICATE KEY UPDATE level=VALUES(level)"""), {"p": body.pi_id, "c": cid, "l": lv})
    else:
        db.execute(text("DELETE FROM pi_courses WHERE pi_id=:p AND course_id=:c"), {"p": body.pi_id, "c": cid})
    db.commit()
    return {"ok": True}


@router.get("/courses/{cid}/plos")
def course_plos(cid: int, db: Session = Depends(get_db), _=Depends(current_user)):
    """PLO dùng để ánh xạ CLO của học phần: PLO các CTĐT có học phần (CTĐT mới nhất trước)."""
    progs = rows(db, """SELECT p.id, p.code, p.name, p.cohort_year FROM programs p JOIN program_courses pc ON pc.program_id=p.id
                        WHERE pc.course_id=:c ORDER BY p.cohort_year IS NULL, p.cohort_year DESC, p.code""", c=cid)
    if not progs:   # học phần chưa gán CTĐT: cho chọn PLO của mọi CTĐT
        progs = rows(db, "SELECT id, code, name, cohort_year FROM programs ORDER BY cohort_year IS NULL, cohort_year DESC, code")
    for p in progs:
        p["plos"] = rows(db, "SELECT id, plo_code, description, group_no FROM plos WHERE program_id=:p ORDER BY LENGTH(plo_code), plo_code", p=p["id"])
        # góp ý F2a: CLO ánh xạ tới PI; kèm mức học phần đáp ứng PI theo ma trận CTĐT (pi_courses.level) để gợi ý
        pis = rows(db, """SELECT i.id, i.plo_id, i.pi_code, i.description, i.competency_level, pc.level AS course_level
                          FROM performance_indicators i JOIN plos l ON l.id=i.plo_id
                          LEFT JOIN pi_courses pc ON pc.pi_id=i.id AND pc.course_id=:c
                          WHERE l.program_id=:p ORDER BY i.pi_code""", p=p["id"], c=cid)
        for plo in p["plos"]:
            plo["pis"] = [i for i in pis if i["plo_id"] == plo["id"]]
    return progs


@router.get("/courses/{cid}/syllabus")
def syllabus(cid: int, version: Optional[int] = None, db: Session = Depends(get_db), u: User = Depends(current_user)):
    """Đề cương chi tiết học phần (mọi tài khoản đều xem được – thông tin công khai trong trường).
    Góp ý F1: kèm phiên bản đề cương (mặc định Bộ môn xem bản mới nhất, GV xem bản đang áp dụng) và bảng kiểm tra trước khi duyệt."""
    c = db.get(Course, cid)
    if not c:
        raise HTTPException(404, "Không tìm thấy học phần")
    info = {k: getattr(c, k) for k in ("id", "course_code", "course_name", "credits", "credits_theory", "credits_practice",
                                       "course_structure", "prerequisites", "description")}
    info["clo_target_pct"] = float(c.clo_target_pct)
    codes = [x.strip() for x in (c.prerequisites or "").replace(";", ",").split(",") if x.strip()]
    pre = {}
    if codes:
        q = text("SELECT id, course_code, course_name FROM courses WHERE course_code IN :codes").bindparams(bindparam("codes", expanding=True))
        pre = {r["course_code"]: dict(r) for r in db.execute(q, {"codes": codes}).mappings()}
    info["prerequisite_list"] = [{"course_code": x, "course_name": pre[x]["course_name"] if x in pre else None,
                                  "id": pre[x]["id"] if x in pre else None} for x in codes]
    info["required_by"] = rows(db, """SELECT id, course_code, course_name FROM courses WHERE id<>:c AND prerequisites LIKE :k
                                      ORDER BY course_code""", c=cid, k=f"%{c.course_code}%")
    programs = rows(db, """SELECT p.id, p.code, p.name, p.cohort_year, pc.semester_no, pc.knowledge_block, pc.is_elective
                           FROM program_courses pc JOIN programs p ON p.id=pc.program_id WHERE pc.course_id=:c
                           ORDER BY p.cohort_year IS NULL, p.cohort_year DESC, p.code""", c=cid)
    for p in programs:
        p["pis"] = rows(db, """SELECT pi.id, pi.pi_code, pi.description, pi.competency_level, pc.level, pl.plo_code, pl.id AS plo_id
                               FROM pi_courses pc JOIN performance_indicators pi ON pi.id=pc.pi_id JOIN plos pl ON pl.id=pi.plo_id
                               WHERE pc.course_id=:c AND pl.program_id=:p ORDER BY LENGTH(pi.pi_code), pi.pi_code""", c=cid, p=p["id"])
    clos = rows(db, """SELECT c.id, c.clo_code, c.description, c.bloom_level_id, b.name_vi AS bloom,
                              (SELECT COUNT(*) FROM question_clo_mapping m JOIN question_bank q ON q.id=m.question_id
                               WHERE m.clo_id=c.id AND q.is_cancelled=0) AS n_questions
                       FROM clos c LEFT JOIN bloom_levels b ON b.id=c.bloom_level_id WHERE c.course_id=:c ORDER BY c.clo_code""", c=cid)
    maps = rows(db, """SELECT m.clo_id, m.plo_id, m.level, p.plo_code, pr.code AS program_code FROM clo_plo_mapping m
                       JOIN plos p ON p.id=m.plo_id JOIN programs pr ON pr.id=p.program_id JOIN clos c ON c.id=m.clo_id
                       WHERE c.course_id=:c ORDER BY pr.code, p.plo_code""", c=cid)
    plans = rows(db, """SELECT p.*, s.name AS semester FROM clo_assessment_plans p JOIN clos c ON c.id=p.clo_id
                        JOIN semesters s ON s.id=p.semester_id WHERE c.course_id=:c ORDER BY s.academic_year DESC, s.term DESC""", c=cid)
    pimaps = rows(db, """SELECT m.clo_id, m.pi_id, m.level, i.pi_code, pl.plo_code, pr.code AS program_code
                         FROM clo_pi_mapping m JOIN performance_indicators i ON i.id=m.pi_id JOIN plos pl ON pl.id=i.plo_id
                         JOIN programs pr ON pr.id=pl.program_id JOIN clos c ON c.id=m.clo_id WHERE c.course_id=:c
                         ORDER BY pr.code, LENGTH(pl.plo_code), pl.plo_code, i.pi_code""", c=cid)
    for x in clos:
        x["plos"] = [m for m in maps if m["clo_id"] == x["id"]]
        x["pis"] = [m for m in pimaps if m["clo_id"] == x["id"]]      # góp ý F2a: CLO → PI
        x["plan"] = next((p for p in plans if p["clo_id"] == x["id"]), None)
    covered = {m["pi_id"] for m in pimaps}
    for p in programs:   # PI mà CTĐT giao cho học phần: đã có CLO đáp ứng chưa
        for pi in p["pis"]:
            pi["clos"] = [m for m in pimaps if m["pi_id"] == pi["id"]]
            pi["covered"] = pi["id"] in covered
    lid = u.lecturer.id if u.role == "lecturer" and u.lecturer else None
    sections = rows(db, """SELECT cs.id, cs.section_code, cs.moodle_course_id, s.name AS semester, s.academic_year, l.full_name AS lecturer,
                                  cs.lecturer_id = :l AS mine,
                                  (SELECT COUNT(*) FROM enrollments e WHERE e.class_section_id=cs.id AND e.status='active') AS n_students,
                                  (SELECT COUNT(*) FROM exams x WHERE x.class_section_id=cs.id) AS n_exams
                           FROM class_sections cs JOIN semesters s ON s.id=cs.semester_id JOIN lecturers l ON l.id=cs.lecturer_id
                           WHERE cs.course_id=:c AND (:l IS NULL OR cs.lecturer_id=:l OR :admin)
                           ORDER BY s.academic_year DESC, s.term DESC, cs.section_code""", c=cid, l=lid, admin=u.role == "admin")
    summary = rows(db, """SELECT s.name AS semester, v.clo_code, v.n_evaluated, v.n_achieved, v.achieved_pct, v.target_pct
                          FROM v_course_clo_summary v JOIN semesters s ON s.id=v.semester_id WHERE v.course_id=:c
                          ORDER BY s.academic_year DESC, s.term DESC, v.clo_code""", c=cid)
    n_q = db.execute(text("SELECT COUNT(*) FROM question_bank WHERE course_id=:c AND is_cancelled=0"), {"c": cid}).scalar()
    return {**info, "programs": programs, "clos": clos, "sections": sections, "clo_summary": summary, "n_questions": n_q,
            "outlines": syllabi.outlines(db, cid), "can_edit": u.role == "admin",
            **syllabi.doc(db, c, syllabi.pick_version(c, version, u.role == "admin"))}
