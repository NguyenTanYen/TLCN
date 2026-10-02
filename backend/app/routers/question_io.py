"""UC-01 (mở rộng): nhập hàng loạt câu hỏi, rồi gán CLO / Bloom / chương cho từng câu bằng file Excel.

Quy trình:
1. GET  /api/questions/import-template            – tải file mẫu nhập câu hỏi (.xlsx)
2. POST /api/questions/import?course_id=&dry_run=  – nhập (xem trước khi dry_run=true); câu chưa có CLO/Bloom = "chưa gán"
3. GET  /api/questions/tagging-template?course_id= – tải file gán CLO: mỗi dòng 1 câu (ID, nội dung, chương, Bloom, CLO)
4. POST /api/questions/tagging-import?course_id=&dry_run= – đọc file đã điền, kiểm tra, cập nhật hàng loạt
Câu hỏi chưa gán đủ CLO và Bloom không được đưa vào đề (tránh sai lệch khi đo CLO).
"""
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..http_utils import attachment
from ..deps import check_course_access, require
from ..models import Course, Question, QuestionCLO, QuestionOption, User
from ..services import question_import as qi

router = APIRouter(prefix="/api/questions", tags=["UC-01 Nhập câu hỏi & gán CLO từ file"])
MAX_BYTES = 10 * 1024 * 1024
HEAD_FILL = PatternFill("solid", fgColor="1D4ED8")
HEAD_FONT = Font(bold=True, color="FFFFFF")


def _course_refs(db: Session, course_id: int):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Không tìm thấy môn học")
    chapters = {r[0]: r[1] for r in db.execute(text("SELECT chapter_number, id FROM course_outlines WHERE course_id=:c"), {"c": course_id})}
    chapter_names = {r[0]: r[1] for r in db.execute(text("SELECT chapter_number, chapter_name FROM course_outlines WHERE course_id=:c ORDER BY chapter_number"), {"c": course_id})}
    clos = {qi.norm(r[0]): r[1] for r in db.execute(text("SELECT clo_code, id FROM clos WHERE course_id=:c"), {"c": course_id})}
    clo_rows = [dict(r) for r in db.execute(text("SELECT id, clo_code, description FROM clos WHERE course_id=:c ORDER BY clo_code"), {"c": course_id}).mappings()]
    levels = [dict(r) for r in db.execute(text("SELECT id, code, name_vi FROM bloom_levels ORDER BY id")).mappings()]
    return course, chapters, chapter_names, clos, clo_rows, levels


async def _read(file: UploadFile) -> bytes:
    data = await file.read()
    if not data:
        raise HTTPException(422, "File rỗng")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File quá lớn (tối đa 10 MB)")
    return data


def _xlsx(wb: Workbook, name: str) -> StreamingResponse:
    buf = BytesIO(); wb.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers=attachment(f"{name}"))


def _style_header(ws, widths):
    for i, w in enumerate(widths, 1):
        c = ws.cell(row=1, column=i)
        c.fill, c.font, c.alignment = HEAD_FILL, HEAD_FONT, Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[c.column_letter].width = w
    ws.freeze_panes = "A2"


def _guide_sheet(wb, chapter_names, clo_rows, levels, lines):
    g = wb.create_sheet("HuongDan")
    g.column_dimensions["A"].width = 16; g.column_dimensions["B"].width = 90
    r = 1
    for ln in lines:
        g.cell(row=r, column=1, value=ln).font = Font(bold=ln.isupper()); r += 1
    r += 1
    g.cell(row=r, column=1, value="CHƯƠNG (ghi số)").font = Font(bold=True); r += 1
    for n, name in chapter_names.items():
        g.cell(row=r, column=1, value=n); g.cell(row=r, column=2, value=name); r += 1
    r += 1
    g.cell(row=r, column=1, value="MỨC BLOOM").font = Font(bold=True); r += 1
    for b in levels:
        g.cell(row=r, column=1, value=f"{b['id']} - {b['name_vi']}"); g.cell(row=r, column=2, value=b["code"]); r += 1
    r += 1
    g.cell(row=r, column=1, value="CLO").font = Font(bold=True); r += 1
    for c in clo_rows:
        g.cell(row=r, column=1, value=c["clo_code"]); g.cell(row=r, column=2, value=c["description"]); r += 1
    return g


