"""Nạp học liệu: tải tệp từ Moodle → đọc PDF (ingest) → chia đoạn (chunk) → lưu trang / đoạn (store)."""
from __future__ import annotations

import hashlib
import logging
import multiprocessing
import os
import queue
import tempfile
import threading
import time
from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy import or_, text, update
from sqlalchemy.orm import Session

from ...config import settings
from ...database import SessionLocal, engine
from ...models import ClassSection, SectionMaterial
from .. import lms
from . import search, semantic, store, sync, vlm
from .chunk import build_passages
from .ingest import read_pdf

log = logging.getLogger(__name__)

MAX_BYTES = 100 * 1024 * 1024
CLAIM_TTL = timedelta(minutes=5)
HEARTBEAT_S = 60.0
PARSE_TIMEOUT = 15 * 60
TMP_MAX_AGE = 60 * 60
SYNC_LOCK = "clo_rag_sync_all"

Fetcher = Callable[[SectionMaterial], "bytes | str"]


class MaterialError(ValueError):
    """Lỗi ở chính tệp học liệu – nạp lại cũng vẫn lỗi cho tới khi GV sửa tệp."""


class _LostClaim(Exception):
    """Gia hạn giữ chỗ thất bại – bên khác đã nhận nạp học liệu này."""


def tmp_dir() -> str:
    d = os.path.join(tempfile.gettempdir(), "clo_hoc_lieu")
    os.makedirs(d, exist_ok=True)
    return d


def clean_tmp(max_age: float = TMP_MAX_AGE) -> int:
    """Xóa tệp tạm sót lại (tiến trình bị kill – SIGKILL / hết RAM – thì finally không chạy)."""
    n, now = 0, time.time()
    for f in os.scandir(tmp_dir()):
        try:
            if f.is_file() and now - f.stat().st_mtime > max_age:
                os.unlink(f.path)
                n += 1
        except OSError:
            pass
    return n


def download_url(m: SectionMaterial) -> str:
    """Liên kết pluginfile (SV mở) → webservice/pluginfile (tải bằng token)."""
    base = settings.moodle_url.rstrip("/")
    url = m.moodle_file_url or ""
    if not url.startswith(base + "/pluginfile.php/"):
        raise MaterialError("Liên kết tệp không thuộc Moodle đã cấu hình (MOODLE_URL) – hãy đồng bộ lại")
    return base + "/webservice" + url[len(base):]


def fetch(m: SectionMaterial, beat: Callable[[], None] = lambda: None) -> str:
    """Tải tệp về một tệp tạm, kiểm trong lúc tải; trả về đường dẫn (nơi gọi xóa sau khi đọc)."""
    if m.file_size and m.file_size > MAX_BYTES:
        raise MaterialError(f"Tệp quá lớn ({m.file_size // 1048576} MB, tối đa {MAX_BYTES // 1048576} MB)")
    url = download_url(m)
    fd, path = tempfile.mkstemp(prefix="hoc_lieu_", suffix=".pdf", dir=tmp_dir())
    try:
        sha, size, head = hashlib.sha1(), 0, b""
        with os.fdopen(fd, "wb") as fh, lms.stream(url) as chunks:
            for c in chunks:
                size += len(c)
                if size > MAX_BYTES:
                    raise MaterialError(f"Tệp quá lớn (trên {MAX_BYTES // 1048576} MB)")
                head = (head + c[:4])[:4]
                sha.update(c)
                fh.write(c)
                beat()
        if sha.hexdigest() != m.content_hash:
            raise MaterialError("Nội dung tải về không khớp tệp trên Moodle (SHA-1 khác) – tệp vừa bị thay, hãy đồng bộ lại")
        if head != b"%PDF":
            raise MaterialError("Tệp không phải PDF")
    except BaseException:
        os.unlink(path)
        raise
    return path


def parse(src: bytes | str):
    try:
        pages = read_pdf(src)
    except Exception as ex:
        raise MaterialError(f"Không đọc được PDF: {ex}") from ex
    passages = build_passages(pages)
    if not passages:
        raise MaterialError("Không đọc được chữ nào trong tệp (PDF ảnh quét?) – hiện chưa hỗ trợ nhận dạng chữ (OCR)")
    return pages, passages


