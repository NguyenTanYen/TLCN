"""Đưa học liệu lên lớp học phần: GV tải PDF lên hệ thống (hoặc sao chép từ lớp khác cùng môn) → hệ thống ĐĂNG tệp lên
khóa học Moodle của từng lớp được chọn (plugin local_clo_add_resource) → đồng bộ lại để tệp thành học liệu → nạp ở nền.

Moodle luôn là nơi chứa tệp: SV mở đúng trang học liệu bằng phiên Moodle của mình, và việc tải lên bằng tay trên Moodle
(rồi bấm "Đồng bộ từ Moodle") vẫn dùng được song song.
"""
from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from ...models import ClassSection, SectionMaterial
from .. import lms
from . import index, sync


class PublishError(RuntimeError):
    pass


def check_pdf(data: bytes) -> None:
    if not data:
        raise PublishError("Tệp rỗng")
    if len(data) > index.MAX_BYTES:
        raise PublishError(f"Tệp quá lớn ({len(data) // 1048576} MB, tối đa {index.MAX_BYTES // 1048576} MB)")
    if data[:4] != b"%PDF":
        raise PublishError("Hiện chỉ nạp được tệp PDF – hãy xuất PowerPoint/Word sang PDF rồi tải lên")


def push_to_class(db: Session, cs: ClassSection, data: bytes, filename: str, title: str, material_type: str,
                  week: int, user_id: int | None) -> dict:
    """Đăng một PDF lên khóa Moodle của lớp rồi biến nó thành học liệu của lớp. Trả {material_id, created, note}."""
    if not cs.moodle_course_id:
        raise PublishError("Lớp chưa gắn khóa học Moodle")
    if not lms.configured():
        raise PublishError("Chưa cấu hình kết nối Moodle (MOODLE_URL, MOODLE_WS_TOKEN)")
    digest = hashlib.sha1(data).hexdigest()
    have = db.query(SectionMaterial).filter_by(class_section_id=cs.id, content_hash=digest).first()
    if have and have.status != "excluded":
        raise PublishError("Lớp đã có học liệu này")
    try:
        res = lms.add_resource(int(cs.moodle_course_id), title, filename, data, week)
    except lms.MoodleWSError as ex:
        raise PublishError(str(ex)) from ex
    sync.sync_section(db, cs, user_id)
    m = db.query(SectionMaterial).filter_by(class_section_id=cs.id, content_hash=digest).first()
    if not m:
        raise PublishError("Đã đăng lên Moodle nhưng hệ thống chưa thấy tệp (chủ đề đang ẩn, hoặc khóa đã có tệp trùng tên "
                           "nhưng nội dung khác) – kiểm tra khóa học trên Moodle rồi bấm \"Đồng bộ từ Moodle\"")
    m.material_type, m.title, m.title_custom = material_type, title.strip()[:255], True
    if m.status in ("excluded", "missing"):
        m.status, m.error = "pending", None
    db.commit()
    index.enqueue(cs.id)
    return {"material_id": m.id, "created": bool(res.get("created", True)),
            "note": "Đã đăng lên Moodle và đang nạp" if res.get("created", True) else "Tệp đã có trên Moodle – đã chọn làm học liệu"}


def fetch_bytes(m: SectionMaterial) -> bytes:
    """Tải nội dung học liệu (đang nằm trên Moodle) về bộ nhớ để sao sang lớp khác."""
    try:
        data, _ = lms.download(index.download_url(m))
    except (lms.MoodleWSError, index.MaterialError) as ex:
        raise PublishError(str(ex)) from ex
    check_pdf(data)
    if hashlib.sha1(data).hexdigest() != m.content_hash:
        raise PublishError("Nội dung tải về không khớp tệp trên Moodle – hãy đồng bộ lại lớp nguồn")
    return data
