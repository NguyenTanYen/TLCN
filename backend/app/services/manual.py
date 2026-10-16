"""Bài kiểm tra nhập điểm (tự luận, thực hành, đồ án, bài làm ngoài hệ thống…).

Mỗi câu/ý chấm tay là một dòng question_bank (question_type = 'manual') gắn CLO bằng question_clo_mapping như câu trắc nghiệm,
nên toàn bộ Analysis Engine (độ khó/độ phân biệt nhiều mức điểm, điểm CLO từng SV, BM6, PI/PLO, lộ trình ôn tập) dùng lại nguyên vẹn.
Điểm từng SV ghi vào exam_attempts (source = 'manual') và item_level_results (response_status = 'graded').
"""
from __future__ import annotations

import io
import re
import unicodedata
from datetime import datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import Exam, ExamQuestion, Question, QuestionCLO


class GradeError(ValueError):
    pass


def _nfc(s) -> str:
    return unicodedata.normalize("NFC", str(s if s is not None else "")).strip()


def _num(v):
    """'7,5' / 7.5 / '' -> float | None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = _nfc(v).replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        raise GradeError(f"'{v}' không phải là điểm")


# ------------------------------------------------------------------ tạo bài nhập điểm
def add_items(db: Session, exam: Exam, course_id: int, items: list[dict], user_id: int | None) -> None:
    """items: [{title, points, clos: [{clo_id, weight}], outline_id?, bloom_level_id?}] – thêm vào cuối đề."""
    clo_ids = {r[0] for r in db.execute(text("SELECT id FROM clos WHERE course_id=:c"), {"c": course_id})}
    start = len(exam.questions)
    for i, it in enumerate(items, start + 1):
        if not it.get("clos"):
            raise GradeError(f"Câu/ý \"{it['title']}\" chưa gắn CLO")
        tot = round(sum(float(c.get("weight", 1)) for c in it["clos"]), 2)
        if abs(tot - 1) > 0.011:
            raise GradeError(f"Tổng trọng số CLO của \"{it['title']}\" phải bằng 1 (đang là {tot})")
        if any(int(c["clo_id"]) not in clo_ids for c in it["clos"]):
            raise GradeError(f"CLO của \"{it['title']}\" không thuộc môn học")
        q = Question(course_id=course_id, question_type="manual", content=_nfc(it["title"])[:2000] or f"Câu {i}",
                     outline_id=it.get("outline_id"), bloom_level_id=it.get("bloom_level_id"), created_by=user_id)
        for c in it["clos"]:
            q.clo_links.append(QuestionCLO(clo_id=int(c["clo_id"]), weight=round(float(c.get("weight", 1)), 2)))
        db.add(q); db.flush()
        exam.questions.append(ExamQuestion(question_id=q.id, order_index=i, points=float(it["points"])))


def items_of(db: Session, exam_id: int) -> list[dict]:
    rows = db.execute(text("""SELECT eq.question_id, eq.order_index, eq.points, q.content AS title, q.question_type,
                                     (SELECT GROUP_CONCAT(CONCAT(c.clo_code, IF(m.weight < 1, CONCAT(' (', m.weight, ')'), ''))
                                      ORDER BY c.clo_code SEPARATOR ', ') FROM question_clo_mapping m JOIN clos c ON c.id=m.clo_id
                                      WHERE m.question_id=q.id) AS clos
                              FROM exam_questions eq JOIN question_bank q ON q.id=eq.question_id
                              WHERE eq.exam_id=:e ORDER BY eq.order_index"""), {"e": exam_id}).mappings()
    return [{**dict(r), "points": float(r["points"])} for r in rows]


def gradebook(db: Session, exam: Exam) -> dict:
    items = items_of(db, exam.id)
    studs = db.execute(text("""SELECT s.id, s.student_code, s.full_name, en.status AS enroll_status FROM enrollments en
                               JOIN students s ON s.id=en.student_id WHERE en.class_section_id=:cs
                               UNION SELECT s.id, s.student_code, s.full_name, 'active' FROM exam_attempts a JOIN students s ON s.id=a.student_id
                               WHERE a.exam_id=:e AND s.id NOT IN (SELECT student_id FROM enrollments WHERE class_section_id=:cs)
                               ORDER BY 2"""), {"cs": exam.class_section_id, "e": exam.id}).mappings().all()
    att = {r["student_id"]: r for r in db.execute(text("SELECT id, student_id, status, total_score FROM exam_attempts WHERE exam_id=:e"),
                                                    {"e": exam.id}).mappings()}
    sc = {}
    for r in db.execute(text("""SELECT a.student_id, r.question_id, r.score_earned, r.response_status FROM item_level_results r
                                JOIN exam_attempts a ON a.id=r.attempt_id WHERE a.exam_id=:e"""), {"e": exam.id}).mappings():
        sc.setdefault(r["student_id"], {})[r["question_id"]] = float(r["score_earned"])
    out = []
    for s in studs:
        a = att.get(s["id"])
        out.append({"student_id": s["id"], "student_code": s["student_code"], "full_name": s["full_name"],
                    "dropped": s["enroll_status"] == "dropped",
                    "status": a["status"] if a else None, "total": float(a["total_score"]) if a else None,
                    "scores": {str(k): v for k, v in sc.get(s["id"], {}).items()}})
    return {"exam_id": exam.id, "items": items, "raw_max": round(sum(i["points"] for i in items), 2),
            "max_score": float(exam.max_score), "students": out}


def save_grades(db: Session, exam: Exam, rows: list[dict]) -> dict:
    """rows: [{student_id, absent: bool, scores: {question_id: điểm|None}}]
    - absent = true -> lượt 'absent' (không tính vào mẫu số);
    - mọi ô trống và không vắng -> xóa điểm của SV (chưa nhập);
    - còn lại: ô trống tính 0 điểm."""
    items = {i["question_id"]: i for i in items_of(db, exam.id)}
    if not items:
        raise GradeError("Bài kiểm tra chưa có câu/ý để nhập điểm")
    n_saved = n_abs = n_cleared = 0
    now = datetime.now()
    for r in rows:
        sid = int(r["student_id"])
        scores = {int(k): _num(v) for k, v in (r.get("scores") or {}).items() if int(k) in items}
        for qid, v in scores.items():
            if v is not None and not (0 <= v <= items[qid]["points"] + 1e-9):
                code = db.execute(text("SELECT student_code FROM students WHERE id=:s"), {"s": sid}).scalar()
                raise GradeError(f"SV {code}: điểm {v:g} của \"{items[qid]['title']}\" phải trong khoảng 0 – {items[qid]['points']:g}")
        old = db.execute(text("SELECT id FROM exam_attempts WHERE exam_id=:e AND student_id=:s"), {"e": exam.id, "s": sid}).scalar()
        if old:
            db.execute(text("DELETE FROM exam_attempts WHERE id=:a"), {"a": old})
        if r.get("absent"):
            db.execute(text("""INSERT INTO exam_attempts (exam_id, student_id, source, status, total_score)
                               VALUES (:e, :s, 'manual', 'absent', 0)"""), {"e": exam.id, "s": sid})
            n_abs += 1
            continue
        if all(v is None for v in scores.values()):
            n_cleared += bool(old)
            continue
        total = round(sum(v or 0 for v in scores.values()), 2)
        aid = db.execute(text("""INSERT INTO exam_attempts (exam_id, student_id, source, started_at, finished_at, status, total_score)
                                 VALUES (:e, :s, 'manual', NULL, :t, 'finished', :tot)"""),
                         {"e": exam.id, "s": sid, "t": now, "tot": total}).lastrowid
        for qid, it in items.items():
            v = scores.get(qid) or 0.0
            db.execute(text("""INSERT INTO item_level_results (attempt_id, question_id, selected_option_id, response_status, is_correct, score_earned)
                               VALUES (:a, :q, NULL, 'graded', :ok, :v)"""),
                       {"a": aid, "q": qid, "ok": v + 1e-9 >= it["points"], "v": round(v, 2)})
        n_saved += 1
    n_fin = db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e AND status='finished'"), {"e": exam.id}).scalar()
    exam.status = "Synced" if n_fin else ("Published" if exam.status != "Draft" else "Draft")
    exam.last_synced_at = now
    db.execute(text("""INSERT INTO sync_runs (exam_id, kind, finished_at, status, n_attempts, n_absent, message)
                       VALUES (:e, 'manual', NOW(), 'success', :n, :a, :m)"""),
               {"e": exam.id, "n": n_saved, "a": n_abs, "m": f"Nhập điểm: {n_saved} SV có điểm, {n_abs} vắng, {n_cleared} xóa điểm"})
    db.commit()
    return {"saved": n_saved, "absent": n_abs, "cleared": n_cleared, "n_finished": n_fin}


# ------------------------------------------------------------------ Excel
THIN = Side(style="thin", color="999999")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEAD = PatternFill("solid", fgColor="DCE6F1")


def template_xlsx(db: Session, exam: Exam) -> bytes:
    """Bảng điểm mẫu của bài: MSSV, Họ tên, Vắng, mỗi câu/ý một cột (dòng 2: điểm tối đa, dòng 3 ẩn: mã câu QB-n)."""
    gb = gradebook(db, exam)
    wb = Workbook()
    ws = wb.active
    ws.title = "NhapDiem"
    cs = exam.class_section
    ws["A1"] = f"BẢNG ĐIỂM – {exam.exam_title} – Lớp {cs.section_code} ({cs.course.course_code} {cs.course.course_name})"
    ws["A1"].font = Font(bold=True, size=12)
    head = ["STT", "MSSV", "Họ và tên", "Vắng (x)"] + [f"{it['order_index']}. {it['title']}" for it in gb["items"]] + ["Tổng"]
    ws.append([])
    ws.append(head)
    ws.append(["", "", "Điểm tối đa →", ""] + [it["points"] for it in gb["items"]] + [gb["raw_max"]])
    ws.append(["", "", "CLO →", ""] + [it["clos"] or "" for it in gb["items"]] + [""])
    ws.append(["#key", "", "", ""] + [f"QB-{it['question_id']}" for it in gb["items"]] + [""])
    first = 7
    n_it = len(gb["items"])
    for i, s in enumerate(gb["students"], 1):
        row = [i, s["student_code"], s["full_name"], "x" if s["status"] == "absent" else ""]
        row += [s["scores"].get(str(it["question_id"])) if s["status"] == "finished" else None for it in gb["items"]]
        r = first + i - 1
        row.append(f"=IF(D{r}=\"x\",\"\",SUM({get_column_letter(5)}{r}:{get_column_letter(4 + n_it)}{r}))" if n_it else "")
        ws.append(row)
    ws.row_dimensions[6].hidden = True
    last = first + len(gb["students"]) - 1
    for row in ws.iter_rows(min_row=3, max_row=max(last, 6), max_col=len(head)):
        for c in row:
            c.border = BOX
    for c in ws[3]:
        c.font = Font(bold=True); c.fill = HEAD; c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    for r in (4, 5):
        for c in ws[r]:
            c.font = Font(italic=True, color="555555"); c.alignment = Alignment(horizontal="center", wrap_text=True)
    ws.row_dimensions[3].height = 48
    widths = [5, 13, 26, 8] + [14] * n_it + [9]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "E7"
    if n_it and last >= first:
        for j, it in enumerate(gb["items"]):
            col = get_column_letter(5 + j)
            dv = DataValidation(type="decimal", operator="between", formula1="0", formula2=str(it["points"]), allow_blank=True,
                                errorTitle="Điểm không hợp lệ", error=f"Điểm phải từ 0 đến {it['points']:g}")
            dv.add(f"{col}{first}:{col}{last}")
            ws.add_data_validation(dv)
    g = wb.create_sheet("HuongDan")
    for line in ["Hướng dẫn nhập điểm:",
                 "• Mỗi dòng một sinh viên; mỗi cột một câu/ý chấm điểm (điểm tối đa ở dòng 4, CLO đo ở dòng 5).",
                 "• Đánh dấu x ở cột 'Vắng' nếu SV vắng thi (không tính vào số SV đánh giá).",
                 "• Ô điểm để trống được tính 0 điểm; dòng để trống hoàn toàn (không vắng) = chưa nhập điểm.",
                 "• Có thể thêm SV chưa có trong danh sách lớp (MSSV, họ tên) – hệ thống hỏi trước khi ghi danh.",
                 "• Không xóa dòng ẩn số 6 (mã câu QB-n) – dùng để khớp cột với câu/ý của bài."]:
        g.append([line])
    g.column_dimensions["A"].width = 110
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()


HEAD_CODE = re.compile(r"^(mssv|mã\s*sv|mã\s*số\s*(sinh\s*viên|sv)|student[_\s]*code|mã\s*sinh\s*viên)$", re.I)
HEAD_NAME = re.compile(r"^(họ\s*(và)?\s*tên|họ tên|full[_\s]*name|tên)$", re.I)
HEAD_ABS = re.compile(r"^vắng", re.I)
HEAD_SKIP = re.compile(r"^(stt|tt|lớp|tổng|tổng điểm|ghi chú|điểm tổng|total|email|ngày sinh)", re.I)


def _find_header(ws):
    for r in range(1, min(ws.max_row, 30) + 1):
        vals = [_nfc(c.value) for c in ws[r]]
        if any(HEAD_CODE.match(v) for v in vals):
            return r, vals
    raise GradeError("Không tìm thấy dòng tiêu đề có cột MSSV (hoặc 'Mã SV', 'student_code')")


def parse_sheet(data: bytes) -> dict:
    """Đọc bảng điểm Excel bất kỳ: dòng tiêu đề có MSSV; các cột còn lại có số là câu/ý (trừ STT, Tổng, Ghi chú…).
    Điểm tối đa: dòng 'Điểm tối đa'/'Max' ngay dưới tiêu đề, hoặc ghi trong tiêu đề '(2đ)', '/2'; CLO: '[CLO1, CLO2]' hoặc dòng 'CLO'.
    Dòng ẩn '#key' (bảng điểm mẫu của hệ thống) chứa mã câu QB-n."""
    try:
        wb = load_workbook(io.BytesIO(data), data_only=True)
    except Exception as ex:   # noqa: BLE001
        raise GradeError(f"Không đọc được file Excel (.xlsx): {ex}")
    ws = wb.worksheets[0]
    hr, head = _find_header(ws)
    ci_code = next(i for i, v in enumerate(head) if HEAD_CODE.match(v))
    ci_name = next((i for i, v in enumerate(head) if HEAD_NAME.match(v)), None)
    ci_abs = next((i for i, v in enumerate(head) if HEAD_ABS.match(v)), None)
    item_cols = [i for i, v in enumerate(head) if v and i not in (ci_code, ci_name, ci_abs) and not HEAD_SKIP.match(v)]
    meta = {i: {"col": i, "header": head[i], "points": None, "clos": [], "key": None} for i in item_cols}
    for i, m in meta.items():
        h = m["header"]
        mm = re.search(r"\(\s*(\d+(?:[.,]\d+)?)\s*(?:đ|điểm|d)?\s*\)", h, re.I) or re.search(r"/\s*(\d+(?:[.,]\d+)?)\s*$", h)
        if mm:
            m["points"] = float(mm.group(1).replace(",", "."))
        mm = re.search(r"\[([^\]]+)\]", h)
        if mm:
            m["clos"] = [x.strip() for x in re.split(r"[,;]", mm.group(1)) if x.strip()]
        m["title"] = re.sub(r"\[[^\]]*\]|\(\s*\d+(?:[.,]\d+)?\s*(?:đ|điểm|d)?\s*\)|/\s*\d+(?:[.,]\d+)?\s*$", "", h).strip(" -–") or h
        m["title"] = re.sub(r"^\d+\.\s*", "", m["title"])
    r = hr + 1
    data_start = r
    while r <= ws.max_row:
        vals = [ws.cell(r, i + 1).value for i in range(len(head))]
        label = " ".join(_nfc(v) for v in vals[:max(ci_code, ci_name or 0) + 2]).lower()
        code = _nfc(vals[ci_code])
        if code.startswith("#key") or "#key" in label:
            for i in item_cols:
                k = _nfc(vals[i])
                if re.match(r"^QB-\d+$", k):
                    meta[i]["key"] = int(k[3:])
            r += 1; data_start = r; continue
        if not code and ("tối đa" in label or "max" in label):
            for i in item_cols:
                v = vals[i]
                if v not in (None, ""):
                    meta[i]["points"] = _num(v)
            r += 1; data_start = r; continue
        if not code and "clo" in label:
            for i in item_cols:
                if _nfc(vals[i]):
                    meta[i]["clos"] = [re.sub(r"\s*\(.*\)$", "", x).strip() for x in re.split(r"[,;]", _nfc(vals[i])) if x.strip()]
            r += 1; data_start = r; continue
        break
    students = []
    for r in range(data_start, ws.max_row + 1):
        vals = [ws.cell(r, i + 1).value for i in range(len(head))]
        code = _nfc(vals[ci_code])
        if not code:
            continue
        if isinstance(vals[ci_code], float) and vals[ci_code].is_integer():
            code = str(int(vals[ci_code]))
        absent = ci_abs is not None and _nfc(vals[ci_abs]).lower() in ("x", "v", "vắng", "1", "có", "true")
        sc = {}
        for i in item_cols:
            try:
                sc[i] = _num(vals[i])
            except GradeError:
                raise GradeError(f"Dòng {r}, cột \"{meta[i]['header']}\": '{vals[i]}' không phải là điểm")
        students.append({"row": r, "student_code": code[:100], "full_name": _nfc(vals[ci_name])[:100] if ci_name is not None else "",
                         "absent": absent, "scores": sc})
    # bỏ cột không có số nào (cột chữ khác)
    used = [i for i in item_cols if meta[i]["key"] or meta[i]["points"] or any(s["scores"].get(i) is not None for s in students)]
    return {"items": [meta[i] for i in used], "students": [{**s, "scores": {i: s["scores"][i] for i in used}} for s in students]}
