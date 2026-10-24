"""UC-01: Quản lý câu hỏi & gán CLO; cây CTĐT → PLO → PI → CLO → câu hỏi (góp ý F2a)."""
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import check_course_access, require
from ..models import CLO, CLOPIMapping, PerformanceIndicator, Question, QuestionCLO, QuestionOption, User
from ..schemas import CancelIn, QuestionIn

router = APIRouter(prefix="/api/questions", tags=["UC-01 Ngân hàng câu hỏi"])
LABELS = "ABCDEFGHIJ"


def outcome_paths(db: Session, clo_ids) -> dict[int, list[dict]]:
    """Với mỗi CLO: các PI (kèm PLO, CTĐT) mà CLO đóng góp – để hiện chuỗi PLO › PI › CLO của câu hỏi."""
    out: dict[int, list[dict]] = defaultdict(list)
    ids = list(set(clo_ids))
    if not ids:
        return out
    for r in db.execute(text("""SELECT m.clo_id, m.pi_id, m.level, i.pi_code, i.plo_id, l.plo_code, pr.code AS program_code
                                FROM clo_pi_mapping m JOIN performance_indicators i ON i.id = m.pi_id JOIN plos l ON l.id = i.plo_id
                                JOIN programs pr ON pr.id = l.program_id WHERE m.clo_id IN :ids
                                ORDER BY pr.code, LENGTH(l.plo_code), l.plo_code, i.pi_code""").bindparams(
                                bindparam("ids", expanding=True)), {"ids": ids}).mappings():
        out[r["clo_id"]].append({"pi_id": r["pi_id"], "plo_id": r["plo_id"], "program_code": r["program_code"], "plo_code": r["plo_code"], "pi_code": r["pi_code"],
                                 "level": r["level"]})
    return out


def to_dict(q: Question, stats: dict | None = None, paths: dict | None = None) -> dict:
    return {"id": q.id, "course_id": q.course_id, "outline_id": q.outline_id, "bloom_level_id": q.bloom_level_id,
            "bloom": q.bloom.name_vi if q.bloom else None, "content": q.content, "is_cancelled": q.is_cancelled,
            "cancel_reason": q.cancel_reason, "moodle_question_id": q.moodle_question_id,
            "chapter": f"Chương {q.outline.chapter_number}" if q.outline else None,
            "options": [{"id": o.id, "label": o.opt_label, "content": o.content, "is_correct": o.is_correct} for o in q.options],
            "clos": [{"clo_id": c.clo_id, "clo_code": c.clo.clo_code, "weight": float(c.weight),
                      "pis": (paths or {}).get(c.clo_id, [])} for c in q.clo_links],
            "tagged": bool(q.clo_links) and q.bloom_level_id is not None,
            "usage": stats or {}}


def _get_q(db: Session, u: User, qid: int) -> Question:
    q = db.get(Question, qid)
    if not q:
        raise HTTPException(404, "Không tìm thấy câu hỏi")
    check_course_access(db, u, q.course_id)
    return q


def _validate(db: Session, body: QuestionIn):
    for c in body.clos:
        clo = db.get(CLO, c.clo_id)
        if not clo or clo.course_id != body.course_id:
            raise HTTPException(422, f"CLO {c.clo_id} không thuộc môn học")
    if body.outline_id:
        ok = db.execute(text("SELECT 1 FROM course_outlines WHERE id=:o AND course_id=:c"),
                        {"o": body.outline_id, "c": body.course_id}).scalar()
        if not ok:
            raise HTTPException(422, "Chương không thuộc môn học")


def _usage(db: Session, qid: int) -> dict:
    r = db.execute(text("""SELECT (SELECT COUNT(*) FROM exam_questions WHERE question_id=:q) AS n_exams,
                                  (SELECT COUNT(*) FROM item_level_results WHERE question_id=:q) AS n_results,
                                  (SELECT ROUND(AVG(p_value),3) FROM item_statistics WHERE question_id=:q) AS avg_p,
                                  (SELECT ROUND(AVG(di_value),3) FROM item_statistics WHERE question_id=:q) AS avg_di"""),
                   {"q": qid}).mappings().one()
    return {k: (float(v) if v is not None and k.startswith("avg") else v) for k, v in r.items()}


