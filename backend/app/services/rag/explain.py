from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...config import settings
from ...models import MaterialExplanation, MaterialPage, MaterialPassage, Question, SectionMaterial

log = logging.getLogger(__name__)

MAX_PER_SOURCE = 2500
REFUSAL = "KHÔNG ĐỦ CĂN CỨ"
_CITE = re.compile(r"\[\s*Nguồn\s*(\d+)\s*\]", re.I)
_LOOSE_CITE = re.compile(r"[\[(]\s*Nguồn\s*(\d+(?:\s*,\s*\d+)*)\s*[\])]", re.I)

RULES = f"""Bạn là trợ lý học tập. Sinh viên vừa làm SAI một câu trắc nghiệm. Hãy giải thích vì sao ĐÁP ÁN ĐÚNG là đúng.
QUY TẮC:
- CHỈ dùng thông tin trong phần TÀI LIỆU bên dưới. KHÔNG dùng kiến thức bên ngoài, KHÔNG bịa.
- Sau mỗi ý lấy từ tài liệu, ghi nguồn dạng [Nguồn 1], [Nguồn 2]... đúng số của đoạn tài liệu đó.
- Nếu TÀI LIỆU không có nội dung giải thích được đáp án đúng, chỉ trả lời đúng một dòng: {REFUSAL}
- Viết bằng tiếng Việt, ngắn gọn, tối đa 5 câu. Giữ nguyên thuật ngữ tiếng Anh. Không chép lại câu hỏi.
VÍ DỤ CÁCH VIẾT (nội dung chỉ để minh họa định dạng):
Khóa chính xác định duy nhất mỗi dòng của bảng nên không được trùng và không được NULL [Nguồn 1]. Khóa ngoại thì \
chỉ tham chiếu tới khóa chính của bảng khác [Nguồn 2]."""


@dataclass
class Source:
    material_title: str
    page_no: int
    text: str
    url: str | None = None


@dataclass
class Explanation:
    text: str
    cited: list[int] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    model: str = ""


def model_name() -> str:
    return settings.rag_llm_model or settings.rag_vlm_model


def llm_options() -> dict:
    return {"temperature": 0, "num_predict": settings.rag_llm_max_tokens, "num_ctx": settings.rag_llm_num_ctx,
            "repeat_penalty": 1.1}


def build_context(sources: list[Source], limit: int | None = None) -> tuple[str, list[Source]]:
    parts, used, room = [], [], limit or settings.rag_llm_max_context
    for s in sources:
        text = " ".join(s.text.split())[:min(MAX_PER_SOURCE, room)]
        if len(text) < 200 and used:
            break
        if not text:
            continue
        used.append(s)
        parts.append(f"[Nguồn {len(used)}] ({s.material_title}, trang {s.page_no})\n{text}")
        room -= len(text)
    return "\n\n".join(parts), used


def build_prompt(stem: str, options: dict[str, str], correct: list[str], context: str) -> str:
    opts = "\n".join(f"{label}. {content}" for label, content in options.items())
    right = "; ".join(f"{label}. {options[label]}" for label in correct)
    return (f"{RULES}\n\nCÂU HỎI:\n{stem}\n{opts}\n\nĐÁP ÁN ĐÚNG: {right}\n\nTÀI LIỆU:\n{context}\n\n"
            "GIẢI THÍCH (mỗi câu kết thúc bằng [Nguồn k]):")