def _child(src: bytes | str, conn) -> None:
    """Chạy trong tiến trình con: đọc + chia đoạn, gửi kết quả qua pipe."""
    try:
        pages, passages = parse(src)
        for p in pages:
            p.blocks, p.figures, p.tables = [], [], []
        msg = ("ok", (pages, passages))
    except MaterialError as ex:
        msg = ("bad", str(ex))
    except Exception as ex:
        msg = ("crash", f"{type(ex).__name__}: {ex}")
    try:
        conn.send(msg)
    except OSError:
        pass
    finally:
        conn.close()


def parse_isolated(src: bytes | str, beat: Callable[[], None] = lambda: None, target=_child):
    """parse() trong tiến trình con (spawn – an toàn khi tiến trình cha có nhiều luồng)."""
    ctx = multiprocessing.get_context("spawn")
    recv, send = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=target, args=(src, send), name="rag-parse", daemon=True)
    proc.start()
    send.close()
    deadline = time.monotonic() + PARSE_TIMEOUT
    try:
        while not recv.poll(min(HEARTBEAT_S, 5.0)):
            if time.monotonic() > deadline:
                raise MaterialError(f"Đọc PDF quá {PARSE_TIMEOUT // 60} phút – tệp có thể bị lỗi cấu trúc")
            beat()
        try:
            kind, value = recv.recv()
        except EOFError:
            raise MaterialError("Tiến trình đọc PDF bị dừng đột ngột (thiếu bộ nhớ?) – tệp có thể quá phức tạp") from None
    finally:
        recv.close()
        proc.join(5)
        if proc.is_alive():
            proc.terminate()
            proc.join(5)
    if kind == "bad":
        raise MaterialError(value)
    if kind == "crash":
        raise RuntimeError(value)
    return value


def _claimable():
    """Chờ nạp, hoặc đang nạp nhưng quá hạn (tiến trình nạp đã chết)."""
    return or_(SectionMaterial.status == "pending",
               (SectionMaterial.status == "indexing") & (SectionMaterial.claimed_at < datetime.now() - CLAIM_TTL))


def _claim(db: Session, material_id: int) -> datetime | None:
    stamp = datetime.now().replace(microsecond=0)
    n = (db.query(SectionMaterial).filter(SectionMaterial.id == material_id, _claimable())
         .update({"status": "indexing", "claimed_at": stamp}, synchronize_session=False))
    db.commit()
    return stamp if n == 1 else None


def _still_mine(db: Session, material_id: int, stamp: datetime) -> SectionMaterial | None:
    m = db.query(SectionMaterial).filter_by(id=material_id).with_for_update().populate_existing().first()
    return m if m and m.status == "indexing" and m.claimed_at == stamp else None


def index_material(db: Session, material_id: int, fetcher: Fetcher | None = None) -> str | None:
    """Nạp một học liệu đang chờ."""
    stamp = _claim(db, material_id)
    if not stamp:
        return None
    claim = {"stamp": stamp, "at": time.monotonic()}

    def beat() -> None:
        """Gia hạn giữ chỗ (tối đa một lần mỗi HEARTBEAT_S giây); bên khác đã giữ chỗ lại → _LostClaim."""
        if time.monotonic() - claim["at"] < HEARTBEAT_S:
            return
        new = datetime.now().replace(microsecond=0)
        if new <= claim["stamp"]:
            return
        with Session(bind=db.get_bind()) as s:
            n = s.execute(update(SectionMaterial)
                          .where(SectionMaterial.id == material_id, SectionMaterial.status == "indexing",
                                 SectionMaterial.claimed_at == claim["stamp"])
                          .values(claimed_at=new)).rowcount
            s.commit()
        if n != 1:
            raise _LostClaim()
        claim.update(stamp=new, at=time.monotonic())

    m = db.get(SectionMaterial, material_id)
    db.expunge(m)
    db.rollback()
    status, error, result = "failed", None, None
    try:
        src = fetcher(m) if fetcher else fetch(m, beat)
        try:
            result = parse_isolated(src, beat)
        finally:
            if isinstance(src, str):
                os.unlink(src)
    except _LostClaim:
        db.rollback()
        return None
    except lms.MoodleWSError as ex:
        status, error = "pending", str(ex)[:1000]
    except MaterialError as ex:
        error = str(ex)[:1000]
    except Exception as ex:
        log.exception("Nạp học liệu %s lỗi", material_id)
        error = f"Lỗi khi nạp: {type(ex).__name__}: {ex}"[:1000]
    db.rollback()
    m = _still_mine(db, material_id, claim["stamp"])
    if not m:
        db.rollback()
        return None
    if result:
        sheets = {p.no for p in result[0] if p.sheet}
        if sheets:
            log.info("Học liệu %s (%s): bản in handout – %d/%d trang, %d slide", m.id, m.file_name, len(sheets),
                     len({p.no for p in result[0]}), sum(1 for p in result[0] if p.sheet))
        sync.delete_indexed(db, m.id)
        store.save_document(db, m, *result)
    else:
        m.status, m.error = status, error
    m.claimed_at = None
    db.commit()
    return m.status


