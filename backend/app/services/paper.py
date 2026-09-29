"""Bài thi giấy nhiều mã đề: sinh mã đề, in đề, đáp án và nhập phiếu trả lời (UC-02, UC-03b).

Mỗi mã đề hoán vị thứ tự câu và thứ tự phương án. Khi nhập phiếu trả lời, nhãn SV chọn trên mã đề
được ánh xạ ngược về phương án gốc qua bảng exam_version_options – tương tự Reverse Shuffle của Moodle.
"""
from __future__ import annotations

import csv
import io
import random
from datetime import datetime
from decimal import Decimal

from docx import Document
from docx.shared import Pt
from openpyxl import Workbook, load_workbook
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import Exam, ExamVersion, ExamVersionOption, ExamVersionQuestion, Student

LABELS = "ABCDEFGHIJ"


def generate_versions(db: Session, exam: Exam, codes: list[str], seed: int | None = None) -> list[ExamVersion]:
    rng = random.Random(seed)
    if db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e"), {"e": exam.id}).scalar():
        raise ValueError("Đề đã có kết quả thi, không thể sinh lại mã đề")
    for v in list(exam.versions):
        db.delete(v)
    db.flush()
    versions = []
    for code in codes:
        v = ExamVersion(exam_id=exam.id, version_code=code)
        db.add(v)
        db.flush()
        eqs = list(exam.questions)
        rng.shuffle(eqs)
        for pos, eq in enumerate(eqs, 1):
            db.add(ExamVersionQuestion(version_id=v.id, question_id=eq.question_id, position=pos))
            db.flush()
            opts = sorted(eq.question.options, key=lambda o: o.position)
            rng.shuffle(opts)
            for i, o in enumerate(opts):
                db.add(ExamVersionOption(version_id=v.id, question_id=eq.question_id, displayed_label=LABELS[i], option_id=o.id))
        versions.append(v)
    db.flush()
    return versions


def version_layout(db: Session, version_id: int) -> list[dict]:
    rows = db.execute(text("""
        SELECT evq.position, q.id AS question_id, q.content, evo.displayed_label, o.content AS opt_content, o.is_correct, o.opt_label
        FROM exam_version_questions evq
        JOIN question_bank q ON q.id = evq.question_id
        JOIN exam_version_options evo ON evo.version_id = evq.version_id AND evo.question_id = evq.question_id
        JOIN question_options o ON o.id = evo.option_id
        WHERE evq.version_id = :v ORDER BY evq.position, evo.displayed_label"""), {"v": version_id}).mappings().all()
    out: dict[int, dict] = {}
    for r in rows:
        item = out.setdefault(r["position"], {"position": r["position"], "question_id": r["question_id"],
                                              "content": r["content"], "options": [], "key": None})
        item["options"].append({"label": r["displayed_label"], "content": r["opt_content"], "orig": r["opt_label"]})
        if r["is_correct"]:
            item["key"] = r["displayed_label"]
    return [out[k] for k in sorted(out)]


def exam_paper_docx(db: Session, exam: Exam, version: ExamVersion) -> bytes:
    cs = exam.class_section
    doc = Document()
    st = doc.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(12)
    doc.add_paragraph("TRƯỜNG ĐẠI HỌC SƯ PHẠM KỸ THUẬT TP. HỒ CHÍ MINH").runs[0].bold = True
    doc.add_paragraph(f"ĐỀ KIỂM TRA: {exam.exam_title}").runs[0].bold = True
    doc.add_paragraph(f"Môn: {cs.course.course_name} ({cs.course.course_code}) – Lớp HP: {cs.section_code} – "
                      f"{cs.semester.name}")
    doc.add_paragraph(f"Thời gian: {exam.duration_minutes or '…'} phút – Mã đề: {version.version_code}")
    doc.add_paragraph("Họ tên: ………………………………  MSSV: ……………………")
    for item in version_layout(db, version.id):
        p = doc.add_paragraph()
        p.add_run(f"Câu {item['position']}. ").bold = True
        p.add_run(item["content"])
        for o in item["options"]:
            doc.add_paragraph(f"    {o['label']}. {o['content']}")
    bio = io.BytesIO(); doc.save(bio)
    return bio.getvalue()


def answer_key_xlsx(db: Session, exam: Exam) -> bytes:
    wb = Workbook(); ws = wb.active; ws.title = "Dap an"
    ws.append(["Mã đề", "Câu", "Đáp án", "question_id"])
    for v in exam.versions:
        for item in version_layout(db, v.id):
            ws.append([v.version_code, item["position"], item["key"], item["question_id"]])
    tpl = wb.create_sheet("Mau nhap phieu")
    n = len(exam.questions)
    tpl.append(["student_code", "version_code"] + [f"Q{i}" for i in range(1, n + 1)])
    bio = io.BytesIO(); wb.save(bio)
    return bio.getvalue()


def _read_rows(filename: str, content: bytes) -> list[dict]:
    if filename.lower().endswith(".xlsx"):
        ws = load_workbook(io.BytesIO(content), data_only=True).active
        rows = list(ws.iter_rows(values_only=True))
        header = [str(h).strip() if h is not None else "" for h in rows[0]]
        return [dict(zip(header, r)) for r in rows[1:] if any(v is not None for v in r)]
    text_data = content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text_data)))


