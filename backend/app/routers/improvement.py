"""Vòng cải tiến (closing the loop): hành động cải tiến có người phụ trách, hạn, trạng thái và kết quả kiểm chứng;
so sánh kết quả CLO của một học phần qua các học kỳ."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import check_course_access, check_section_access, require
from ..models import User

router = APIRouter(prefix="/api", tags=["Vòng cải tiến"])
STATUS = ("open", "doing", "done", "verified")


class ActionIn(BaseModel):
    description: str = Field(min_length=3, max_length=2000)
    clo_id: Optional[int] = None
    owner: Optional[str] = Field(default=None, max_length=150)
    due_date: Optional[date] = None
    status: str = "open"
    result: Optional[str] = Field(default=None, max_length=2000)


class ActionPatch(BaseModel):
    description: Optional[str] = Field(default=None, min_length=3, max_length=2000)
    clo_id: Optional[int] = None
    owner: Optional[str] = Field(default=None, max_length=150)
    due_date: Optional[date] = None
    status: Optional[str] = None
    result: Optional[str] = Field(default=None, max_length=2000)


def _rows(db, sql, **p):
    return [dict(r) for r in db.execute(text(sql), p).mappings()]


def _check_status(v):
    if v is not None and v not in STATUS:
        raise HTTPException(422, "Trạng thái phải là open, doing, done hoặc verified")


def _check_clo(db, cs, clo_id):
    if clo_id is not None and not db.execute(text("SELECT 1 FROM clos WHERE id=:c AND course_id=:k"), {"c": clo_id, "k": cs.course_id}).scalar():
        raise HTTPException(422, "CLO không thuộc học phần của lớp này")


def _serialize(r):
    r = dict(r)
    r["overdue"] = bool(r.get("due_date") and r["status"] in ("open", "doing") and r["due_date"] < date.today())
    for k in ("due_date", "created_at", "updated_at"):
        if r.get(k) is not None:
            r[k] = r[k].isoformat()
    return r


@router.get("/class-sections/{cs_id}/improvement-actions")
def list_actions(cs_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    check_section_access(db, u, cs_id)
    return [_serialize(r) for r in _rows(db, """SELECT a.*, c.clo_code FROM improvement_actions a LEFT JOIN clos c ON c.id=a.clo_id
                                                WHERE a.class_section_id=:cs ORDER BY a.id""", cs=cs_id)]


@router.post("/class-sections/{cs_id}/improvement-actions", status_code=201)
def add_action(cs_id: int, body: ActionIn, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    cs = check_section_access(db, u, cs_id)
    _check_status(body.status)
    _check_clo(db, cs, body.clo_id)
    r = db.execute(text("""INSERT INTO improvement_actions (class_section_id, clo_id, description, owner, due_date, status, result)
                           VALUES (:cs,:clo,:d,:o,:due,:st,:res)"""),
                   {"cs": cs_id, "clo": body.clo_id, "d": body.description.strip(), "o": body.owner, "due": body.due_date, "st": body.status, "res": body.result})
    db.commit()
    return {"id": r.lastrowid}


def _action(db, u, aid):
    a = db.execute(text("SELECT * FROM improvement_actions WHERE id=:i"), {"i": aid}).mappings().first()
    if not a:
        raise HTTPException(404, "Không tìm thấy hành động cải tiến")
    return check_section_access(db, u, a["class_section_id"]), dict(a)


@router.patch("/improvement-actions/{aid}")
def patch_action(aid: int, body: ActionPatch, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    cs, a = _action(db, u, aid)
    data = body.model_dump(exclude_unset=True)
    _check_status(data.get("status"))
    if "clo_id" in data:
        _check_clo(db, cs, data["clo_id"])
    if "description" in data and data["description"]:
        data["description"] = data["description"].strip()
    if data.get("status") == "verified" and not (data.get("result") or a.get("result")):
        raise HTTPException(422, "Đánh dấu 'Đã kiểm chứng' cần ghi kết quả kiểm chứng")
    if data:
        sets = ", ".join(f"{k}=:{k}" for k in data)
        db.execute(text(f"UPDATE improvement_actions SET {sets} WHERE id=:id"), {**data, "id": aid})
        db.commit()
    return {"ok": True}


@router.delete("/improvement-actions/{aid}")
def delete_action(aid: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    _action(db, u, aid)
    db.execute(text("DELETE FROM improvement_actions WHERE id=:i"), {"i": aid})
    db.commit()
    return {"ok": True}


@router.get("/courses/{course_id}/clo-trend")
def clo_trend(course_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """Tỷ lệ SV đạt từng CLO của học phần qua các học kỳ (gộp các lớp HP cùng học kỳ), kèm chỉ tiêu và hành động cải tiến."""
    check_course_access(db, u, course_id)
    data = _rows(db, """SELECT s.id AS semester_id, s.name AS semester, s.start_date, c.id AS clo_id, c.clo_code,
                               SUM(r.n_evaluated) AS n_evaluated, SUM(r.n_achieved) AS n_achieved, MAX(r.target_pct) AS target_pct
                        FROM clo_results r JOIN class_sections cs ON cs.id=r.class_section_id JOIN semesters s ON s.id=cs.semester_id
                        JOIN clos c ON c.id=r.clo_id WHERE cs.course_id=:k
                        GROUP BY s.id, s.name, s.start_date, c.id, c.clo_code ORDER BY s.start_date, c.clo_code""", k=course_id)
    sems, clos = {}, {}
    for d in data:
        sems.setdefault(d["semester_id"], {"semester_id": d["semester_id"], "semester": d["semester"], "start": d["start_date"]})
        n, ok = int(d["n_evaluated"]), int(d["n_achieved"])
        pct = round(100 * ok / n, 2) if n else None
        c = clos.setdefault(d["clo_id"], {"clo_id": d["clo_id"], "clo_code": d["clo_code"], "points": []})
        c["points"].append({"semester_id": d["semester_id"], "semester": d["semester"], "n_evaluated": n, "n_achieved": ok, "achieved_pct": pct,
                            "target_pct": float(d["target_pct"]), "is_achieved": pct is not None and pct + 1e-9 >= float(d["target_pct"])})
    for c in clos.values():
        pts = c["points"]
        c["change"] = round(pts[-1]["achieved_pct"] - pts[-2]["achieved_pct"], 2) if len(pts) >= 2 else None
        c["trend"] = None if c["change"] is None else ("up" if c["change"] > 0.5 else "down" if c["change"] < -0.5 else "flat")
    acts = [_serialize(r) for r in _rows(db, """SELECT a.*, c.clo_code, s.name AS semester FROM improvement_actions a
                                                JOIN class_sections cs ON cs.id=a.class_section_id JOIN semesters s ON s.id=cs.semester_id
                                                LEFT JOIN clos c ON c.id=a.clo_id WHERE cs.course_id=:k ORDER BY s.start_date, a.id""", k=course_id)]
    return {"course_id": course_id, "semesters": [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in s.items()} for s in sems.values()],
            "clos": list(clos.values()), "actions": acts}
