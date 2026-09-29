"""UC-03: Đồng bộ Moodle / nhập bài giấy và phân tích dữ liệu."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_exam_for, require
from ..models import User
from ..services import moodle, paper, results

router = APIRouter(prefix="/api", tags=["UC-03 Đồng bộ & phân tích"])


def _db_error(ex: DBAPIError) -> str:
    orig = getattr(ex, "orig", None)
    return orig.args[1] if orig is not None and len(getattr(orig, "args", ())) > 1 else str(ex)


@router.post("/exams/{exam_id}/sync")
def sync_moodle(exam_id: int, analyze: bool = True, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    if e.exam_type != "online":
        raise HTTPException(422, "Bài thi giấy: hãy dùng chức năng nhập phiếu trả lời")
    if not e.moodle_quiz_id:
        raise HTTPException(422, "Bài KT chưa được liên kết với Moodle Quiz (moodle_quiz_id)")
    try:
        sync = moodle.sync_exam(db, exam_id)
    except DBAPIError as ex:
        msg = _db_error(ex)
        raise HTTPException(502 if "LMS" in msg else 409, msg)
    out = {"sync": sync}
    if analyze:
        out["analysis"] = results.analyze_exam(db, exam_id)
    return out


@router.post("/exams/{exam_id}/paper-import")
async def paper_import(exam_id: int, file: UploadFile = File(...), analyze: bool = True,
                       u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    if e.exam_type != "paper":
        raise HTTPException(422, "Chỉ bài thi giấy mới nhập phiếu trả lời")
    try:
        res = paper.import_answer_sheets(db, e, file.filename or "", await file.read())
    except ValueError as ex:
        raise HTTPException(422, str(ex))
    out = {"import": res}
    if analyze and res["imported"]:
        out["analysis"] = results.analyze_exam(db, exam_id)
    return out


@router.post("/exams/{exam_id}/analyze")
def analyze(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    get_exam_for(db, u, exam_id)
    if not db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e"), {"e": exam_id}).scalar():
        raise HTTPException(409, "Chưa có dữ liệu bài làm – hãy đồng bộ Moodle hoặc nhập phiếu trả lời trước")
    return results.analyze_exam(db, exam_id)


@router.get("/exams/{exam_id}/sync-runs")
def sync_runs(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    get_exam_for(db, u, exam_id)
    return [dict(r) for r in db.execute(text("SELECT * FROM sync_runs WHERE exam_id=:e ORDER BY id DESC"), {"e": exam_id}).mappings()]


@router.get("/system/moodle-status")
def moodle_status(_=Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    avail = moodle.moodle_available()
    bridge = bool(db.execute(text("SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema=DATABASE() AND routine_name='sp_sync_exam'")).scalar())
    return {"moodle_db": moodle.settings.moodle_db_name, "moodle_available": avail, "bridge_installed": bridge}


@router.post("/system/install-bridge")
def install_bridge(_=Depends(require("admin"))):
    try:
        return {"statements": moodle.install_bridge()}
    except RuntimeError as ex:
        raise HTTPException(409, str(ex))