def import_answer_sheets(db: Session, exam: Exam, filename: str, content: bytes) -> dict:
    """Nhập phiếu trả lời: mỗi dòng = student_code, version_code, Q1..Qn (nhãn SV tô; rỗng = bỏ trống)."""
    run_id = db.execute(text("INSERT INTO sync_runs (exam_id, kind) VALUES (:e, 'paper')"), {"e": exam.id}).lastrowid
    db.commit()
    try:
        rows = _read_rows(filename, content)
        versions = {v.version_code: v for v in exam.versions}
        if not versions:
            raise ValueError("Đề chưa có mã đề – hãy sinh mã đề trước")
        points = {eq.question_id: Decimal(eq.points) for eq in exam.questions}
        layouts = {code: {it["position"]: it for it in version_layout(db, v.id)} for code, v in versions.items()}
        opt_map = {}
        for code, v in versions.items():
            for r in db.execute(text("""SELECT evo.question_id, evo.displayed_label, o.id, o.is_correct
                                        FROM exam_version_options evo JOIN question_options o ON o.id = evo.option_id
                                        WHERE evo.version_id = :v"""), {"v": v.id}):
                opt_map[(code, r[0], r[1])] = (r[2], bool(r[3]))
        seen, errors = set(), []
        db.execute(text("""DELETE r FROM item_level_results r JOIN exam_attempts a ON a.id = r.attempt_id
                           WHERE a.exam_id = :e AND a.source = 'paper'"""), {"e": exam.id})
        db.execute(text("DELETE FROM exam_attempts WHERE exam_id = :e AND source = 'paper'"), {"e": exam.id})
        for i, row in enumerate(rows, 2):
            code = str(row.get("student_code") or "").strip()
            vcode = str(row.get("version_code") or "").strip()
            stu = db.query(Student).filter_by(student_code=code).first()
            if not stu:
                errors.append(f"Dòng {i}: không tìm thấy SV {code}"); continue
            if vcode not in versions:
                errors.append(f"Dòng {i}: mã đề {vcode} không tồn tại"); continue
            att_id = db.execute(text("""INSERT INTO exam_attempts (exam_id, student_id, version_id, source, started_at, finished_at, status)
                                        VALUES (:e, :s, :v, 'paper', :t, :t, 'finished')"""),
                                {"e": exam.id, "s": stu.id, "v": versions[vcode].id, "t": datetime.combine(exam.exam_date or datetime.now().date(), datetime.min.time())}).lastrowid
            total = Decimal(0)
            for pos, item in layouts[vcode].items():
                raw = row.get(f"Q{pos}")
                label = str(raw).strip().upper() if raw not in (None, "") else ""
                qid = item["question_id"]
                if label and (vcode, qid, label) in opt_map:
                    oid, ok = opt_map[(vcode, qid, label)]
                    sc = points[qid] if ok else Decimal(0)
                    total += sc
                    db.execute(text("""INSERT INTO item_level_results (attempt_id, question_id, selected_option_id, response_status, is_correct, score_earned)
                                       VALUES (:a, :q, :o, 'answered', :ok, :sc)"""), {"a": att_id, "q": qid, "o": oid, "ok": ok, "sc": sc})
                else:
                    if label:
                        errors.append(f"Dòng {i}: câu {pos} nhãn '{label}' không hợp lệ – coi như bỏ trống")
                    db.execute(text("""INSERT INTO item_level_results (attempt_id, question_id, response_status)
                                       VALUES (:a, :q, 'blank')"""), {"a": att_id, "q": qid})
            db.execute(text("UPDATE exam_attempts SET total_score = :t WHERE id = :a"), {"t": total, "a": att_id})
            seen.add(stu.id)
        # vắng thi: SV trong danh sách lớp HP không có phiếu
        absent = db.execute(text("""SELECT student_id FROM enrollments WHERE class_section_id = :cs AND status = 'active'"""),
                            {"cs": exam.class_section_id}).scalars().all()
        n_abs = 0
        for sid in absent:
            if sid in seen:
                continue
            exists = db.execute(text("SELECT id FROM exam_attempts WHERE exam_id=:e AND student_id=:s"), {"e": exam.id, "s": sid}).scalar()
            if exists:
                continue
            aid = db.execute(text("""INSERT INTO exam_attempts (exam_id, student_id, source, status, total_score)
                                     VALUES (:e, :s, 'paper', 'absent', 0)"""), {"e": exam.id, "s": sid}).lastrowid
            for eq in exam.questions:
                db.execute(text("INSERT INTO item_level_results (attempt_id, question_id, response_status) VALUES (:a, :q, 'absent')"),
                           {"a": aid, "q": eq.question_id})
            n_abs += 1
        db.execute(text("UPDATE exams SET status = IF(status='Analyzed', status, 'Synced'), last_synced_at = NOW() WHERE id = :e"), {"e": exam.id})
        db.commit()
        db.execute(text("UPDATE sync_runs SET status='success', finished_at=NOW(), n_attempts=:n, n_absent=:a, message=:m WHERE id=:r"),
                   {"n": len(seen), "a": n_abs, "m": "\n".join(errors)[:2000] or None, "r": run_id})
        db.commit()
        return {"imported": len(seen), "absent": n_abs, "warnings": errors}
    except Exception as exc:
        db.rollback()
        db.execute(text("UPDATE sync_runs SET status='failed', finished_at=NOW(), message=:m WHERE id=:r"), {"m": str(exc)[:1000], "r": run_id})
        db.commit()
        raise
