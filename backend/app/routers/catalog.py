"""Danh mục: học kỳ, CTĐT–PLO–PI, kế hoạch đo PI (BM3b), phân công, môn học–CLO, kế hoạch CLO (BM6a),
lớp học phần và danh sách SV (UC-06)."""
import csv
import io
import unicodedata

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import check_course_access, check_section_access, current_user, require
from ..models import (CLO, CLOAssessmentPlan, CLOPLOMapping, ClassSection, Course, Enrollment, PIAssessmentPlan,
                      PIPlanCLO, PLO, Program, Student, User)
from ..services import results
from ..schemas import CLOIn, CLOPlanIn, PIPlanIn, PLOIn

router = APIRouter(prefix="/api", tags=["Danh mục & kế hoạch đo lường"])


def rows(db: Session, sql: str, **p) -> list[dict]:
    return [dict(r) for r in db.execute(text(sql), p).mappings()]


@router.get("/semesters")
def semesters(db: Session = Depends(get_db), _=Depends(current_user)):
    return rows(db, "SELECT * FROM semesters ORDER BY academic_year DESC, term DESC")


@router.get("/bloom-levels")
def bloom(db: Session = Depends(get_db), _=Depends(current_user)):
    return rows(db, "SELECT * FROM bloom_levels ORDER BY id")


@router.get("/lecturers")
def lecturers(db: Session = Depends(get_db), _=Depends(current_user)):
    return rows(db, "SELECT id, lecturer_code, full_name, department FROM lecturers ORDER BY full_name")


# ------------------------------------------------------------------ CTĐT, PLO, PI
@router.get("/programs")
def programs(db: Session = Depends(get_db), _=Depends(current_user)):
    return rows(db, "SELECT * FROM programs ORDER BY code")


@router.get("/programs/{pid}")
def program_detail(pid: int, db: Session = Depends(get_db), _=Depends(current_user)):
    prog = db.get(Program, pid)
    if not prog:
        raise HTTPException(404, "Không tìm thấy CTĐT")
    plos = rows(db, "SELECT * FROM plos WHERE program_id=:p ORDER BY plo_code", p=pid)
    pis = rows(db, """SELECT pi.*, (SELECT GROUP_CONCAT(c.course_code) FROM pi_courses pc JOIN courses c ON c.id=pc.course_id
                                     WHERE pc.pi_id=pi.id) AS courses
                      FROM performance_indicators pi JOIN plos p ON p.id=pi.plo_id WHERE p.program_id=:p ORDER BY pi.pi_code""", p=pid)
    mplans = rows(db, "SELECT m.* FROM plo_measurement_plans m JOIN plos p ON p.id=m.plo_id WHERE p.program_id=:p", p=pid)
    for p in plos:
        p["pis"] = [x for x in pis if x["plo_id"] == p["id"]]
        p["measurement_plans"] = sorted([m for m in mplans if m["plo_id"] == p["id"]], key=lambda m: m["round_no"])
    return {"id": prog.id, "code": prog.code, "name": prog.name, "department": prog.department,
            "target_pct": float(prog.target_pct), "plos": plos}


@router.put("/plos/{plo_id}")
def update_plo(plo_id: int, body: PLOIn, db: Session = Depends(get_db), _=Depends(require("admin"))):
    plo = db.get(PLO, plo_id)
    if not plo:
        raise HTTPException(404, "Không tìm thấy CĐR")
    if body.description is not None:
        plo.description = body.description
    changed = body.target_pct is not None and float(plo.target_pct) != float(body.target_pct)
    if body.target_pct is not None:
        plo.target_pct = body.target_pct
    db.commit()
    if changed:  # chỉ tiêu PLO đổi → đánh giá lại Đạt/Không đạt của PLO (BM2)
        results.recompute_plo_all_years(db, plo_id)
    return {"ok": True}


