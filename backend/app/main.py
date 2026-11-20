import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import DataError, IntegrityError
from fastapi.staticfiles import StaticFiles

from . import migrate
from .config import settings
from .services.rag import index as rag_index
from .routers import analytics, dashboard, improvement, auth, catalog, courses, exams, grading, insights, lms, paper_exam, rubrics, programs, qsync, remedial, question_io, questions, reports, section_materials, syllabi, sync

app = FastAPI(title="Hệ thống đánh giá mức độ đạt CĐR (OBE Assessment)", version="2.0",
              description="Tiểu luận chuyên ngành – Nhóm 01. Tài liệu API tự sinh (OpenAPI).")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for r in (auth, programs, catalog, courses, syllabi, question_io, questions, exams, grading, remedial, paper_exam, qsync, sync, lms, analytics, dashboard, improvement, insights, reports, rubrics, section_materials):
    app.include_router(r.router)


@app.exception_handler(IntegrityError)
def _integrity(_req: Request, ex: IntegrityError):
    msg = str(getattr(ex, "orig", ex))
    hint = "Dữ liệu bị trùng" if "Duplicate" in msg else "Dữ liệu vi phạm ràng buộc toàn vẹn"
    return JSONResponse({"detail": f"{hint}: {msg[:300]}"}, status_code=409)


@app.exception_handler(DataError)
def _data(_req: Request, ex: DataError):
    return JSONResponse({"detail": f"Dữ liệu không hợp lệ (quá dài hoặc sai kiểu): {str(getattr(ex, 'orig', ex))[:300]}"},
                        status_code=422)


async def _rag_loop():
    while True:
        await asyncio.sleep(settings.rag_sync_minutes * 60)
        try:
            await asyncio.to_thread(rag_index.run_all)
        except Exception:
            logging.getLogger(__name__).exception("Đồng bộ học liệu định kỳ lỗi")


@asynccontextmanager
async def lifespan(_app):
    migrate.run()
    task = asyncio.create_task(_rag_loop()) if settings.rag_sync_minutes > 0 else None
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app.router.lifespan_context = lifespan


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/public-config")
def public_config():
    return {"moodle_url": settings.moodle_url, "demo_mode": settings.demo_mode}


dist = (Path(__file__).resolve().parent.parent / settings.frontend_dist).resolve()
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Không có chức năng API này")
        f = (dist / path).resolve()
        ok = path and f.is_file() and dist in f.parents
        return FileResponse(f if ok else dist / "index.html", headers={"Cache-Control": "no-cache, must-revalidate"})
