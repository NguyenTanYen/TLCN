"""Rubric chấm điểm theo tiêu chí: mỗi tiêu chí gắn một CLO, mỗi mức quy ra % điểm tối đa của tiêu chí.
Bài chấm theo rubric là bài "nhập điểm": mỗi tiêu chí là một câu/ý, điểm = điểm tối đa × % của mức đã chọn,
nên toàn bộ phân tích CLO/PI/PLO dùng lại nguyên vẹn."""
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import check_course_access, check_section_access, get_exam_for, lecturer_only, require
from ..models import Exam, User
from ..services import manual, results

router = APIRouter(prefix="/api", tags=["Rubric"])


class LevelIn(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    descriptor: Optional[str] = Field(default=None, max_length=1000)
    score_pct: float = Field(ge=0, le=100)


class CriterionIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    points: float = Field(gt=0, le=100)
    clo_id: int
    levels: list[LevelIn] = Field(min_length=2, max_length=6)


class RubricIn(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    description: Optional[str] = Field(default=None, max_length=1000)
    criteria: list[CriterionIn] = Field(min_length=1, max_length=20)


class RubricExamIn(BaseModel):
    rubric_id: int
    exam_title: str = Field(min_length=3, max_length=255)
    assessment_type: Literal["process", "final"] = "process"
    exam_date: Optional[date] = None
    max_score: float = Field(default=10, gt=0, le=999)
    counts_for_clo: bool = True


class RubricRow(BaseModel):
    student_id: int
    absent: bool = False
    levels: dict[int, Optional[int]] = {}


class RubricGradesIn(BaseModel):
    rows: list[RubricRow]
    analyze: bool = False


def _rows(db, sql, **p):
    return [dict(r) for r in db.execute(text(sql), p).mappings()]


def _validate(db: Session, course_id: int, body: RubricIn) -> None:
    clo_ids = {r[0] for r in db.execute(text("SELECT id FROM clos WHERE course_id=:c"), {"c": course_id})}
    for i, c in enumerate(body.criteria, 1):
        if c.clo_id not in clo_ids:
            raise HTTPException(422, f"Tiêu chí {i} (\"{c.name}\"): CLO không thuộc môn học")
        pcts = [round(l.score_pct, 2) for l in c.levels]
        if len(set(pcts)) != len(pcts):
            raise HTTPException(422, f"Tiêu chí {i} (\"{c.name}\"): hai mức không được có cùng tỷ lệ điểm")
        if max(pcts) != 100:
            raise HTTPException(422, f"Tiêu chí {i} (\"{c.name}\"): phải có một mức đạt 100% điểm tối đa")
        if len({l.label.strip().lower() for l in c.levels}) != len(c.levels):
            raise HTTPException(422, f"Tiêu chí {i} (\"{c.name}\"): tên các mức không được trùng nhau")


def _write(db: Session, rid: int, body: RubricIn) -> None:
    for i, c in enumerate(body.criteria, 1):
        cid = db.execute(text("INSERT INTO rubric_criteria (rubric_id, order_no, name, points, clo_id) VALUES (:r,:o,:n,:p,:c)"),
                         {"r": rid, "o": i, "n": c.name.strip(), "p": c.points, "c": c.clo_id}).lastrowid
        for j, l in enumerate(sorted(c.levels, key=lambda x: -x.score_pct), 1):
            db.execute(text("INSERT INTO rubric_levels (criterion_id, order_no, label, descriptor, score_pct) VALUES (:c,:o,:l,:d,:s)"),
                       {"c": cid, "o": j, "l": l.label.strip(), "d": (l.descriptor or "").strip() or None, "s": l.score_pct})


def _load(db: Session, rid: int) -> dict:
    r = db.execute(text("SELECT * FROM rubrics WHERE id=:i"), {"i": rid}).mappings().first()
    if not r:
        raise HTTPException(404, "Không tìm thấy rubric")
    crit = _rows(db, """SELECT c.id, c.order_no, c.name, c.points, c.clo_id, k.clo_code FROM rubric_criteria c JOIN clos k ON k.id=c.clo_id
                        WHERE c.rubric_id=:r ORDER BY c.order_no""", r=rid)
    for c in crit:
        c["points"] = float(c["points"])
        c["levels"] = [{**l, "score_pct": float(l["score_pct"])} for l in _rows(
            db, "SELECT id, order_no, label, descriptor, score_pct FROM rubric_levels WHERE criterion_id=:c ORDER BY order_no", c=c["id"])]
    in_use = bool(db.execute(text("SELECT 1 FROM exam_rubrics WHERE rubric_id=:i"), {"i": rid}).scalar())
    return {"id": r["id"], "course_id": r["course_id"], "name": r["name"], "description": r["description"],
            "total_points": round(sum(c["points"] for c in crit), 2), "in_use": in_use, "criteria": crit}


@router.get("/courses/{course_id}/rubrics")
def list_rubrics(course_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    check_course_access(db, u, course_id)
    return _rows(db, """SELECT r.id, r.name, r.description, COUNT(c.id) AS n_criteria, COALESCE(SUM(c.points),0) AS total_points,
                               EXISTS(SELECT 1 FROM exam_rubrics e WHERE e.rubric_id=r.id) AS in_use
                        FROM rubrics r LEFT JOIN rubric_criteria c ON c.rubric_id=r.id WHERE r.course_id=:c GROUP BY r.id ORDER BY r.name""", c=course_id)


@router.post("/courses/{course_id}/rubrics", status_code=201)
def create_rubric(course_id: int, body: RubricIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    check_course_access(db, u, course_id)
    _validate(db, course_id, body)
    rid = db.execute(text("INSERT INTO rubrics (course_id, name, description, created_by) VALUES (:c,:n,:d,:u)"),
                     {"c": course_id, "n": body.name.strip(), "d": body.description, "u": u.id}).lastrowid
    _write(db, rid, body)
    db.commit()
    return {"id": rid}


@router.get("/rubrics/{rid}")
def get_rubric(rid: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    d = _load(db, rid)
    check_course_access(db, u, d["course_id"])
    return d


@router.put("/rubrics/{rid}")
def update_rubric(rid: int, body: RubricIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    d = _load(db, rid)
    check_course_access(db, u, d["course_id"])
    if d["in_use"]:
        raise HTTPException(409, "Rubric đã được dùng để chấm điểm nên không sửa được (sửa sẽ làm điểm cũ sai). Hãy nhân bản rồi sửa bản mới")
    _validate(db, d["course_id"], body)
    db.execute(text("UPDATE rubrics SET name=:n, description=:d WHERE id=:i"), {"n": body.name.strip(), "d": body.description, "i": rid})
    db.execute(text("DELETE FROM rubric_criteria WHERE rubric_id=:i"), {"i": rid})
    _write(db, rid, body)
    db.commit()
    return {"ok": True}


@router.post("/rubrics/{rid}/duplicate", status_code=201)
def duplicate_rubric(rid: int, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    d = _load(db, rid)
    check_course_access(db, u, d["course_id"])
    body = RubricIn(name=f"{d['name']} (bản sao)"[:150], description=d["description"],
                    criteria=[CriterionIn(name=c["name"], points=c["points"], clo_id=c["clo_id"],
                                          levels=[LevelIn(label=l["label"], descriptor=l["descriptor"], score_pct=l["score_pct"]) for l in c["levels"]])
                              for c in d["criteria"]])
    new = db.execute(text("INSERT INTO rubrics (course_id, name, description, created_by) VALUES (:c,:n,:d,:u)"),
                     {"c": d["course_id"], "n": body.name, "d": body.description, "u": u.id}).lastrowid
    _write(db, new, body)
    db.commit()
    return {"id": new}


@router.delete("/rubrics/{rid}")
def delete_rubric(rid: int, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    d = _load(db, rid)
    check_course_access(db, u, d["course_id"])
    if d["in_use"]:
        raise HTTPException(409, "Rubric đang được dùng ở một bài kiểm tra nên không xóa được")
    db.execute(text("DELETE FROM rubrics WHERE id=:i"), {"i": rid})
    db.commit()
    return {"ok": True}


@router.post("/class-sections/{cs_id}/rubric-exams", status_code=201)
def create_rubric_exam(cs_id: int, body: RubricExamIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    cs = check_section_access(db, u, cs_id)
    d = _load(db, body.rubric_id)
    if d["course_id"] != cs.course_id:
        raise HTTPException(422, "Rubric không thuộc môn học của lớp này")
    e = Exam(class_section_id=cs.id, exam_title=body.exam_title.strip(), assessment_type=body.assessment_type, exam_type="manual",
             exam_date=body.exam_date, max_score=body.max_score, counts_for_clo=body.counts_for_clo, status="Published", created_by=u.id)
    db.add(e); db.flush()
    items = [{"title": c["name"], "points": c["points"], "clos": [{"clo_id": c["clo_id"], "weight": 1}]} for c in d["criteria"]]
    try:
        manual.add_items(db, e, cs.course_id, items, u.id)
    except manual.GradeError as ex:
        db.rollback(); raise HTTPException(422, str(ex))
    db.flush()
    qs = [r["question_id"] for r in _rows(db, "SELECT question_id FROM exam_questions WHERE exam_id=:e ORDER BY order_index", e=e.id)]
    db.execute(text("INSERT INTO exam_rubrics (exam_id, rubric_id) VALUES (:e,:r)"), {"e": e.id, "r": d["id"]})
    for c, q in zip(d["criteria"], qs):
        db.execute(text("INSERT INTO exam_rubric_items (exam_id, criterion_id, question_id) VALUES (:e,:c,:q)"), {"e": e.id, "c": c["id"], "q": q})
    db.commit()
    return {"id": e.id}


def _rubric_exam(db: Session, u: User, exam_id: int) -> tuple[Exam, int]:
    e = get_exam_for(db, u, exam_id)
    rid = db.execute(text("SELECT rubric_id FROM exam_rubrics WHERE exam_id=:e"), {"e": exam_id}).scalar()
    if not rid:
        raise HTTPException(422, "Bài này không chấm theo rubric")
    return e, rid


@router.get("/exams/{exam_id}/rubric-grid")
def rubric_grid(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e, rid = _rubric_exam(db, u, exam_id)
    gb = manual.gradebook(db, e)
    chosen: dict[int, dict[int, int]] = {}
    for r in _rows(db, "SELECT student_id, criterion_id, level_id FROM rubric_grades WHERE exam_id=:e", e=exam_id):
        chosen.setdefault(r["student_id"], {})[r["criterion_id"]] = r["level_id"]
    studs = [{**s, "levels": {str(k): v for k, v in chosen.get(s["student_id"], {}).items()}} for s in gb["students"]]
    return {"exam_id": exam_id, "rubric": _load(db, rid), "students": studs, "max_score": gb["max_score"], "raw_max": gb["raw_max"]}


@router.put("/exams/{exam_id}/rubric-grades")
def put_rubric_grades(exam_id: int, body: RubricGradesIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    e, rid = _rubric_exam(db, u, exam_id)
    d = _load(db, rid)
    crit = {c["id"]: c for c in d["criteria"]}
    qmap = {r["criterion_id"]: r["question_id"] for r in _rows(db, "SELECT criterion_id, question_id FROM exam_rubric_items WHERE exam_id=:e", e=exam_id)}
    allowed = {r[0]: r[1] for r in db.execute(text("""SELECT s.id, s.student_code FROM students s JOIN enrollments en ON en.student_id=s.id
                                                       WHERE en.class_section_id=:cs"""), {"cs": e.class_section_id})}
    rows, picks = [], []
    for r in body.rows:
        if r.student_id not in allowed:
            raise HTTPException(422, "Có SV không thuộc lớp học phần")
        if r.absent:
            rows.append({"student_id": r.student_id, "absent": True, "scores": {}})
            continue
        sel = {int(k): v for k, v in r.levels.items() if v is not None}
        if not sel:
            rows.append({"student_id": r.student_id, "absent": False, "scores": {}})
            continue
        missing = [c["name"] for cid, c in crit.items() if cid not in sel]
        if missing:
            raise HTTPException(422, f"SV {allowed[r.student_id]} chưa được chấm tiêu chí: {', '.join(missing)}")
        scores = {}
        for cid, lid in sel.items():
            if cid not in crit:
                raise HTTPException(422, "Có tiêu chí không thuộc rubric của bài này")
            lv = next((l for l in crit[cid]["levels"] if l["id"] == lid), None)
            if not lv:
                raise HTTPException(422, f"Mức đạt không thuộc tiêu chí \"{crit[cid]['name']}\"")
            scores[qmap[cid]] = round(crit[cid]["points"] * lv["score_pct"] / 100, 2)
            picks.append((r.student_id, cid, lid))
        rows.append({"student_id": r.student_id, "absent": False, "scores": scores})
    try:
        res = manual.save_grades(db, e, rows)
    except manual.GradeError as ex:
        db.rollback(); raise HTTPException(422, str(ex))
    sids = [r["student_id"] for r in rows]
    if sids:
        db.execute(text("DELETE FROM rubric_grades WHERE exam_id=:e AND student_id IN :s").bindparams(
            __import__("sqlalchemy").bindparam("s", expanding=True)), {"e": exam_id, "s": sids})
    for sid, cid, lid in picks:
        db.execute(text("INSERT INTO rubric_grades (exam_id, student_id, criterion_id, level_id) VALUES (:e,:s,:c,:l)"),
                   {"e": exam_id, "s": sid, "c": cid, "l": lid})
    db.commit()
    if body.analyze:
        n = db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e AND status='finished'"), {"e": exam_id}).scalar()
        res["analysis"] = results.analyze_exam(db, exam_id) if n else None
    return res