@router.get("")
def list_questions(course_id: int, clo_id: int | None = None, bloom_level_id: int | None = None, outline_id: int | None = None,
                   include_cancelled: bool = False, untagged: bool = False, q: str | None = None,
                   pi_id: int | None = None, plo_id: int | None = None, db: Session = Depends(get_db),
                   u: User = Depends(require("admin", "lecturer"))):
    check_course_access(db, u, course_id)
    query = db.query(Question).filter(Question.course_id == course_id, Question.question_type == "multichoice")   # câu/ý chấm tay chỉ thuộc bài nhập điểm
    if not include_cancelled:
        query = query.filter(Question.is_cancelled.is_(False))
    if bloom_level_id:
        query = query.filter(Question.bloom_level_id == bloom_level_id)
    if outline_id:
        query = query.filter(Question.outline_id == outline_id)
    if clo_id:
        query = query.filter(Question.clo_links.any(QuestionCLO.clo_id == clo_id))
    if pi_id or plo_id:   # lọc theo nút PI / PLO của cây: câu đo ít nhất một CLO đóng góp cho PI / PLO đó
        sub = db.query(CLOPIMapping.clo_id).join(PerformanceIndicator, PerformanceIndicator.id == CLOPIMapping.pi_id)
        sub = sub.filter(CLOPIMapping.pi_id == pi_id) if pi_id else sub.filter(PerformanceIndicator.plo_id == plo_id)
        query = query.filter(Question.clo_links.any(QuestionCLO.clo_id.in_(sub)))
    if q:
        query = query.filter(Question.content.like(f"%{q}%"))
    if untagged:   # câu nhập hàng loạt chưa gán đủ Bloom + CLO
        query = query.filter((Question.bloom_level_id.is_(None)) | ~Question.clo_links.any())
    items = query.order_by(Question.id).all()
    paths = outcome_paths(db, [c.clo_id for x in items for c in x.clo_links])
    return [to_dict(x, _usage(db, x.id), paths) for x in items]


def _code_key(code: str) -> list:
    """Sắp mã PLO/PI theo số: PLO2 < PLO10, PI1.2 < PI1.10."""
    return [int(t) if t.isdigit() else t for t in code.replace("PLO", " ").replace("PI", " ").replace(".", " ").split()]


