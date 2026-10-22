"""Phụ đạo (góp ý 15/10): mỗi SV trả lời sai bao nhiêu câu → bấm vào SV xem danh sách câu sai → tạo bài KT phụ đạo riêng
cho một SV hoặc một nhóm SV (câu đã sai + câu tương tự cùng CLO/chương trong ngân hàng câu hỏi).

Bài phụ đạo là bài KT bình thường của lớp HP (phát hành lên Moodle Quiz hoặc in giấy, chấm như mọi bài) nhưng mặc định
KHÔNG gộp vào minh chứng CLO (counts_for_clo = 0), có parent_exam_id = bài gốc và target_students = MSSV được giao.

Góp ý F5: Quiz phụ đạo trên Moodle chỉ các SV được giao thấy và làm được (nhóm Moodle + điều kiện truy cập, xem
routers/lms.py), và theo dõi tiến bộ của từng SV: tỷ lệ điểm trên chính các câu đó ở bài trước → ở bài phụ đạo.
"""
import random
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import check_section_access, require
from ..models import Exam, ExamQuestion, User

router = APIRouter(prefix="/api", tags=["Ôn tập theo câu trả lời sai (phụ đạo)"])


class RemedialIn(BaseModel):
    student_ids: list[int] = Field(min_length=1)
    exam_ids: list[int] = []                    # rỗng = mọi bài đã phân tích của lớp
    exam_title: Optional[str] = Field(default=None, max_length=255)
    exam_type: Literal["online", "paper"] = "online"
    similar_per_question: int = Field(default=1, ge=0, le=3, description="Số câu tương tự (cùng CLO, cùng chương) thêm cho mỗi câu sai")
    include_wrong: bool = True                  # đưa lại chính các câu đã sai
    max_questions: int = Field(default=40, ge=1, le=200)
    max_score: float = Field(default=10, gt=0, le=100)
    seed: Optional[int] = None


def _exam_ids(db: Session, cs_id: int, ids: list[int]) -> list[int]:
    all_ids = [r[0] for r in db.execute(text("""SELECT id FROM exams WHERE class_section_id=:cs AND status='Analyzed'
                                                ORDER BY COALESCE(exam_date, created_at), id"""), {"cs": cs_id})]
    if ids:
        bad = set(ids) - set(all_ids)
        if bad:
            raise HTTPException(422, f"Bài KT {sorted(bad)} không thuộc lớp hoặc chưa phân tích")
        return ids
    return all_ids


def _wrong_rows(db: Session, exam_ids: list[int], student_id: int | None = None):
    """Mọi câu (không bị Hủy) SV làm chưa đúng/chưa đủ điểm: sai, bỏ trống, hoặc câu nhập điểm chưa đạt điểm tối đa."""
    if not exam_ids:
        return []
    q = text("""SELECT a.exam_id, e.exam_title, a.student_id, r.question_id, r.response_status, r.score_earned, eq.points, eq.order_index,
                       q.content, q.question_type, q.outline_id, o.chapter_number, o.chapter_name,
                       so.opt_label AS chosen_label, so.content AS chosen_content,
                       (SELECT co.opt_label FROM question_options co WHERE co.question_id=q.id AND co.is_correct) AS correct_label,
                       (SELECT co.content FROM question_options co WHERE co.question_id=q.id AND co.is_correct) AS correct_content,
                       (SELECT GROUP_CONCAT(c.clo_code ORDER BY c.clo_code) FROM question_clo_mapping m JOIN clos c ON c.id=m.clo_id
                         WHERE m.question_id=q.id) AS clos,
                       (SELECT vq.position FROM exam_version_questions vq WHERE vq.version_id=a.version_id AND vq.question_id=q.id) AS version_pos
                FROM item_level_results r JOIN exam_attempts a ON a.id=r.attempt_id JOIN exams e ON e.id=a.exam_id
                JOIN exam_questions eq ON eq.exam_id=a.exam_id AND eq.question_id=r.question_id
                JOIN question_bank q ON q.id=r.question_id
                LEFT JOIN course_outlines o ON o.id=q.outline_id LEFT JOIN question_options so ON so.id=r.selected_option_id
                WHERE a.exam_id IN :ids AND a.status='finished' AND q.is_cancelled=0 AND r.score_earned + 0.0001 < eq.points
                  AND (:s IS NULL OR a.student_id=:s)
                ORDER BY a.exam_id, eq.order_index""").bindparams(bindparam("ids", expanding=True))
    return [dict(r) for r in db.execute(q, {"ids": exam_ids, "s": student_id}).mappings()]


