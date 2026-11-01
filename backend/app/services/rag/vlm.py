"""Mô tả HÌNH trong học liệu bằng VLM chạy cục bộ (Ollama, mặc định qwen2.5vl:3b) – điền material_passages.vlm_desc.

Vì sao cần: slide vẽ theo kiểu THẺ / KHỐI (hộp bo góc có nền, sơ đồ ô + mũi tên) bị bộ đọc PDF coi là HÌNH; chữ trong
hình vẫn được giữ (thân đoạn hình) nhưng là các mảnh rời theo thứ tự vẽ, trộn giữa các thẻ ("1 CẤU TRÚC 2 ĐẶC TÍNH DỮ
LIỆU Hệ thống, database..."), không có ý nghĩa của bố cục (cột nào so với cột nào, mũi tên đi đâu); trang scan / ảnh
chụp thì không có chữ nào. VLM NHÌN vùng hình và viết vài câu mô tả – đoạn hình tìm được theo ý ("so sánh static
capture và incremental capture") chứ không chỉ theo từ rời, và cổng ngữ nghĩa có câu đầy đủ để so.

Chạy ở luồng nạp, SAU khi đoạn đã commit và đã có chỉ mục + vector (gợi ý dùng được ngay, mô tả hình đến sau – VLM
chậm, vài giây mỗi hình trên GPU laptop): mỗi học liệu 'ready' chưa mô tả (vlm_model NULL / model khác) → tải lại PDF
từ Moodle → cắt ảnh từng vùng hình → hỏi VLM → ghi mô tả trong giao dịch NGẮN, CHỈ khi học liệu chưa bị nạp lại
(indexed_at không đổi – cùng quy ước với semantic.embed_missing). Đoạn được mô tả thì xóa vector và embed_model của học
liệu để semantic.embed_missing tính lại; vlm_model đổi → khóa chỉ mục tìm kiếm của lớp đổi → chỉ mục dựng lại.

Gửi kèm VLM phần chữ bộ đọc PDF đã lấy được trong hình: model nhỏ đọc chữ tiếng Việt có dấu trong ảnh hay sai – có
chữ gốc thì mô tả dùng đúng thuật ngữ; VLM chỉ phải hiểu BỐ CỤC.

Tùy chọn, không chặn: RAG_VLM_MODEL rỗng, Ollama không chạy hoặc chưa tải model → bỏ qua (đoạn hình chỉ có chữ của
PDF). Lỗi giữa chừng (Ollama tắt, quá giờ) → bỏ dở học liệu đó, không ghi gì, lần nạp / đồng bộ sau làm lại. Ollama
TỪ CHỐI riêng một hình (trả lỗi HTTP, vd. "token repeat limit reached" khi model lặp chữ mãi) → bỏ qua hình đó (chỉ có
chữ PDF), các hình khác vẫn ghi – không để một hình chặn cả học liệu ở mọi lần đồng bộ.
"""
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

TIMEOUT_S = 180.0         # một hình: lần gọi đầu phải nạp model vào GPU (~10–20 s), sau đó vài giây
MAX_FIGURES = 300         # học liệu nhiều hình hơn: chỉ mô tả ngần này hình đầu (giáo trình scan vài trăm trang)
MAX_DESC = 1500           # ký tự mô tả tối đa lưu lại
PDF_TEXT_MAX = 600        # ký tự chữ-trong-hình gửi kèm
NUM_PREDICT = 320         # token trả lời tối đa (~5 câu)
# repeat_penalty: model 3B đôi khi lặp một cụm mãi (hình nhiều ô giống nhau) → Ollama hủy câu trả lời; 1.1 đủ chặn mà
# vẫn trả lời tiếng Việt (1.15 đã bắt đầu trả lời tiếng Anh). evaluate.describe_corpus lưu đệm theo OPTIONS.
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
    """Hỏi VLM về một ảnh. Ollama từ chối ảnh này (HTTP 4xx/5xx) → "" (bỏ qua hình); lỗi kết nối / quá giờ →
    httpx.TransportError (nơi gọi bỏ dở học liệu, lần sau làm lại)."""
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
    """Mô tả hình cho các học liệu 'ready' của lớp chưa mô tả (hoặc mô tả bằng model khác). Trả về số đoạn hình đã mô tả.
    fetcher(m) → đường dẫn / nội dung PDF (mặc định tải từ Moodle như lúc nạp)."""
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
                    if d:                                    # hình bị Ollama từ chối: giữ nguyên đoạn + vector
                        descs.append((pid, d))
            except Exception as ex:                          # Moodle / Ollama lỗi, quá giờ: bỏ dở, lần sau làm lại
                log.warning("Mô tả hình học liệu %s (%s) dừng: %s: %s", m.id, m.file_name, type(ex).__name__, ex)
                return total
            finally:
                if isinstance(src, str):
                    os.unlink(src)
        if descs:    # executemany trên connection – đoạn bị xóa (nạp lại trong lúc mô tả) thì trượt, kiểm ngay dưới
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
        else:                                                # đã bị nạp lại / bỏ chọn trong lúc mô tả: bỏ kết quả
            db.rollback()
    return total
