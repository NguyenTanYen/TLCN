"""Học liệu của học phần → các "đoạn" (trang PDF / slide PPTX / mục DOCX) → truy xuất BM25 → gợi ý đọc đúng trang.

Đây là phần RAG của hệ thống: chỉ tìm trong học liệu của ĐÚNG học phần (course_id). VLM (mô hình thị giác) là tùy chọn:
chỉ dùng cho trang gần như không có chữ (sơ đồ, ảnh chụp slide, bảng dạng ảnh) khi đã cấu hình VLM_URL.
"""
from __future__ import annotations

import base64
import math
import re
import unicodedata
import uuid
from collections import Counter
from pathlib import Path

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings

ALLOWED = {"pdf", "pptx", "docx", "txt", "md"}
MAX_BYTES = 60 * 1024 * 1024
MIN_TEXT = 40            # trang có ít chữ hơn mức này (và có hình) mới nhờ VLM mô tả
CHUNK_CHARS = 1400       # DOCX/TXT: gộp đoạn văn tới cỡ này thì tách một đoạn mới

_STOP_RAW = set("""và của là có các một những cho được trong khi với để này đó từ theo như không cũng đã sẽ tại về ra vào
the of and a an to in is are for on with by as at be or from that this it""".split())


def storage_dir() -> Path:
    d = Path(settings.materials_dir) if settings.materials_dir else Path(__file__).resolve().parents[2] / "du_lieu_hoc_lieu"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower().replace("đ", "d"))
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


STOP = {fold(w) for w in _STOP_RAW}


def tokens(s: str) -> list[str]:
    """Từ không dấu + cặp từ liền kề (tiếng Việt nhiều từ ghép: 'khóa ngoại', 'chuẩn hóa')."""
    words = [w for w in re.findall(r"[a-z0-9]+", fold(s)) if w not in STOP and (len(w) > 1 or w.isdigit())]
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:])]


# ---------------------------------------------------------------- trích xuất
def _clean(t: str) -> str:
    return re.sub(r"[ \t ]+", " ", re.sub(r"\n{3,}", "\n\n", t or "")).strip()


def _heading_of(t: str) -> str | None:
    for line in t.splitlines():
        line = line.strip()
        if 3 <= len(line) <= 120:
            return line
    return None


def describe_image(png: bytes) -> str | None:
    """VLM tùy chọn: mô tả trang hình/sơ đồ bằng văn bản để vẫn tìm kiếm được. Trả None khi chưa cấu hình hoặc lỗi."""
    if not (settings.vlm_url and settings.vlm_model):
        return None
    body = {"model": settings.vlm_model, "max_tokens": 400, "messages": [{"role": "user", "content": [
        {"type": "text", "text": "Đây là một trang/slide của giáo trình. Hãy chép lại chữ trong ảnh và mô tả ngắn gọn "
                                 "nội dung kiến thức của sơ đồ/bảng/hình (tiếng Việt, tối đa 120 từ)."},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}}]}]}
    headers = {"Authorization": f"Bearer {settings.vlm_api_key}"} if settings.vlm_api_key else {}
    try:
        r = httpx.post(settings.vlm_url, json=body, headers=headers, timeout=90)
        r.raise_for_status()
        return _clean(r.json()["choices"][0]["message"]["content"]) or None
    except Exception:
        return None


def _extract_pdf(path: Path):
    import fitz
    doc = fitz.open(path)
    for i, page in enumerate(doc, 1):
        t = _clean(page.get_text())
        vlm = False
        if len(t) < MIN_TEXT and (page.get_images() or page.get_drawings()):
            d = describe_image(page.get_pixmap(dpi=110).tobytes("png"))
            if d:
                t, vlm = _clean(t + "\n" + d), True
        if t:
            yield i, _heading_of(t), t, vlm


def _extract_pptx(path: Path):
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    prs = Presentation(str(path))
    for i, slide in enumerate(prs.slides, 1):
        parts, title, has_pic = [], None, False
        for sh in slide.shapes:
            if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                has_pic = True
            if sh.has_text_frame and sh.text_frame.text.strip():
                if title is None and getattr(slide.shapes, "title", None) is not None and sh == slide.shapes.title:
                    title = sh.text_frame.text.strip()
                parts.append(sh.text_frame.text.strip())
            if getattr(sh, "has_table", False) and sh.has_table:
                for row in sh.table.rows:
                    parts.append(" | ".join(c.text.strip() for c in row.cells))
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            parts.append(slide.notes_slide.notes_text_frame.text.strip())
        t, vlm = _clean("\n".join(parts)), False
        if len(t) < MIN_TEXT and has_pic and settings.vlm_url:
            pic = next((sh for sh in slide.shapes if sh.shape_type == MSO_SHAPE_TYPE.PICTURE), None)
            d = describe_image(pic.image.blob) if pic is not None else None
            if d:
                t, vlm = _clean(t + "\n" + d), True
        if t:
            yield i, title or _heading_of(t), t, vlm


