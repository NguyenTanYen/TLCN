"""Đề cương chi tiết học phần có phiên bản (góp ý F1): Bộ môn soạn bản nháp, kiểm tra rồi duyệt; GV chỉ xem.

Mỗi môn có nhiều phiên bản (course_syllabi.version_no): đúng một bản `approved` đang áp dụng, bản cũ chuyển `archived`.
Bản đã duyệt không sửa trực tiếp – tạo phiên bản mới (chép nội dung bản mới nhất) rồi sửa bản nháp đó.
Thông tin chung (tên, mã, tín chỉ, cấu trúc, tiên quyết, mô tả vắn tắt), chương và CLO dùng chung cho mọi phiên bản.
"""
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require
from ..models import CLO, Course, CourseSyllabus, SyllabusAssessment, SyllabusReference, User

router = APIRouter(prefix="/api", tags=["Đề cương chi tiết"])

STATUS_VI = {"draft": "Bản nháp", "approved": "Đang áp dụng", "archived": "Đã thay thế"}
COPY_FIELDS = ("english_name", "self_study_hours", "objectives", "teaching_methods", "course_policy", "effective_semester_id")


class ReferenceIn(BaseModel):
    ref_type: Literal["main", "extra"] = "main"
    citation: str = Field(min_length=3)


class AssessmentIn(BaseModel):
    component_code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=2, max_length=255)
    method: Optional[str] = Field(default=None, max_length=150)
    timing: Optional[str] = Field(default=None, max_length=100)
    weight_pct: float = Field(gt=0, le=100)
    clo_ids: list[int] = []


class SyllabusIn(BaseModel):
    """Chỉ các trường gửi lên mới được ghi; references / assessments gửi lên thì thay toàn bộ danh sách."""
    english_name: Optional[str] = Field(default=None, max_length=255)
    self_study_hours: Optional[int] = Field(default=None, ge=0, le=1000)
    objectives: Optional[str] = None
    teaching_methods: Optional[str] = None
    course_policy: Optional[str] = None
    effective_semester_id: Optional[int] = None
    references: Optional[list[ReferenceIn]] = None
    assessments: Optional[list[AssessmentIn]] = None


def _course(db: Session, cid: int) -> Course:
    c = db.get(Course, cid)
    if not c:
        raise HTTPException(404, "Không tìm thấy học phần")
    return c


def latest(c: Course) -> Optional[CourseSyllabus]:
    return c.syllabi[-1] if c.syllabi else None


def pick_version(c: Course, version: Optional[int], is_admin: bool) -> Optional[CourseSyllabus]:
    """Phiên bản để xem: theo yêu cầu; mặc định Bộ môn xem bản mới nhất, GV xem bản đang áp dụng (chưa duyệt thì bản mới nhất)."""
    if version is not None:
        s = next((x for x in c.syllabi if x.version_no == version), None)
        if not s:
            raise HTTPException(404, f"Không có đề cương phiên bản {version}")
        return s
    if is_admin:
        return latest(c)
    return next((x for x in reversed(c.syllabi) if x.status == "approved"), None) or latest(c)


