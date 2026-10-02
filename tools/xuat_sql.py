"""Xuất toàn bộ CSDL assessment_db (cấu trúc + dữ liệu + view + thủ tục) thành tệp .sql nhập được bằng HeidiSQL,
kèm cấu trúc + dữ liệu 2 bảng của plugin Moodle local_clo.

Chạy từ thư mục backend:  python ../tools/xuat_sql.py "D:\\3. TLCN\\NopBai\\SQL"
"""
import datetime as dt
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import engine  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "sql_export"); OUT.mkdir(parents=True, exist_ok=True)
MDB, PRE = settings.moodle_db_name, settings.moodle_prefix


def lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float, Decimal)):
        return str(v)
    if isinstance(v, (dt.datetime, dt.date, dt.time, dt.timedelta)):
        return "'" + str(v) + "'"
    if isinstance(v, (bytes, bytearray)):
        return "0x" + v.hex() if v else "''"
    s = str(v).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r").replace("\x00", "\\0")
    return "'" + s + "'"


def dump_table(c, schema, t, out, data=True):
    ddl = c.execute(text(f"SHOW CREATE TABLE `{schema}`.`{t}`")).fetchone()[1]
    out.append(f"-- ----------------------------------------------------------------\n-- Bảng {t}\nDROP TABLE IF EXISTS `{t}`;\n{ddl};\n")
    if not data:
        return 0
    cols = [r[0] for r in c.execute(text("""SELECT column_name FROM information_schema.columns WHERE table_schema=:s AND table_name=:t
                                              AND extra NOT LIKE '%GENERATED%' ORDER BY ordinal_position"""), {"s": schema, "t": t})]
    rows = c.execute(text(f"SELECT {', '.join('`'+x+'`' for x in cols)} FROM `{schema}`.`{t}`")).fetchall()
    head = f"INSERT INTO `{t}` ({', '.join('`'+x+'`' for x in cols)}) VALUES\n"
    for i in range(0, len(rows), 200):
        out.append(head + ",\n".join("(" + ", ".join(lit(v) for v in r) + ")" for r in rows[i:i + 200]) + ";")
    out.append("")
    return len(rows)


def main():
    stamp = dt.datetime.now().strftime("%d/%m/%Y %H:%M")
    with engine.connect() as c:
        db = c.execute(text("SELECT DATABASE()")).scalar()
        ver = c.execute(text("SELECT VERSION()")).scalar()
        out = [f"-- =====================================================================",
               f"-- Bản xuất đầy đủ CSDL {db} (cấu trúc + dữ liệu + view + thủ tục) – {stamp}",
               f"-- Máy chủ: {ver}. Tiểu luận chuyên ngành – Nhóm 01.",
               f"-- Nhập bằng HeidiSQL: File > Run SQL file... (hoặc mở tệp rồi nhấn F9).",
               f"-- Cầu nối đọc CSDL Moodle `{MDB}` (tiền tố {PRE}); nếu tên CSDL Moodle khác, đổi `{MDB}.` trong phần VIEW.",
               f"-- =====================================================================",
               "SET NAMES utf8mb4;", "SET @OLD_FK = @@FOREIGN_KEY_CHECKS, @OLD_SQL_MODE = @@SQL_MODE;",
               "SET FOREIGN_KEY_CHECKS = 0;", "SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';",
               f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;", f"USE `{db}`;", ""]
        tables = [r[0] for r in c.execute(text("SHOW FULL TABLES WHERE Table_type='BASE TABLE'"))]
        views = [r[0] for r in c.execute(text("SHOW FULL TABLES WHERE Table_type='VIEW'"))]
        nrows = {t: dump_table(c, db, t, out) for t in tables}
        # view theo thứ tự phụ thuộc
        defs = {}
        for v in views:
            d = c.execute(text(f"SHOW CREATE VIEW `{v}`")).fetchone()[1]
            d = re.sub(r"DEFINER=`[^`]*`@`[^`]*`\s*", "", d).replace(f"`{db}`.", "")
            defs[v] = d
        order, left = [], set(views)
        while left:
            ready = [v for v in sorted(left) if not any(re.search(rf"`{o}`", defs[v]) for o in left if o != v)]
            if not ready:
                ready = sorted(left)
            for v in ready:
                order.append(v); left.discard(v)
        out.append("-- ---------------------------------------------------------------- VIEW")
        for v in order:
            out.append(f"DROP VIEW IF EXISTS `{v}`;\n{defs[v]};\n")
        procs = [r[1] for r in c.execute(text("SHOW PROCEDURE STATUS WHERE Db = DATABASE()"))]
        out.append("-- ---------------------------------------------------------------- THỦ TỤC")
        for p in procs:
            d = c.execute(text(f"SHOW CREATE PROCEDURE `{p}`")).fetchone()[2]
            d = re.sub(r"DEFINER=`[^`]*`@`[^`]*`\s*", "", d)
            out.append(f"DROP PROCEDURE IF EXISTS `{p}`;\nDELIMITER $$\n{d}$$\nDELIMITER ;\n")
        out.append("SET FOREIGN_KEY_CHECKS = @OLD_FK, SQL_MODE = @OLD_SQL_MODE;\n")
        f1 = OUT / f"05_ban_xuat_day_du_{db}.sql"
        f1.write_text("\n".join(out), encoding="utf-8")

        # plugin Moodle local_clo
        out2 = [f"-- Hai bảng của plugin Moodle local_clo trong CSDL `{MDB}` (do Moodle tạo khi cài plugin; hệ thống ghi qua Web Service)",
                f"-- Xuất lúc {stamp}.", "SET NAMES utf8mb4;", f"USE `{MDB}`;", ""]
        nplug = {}
        for t in ("local_clo_exam", "local_clo_result"):
            try:
                nplug[t] = dump_table(c, MDB, PRE + t, out2)
            except Exception as ex:  # plugin chưa cài
                out2.append(f"-- (chưa có bảng {PRE}{t}: {ex.__class__.__name__})")
        f2 = OUT / "06_moodle_plugin_local_clo.sql"
        f2.write_text("\n".join(out2) + "\n", encoding="utf-8")
    print(f"Đã xuất {f1}")
    print(f"  {len(tables)} bảng, {sum(nrows.values())} dòng dữ liệu, {len(views)} view, {len(procs)} thủ tục")
    print(f"Đã xuất {f2}: {nplug}")


if __name__ == "__main__":
    main()
