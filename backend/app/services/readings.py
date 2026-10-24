"""Gợi ý đọc: câu SV làm sai → trang/slide cụ thể trong học liệu của học phần (RAG theo từng khóa học)."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.orm import Session

from . import materials

PER_QUESTION = 2        # mỗi câu sai gợi ý tối đa vài đoạn
PER_PATH = 8            # mỗi SV hiện tối đa vài chỗ cần đọc (ưu tiên chỗ nhiều câu sai cùng trỏ tới)


def question_texts(db: Session, question_ids: list[int]) -> dict[int, dict]:
    """Nội dung câu hỏi + đáp án đúng (truy vấn gồm cả hai: đáp án đúng chứa thuật ngữ cần ôn)."""
    if not question_ids:
        return {}
    ids = ",".join(str(int(i)) for i in set(question_ids))
    out = {r.id: {"content": r.content, "outline_id": r.outline_id, "correct": ""} for r in
           db.execute(text(f"SELECT id, content, outline_id FROM question_bank WHERE id IN ({ids})"))}
    for r in db.execute(text(f"SELECT question_id, content FROM question_options WHERE is_correct=1 AND question_id IN ({ids})")):
        out[r.question_id]["correct"] = r.content
    return out


def readings_for_questions(db: Session, course_id: int, wrong_qids: list[int], qtexts: dict[int, dict],
                           cache: dict | None = None, limit: int = PER_PATH) -> list[dict]:
    """Gộp gợi ý của các câu sai: một đoạn được nhiều câu sai trỏ tới thì xếp trước.
    cache: kết quả tìm theo từng câu (dùng chung khi tính cho nhiều SV/nhóm trong một yêu cầu)."""
    cache = {} if cache is None else cache
    agg: dict[int, dict] = {}
    votes: dict[int, set] = defaultdict(set)
    for qid in dict.fromkeys(wrong_qids):
        qt = qtexts.get(qid)
        if not qt:
            continue
        if qid not in cache:
            cache[qid] = materials.search(db, course_id, f"{qt['content']} {qt['correct']}", k=PER_QUESTION, outline_id=qt["outline_id"])
        for rank, hit in enumerate(cache[qid], 1):
            a = agg.setdefault(hit["chunk_id"], {**hit, "questions": [], "best_rank": rank, "sum": 0.0})
            a["sum"] += hit["score"]
            a["best_rank"] = min(a["best_rank"], rank)
            votes[hit["chunk_id"]].add(qid)
    for cid, a in agg.items():
        a["questions"] = sorted(votes[cid])
    return sorted(agg.values(), key=lambda a: (-len(a["questions"]), a["best_rank"], -a["sum"]))[:limit]


def store(db: Session, path_id: int, readings: list[dict]) -> None:
    db.execute(text("DELETE FROM learning_reading_items WHERE path_id=:p"), {"p": path_id})
    for n, r in enumerate(readings, 1):
        for qid in r["questions"]:
            db.execute(text("""INSERT INTO learning_reading_items (path_id, question_id, chunk_id, rank_no, score)
                               VALUES (:p,:q,:c,:r,:s)"""), {"p": path_id, "q": qid, "c": r["chunk_id"], "r": min(n, 127), "s": r["score"]})


def _short(t: str, n: int = 260) -> str:
    return t[:n] + ("…" if len(t) > n else "")


def for_path(db: Session, path_ids: list[int]) -> dict[int, list[dict]]:
    """Đọc lại gợi ý đã lưu, gom theo path_id → danh sách chỗ cần đọc (đã có tên tài liệu, trang, đoạn trích)."""
    if not path_ids:
        return {}
    ids = ",".join(str(int(i)) for i in path_ids)
    rows = db.execute(text(f"""
        SELECT i.path_id, i.rank_no, i.score, i.question_id, c.id AS chunk_id, c.page_no, c.heading, c.content, c.from_vlm,
               m.id AS material_id, m.title, m.material_type, m.file_ext, m.moodle_cmid,
               o.chapter_number, o.chapter_name
        FROM learning_reading_items i JOIN material_chunks c ON c.id=i.chunk_id JOIN course_materials m ON m.id=c.material_id
        JOIN question_bank q ON q.id=i.question_id LEFT JOIN course_outlines o ON o.id=q.outline_id
        WHERE i.path_id IN ({ids}) ORDER BY i.path_id, i.rank_no""")).mappings().all()
    out: dict[int, dict[int, dict]] = defaultdict(dict)
    for r in rows:
        d = out[r["path_id"]].get(r["chunk_id"])
        if not d:
            d = out[r["path_id"]][r["chunk_id"]] = {
                "material_id": r["material_id"], "material": r["title"], "type": r["material_type"], "page": r["page_no"],
                "unit": "slide" if r["file_ext"] == "pptx" else ("mục" if r["file_ext"] in ("docx", "txt", "md") else "trang"),
                "heading": r["heading"], "snippet": _short(materials.body_of(r["content"], r["heading"])),
                "score": float(r["score"]), "question_ids": [], "moodle_cmid": r["moodle_cmid"],
                "chapter": f"Chương {r['chapter_number']}. {r['chapter_name']}" if r["chapter_number"] else None}
        d["question_ids"].append(r["question_id"])
    return {p: list(v.values()) for p, v in out.items()}