def checks(db: Session, c: Course, s: Optional[CourseSyllabus]) -> list[dict]:
    """Bảng kiểm tra trước khi duyệt đề cương: mục `required` chưa đạt thì không duyệt được."""
    clos = c.clos
    assessed = {cl.id for a in (s.assessments if s else []) for cl in a.clos}
    taught = {cl.id for o in c.outlines for cl in o.clos}
    weight = sum(float(a.weight_pct) for a in (s.assessments if s else []))
    no_pi = [cl.clo_code for cl in clos if not cl.pi_links]
    not_assessed = [cl.clo_code for cl in clos if cl.id not in assessed]
    not_taught = [cl.clo_code for cl in clos if cl.id not in taught]
    covered = {l.pi_id for cl in clos for l in cl.pi_links}
    missing = [f"{r['program_code']} {r['pi_code']}" for r in db.execute(text(
        """SELECT p.code AS program_code, i.id, i.pi_code FROM pi_courses pc JOIN performance_indicators i ON i.id=pc.pi_id
           JOIN plos l ON l.id=i.plo_id JOIN programs p ON p.id=l.program_id WHERE pc.course_id=:c
           ORDER BY p.code, LENGTH(i.pi_code), i.pi_code"""), {"c": c.id}).mappings() if r["id"] not in covered]
    return [
        {"key": "general", "label": "Mô tả vắn tắt và mục tiêu học phần", "required": True,
         "ok": bool((c.description or "").strip() and s and (s.objectives or "").strip())},
        {"key": "clos", "label": "Có CLO và mọi CLO đã gắn PI của CTĐT", "required": True,
         "ok": bool(clos) and not no_pi, "detail": f"Chưa gắn PI: {', '.join(no_pi)}" if no_pi else f"{len(clos)} CLO"},
        {"key": "chapters", "label": "Nội dung các chương", "required": True, "ok": bool(c.outlines),
         "detail": f"{len(c.outlines)} chương" + (f"; CLO chưa thuộc chương nào: {', '.join(not_taught)}" if not_taught else "")},
        {"key": "weights", "label": "Tổng tỷ trọng đánh giá = 100%", "required": True, "ok": abs(weight - 100) < 0.01,
         "detail": f"Hiện tại {weight:g}%"},
        {"key": "assessed", "label": "Mọi CLO được đánh giá ở ít nhất một thành phần", "required": True,
         "ok": bool(clos) and not not_assessed, "detail": f"Chưa đánh giá: {', '.join(not_assessed)}" if not_assessed else None},
        {"key": "references", "label": "Có giáo trình chính", "required": False,
         "ok": bool(s and any(r.ref_type == "main" for r in s.references))},
        {"key": "ctdt", "label": "CLO đáp ứng đủ các PI mà CTĐT giao cho học phần (Phụ lục II)", "required": False,
         "ok": not missing, "detail": f"Chưa có CLO cho: {', '.join(missing)}" if missing else None},
    ]


def doc(db: Session, c: Course, s: Optional[CourseSyllabus]) -> dict:
    """Phần đề cương theo phiên bản, ghép vào GET /api/courses/{cid}/syllabus."""
    approved = next((x for x in reversed(c.syllabi) if x.status == "approved"), None)
    sem = db.execute(text("SELECT name FROM semesters WHERE id=:s"), {"s": s.effective_semester_id}).scalar() if s and s.effective_semester_id else None
    return {
        "doc": None if not s else {
            "id": s.id, "version_no": s.version_no, "status": s.status, "status_label": STATUS_VI[s.status],
            "english_name": s.english_name, "self_study_hours": s.self_study_hours, "objectives": s.objectives,
            "teaching_methods": s.teaching_methods, "course_policy": s.course_policy,
            "effective_semester_id": s.effective_semester_id, "effective_semester": sem,
            "approved_at": s.approved_at.isoformat() if s.approved_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            "references": [{"id": r.id, "ref_type": r.ref_type, "citation": r.citation} for r in s.references],
            "assessments": [{"id": a.id, "component_code": a.component_code, "name": a.name, "method": a.method, "timing": a.timing,
                             "weight_pct": float(a.weight_pct), "clos": [{"id": x.id, "clo_code": x.clo_code} for x in a.clos]}
                            for a in s.assessments],
            "is_latest": s is latest(c),
        },
        "approved_version": approved.version_no if approved else None,
        "versions": [{"version_no": x.version_no, "status": x.status, "status_label": STATUS_VI[x.status],
                      "approved_at": x.approved_at.isoformat() if x.approved_at else None} for x in c.syllabi],
        "checks": checks(db, c, latest(c)),
    }


def outlines(db: Session, cid: int) -> list[dict]:
    """Các chương của môn kèm nội dung, số tiết, hoạt động dạy học và CLO của chương."""
    out = [dict(r) for r in db.execute(text("SELECT * FROM course_outlines WHERE course_id=:c ORDER BY chapter_number"), {"c": cid}).mappings()]
    links = db.execute(text("""SELECT oc.outline_id, c.id, c.clo_code FROM outline_clos oc JOIN clos c ON c.id=oc.clo_id
                               JOIN course_outlines o ON o.id=oc.outline_id WHERE o.course_id=:c ORDER BY c.clo_code"""), {"c": cid}).all()
    for o in out:
        o["clos"] = [{"id": i, "clo_code": code} for oid, i, code in links if oid == o["id"]]
    return out


def _clos_of(db: Session, cid: int, ids: list[int]) -> list[CLO]:
    if not ids:
        return []
    clos = db.query(CLO).filter(CLO.id.in_(set(ids))).all()
    if len(clos) != len(set(ids)) or any(x.course_id != cid for x in clos):
        raise HTTPException(422, "CLO không thuộc học phần này")
    return clos


