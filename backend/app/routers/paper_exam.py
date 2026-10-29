"""Đề thi giấy sinh & chấm ngay trên hệ thống (song song với Moodle Offline Quiz) – góp ý 15/10.

GV xem trước toàn bộ đề từng mã đề và phiếu trả lời NGAY trên hệ thống (một cột hoặc chia hai cột), chỉnh lời dặn,
tiêu đề, cỡ chữ, số chữ số MSSV… rồi mới xuất PDF/Word để in. Sau khi thi: tải ảnh quét hoặc ảnh chụp điện thoại
phiếu trả lời → hệ thống nhận diện, GV soát/sửa → lưu kết quả và phân tích như mọi bài KT.
"""
import io
import json
import zipfile
from dataclasses import asdict, fields
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_exam_for, require, lecturer_only
from ..http_utils import attachment
from ..models import Exam, User
from ..services import omr, paper, results

router = APIRouter(prefix="/api", tags=["Đề thi giấy & chấm phiếu trên hệ thống"])
PDF, DOCX = "application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SHEET_KEYS = ("title", "school", "student_digits", "version_digits", "essay_lines", "note")


class VersionsIn(BaseModel):
    n_versions: int = Field(default=2, ge=1, le=8)
    shuffle_questions: bool = True
    shuffle_options: bool = True
    seed: Optional[int] = None


class SettingsIn(BaseModel):
    paper: dict = {}
    sheet: dict = {}


class SheetResult(BaseModel):
    student_code: str = Field(min_length=1, max_length=100)
    version_code: str = Field(min_length=1, max_length=10)
    answers: dict[str, str] = {}
    source_name: Optional[str] = None


class CommitIn(BaseModel):
    sheets: list[SheetResult] = Field(min_length=1)
    mark_absent: bool = True          # SV trong danh sách lớp không có phiếu -> vắng
    analyze: bool = True


def _paper(db: Session, u: User, exam_id: int) -> Exam:
    e = get_exam_for(db, u, exam_id)
    if e.exam_type != "paper":
        raise HTTPException(422, "Chỉ bài thi giấy mới in đề / chấm phiếu")
    return e


def _settings(e: Exam) -> dict:
    try:
        s = json.loads(e.paper_settings or "{}")
    except ValueError:
        s = {}
    s.setdefault("paper", {}); s.setdefault("sheet", {})
    return s


def _paper_opts(e: Exam, override: dict | None = None) -> paper.PaperOptions:
    base = {**_settings(e)["paper"], **{k: v for k, v in (override or {}).items() if v is not None}}
    names = {f.name for f in fields(paper.PaperOptions)}
    p = paper.PaperOptions(**{k: v for k, v in base.items() if k in names})
    p.columns = 2 if int(p.columns or 1) == 2 else 1
    p.font_size = max(9.0, min(14.0, float(p.font_size)))
    return p


def _sheet_opts(db: Session, e: Exam, override: dict | None = None) -> paper.SheetOptions:
    s = {**_settings(e)["sheet"], **{k: v for k, v in (override or {}).items() if v is not None}}
    s = {k: v for k, v in s.items() if k in SHEET_KEYS}
    for k in ("student_digits", "version_digits", "essay_lines"):
        if k in s:
            s[k] = int(s[k])
    if not 4 <= s.get("student_digits", 8) <= 12:
        raise HTTPException(422, "Số chữ số MSSV từ 4 đến 12")
    if not 0 <= s.get("essay_lines", 0) <= 15:
        raise HTTPException(422, "Số dòng phần tự luận từ 0 đến 15")
    return paper.sheet_options_for(db, e, **s)


def _semester(e: Exam) -> str:
    return e.class_section.semester.name


