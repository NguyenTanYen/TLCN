"""Học liệu của lớp học phần (RAG): tệp trong khóa học Moodle của lớp.

TỰ ĐỘNG: đồng bộ lấy mọi tệp PDF sinh viên đang xem được (không ẩn, không giới hạn truy cập) làm học liệu – tệp SV đã
xem được thì gợi ý trỏ tới nó không làm lộ gì thêm; đề thi trên Moodle là Quiz / Offline Quiz, không phải tệp. GV chỉ
cần BỎ CHỌN tệp không muốn dùng (đồng bộ sau không lấy lại) hoặc chọn lại. Tệp mới ở trạng thái 'pending' (chờ tải và
nạp). Giao diện gọi đồng bộ khi GV mở trang học liệu; sau đó các tệp chờ được xếp vào HÀNG ĐỢI của luồng nạp riêng
(services/rag/index) –
GV xem trạng thái từng tệp (đang nạp / đã nạp / lỗi). Ngoài ra hệ thống tự đồng bộ + nạp định kỳ (RAG_SYNC_MINUTES).
Phân quyền: GV phụ trách lớp đồng bộ / chọn / bỏ chọn / nạp lại; Bộ môn chỉ xem.
"""
from dataclasses import asdict
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import check_section_access, lecturer_only, require
from ..models import SectionMaterial, User
from ..services.rag import index, moodle_files, search, sync

router = APIRouter(prefix="/api/class-sections", tags=["Học liệu (RAG)"])


class MaterialPatchIn(BaseModel):
    material_type: Optional[Literal["slide", "reference"]] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)


class MoodlePickIn(BaseModel):
    cmid: int
    content_hash: str = Field(pattern=r"^[0-9a-f]{40}$")
    material_type: Literal["slide", "reference"] = "slide"
    title: Optional[str] = Field(default=None, max_length=255)


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
    return [asdict(h) for h in search.search(db, cs_id, q, k)]


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
    """Chọn (hoặc chọn LẠI tệp đã bỏ chọn) một tệp của khóa học Moodle làm học liệu. Chỉ nhận tệp đang có – và SV đang
    xem được – trong khóa học của CHÍNH lớp này."""
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
    if m:                                            # chọn lại tệp đã bỏ chọn
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
    """Nạp lại học liệu đã nạp hoặc bị lỗi (GV sửa xong tệp, hoặc bộ đọc PDF được cải tiến). Trang / đoạn cũ giữ nguyên
    cho tới khi nạp xong bản mới."""
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
    """Bỏ chọn học liệu. Tệp từ Moodle: đánh dấu 'excluded' (đồng bộ sau không lấy lại) và xóa trang / đoạn đã nạp;
    tệp GV tải trực tiếp lên hệ thống: xóa hẳn."""
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
    index.enqueue(cs_id)                         # luồng nạp dựng lại chỉ mục tìm kiếm của lớp
    return {"excluded": material_id}


@router.patch("/{cs_id}/materials/{material_id}")
def update_material(cs_id: int, material_id: int, body: MaterialPatchIn, db: Session = Depends(get_db),
                    u: User = Depends(lecturer_only)):
    """GV sửa loại học liệu (slide / tài liệu tham khảo – mặc định chỉ đoán theo hoạt động Moodle) và tên hiển thị.
    Tên GV tự đặt được giữ nguyên qua các lần đồng bộ."""
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
