"""Ghi kết quả đọc PDF (ingest) + gom đoạn (chunk) của MỘT học liệu vào CSDL: material_pages, material_passages."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ...models import MaterialPage, MaterialPassage, SectionMaterial
from .chunk import Passage
from .ingest import Page


def save_document(db: Session, material: SectionMaterial, pages: list[Page], passages: list[Passage]) -> None:
    db.query(MaterialPassage).filter_by(material_id=material.id).delete()
    db.query(MaterialPage).filter_by(material_id=material.id).delete()
    rows: dict[int, MaterialPage] = {}
    for p in pages:
        w, h = p.sheet or (p.width, p.height)
        r = rows.setdefault(p.no, MaterialPage(material_id=material.id, page_no=p.no, width=round(w, 1),
                                               height=round(h, 1), running_header=None, is_scanned=False,
                                               is_visual=False))
        running = [x for x in (r.running_header or "").split(" | ") if x]
        r.running_header = " | ".join(dict.fromkeys(running + p.running)) or None
        r.is_scanned, r.is_visual = r.is_scanned or p.scanned, r.is_visual or p.visual
    db.add_all(rows.values())
    db.flush()
    db.add_all(MaterialPassage(material_id=material.id, page_id=rows[ps.page].id, seq=i, kind=ps.kind,
                               title=ps.title[:255], breadcrumb=ps.breadcrumb[:1000], level=ps.level,
                               caption=ps.caption or None, body=ps.body, vlm_desc=ps.vlm_desc or None, is_code=ps.code,
                               bboxes=[list(b) for b in ps.bboxes])
               for i, ps in enumerate(passages, 1))
    material.n_pages = len(rows)
    material.status, material.error, material.indexed_at = "ready", None, datetime.now()
    material.embed_model = None
    material.vlm_model = None
    db.flush()
