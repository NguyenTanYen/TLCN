"""Bước 8: sinh viên làm SAI một câu → gợi ý các TRANG học liệu của lớp nên đọc lại.

Truy vấn = thân câu + nội dung đáp án đúng (BM25 + từ điển đồng nghĩa của môn). Các lựa chọn khác đã ĐO trên bộ câu
hỏi chuẩn (eval/rag_gold.json, `python -m app.services.rag.evaluate`, bảng "gợi ý theo trang") và bỏ vì không giúp:
  - bỏ từ khuôn mẫu của đề ("nào sau đây", "là gì"...): không đổi chỉ số – hư từ + IDF đã lo;
  - trộn thêm truy vấn PHƯƠNG ÁN SAI sinh viên chọn bằng RRF: Hit@1 0,78 → 0,54 (trọng số 0,25) / 0,46 (×1) – kéo
    lên các đoạn nhắc CẢ hai khái niệm (trang tổng quan) chen mất trang giải thích chính. Giữ hàm (wrong_weight) để
    đo lại khi có bộ nhãn cho "trang giải thích chỗ nhầm".
Cổng ngữ nghĩa (semantic.py): không đoạn ứng viên nào đủ gần câu hỏi (cos MiniLM) → không gợi ý gì – tài liệu của lớp
không nói về câu hỏi (BM25 thì luôn trả về "đoạn gần nhất"); qua cổng thì giữ nguyên thứ tự BM25.
Kết quả gom theo TRANG (sinh viên mở một trang, không mở một "đoạn"): mỗi trang lấy hạng của đoạn tốt nhất, kèm
khung tô của đoạn đó.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session, undefer

from ...models import ClassSection, Course, MaterialPage, MaterialPassage, Question, SectionMaterial

RRF_K = 60
DEPTH = 30                  # số đoạn lấy về trước khi gom theo trang
PAGES = 3                   # số trang gợi ý cho một câu
SNIPPET = 240


def fuse(lists: list[tuple[list, float]], k: int = RRF_K) -> list:
    """Reciprocal Rank Fusion có trọng số: Σ w / (k + hạng) – trộn theo HẠNG (điểm BM25 không có trần, hai truy vấn
    dài ngắn khác nhau không so được). Hòa điểm: giữ thứ tự xuất hiện đầu tiên."""
    score: dict = {}
    for items, w in lists:
        for r, x in enumerate(items, 1):
            score[x] = score.get(x, 0.0) + w / (k + r)
    return sorted(score, key=lambda x: -score[x])


def query_text(stem: str, correct: list[str]) -> str:
    return stem + "\n" + "\n".join(correct)


def rank_passages(ix, stem: str, correct: list[str], wrong: str | None = None, synonyms=None,
                  wrong_weight: float = 0.0) -> list[int]:
    """Id đoạn theo thứ tự gợi ý (ix: search.Index của lớp). wrong / wrong_weight: chỉ để đo (mặc định không dùng)."""
    first = [i for i, _, _ in ix.score(query_text(stem, correct), DEPTH, synonyms)]
    if not wrong or not wrong_weight:
        return first
    return fuse([(first, 1.0), ([i for i, _, _ in ix.score(wrong, DEPTH, synonyms)], wrong_weight)])


def pages_of(ranked: list[int], page_of) -> list:
    """Gom đoạn theo trang, giữ thứ tự xuất hiện đầu tiên: [(trang, id đoạn tốt nhất của trang)]."""
    seen, out = set(), []
    for pid in ranked:
        pg = page_of(pid)
        if pg not in seen:
            seen.add(pg)
            out.append((pg, pid))
    return out


@dataclass
class PageSuggestion:
    material_id: int
    material_title: str
    file_name: str
    url: str | None                 # tệp trên Moodle (SV xem được) + "#page=N"
    page_no: int
    title: str                      # đề mục của đoạn tốt nhất trên trang
    snippet: str
    bboxes: list = field(default_factory=list)


def for_question(db: Session, cs_id: int, question: Question, k: int = PAGES) -> list[PageSuggestion]:
    """Các trang học liệu của lớp nên đọc lại khi làm sai câu hỏi (chỉ học liệu 'ready' của đúng lớp)."""
    from . import search, semantic, synonyms                     # tránh vòng import khi nạp models

    correct = [o.content for o in question.options if o.is_correct]
    if not correct:                                              # câu tự luận / chưa có đáp án: không gợi ý
        return []
    code = (db.query(Course.course_code).join(ClassSection, ClassSection.course_id == Course.id)
            .filter(ClassSection.id == cs_id).scalar())
    ranked = rank_passages(search.section_index(db, cs_id), question.content, correct, synonyms=synonyms.for_course(code))
    if not ranked:
        return []
    rows = {p.id: (p, pg, m) for p, pg, m in
            db.query(MaterialPassage, MaterialPage, SectionMaterial)
            .join(MaterialPage, MaterialPage.id == MaterialPassage.page_id)
            .join(SectionMaterial, SectionMaterial.id == MaterialPassage.material_id)
            .options(undefer(MaterialPassage.embedding))
            .filter(MaterialPassage.id.in_(ranked), SectionMaterial.class_section_id == cs_id,
                    SectionMaterial.status == "ready")}
    live = [pid for pid in ranked if pid in rows]                # bản chỉ mục cũ: bỏ đoạn đã bị nạp lại / bỏ chọn
    if not semantic.related(query_text(question.content, correct), [rows[pid][0].embedding for pid in live]):
        return []
    out = []
    for (_, _), pid in pages_of(live, lambda i: (rows[i][2].id, rows[i][1].page_no))[:k]:
        p, pg, m = rows[pid]
        url = f"{m.moodle_file_url}#page={pg.page_no}" if m.moodle_file_url else None
        out.append(PageSuggestion(m.id, m.title, m.file_name, url, pg.page_no, p.title, p.body[:SNIPPET], p.bboxes))
    return out


def for_questions(db: Session, cs_id: int, question_ids: list[int], k: int = PAGES) -> dict[int, list]:
    """Gợi ý cho từng câu (tính MỘT lần mỗi câu, dùng chung cho mọi SV làm sai câu đó)."""
    qs = db.query(Question).filter(Question.id.in_(question_ids)).all() if question_ids else []
    return {q.id: for_question(db, cs_id, q, k) for q in qs}