def index_pending(db: Session, cs_id: int, fetcher: Fetcher | None = None) -> dict:
    out = {"ready": [], "failed": [], "pending": []}
    ids = [i for (i,) in db.query(SectionMaterial.id)
           .filter(SectionMaterial.class_section_id == cs_id, SectionMaterial.source == "moodle", _claimable())
           .order_by(SectionMaterial.id)]
    db.rollback()
    for i in ids:
        st = index_material(db, i, fetcher)
        if st in out:
            out[st].append(i)
    return out


def run_section(cs_id: int) -> None:
    """Nạp các tệp chờ của một lớp – phiên CSDL riêng – rồi dựng sẵn chỉ mục tìm kiếm của lớp (dựng khi GHI: lần tìm sau không phải dựng) và tính vector cho cổng ngữ nghĩa (sau khi đoạn đã commit; cổng tắt thì bỏ qua)."""
    db = SessionLocal()
    try:
        index_pending(db, cs_id)
        db.rollback()
        search.warm(db, cs_id)
        semantic.embed_missing(db, cs_id)
        if vlm.describe_missing(db, cs_id):
            search.warm(db, cs_id)
            semantic.embed_missing(db, cs_id)
    except Exception:
        log.exception("Nạp học liệu lớp %s lỗi", cs_id)
    finally:
        db.close()


_jobs: "queue.Queue[int]" = queue.Queue()
_waiting: set[int] = set()
_guard = threading.Lock()
_worker: threading.Thread | None = None


def _work() -> None:
    clean_tmp()
    while True:
        cs_id = _jobs.get()
        with _guard:
            _waiting.discard(cs_id)
        run_section(cs_id)


def enqueue(cs_id: int) -> None:
    """Xếp lớp vào hàng đợi nạp (lớp đã đang chờ thì thôi) – trả về ngay."""
    global _worker
    with _guard:
        if cs_id in _waiting:
            return
        _waiting.add(cs_id)
        _jobs.put(cs_id)
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_work, name="rag-indexer", daemon=True)
            _worker.start()


def run_all() -> bool:
    """Đồng bộ học liệu của mọi lớp có gắn khóa học Moodle rồi xếp vào hàng đợi nạp (chạy định kỳ)."""
    with engine.connect() as lock:
        if not lock.execute(text("SELECT GET_LOCK(:n, 0)"), {"n": SYNC_LOCK}).scalar():
            return False
        try:
            db = SessionLocal()
            try:
                for cs in db.query(ClassSection).filter(ClassSection.moodle_course_id.isnot(None)).all():
                    try:
                        sync.sync_section(db, cs)
                    except Exception:
                        db.rollback()
                        log.exception("Đồng bộ học liệu lớp %s lỗi", cs.id)
                    enqueue(cs.id)
            finally:
                db.close()
        finally:
            lock.execute(text("SELECT RELEASE_LOCK(:n)"), {"n": SYNC_LOCK})
    return True