@router.get("/class-sections/{cs_id}/remedial")
def remedial_overview(cs_id: int, exam_ids: str = "", u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """Bảng tổng hợp: mỗi SV sai bao nhiêu câu (trên các bài chọn), CLO chưa đạt; mỗi câu bao nhiêu SV sai."""
    check_section_access(db, u, cs_id)
    ids = _exam_ids(db, cs_id, [int(x) for x in exam_ids.split(",") if x.strip().isdigit()])
    exams = [dict(r) for r in db.execute(text("""SELECT id, exam_title, exam_type, parent_exam_id, counts_for_clo,
                                                  (SELECT COUNT(*) FROM exam_questions eq JOIN question_bank q ON q.id=eq.question_id
                                                   WHERE eq.exam_id=e.id AND q.is_cancelled=0) AS n_questions
                                                  FROM exams e WHERE class_section_id=:cs AND status='Analyzed' ORDER BY id"""),
                                          {"cs": cs_id}).mappings()]
    if not ids:
        return {"exams": exams, "selected": [], "students": [], "questions": []}
    q = text("""SELECT s.id AS student_id, s.student_code, s.full_name, COUNT(DISTINCT a.exam_id) AS n_exams,
                       SUM(q.is_cancelled = 0) AS n_items,
                       SUM(q.is_cancelled = 0 AND r.score_earned + 0.0001 < eq.points) AS n_wrong,
                       SUM(q.is_cancelled = 0 AND r.response_status = 'blank') AS n_blank
                FROM exam_attempts a JOIN students s ON s.id=a.student_id
                JOIN item_level_results r ON r.attempt_id=a.id
                JOIN exam_questions eq ON eq.exam_id=a.exam_id AND eq.question_id=r.question_id
                JOIN question_bank q ON q.id=r.question_id
                WHERE a.exam_id IN :ids AND a.status='finished'
                GROUP BY s.id, s.student_code, s.full_name ORDER BY n_wrong DESC, s.student_code""").bindparams(bindparam("ids", expanding=True))
    studs = [dict(r) for r in db.execute(q, {"ids": ids}).mappings()]
    q = text("""SELECT a.student_id, c.clo_code FROM attempt_clo_results r JOIN exam_attempts a ON a.id=r.attempt_id
                JOIN clos c ON c.id=r.clo_id WHERE a.exam_id IN :ids AND a.status='finished' AND NOT r.is_achieved""").bindparams(
        bindparam("ids", expanding=True))
    weak = {}
    for r in db.execute(q, {"ids": ids}):
        weak.setdefault(r[0], set()).add(r[1])
    for s in studs:
        for k in ("n_items", "n_wrong", "n_blank"):
            s[k] = int(s[k] or 0)
        s["wrong_pct"] = round(100 * s["n_wrong"] / s["n_items"], 1) if s["n_items"] else 0
        s["weak_clos"] = sorted(weak.get(s["student_id"], []))
    q = text("""SELECT eq.exam_id, eq.order_index, q.id AS question_id, LEFT(q.content, 200) AS content, q.question_type,
                       COUNT(r.id) AS n_students, SUM(r.score_earned + 0.0001 < eq.points) AS n_wrong,
                       (SELECT GROUP_CONCAT(c.clo_code ORDER BY c.clo_code) FROM question_clo_mapping m JOIN clos c ON c.id=m.clo_id
                         WHERE m.question_id=q.id) AS clos
                FROM exam_questions eq JOIN question_bank q ON q.id=eq.question_id
                JOIN exam_attempts a ON a.exam_id=eq.exam_id AND a.status='finished'
                JOIN item_level_results r ON r.attempt_id=a.id AND r.question_id=q.id
                WHERE eq.exam_id IN :ids AND q.is_cancelled=0
                GROUP BY eq.exam_id, eq.order_index, q.id, q.content, q.question_type
                ORDER BY n_wrong DESC, eq.exam_id, eq.order_index""").bindparams(bindparam("ids", expanding=True))
    qs = [dict(r) for r in db.execute(q, {"ids": ids}).mappings()]
    for x in qs:
        x["n_wrong"] = int(x["n_wrong"] or 0)
        x["wrong_pct"] = round(100 * x["n_wrong"] / x["n_students"], 1) if x["n_students"] else 0
    return {"exams": exams, "selected": ids, "students": studs, "questions": qs}


def target_moodle_users(db: Session, e: Exam) -> list[int]:
    """Tài khoản Moodle của các SV được giao bài phụ đạo; thiếu tài khoản thì báo lỗi trước khi tạo gì trên Moodle."""
    codes = [x.strip() for x in (e.target_students or "").split(",") if x.strip()]
    if not codes:
        return []
    rows = db.execute(text("""SELECT s.student_code, s.moodle_user_id FROM students s JOIN enrollments en ON en.student_id=s.id
                              WHERE en.class_section_id=:cs AND s.student_code IN :codes""").bindparams(bindparam("codes", expanding=True)),
                      {"cs": e.class_section_id, "codes": codes}).all()
    found = {r[0]: r[1] for r in rows}
    missing = [c for c in codes if not found.get(c)]
    if missing:
        raise HTTPException(422, f"SV {', '.join(missing)} chưa gắn tài khoản Moodle (hoặc không thuộc lớp) – đồng bộ danh sách SV từ Moodle trước")
    return [int(found[c]) for c in codes]


def _pct(db: Session, exam_ids: list[int], student_id: int, qids: list[int]):
    """Tỷ lệ điểm (%) của SV trên các câu qids ở các bài exam_ids (bài đã nộp); chưa làm câu nào → None."""
    if not exam_ids or not qids:
        return None
    r = db.execute(text("""SELECT SUM(r.score_earned), SUM(eq.points) FROM item_level_results r JOIN exam_attempts a ON a.id=r.attempt_id
                           JOIN exam_questions eq ON eq.exam_id=a.exam_id AND eq.question_id=r.question_id
                           WHERE a.exam_id IN :e AND a.student_id=:s AND a.status='finished' AND r.question_id IN :q""").bindparams(
                       bindparam("e", expanding=True), bindparam("q", expanding=True)),
                   {"e": exam_ids, "s": student_id, "q": qids}).one()
    return round(100 * float(r[0]) / float(r[1]), 1) if r[1] else None


@router.get("/class-sections/{cs_id}/remedial-exams")
def remedial_progress(cs_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """Các bài phụ đạo của lớp và tiến bộ của từng SV được giao (góp ý F5):
    - before_pct: điểm trên các câu của bài phụ đạo mà SV đã làm ở các bài KT chính thức trước đó (câu đã sai được đưa lại);
    - after_same_pct: điểm trên chính các câu đó ở bài phụ đạo; after_pct: điểm cả bài phụ đạo (gồm câu tương tự)."""
    check_section_access(db, u, cs_id)
    regular = [r[0] for r in db.execute(text("""SELECT id FROM exams WHERE class_section_id=:cs AND target_students IS NULL
                                                AND status IN ('Synced','Analyzed')"""), {"cs": cs_id})]
    out = []
    for e in db.query(Exam).filter(Exam.class_section_id == cs_id, Exam.target_students.isnot(None)).order_by(Exam.id):
        qids = [q.question_id for q in e.questions if not q.question.is_cancelled]
        codes = [x.strip() for x in e.target_students.split(",") if x.strip()]
        studs = db.execute(text("""SELECT s.id, s.student_code, s.full_name FROM students s WHERE s.student_code IN :c""").bindparams(
            bindparam("c", expanding=True)), {"c": codes}).mappings().all() if codes else []
        by_code = {s["student_code"]: s for s in studs}
        rows = []
        for code in codes:
            s = by_code.get(code)
            if not s:
                continue
            seen = [r[0] for r in db.execute(text("""SELECT DISTINCT r.question_id FROM item_level_results r JOIN exam_attempts a ON a.id=r.attempt_id
                                                     WHERE a.student_id=:s AND a.status='finished' AND a.exam_id IN :e AND r.question_id IN :q""").bindparams(
                bindparam("e", expanding=True), bindparam("q", expanding=True)), {"s": s["id"], "e": regular or [0], "q": qids or [0]})]
            st = db.execute(text("SELECT status FROM exam_attempts WHERE exam_id=:e AND student_id=:s ORDER BY status='finished' DESC LIMIT 1"),
                            {"e": e.id, "s": s["id"]}).scalar()
            before, after_same = _pct(db, regular, s["id"], seen), _pct(db, [e.id], s["id"], seen)
            rows.append({"student_id": s["id"], "student_code": code, "full_name": s["full_name"], "n_reused": len(seen),
                         "before_pct": before, "after_same_pct": after_same, "after_pct": _pct(db, [e.id], s["id"], qids),
                         "gain": round(after_same - before, 1) if before is not None and after_same is not None else None,
                         "status": st or "not_started"})
        done = [r for r in rows if r["gain"] is not None]
        out.append({"exam_id": e.id, "exam_title": e.exam_title, "exam_type": e.exam_type, "status": e.status,
                    "parent_exam_id": e.parent_exam_id, "moodle_quiz_id": e.moodle_quiz_id, "n_questions": len(qids),
                    "n_targets": len(codes), "n_done": sum(1 for r in rows if r["status"] == "finished"),
                    "avg_gain": round(sum(r["gain"] for r in done) / len(done), 1) if done else None, "students": rows})
    return out


@router.get("/class-sections/{cs_id}/remedial/students/{student_id}")
def student_wrong(cs_id: int, student_id: int, exam_ids: str = "", u: User = Depends(require("admin", "lecturer")),
                  db: Session = Depends(get_db)):
    """Danh sách câu SV trả lời sai/bỏ trống (kèm phương án đã chọn, đáp án đúng, CLO, chương)."""
    check_section_access(db, u, cs_id)
    st = db.execute(text("SELECT id, student_code, full_name FROM students WHERE id=:s"), {"s": student_id}).mappings().first()
    if not st:
        raise HTTPException(404, "Không tìm thấy sinh viên")
    ids = _exam_ids(db, cs_id, [int(x) for x in exam_ids.split(",") if x.strip().isdigit()])
    rows = _wrong_rows(db, ids, student_id)
    for r in rows:
        r["points"] = float(r["points"]); r["score_earned"] = float(r["score_earned"])
    return {"student": dict(st), "exam_ids": ids, "wrong": rows}


@router.post("/class-sections/{cs_id}/remedial-exams", status_code=201)
def create_remedial(cs_id: int, body: RemedialIn, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """Tạo bài KT phụ đạo: câu trắc nghiệm các SV đã chọn làm sai (+ câu tương tự cùng CLO/chương chưa gặp)."""
    cs = check_section_access(db, u, cs_id)
    ids = _exam_ids(db, cs_id, body.exam_ids)
    enrolled = {r[0]: r[1] for r in db.execute(text("""SELECT s.id, s.student_code FROM enrollments e JOIN students s ON s.id=e.student_id
                                                       WHERE e.class_section_id=:cs"""), {"cs": cs_id})}
    if any(s not in enrolled for s in body.student_ids):
        raise HTTPException(422, "Có SV không thuộc lớp học phần")
    wrong = [r for sid in body.student_ids for r in _wrong_rows(db, ids, sid) if r["question_type"] == "multichoice"]
    if not wrong:
        raise HTTPException(422, "Các SV đã chọn không có câu trắc nghiệm nào làm sai trong các bài đã chọn")
    freq = {}
    for r in wrong:
        freq[r["question_id"]] = freq.get(r["question_id"], 0) + 1
    base = sorted(freq, key=lambda q: -freq[q])                # câu nhiều SV sai nhất trước
    seen = {r[0] for r in db.execute(text("""SELECT DISTINCT eq.question_id FROM exam_questions eq JOIN exams e ON e.id=eq.exam_id
                                             WHERE e.class_section_id=:cs"""), {"cs": cs_id})}
    pool = {}
    for r in db.execute(text("""SELECT q.id, q.outline_id, GROUP_CONCAT(m.clo_id) FROM question_bank q JOIN question_clo_mapping m ON m.question_id=q.id
                                WHERE q.course_id=:c AND q.is_cancelled=0 AND q.question_type='multichoice' AND q.bloom_level_id IS NOT NULL
                                GROUP BY q.id, q.outline_id"""), {"c": cs.course_id}):
        pool[r[0]] = (r[1], set(int(x) for x in str(r[2]).split(",")))
    rng = random.Random(body.seed)
    chosen = []
    used = set()
    for qid in base:
        if body.include_wrong and qid not in used:
            chosen.append(qid); used.add(qid)
        if body.similar_per_question and qid in pool:
            o, cl = pool[qid]
            cands = [x for x, (o2, c2) in pool.items() if x not in used and x not in seen and c2 & cl]
            cands.sort(key=lambda x: (pool[x][0] != o, rng.random()))   # ưu tiên cùng chương
            for x in cands[:body.similar_per_question]:
                chosen.append(x); used.add(x)
        if len(chosen) >= body.max_questions:
            break
    chosen = chosen[:body.max_questions]
    if not chosen:
        raise HTTPException(422, "Không chọn được câu nào (bật 'đưa lại câu đã sai' hoặc bổ sung câu hỏi cùng CLO vào ngân hàng)")
    n = len(chosen)
    each = round(body.max_score / n, 2)
    codes = [enrolled[s] for s in body.student_ids]
    title = body.exam_title or (f"Ôn tập – {codes[0]}" if len(codes) == 1 else f"Ôn tập – nhóm {len(codes)} SV")
    e = Exam(class_section_id=cs.id, exam_title=title[:255], assessment_type="process", exam_type=body.exam_type,
             max_score=body.max_score, counts_for_clo=False, parent_exam_id=ids[-1] if ids else None,
             target_students=",".join(codes), created_by=u.id)
    for i, qid in enumerate(chosen, 1):
        e.questions.append(ExamQuestion(question_id=qid, order_index=i, points=each if i < n else round(body.max_score - each * (n - 1), 2)))
    db.add(e); db.commit()
    return {"id": e.id, "n_questions": n, "n_wrong_reused": sum(1 for q in chosen if q in freq), "n_similar": sum(1 for q in chosen if q not in freq),
            "target_students": codes}
