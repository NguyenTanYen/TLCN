"""Cấu hình ứng dụng, đọc từ biến môi trường (hoặc tệp .env)."""
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("cau_hinh.env", ".env"), env_file_encoding="utf-8", extra="ignore")

    database_url: str = "mysql+pymysql://root:@127.0.0.1:3306/assessment_db?charset=utf8mb4"
    database_admin_url: str = ""        # tài khoản quản trị CSDL (tools/tao_tai_khoan_csdl.py ghi lại) – chỉ dùng cho kịch bản dữ liệu minh họa
    moodle_db_name: str = "moodle"      # schema CSDL Moodle trên cùng MySQL server
    moodle_prefix: str = "mdl_"         # tiền tố bảng Moodle
    jwt_secret: str = "doi-khoa-bi-mat-nay-khi-trien-khai-that-2025"
    jwt_expire_minutes: int = 8 * 60
    default_pass_threshold: float = 60.0   # % điểm tối đa để SV đạt CLO (BM6c)
    default_clo_target: float = 70.0       # % SV đạt để CLO đạt
    frontend_dist: str = "../frontend/dist"
    # Kết nối hai chiều với Moodle (ghi bằng Web Service chính thức; đọc bài làm vẫn qua cầu nối CSDL chỉ đọc)
    moodle_url: str = ""                # ví dụ http://localhost/moodle
    moodle_ws_token: str = ""           # token dịch vụ "local_clo" (tạo bởi local/clo/cli/setup.php)
    moodle_sso_secret: str = ""         # khóa dùng chung để kiểm tra vé đăng nhập một lần từ nút "Phân tích CĐR"
    demo_mode: bool = False             # True: trang đăng nhập hiện nút điền nhanh tài khoản minh họa (bước 4 tự bật)


settings = Settings()

# Khóa ký JWT: nếu chưa đặt JWT_SECRET riêng (hoặc còn giá trị mẫu), tự sinh khóa ngẫu nhiên 256 bit một lần
# và lưu ở backend/.jwt_secret (không nằm trong bộ mã nguồn phát hành) – tránh dùng khóa mặc định công khai.
_KEY_FILE = Path(__file__).resolve().parents[1] / ".jwt_secret"
if "doi-khoa-bi-mat" in settings.jwt_secret or len(settings.jwt_secret) < 32:
    if _KEY_FILE.exists() and len(_KEY_FILE.read_text().strip()) >= 32:
        settings.jwt_secret = _KEY_FILE.read_text().strip()
    else:
        settings.jwt_secret = secrets.token_hex(32)
        try:
            _KEY_FILE.write_text(settings.jwt_secret)
        except OSError:
            pass
