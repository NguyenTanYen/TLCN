"""Điểm vào ứng dụng FastAPI – Hệ thống hỗ trợ kiểm tra, đánh giá và phân tích mức độ đạt CĐR."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .routers import analytics, auth, catalog, exams, lms, questions, reports, sync

app = FastAPI(title="Hệ thống đánh giá mức độ đạt CĐR (OBE Assessment)", version="2.0",
              description="Tiểu luận chuyên ngành – Nhóm 01. Tài liệu API tự sinh (OpenAPI).")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for r in (auth, catalog, questions, exams, sync, lms, analytics, reports):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/public-config")
def public_config():
    """Địa chỉ Moodle để giao diện hiển thị liên kết "Về Moodle"."""
    return {"moodle_url": settings.moodle_url}


dist = (Path(__file__).resolve().parent.parent / settings.frontend_dist).resolve()
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = (dist / path).resolve()
        ok = path and f.is_file() and dist in f.parents  # chặn truy cập ra ngoài thư mục dist
        return FileResponse(f if ok else dist / "index.html")
