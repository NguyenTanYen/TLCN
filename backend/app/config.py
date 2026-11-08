"""Cấu hình ứng dụng, đọc từ biến môi trường (hoặc tệp .env)."""
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("cau_hinh.env", ".env"), env_file_encoding="utf-8", extra="ignore")

    database_url: str = "mysql+pymysql://root:@127.0.0.1:3306/assessment_db?charset=utf8mb4"
    database_admin_url: str = ""
    moodle_db_name: str = "moodle"
    moodle_prefix: str = "mdl_"
    jwt_secret: str = "doi-khoa-bi-mat-nay-khi-trien-khai-that-2025"
    jwt_expire_minutes: int = 8 * 60
    default_pass_threshold: float = 60.0
    default_clo_target: float = 70.0
    frontend_dist: str = "../frontend/dist"
    moodle_url: str = ""
    moodle_ws_token: str = ""
    moodle_new_user_password: str = "Sv@123456"
    moodle_sso_secret: str = ""
    rag_sync_minutes: int = 30
    rag_embed_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    rag_page_margin: float = 0.15
    rag_search_similarity: float = 0.40
    rag_min_similarity: float = 0.55
    rag_vlm_model: str = "qwen2.5vl:3b"
    rag_vlm_url: str = "http://127.0.0.1:11434"
    demo_mode: bool = False

    @property
    def app_db_name(self) -> str:
        """Tên CSDL của hệ thống lấy từ DATABASE_URL (mặc định assessment_db)."""
        from urllib.parse import urlparse
        return urlparse(self.database_url.replace("mysql+pymysql", "mysql")).path.lstrip("/") or "assessment_db"


settings = Settings()

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
