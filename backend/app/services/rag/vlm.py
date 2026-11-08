"""Mô tả HÌNH trong học liệu bằng VLM chạy cục bộ (Ollama, mặc định qwen2.5vl:3b) – điền material_passages.vlm_desc."""
from __future__ import annotations

import base64
import logging
import os

import httpx
from sqlalchemy import bindparam, update
from sqlalchemy.orm import Session

from ...config import settings
from ...models import ClassSection, Course, MaterialPage, MaterialPassage, SectionMaterial

log = logging.getLogger(__name__)

TIMEOUT_S = 180.0
MAX_FIGURES = 300
MAX_DESC = 1500
PDF_TEXT_MAX = 600
NUM_PREDICT = 320
OPTIONS = {"temperature": 0, "num_predict": NUM_PREDICT, "repeat_penalty": 1.1}

PROMPT = """Ảnh là một hình cắt từ {where} của môn "{course}"{crumb}.
{text}Hãy mô tả NGẮN GỌN bằng tiếng Việt (tối đa 5 câu) nội dung hình để sinh viên tìm lại được: hình là loại gì (sơ đồ, \
các thẻ / khối so sánh, quy trình, bảng, biểu đồ, ảnh chụp màn hình...), các ý chính và quan hệ giữa các phần (khối \
nào so với khối nào, mũi tên đi từ đâu tới đâu). Giữ nguyên thuật ngữ tiếng Anh. Chỉ nói điều có trong hình, không \
thêm kiến thức bên ngoài, không mở đầu bằng "Hình này"."""


def model_name() -> str:
    return settings.rag_vlm_model


def _url(path: str) -> str:
    return settings.rag_vlm_url.rstrip("/") + path


def available() -> bool:
    """Ollama đang chạy và đã có model (ollama pull) – hỏi nhanh, không nạp model."""
    if not model_name():
        return False
    try:
        r = httpx.get(_url("/api/tags"), timeout=3.0)
        r.raise_for_status()
        names = {m.get("name") for m in r.json().get("models", [])} | {m.get("model") for m in r.json().get("models", [])}
    except (httpx.HTTPError, ValueError) as ex:
        log.info("VLM tắt (không gọi được Ollama ở %s: %s) – hình chỉ có chữ đọc từ PDF", settings.rag_vlm_url, ex)
        return False
    name = model_name()
    if name not in names and f"{name}:latest" not in names:
        log.warning("VLM tắt: Ollama chưa có model %s (chạy: ollama pull %s)", name, name)
        return False
    return True


def describe(png: bytes, prompt: str) -> str:
    """Hỏi VLM về một ảnh."""
    r = httpx.post(_url("/api/chat"), timeout=TIMEOUT_S, json={
        "model": model_name(), "stream": False, "keep_alive": "10m",
        "options": OPTIONS,
        "messages": [{"role": "user", "content": prompt, "images": [base64.b64encode(png).decode()]}]})
    if r.is_error:
        log.warning("VLM bỏ qua một hình: HTTP %s %s", r.status_code, r.text[:200])
        return ""
    return " ".join((r.json().get("message", {}).get("content") or "").split())[:MAX_DESC]


def prompt_for(course: str, slide: bool, breadcrumb: str, body: str) -> str:
    text = " ".join((body or "").split())
    if len(text) > PDF_TEXT_MAX:
        text = text[:PDF_TEXT_MAX].rsplit(" ", 1)[0] + " …"
    return PROMPT.format(where="slide bài giảng" if slide else "tài liệu", course=course,
                         crumb=f', phần "{breadcrumb}"' if breadcrumb else "",
                         text=f'Chữ đọc được trong hình (có thể lộn thứ tự): "{text}".\n' if text else "")


def describe_missing(db: Session, cs_id: int, fetcher=None) -> int:
    """Mô tả hình cho các học liệu 'ready' của lớp chưa mô tả (hoặc mô tả bằng model khác)."""
    if not model_name():
        return 0
    name = model_name()
    todo = (db.query(SectionMaterial)
            .filter(SectionMaterial.class_section_id == cs_id, SectionMaterial.status == "ready",
                    SectionMaterial.source == "moodle",
                    (SectionMaterial.vlm_model.is_(None)) | (SectionMaterial.vlm_model != name))
            .order_by(SectionMaterial.id).all())
    course = (db.query(Course.course_name).join(ClassSection, ClassSection.course_id == Course.id)
              .filter(ClassSection.id == cs_id).scalar()) or ""
    for m in todo:
        db.expunge(m)
    db.rollback()
    if not todo or not available():
        return 0
    from . import index
    from .ingest import render_regions
    total = 0
    for m in todo:
        figs = (db.query(MaterialPassage.id, MaterialPage.page_no, MaterialPassage.bboxes, MaterialPassage.breadcrumb,
                         MaterialPassage.body)
                .join(MaterialPage, MaterialPage.id == MaterialPassage.page_id)
                .filter(MaterialPassage.material_id == m.id, MaterialPassage.kind == "figure")
                .order_by(MaterialPassage.seq).limit(MAX_FIGURES).all())
        db.rollback()
        descs: list[tuple[int, str]] = []
        if figs:
            src = None
            try:
                src = fetcher(m) if fetcher else index.fetch(m)
                pngs = render_regions(src, [(pg, tuple(bbs[0])) for _, pg, bbs, _, _ in figs])
                for (pid, _, _, crumb, body), png in zip(figs, pngs):
                    d = describe(png, prompt_for(course, m.material_type == "slide", crumb, body))
                    if d:
                        descs.append((pid, d))
            except Exception as ex:
                log.warning("Mô tả hình học liệu %s (%s) dừng: %s: %s", m.id, m.file_name, type(ex).__name__, ex)
                return total
            finally:
                if isinstance(src, str):
                    os.unlink(src)
        if descs:
            db.connection().execute(
                update(MaterialPassage).where(MaterialPassage.id == bindparam("b_id"))
                .values(vlm_desc=bindparam("b_desc"), embedding=None),
                [{"b_id": pid, "b_desc": d} for pid, d in descs])
        n = db.execute(update(SectionMaterial).where(SectionMaterial.id == m.id, SectionMaterial.indexed_at == m.indexed_at,
                                                     SectionMaterial.status == "ready")
                       .values(vlm_model=name, **({"embed_model": None} if descs else {}))).rowcount
        if n:
            db.commit()
            total += len(descs)
            log.info("Đã mô tả %d hình của học liệu %s (%s)", len(descs), m.id, m.file_name)
        else:
            db.rollback()
    return total