def _validations(ws, chapter_names, levels, col_chapter, col_bloom, n_rows):
    if chapter_names:
        dv = DataValidation(type="list", formula1='"' + ",".join(str(n) for n in chapter_names) + '"', allow_blank=True)
        dv.error = "Chọn số chương có trong đề cương"; ws.add_data_validation(dv)
        dv.add(f"{col_chapter}2:{col_chapter}{n_rows + 200}")
    dv2 = DataValidation(type="list", formula1='"' + ",".join(f"{b['id']} - {b['name_vi']}" for b in levels) + '"', allow_blank=True)
    dv2.error = "Chọn mức Bloom 1–6"; ws.add_data_validation(dv2)
    dv2.add(f"{col_bloom}2:{col_bloom}{n_rows + 200}")


# ------------------------------------------------------------------ 1. file mẫu nhập câu hỏi
@router.get("/import-template")
def import_template(course_id: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    check_course_access(db, u, course_id)
    course, _c, chapter_names, _cl, clo_rows, levels = _course_refs(db, course_id)
    wb = Workbook(); ws = wb.active; ws.title = "CauHoi"
    ws.append(["Nội dung", "A", "B", "C", "D", "E", "Đáp án", "Chương", "Bloom", "CLO"])
    _style_header(ws, [60, 28, 28, 28, 28, 16, 9, 9, 16, 22])
    ws.append(["Lệnh nào dùng để tạo thủ tục lưu trữ trong SQL Server?", "CREATE PROCEDURE", "CREATE FUNCTION",
               "CREATE TRIGGER", "CREATE VIEW", None, "A", None, None, None])
    ws.append(["Mức cô lập nào ngăn được hiện tượng đọc bóng ma (phantom read)?", "READ COMMITTED", "REPEATABLE READ",
               "SERIALIZABLE", "READ UNCOMMITTED", None, "C", 4, "3 - Vận dụng", "CLO3"])
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    _validations(ws, chapter_names, levels, "H", "I", 2)
    _guide_sheet(wb, chapter_names, clo_rows, levels, [
        "HƯỚNG DẪN NHẬP CÂU HỎI", f"Môn: {course.course_code} – {course.course_name}",
        "Mỗi dòng của sheet CauHoi là 1 câu trắc nghiệm một đáp án đúng. Xóa 2 dòng ví dụ trước khi nhập.",
        "Cột A..J: các phương án (tối thiểu 2, tối đa 10, không bỏ trống ở giữa). Đáp án: chữ cái của phương án đúng.",
        "Chương, Bloom, CLO: CÓ THỂ ĐỂ TRỐNG – câu sẽ ở trạng thái 'Chưa gán', gán sau bằng file Gán CLO.",
        "CLO: 'CLO2' hoặc nhiều CLO 'CLO1; CLO3' (chia đều) hoặc có trọng số 'CLO1:0.6; CLO3:0.4' (tổng = 1).",
        "Ngoài Excel còn nhập được: file Aiken (.txt/.docx: câu hỏi, 'A. ...', 'ANSWER: B') và Moodle XML (.xml).",
    ])
    return _xlsx(wb, f"mau_nhap_cau_hoi_{course.course_code}.xlsx")


# ------------------------------------------------------------------ 2. nhập hàng loạt câu hỏi
@router.post("/import")
async def import_questions(course_id: int, dry_run: bool = True, skip_duplicates: bool = True, file: UploadFile = File(...),
                           db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    check_course_access(db, u, course_id)
    _course, chapters, _cn, clos, _cr, levels = _course_refs(db, course_id)
    data = await _read(file)
    try:
        fmt, raw = qi.parse_questions(data, file.filename or "")
    except qi.ImportError_ as ex:
        raise HTTPException(422, str(ex))
    if not raw:
        raise HTTPException(422, "Không đọc được câu hỏi nào trong file")
    existing = {qi.norm_content(r[0]) for r in db.execute(text("SELECT content FROM question_bank WHERE course_id=:c"), {"c": course_id})}
    seen: set[str] = set()
    rows = []
    for q in raw:
        errs, warns = list(q["errors"]), []
        content = (q["content"] or "").strip()
        opts = [o.strip() for o in q["options"]]
        if len(content) < 3:
            errs.append("Thiếu nội dung câu hỏi")
        if not 2 <= len(opts) <= qi.MAX_OPTIONS:
            errs.append(f"Cần 2–10 phương án (đang có {len(opts)})")
        ans = (q["answer"] or "").strip().upper()
        if ans.isdigit() and 1 <= int(ans) <= len(opts):
            ans = qi.LABELS[int(ans) - 1]
        if not ans:
            errs.append("Thiếu đáp án đúng")
        elif len(ans) != 1 or ans not in qi.LABELS[:len(opts)]:
            errs.append(f"Đáp án '{q['answer']}' không khớp phương án nào")
        outline_id, e1 = qi.parse_chapter(q["chapter"], chapters)
        bloom_id, e2 = qi.parse_bloom(q["bloom"], levels)
        clo_links, e3 = qi.parse_clos(q["clo"], clos)
        errs += [e for e in (e1, e2, e3) if e]
        key = qi.norm_content(content)
        status = "error" if errs else "ok"
        if status == "ok" and key in existing:
            status, warns = "duplicate", warns + ["Trùng nội dung với câu đã có trong ngân hàng"]
        elif status == "ok" and key in seen:
            status, warns = "duplicate", warns + ["Trùng với một câu phía trên trong file"]
        seen.add(key)
        tagged = bool(clo_links) and bool(bloom_id)
        if status == "ok" and not tagged:
            warns.append("Chưa đủ CLO + Bloom – sẽ ở trạng thái 'Chưa gán'")
        rows.append({"row": q["row"], "content": content, "options": opts, "answer": ans, "outline_id": outline_id,
                     "chapter": q["chapter"] or None, "bloom_level_id": bloom_id, "clos": clo_links or [],
                     "clo_text": q["clo"] or None, "bloom_text": q["bloom"] or None, "tagged": tagged,
                     "status": status, "errors": errs, "warnings": warns})
    to_add = [r for r in rows if r["status"] == "ok" or (r["status"] == "duplicate" and not skip_duplicates)]
    summary = {"format": fmt, "total": len(rows), "ok": sum(r["status"] == "ok" for r in rows),
               "duplicate": sum(r["status"] == "duplicate" for r in rows), "error": sum(r["status"] == "error" for r in rows),
               "will_add": len(to_add), "untagged": sum(1 for r in to_add if not r["tagged"])}
    created = []
    if not dry_run and to_add:
        for r in to_add:
            q = Question(course_id=course_id, outline_id=r["outline_id"], bloom_level_id=r["bloom_level_id"],
                         content=r["content"], created_by=u.id)
            for i, o in enumerate(r["options"]):
                q.options.append(QuestionOption(position=i + 1, opt_label=qi.LABELS[i], content=o, is_correct=qi.LABELS[i] == r["answer"]))
            for cid, w in r["clos"]:
                q.clo_links.append(QuestionCLO(clo_id=cid, weight=w))
            db.add(q); db.flush()
            created.append(q.id)
        db.commit()
    for r in rows:
        r.pop("clos")
    return {"dry_run": dry_run, "summary": summary, "rows": rows, "created_ids": created}


# ------------------------------------------------------------------ 3. file gán CLO / Bloom / chương
def _question_rows(db, course_id, only_untagged, ids):
    rows = [dict(r) for r in db.execute(text("""
        SELECT q.id, q.content, q.bloom_level_id, q.is_cancelled, o.chapter_number,
               (SELECT opt_label FROM question_options WHERE question_id=q.id AND is_correct=1 LIMIT 1) AS answer,
               (SELECT COUNT(*) FROM item_level_results WHERE question_id=q.id) AS n_results
        FROM question_bank q LEFT JOIN course_outlines o ON o.id=q.outline_id
        WHERE q.course_id=:c ORDER BY q.id"""), {"c": course_id}).mappings()]
    links: dict[int, list] = {}
    for r in db.execute(text("""SELECT m.question_id, c.clo_code, m.weight FROM question_clo_mapping m JOIN clos c ON c.id=m.clo_id
                                JOIN question_bank q ON q.id=m.question_id WHERE q.course_id=:c ORDER BY c.clo_code"""), {"c": course_id}):
        links.setdefault(r[0], []).append((r[1], float(r[2])))
    for r in rows:
        r["clos"] = links.get(r["id"], [])
        r["tagged"] = bool(r["clos"]) and bool(r["bloom_level_id"])
    if ids:
        rows = [r for r in rows if r["id"] in ids]
    if only_untagged:
        rows = [r for r in rows if not r["tagged"]]
    return [r for r in rows if not r["is_cancelled"]]


@router.get("/tagging-template")
def tagging_template(course_id: int, only_untagged: bool = False, ids: str | None = None,
                     db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    check_course_access(db, u, course_id)
    course, _c, chapter_names, _cl, clo_rows, levels = _course_refs(db, course_id)
    id_set = {int(x) for x in ids.split(",") if x.strip().isdigit()} if ids else None
    rows = _question_rows(db, course_id, only_untagged, id_set)
    bname = {b["id"]: f"{b['id']} - {b['name_vi']}" for b in levels}
    wb = Workbook(); ws = wb.active; ws.title = "GanCLO"
    ws.append(["ID", "Nội dung câu hỏi", "Đáp án", "Chương", "Bloom", "CLO", "Ghi chú"])
    _style_header(ws, [7, 80, 8, 9, 16, 24, 30])
    locked_fill = PatternFill("solid", fgColor="F2F4F7")
    for r in rows:
        note = "Đã có kết quả thi – không đổi được" if r["n_results"] else ("Chưa gán" if not r["tagged"] else "")
        ws.append([r["id"], r["content"], r["answer"], r["chapter_number"], bname.get(r["bloom_level_id"]),
                   qi.clo_text(r["clos"]), note])
        if r["n_results"]:
            for c in ws[ws.max_row]:
                c.fill = locked_fill
    for row in ws.iter_rows(min_row=2):
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
    _validations(ws, chapter_names, levels, "D", "E", len(rows))
    _guide_sheet(wb, chapter_names, clo_rows, levels, [
        "HƯỚNG DẪN GÁN CLO / BLOOM / CHƯƠNG", f"Môn: {course.course_code} – {course.course_name}",
        "Điền cột Chương, Bloom, CLO cho từng câu (giữ nguyên cột ID). Không sửa nội dung/đáp án ở file này.",
        "Ô để trống = giữ nguyên giá trị hiện có. Có thể xóa bớt dòng không cần đổi.",
        "CLO: 'CLO2' hoặc 'CLO1; CLO3' (chia đều) hoặc 'CLO1:0.6; CLO3:0.4' (tổng trọng số = 1). Bloom: chọn 1–6.",
        "Câu đã có kết quả thi (dòng tô xám) không được đổi CLO/Bloom/Chương để giữ toàn vẹn minh chứng đã đo.",
    ])
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return _xlsx(wb, f"gan_clo_{course.course_code}_{stamp}.xlsx")


# ------------------------------------------------------------------ 4. đọc file gán CLO và cập nhật
@router.post("/tagging-import")
async def tagging_import(course_id: int, dry_run: bool = True, file: UploadFile = File(...),
                         db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    check_course_access(db, u, course_id)
    _course, chapters, _cn, clos, clo_rows, levels = _course_refs(db, course_id)
    data = await _read(file)
    try:
        table = qi.read_table(data, file.filename or "")
    except qi.ImportError_ as ex:
        raise HTTPException(422, str(ex))
    current = {r["id"]: r for r in _question_rows(db, course_id, False, None)}
    code_of = {c["id"]: c["clo_code"] for c in clo_rows}
    bname = {b["id"]: b["name_vi"] for b in levels}
    out, seen = [], set()
    for t in table:
        raw_id = t.get("id", "")
        res = {"row": t["_row"], "id": None, "content": t.get("content", "")[:160], "status": "error", "errors": [], "changes": []}
        if not raw_id.isdigit():
            res["errors"].append("Thiếu hoặc sai ID câu hỏi"); out.append(res); continue
        qid = int(raw_id); res["id"] = qid
        cur = current.get(qid)
        if not cur:
            res["errors"].append("ID không thuộc ngân hàng câu hỏi của môn này (hoặc đã Hủy)"); out.append(res); continue
        res["content"] = cur["content"][:160]
        if qid in seen:
            res["errors"].append("ID lặp lại trong file"); out.append(res); continue
        seen.add(qid)
        outline_id, e1 = qi.parse_chapter(t.get("chapter", ""), chapters)
        bloom_id, e2 = qi.parse_bloom(t.get("bloom", ""), levels)
        links, e3 = qi.parse_clos(t.get("clo", ""), clos)
        res["errors"] += [e for e in (e1, e2, e3) if e]
        if res["errors"]:
            out.append(res); continue
        cur_outline = chapters.get(cur["chapter_number"]) if cur["chapter_number"] else None
        new = {"outline_id": outline_id if outline_id else cur_outline,
               "bloom_level_id": bloom_id or cur["bloom_level_id"],
               "clos": [(code_of[c], w) for c, w in links] if links else cur["clos"]}
        inv_ch = {v: k for k, v in chapters.items()}
        if new["outline_id"] != cur_outline:
            res["changes"].append(f"Chương: {cur['chapter_number'] or '—'} → {inv_ch.get(new['outline_id'])}")
        if new["bloom_level_id"] != cur["bloom_level_id"]:
            res["changes"].append(f"Bloom: {bname.get(cur['bloom_level_id'], '—')} → {bname.get(new['bloom_level_id'])}")
        if sorted(new["clos"]) != sorted(cur["clos"]):
            res["changes"].append(f"CLO: {qi.clo_text(cur['clos']) or '—'} → {qi.clo_text(new['clos'])}")
        res["tagged_after"] = bool(new["clos"]) and bool(new["bloom_level_id"])
        if not res["changes"]:
            res["status"] = "unchanged"
        elif cur["n_results"]:
            res["status"] = "locked"
            res["errors"].append("Câu đã có kết quả thi – không đổi CLO/Bloom/Chương (hãy Hủy và tạo câu mới)")
        else:
            res["status"] = "update"
            res["_new"] = new
        out.append(res)
    updates = [r for r in out if r["status"] == "update"]
    if not dry_run and updates:
        id_of = {v: k for k, v in code_of.items()}
        for r in updates:
            q = db.get(Question, r["id"])
            n = r["_new"]
            q.outline_id, q.bloom_level_id = n["outline_id"], n["bloom_level_id"]
            q.clo_links.clear(); db.flush()
            for code, w in n["clos"]:
                q.clo_links.append(QuestionCLO(clo_id=id_of[code], weight=w))
        db.commit()
    for r in out:
        r.pop("_new", None)
    after_untagged = db.execute(text("""SELECT COUNT(*) FROM question_bank q WHERE q.course_id=:c AND q.is_cancelled=0 AND
                                         (q.bloom_level_id IS NULL OR NOT EXISTS (SELECT 1 FROM question_clo_mapping m WHERE m.question_id=q.id))"""),
                                {"c": course_id}).scalar()
    return {"dry_run": dry_run, "rows": out,
            "summary": {"total": len(out), "update": len(updates), "unchanged": sum(r["status"] == "unchanged" for r in out),
                        "locked": sum(r["status"] == "locked" for r in out), "error": sum(r["status"] == "error" for r in out),
                        "untagged_left": after_untagged}}