@router.get("/pi-plans")
def pi_plans(program_id: int = 1, academic_year: str | None = None, db: Session = Depends(get_db), _=Depends(current_user)):
    if not db.get(Program, program_id):
        raise HTTPException(404, "Không tìm thấy CTĐT")
    data = rows(db, """
        SELECT pl.id, pl.pi_id, pi.pi_code, pi.description AS pi_description, p.id AS plo_id, p.plo_code,
               pl.course_id, c.course_code, c.course_name, pl.semester_id, s.name AS semester, s.academic_year,
               pl.method, pl.cycle, pl.target_pct, pl.lecturer_id, l.full_name AS lecturer,
               r.n_evaluated, r.n_achieved, r.achieved_pct, r.is_achieved,
               (SELECT GROUP_CONCAT(cl.clo_code ORDER BY cl.clo_code) FROM pi_plan_clos x JOIN clos cl ON cl.id=x.clo_id
                 WHERE x.plan_id=pl.id) AS clo_codes
        FROM pi_assessment_plans pl JOIN performance_indicators pi ON pi.id=pl.pi_id JOIN plos p ON p.id=pi.plo_id
        JOIN courses c ON c.id=pl.course_id JOIN semesters s ON s.id=pl.semester_id
        LEFT JOIN lecturers l ON l.id=pl.lecturer_id LEFT JOIN pi_results r ON r.plan_id=pl.id
        WHERE p.program_id=:p AND (:y IS NULL OR s.academic_year=:y)
        ORDER BY p.plo_code, pi.pi_code""", p=program_id, y=academic_year)
    return data


@router.post("/pi-plans")
def create_pi_plan(body: PIPlanIn, db: Session = Depends(get_db), _=Depends(require("admin"))):
    plan = PIAssessmentPlan(**body.model_dump(exclude={"clo_ids"}))
    db.add(plan); db.flush()
    for cid in body.clo_ids:
        clo = db.get(CLO, cid)
        if not clo or clo.course_id != body.course_id:
            raise HTTPException(422, "CLO không thuộc môn học lấy minh chứng")
        db.add(PIPlanCLO(plan_id=plan.id, clo_id=cid))
    db.commit()
    results.recompute_pi_plans(db)  # kế hoạch mới có thể dùng ngay kết quả CLO đã đo
    return {"id": plan.id}


def _plan_plo_year(db: Session, plan_id: int):
    return db.execute(text("""SELECT pi.plo_id, s.academic_year FROM pi_assessment_plans p JOIN performance_indicators pi ON pi.id=p.pi_id
                              JOIN semesters s ON s.id=p.semester_id WHERE p.id=:p"""), {"p": plan_id}).first()


@router.put("/pi-plans/{plan_id}")
def update_pi_plan(plan_id: int, body: PIPlanIn, db: Session = Depends(get_db), _=Depends(require("admin"))):
    plan = db.get(PIAssessmentPlan, plan_id)
    if not plan:
        raise HTTPException(404, "Không tìm thấy kế hoạch")
    old = _plan_plo_year(db, plan_id)
    for k, v in body.model_dump(exclude={"clo_ids"}).items():
        setattr(plan, k, v)
    db.execute(text("DELETE FROM pi_plan_clos WHERE plan_id=:p"), {"p": plan_id})
    for cid in body.clo_ids:
        clo = db.get(CLO, cid)
        if not clo or clo.course_id != body.course_id:
            raise HTTPException(422, "CLO không thuộc môn học lấy minh chứng")
        db.add(PIPlanCLO(plan_id=plan_id, clo_id=cid))
    db.commit()
    results.recompute_pi_plans(db)
    results.recompute_plo(db, *old)  # PI có thể đã chuyển sang CĐR/năm học khác
    return {"ok": True}


@router.delete("/pi-plans/{plan_id}")
def delete_pi_plan(plan_id: int, db: Session = Depends(get_db), _=Depends(require("admin"))):
    old = _plan_plo_year(db, plan_id)
    if not old:
        raise HTTPException(404, "Không tìm thấy kế hoạch")
    db.execute(text("DELETE FROM pi_assessment_plans WHERE id=:p"), {"p": plan_id}); db.commit()
    results.recompute_plo(db, *old)
    return {"ok": True}


