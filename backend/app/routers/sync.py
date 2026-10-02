"""UC-03: Đồng bộ kết quả từ Moodle (bài online: Quiz; bài giấy: Offline Quiz đã chấm) và phân tích dữ liệu."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_exam_for, require
from ..models import User
from ..services import lms, moodle, results

router = APIRouter(prefix="/api", tags=["UC-03 Đồng bộ & phân tích"])


def _db_error(ex: DBAPIError) -> str:
    orig = getattr(ex, "orig", None)
    return orig.args[1] if orig is not None and len(getattr(orig, "args", ())) > 1 else str(ex)


@router.post("/exams/{exam_id}/sync")
def sync_moodle(exam_id: int, analyze: bool = True, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    e = get_exam_for(db, u, exam_id)
    out = {}
    if e.exam_type == "online" and not e.moodle_quiz_id:
        raise HTTPException(422, "Bài KT chưa được liên kết với Moodle Quiz (moodle_quiz_id)")
    if e.exam_type == "paper":
        if not e.moodle_offlinequiz_id:
            raise HTTPException(422, "Bài thi giấy chưa tạo Offline Quiz trên Moodle – hãy tạo đề thi giấy trên Moodle trước")
        if not moodle.offlinequiz_available():
            raise HTTPException(502, "Moodle chưa cài plugin Offline Quiz (chạy lại 3_CAI_GIAO_DIEN_MOODLE.bat)")
        # Phiếu đã tải lên Moodle nhưng chưa được chấm (Moodle chưa chạy cron) -> nhờ Moodle chấm ngay trước khi kéo về.
        if lms.configured():
            try:
                scans = lms.process_scans(e)
                out["scans"] = {k: scans[k] for k in ("results", "pending", "errorpages", "processedjobs", "correcturl")}
            except lms.MoodleWSError as ex:
                out["scans_error"] = str(ex)
            if out.get("scans") and not out["scans"]["results"]:
                raise HTTPException(409, "Moodle chưa chấm phiếu nào – hãy tải ảnh phiếu đã quét lên Moodle"
                                         + (f" ({out['scans']['errorpages']} phiếu cần sửa trên Moodle)" if out["scans"]["errorpages"] else ""))
    if e.exam_type == "online":
        gm = db.execute(text(f"SELECT grademethod FROM `{moodle.settings.moodle_db_name}`.`{moodle.settings.moodle_prefix}quiz` WHERE id=:q"),
                        {"q": e.moodle_quiz_id}).scalar()
        if gm == 2:
            out["warnings"] = ["Quiz đang tính điểm TRUNG BÌNH các lượt: hệ thống phân tích lượt cuối của mỗi SV, "
                               "điểm có thể khác sổ điểm Moodle – nên đặt Quiz 1 lượt hoặc cách tính khác"]
    try:
        out["sync"] = moodle.sync_exam(db, exam_id)
    except DBAPIError as ex:
        msg = _db_error(ex)
        raise HTTPException(502 if "LMS" in msg else 409, msg)
    if out["sync"]["n_attempts"]:
        missing = db.execute(text("""SELECT COUNT(*) FROM exam_questions eq WHERE eq.exam_id=:e AND NOT EXISTS (
                                       SELECT 1 FROM item_level_results r JOIN exam_attempts a ON a.id=r.attempt_id
                                       WHERE a.exam_id=:e AND a.status='finished' AND r.question_id=eq.question_id)"""),
                             {"e": exam_id}).scalar()
        if missing:
            out.setdefault("warnings", []).append(
                f"{missing} câu của đề không có trong bài làm trên Moodle (chưa đưa vào Quiz/Offline Quiz?) – "
                "các câu này không được tính khi đo CLO")
    if analyze and out["sync"]["n_attempts"]:
        out["analysis"] = results.analyze_exam(db, exam_id)
    else:
        if analyze:
            out["analysis_skipped"] = "Moodle chưa có bài nào được chấm – chưa phân tích"
        # bài KT trở về trạng thái "Đã đồng bộ": loại khỏi tổng hợp CLO–PI–PLO cho tới khi phân tích lại
        results.recompute_class_section(db, e.class_section_id)
    return out


@router.post("/exams/{exam_id}/analyze")
def analyze(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    get_exam_for(db, u, exam_id)
    if not db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e"), {"e": exam_id}).scalar():
        raise HTTPException(409, "Chưa có dữ liệu bài làm – hãy đồng bộ kết quả từ Moodle trước")
    return results.analyze_exam(db, exam_id)


@router.get("/exams/{exam_id}/sync-runs")
def sync_runs(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    get_exam_for(db, u, exam_id)
    return [dict(r) for r in db.execute(text("SELECT * FROM sync_runs WHERE exam_id=:e ORDER BY id DESC"), {"e": exam_id}).mappings()]


@router.get("/system/moodle-status")
def moodle_status(_=Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    avail = moodle.moodle_available()
    bridge = bool(db.execute(text("SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema=DATABASE() AND routine_name='sp_sync_exam'")).scalar())
    return {"moodle_db": moodle.settings.moodle_db_name, "moodle_available": avail, "bridge_installed": bridge,
            "offlinequiz_available": avail and moodle.offlinequiz_available()}


@router.post("/system/install-bridge")
def install_bridge(_=Depends(require("admin"))):
    try:
        return {"statements": moodle.install_bridge()}
    except RuntimeError as ex:
        raise HTTPException(409, str(ex))
