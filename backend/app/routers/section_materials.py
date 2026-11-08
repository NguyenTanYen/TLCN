"""Học liệu của lớp học phần (RAG): tệp trong khóa học Moodle của lớp."""
from dataclasses import asdict
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import check_section_access, lecturer_only, require
from ..models import SectionMaterial, User
from ..services.rag import index, moodle_files, publish, search, sync

router = APIRouter(prefix="/api/class-sections", tags=["Học liệu (RAG)"])


class MaterialPatchIn(BaseModel):
    material_type: Optional[Literal["slide", "reference"]] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)


class MoodlePickIn(BaseModel):
    cmid: int
    content_hash: str = Field(pattern=r"^[0-9a-f]{40}$")
    material_type: Literal["slide", "reference"] = "slide"
    title: Optional[str] = Field(default=None, max_length=255)


class CopyMaterialIn(BaseModel):
    class_section_ids: list[int] = Field(min_length=1, max_length=30)


def _targets(db: Session, u: User, cs_id: int, ids: list[int]):
    """Các lớp nhận học liệu: cùng môn với lớp nguồn, GV phụ trách (không kể lớp nguồn)."""
    src = check_section_access(db, u, cs_id)
    out = []
    for i in dict.fromkeys(ids):
        if i == cs_id:
            continue
        cs = check_section_access(db, u, i)
        if cs.course_id != src.course_id:
            raise HTTPException(422, f"Lớp {cs.section_code} không cùng môn học")
        out.append(cs)
    return src, out


def _run(db: Session, targets, fn) -> list[dict]:
    res = []
    for cs in targets:
        r = {"class_section_id": cs.id, "section_code": cs.section_code, "ok": False, "message": "", "material_id": None}
        try:
            out = fn(cs)
            r.update(ok=True, message=out["note"], material_id=out["material_id"])
        except publish.PublishError as ex:
            db.rollback()
            r["message"] = str(ex)
        res.append(r)
    return res


def _material(m: SectionMaterial) -> dict:
    return {"id": m.id, "source": m.source, "material_type": m.material_type, "title": m.title,
            "title_custom": bool(m.title_custom), "file_name": m.file_name,
            "content_hash": m.content_hash, "file_size": m.file_size, "moodle_cmid": m.moodle_cmid,
            "moodle_file_url": m.moodle_file_url, "status": m.status, "error": m.error, "n_pages": m.n_pages,
            "created_at": m.created_at, "indexed_at": m.indexed_at}


