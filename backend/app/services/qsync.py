"""Đồng bộ ngân hàng câu hỏi HAI CHIỀU giữa hệ thống và Moodle (góp ý 15/10).

Khóa nối giữa hai bên: idnumber "QB-n" của câu trên Moodle = question_bank.id của hệ thống.
* Chiều ĐỌC (Moodle → hệ thống): đọc bản mới nhất của mọi câu Nhiều lựa chọn (một đáp án) trong ngân hàng câu hỏi
  của khóa học Moodle qua kết nối CSDL chỉ đọc (question_bank_entries → question_versions → question → question_answers).
* Chiều GHI (hệ thống → Moodle): Web Service local_clo_sync_questions tạo câu mới hoặc PHIÊN BẢN MỚI (Moodle 4.x),
  và gắn idnumber QB-n cho câu GV soạn trực tiếp trên Moodle sau khi hệ thống nhập câu đó về.

So sánh từng câu cho ra trạng thái và hành động đề xuất:
  synced        – hai bên giống nhau
  only_system   – chưa có trên Moodle            → đẩy lên (tạo mới)
  system_newer  – hệ thống đã sửa sau lần đồng bộ → đẩy lên (phiên bản mới trên Moodle)
  moodle_newer  – Moodle có phiên bản mới         → kéo về (cập nhật câu bên hệ thống)
  conflict      – hai bên đều khác và chưa từng nối phiên bản → GV chọn chiều
  only_moodle   – câu soạn trên Moodle chưa có idnumber QB → kéo về (tạo câu mới, chưa gán CLO/Bloom) và gắn QB-n
"""
from __future__ import annotations

import html
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import Question, QuestionOption
from .moodle import _t

LABELS = "ABCDEFGHIJ"


def norm(s: str | None) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return " ".join(html.unescape(s).split())


def moodle_questions(db: Session, moodle_course_id: int) -> list[dict]:
    """Bản mới nhất của các câu multichoice (một đáp án) trong các danh mục câu hỏi của khóa học Moodle."""
    rows = db.execute(text(f"""
        SELECT qbe.id AS entry_id, qbe.idnumber, q.id AS questionid, q.name, q.questiontext, q.defaultmark, q.timemodified,
               qv.version, qc.name AS category
        FROM {_t('context')} cx
        JOIN {_t('question_categories')} qc ON qc.contextid = cx.id
        JOIN {_t('question_bank_entries')} qbe ON qbe.questioncategoryid = qc.id
        JOIN {_t('question_versions')} qv ON qv.questionbankentryid = qbe.id
        JOIN {_t('question')} q ON q.id = qv.questionid AND q.qtype = 'multichoice' AND q.parent = 0
        JOIN {_t('qtype_multichoice_options')} mo ON mo.questionid = q.id AND mo.single = 1
        WHERE cx.contextlevel = 50 AND cx.instanceid = :c
          AND qv.version = (SELECT MAX(v2.version) FROM {_t('question_versions')} v2 WHERE v2.questionbankentryid = qbe.id)
        ORDER BY qbe.id"""), {"c": moodle_course_id}).mappings().all()
    if not rows:
        return []
    ids = ",".join(str(int(r["questionid"])) for r in rows)
    ans = {}
    for a in db.execute(text(f"SELECT id, question, answer, fraction FROM {_t('question_answers')} WHERE question IN ({ids}) ORDER BY id")).mappings():
        ans.setdefault(a["question"], []).append({"id": a["id"], "text": a["answer"], "fraction": float(a["fraction"])})
    return [{**dict(r), "defaultmark": float(r["defaultmark"]), "answers": ans.get(r["questionid"], [])} for r in rows]


def _sys_questions(db: Session, course_id: int) -> dict[int, Question]:
    return {q.id: q for q in db.query(Question).filter(Question.course_id == course_id, Question.question_type == "multichoice").all()}


def _same(q: Question, m: dict) -> bool:
    opts = sorted(q.options, key=lambda o: o.position)
    return norm(q.content) == norm(m["questiontext"]) and len(opts) == len(m["answers"]) and all(
        norm(o.content) == norm(a["text"]) and bool(o.is_correct) == (a["fraction"] > 0.5) for o, a in zip(opts, m["answers"]))