def _extract_flow(blocks):
    """DOCX/TXT: gộp đoạn văn theo mục (tiêu đề) và cỡ ~CHUNK_CHARS; page_no = số thứ tự đoạn."""
    n, heading, buf, size = 0, None, [], 0
    for is_head, line in blocks:
        if is_head or size + len(line) > CHUNK_CHARS:
            if buf:
                n += 1
                yield n, heading, "\n".join(buf), False
                buf, size = [], 0
        if is_head:
            heading = line[:200]
        buf.append(line)
        size += len(line)
    if buf:
        yield n + 1, heading, "\n".join(buf), False


def _extract_docx(path: Path):
    from docx import Document
    d = Document(str(path))
    blocks = []
    for p in d.paragraphs:
        t = p.text.strip()
        if t:
            blocks.append((p.style is not None and p.style.name.lower().startswith(("heading", "title")), t))
    return _extract_flow(blocks)


def _extract_text(path: Path):
    blocks = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        t = line.strip()
        if t:
            blocks.append((t.startswith("#") or (t.isupper() and len(t) < 90), t.lstrip("# ").strip()))
    return _extract_flow(blocks)


def extract(path: Path, ext: str):
    return {"pdf": _extract_pdf, "pptx": _extract_pptx, "docx": _extract_docx, "txt": _extract_text, "md": _extract_text}[ext](path)


# ---------------------------------------------------------------- lưu và lập chỉ mục
def index_material(db: Session, material_id: int) -> int:
    """Trích xuất lại toàn bộ đoạn của một học liệu (xóa đoạn cũ). Trả số đoạn."""
    m = db.execute(text("SELECT file_path, file_ext FROM course_materials WHERE id=:i"), {"i": material_id}).one()
    db.execute(text("DELETE FROM material_chunks WHERE material_id=:i"), {"i": material_id})
    n = 0
    for page, heading, content, vlm in extract(Path(m.file_path), m.file_ext):
        db.execute(text("""INSERT INTO material_chunks (material_id, page_no, heading, content, from_vlm)
                           VALUES (:m, :p, :h, :c, :v)"""),
                   {"m": material_id, "p": page, "h": (heading or "")[:255] or None, "c": content, "v": vlm})
        n += 1
    db.execute(text("UPDATE course_materials SET n_pages=:n WHERE id=:i"), {"n": n, "i": material_id})
    db.commit()
    _CACHE.clear()
    return n


