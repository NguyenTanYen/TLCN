"""Giao tiếp với Moodle qua Web Service (plugin local_clo) – chiều GHI của tích hợp.

- Tạo Quiz từ đề đã soạn (UC-02, thay cho bước import XML thủ công): local_clo_create_quiz.
- Bài thi giấy: tạo Offline Quiz (Moodle sinh đề in, phiếu trả lời, nhận diện phiếu quét và chấm):
  local_clo_create_offlinequiz / local_clo_get_offlinequiz / local_clo_process_scans; tải tệp đề/phiếu qua webservice/pluginfile.
- Đẩy kết quả phân tích từng SV + trạng thái công bố về Moodle để SV xem (UC-05): local_clo_push_results.
Chiều ĐỌC (bài làm của SV) vẫn dùng cầu nối CSDL chỉ đọc + sp_sync_exam như thiết kế (mục V báo cáo).
"""
from __future__ import annotations

import json
from datetime import datetime
from urllib.parse import urlencode

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Exam
from . import xml_export


class MoodleWSError(RuntimeError):
    """Lỗi khi gọi Web Service của Moodle (mất kết nối, token sai, Moodle báo lỗi...)."""


def configured() -> bool:
    return bool(settings.moodle_url and settings.moodle_ws_token)


def _flatten(prefix: str, value, out: list[tuple[str, str]]) -> None:
    """Chuyển tham số lồng nhau sang dạng form của REST Moodle: results[0][username]=..."""
    if isinstance(value, dict):
        for k, v in value.items():
            _flatten(f"{prefix}[{k}]" if prefix else k, v, out)
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            _flatten(f"{prefix}[{i}]", v, out)
    elif isinstance(value, bool):
        out.append((prefix, "1" if value else "0"))
    elif value is not None:
        out.append((prefix, str(value)))


def call(function: str, params: dict | None = None, timeout: float = 60) -> dict:
    if not configured():
        raise MoodleWSError("Chưa cấu hình kết nối Moodle (MOODLE_URL, MOODLE_WS_TOKEN trong cau_hinh.env)")
    form: list[tuple[str, str]] = []
    _flatten("", params or {}, form)
    url = settings.moodle_url.rstrip("/") + "/webservice/rest/server.php"
    query = {"wstoken": settings.moodle_ws_token, "wsfunction": function, "moodlewsrestformat": "json"}
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:   # Moodle nội bộ: không đi qua proxy hệ thống
            r = client.post(url, params=query, content=urlencode(form).encode(),
                            headers={"Content-Type": "application/x-www-form-urlencoded"})
    except httpx.HTTPError as ex:
        raise MoodleWSError(f"Lỗi kết nối LMS: {ex}") from ex
    try:
        data = r.json()
    except ValueError:
        raise MoodleWSError(f"Lỗi kết nối LMS: Moodle trả về HTTP {r.status_code} không phải JSON")
    if isinstance(data, dict) and data.get("exception"):
        msg = data.get("message") or data.get("errorcode")
        if data.get("debuginfo"):
            msg += f" ({data['debuginfo']})"
        raise MoodleWSError(f"Moodle báo lỗi: {msg}")
    return data


def site_info() -> dict:
    return call("core_webservice_get_site_info")


# ------------------------------------------------------------------ tạo Quiz (UC-02)
def create_quiz(db: Session, exam: Exam, moodle_course_id: int) -> dict:
    xml = xml_export.exam_to_moodle_xml(exam)
    res = call("local_clo_create_quiz", {
        "courseid": moodle_course_id, "examref": exam.id, "name": exam.exam_title, "questionsxml": xml,
        "grade": float(exam.max_score), "timelimit": int(exam.duration_minutes or 0) * 60,
    }, timeout=180)
    return res


# ------------------------------------------------------------------ bài thi giấy: Offline Quiz
def create_offlinequiz(exam: Exam, moodle_course_id: int, numgroups: int = 2, shuffle_questions: bool = True,
                       shuffle_answers: bool = True, docx: bool = False, intro: str = "") -> dict:
    xml = xml_export.exam_to_moodle_xml(exam)
    examdate = int(datetime.combine(exam.exam_date, datetime.min.time()).timestamp()) if exam.exam_date else 0
    return call("local_clo_create_offlinequiz", {
        "courseid": moodle_course_id, "examref": exam.id, "name": exam.exam_title, "questionsxml": xml,
        "grade": float(exam.max_score), "numgroups": numgroups, "shufflequestions": shuffle_questions,
        "shuffleanswers": shuffle_answers, "examdate": examdate, "fileformat": 1 if docx else 0, "pdfintro": intro,
    }, timeout=300)


def get_offlinequiz(exam: Exam) -> dict:
    return call("local_clo_get_offlinequiz", {"examref": exam.id})


def process_scans(exam: Exam) -> dict:
    """Moodle nhận diện & chấm ngay các phiếu đã tải lên đang chờ (không phải đợi cron của Moodle)."""
    return call("local_clo_process_scans", {"examref": exam.id}, timeout=600)


def download(url: str) -> tuple[bytes, str]:
    """Tải tệp Moodle qua webservice/pluginfile.php bằng token (chỉ nhận URL thuộc Moodle đã cấu hình)."""
    base = settings.moodle_url.rstrip("/") + "/webservice/pluginfile.php/"
    if not url.startswith(base):
        raise MoodleWSError("Đường dẫn tệp không thuộc Moodle đã cấu hình")
    try:
        with httpx.Client(timeout=120, trust_env=False) as client:
            r = client.get(url, params={"token": settings.moodle_ws_token})
    except httpx.HTTPError as ex:
        raise MoodleWSError(f"Lỗi kết nối LMS: {ex}") from ex
    ctype = r.headers.get("content-type", "application/octet-stream")
    if r.status_code != 200 or "json" in ctype:
        raise MoodleWSError(f"Moodle không trả tệp (HTTP {r.status_code}): {r.text[:200]}")
    return r.content, ctype