def _replace_children(db: Session, s: CourseSyllabus, cid: int, body: SyllabusIn) -> None:
    if body.references is not None:
        s.references.clear()
        db.flush()
        order = {"main": 0, "extra": 0}
        for r in body.references:
            order[r.ref_type] += 1
            s.references.append(SyllabusReference(ref_type=r.ref_type, citation=r.citation.strip(), sort_order=order[r.ref_type]))
    if body.assessments is not None:
        codes = [a.component_code.strip().upper() for a in body.assessments]
        if len(codes) != len(set(codes)):
            raise HTTPException(422, "Mã thành phần đánh giá bị trùng")
        s.assessments.clear()
        db.flush()
        for i, a in enumerate(body.assessments, 1):
            s.assessments.append(SyllabusAssessment(
                component_code=a.component_code.strip().upper(), name=a.name.strip(), method=(a.method or "").strip() or None,
                timing=(a.timing or "").strip() or None, weight_pct=a.weight_pct, sort_order=i, clos=_clos_of(db, cid, a.clo_ids)))


@router.put("/courses/{cid}/syllabus")
def save_syllabus(cid: int, body: SyllabusIn, db: Session = Depends(get_db), u: User = Depends(require("admin"))):
    """Lưu bản nháp mới nhất (chưa có thì tạo phiên bản 1). Bản đã duyệt phải tạo phiên bản mới để sửa."""
    c = _course(db, cid)
    s = latest(c)
    if s and s.status != "draft":
        raise HTTPException(409, f"Đề cương phiên bản {s.version_no} đã duyệt – tạo phiên bản mới để chỉnh sửa")
    if body.effective_semester_id and not db.execute(text("SELECT 1 FROM semesters WHERE id=:s"), {"s": body.effective_semester_id}).scalar():
        raise HTTPException(422, "Học kỳ áp dụng không tồn tại")
    if not s:
        s = CourseSyllabus(course_id=cid, version_no=1, status="draft")
        c.syllabi.append(s)
    for k, v in body.model_dump(exclude={"references", "assessments"}, exclude_unset=True).items():
        setattr(s, k, (v.strip() or None) if isinstance(v, str) else v)
    s.updated_by = u.id
    _replace_children(db, s, cid, body)
    db.commit()
    return {"version_no": s.version_no, "status": s.status}


@router.post("/courses/{cid}/syllabus/versions", status_code=201)
def new_version(cid: int, db: Session = Depends(get_db), u: User = Depends(require("admin"))):
    """Tạo bản nháp phiên bản mới, chép nội dung từ phiên bản mới nhất."""
    c = _course(db, cid)
    old = latest(c)
    if old and old.status == "draft":
        raise HTTPException(409, f"Đang có bản nháp phiên bản {old.version_no}")
    s = CourseSyllabus(course_id=cid, version_no=(old.version_no + 1) if old else 1, status="draft", updated_by=u.id)
    if old:
        for k in COPY_FIELDS:
            setattr(s, k, getattr(old, k))
        s.references = [SyllabusReference(ref_type=r.ref_type, citation=r.citation, sort_order=r.sort_order) for r in old.references]
        s.assessments = [SyllabusAssessment(component_code=a.component_code, name=a.name, method=a.method, timing=a.timing,
                                            weight_pct=a.weight_pct, sort_order=a.sort_order, clos=list(a.clos)) for a in old.assessments]
    c.syllabi.append(s)
    db.commit()
    return {"version_no": s.version_no, "status": s.status}


@router.post("/courses/{cid}/syllabus/approve")
def approve(cid: int, db: Session = Depends(get_db), u: User = Depends(require("admin"))):
    """Duyệt bản nháp mới nhất khi đạt mọi mục bắt buộc; bản đang áp dụng trước đó chuyển sang 'Đã thay thế'."""
    c = _course(db, cid)
    s = latest(c)
    if not s or s.status != "draft":
        raise HTTPException(409, "Không có bản nháp đề cương để duyệt")
    failed = [k["label"] + (f" ({k['detail']})" if k.get("detail") else "") for k in checks(db, c, s) if k["required"] and not k["ok"]]
    if failed:
        raise HTTPException(422, "Chưa duyệt được đề cương: " + "; ".join(failed))
    for old in c.syllabi:
        if old.status == "approved":
            old.status = "archived"
    s.status, s.approved_by, s.approved_at = "approved", u.id, datetime.now()
    db.commit()
    return {"version_no": s.version_no, "status": s.status}
