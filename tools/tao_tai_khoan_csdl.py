"""Tạo tài khoản MySQL/MariaDB đặc quyền tối thiểu cho hệ thống phân tích CĐR và chuyển cấu hình sang tài khoản đó.

  clo_app: toàn quyền trên CSDL của hệ thống (assessment_db) + CHỈ SELECT trên CSDL Moodle.
Chạy một lần (3_CAI_GIAO_DIEN_MOODLE.bat gọi tự động) bằng tài khoản quản trị đang ghi trong backend/cau_hinh.env;
mật khẩu sinh ngẫu nhiên và được ghi lại vào DATABASE_URL. Chạy lại an toàn (đổi mật khẩu mới).
  python tools/tao_tai_khoan_csdl.py [đường_dẫn_cau_hinh.env]
"""
import re
import secrets
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ENV = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "backend" / "cau_hinh.env"
APP_USER = "clo_app"

body = ENV.read_text(encoding="utf-8")
vals = dict(re.findall(r"^(\w+)=(.*)$", body, flags=re.M))
url = make_url(vals["DATABASE_URL"].strip())
mdb = vals.get("MOODLE_DB_NAME", "moodle").strip()
if url.username == APP_USER:
    admin_url = vals.get("DATABASE_ADMIN_URL")
    if not admin_url:
        print("Cấu hình đã dùng tài khoản", APP_USER, "– không cần làm gì.")
        sys.exit(0)
    url_admin = make_url(admin_url.strip())
else:
    url_admin = url
pw = secrets.token_urlsafe(18)
eng = create_engine(url_admin.set(database=None))
with eng.begin() as c:
    for host in ("localhost", "127.0.0.1", "::1"):
        c.execute(text(f"CREATE USER IF NOT EXISTS '{APP_USER}'@'{host}' IDENTIFIED BY :pw"), {"pw": pw})
        c.execute(text(f"ALTER USER '{APP_USER}'@'{host}' IDENTIFIED BY :pw"), {"pw": pw})
        c.execute(text(f"GRANT ALL PRIVILEGES ON `{url.database}`.* TO '{APP_USER}'@'{host}'"))
        c.execute(text(f"GRANT SELECT ON `{mdb}`.* TO '{APP_USER}'@'{host}'"))
    c.execute(text("FLUSH PRIVILEGES"))
new = url.set(username=APP_USER, password=pw).render_as_string(hide_password=False)
lines = []
for line in body.splitlines():
    if line.startswith("DATABASE_URL="):
        lines.append("DATABASE_URL=" + new)
        if url.username != APP_USER:
            lines.append("# Tài khoản quản trị CSDL (chỉ dùng khi khởi tạo lại CSDL / tạo lại tài khoản):")
            lines.append("DATABASE_ADMIN_URL=" + url.render_as_string(hide_password=False))
    else:
        lines.append(line)
ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
# Kiểm tra: tài khoản mới đọc được Moodle nhưng không ghi được
chk = create_engine(new)
with chk.connect() as c:
    c.execute(text(f"SELECT COUNT(*) FROM `{mdb}`.`{vals.get('MOODLE_PREFIX', 'mdl_').strip()}config`")).scalar()
    try:
        c.execute(text(f"UPDATE `{mdb}`.`{vals.get('MOODLE_PREFIX', 'mdl_').strip()}config` SET value=value WHERE 1=0"))
        print("CẢNH BÁO: tài khoản vẫn ghi được CSDL Moodle")
    except Exception:
        print(f"Đã chuyển hệ thống sang tài khoản {APP_USER}: toàn quyền {url.database}, CHỈ ĐỌC {mdb} (đã thử ghi Moodle – bị từ chối).")