@router.get("/assignments")
def assignments(semester_id: int | None = None, db: Session = Depends(get_db), _=Depends(current_user)):
    return rows(db, """SELECT a.*, s.name AS semester, c.course_code, c.course_name, l.full_name AS lecturer
                       FROM assessment_assignments a JOIN semesters s ON s.id=a.semester_id JOIN courses c ON c.id=a.course_id
                       JOIN lecturers l ON l.id=a.lecturer_id WHERE (:s IS NULL OR a.semester_id=:s)
                       ORDER BY s.academic_year DESC, s.term DESC, c.course_code""", s=semester_id)


# ------------------------------------------------------------------ Môn học & CLO
@router.get("/courses")
def courses(db: Session = Depends(get_db), _=Depends(current_user)):
    return rows(db, "SELECT * FROM courses ORDER BY course_code")


@router.get("/courses/{cid}")
def course_detail(cid: int, semester_id: int | None = None, db: Session = Depends(get_db), _=Depends(current_user)):
    """Đề cương môn (CLO, ma trận CLO–PLO, kế hoạch đo) là thông tin công khai trong trường – mọi tài khoản đều xem được."""
    c = db.get(Course, cid)
    if not c:
        raise HTTPException(404, "Không tìm thấy môn học")
    clos = rows(db, "SELECT c.*, b.name_vi AS bloom FROM clos c LEFT JOIN bloom_levels b ON b.id=c.bloom_level_id WHERE course_id=:c ORDER BY clo_code", c=cid)
    maps = rows(db, """SELECT m.clo_id, m.plo_id, m.level, p.plo_code FROM clo_plo_mapping m JOIN plos p ON p.id=m.plo_id
                       JOIN clos c ON c.id=m.clo_id WHERE c.course_id=:c""", c=cid)
    plans = rows(db, "SELECT p.* FROM clo_assessment_plans p JOIN clos c ON c.id=p.clo_id WHERE c.course_id=:c AND (:s IS NULL OR p.semester_id=:s)",
                 c=cid, s=semester_id)
    for x in clos:
        x["plos"] = [m for m in maps if m["clo_id"] == x["id"]]
        x["plan"] = next((p for p in plans if p["clo_id"] == x["id"]), None)
    return {"id": c.id, "course_code": c.course_code, "course_name": c.course_name, "credits": c.credits,
            "clo_target_pct": float(c.clo_target_pct), "clos": clos,
            "outlines": rows(db, "SELECT * FROM course_outlines WHERE course_id=:c ORDER BY chapter_number", c=cid)}