def _n_results(db: Session, qid: int) -> int:
    return db.execute(text("SELECT COUNT(*) FROM item_level_results WHERE question_id=:q"), {"q": qid}).scalar()


def compare(db: Session, course_id: int, moodle_course_id: int) -> dict:
    sysq = _sys_questions(db, course_id)
    mq = moodle_questions(db, moodle_course_id)
    by_idn = {}
    rows = []
    for m in mq:
        mm = re.fullmatch(r"QB-(\d+)", m["idnumber"] or "")
        if mm and int(mm.group(1)) in sysq:
            by_idn[int(mm.group(1))] = m
        elif not mm:
            ok = sum(1 for a in m["answers"] if a["fraction"] > 0.5) == 1 and len(m["answers"]) >= 2
            rows.append({"state": "only_moodle", "action": "pull" if ok else None, "question_id": None,
                         "moodle_questionid": m["questionid"], "moodle_version": m["version"], "content": norm(m["questiontext"])[:200],
                         "moodle_content": norm(m["questiontext"])[:200], "n_options": len(m["answers"]),
                         "note": None if ok else "Câu nhiều đáp án đúng – hệ thống chỉ nhận câu một đáp án"})
        # QB-n của môn khác / câu đã xóa: bỏ qua
    for qid, q in sysq.items():
        m = by_idn.get(qid)
        base = {"question_id": qid, "content": norm(q.content)[:200], "is_cancelled": q.is_cancelled,
                "tagged": q.bloom_level_id is not None and bool(q.clo_links), "n_options": len(q.options)}
        if not m:
            if q.is_cancelled:
                continue
            rows.append({**base, "state": "only_system", "action": "push"}); continue
        info = {"moodle_questionid": m["questionid"], "moodle_version": m["version"], "moodle_content": norm(m["questiontext"])[:200]}
        if _same(q, m):
            st, act = "synced", None
        elif q.moodle_question_id and int(q.moodle_question_id) == int(m["questionid"]):
            st, act = "system_newer", "push"
        elif q.moodle_question_id:
            st, act = "moodle_newer", "pull"
        else:
            st, act = "conflict", None
        locked = act == "pull" and _n_results(db, qid) > 0
        rows.append({**base, **info, "state": st, "action": None if locked else act,
                     "note": "Câu đã có kết quả thi – không ghi đè từ Moodle (Hủy câu và tạo câu mới nếu cần)" if locked else None})
    order = {"conflict": 0, "moodle_newer": 1, "only_moodle": 2, "system_newer": 3, "only_system": 4, "synced": 5}
    rows.sort(key=lambda r: (order[r["state"]], r["question_id"] or 0))
    summary = {k: sum(1 for r in rows if r["state"] == k) for k in order}
    return {"moodle_course_id": moodle_course_id, "rows": rows, "summary": summary, "n_moodle": len(mq), "n_system": len(sysq)}


def push(db: Session, course_id: int, moodle_course_id: int, qids: list[int], call) -> list[dict]:
    """Đẩy câu của hệ thống lên Moodle (call = lms.call)."""
    sysq = _sys_questions(db, course_id)
    payload = []
    for qid in qids:
        q = sysq.get(qid)
        if not q:
            raise ValueError(f"Câu {qid} không thuộc môn học")
        pts = db.execute(text("SELECT points FROM exam_questions WHERE question_id=:q ORDER BY exam_id DESC LIMIT 1"), {"q": qid}).scalar()
        payload.append({"idnumber": f"QB-{q.id}", "name": f"QB-{q.id}", "questiontext": q.content, "defaultmark": float(pts or 1),
                        "answers": [{"text": o.content, "fraction": 1 if o.is_correct else 0} for o in sorted(q.options, key=lambda o: o.position)]})
    out = []
    for i in range(0, len(payload), 50):
        res = call("local_clo_sync_questions", {"courseid": moodle_course_id, "questions": payload[i:i + 50]}, timeout=180)
        out += res["results"]
    _relink(db, out)
    return out


