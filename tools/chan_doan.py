"""Chẩn đoán nhanh: kết nối CSDL, số bảng, dữ liệu demo, cổng 8000. In ra stdout (bat ghi vào logs\\chan_doan.log)."""
import os, sys, socket, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend")); os.chdir(ROOT / "backend")
print("python", sys.version.split()[0], flush=True)
s = socket.socket(); s.settimeout(2)
for port, name in ((3306, "MySQL"), (8000, "He thong"), (80, "Apache/Moodle")):
    try:
        socket.create_connection(("127.0.0.1", port), 2).close(); print(f"cong {port} ({name}): MO", flush=True)
    except Exception as e:
        print(f"cong {port} ({name}): DONG ({e})", flush=True)
try:
    from sqlalchemy import text
    from app.database import engine
    with engine.connect() as c:
        print("CSDL:", c.execute(text("SELECT DATABASE()")).scalar(), flush=True)
        n = c.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_type='BASE TABLE'")).scalar()
        print("so bang:", n, flush=True)
        for t in ("users", "courses", "exams"):
            try:
                print(f"  {t}:", c.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar(), flush=True)
            except Exception as e:
                print(f"  {t}: LOI {str(e)[:120]}", flush=True)
        for r in c.execute(text("SELECT e.id,e.exam_title,e.status,e.class_section_id,cs.section_code,cs.moodle_course_id,e.moodle_quiz_id,e.exam_type FROM exams e JOIN class_sections cs ON cs.id=e.class_section_id")):
            print("  exam", tuple(r), flush=True)
        print("  attempts:", c.execute(text("SELECT exam_id,COUNT(*) FROM exam_attempts GROUP BY exam_id")).all(), flush=True)
except Exception as e:
    print("LOI CSDL:", str(e)[:400], flush=True)
try:
    print("health:", urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=5).read()[:200], flush=True)
except Exception as e:
    print("health LOI:", e, flush=True)
