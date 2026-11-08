"""Đồng bộ học liệu của lớp học phần từ khóa học Moodle của lớp – TỰ ĐỘNG, GV không phải tick từng tệp."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ...models import ClassSection, MaterialPage, MaterialPassage, SectionMaterial
from . import moodle_files


def auto_title(f: dict) -> str:
    return ((f["activity"] if f["module"] == "resource" else f["file_name"]) or f["file_name"]).strip()[:255]


def new_material(cs_id: int, f: dict, material_type: str, title: str | None, user_id: int | None) -> SectionMaterial:
    return SectionMaterial(class_section_id=cs_id, source="moodle", material_type=material_type,
                           title=(title or auto_title(f)).strip()[:255], title_custom=bool(title),
                           file_name=f["file_name"], content_hash=f["content_hash"], file_size=f["file_size"],
                           moodle_cmid=f["cmid"], moodle_file_url=f["url"], moodle_timemodified=f["timemodified"],
                           added_by=user_id)


def delete_indexed(db: Session, material_id: int) -> None:
    """Xóa trang + đoạn đã nạp của một học liệu – xóa đoạn TƯỜNG MINH rồi mới xóa trang (như store.save_document), không phụ thuộc ràng buộc ON DELETE CASCADE của CSDL."""
    db.query(MaterialPassage).filter_by(material_id=material_id).delete()
    db.query(MaterialPage).filter_by(material_id=material_id).delete()


def _refresh(m: SectionMaterial, f: dict) -> bool:
    """Cập nhật thông tin đổi được mà nội dung không đổi (đổi tên tệp, đổi tên hoạt động, chuyển chỗ)."""
    new = {"file_name": f["file_name"], "moodle_file_url": f["url"], "moodle_timemodified": f["timemodified"],
           "moodle_cmid": f["cmid"]}
    if not m.title_custom:
        new["title"] = auto_title(f)
    changed = False
    for k, v in new.items():
        if getattr(m, k) != v:
            setattr(m, k, v)
            changed = True
    return changed


def sync_section(db: Session, cs: ClassSection, user_id: int | None = None) -> dict:
    out = {"added": [], "replaced": [], "missing": [], "restored": [], "updated": []}
    if not cs.moodle_course_id:
        return out
    files = [f for f in moodle_files.list_course_files(db, int(cs.moodle_course_id)) if f["supported"]]
    by_hash = {f["content_hash"]: f for f in files}
    resource_cmids = {f["cmid"] for f in files if f["module"] == "resource"}
    mine = db.query(SectionMaterial).filter_by(class_section_id=cs.id, source="moodle").all()
    have = {m.content_hash for m in mine}
    excluded_resources = {m.moodle_cmid for m in mine
                          if m.status == "excluded" and "/mod_resource/" in (m.moodle_file_url or "")}
    for m in mine:
        f = by_hash.get(m.content_hash)
        if f:
            if _refresh(m, f):
                out["updated"].append(m.file_name)
            if m.status == "missing":
                m.status = "ready" if m.n_pages else "pending"
                out["restored"].append(m.file_name)
        elif m.status == "excluded":
            continue
        elif m.moodle_cmid in resource_cmids:
            out["replaced"].append(m.file_name)
            delete_indexed(db, m.id)
            db.delete(m)
        elif m.status != "missing":
            m.status = "missing"
            out["missing"].append(m.file_name)
    for f in files:
        if f["content_hash"] in have:
            continue
        if f["module"] == "resource" and f["cmid"] in excluded_resources:
            continue
        db.add(new_material(cs.id, f, "slide" if f["module"] == "resource" else "reference", None, user_id))
        out["added"].append(f["file_name"])
    db.commit()
    return out
