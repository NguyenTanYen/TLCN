"""Cấu hình ứng dụng, đọc từ biến môi trường (hoặc tệp .env)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("cau_hinh.env", ".env"), env_file_encoding="utf-8", extra="ignore")

    database_url: str = "mysql+pymysql://root:@127.0.0.1:3306/assessment_db?charset=utf8mb4"
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


settings = Settings()
