"""Ghi kết quả đọc PDF (ingest) + gom đoạn (chunk) của MỘT học liệu vào CSDL: material_pages, material_passages.

Nạp lại một học liệu (GV sửa tệp trên Moodle) thì thay toàn bộ trang / đoạn cũ của học liệu đó. Hàm không commit –
nơi gọi quyết định giao dịch.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ...models import MaterialPage, MaterialPassage, SectionMaterial
from .chunk import Passage
from .ingest import Page


def save_document(db: Session, material: SectionMaterial, pages: list[Page], passages: list[Passage]) -> None:
    db.query(MaterialPassage).filter_by(material_id=material.id).delete()
    db.query(MaterialPage).filter_by(material_id=material.id).delete()
    rows = {p.no: MaterialPage(material_id=material.id, page_no=p.no, width=round(p.width, 1), height=round(p.height, 1),
                               running_header=" | ".join(p.running) or None, is_scanned=p.scanned, is_visual=p.visual)
            for p in pages}
    db.add_all(rows.values())
    db.flush()                                                    # lấy id trang cho khóa ngoại của đoạn
    db.add_all(MaterialPassage(material_id=material.id, page_id=rows[ps.page].id, seq=i, kind=ps.kind,
                               title=ps.title[:255], breadcrumb=ps.breadcrumb[:1000], level=ps.level,
                               caption=ps.caption or None, body=ps.body, vlm_desc=ps.vlm_desc or None, is_code=ps.code,
                               bboxes=[list(b) for b in ps.bboxes])
               for i, ps in enumerate(passages, 1))
    material.n_pages = len(pages)
    material.status, material.error, material.indexed_at = "ready", None, datetime.now()
    db.flush()