@router.get("/tree")
def outcome_tree(course_id: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    """Cây CTĐT → PLO → PI → CLO của học phần với số câu hỏi đang dùng ở mỗi nút (góp ý F2a);
    một câu đo nhiều CLO chỉ được đếm một lần ở nút cha."""
    check_course_access(db, u, course_id)
    by_clo: dict[int, set] = defaultdict(set)
    for qid, clo_id in db.execute(text("""SELECT m.question_id, m.clo_id FROM question_clo_mapping m JOIN question_bank q ON q.id = m.question_id
                                          WHERE q.course_id = :c AND q.is_cancelled = 0 AND q.question_type = 'multichoice'"""),
                                  {"c": course_id}):
        by_clo[clo_id].add(qid)
    clos = db.query(CLO).filter_by(course_id=course_id).order_by(CLO.clo_code).all()
    progs: dict[int, dict] = {}
    for clo in clos:
        for link in clo.pi_links:
            pi, plo = link.pi, link.pi.plo
            g = progs.setdefault(plo.program_id, {"program_id": plo.program_id, "_q": set(), "plos": {}})
            pn = g["plos"].setdefault(plo.id, {"id": plo.id, "plo_code": plo.plo_code, "description": plo.description,
                                               "_q": set(), "pis": {}})
            node = pn["pis"].setdefault(pi.id, {"id": pi.id, "pi_code": pi.pi_code, "description": pi.description,
                                                "_q": set(), "clos": []})
            node["clos"].append({"id": clo.id, "clo_code": clo.clo_code, "description": clo.description, "level": link.level,
                                 "n": len(by_clo[clo.id])})
            for x in (node, pn, g):
                x["_q"] |= by_clo[clo.id]
    names = {r[0]: (r[1], r[2]) for r in db.execute(text("SELECT id, code, name FROM programs"))}
    tree = []
    for g in sorted(progs.values(), key=lambda x: names.get(x["program_id"], ("", ""))[0]):
        plos = []
        for pn in sorted(g.pop("plos").values(), key=lambda x: _code_key(x["plo_code"])):
            pis = sorted(pn.pop("pis").values(), key=lambda x: _code_key(x["pi_code"]))
            for i in pis:
                i["n"] = len(i.pop("_q"))
            plos.append(pn | {"n": len(pn.pop("_q")), "pis": pis})
        code, name = names.get(g["program_id"], ("", ""))
        tree.append({"program_id": g["program_id"], "program_code": code, "program_name": name, "n": len(g.pop("_q")), "plos": plos})
    counts = db.execute(text("""SELECT SUM(is_cancelled = 0), SUM(is_cancelled = 1),
                                       SUM(is_cancelled = 0 AND (bloom_level_id IS NULL OR NOT EXISTS
                                           (SELECT 1 FROM question_clo_mapping m WHERE m.question_id = q.id)))
                                FROM question_bank q WHERE course_id = :c AND question_type = 'multichoice'"""), {"c": course_id}).one()
    return {"total": int(counts[0] or 0), "cancelled": int(counts[1] or 0), "untagged": int(counts[2] or 0), "programs": tree,
            "clos_without_pi": [{"id": c.id, "clo_code": c.clo_code, "description": c.description, "n": len(by_clo[c.id])}
                                for c in clos if not c.pi_links]}


@router.get("/{qid}")
def get_question(qid: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    q = _get_q(db, u, qid)
    return to_dict(q, _usage(db, qid), outcome_paths(db, [c.clo_id for c in q.clo_links]))


@router.post("", status_code=201)
def create_question(body: QuestionIn, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    check_course_access(db, u, body.course_id)
    _validate(db, body)
    q = Question(course_id=body.course_id, outline_id=body.outline_id, bloom_level_id=body.bloom_level_id,
                 content=body.content, created_by=u.id)
    for i, o in enumerate(body.options):
        q.options.append(QuestionOption(position=i + 1, opt_label=LABELS[i], content=o.content, is_correct=o.is_correct))
    for c in body.clos:
        q.clo_links.append(QuestionCLO(clo_id=c.clo_id, weight=c.weight))
    db.add(q); db.commit(); db.refresh(q)
    return to_dict(q)


@router.put("/{qid}")
def update_question(qid: int, body: QuestionIn, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    q = _get_q(db, u, qid)
    if body.course_id != q.course_id:
        raise HTTPException(422, "Không được chuyển câu hỏi sang môn học khác")
    if _usage(db, qid)["n_results"]:
        raise HTTPException(409, "Câu hỏi đã có kết quả thi – không được sửa nội dung/đáp án; hãy Hủy và tạo câu mới")
    same_body = q.content == body.content and [(o.content, bool(o.is_correct)) for o in q.options] == \
        [(o.content, bool(o.is_correct)) for o in body.options]
    on_moodle = db.execute(text("""SELECT 1 FROM exam_questions eq JOIN exams e ON e.id=eq.exam_id WHERE eq.question_id=:q
                                   AND (e.moodle_quiz_id IS NOT NULL OR e.moodle_offlinequiz_id IS NOT NULL) LIMIT 1"""),
                           {"q": qid}).scalar()
    if on_moodle and not same_body:
        raise HTTPException(409, "Câu hỏi đã nằm trong đề trên Moodle – chỉ được sửa CLO/Bloom/chương; "
                                 "muốn sửa nội dung/đáp án hãy Hủy và tạo câu mới")
    _validate(db, body)
    q.outline_id, q.bloom_level_id, q.content = body.outline_id, body.bloom_level_id, body.content
    q.options.clear(); q.clo_links.clear(); db.flush()
    for i, o in enumerate(body.options):
        q.options.append(QuestionOption(position=i + 1, opt_label=LABELS[i], content=o.content, is_correct=o.is_correct))
    for c in body.clos:
        q.clo_links.append(QuestionCLO(clo_id=c.clo_id, weight=c.weight))
    db.commit(); db.refresh(q)
    return to_dict(q)


@router.patch("/{qid}/cancel")
def cancel_question(qid: int, body: CancelIn, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    q = _get_q(db, u, qid)
    q.is_cancelled, q.cancel_reason = True, body.reason
    db.commit()
    return {"id": qid, "is_cancelled": True}


@router.delete("/{qid}")
def delete_question(qid: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    q = _get_q(db, u, qid)
    if _usage(db, qid)["n_exams"]:
        raise HTTPException(409, "Câu hỏi đã được dùng trong đề – chỉ được Hủy, không được xóa")
    db.delete(q); db.commit()
    return {"deleted": qid}
