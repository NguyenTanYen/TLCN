"""Nhập điểm thủ công / bằng Excel và gộp nhiều bài KT để đánh giá CĐR (góp ý 15/10).

- Bài KT nhập điểm (exam_type = manual): GV khai báo các câu/ý chấm tay, điểm tối đa và CLO mỗi câu/ý đo;
  nhập điểm trên lưới hoặc tải bảng điểm mẫu Excel về điền rồi tải lên; hoặc tạo luôn bài từ một file Excel bất kỳ
  (bài làm ngoài hệ thống: tiểu luận, thực hành, đồ án…).
- Chọn bài làm minh chứng CLO (counts_for_clo) và gộp 2, 3… bài (kể cả khác lớp HP cùng môn) để phân tích CLO, PI/PLO.
"""
import json
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import check_course_access, check_section_access, get_exam_for, require, lecturer_only
from ..http_utils import attachment
from ..models import Exam, Student, User
from ..services import combine, manual, results

router = APIRouter(prefix="/api", tags=["Nhập điểm thủ công & gộp bài KT"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class CLOWeight(BaseModel):
    clo_id: int
    weight: float = Field(default=1, gt=0, le=1)


class ManualItemIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    points: float = Field(gt=0, le=999)
    clos: list[CLOWeight] = Field(min_length=1)
    outline_id: Optional[int] = None
    bloom_level_id: Optional[int] = Field(default=None, ge=1, le=6)


class ManualExamIn(BaseModel):
    exam_title: str = Field(min_length=3, max_length=255)
    assessment_type: Literal["process", "final"] = "process"
    exam_date: Optional[date] = None
    max_score: float = Field(default=10, gt=0, le=999)
    counts_for_clo: bool = True
    items: list[ManualItemIn] = Field(min_length=1)


class ItemsIn(BaseModel):
    items: list[ManualItemIn] = Field(min_length=1)


class GradeRow(BaseModel):
    student_id: int
    absent: bool = False
    scores: dict[str, Optional[float]] = {}


class GradesIn(BaseModel):
    rows: list[GradeRow]
    analyze: bool = True


class EvidenceIn(BaseModel):
    counts_for_clo: bool


class CombineIn(BaseModel):
    exam_ids: list[int] = Field(min_length=1, max_length=20)
    mode: Literal["merge", "cumulative"] = "merge"


def _manual_exam(db: Session, u: User, exam_id: int) -> Exam:
    e = get_exam_for(db, u, exam_id)
    if e.exam_type != "manual":
        raise HTTPException(422, "Chỉ bài KT nhập điểm mới nhập điểm thủ công (bài Moodle/giấy lấy kết quả từ đồng bộ hoặc chấm phiếu)")
    return e


def _check_items(db: Session, course_id: int, items: list[ManualItemIn]) -> None:
    for it in items:
        if it.outline_id and not db.execute(text("SELECT 1 FROM course_outlines WHERE id=:o AND course_id=:c"),
                                            {"o": it.outline_id, "c": course_id}).scalar():
            raise HTTPException(422, f"Chương của \"{it.title}\" không thuộc môn học")


def _analyze(db: Session, e: Exam) -> dict | None:
    n = db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e AND status='finished'"), {"e": e.id}).scalar()
    if not n:
        results.recompute_class_section(db, e.class_section_id)
        return None
    return results.analyze_exam(db, e.id)


# ------------------------------------------------------------------ bài nhập điểm
@router.post("/class-sections/{cs_id}/manual-exams", status_code=201)
def create_manual_exam(cs_id: int, body: ManualExamIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    cs = check_section_access(db, u, cs_id)
    _check_items(db, cs.course_id, body.items)
    e = Exam(class_section_id=cs.id, exam_title=body.exam_title.strip(), assessment_type=body.assessment_type, exam_type="manual",
             exam_date=body.exam_date, max_score=body.max_score, counts_for_clo=body.counts_for_clo, status="Published", created_by=u.id)
    db.add(e); db.flush()
    try:
        manual.add_items(db, e, cs.course_id, [i.model_dump() for i in body.items], u.id)
    except manual.GradeError as ex:
        db.rollback(); raise HTTPException(422, str(ex))
    db.commit()
    return {"id": e.id}


@router.post("/courses/{course_id}/manual-exams", status_code=201)
def create_course_manual_exam(course_id: int, body: ManualExamIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    """Đề nhập điểm của môn (tạo ở trang môn học): khai báo câu/ý gắn CLO một lần, giao cho các lớp HP để nhập điểm."""
    check_course_access(db, u, course_id)
    _check_items(db, course_id, body.items)
    e = Exam(class_section_id=None, course_id=course_id, exam_title=body.exam_title.strip(), assessment_type=body.assessment_type,
             exam_type="manual", exam_date=body.exam_date, max_score=body.max_score, counts_for_clo=body.counts_for_clo,
             status="Draft", created_by=u.id)
    db.add(e); db.flush()
    try:
        manual.add_items(db, e, course_id, [i.model_dump() for i in body.items], u.id)
    except manual.GradeError as ex:
        db.rollback(); raise HTTPException(422, str(ex))
    db.commit()
    return {"id": e.id}


@router.put("/exams/{exam_id}/manual-items")
def replace_items(exam_id: int, body: ItemsIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    e = _manual_exam(db, u, exam_id)
    if db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e"), {"e": exam_id}).scalar():
        raise HTTPException(409, "Bài đã có điểm – xóa điểm đã nhập trước khi đổi cấu trúc câu/ý")
    _check_items(db, e.class_section.course_id, body.items)
    old = [q.question_id for q in e.questions]
    e.questions.clear(); db.flush()
    if old:
        db.execute(text("DELETE FROM question_bank WHERE question_type='manual' AND id IN :ids AND NOT EXISTS "
                        "(SELECT 1 FROM exam_questions eq WHERE eq.question_id=question_bank.id)").bindparams(
            bindparam("ids", expanding=True)), {"ids": old})
    try:
        manual.add_items(db, e, e.class_section.course_id, [i.model_dump() for i in body.items], u.id)
    except manual.GradeError as ex:
        db.rollback(); raise HTTPException(422, str(ex))
    db.commit()
    return {"ok": True, "n_items": len(body.items)}


@router.get("/exams/{exam_id}/grades")
def get_grades(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    return manual.gradebook(db, _manual_exam(db, u, exam_id))


@router.put("/exams/{exam_id}/grades")
def put_grades(exam_id: int, body: GradesIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    e = _manual_exam(db, u, exam_id)
    allowed = {r[0] for r in db.execute(text("""SELECT student_id FROM enrollments WHERE class_section_id=:cs
                                                 UNION SELECT student_id FROM exam_attempts WHERE exam_id=:e"""),
                                          {"cs": e.class_section_id, "e": exam_id})}
    if any(r.student_id not in allowed for r in body.rows):
        raise HTTPException(422, "Có SV không thuộc lớp học phần")
    try:
        res = manual.save_grades(db, e, [r.model_dump() for r in body.rows])
    except manual.GradeError as ex:
        db.rollback(); raise HTTPException(422, str(ex))
    if body.analyze:
        res["analysis"] = _analyze(db, e)
    return res


@router.get("/exams/{exam_id}/grades.xlsx")
def grades_template(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = _manual_exam(db, u, exam_id)
    return Response(manual.template_xlsx(db, e), media_type=XLSX,
                    headers=attachment(f"BangDiem_{e.class_section.section_code}_{e.exam_title}.xlsx"))


async def _read(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "File quá lớn (tối đa 10 MB)")
    return data


def _resolve_students(db: Session, cs_id: int, parsed: dict, enroll_missing: bool, apply: bool):
    """MSSV trong file -> student_id; SV chưa có trong lớp: báo lại, hoặc ghi danh khi enroll_missing."""
    known, missing = {}, []
    for s in parsed["students"]:
        row = db.execute(text("""SELECT s.id, EXISTS(SELECT 1 FROM enrollments WHERE class_section_id=:cs AND student_id=s.id)
                                 FROM students s WHERE s.student_code=:c"""), {"cs": cs_id, "c": s["student_code"]}).first()
        if row and row[1]:
            known[s["student_code"]] = row[0]; continue
        missing.append({"student_code": s["student_code"], "full_name": s["full_name"], "exists": bool(row)})
        if apply and enroll_missing:
            sid = row[0] if row else None
            if not sid:
                st = Student(student_code=s["student_code"], full_name=s["full_name"] or s["student_code"]); db.add(st); db.flush(); sid = st.id
            db.execute(text("INSERT IGNORE INTO enrollments (class_section_id, student_id) VALUES (:cs, :s)"), {"cs": cs_id, "s": sid})
            known[s["student_code"]] = sid
    return known, missing


def _rows_for(parsed: dict, col_to_q: dict, known: dict) -> list[dict]:
    out = []
    for s in parsed["students"]:
        if s["student_code"] not in known:
            continue
        out.append({"student_id": known[s["student_code"]], "absent": s["absent"],
                    "scores": {str(col_to_q[i]): v for i, v in s["scores"].items() if i in col_to_q}})
    return out


@router.post("/exams/{exam_id}/grades/import")
async def import_grades(exam_id: int, dry_run: bool = True, enroll_missing: bool = False, file: UploadFile = File(...),
                        u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    """Nhập điểm từ Excel vào bài đã có: khớp cột theo mã câu (bảng điểm mẫu), theo tên câu/ý, hoặc theo thứ tự cột."""
    e = _manual_exam(db, u, exam_id)
    try:
        parsed = manual.parse_sheet(await _read(file))
    except manual.GradeError as ex:
        raise HTTPException(422, str(ex))
    items = manual.items_of(db, exam_id)
    ids = {i["question_id"] for i in items}
    col_to_q, unmatched = {}, []
    by_title = {i["title"].strip().lower(): i["question_id"] for i in items}
    for k, m in enumerate(parsed["items"]):
        q = m["key"] if m["key"] in ids else by_title.get(m["title"].strip().lower())
        if q is None and len(parsed["items"]) == len(items):
            q = items[k]["question_id"]
        if q is None:
            unmatched.append(m["header"])
        else:
            col_to_q[m["col"]] = q
    if unmatched:
        raise HTTPException(422, "Không khớp được cột với câu/ý của bài: " + "; ".join(unmatched)
                            + " – dùng bảng điểm mẫu của hệ thống hoặc đặt tên cột trùng tên câu/ý")
    known, missing = _resolve_students(db, e.class_section_id, parsed, enroll_missing, apply=not dry_run)
    rows = _rows_for(parsed, {k: v for k, v in col_to_q.items()}, known)
    preview = {"n_rows": len(parsed["students"]), "n_matched": len(rows), "missing_students": missing,
               "columns": [{"header": m["header"], "question_id": col_to_q.get(m["col"])} for m in parsed["items"]]}
    if dry_run:
        # kiểm tra điểm hợp lệ ngay ở bước xem trước
        pts = {i["question_id"]: i["points"] for i in items}
        errs = [f"{s['student_code']}: {v:g} > {pts[col_to_q[c]]:g} ở cột \"{next(m['header'] for m in parsed['items'] if m['col'] == c)}\""
                for s in parsed["students"] for c, v in s["scores"].items() if v is not None and c in col_to_q and (v < 0 or v > pts[col_to_q[c]] + 1e-9)]
        return {**preview, "errors": errs[:30], "dry_run": True}
    try:
        res = manual.save_grades(db, e, rows)
    except manual.GradeError as ex:
        db.rollback(); raise HTTPException(422, str(ex))
    res["analysis"] = _analyze(db, e)
    return {**preview, **res, "dry_run": False}


@router.post("/class-sections/{cs_id}/manual-exams/import")
async def create_from_excel(cs_id: int, dry_run: bool = True, enroll_missing: bool = False, file: UploadFile = File(...),
                            exam_title: str = Form(""), assessment_type: str = Form("process"), max_score: float = Form(10),
                            clo_map: str = Form("{}"), points_map: str = Form("{}"),
                            u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    """Tạo bài nhập điểm từ một file Excel bất kỳ (bài làm ngoài hệ thống) và nhập luôn điểm.
    Tiêu đề cột: 'Câu 1 (2đ) [CLO1]' hoặc dòng 'Điểm tối đa' / 'CLO' dưới tiêu đề; thiếu thông tin thì xem trước
    trả về các cột cần chọn CLO/điểm tối đa (clo_map, points_map: {chỉ số cột: ...})."""
    cs = check_section_access(db, u, cs_id)
    try:
        parsed = manual.parse_sheet(await _read(file))
    except manual.GradeError as ex:
        raise HTTPException(422, str(ex))
    if not parsed["items"]:
        raise HTTPException(422, "Không tìm thấy cột điểm nào ngoài MSSV/họ tên")
    cmap = {int(k): v for k, v in json.loads(clo_map or "{}").items()}
    pmap = {int(k): float(v) for k, v in json.loads(points_map or "{}").items() if v not in (None, "")}
    clos = {r[1].upper(): r[0] for r in db.execute(text("SELECT id, clo_code FROM clos WHERE course_id=:c"), {"c": cs.course_id})}
    items, problems = [], []
    for m in parsed["items"]:
        pts = pmap.get(m["col"]) or m["points"]
        if not pts:   # không ghi điểm tối đa: lấy điểm cao nhất trong cột, làm tròn lên số nguyên
            vals = [s["scores"].get(m["col"]) or 0 for s in parsed["students"]]
            pts = float(int(max(vals)) + (0 if max(vals).is_integer() else 1)) if vals and max(vals) > 0 else None
            m["points_guessed"] = True
        chosen = cmap.get(m["col"])
        ids = [int(x) for x in chosen] if chosen else [clos.get(c.upper().replace(" ", "")) for c in m["clos"]]
        bad = [c for c, i in zip(m["clos"], ids) if i is None] if not chosen else []
        ids = [i for i in ids if i]
        m.update({"points": pts, "clo_ids": ids})
        if not pts or not ids or bad:
            problems.append({"col": m["col"], "header": m["header"], "need_points": not pts, "need_clos": not ids,
                             "unknown_clos": bad})
        items.append(m)
    known, missing = _resolve_students(db, cs_id, parsed, enroll_missing, apply=False)
    preview = {"items": [{"col": m["col"], "header": m["header"], "title": m["title"], "points": m["points"],
                          "points_guessed": m.get("points_guessed", False), "clo_ids": m["clo_ids"]} for m in items],
               "problems": problems, "n_rows": len(parsed["students"]), "n_matched": len(known), "missing_students": missing,
               "clos": [{"id": v, "clo_code": k} for k, v in sorted(clos.items())]}
    if dry_run or problems:
        return {**preview, "dry_run": True}
    title = exam_title.strip() or "Bài nhập điểm từ Excel"
    e = Exam(class_section_id=cs.id, exam_title=title[:255], assessment_type="final" if assessment_type == "final" else "process",
             exam_type="manual", max_score=max_score, status="Published", created_by=u.id)
    db.add(e); db.flush()
    try:
        manual.add_items(db, e, cs.course_id, [{"title": m["title"], "points": m["points"],
                                                 "clos": [{"clo_id": c, "weight": round(1 / len(m["clo_ids"]), 2) if k < len(m["clo_ids"]) - 1
                                                           else round(1 - round(1 / len(m["clo_ids"]), 2) * (len(m["clo_ids"]) - 1), 2)}
                                                          for k, c in enumerate(m["clo_ids"])]} for m in items], u.id)
        db.flush()
        known, missing = _resolve_students(db, cs_id, parsed, enroll_missing, apply=True)
        qids = [q.question_id for q in sorted(e.questions, key=lambda q: q.order_index)]
        res = manual.save_grades(db, e, _rows_for(parsed, {m["col"]: qids[k] for k, m in enumerate(items)}, known))
    except manual.GradeError as ex:
        db.rollback(); raise HTTPException(422, str(ex))
    res["analysis"] = _analyze(db, e)
    return {**preview, **res, "exam_id": e.id, "dry_run": False}


# ------------------------------------------------------------------ chọn bài minh chứng & gộp bài
@router.patch("/exams/{exam_id}/evidence")
def set_evidence(exam_id: int, body: EvidenceIn, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """Bài có được gộp vào kết quả CLO của lớp (BM6, PI, PLO) hay không."""
    e = get_exam_for(db, u, exam_id)
    e.counts_for_clo = body.counts_for_clo
    db.commit()
    results.recompute_class_section(db, e.class_section_id)
    return {"id": e.id, "counts_for_clo": e.counts_for_clo}


@router.get("/courses/{course_id}/analyzed-exams")
def analyzed_exams(course_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """Các bài đã phân tích của môn trong các lớp HP người dùng phụ trách – để chọn bài gộp."""
    lid = u.lecturer.id if u.role == "lecturer" and u.lecturer else (0 if u.role == "lecturer" else None)
    return [dict(r) for r in db.execute(text("""
        SELECT e.id, e.exam_title, e.exam_type, e.assessment_type, e.exam_date, e.counts_for_clo, e.parent_exam_id,
               cs.id AS class_section_id, cs.section_code, s.name AS semester, s.academic_year,
               (SELECT COUNT(*) FROM exam_attempts a WHERE a.exam_id=e.id AND a.status='finished') AS n_students
        FROM exams e JOIN class_sections cs ON cs.id=e.class_section_id JOIN semesters s ON s.id=cs.semester_id
        WHERE cs.course_id=:c AND e.status='Analyzed' AND (:l IS NULL OR cs.lecturer_id=:l)
        ORDER BY s.academic_year DESC, s.term DESC, cs.section_code, e.id"""), {"c": course_id, "l": lid}).mappings()]


def _combine(db: Session, u: User, ids: list[int], mode: str) -> dict:
    for i in ids:
        get_exam_for(db, u, i)
    try:
        return combine.combined(db, ids, mode)
    except ValueError as ex:
        raise HTTPException(422, str(ex))


@router.post("/combined-analysis")
def combined(body: CombineIn, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    return _combine(db, u, body.exam_ids, body.mode)


@router.get("/combined-analysis.xlsx")
def combined_xlsx(ids: str, mode: Literal["merge", "cumulative"] = "merge", u: User = Depends(require("admin", "lecturer")),
                  db: Session = Depends(get_db)):
    exam_ids = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    if not exam_ids:
        raise HTTPException(422, "Chọn ít nhất một bài kiểm tra")
    d = _combine(db, u, exam_ids, mode)
    code = db.execute(text("SELECT course_code FROM courses WHERE id=:c"), {"c": d["course_id"]}).scalar()
    return Response(combine.combined_xlsx(d, f"Đánh giá CĐR gộp {len(exam_ids)} bài kiểm tra – môn {code}"), media_type=XLSX,
                    headers=attachment(f"DanhGiaGop_{code}.xlsx"))
