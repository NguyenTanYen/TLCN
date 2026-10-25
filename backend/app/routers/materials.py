"""Học liệu của học phần (giáo trình, slide, tài liệu tham khảo) và gợi ý đọc đúng trang cho câu SV làm sai (RAG).

Chỉ học liệu thuộc học phần đó mới được dùng để gợi ý. GV tải lên ở đây; có thể đẩy lên khóa học Moodle và lấy từ Moodle về
(routers/lms.py). Chỉ mục BM25 chạy ngay trên máy; VLM (VLM_URL) là tùy chọn cho trang hình/sơ đồ.
"""
from pathlib import Path
from typing import Optional

from pydantic import BaseModel
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require
from ..models import Course, User
from ..services import lms, materials, readings

router = APIRouter(prefix="/api", tags=["Học liệu và gợi ý đọc (RAG)"])
TYPES = ("slide", "textbook", "reference", "other")


def _row(db: Session, mid: int):
    r = db.execute(text("SELECT * FROM course_materials WHERE id=:i"), {"i": mid}).mappings().first()
    if not r:
        raise HTTPException(404, "Không tìm thấy học liệu")
    return r


@router.get("/courses/{cid}/materials")
def list_materials(cid: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    if not db.get(Course, cid):
        raise HTTPException(404, "Không tìm thấy học phần")
    rows = db.execute(text("""
        SELECT m.id, m.title, m.material_type, m.file_name, m.file_ext, m.n_pages, m.source, m.created_at, m.outline_id,
               m.moodle_course_id, m.moodle_cmid, o.chapter_number, o.chapter_name,
               (SELECT COUNT(*) FROM material_chunks c WHERE c.material_id=m.id AND c.from_vlm=1) AS n_vlm
        FROM course_materials m LEFT JOIN course_outlines o ON o.id=m.outline_id
        WHERE m.course_id=:c ORDER BY m.created_at, m.id"""), {"c": cid}).mappings().all()
    return [{**r, "chapter": f"Chương {r['chapter_number']}. {r['chapter_name']}" if r["chapter_number"] else None} for r in rows]


@router.post("/courses/{cid}/materials", status_code=201)
async def upload_material(cid: int, file: UploadFile = File(...), title: Optional[str] = Form(None), material_type: str = Form("slide"),
                          outline_id: Optional[int] = Form(None), db: Session = Depends(get_db),
                          u: User = Depends(require("admin", "lecturer"))):
    if not db.get(Course, cid):
        raise HTTPException(404, "Không tìm thấy học phần")
    if material_type not in TYPES:
        raise HTTPException(422, f"Loại học liệu phải là một trong {', '.join(TYPES)}")
    if outline_id and not db.execute(text("SELECT 1 FROM course_outlines WHERE id=:o AND course_id=:c"), {"o": outline_id, "c": cid}).first():
        raise HTTPException(422, "Chương không thuộc học phần này")
    data = await file.read()
    name = file.filename or "tai_lieu"
    try:
        r = materials.add_material(db, course_id=cid, title=(title or name.rsplit(".", 1)[0]).strip(), filename=name, data=data,
                                   material_type=material_type, outline_id=outline_id, user_id=u.id)
    except ValueError as ex:
        raise HTTPException(422, str(ex))
    return r


@router.delete("/materials/{mid}")
def delete_material(mid: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    _row(db, mid)
    materials.delete_material(db, mid)
    return {"ok": True}


@router.post("/materials/{mid}/reindex")
def reindex(mid: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    _row(db, mid)
    return {"n_pages": materials.index_material(db, mid)}


@router.get("/materials/{mid}/file")
def download(mid: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    r = _row(db, mid)
    if not Path(r["file_path"]).exists():
        raise HTTPException(404, "Tệp gốc không còn trên máy chủ")
    return FileResponse(r["file_path"], filename=r["file_name"])


@router.get("/materials/{mid}/pages/{page}")
def page_text(mid: int, page: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    _row(db, mid)
    r = db.execute(text("SELECT page_no, heading, content, from_vlm FROM material_chunks WHERE material_id=:m AND page_no=:p"),
                   {"m": mid, "p": page}).mappings().first()
    if not r:
        raise HTTPException(404, "Không có trang này")
    return dict(r)


@router.get("/courses/{cid}/materials/search")
def search(cid: int, q: str = Query(min_length=2), k: int = Query(5, ge=1, le=20), outline_id: Optional[int] = None,
           db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    """Thử truy xuất: gõ câu hỏi/thuật ngữ → trang/slide của học liệu thuộc học phần này."""
    return {"query": q, "hits": materials.search(db, cid, q, k=k, outline_id=outline_id)}


@router.post("/exams/{eid}/readings/rebuild")
def rebuild_readings(eid: int, db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    """Tạo lại gợi ý đọc của cả bài KT từ học liệu hiện có (dùng sau khi tải thêm học liệu, không cần phân tích lại)."""
    e = db.execute(text("""SELECT e.id, e.status, COALESCE(e.course_id, cs.course_id) AS course_id FROM exams e
                           LEFT JOIN class_sections cs ON cs.id=e.class_section_id WHERE e.id=:e"""), {"e": eid}).first()
    if not e:
        raise HTTPException(404, "Không tìm thấy bài kiểm tra")
    if e.status != "Analyzed":
        raise HTTPException(409, "Bài chưa được phân tích – chạy phân tích trước")
    paths = db.execute(text("""SELECT p.id, p.attempt_id FROM personalized_learning_paths p JOIN exam_attempts a ON a.id=p.attempt_id
                               WHERE a.exam_id=:e"""), {"e": eid}).all()
    wrong: dict[int, list[int]] = {}
    for r in db.execute(text("""SELECT r.attempt_id, r.question_id FROM item_level_results r JOIN exam_attempts a ON a.id=r.attempt_id
                                JOIN question_bank q ON q.id=r.question_id
                                WHERE a.exam_id=:e AND r.is_correct=0 AND q.is_cancelled=0"""), {"e": eid}):
        wrong.setdefault(r.attempt_id, []).append(r.question_id)
    qt = readings.question_texts(db, [q for v in wrong.values() for q in v])
    n = 0
    for pid, att in paths:
        found = readings.readings_for_questions(db, e.course_id, wrong.get(att, []), qt)
        readings.store(db, pid, found)
        n += bool(found)
    db.commit()
    return {"n_students": len(paths), "n_with_readings": n}


# ------------------------------------------------------------------ đồng bộ hai chiều với khóa học Moodle
class MoodleIn(BaseModel):
    moodle_course_id: Optional[int] = None


def _moodle_course(db: Session, cid: int, given: Optional[int]) -> int:
    if given:
        return given
    r = db.execute(text("SELECT moodle_course_id FROM class_sections WHERE course_id=:c AND moodle_course_id IS NOT NULL LIMIT 1"), {"c": cid}).scalar()
    if not r:
        raise HTTPException(409, "Học phần chưa có lớp nào gắn với khóa học Moodle – chọn khóa Moodle ở trang lớp học phần trước")
    return int(r)


@router.post("/courses/{cid}/materials/sync-moodle")
def sync_from_moodle(cid: int, body: MoodleIn = MoodleIn(), db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    """Lấy học liệu đã có trong khóa học Moodle (hoạt động Tệp/Thư mục: PDF, PPTX, DOCX, TXT, MD) về lập chỉ mục.
    Tệp đã lấy và chưa đổi thì bỏ qua; tệp bị sửa trên Moodle thì lấy lại bản mới."""
    if not db.get(Course, cid):
        raise HTTPException(404, "Không tìm thấy học phần")
    mcid = _moodle_course(db, cid, body.moodle_course_id)
    try:
        files = lms.course_files(mcid)
    except lms.MoodleWSError as ex:
        raise HTTPException(502, str(ex))
    added = updated = skipped = 0
    errors: list[str] = []
    for f in files:
        ext = f["filename"].rsplit(".", 1)[-1].lower() if "." in f["filename"] else ""
        if ext not in materials.ALLOWED:
            skipped += 1
            continue
        # tệp đã có: cùng địa chỉ tệp Moodle, hoặc chính là tệp hệ thống đã đẩy lên (cùng khóa học + cùng course module)
        old = db.execute(text("SELECT id, moodle_modified FROM course_materials WHERE course_id=:c AND "
                              "(moodle_file_url=:u OR (moodle_course_id=:mc AND moodle_cmid=:cm)) ORDER BY id LIMIT 1"),
                         {"c": cid, "u": f["url"], "mc": mcid, "cm": f["cmid"]}).first()
        if old and (old.moodle_modified is None or old.moodle_modified >= (f["modified"] or 0)):
            skipped += 1
            continue
        try:
            data, _ = lms.download(f["url"])
            r = materials.add_material(db, course_id=cid, title=f["name"] or f["filename"], filename=f["filename"], data=data,
                                       material_type="slide" if ext == "pptx" else "reference", user_id=u.id, source="moodle",
                                       moodle={"course_id": mcid, "cmid": f["cmid"], "url": f["url"]})
            db.execute(text("UPDATE course_materials SET moodle_modified=:m WHERE id=:i"), {"m": f["modified"] or 0, "i": r["id"]})
            db.commit()
            if old:                                  # bản mới đã lập chỉ mục xong mới bỏ bản cũ
                materials.delete_material(db, old.id)
            updated += bool(old)
            added += not old
        except (lms.MoodleWSError, ValueError) as ex:
            errors.append(f"{f['filename']}: {ex}")
    return {"moodle_course_id": mcid, "n_files": len(files), "added": added, "updated": updated, "skipped": skipped, "errors": errors}


@router.post("/materials/{mid}/push-moodle")
def push_to_moodle(mid: int, body: MoodleIn = MoodleIn(), db: Session = Depends(get_db), u: User = Depends(require("admin", "lecturer"))):
    """Đẩy học liệu lên khóa học Moodle thành hoạt động Tệp để sinh viên xem ngay trên Moodle."""
    m = _row(db, mid)
    if m["source"] == "moodle":
        raise HTTPException(409, "Học liệu này vốn lấy từ Moodle")
    if m["moodle_cmid"]:
        return {"cmid": m["moodle_cmid"], "created": False}
    mcid = _moodle_course(db, m["course_id"], body.moodle_course_id)
    try:
        r = lms.add_resource(mcid, m["title"], m["file_name"], Path(m["file_path"]).read_bytes())
    except lms.MoodleWSError as ex:
        raise HTTPException(502, str(ex))
    db.execute(text("UPDATE course_materials SET moodle_course_id=:c, moodle_cmid=:m WHERE id=:i"), {"c": mcid, "m": r["cmid"], "i": mid})
    db.commit()
    return r