def _relink(db: Session, results: list[dict]) -> None:
    """Ghi lại id câu / id phương án phiên bản mới nhất trên Moodle cho câu bên hệ thống."""
    for r in results:
        qid = int(r["idnumber"][3:])
        db.execute(text("UPDATE question_bank SET moodle_question_id=:m WHERE id=:q"), {"m": r["questionid"], "q": qid})
        ans = [a[0] for a in db.execute(text(f"SELECT id FROM {_t('question_answers')} WHERE question=:m ORDER BY id"), {"m": r["questionid"]})]
        opts = db.execute(text("SELECT id FROM question_options WHERE question_id=:q ORDER BY position"), {"q": qid}).scalars().all()
        db.execute(text("UPDATE question_options SET moodle_answer_id=NULL WHERE question_id=:q"), {"q": qid})
        if len(ans) == len(opts):
            for oid, aid in zip(opts, ans):
                db.execute(text("UPDATE question_options SET moodle_answer_id=NULL WHERE moodle_answer_id=:a"), {"a": aid})
                db.execute(text("UPDATE question_options SET moodle_answer_id=:a WHERE id=:o"), {"a": aid, "o": oid})
    db.commit()


def _set_options(db: Session, q: Question, answers: list[dict]) -> None:
    q.options.clear(); db.flush()          # xóa phương án cũ trước (ràng buộc duy nhất question_id + position)
    for i, a in enumerate(answers):
        q.options.append(QuestionOption(position=i + 1, opt_label=LABELS[i], content=norm(a["text"]) if "<" in a["text"] else a["text"].strip(),
                                        is_correct=a["fraction"] > 0.5, moodle_answer_id=None))


def pull(db: Session, course_id: int, moodle_course_id: int, qids: list[int], moodle_new: list[int], user_id: int | None, call) -> dict:
    """Kéo về: cập nhật câu đã nối (bản mới trên Moodle) và nhập câu soạn trên Moodle (rồi gắn idnumber QB-n lên Moodle)."""
    mq = moodle_questions(db, moodle_course_id)
    by_idn = {int(m["idnumber"][3:]): m for m in mq if re.fullmatch(r"QB-\d+", m["idnumber"] or "")}
    by_mid = {int(m["questionid"]): m for m in mq}
    sysq = _sys_questions(db, course_id)
    updated, created, tags = [], [], []
    for qid in qids:
        q, m = sysq.get(qid), by_idn.get(qid)
        if not q or not m:
            raise ValueError(f"Câu {qid} chưa có trên Moodle hoặc không thuộc môn học")
        if _n_results(db, qid):
            raise ValueError(f"Câu {qid} đã có kết quả thi – không ghi đè từ Moodle")
        if sum(1 for a in m["answers"] if a["fraction"] > 0.5) != 1:
            raise ValueError(f"Câu {qid} trên Moodle không đúng một đáp án đúng")
        q.content = norm(m["questiontext"]) if "<" in (m["questiontext"] or "") else m["questiontext"]
        db.flush()
        _set_options(db, q, m["answers"]); db.flush()
        q.moodle_question_id = m["questionid"]
        updated.append(qid)
    for mid in moodle_new:
        m = by_mid.get(int(mid))
        if not m or (m["idnumber"] or "").startswith("QB-"):
            raise ValueError(f"Câu Moodle {mid} không còn ở trạng thái chưa nối")
        if sum(1 for a in m["answers"] if a["fraction"] > 0.5) != 1 or len(m["answers"]) < 2:
            raise ValueError(f"Câu Moodle {mid} không phải câu một đáp án đúng")
        q = Question(course_id=course_id, question_type="multichoice", content=norm(m["questiontext"]) if "<" in m["questiontext"] else m["questiontext"],
                     moodle_question_id=m["questionid"], created_by=user_id)
        db.add(q); db.flush()
        _set_options(db, q, m["answers"])
        db.flush()
        created.append(q.id)
        tags.append({"idnumber": f"QB-{q.id}", "moodlequestionid": m["questionid"]})
    db.commit()
    tagged = []
    if tags:
        res = call("local_clo_sync_questions", {"courseid": moodle_course_id, "questions": tags}, timeout=120)
        tagged = res["results"]
        _relink(db, tagged)
    else:
        _relink(db, [{"idnumber": f"QB-{qid}", "questionid": by_idn[qid]["questionid"]} for qid in updated])
    return {"updated": updated, "created": created, "tagged": len(tagged)}
