"""Bước 8: sinh viên làm SAI một câu → gợi ý các TRANG học liệu của lớp nên đọc lại."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session, undefer

from ...models import ClassSection, Course, MaterialPage, MaterialPassage, Question, SectionMaterial

RRF_K = 60
DEPTH = 30
PAGES = 3
SNIPPET = 240


def fuse(lists: list[tuple[list, float]], k: int = RRF_K) -> list:
    """Reciprocal Rank Fusion có trọng số: Σ w / (k + hạng) – trộn theo HẠNG (điểm BM25 không có trần, hai truy vấn dài ngắn khác nhau không so được)."""
    score: dict = {}
    for items, w in lists:
        for r, x in enumerate(items, 1):
            score[x] = score.get(x, 0.0) + w / (k + r)
    return sorted(score, key=lambda x: -score[x])


def query_text(stem: str, correct: list[str]) -> str:
    return stem + "\n" + "\n".join(correct)


def rank_passages(ix, stem: str, correct: list[str], wrong: str | None = None, synonyms=None,
                  wrong_weight: float = 0.0) -> list[int]:
    """Id đoạn theo thứ tự gợi ý (ix: search.Index của lớp)."""
    first = [i for i, _, _ in ix.score(query_text(stem, correct), DEPTH, synonyms)]
    if not wrong or not wrong_weight:
        return first
    return fuse([(first, 1.0), ([i for i, _, _ in ix.score(wrong, DEPTH, synonyms)], wrong_weight)])


def close_pages(pages: list[tuple], margin: float | None, floor: float | None = None) -> list:
    """[(trang, cos cao nhất của các đoạn ứng viên trên trang)] theo thứ tự gợi ý → các trang giữ lại (giữ thứ tự): bỏ trang có cos thấp hơn trang gần câu hỏi nhất quá margin, hoặc thấp hơn floor."""
    if not pages:
        return []
    top = max(c for _, c in pages)
    return [pg for pg, c in pages if c == top or ((margin is None or c >= top - margin) and (floor is None or c >= floor))]


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
    url: str | None
    page_no: int
    title: str
    snippet: str
    bboxes: list = field(default_factory=list)


def for_question(db: Session, cs_id: int, question: Question, k: int = PAGES) -> list[PageSuggestion]:
    """Các trang học liệu của lớp nên đọc lại khi làm sai câu hỏi (chỉ học liệu 'ready' của đúng lớp)."""
    from ...config import settings
    from . import search, semantic, synonyms

    correct = [o.content for o in question.options if o.is_correct]
    if not correct:
        return []
    code = (db.query(Course.course_code).join(ClassSection, ClassSection.course_id == Course.id)
            .filter(ClassSection.id == cs_id).scalar())
    ranked = rank_passages(search.section_index(db, cs_id), question.content, correct, synonyms=synonyms.for_course(code))
    try:
        dense = [pid for pid, _ in semantic.dense_top(db, cs_id, query_text(question.content, correct), DEPTH)]
    except Exception:
        dense = []
    if dense:
        seen = set(ranked)
        ranked = (ranked + [pid for pid in dense if pid not in seen])[:DEPTH]
    if not ranked:
        return []
    rows = {p.id: (p, pg, m) for p, pg, m in
            db.query(MaterialPassage, MaterialPage, SectionMaterial)
            .join(MaterialPage, MaterialPage.id == MaterialPassage.page_id)
            .join(SectionMaterial, SectionMaterial.id == MaterialPassage.material_id)
            .options(undefer(MaterialPassage.embedding))
            .filter(MaterialPassage.id.in_(ranked), SectionMaterial.class_section_id == cs_id,
                    SectionMaterial.status == "ready")}
    live = [pid for pid in ranked if pid in rows]
    page_key = lambda i: (rows[i][2].id, rows[i][1].page_no)
    pages = pages_of(live, page_key)[:k]
    cos = semantic.scores(query_text(question.content, correct), [rows[pid][0].embedding for pid in live])
    if cos is not None:
        if max(cos) < settings.rag_min_similarity:
            return []
        best: dict = {}
        for pid, c in zip(live, cos):
            best[page_key(pid)] = max(best.get(page_key(pid), -1.0), c)
        keep = set(close_pages([(pg, best[pg]) for pg, _ in pages], settings.rag_page_margin))
        pages = [(pg, pid) for pg, pid in pages if pg in keep]
    out = []
    for (_, _), pid in pages:
        p, pg, m = rows[pid]
        url = f"{m.moodle_file_url}#page={pg.page_no}" if m.moodle_file_url else None
        out.append(PageSuggestion(m.id, m.title, m.file_name, url, pg.page_no, p.title, p.body[:SNIPPET], p.bboxes))
    return out


def for_questions(db: Session, cs_id: int, question_ids: list[int], k: int = PAGES) -> dict[int, list]:
    """Gợi ý cho từng câu (tính MỘT lần mỗi câu, dùng chung cho mọi SV làm sai câu đó)."""
    qs = db.query(Question).filter(Question.id.in_(question_ids)).all() if question_ids else []
    return {q.id: for_question(db, cs_id, q, k) for q in qs}
