"""Cầu nối CSDL Moodle: cài đặt view/thủ tục (database/02_moodle_bridge.sql) và gọi đồng bộ."""
from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..database import engine

BRIDGE_SQL = Path(__file__).resolve().parents[3] / "database" / "02_moodle_bridge.sql"


OQ_BLOCK = re.compile(r"^-- >>> offlinequiz\n.*?^-- <<< offlinequiz\n", re.S | re.M)


def render_bridge_sql(with_offlinequiz: bool = True, db_name: str | None = None, prefix: str | None = None) -> str:
    """Thay tên CSDL/tiền tố Moodle; bỏ phần đọc bài thi giấy nếu Moodle chưa cài plugin Offline Quiz."""
    sql = BRIDGE_SQL.read_text(encoding="utf-8")
    if not with_offlinequiz:
        sql = OQ_BLOCK.sub("", sql)
    return sql.replace("moodle.mdl_", f"`{db_name or settings.moodle_db_name}`.{prefix or settings.moodle_prefix}")


def split_statements(sql: str) -> list[str]:
    """Tách script có DELIMITER $$ thành các câu lệnh riêng."""
    stmts, delim, buf = [], ";", []
    for line in sql.splitlines():
        s = line.strip()
        if s.upper().startswith("DELIMITER"):
            delim = s.split()[1]
            continue
        if s.startswith("--") and not buf:
            continue
        buf.append(line)
        if s.endswith(delim):
            stmt = "\n".join(buf).rstrip()
            stmts.append(stmt[: -len(delim)].strip())
            buf = []
    if "".join(buf).strip():
        stmts.append("\n".join(buf))
    return [s for s in stmts if s and not re.fullmatch(r"USE\s+\w+", s)]


def _has_table(name: str) -> bool:
    with engine.connect() as c:
        n = c.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=:s AND table_name=:t"),
                      {"s": settings.moodle_db_name, "t": f"{settings.moodle_prefix}{name}"}).scalar()
    return bool(n)


def moodle_available() -> bool:
    return _has_table("quiz_attempts")


def offlinequiz_available() -> bool:
    """Moodle đã cài plugin Offline Quiz (mod_offlinequiz) – nơi chấm bài thi giấy."""
    return _has_table("offlinequiz_results")


def install_bridge() -> int:
    if not moodle_available():
        raise RuntimeError(f"Không tìm thấy CSDL Moodle '{settings.moodle_db_name}' (bảng {settings.moodle_prefix}quiz_attempts)")
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        stmts = split_statements(render_bridge_sql(offlinequiz_available()))
        for s in stmts:
            cur.execute(s)
        raw.commit()
        return len(stmts)
    finally:
        raw.close()


def sync_exam(db: Session, exam_id: int) -> dict:
    """Gọi thủ tục trên kết nối AUTOCOMMIT để nhật ký sync_runs được giữ lại cả khi thủ tục ROLLBACK.
    Phiên `db` được kết thúc giao dịch trước/sau khi gọi để không đọc ảnh chụp cũ (REPEATABLE READ)."""
    db.commit()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("CALL sp_sync_exam(:e)"), {"e": exam_id})
    db.commit()
    db.expire_all()
    r = db.execute(text("SELECT status, n_attempts, n_absent FROM sync_runs WHERE exam_id=:e AND kind='moodle' ORDER BY id DESC LIMIT 1"),
                   {"e": exam_id}).one()
    return {"status": r.status, "n_attempts": r.n_attempts, "n_absent": r.n_absent}


# ------------------------------------------------------------------ kiểm tra quyền trên khóa học / hoạt động Moodle (chỉ đọc)
def _t(name: str) -> str:
    return f"`{settings.moodle_db_name}`.`{settings.moodle_prefix}{name}`"


def course_exists(db: Session, course_id: int) -> bool:
    return bool(db.execute(text(f"SELECT 1 FROM {_t('course')} WHERE id=:c AND id<>1"), {"c": course_id}).scalar())


def activity_course(db: Session, kind: str, instance_id: int) -> int | None:
    """Khóa học Moodle chứa Quiz (kind='quiz') hoặc Offline Quiz (kind='offlinequiz')."""
    if kind == "offlinequiz" and not offlinequiz_available():
        return None
    return db.execute(text(f"SELECT course FROM {_t(kind)} WHERE id=:i"), {"i": instance_id}).scalar()