@router.post("/clos")
def create_clo(body: CLOIn, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    check_course_access(db, u, body.course_id)
    if db.query(CLO).filter_by(course_id=body.course_id, clo_code=body.clo_code).first():
        raise HTTPException(409, f"Môn học đã có {body.clo_code}")
    for m in body.plos:
        if not db.get(PLO, int(m["plo_id"])):
            raise HTTPException(422, f"PLO {m['plo_id']} không tồn tại")
        if m.get("level", "R") not in ("I", "R", "M"):
            raise HTTPException(422, "Mức đóng góp CLO–PLO phải là I, R hoặc M")
    clo = CLO(course_id=body.course_id, clo_code=body.clo_code, description=body.description, bloom_level_id=body.bloom_level_id)
    db.add(clo); db.flush()
    for m in body.plos:
        db.add(CLOPLOMapping(clo_id=clo.id, plo_id=int(m["plo_id"]), level=m.get("level", "R")))
    db.commit()
    return {"id": clo.id}


@router.put("/clo-plans")
def upsert_clo_plan(body: CLOPlanIn, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    clo = db.get(CLO, body.clo_id)
    if not clo:
        raise HTTPException(404, "Không tìm thấy CLO")
    check_course_access(db, u, clo.course_id)
    plan = db.query(CLOAssessmentPlan).filter_by(clo_id=body.clo_id, semester_id=body.semester_id).first()
    if not plan:
        plan = CLOAssessmentPlan(clo_id=body.clo_id, semester_id=body.semester_id); db.add(plan)
    for k, v in body.model_dump().items():
        setattr(plan, k, v)
    db.commit()
    n = results.reanalyze_course(db, clo.course_id, body.semester_id)  # ngưỡng/chỉ tiêu mới áp dụng cho kết quả đã đo
    return {"id": plan.id, "reanalyzed_exams": n}


# ------------------------------------------------------------------ Lớp học phần
@router.get("/class-sections")
def class_sections(u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    if u.role == "lecturer" and not u.lecturer:
        return []   # tài khoản GV chưa gắn hồ sơ giảng viên: không thấy lớp nào
    lid = u.lecturer.id if u.role == "lecturer" else None
    return rows(db, """SELECT cs.id, cs.section_code, cs.course_id, c.course_code, c.course_name, cs.semester_id, s.name AS semester,
                              s.academic_year, l.full_name AS lecturer, cs.moodle_course_id,
                              (SELECT COUNT(*) FROM enrollments e WHERE e.class_section_id=cs.id AND e.status='active') AS n_students,
                              (SELECT COUNT(*) FROM exams x WHERE x.class_section_id=cs.id) AS n_exams
                       FROM class_sections cs JOIN courses c ON c.id=cs.course_id JOIN semesters s ON s.id=cs.semester_id
                       JOIN lecturers l ON l.id=cs.lecturer_id WHERE (:l IS NULL OR cs.lecturer_id=:l)
                       ORDER BY s.academic_year DESC, s.term DESC, cs.section_code""", l=lid)


@router.get("/class-sections/{cs_id}/students")
def section_students(cs_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    check_section_access(db, u, cs_id)
    return rows(db, """SELECT s.id, s.student_code, s.full_name, s.class_name, s.moodle_user_id, e.status
                       FROM enrollments e JOIN students s ON s.id=e.student_id WHERE e.class_section_id=:cs
                       ORDER BY s.student_code""", cs=cs_id)


@router.post("/class-sections/{cs_id}/students/import")
async def import_students(cs_id: int, file: UploadFile = File(...), u: User = Depends(require("admin", "lecturer")),
                          db: Session = Depends(get_db)):
    """Nhập danh sách lớp HP từ CSV: student_code, full_name, class_name (UTF-8/UTF-8 BOM/Windows-1258; dấu , hoặc ;)."""
    check_section_access(db, u, cs_id)
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "File quá lớn (tối đa 5 MB)")
    for enc in ("utf-8-sig", "cp1258", "cp1252"):
        try:
            content = raw.decode(enc); break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(422, "Không đọc được bảng mã của file – hãy lưu file CSV dạng UTF-8")
    content = unicodedata.normalize("NFC", content)   # Windows-1258 tách dấu thành ký tự tổ hợp → gộp lại
    first = content.splitlines()[0] if content.strip() else ""
    delim = ";" if first.count(";") > first.count(",") else ","
    reader = csv.DictReader(io.StringIO(content), delimiter=delim)
    if not reader.fieldnames or "student_code" not in [f.strip() for f in reader.fieldnames]:
        raise HTTPException(422, "File thiếu cột student_code (cần: student_code, full_name, class_name)")
    n = 0
    for r in reader:
        r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
        code = r.get("student_code", "")
        if not code:
            continue
        if len(code) > 100:
            raise HTTPException(422, f"Mã SV quá dài: {code[:30]}…")
        s = db.query(Student).filter_by(student_code=code).first()
        if not s:
            s = Student(student_code=code, full_name=(r.get("full_name") or code)[:100], class_name=(r.get("class_name") or None))
            db.add(s); db.flush()
        if not db.get(Enrollment, (cs_id, s.id)):
            db.add(Enrollment(class_section_id=cs_id, student_id=s.id)); n += 1
    db.commit()
    return {"added": n}