# ------------------------------------------------------------------ kết quả từng SV (UC-05)
def student_results(db: Session, exam_id: int) -> list[dict]:
    """Kết quả phân tích của từng SV trong bài KT – dữ liệu SV sẽ xem trên Moodle."""
    e = db.execute(text("""SELECT e.id, e.max_score, e.class_section_id, cs.course_id,
                                  (SELECT SUM(points) FROM exam_questions WHERE exam_id=e.id) AS raw_max
                           FROM exams e JOIN class_sections cs ON cs.id=e.class_section_id WHERE e.id=:e"""),
                   {"e": exam_id}).mappings().first()
    if not e:
        return []
    raw_max = float(e["raw_max"] or 1)
    clo_desc = {r[0]: r[1] for r in db.execute(text("SELECT clo_code, description FROM clos WHERE course_id=:c"),
                                                 {"c": e["course_id"]})}
    class_avg = {r[0]: float(r[1]) for r in db.execute(text("""
        SELECT c.clo_code, ROUND(AVG(r.score_pct), 2) FROM attempt_clo_results r
        JOIN exam_attempts a ON a.id=r.attempt_id JOIN clos c ON c.id=r.clo_id
        WHERE a.exam_id=:e AND a.status='finished' GROUP BY c.clo_code"""), {"e": exam_id})}
    radar: dict[int, list] = {}
    for r in db.execute(text("""SELECT attempt_id, clo_code, score_pct, is_achieved, pass_threshold_pct
                                FROM v_student_clo_radar WHERE exam_id=:e ORDER BY clo_code"""), {"e": exam_id}).mappings():
        radar.setdefault(r["attempt_id"], []).append({
            "code": r["clo_code"], "description": clo_desc.get(r["clo_code"], ""), "pct": float(r["score_pct"]),
            "threshold": float(r["pass_threshold_pct"]), "class_avg": class_avg.get(r["clo_code"]),
            "achieved": bool(r["is_achieved"])})
    paths = {r["attempt_id"]: r for r in db.execute(text("""
        SELECT p.id, p.attempt_id, p.diagnostic_summary, p.recommended_study_plan FROM personalized_learning_paths p
        JOIN exam_attempts a ON a.id=p.attempt_id WHERE a.exam_id=:e"""), {"e": exam_id}).mappings()}
    items: dict[int, list] = {}
    for r in db.execute(text("""
        SELECT p.attempt_id, i.priority, c.clo_code, c.description, i.gap_pct, o.chapter_number, o.chapter_name
        FROM learning_path_items i JOIN personalized_learning_paths p ON p.id=i.path_id
        JOIN exam_attempts a ON a.id=p.attempt_id JOIN clos c ON c.id=i.clo_id
        LEFT JOIN course_outlines o ON o.id=i.outline_id
        WHERE a.exam_id=:e ORDER BY i.priority, o.chapter_number"""), {"e": exam_id}).mappings():
        chap = f"Chương {r['chapter_number']}. {r['chapter_name']}" if r["chapter_number"] else None
        items.setdefault(r["attempt_id"], []).append({"priority": r["priority"], "clo": r["clo_code"],
                                                      "clo_description": r["description"], "chapter": chap,
                                                      "gap": float(r["gap_pct"])})
    out = []
    for a in db.execute(text("""SELECT a.id, a.status, a.total_score, s.student_code, s.full_name, s.moodle_user_id
                                FROM exam_attempts a JOIN students s ON s.id=a.student_id
                                WHERE a.exam_id=:e ORDER BY s.student_code"""), {"e": exam_id}).mappings():
        absent = a["status"] == "absent"
        p = paths.get(a["id"])
        data = {} if absent else {"clos": radar.get(a["id"], []), "summary": p["diagnostic_summary"] if p else None,
                                  "study_plan": p["recommended_study_plan"] if p else None, "items": items.get(a["id"], [])}
        out.append({"student_code": a["student_code"], "full_name": a["full_name"], "moodle_user_id": a["moodle_user_id"],
                    "status": "absent" if absent else "finished",
                    "score": None if absent else round(float(a["total_score"]) * float(e["max_score"]) / raw_max, 2),
                    "max_score": float(e["max_score"]), "data": data})
    return out


def push_results(db: Session, exam: Exam) -> dict:
    cs = exam.class_section
    if not cs.moodle_course_id:
        raise MoodleWSError("Lớp học phần chưa gắn với khóa học Moodle (moodle_course_id)")
    rows = student_results(db, exam.id)
    payload = [{"userid": r["moodle_user_id"] or 0, "username": r["student_code"], "status": r["status"],
                "score": r["score"], "maxscore": r["max_score"],
                "data": json.dumps(r["data"], ensure_ascii=False)} for r in rows]
    res = call("local_clo_push_results", {"examref": exam.id, "courseid": cs.moodle_course_id,
                                          "quizid": exam.moodle_quiz_id or 0, "title": exam.exam_title,
                                          "published": bool(exam.publish_flag), "results": payload}, timeout=120)
    res["sent"] = len(payload)
    return res