def is_course_teacher(db: Session, username: str, course_id: int) -> bool:
    """Người dùng Moodle cùng tên đăng nhập có vai trò giảng viên/quản lý trong khóa học (hoặc toàn hệ thống)."""
    return bool(db.execute(text(f"""
        SELECT 1 FROM {_t('role_assignments')} ra
        JOIN {_t('user')} u ON u.id = ra.userid AND u.username = :u AND u.deleted = 0
        JOIN {_t('role')} r ON r.id = ra.roleid AND r.shortname IN ('editingteacher', 'teacher', 'manager')
        JOIN {_t('context')} cx ON cx.id = ra.contextid
        WHERE (cx.contextlevel = 50 AND cx.instanceid = :c) OR cx.contextlevel = 10
        LIMIT 1"""), {"u": username, "c": course_id}).scalar())


TEACHER_ROLES = "('editingteacher', 'teacher')"


def teacher_courses(db: Session, username: str | None) -> list[dict]:
    """Khóa học Moodle mà `username` là giảng viên (vai trò Teacher/Non-editing teacher trong khóa học);
    username=None (Bộ môn): mọi khóa học. Kèm danh sách GV và số SV đang ghi danh."""
    where, params = "c.id <> 1", {}
    if username is not None:
        where += f""" AND EXISTS (SELECT 1 FROM {_t('role_assignments')} ra JOIN {_t('user')} u ON u.id = ra.userid AND u.deleted = 0
                      JOIN {_t('role')} r ON r.id = ra.roleid AND r.shortname IN {TEACHER_ROLES}
                      WHERE ra.contextid = cx.id AND u.username = :u)"""
        params["u"] = username
    cat = _has_table("course_categories")
    rows = db.execute(text(f"""
        SELECT c.id, c.shortname, c.fullname, c.idnumber, c.startdate, c.visible, {'cc.name' if cat else 'NULL'} AS category
        FROM {_t('course')} c
        JOIN {_t('context')} cx ON cx.contextlevel = 50 AND cx.instanceid = c.id
        {f"LEFT JOIN {_t('course_categories')} cc ON cc.id = c.category" if cat else ''}
        WHERE {where} ORDER BY c.startdate DESC, c.id DESC"""), params).mappings().all()
    if not rows:
        return []
    ids = ",".join(str(int(r["id"])) for r in rows)
    people = db.execute(text(f"""
        SELECT cx.instanceid AS cid, r.shortname AS role, u.username, u.idnumber,
               TRIM(CONCAT(u.lastname, ' ', u.firstname)) AS name
        FROM {_t('context')} cx
        JOIN {_t('role_assignments')} ra ON ra.contextid = cx.id
        JOIN {_t('role')} r ON r.id = ra.roleid AND r.shortname IN ('editingteacher', 'teacher', 'student')
        JOIN {_t('user')} u ON u.id = ra.userid AND u.deleted = 0
        WHERE cx.contextlevel = 50 AND cx.instanceid IN ({ids})""")).mappings().all()
    out = []
    for r in rows:
        ps = [p for p in people if p["cid"] == r["id"]]
        teachers, seen = [], set()
        for p in ps:
            if p["role"] != "student" and p["username"] not in seen:
                seen.add(p["username"]); teachers.append({"username": p["username"], "idnumber": p["idnumber"] or "", "name": p["name"]})
        out.append({**dict(r), "teachers": teachers,
                    "n_students": len({p["username"] for p in ps if p["role"] == "student"})})
    return out


def course_roster(db: Session, course_id: int) -> list[dict]:
    """SV đang ghi danh (vai trò student) của một khóa học Moodle – cùng quy tắc mã SV với cầu nối (idnumber, nếu trống thì username)."""
    return [dict(r) for r in db.execute(text(f"""
        SELECT DISTINCT u.id AS mdl_user_id, COALESCE(NULLIF(TRIM(u.idnumber), ''), u.username) AS student_code,
               TRIM(CONCAT(u.lastname, ' ', u.firstname)) AS full_name
        FROM {_t('enrol')} en
        JOIN {_t('user_enrolments')} ue ON ue.enrolid = en.id AND ue.status = 0
        JOIN {_t('user')} u ON u.id = ue.userid AND u.deleted = 0
        JOIN {_t('context')} cx ON cx.contextlevel = 50 AND cx.instanceid = en.courseid
        JOIN {_t('role_assignments')} ra ON ra.contextid = cx.id AND ra.userid = u.id
        JOIN {_t('role')} r ON r.id = ra.roleid AND r.shortname = 'student'
        WHERE en.courseid = :c AND en.status = 0"""), {"c": course_id}).mappings()]