@router.get("/exams/{exam_id}/paper")
def paper_state(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """Trạng thái đề giấy: chế độ (hệ thống tự in & chấm / Moodle Offline Quiz), các mã đề với đầy đủ câu, đáp án; tùy chọn in."""
    e = _paper(db, u, exam_id)
    st = _settings(e)
    mode = "moodle" if e.moodle_offlinequiz_id else ("system" if e.versions else None)
    sheet = _sheet_opts(db, e) if e.questions else None
    return {"mode": mode, "versions": paper.versions_data(db, e) if mode == "system" else [],
            "paper": asdict(_paper_opts(e)), "sheet": {k: getattr(sheet, k) for k in SHEET_KEYS} if sheet else {},
            "sheet_printed": bool(st.get("sheet_printed")),
            "n_scanned": db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e AND source='scan'"), {"e": exam_id}).scalar()}


@router.post("/exams/{exam_id}/paper/versions")
def make_versions(exam_id: int, body: VersionsIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    e = _paper(db, u, exam_id)
    try:
        v = paper.generate_versions(db, e, body.n_versions, body.shuffle_questions, body.shuffle_options, body.seed)
    except paper.PaperError as ex:
        db.rollback(); raise HTTPException(409, str(ex))
    if e.status == "Draft":
        e.status = "Published"
    db.commit()
    return {"versions": v}


@router.delete("/exams/{exam_id}/paper/versions")
def delete_versions(exam_id: int, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    """Bỏ các mã đề hệ thống đã sinh (khi chưa chấm phiếu) – để sinh lại hoặc chuyển sang Moodle Offline Quiz."""
    e = _paper(db, u, exam_id)
    if e.moodle_offlinequiz_id:
        raise HTTPException(409, "Mã đề do Moodle Offline Quiz quản lý")
    if db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e"), {"e": exam_id}).scalar():
        raise HTTPException(409, "Bài đã có kết quả chấm – không xóa mã đề được")
    e.versions.clear()
    st = _settings(e); st.pop("sheet_printed", None)
    e.paper_settings = json.dumps(st, ensure_ascii=False)
    db.commit()
    return {"ok": True}


@router.put("/exams/{exam_id}/paper/settings")
def save_settings(exam_id: int, body: SettingsIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    e = _paper(db, u, exam_id)
    st = _settings(e)
    new_sheet = {k: v for k, v in body.sheet.items() if k in SHEET_KEYS}
    layout_keys = ("student_digits", "version_digits", "essay_lines")
    if st.get("sheet_printed") and any(str(new_sheet.get(k, st["sheet"].get(k))) != str(st["sheet"].get(k)) for k in layout_keys if k in new_sheet) \
            and db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e AND source='scan'"), {"e": exam_id}).scalar():
        raise HTTPException(409, "Đã chấm phiếu theo bố cục cũ – không đổi số chữ số MSSV/mã đề hoặc số dòng tự luận được")
    st["paper"] = {k: v for k, v in body.paper.items() if k in {f.name for f in fields(paper.PaperOptions)}}
    st["sheet"] = new_sheet
    _paper_opts(e, st["paper"]); _sheet_opts(db, e, st["sheet"])          # kiểm tra hợp lệ
    e.paper_settings = json.dumps(st, ensure_ascii=False)
    db.commit()
    return {"ok": True}


def _version(e: Exam, db: Session, code: str | None):
    vs = paper.versions_data(db, e)
    if not vs:
        raise HTTPException(409, "Chưa sinh mã đề – bấm 'Sinh mã đề' trước")
    if code and code != "all":
        vs = [v for v in vs if v["version_code"] == code]
        if not vs:
            raise HTTPException(404, "Không có mã đề này")
    return vs


@router.get("/exams/{exam_id}/paper/exam.{fmt}")
def exam_file(exam_id: int, fmt: str, version: str = "all", columns: Optional[int] = None,
              u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = _paper(db, u, exam_id)
    vs = _version(e, db, version)
    p = _paper_opts(e, {"columns": columns})
    name = f"De_{e.class_section.section_code}_{e.exam_title}" + (f"_ma_de_{version}" if version != "all" else "")
    if fmt == "docx":
        return Response(paper.exam_docx(e, vs, p, _semester(e)), media_type=DOCX, headers=attachment(name + ".docx"))
    if fmt != "pdf":
        raise HTTPException(404, "Định dạng phải là pdf hoặc docx")
    if len(vs) == 1:
        return Response(paper.exam_pdf(e, vs[0], p, _semester(e)), media_type=PDF, headers=attachment(name + ".pdf"))
    import fitz
    out = fitz.open()
    for v in vs:
        out.insert_pdf(fitz.open(stream=paper.exam_pdf(e, v, p, _semester(e)), filetype="pdf"))
    return Response(out.tobytes(), media_type=PDF, headers=attachment(name + ".pdf"))


@router.get("/exams/{exam_id}/paper/answer-sheet.{fmt}")
def answer_sheet(exam_id: int, fmt: str, copies: int = 1, title: Optional[str] = None, student_digits: Optional[int] = None,
                 version_digits: Optional[int] = None, essay_lines: Optional[int] = None, u: User = Depends(require("admin", "lecturer")),
                 db: Session = Depends(get_db)):
    """Phiếu trả lời: png = ảnh xem trước (theo tham số đang chỉnh); pdf = tệp in (theo cài đặt đã lưu)."""
    e = _paper(db, u, exam_id)
    if not e.questions:
        raise HTTPException(422, "Bài kiểm tra chưa có câu hỏi")
    try:
        if fmt == "png":
            o = _sheet_opts(db, e, {"title": title, "student_digits": student_digits, "version_digits": version_digits, "essay_lines": essay_lines})
            return Response(paper.sheet_png(o), media_type="image/png")
        if fmt != "pdf":
            raise HTTPException(404, "Định dạng phải là pdf hoặc png")
        o = _sheet_opts(db, e)
        data = paper.sheet_pdf(o, copies=max(1, min(copies, 200)))
    except paper.PaperError as ex:
        raise HTTPException(422, str(ex))
    st = _settings(e)
    if not st.get("sheet_printed"):
        st["sheet_printed"] = True
        e.paper_settings = json.dumps(st, ensure_ascii=False); db.commit()
    return Response(data, media_type=PDF, headers=attachment(f"PhieuTraLoi_{e.class_section.section_code}_{e.exam_title}.pdf"))


@router.get("/exams/{exam_id}/paper/answer-key.pdf")
def answer_key(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = _paper(db, u, exam_id)
    return Response(paper.answer_key_pdf(e, _version(e, db, None)), media_type=PDF,
                    headers=attachment(f"DapAn_{e.class_section.section_code}_{e.exam_title}.pdf"))


@router.get("/exams/{exam_id}/paper/package.zip")
def package(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """Trọn bộ để in: đề từng mã đề (PDF + Word), phiếu trả lời, đáp án."""
    e = _paper(db, u, exam_id)
    vs = _version(e, db, None)
    p = _paper_opts(e)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for v in vs:
            z.writestr(f"de_ma_{v['version_code']}.pdf", paper.exam_pdf(e, v, p, _semester(e)))
            z.writestr(f"de_ma_{v['version_code']}.docx", paper.exam_docx(e, [v], p, _semester(e)))
        z.writestr("phieu_tra_loi.pdf", paper.sheet_pdf(_sheet_opts(db, e)))
        z.writestr("dap_an.pdf", paper.answer_key_pdf(e, vs))
    st = _settings(e); st["sheet_printed"] = True
    e.paper_settings = json.dumps(st, ensure_ascii=False); db.commit()
    return Response(buf.getvalue(), media_type="application/zip", headers=attachment(f"DeThiGiay_{e.class_section.section_code}_bai_{e.id}.zip"))


# ------------------------------------------------------------------ chấm phiếu
async def _read_files(db: Session, e: Exam, files: list[UploadFile]) -> tuple[list, dict]:
    """Đọc các tệp ảnh/PDF -> danh sách kết quả từng trang (đã đối chiếu danh sách lớp, chấm thử) + các mã đề."""
    vs = {v["version_code"]: v for v in paper.versions_data(db, e)}
    if not vs:
        raise HTTPException(409, "Chưa sinh mã đề")
    o = _sheet_opts(db, e)
    roster = {r[0]: r[1] for r in db.execute(text("""SELECT s.student_code, s.full_name FROM enrollments en JOIN students s ON s.id=en.student_id
                                                     WHERE en.class_section_id=:cs"""), {"cs": e.class_section_id})}
    out = []
    total = 0
    for f in files[:200]:
        data = await f.read()
        total += len(data)
        if total > 80 * 1024 * 1024:
            raise HTTPException(413, "Tổng dung lượng ảnh tối đa 80 MB mỗi lần")
        try:
            pages = omr.load_pages(data, f.filename or "")
        except omr.OMRError as ex:
            out.append({"source_name": f.filename, "error": str(ex)}); continue
        for k, g in enumerate(pages):
            name = f.filename + (f" – trang {k + 1}" if len(pages) > 1 else "")
            try:
                r = omr.read_sheet(g, o)
            except (omr.OMRError, paper.PaperError) as ex:
                out.append({"source_name": name, "error": str(ex)}); continue
            v = vs.get(r["version_code"])
            if not v:
                r["issues"].insert(0, f"Mã đề '{r['version_code']}' không có trong bài (có: {', '.join(vs)})")
            if r["student_code"] not in roster:
                r["issues"].insert(0, f"MSSV '{r['student_code']}' không có trong danh sách lớp")
            r.update({"source_name": name, "full_name": roster.get(r["student_code"])})
            if v:   # chấm thử để GV xem điểm ngay
                ans = {q["position"]: q["answer"] for q in v["questions"]}
                pts = {q["position"]: q["points"] for q in v["questions"]}
                r["score"] = round(sum(pts[p] for p, a in r["answers"].items() if p in ans and a == ans[p]), 2)
                r["raw_max"] = round(sum(pts.values()), 2)
            r["answers"] = {str(k2): v2 for k2, v2 in r["answers"].items()}
            out.append(r)
    return out, vs


@router.post("/exams/{exam_id}/scan")
async def scan(exam_id: int, files: list[UploadFile] = File(...), u: User = Depends(lecturer_only),
               db: Session = Depends(get_db)):
    """Nhận diện phiếu từ ảnh quét / ảnh chụp (JPG, PNG) hoặc PDF nhiều trang. Chưa ghi CSDL – GV soát rồi lưu (scan/commit)."""
    e = _paper(db, u, exam_id)
    if e.moodle_offlinequiz_id:
        raise HTTPException(409, "Bài dùng Moodle Offline Quiz – tải phiếu lên Moodle để chấm")
    out, vs = await _read_files(db, e, files)
    return {"sheets": out, "n_questions": _sheet_opts(db, e).n_questions, "versions": list(vs)}


# ---------------------------------------------------------------- Quét là chấm & lưu ngay (phiếu sai MSSV/mã đề chờ GV xử lý)
def _roster_ids(db: Session, e: Exam) -> dict:
    return {r[0]: (r[1], r[2]) for r in db.execute(text("""SELECT s.student_code, s.id, s.full_name FROM enrollments en JOIN students s ON s.id=en.student_id
                                                           WHERE en.class_section_id=:cs"""), {"cs": e.class_section_id})}


def _problems(code: str, vcode: str, vs: dict, roster: dict) -> list[str]:
    out = []
    if not code or "?" in code:
        out.append("MSSV đọc chưa đủ (có cột chưa tô hoặc tô nhiều ô) – nhập lại MSSV")
    elif code not in roster:
        out.append(f"MSSV '{code}' không có trong danh sách lớp")
    if vcode not in vs:
        out.append(f"Mã đề '{vcode}' không có trong bài (có: {', '.join(vs)})")
    return out


def _suggest(code: str, roster: dict, k: int = 3) -> list[dict]:
    """MSSV trong lớp gần nhất với mã đọc được (đếm số chữ số khác nhau, '?' tính là khác); tối đa 2 chữ số lệch."""
    cand = []
    for c, (sid, name) in roster.items():
        if len(c) != len(code):
            continue
        d = sum(1 for a, b in zip(c, code) if a != b)
        if d <= 2:
            cand.append((d, c, name))
    return [{"student_code": c, "full_name": n} for d, c, n in sorted(cand)[:k]]


def _write_attempt(db: Session, e: Exam, student_id: int, v: dict, vid: int, answers: dict) -> int:
    """Chấm một phiếu (Reverse Shuffle: nhãn in trên mã đề -> phương án gốc) và ghi thay kết quả cũ của SV này."""
    db.execute(text("DELETE FROM exam_attempts WHERE exam_id=:e AND student_id=:s"), {"e": e.id, "s": student_id})
    aid = db.execute(text("""INSERT INTO exam_attempts (exam_id, student_id, version_id, source, finished_at, status, total_score)
                             VALUES (:e, :s, :v, 'scan', NOW(), 'finished', 0)"""), {"e": e.id, "s": student_id, "v": vid}).lastrowid
    total = 0.0
    for q in v["questions"]:
        lab = (answers.get(str(q["position"])) or "").strip().upper()
        opt = next((o for o in q["options"] if o["label"] == lab), None) if len(lab) == 1 else None
        ok = bool(opt) and lab == q["answer"]
        sc = q["points"] if ok else 0.0
        total += sc
        db.execute(text("""INSERT INTO item_level_results (attempt_id, question_id, selected_option_id, response_status, is_correct, score_earned)
                           VALUES (:a, :q, :o, :st, :ok, :sc)"""),
                   {"a": aid, "q": q["question_id"], "o": opt["option_id"] if opt else None,
                    "st": "answered" if opt else "blank", "ok": ok, "sc": sc})
    db.execute(text("UPDATE exam_attempts SET total_score=:t WHERE id=:a"), {"t": round(total, 2), "a": aid})
    return aid


def _score(v: dict | None, answers: dict) -> tuple[Optional[float], Optional[float]]:
    if not v:
        return None, None
    ans = {str(q["position"]): q["answer"] for q in v["questions"]}
    pts = {str(q["position"]): q["points"] for q in v["questions"]}
    return round(sum(pts[p] for p, a in answers.items() if p in ans and a == ans[p]), 2), round(sum(pts.values()), 2)


def _apply_sheet(db: Session, e: Exam, sid: int, vs: dict, roster: dict, vid: dict) -> dict:
    """Đặt trạng thái phiếu theo nội dung hiện tại: hợp lệ -> chấm & ghi kết quả lớp (saved), ngược lại -> chờ GV (review)."""
    row = db.execute(text("SELECT * FROM scan_sheets WHERE id=:i AND exam_id=:e"), {"i": sid, "e": e.id}).mappings().first()
    if not row:
        raise HTTPException(404, "Không có phiếu này")
    answers = json.loads(row["answers"] or "{}")
    code, vcode = (row["student_code"] or "").strip(), (row["version_code"] or "").strip()
    probs = _problems(code, vcode, vs, roster)
    v = vs.get(vcode)
    score, raw_max = _score(v, answers)
    if row["attempt_id"]:   # phiếu từng được ghi: gỡ kết quả cũ (có thể đã đổi SV hoặc đáp án)
        db.execute(text("DELETE FROM exam_attempts WHERE id=:a"), {"a": row["attempt_id"]})
    aid, status = None, "review"
    if not probs:
        aid = _write_attempt(db, e, roster[code][0], v, vid[vcode], answers)
        status = "saved"
        db.execute(text("""UPDATE scan_sheets SET status='superseded', attempt_id=NULL WHERE exam_id=:e AND student_code=:c AND id<>:i AND status='saved'"""),
                   {"e": e.id, "c": code, "i": sid})
    db.execute(text("""UPDATE scan_sheets SET student_code=:c, version_code=:v, score=:sc, raw_max=:mx, issues=:iss, status=:st, attempt_id=:a WHERE id=:i"""),
               {"c": code, "v": vcode, "sc": score, "mx": raw_max, "iss": json.dumps(probs, ensure_ascii=False), "st": status, "a": aid, "i": sid})
    return {"id": sid, "status": status, "issues": probs}


def _sheet_row(r, roster: dict) -> dict:
    d = {"id": r["id"], "source_name": r["source_name"], "student_code": r["student_code"], "version_code": r["version_code"],
         "full_name": roster.get(r["student_code"], (None, None))[1], "score": float(r["score"]) if r["score"] is not None else None,
         "raw_max": float(r["raw_max"]) if r["raw_max"] is not None else None, "confidence": float(r["confidence"] or 0),
         "issues": json.loads(r["issues"] or "[]"), "status": r["status"], "created_at": r["created_at"].isoformat() if r["created_at"] else None}
    if r["status"] == "review":
        d["suggest"] = _suggest(r["student_code"] or "", roster)
    return d


@router.post("/exams/{exam_id}/scan/save")
async def scan_save(exam_id: int, files: list[UploadFile] = File(...), u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    """Quét là chấm & lưu ngay: phiếu có MSSV thuộc lớp và mã đề hợp lệ được chấm vào kết quả lớp luôn; phiếu còn lỗi được lưu ở
    danh sách "cần xử lý" để giảng viên sửa MSSV/mã đề/đáp án sau (xem scan/sheets). Phân tích chạy khi bấm Hoàn tất (scan/finish)."""
    e = _paper(db, u, exam_id)
    if e.moodle_offlinequiz_id:
        raise HTTPException(409, "Bài dùng Moodle Offline Quiz – tải phiếu lên Moodle để chấm")
    out, vs = await _read_files(db, e, files)
    roster, vid = _roster_ids(db, e), {v.version_code: v.id for v in e.versions}
    res = []
    for r in out:
        if r.get("error"):
            res.append({"source_name": r["source_name"], "error": r["error"]}); continue
        sid = db.execute(text("""INSERT INTO scan_sheets (exam_id, source_name, student_code, version_code, answers, confidence, image)
                                 VALUES (:e, :n, :c, :v, :a, :cf, :im)"""),
                         {"e": exam_id, "n": r["source_name"], "c": r["student_code"] or "", "v": r["version_code"] or "",
                          "a": json.dumps(r["answers"]), "cf": r.get("confidence"), "im": r.get("image")}).lastrowid
        _apply_sheet(db, e, sid, vs, roster, vid)
        row = db.execute(text("SELECT * FROM scan_sheets WHERE id=:i"), {"i": sid}).mappings().first()
        res.append(_sheet_row(row, roster))
    if any(x.get("status") == "saved" for x in res):
        from datetime import datetime
        e.status = "Synced"; e.last_synced_at = datetime.now()
    db.commit()
    return {"sheets": res, "saved": sum(1 for x in res if x.get("status") == "saved"),
            "review": sum(1 for x in res if x.get("status") == "review"), "errors": sum(1 for x in res if x.get("error"))}


@router.get("/exams/{exam_id}/scan/sheets")
def scan_sheets(exam_id: int, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    """Danh sách phiếu đã quét của bài (không kèm ảnh): đã chấm / cần xử lý, kèm gợi ý MSSV gần đúng và danh sách lớp để chọn."""
    e = _paper(db, u, exam_id)
    roster = _roster_ids(db, e)
    rows = db.execute(text("SELECT id, source_name, student_code, version_code, score, raw_max, confidence, issues, status, created_at, answers "
                           "FROM scan_sheets WHERE exam_id=:e AND status<>'superseded' ORDER BY (status='review') DESC, id DESC"), {"e": exam_id}).mappings().all()
    sheets = [_sheet_row(r, roster) for r in rows]
    return {"sheets": sheets, "n_saved": sum(1 for s in sheets if s["status"] == "saved"), "n_review": sum(1 for s in sheets if s["status"] == "review"),
            "roster": [{"student_code": c, "full_name": n} for c, (_i, n) in sorted(roster.items())],
            "n_absent_if_finish": sum(1 for c, (sid, _n) in roster.items()
                                      if not db.execute(text("SELECT 1 FROM exam_attempts WHERE exam_id=:e AND student_id=:s AND status<>'absent'"), {"e": exam_id, "s": sid}).scalar())}


@router.get("/exams/{exam_id}/scan/sheets/{sheet_id}")
def scan_sheet_detail(exam_id: int, sheet_id: int, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    e = _paper(db, u, exam_id)
    roster = _roster_ids(db, e)
    r = db.execute(text("SELECT * FROM scan_sheets WHERE id=:i AND exam_id=:e"), {"i": sheet_id, "e": exam_id}).mappings().first()
    if not r:
        raise HTTPException(404, "Không có phiếu này")
    return {**_sheet_row(r, roster), "image": r["image"], "answers": json.loads(r["answers"] or "{}")}


class SheetPatch(BaseModel):
    student_code: Optional[str] = Field(default=None, max_length=100)
    version_code: Optional[str] = Field(default=None, max_length=10)
    answers: Optional[dict[str, str]] = None


@router.patch("/exams/{exam_id}/scan/sheets/{sheet_id}")
def scan_sheet_fix(exam_id: int, sheet_id: int, body: SheetPatch, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    """GV sửa MSSV / mã đề / đáp án của phiếu: hợp lệ thì chấm lại & ghi vào kết quả lớp, chưa hợp lệ thì vẫn ở danh sách cần xử lý."""
    e = _paper(db, u, exam_id)
    if not db.execute(text("SELECT 1 FROM scan_sheets WHERE id=:i AND exam_id=:e"), {"i": sheet_id, "e": exam_id}).scalar():
        raise HTTPException(404, "Không có phiếu này")
    upd, par = [], {"i": sheet_id}
    if body.student_code is not None:
        upd.append("student_code=:c"); par["c"] = body.student_code.strip()
    if body.version_code is not None:
        upd.append("version_code=:v"); par["v"] = body.version_code.strip()
    if body.answers is not None:
        upd.append("answers=:a"); par["a"] = json.dumps({str(k): (v or "").strip().upper()[:2] for k, v in body.answers.items()})
    if upd:
        db.execute(text(f"UPDATE scan_sheets SET {', '.join(upd)}, status='review' WHERE id=:i"), par)
    vs = {v["version_code"]: v for v in paper.versions_data(db, e)}
    out = _apply_sheet(db, e, sheet_id, vs, _roster_ids(db, e), {v.version_code: v.id for v in e.versions})
    if out["status"] == "saved":
        from datetime import datetime
        e.status = "Synced"; e.last_synced_at = datetime.now()
    db.commit()
    return out


@router.delete("/exams/{exam_id}/scan/sheets/{sheet_id}")
def scan_sheet_drop(exam_id: int, sheet_id: int, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    """Xóa phiếu (quét nhầm / trùng); nếu phiếu đã được chấm vào kết quả lớp thì gỡ kết quả đó."""
    _paper(db, u, exam_id)
    r = db.execute(text("SELECT attempt_id FROM scan_sheets WHERE id=:i AND exam_id=:e"), {"i": sheet_id, "e": exam_id}).first()
    if not r:
        raise HTTPException(404, "Không có phiếu này")
    if r[0]:
        db.execute(text("DELETE FROM exam_attempts WHERE id=:a"), {"a": r[0]})
    db.execute(text("DELETE FROM scan_sheets WHERE id=:i"), {"i": sheet_id})
    db.commit()
    return {"deleted": sheet_id}


class FinishIn(BaseModel):
    mark_absent: bool = True
    analyze: bool = True


@router.post("/exams/{exam_id}/scan/finish")
def scan_finish(exam_id: int, body: FinishIn = FinishIn(), u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    """Hoàn tất đợt chấm: SV trong lớp chưa có bài -> vắng, rồi chạy phân tích CĐR. Còn phiếu cần xử lý thì báo để GV biết (vẫn hoàn tất được)."""
    e = _paper(db, u, exam_id)
    roster = _roster_ids(db, e)
    n_abs = 0
    if body.mark_absent:
        for code, (sid, _n) in roster.items():
            if not db.execute(text("SELECT 1 FROM exam_attempts WHERE exam_id=:e AND student_id=:s"), {"e": exam_id, "s": sid}).scalar():
                db.execute(text("INSERT INTO exam_attempts (exam_id, student_id, source, status, total_score) VALUES (:e, :s, 'scan', 'absent', 0)"),
                           {"e": exam_id, "s": sid}); n_abs += 1
    n_saved = db.execute(text("SELECT COUNT(*) FROM scan_sheets WHERE exam_id=:e AND status='saved'"), {"e": exam_id}).scalar()
    n_review = db.execute(text("SELECT COUNT(*) FROM scan_sheets WHERE exam_id=:e AND status='review'"), {"e": exam_id}).scalar()
    db.execute(text("INSERT INTO sync_runs (exam_id, kind, status, finished_at, n_attempts, n_absent, message) VALUES (:e,'scan','success',NOW(),:n,:a,:m)"),
               {"e": exam_id, "n": n_saved, "a": n_abs, "m": f"Hoàn tất chấm phiếu: {n_saved} phiếu đã chấm, {n_review} phiếu còn chờ xử lý"})
    from datetime import datetime
    e.status = "Synced"; e.last_synced_at = datetime.now()
    db.commit()
    res = {"saved": n_saved, "review": n_review, "absent": n_abs}
    if body.analyze and n_saved:
        res["analysis"] = results.analyze_exam(db, exam_id)
    return res


@router.post("/exams/{exam_id}/scan/commit")
def scan_commit(exam_id: int, body: CommitIn, u: User = Depends(lecturer_only), db: Session = Depends(get_db)):
    """Lưu kết quả phiếu đã soát: Reverse Shuffle nhãn in trên mã đề -> phương án gốc, chấm và phân tích."""
    e = _paper(db, u, exam_id)
    vs = {v["version_code"]: v for v in paper.versions_data(db, e)}
    vid = {v.version_code: v.id for v in e.versions}
    roster = {r[0]: r[1] for r in db.execute(text("""SELECT s.student_code, s.id FROM enrollments en JOIN students s ON s.id=en.student_id
                                                     WHERE en.class_section_id=:cs"""), {"cs": e.class_section_id})}
    errs = [f"{s.source_name or s.student_code}: MSSV {s.student_code} không thuộc lớp" for s in body.sheets if s.student_code not in roster]
    errs += [f"{s.source_name or s.student_code}: mã đề {s.version_code} không có" for s in body.sheets if s.version_code not in vs]
    if errs:
        raise HTTPException(422, "; ".join(errs[:10]))
    seen = {}
    for s in body.sheets:
        seen[s.student_code] = s                    # quét lại nhiều lần: lấy phiếu sau cùng
    run = db.execute(text("INSERT INTO sync_runs (exam_id, kind) VALUES (:e, 'scan')"), {"e": exam_id}).lastrowid
    for code in seen:                               # chấm bổ sung theo đợt: chỉ thay kết quả của SV có phiếu trong đợt này
        db.execute(text("DELETE FROM exam_attempts WHERE exam_id=:e AND student_id=:s"), {"e": exam_id, "s": roster[code]})
    n_abs = 0
    for code, s in seen.items():
        v = vs[s.version_code]
        aid = db.execute(text("""INSERT INTO exam_attempts (exam_id, student_id, version_id, source, finished_at, status, total_score)
                                 VALUES (:e, :s, :v, 'scan', NOW(), 'finished', 0)"""),
                         {"e": exam_id, "s": roster[code], "v": vid[s.version_code]}).lastrowid
        total = 0.0
        for q in v["questions"]:
            lab = (s.answers.get(str(q["position"])) or "").strip().upper()
            opt = next((o for o in q["options"] if o["label"] == lab), None) if len(lab) == 1 else None
            ok = bool(opt) and lab == q["answer"]
            sc = q["points"] if ok else 0.0
            total += sc
            db.execute(text("""INSERT INTO item_level_results (attempt_id, question_id, selected_option_id, response_status, is_correct, score_earned)
                               VALUES (:a, :q, :o, :st, :ok, :sc)"""),
                       {"a": aid, "q": q["question_id"], "o": opt["option_id"] if opt else None,
                        "st": "answered" if opt else "blank", "ok": ok, "sc": sc})
        db.execute(text("UPDATE exam_attempts SET total_score=:t WHERE id=:a"), {"t": round(total, 2), "a": aid})
    if body.mark_absent:
        for code, sid in roster.items():
            if code not in seen and not db.execute(text("SELECT 1 FROM exam_attempts WHERE exam_id=:e AND student_id=:s"),
                                                   {"e": exam_id, "s": sid}).scalar():
                db.execute(text("INSERT INTO exam_attempts (exam_id, student_id, source, status, total_score) VALUES (:e, :s, 'scan', 'absent', 0)"),
                           {"e": exam_id, "s": sid})
                n_abs += 1
    e.status = "Synced"
    from datetime import datetime
    e.last_synced_at = datetime.now()
    db.execute(text("UPDATE sync_runs SET status='success', finished_at=NOW(), n_attempts=:n, n_absent=:a, message=:m WHERE id=:r"),
               {"n": len(seen), "a": n_abs, "r": run, "m": f"Chấm {len(body.sheets)} phiếu trên hệ thống ({len(seen)} SV)"})
    db.commit()
    res = {"saved": len(seen), "absent": n_abs, "duplicates": len(body.sheets) - len(seen)}
    if body.analyze and seen:
        res["analysis"] = results.analyze_exam(db, exam_id)
    return res