@router.get("/{cs_id}/materials")
def list_materials(cs_id: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    """Tệp trong khóa học Moodle của lớp (kèm học liệu tương ứng nếu có) + toàn bộ học liệu của lớp."""
    cs = check_section_access(db, u, cs_id)
    chosen = db.query(SectionMaterial).filter_by(class_section_id=cs_id).order_by(SectionMaterial.id).all()
    by_hash = {m.content_hash: m for m in chosen}
    files = moodle_files.list_course_files(db, int(cs.moodle_course_id)) if cs.moodle_course_id else []
    return {"moodle_course_id": cs.moodle_course_id,
            "moodle_files": [{**f, "material_id": by_hash[f["content_hash"]].id if f["content_hash"] in by_hash else None,
                              "material_status": by_hash[f["content_hash"]].status if f["content_hash"] in by_hash else None}
                             for f in files],
            "materials": [_material(m) for m in chosen]}


@router.get("/{cs_id}/materials/search")
def search_materials(cs_id: int, q: str = Query(min_length=1, max_length=2000), k: int = Query(10, ge=1, le=50),
                     db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    """Tìm đoạn trong học liệu đã nạp của lớp (BM25) – để GV / Bộ môn thử truy vấn, dựng bộ câu hỏi chuẩn."""
    check_section_access(db, u, cs_id)
    from ..config import settings
    return [asdict(h) for h in search.search(db, cs_id, q, k, floor=settings.rag_search_similarity)]


@router.get("/{cs_id}/materials/semantic-info")
def semantic_info(cs_id: int, q: str = Query("", max_length=2000), db: Session = Depends(get_db),
                  u: User = Depends(require("admin", "lecturer"))):
    """Chẩn đoán tìm theo nghĩa của lớp: bật chưa, số đoạn có vector, độ gần nghĩa cao nhất với câu q, các ngưỡng."""
    from ..services.rag import semantic
    check_section_access(db, u, cs_id)
    return semantic.dense_info(db, cs_id, q)


@router.post("/{cs_id}/materials/sync")
def sync_materials(cs_id: int, db: Session = Depends(get_db), u: User = Depends(lecturer_only)):
    """Đồng bộ học liệu từ khóa học Moodle của lớp (giao diện gọi khi GV mở trang học liệu), rồi nạp ở nền các tệp chờ."""
    cs = check_section_access(db, u, cs_id)
    if not cs.moodle_course_id:
        raise HTTPException(409, "Lớp học phần chưa gắn với khóa học Moodle")
    out = sync.sync_section(db, cs, u.id)
    index.enqueue(cs_id)
    return out


@router.post("/{cs_id}/materials/moodle", status_code=201)
def pick_moodle_file(cs_id: int, body: MoodlePickIn, db: Session = Depends(get_db), u: User = Depends(lecturer_only)):
    """Chọn (hoặc chọn LẠI tệp đã bỏ chọn) một tệp của khóa học Moodle làm học liệu."""
    cs = check_section_access(db, u, cs_id)
    if not cs.moodle_course_id:
        raise HTTPException(409, "Lớp học phần chưa gắn với khóa học Moodle")
    f = next((f for f in moodle_files.list_course_files(db, int(cs.moodle_course_id))
              if f["cmid"] == body.cmid and f["content_hash"] == body.content_hash), None)
    if not f:
        raise HTTPException(404, "Không tìm thấy tệp trong khóa học Moodle của lớp (hoặc tệp đang ẩn / giới hạn truy cập)")
    if not f["supported"]:
        raise HTTPException(422, "Hiện mới nạp được tệp PDF – hãy xuất PowerPoint/Word sang PDF rồi tải lên Moodle")
    m = db.query(SectionMaterial).filter_by(class_section_id=cs_id, content_hash=f["content_hash"]).first()
    if m and m.status != "excluded":
        raise HTTPException(409, "Tệp này đã là học liệu của lớp")
    if m:
        m.status, m.material_type, m.error = "pending", body.material_type, None
        if body.title:
            m.title, m.title_custom = body.title.strip()[:255], True
    else:
        m = sync.new_material(cs_id, f, body.material_type, body.title, u.id)
        db.add(m)
    db.commit()
    db.refresh(m)
    index.enqueue(cs_id)
    return _material(m)


@router.post("/{cs_id}/materials/{material_id}/reindex")
def reindex_material(cs_id: int, material_id: int, db: Session = Depends(get_db), u: User = Depends(lecturer_only)):
    """Nạp lại học liệu đã nạp hoặc bị lỗi (GV sửa xong tệp, hoặc bộ đọc PDF được cải tiến)."""
    check_section_access(db, u, cs_id)
    m = db.get(SectionMaterial, material_id)
    if not m or m.class_section_id != cs_id:
        raise HTTPException(404, "Không tìm thấy học liệu của lớp học phần này")
    if m.source != "moodle" or m.status not in ("ready", "failed"):
        raise HTTPException(409, "Chỉ nạp lại được học liệu từ Moodle đã nạp xong hoặc bị lỗi")
    m.status, m.error = "pending", None
    db.commit()
    index.enqueue(cs_id)
    return _material(m)


@router.delete("/{cs_id}/materials/{material_id}")
def unpick_material(cs_id: int, material_id: int, db: Session = Depends(get_db), u: User = Depends(lecturer_only)):
    """Bỏ chọn học liệu."""
    check_section_access(db, u, cs_id)
    m = db.get(SectionMaterial, material_id)
    if not m or m.class_section_id != cs_id:
        raise HTTPException(404, "Không tìm thấy học liệu của lớp học phần này")
    if m.source != "moodle":
        db.delete(m)
        db.commit()
        return {"deleted": material_id}
    sync.delete_indexed(db, m.id)
    m.status, m.n_pages, m.indexed_at, m.error = "excluded", None, None, None
    db.commit()
    index.enqueue(cs_id)
    return {"excluded": material_id}


@router.patch("/{cs_id}/materials/{material_id}")
def update_material(cs_id: int, material_id: int, body: MaterialPatchIn, db: Session = Depends(get_db),
                    u: User = Depends(lecturer_only)):
    """GV sửa loại học liệu (slide / tài liệu tham khảo – mặc định chỉ đoán theo hoạt động Moodle) và tên hiển thị."""
    check_section_access(db, u, cs_id)
    if body.material_type is None and body.title is None:
        raise HTTPException(422, "Không có thông tin nào để sửa (material_type hoặc title)")
    m = db.get(SectionMaterial, material_id)
    if not m or m.class_section_id != cs_id:
        raise HTTPException(404, "Không tìm thấy học liệu của lớp học phần này")
    if body.material_type:
        m.material_type = body.material_type
    if body.title is not None:
        m.title, m.title_custom = body.title.strip()[:255], True
    db.commit()
    db.refresh(m)
    return _material(m)


@router.post("/{cs_id}/materials/upload")
async def upload_material(cs_id: int, file: UploadFile = File(...), title: str = Form(""),
                          material_type: Literal["slide", "reference"] = Form("slide"),
                          class_section_ids: str = Form(""), week: int = Form(0),
                          db: Session = Depends(get_db), u: User = Depends(lecturer_only)):
    """GV tải PDF học liệu lên hệ thống và chọn các lớp cùng môn (kể cả lớp này) sẽ nhận: tệp được đăng lên khóa Moodle của từng lớp, đồng bộ thành học liệu và nạp ở nền."""
    ids = [int(x) for x in class_section_ids.replace(" ", "").split(",") if x.isdigit()]
    src, others = _targets(db, u, cs_id, ids)
    targets = [src] + others
    data = await file.read(index.MAX_BYTES + 1)
    name = (file.filename or "hoc_lieu.pdf").replace("\\", "/").rsplit("/", 1)[-1]
    try:
        publish.check_pdf(data)
    except publish.PublishError as ex:
        raise HTTPException(422, str(ex))
    ttl = (title.strip() or name.rsplit(".", 1)[0])[:255]
    return {"results": _run(db, targets, lambda cs: publish.push_to_class(db, cs, data, name, ttl, material_type, max(0, week), u.id))}


@router.post("/{cs_id}/materials/{material_id}/copy")
def copy_material(cs_id: int, material_id: int, body: CopyMaterialIn, db: Session = Depends(get_db),
                  u: User = Depends(lecturer_only)):
    """Dùng một học liệu của lớp này cho các lớp khác cùng môn (đăng tệp lên khóa Moodle của từng lớp)."""
    _, targets = _targets(db, u, cs_id, body.class_section_ids)
    m = db.get(SectionMaterial, material_id)
    if not m or m.class_section_id != cs_id or m.status in ("excluded", "missing") or m.source != "moodle":
        raise HTTPException(404, "Không tìm thấy học liệu đang dùng của lớp này")
    try:
        data = publish.fetch_bytes(m)
    except publish.PublishError as ex:
        raise HTTPException(422, str(ex))
    name, title, mtype = m.file_name, m.title, m.material_type
    return {"results": _run(db, targets, lambda cs: publish.push_to_class(db, cs, data, name, title, mtype, 0, u.id))}


@router.post("/{cs_id}/materials/copy-from/{src_id}")
def copy_from_section(cs_id: int, src_id: int, db: Session = Depends(get_db), u: User = Depends(lecturer_only)):
    """Lớp mới: sao chép TOÀN BỘ học liệu đang dùng của một lớp cùng môn (vd học kỳ trước) sang lớp này."""
    dst, srcs = _targets(db, u, cs_id, [src_id])
    if not srcs:
        raise HTTPException(422, "Chọn một lớp khác để sao chép học liệu")
    items = db.query(SectionMaterial).filter(SectionMaterial.class_section_id == src_id, SectionMaterial.source == "moodle",
                                             SectionMaterial.status.in_(("ready", "pending", "indexing"))).all()
    if not items:
        raise HTTPException(404, "Lớp nguồn chưa có học liệu nào đang dùng")
    res = []
    for m in items:
        r = {"title": m.title, "ok": False, "message": ""}
        try:
            data = publish.fetch_bytes(m)
            out = publish.push_to_class(db, dst, data, m.file_name, m.title, m.material_type, 0, u.id)
            r.update(ok=True, message=out["note"])
        except publish.PublishError as ex:
            db.rollback()
            r["message"] = str(ex)
        res.append(r)
    return {"results": res}
