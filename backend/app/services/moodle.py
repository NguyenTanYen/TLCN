"""Cầu nối CSDL Moodle: cài đặt view/thủ tục (database/02_moodle_bridge.sql) và gọi đồng bộ."""
from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..database import engine

BRIDGE_SQL = Path(__file__).resolve().parents[3] / "database" / "02_moodle_bridge.sql"


def render_bridge_sql() -> str:
    sql = BRIDGE_SQL.read_text(encoding="utf-8")
    return sql.replace("moodle.mdl_", f"`{settings.moodle_db_name}`.{settings.moodle_prefix}")


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


def moodle_available() -> bool:
    with engine.connect() as c:
        n = c.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=:s AND table_name=:t"),
                      {"s": settings.moodle_db_name, "t": f"{settings.moodle_prefix}quiz_attempts"}).scalar()
    return bool(n)


def install_bridge() -> int:
    if not moodle_available():
        raise RuntimeError(f"Không tìm thấy CSDL Moodle '{settings.moodle_db_name}' (bảng {settings.moodle_prefix}quiz_attempts)")
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        stmts = split_statements(render_bridge_sql())
        for s in stmts:
            cur.execute(s)
        raw.commit()
        return len(stmts)
    finally:
        raw.close()


def sync_exam(db: Session, exam_id: int) -> dict:
    """Gọi thủ tục trên kết nối AUTOCOMMIT để nhật ký sync_runs được giữ lại cả khi thủ tục ROLLBACK."""
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("CALL sp_sync_exam(:e)"), {"e": exam_id})
    db.expire_all()
    r = db.execute(text("SELECT status, n_attempts, n_absent FROM sync_runs WHERE exam_id=:e AND kind='moodle' ORDER BY id DESC LIMIT 1"),
                   {"e": exam_id}).one()
    return {"status": r.status, "n_attempts": r.n_attempts, "n_absent": r.n_absent}