def add_material(db: Session, *, course_id: int, title: str, filename: str, data: bytes, material_type: str = "slide",
                 outline_id: int | None = None, user_id: int | None = None, source: str = "upload",
                 moodle: dict | None = None) -> dict:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED:
        raise ValueError(f"Chỉ nhận tệp {', '.join(sorted(ALLOWED)).upper()} (nhận được: .{ext or '?'})")
    if len(data) > MAX_BYTES:
        raise ValueError("Tệp quá lớn (tối đa 60 MB)")
    d = storage_dir() / str(course_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{uuid.uuid4().hex}.{ext}"
    path.write_bytes(data)
    moodle = moodle or {}
    mid = db.execute(text("""INSERT INTO course_materials (course_id, title, material_type, outline_id, file_name, file_ext, file_path,
                                 source, uploaded_by, moodle_course_id, moodle_cmid, moodle_file_url)
                             VALUES (:c,:t,:ty,:o,:fn,:fe,:fp,:s,:u,:mc,:cm,:mu)"""),
                     {"c": course_id, "t": title[:255], "ty": material_type, "o": outline_id, "fn": filename[:255], "fe": ext,
                      "fp": str(path), "s": source, "u": user_id, "mc": moodle.get("course_id"), "mu": moodle.get("url"),
                      "cm": moodle.get("cmid")}).lastrowid
    db.commit()
    try:
        n = index_material(db, mid)
    except Exception as ex:                       # tệp hỏng/không đọc được: bỏ bản ghi để không để rác
        db.rollback()
        db.execute(text("DELETE FROM course_materials WHERE id=:i"), {"i": mid})
        db.commit()
        path.unlink(missing_ok=True)
        raise ValueError(f"Không đọc được nội dung tệp: {ex}") from ex
    if n == 0:
        db.execute(text("DELETE FROM course_materials WHERE id=:i"), {"i": mid})
        db.commit()
        path.unlink(missing_ok=True)
        raise ValueError("Tệp không có chữ để lập chỉ mục (nếu là bản scan/ảnh, hãy bật VLM_URL để mô tả trang ảnh)")
    return {"id": mid, "n_pages": n}


def delete_material(db: Session, material_id: int) -> None:
    fp = db.execute(text("SELECT file_path FROM course_materials WHERE id=:i"), {"i": material_id}).scalar()
    db.execute(text("DELETE FROM course_materials WHERE id=:i"), {"i": material_id})
    db.commit()
    if fp:
        Path(fp).unlink(missing_ok=True)
    _CACHE.clear()


# ---------------------------------------------------------------- truy xuất BM25
_CACHE: dict[int, "Index"] = {}
K1, B = 1.4, 0.75


class Index:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.tf = [Counter(tokens((r["heading"] or "") + " " + (r["heading"] or "") + " " + r["content"])) for r in rows]
        self.len = [sum(t.values()) for t in self.tf]
        self.avg = (sum(self.len) / len(self.len)) if self.len else 1.0
        df: Counter = Counter()
        for t in self.tf:
            df.update(t.keys())
        n = len(rows)
        self.idf = {w: math.log(1 + (n - d + 0.5) / (d + 0.5)) for w, d in df.items()}

    def score(self, q: Counter, i: int) -> float:
        tf, ln = self.tf[i], self.len[i]
        s = 0.0
        for w, qc in q.items():
            f = tf.get(w)
            if f:
                s += self.idf[w] * (f * (K1 + 1)) / (f + K1 * (1 - B + B * ln / self.avg)) * (1 + 0.15 * (qc - 1))
        return s

    def self_score(self, q: Counter) -> float:
        """Điểm tối đa có thể đạt (mọi từ truy vấn xuất hiện) – dùng chuẩn hóa về 0–1."""
        return sum(self.idf.get(w, math.log(1 + (len(self.rows) + 0.5) / 0.5)) * (K1 + 1) / (1 + K1 * (1 - B + B * 1)) for w in q) or 1.0


def _index(db: Session, course_id: int) -> Index:
    sig = db.execute(text("""SELECT COUNT(*), COALESCE(MAX(c.id),0) FROM material_chunks c JOIN course_materials m ON m.id=c.material_id
                             WHERE m.course_id=:c"""), {"c": course_id}).one()
    hit = _CACHE.get(course_id)
    if hit and hit.sig == tuple(sig):
        return hit
    rows = [dict(r) for r in db.execute(text("""
        SELECT c.id AS chunk_id, c.page_no, c.heading, c.content, c.from_vlm, m.id AS material_id, m.title, m.material_type,
               m.file_ext, m.outline_id FROM material_chunks c JOIN course_materials m ON m.id=c.material_id
        WHERE m.course_id=:c ORDER BY m.id, c.page_no"""), {"c": course_id}).mappings()]
    idx = Index(rows)
    idx.sig = tuple(sig)
    _CACHE[course_id] = idx
    return idx


def body_of(content: str, heading: str | None) -> str:
    """Bỏ dòng tiêu đề lặp ở đầu đoạn (tiêu đề đã hiển thị riêng)."""
    lines = content.split("\n", 1)
    return lines[1].strip() if heading and len(lines) == 2 and lines[0].strip() == heading and lines[1].strip() else content


def snippet(content: str, q: Counter, width: int = 260) -> str:
    """Câu/đoạn ngắn chứa nhiều từ khóa của truy vấn nhất – để GV/SV thấy ngay chỗ cần đọc."""
    sents = [s.strip() for s in re.split(r"(?<=[.!?;:])\s+|\n+", content) if s.strip()]
    if not sents:
        return content[:width]
    best = max(range(len(sents)), key=lambda i: sum(1 for w in set(tokens(sents[i])) if w in q))
    out = sents[best]
    if len(out) < width // 2 and best + 1 < len(sents):
        out += " " + sents[best + 1]
    return (out[:width] + "…") if len(out) > width else out


def search(db: Session, course_id: int, query: str, k: int = 3, outline_id: int | None = None, min_rel: float = 0.12) -> list[dict]:
    """Top-k đoạn học liệu của học phần khớp truy vấn nhất. outline_id: ưu tiên tài liệu gắn đúng chương."""
    idx = _index(db, course_id)
    if not idx.rows:
        return []
    q = Counter(tokens(query))
    if not q:
        return []
    top = idx.self_score(q)
    scored = []
    for i, r in enumerate(idx.rows):
        s = idx.score(q, i)
        if s <= 0:
            continue
        if outline_id and r["outline_id"] == outline_id:
            s *= 1.25
        scored.append((s, i))
    scored.sort(reverse=True)
    out = []
    for s, i in scored[:k]:
        rel = min(1.0, s / top)
        if rel < min_rel:
            continue
        r = idx.rows[i]
        out.append({"chunk_id": r["chunk_id"], "material_id": r["material_id"], "material": r["title"], "type": r["material_type"],
                    "page": r["page_no"], "unit": "slide" if r["file_ext"] == "pptx" else ("mục" if r["file_ext"] in ("docx", "txt", "md") else "trang"),
                    "heading": r["heading"], "snippet": snippet(body_of(r["content"], r["heading"]), q), "score": round(rel, 4), "from_vlm": bool(r["from_vlm"])})
    return out
