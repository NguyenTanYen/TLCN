"""Cổng chặn ngữ nghĩa cho gợi ý học liệu (MiniLM đa ngôn ngữ, CPU)."""
from __future__ import annotations

import logging
import os
import threading

import numpy as np
from sqlalchemy import bindparam, update
from sqlalchemy.orm import Session

from ...config import settings
from ...models import MaterialPassage, SectionMaterial

log = logging.getLogger(__name__)

_model = None
_loaded = False
_lock = threading.Lock()


def model_name() -> str:
    return settings.rag_embed_model


def _load():
    """Nạp model một lần cho cả tiến trình (~5 s, ~470 MB RAM)."""
    global _model, _loaded
    with _lock:
        if not _loaded:
            _loaded = True
            if model_name():
                os.environ.setdefault("USE_TF", "0")
                try:
                    from sentence_transformers import SentenceTransformer
                    _model = SentenceTransformer(model_name(), device="cpu")
                except Exception as ex:
                    log.warning("Cổng ngữ nghĩa tắt (%s: %s) – gợi ý học liệu chỉ dùng BM25", type(ex).__name__, ex)
        return _model


def enabled() -> bool:
    return _load() is not None


def encode(texts: list[str]) -> np.ndarray | None:
    """Vector đã chuẩn hóa (cos = tích vô hướng); None nếu cổng tắt."""
    m = _load()
    if m is None:
        return None
    return m.encode(texts, batch_size=32, normalize_embeddings=True, convert_to_numpy=True).astype(np.float32)


def pack(v: np.ndarray) -> bytes:
    return v.astype(np.float16).tobytes()


def unpack(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float16).astype(np.float32)


def scores(query: str, embeddings: list[bytes | None]) -> list[float] | None:
    """cos(câu hỏi, từng đoạn ứng viên); None = không đánh giá được (cổng tắt, tiếng Việt không dấu, không có ứng viên, có ứng viên chưa có vector / vector của model khác – chưa tính lại xong) → không chặn, không lọc gì."""
    from .search import looks_english, plain
    if not embeddings or not all(embeddings) or (plain(query) and not looks_english(query)):
        return None
    q = encode([query])
    if q is None:
        return None
    vs = [unpack(b) for b in embeddings]
    if any(v.shape[0] != q.shape[1] for v in vs):
        return None
    return [float(v @ q[0]) for v in vs]


def related(query: str, embeddings: list[bytes | None], threshold: float | None = None) -> bool:
    """Câu hỏi có liên quan tới các đoạn ứng viên không: cos cao nhất ≥ ngưỡng (không đánh giá được → True)."""
    threshold = settings.rag_min_similarity if threshold is None else threshold
    s = scores(query, embeddings)
    return s is None or max(s) >= threshold


_dense_cache: dict = {}


def _matrix(db: Session, cs_id: int):
    """Ma trận vector đoạn của lớp (chỉ học liệu 'ready' đã tính bằng model hiện tại), nhớ tạm theo khóa học liệu."""
    name = model_name()
    mats = db.query(SectionMaterial.id, SectionMaterial.indexed_at).filter(
        SectionMaterial.class_section_id == cs_id, SectionMaterial.status == "ready",
        SectionMaterial.embed_model == name).order_by(SectionMaterial.id).all()
    key = (name, tuple((i, str(t)) for i, t in mats))
    got = _dense_cache.get(cs_id)
    if got and got[0] == key:
        return got[1], got[2]
    if not mats:
        return [], None
    rows = (db.query(MaterialPassage.id, MaterialPassage.embedding)
            .filter(MaterialPassage.material_id.in_([i for i, _ in mats]), MaterialPassage.embedding.isnot(None))
            .order_by(MaterialPassage.id).all())
    db.rollback()
    if not rows:
        return [], None
    ids = [r[0] for r in rows]
    mat = np.stack([unpack(r[1]) for r in rows])
    _dense_cache[cs_id] = (key, ids, mat)
    return ids, mat


def dense_info(db: Session, cs_id: int, query: str) -> dict:
    """Chẩn đoán tìm theo nghĩa cho một câu hỏi: cổng bật chưa, số đoạn đã có vector, cos cao nhất và các ngưỡng đang dùng (để giảng viên / Bộ môn thấy vì sao không ra kết quả và chỉnh ngưỡng theo số đo thật)."""
    out = {"enabled": bool(enabled()), "model": model_name(), "vectors": 0, "top_cos": None,
           "gate_threshold": settings.rag_min_similarity, "search_threshold": settings.rag_search_similarity}
    if not out["enabled"]:
        return out
    ids, mat = _matrix(db, cs_id)
    out["vectors"] = len(ids)
    if mat is None or not query.strip():
        return out
    q = encode([query])
    if q is not None and q.shape[1] == mat.shape[1]:
        out["top_cos"] = round(float(np.max(mat @ q[0])), 3)
    return out


def dense_top(db: Session, cs_id: int, query: str, k: int = 30, margin: float | None = None,
              floor: float | None = None) -> list[tuple[int, float]]:
    """k đoạn của lớp GẦN NGHĨA nhất với câu hỏi (cos MiniLM đa ngôn ngữ) – tìm được cả khi câu hỏi tiếng Việt không có từ nào trùng với giáo trình tiếng Anh."""
    from .search import looks_english, plain
    if not query.strip() or (plain(query) and not looks_english(query)) or not enabled():
        return []
    ids, mat = _matrix(db, cs_id)
    if mat is None:
        return []
    q = encode([query])
    if q is None or q.shape[1] != mat.shape[1]:
        return []
    cos = mat @ q[0]
    order = np.argsort(-cos)[:k]
    top = float(cos[order[0]])
    if top < (settings.rag_min_similarity if floor is None else floor):
        return []
    margin = settings.rag_page_margin if margin is None else margin
    return [(ids[i], float(cos[i])) for i in order if cos[i] >= top - margin]


def embed_missing(db: Session, cs_id: int) -> int:
    """Tính vector cho các học liệu 'ready' của lớp chưa có vector (hoặc tính bằng model khác)."""
    if not enabled():
        return 0
    from .search import _doc_text
    name = model_name()
    todo = [(i, at) for i, at in db.query(SectionMaterial.id, SectionMaterial.indexed_at)
            .filter(SectionMaterial.class_section_id == cs_id, SectionMaterial.status == "ready",
                    (SectionMaterial.embed_model.is_(None)) | (SectionMaterial.embed_model != name))]
    db.rollback()
    total = 0
    for mid, stamp in todo:
        rows = db.query(MaterialPassage.id, MaterialPassage.title, MaterialPassage.breadcrumb, MaterialPassage.caption,
                        MaterialPassage.body, MaterialPassage.vlm_desc).filter(MaterialPassage.material_id == mid).all()
        db.rollback()
        vecs = encode([_doc_text(t, b, c, body, v) for _, t, b, c, body, v in rows]) if rows else []
        if rows:
            db.connection().execute(
                update(MaterialPassage).where(MaterialPassage.id == bindparam("b_id"))
                .values(embedding=bindparam("b_emb")),
                [{"b_id": pid, "b_emb": pack(v)} for (pid, *_), v in zip(rows, vecs)])
        n = db.execute(update(SectionMaterial).where(SectionMaterial.id == mid, SectionMaterial.indexed_at == stamp,
                                                     SectionMaterial.status == "ready")
                       .values(embed_model=name)).rowcount
        if n:
            db.commit()
            total += len(rows)
        else:
            db.rollback()
    return total
