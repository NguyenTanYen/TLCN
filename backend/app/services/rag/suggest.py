from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session, undefer

from ...models import ClassSection, Course, MaterialPage, MaterialPassage, Question, SectionMaterial

RRF_K = 60
DEPTH = 30
PAGES = 3
SNIPPET = 240
MIN_TERMS = 2
LEX_RATIO = 0.6


def fuse(lists: list[tuple[list, float]], k: int = RRF_K) -> list:
    score: dict = {}
    for items, w in lists:
        for r, x in enumerate(items, 1):
            score[x] = score.get(x, 0.0) + w / (k + r)
    return sorted(score, key=lambda x: -score[x])


def query_text(stem: str, correct: list[str]) -> str:
    return stem + "\n" + "\n".join(correct)


def rank_passages(ix, stem: str, correct: list[str], wrong: str | None = None, synonyms=None,
                  wrong_weight: float = 0.0) -> list[int]:
    first = [i for i, _, _ in ix.score(query_text(stem, correct), DEPTH, synonyms)]
    if not wrong or not wrong_weight:
        return first
    return fuse([(first, 1.0), ([i for i, _, _ in ix.score(wrong, DEPTH, synonyms)], wrong_weight)])


def close_pages(pages: list[tuple], margin: float | None, floor: float | None = None) -> list:
    if not pages:
        return []
    top = max(c for _, c in pages)
    return [pg for pg, c in pages if c == top or ((margin is None or c >= top - margin) and (floor is None or c >= floor))]


def pages_of(ranked: list[int], page_of) -> list:
    seen, out = set(), []
    for pid in ranked:
        pg = page_of(pid)
        if pg not in seen:
            seen.add(pg)
            out.append((pg, pid))
    return out


def lexical_gate(scored: list[tuple], pages: list[tuple], page_key, wanted: frozenset = frozenset()) -> list[tuple]:
    by_pid = {pid: (s, set(m)) for pid, s, m in scored}
    best: dict = {}
    for _, pid in pages:
        s, m = by_pid.get(pid, (0.0, set()))
        if wanted and not m & wanted:
            continue
        best[page_key(pid)] = (s, len({t for t in m if "_" not in t}))
    if not best:
        return []
    top, terms = max(best.values())
    if terms < MIN_TERMS:
        return []
    return [(pg, pid) for pg, pid in pages if pg in best and best[pg][0] >= top * LEX_RATIO]


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
    from ...config import settings
    from . import relevance, search, semantic, synonyms
    from .search import tokens

    correct = [o.content for o in question.options if o.is_correct]
    if not correct:
        return []
    code = (db.query(Course.course_code).join(ClassSection, ClassSection.course_id == Course.id)
            .filter(ClassSection.id == cs_id).scalar())
    ix, syn = search.section_index(db, cs_id), synonyms.for_course(code)
    ranked = rank_passages(ix, question.content, correct, synonyms=syn)
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
    off = relevance.off_topic_ids(db, cs_id)
    live = [pid for pid in ranked if pid in rows and rows[pid][2].id not in off]
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
    else:
        query = query_text(question.content, correct)
        wanted = frozenset(t for t in tokens(query) if relevance.specific(t))
        pages = lexical_gate(ix.score(query, DEPTH, syn), pages, page_key, wanted)
    out = []
    for (_, _), pid in pages:
        p, pg, m = rows[pid]
        url = f"{m.moodle_file_url}#page={pg.page_no}" if m.moodle_file_url else None
        out.append(PageSuggestion(m.id, m.title, m.file_name, url, pg.page_no, p.title, p.body[:SNIPPET], p.bboxes))
    return out


def for_questions(db: Session, cs_id: int, question_ids: list[int], k: int = PAGES) -> dict[int, list]:
    qs = db.query(Question).filter(Question.id.in_(question_ids)).all() if question_ids else []
    return {q.id: for_question(db, cs_id, q, k) for q in qs}