def generate(prompt: str) -> str:
    r = httpx.post(settings.rag_vlm_url.rstrip("/") + "/api/chat", timeout=float(settings.rag_llm_timeout), json={
        "model": model_name(), "stream": False, "keep_alive": "10m", "options": llm_options(),
        "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    return (r.json().get("message", {}).get("content") or "").strip()


def check(answer: str, n_sources: int) -> tuple[str, list[int]] | None:
    if not answer or REFUSAL.lower() in answer.lower():
        return None
    answer = _LOOSE_CITE.sub(lambda m: " ".join(f"[Nguồn {n.strip()}]" for n in m.group(1).split(",")), answer)
    cited = sorted({int(m) for m in _CITE.findall(answer) if 1 <= int(m) <= n_sources})
    if not cited:
        return None
    clean = _CITE.sub(lambda m: m.group(0) if 1 <= int(m.group(1)) <= n_sources else "", answer)
    return re.sub(r"[ \t]{2,}", " ", clean).strip(), cited


def explain(stem: str, options: dict[str, str], correct: list[str], sources: list[Source]) -> Explanation | None:
    context, used = build_context(sources)
    if not used or not correct or not model_name():
        return None
    ok = check(generate(build_prompt(stem, options, correct, context)), len(used))
    if ok is None:
        return Explanation("", [], used, model_name())
    return Explanation(ok[0], ok[1], used, model_name())


def page_sources(db: Session, pages: list) -> list[Source]:
    out = []
    for s in pages:
        rows = (db.query(MaterialPassage.title, MaterialPassage.caption, MaterialPassage.body, MaterialPassage.vlm_desc)
                .join(MaterialPage, MaterialPage.id == MaterialPassage.page_id)
                .join(SectionMaterial, SectionMaterial.id == MaterialPassage.material_id)
                .filter(MaterialPassage.material_id == s.material_id, MaterialPage.page_no == s.page_no,
                        SectionMaterial.status == "ready")
                .order_by(MaterialPassage.seq).all())
        lines, last = [], None
        for title, caption, body, desc in rows:
            if title and title != last:
                lines.append(title)
                last = title
            lines += [x for x in (caption, body, desc) if x]
        if lines:
            out.append(Source(s.material_title, s.page_no, "\n".join(lines), s.url))
    return out


def input_hash(stem: str, options: dict[str, str], correct: list[str], sources: list[Source], model: str) -> str:
    raw = json.dumps([RULES, llm_options(), settings.rag_llm_max_context, model, stem, sorted(options.items()), sorted(correct),
                      [(s.material_title, s.page_no, s.text) for s in sources]], ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _view(row: MaterialExplanation) -> dict:
    status = "refused" if not row.text else "rejected" if row.rejected_at else "ready"
    return {"status": status, "text": row.text, "cited": row.cited, "sources": row.sources, "model": row.model}


def for_question(db: Session, cs_id: int, question: Question, pages: list | None = None,
                 generate_missing: bool = True) -> dict:
    from . import suggest
    if pages is None:
        pages = suggest.for_question(db, cs_id, question)
    options = {o.opt_label: o.content for o in sorted(question.options, key=lambda o: o.position)}
    correct = [o.opt_label for o in question.options if o.is_correct]
    sources = page_sources(db, pages) if pages else []
    model = model_name()
    if not sources or not correct or not model:
        return {"status": "none"}
    key = input_hash(question.content, options, correct, sources, model)
    row = db.query(MaterialExplanation).filter_by(class_section_id=cs_id, question_id=question.id).one_or_none()
    if row is not None and row.input_hash == key:
        return _view(row)
    if not generate_missing:
        return {"status": "missing"}
    try:
        e = explain(question.content, options, correct, sources)
    except httpx.HTTPError as ex:
        log.warning("Sinh lời giải thích lỗi (%s: %s)", type(ex).__name__, ex)
        return {"status": "error"}
    if e is None:
        return {"status": "none"}
    if row is None:
        row = MaterialExplanation(class_section_id=cs_id, question_id=question.id)
        db.add(row)
    row.input_hash, row.model, row.text, row.cited = key, e.model, e.text or None, e.cited
    row.sources = [{"title": s.material_title, "page_no": s.page_no, "url": s.url} for s in e.sources]
    row.created_at = func.now()
    row.rejected_at = row.rejected_by = None
    db.flush()
    return _view(row)


def set_rejected(db: Session, cs_id: int, question: Question, rejected: bool, user_id: int) -> dict | None:
    if for_question(db, cs_id, question, generate_missing=False)["status"] not in ("ready", "rejected"):
        return None
    row = db.query(MaterialExplanation).filter_by(class_section_id=cs_id, question_id=question.id).one()
    row.rejected_at, row.rejected_by = (func.now(), user_id) if rejected else (None, None)
    db.flush()
    db.refresh(row)
    return _view(row)
