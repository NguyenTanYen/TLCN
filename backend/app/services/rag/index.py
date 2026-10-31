"""Nạp học liệu: tải tệp từ Moodle → đọc PDF (ingest) → chia đoạn (chunk) → lưu trang / đoạn (store).

Tải qua webservice/pluginfile.php bằng token của dịch vụ local_clo (đã bật "tải tệp"), không đọc thẳng thư mục
moodledata – backend chạy ở máy khác Moodle vẫn dùng được. Tệp được tải THEO TỪNG KHÚC xuống tệp tạm (PyMuPDF đọc từ
đĩa – tệp 100 MB không nằm trọn trong RAM) và được kiểm ngay trong lúc tải:
  - không vượt MAX_BYTES (không tin kích thước Moodle báo – cắt ngay khi vượt);
  - SHA-1 nội dung phải đúng content_hash (Moodle đặt contenthash = SHA-1 nội dung) – tải nhầm / hỏng giữa đường là
    phát hiện được;
  - bắt đầu bằng "%PDF".

MỘT LUỒNG NẠP RIÊNG cho cả tiến trình (enqueue): API chỉ xếp lớp vào hàng đợi rồi trả lời ngay, mỗi lúc chỉ nạp MỘT
tệp (RAM có trần). Việc đọc PDF + chia đoạn (nặng CPU, giáo trình 371 trang mất ~1,5 phút) chạy trong TIẾN TRÌNH CON
(parse_isolated): đọc ở luồng thì giữ GIL – đo được request nhẹ của API bị trễ thêm p95 ≈ 25 ms, có lúc 200 ms. Tiến
trình con còn cách ly sự cố: hết RAM bị hệ điều hành kill thì chỉ tiến trình con chết (tệp → 'failed'), server vẫn
sống; quá PARSE_TIMEOUT thì bị dừng.

Mỗi học liệu đi qua ba giao dịch NGẮN, không giữ khóa trong lúc tải và đọc PDF:
  1. giữ chỗ: 'pending' → 'indexing' + claimed_at (UPDATE có điều kiện – nhiều luồng / nhiều tiến trình cùng lúc thì
     chỉ một bên giữ được). Giữ chỗ CÓ HẠN, có NHỊP (heartbeat): trong lúc tải / đọc, cứ HEARTBEAT_S giây gia hạn
     claimed_at một lần; tiến trình nạp chết thì sau CLAIM_TTL (vài phút) bên khác nạp lại – không có bước "khởi động
     thì reset" (tiến trình vừa khởi động không biết tiến trình khác còn đang nạp hay không). Gia hạn thất bại (bên khác
     đã giữ chỗ lại) → dừng ngay;
  2. tải + đọc + chia đoạn, không ghi CSDL;
  3. ghi kết quả – CHỈ khi học liệu vẫn đang 'indexing' với ĐÚNG lần giữ chỗ của mình: trong lúc nạp mà đồng bộ đánh
     dấu 'missing', GV bỏ chọn ('excluded'), có phiên bản mới (bản ghi bị xóa) hoặc quá hạn và bên khác đã giữ chỗ lại
     thì bỏ kết quả. Kiểm tra (SELECT ... FOR UPDATE) và ghi trang / đoạn nằm trong CÙNG một giao dịch. QUY ƯỚC cho
     giai đoạn sau: dữ liệu ngoài MySQL (vector, ảnh trang) chỉ được ghi SAU khi giao dịch này commit, khóa theo id
     đoạn – không ghi trước rồi mới kiểm, để bên mất quyền không để lại dữ liệu mồ côi.
Lỗi kết nối Moodle → trả về 'pending' (lần đồng bộ sau thử lại); lỗi ở chính tệp (không phải PDF, sai SHA-1, PDF hỏng,
không có chữ) → 'failed' kèm lý do, GV nạp lại bằng tay. Một tệp lỗi không chặn các tệp khác.

Đồng bộ định kỳ (run_all) giữ khóa tên của MySQL (GET_LOCK): chạy nhiều worker uvicorn thì mỗi lúc cũng chỉ một vòng
đồng bộ chạy, các worker khác bỏ lượt.
"""
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
from . import search, store, sync
from .chunk import build_passages
from .ingest import read_pdf

log = logging.getLogger(__name__)

MAX_BYTES = 100 * 1024 * 1024      # tệp lớn hơn thì không nạp (giáo trình scan vài trăm MB)
CLAIM_TTL = timedelta(minutes=5)   # không gia hạn giữ chỗ quá lâu = tiến trình nạp đã chết → cho nạp lại
HEARTBEAT_S = 60.0                 # nhịp gia hạn giữ chỗ trong lúc tải / đọc (phải nhỏ hơn nhiều so với CLAIM_TTL)
PARSE_TIMEOUT = 15 * 60            # giây: đọc một PDF quá lâu (tệp lỗi làm treo bộ đọc) → dừng tiến trình con, 'failed'
TMP_MAX_AGE = 60 * 60              # giây: tệp tạm cũ hơn = sót lại sau khi tiến trình bị kill → xóa
SYNC_LOCK = "clo_rag_sync_all"     # khóa tên (GET_LOCK) của vòng đồng bộ định kỳ

Fetcher = Callable[[SectionMaterial], "bytes | str"]   # nội dung PDF, hoặc đường dẫn tệp tạm (nơi gọi xóa)


class MaterialError(ValueError):
    """Lỗi ở chính tệp học liệu – nạp lại cũng vẫn lỗi cho tới khi GV sửa tệp."""


class _LostClaim(Exception):
    """Gia hạn giữ chỗ thất bại – bên khác đã nhận nạp học liệu này."""


def tmp_dir() -> str:
    d = os.path.join(tempfile.gettempdir(), "clo_hoc_lieu")
    os.makedirs(d, exist_ok=True)
    return d


def clean_tmp(max_age: float = TMP_MAX_AGE) -> int:
    """Xóa tệp tạm sót lại (tiến trình bị kill – SIGKILL / hết RAM – thì finally không chạy). Chỉ xóa tệp CŨ: worker
    khác đang tải dở thì tệp còn mới."""
    n, now = 0, time.time()
    for f in os.scandir(tmp_dir()):
        try:
            if f.is_file() and now - f.stat().st_mtime > max_age:
                os.unlink(f.path)
                n += 1
        except OSError:
            pass                              # đang được mở (Windows) / vừa bị worker khác xóa
    return n


def download_url(m: SectionMaterial) -> str:
    """Liên kết pluginfile (SV mở) → webservice/pluginfile (tải bằng token)."""
    base = settings.moodle_url.rstrip("/")
    url = m.moodle_file_url or ""
    if not url.startswith(base + "/pluginfile.php/"):
        raise MaterialError("Liên kết tệp không thuộc Moodle đã cấu hình (MOODLE_URL) – hãy đồng bộ lại")
    return base + "/webservice" + url[len(base):]


def fetch(m: SectionMaterial, beat: Callable[[], None] = lambda: None) -> str:
    """Tải tệp về một tệp tạm, kiểm trong lúc tải; trả về đường dẫn (nơi gọi xóa sau khi đọc). beat: gia hạn giữ chỗ."""
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
    except Exception as ex:                                   # PDF hỏng, có mật khẩu...
        raise MaterialError(f"Không đọc được PDF: {ex}") from ex
    passages = build_passages(pages)
    if not passages:
        raise MaterialError("Không đọc được chữ nào trong tệp (PDF ảnh quét?) – hiện chưa hỗ trợ nhận dạng chữ (OCR)")
    return pages, passages


def _child(src: bytes | str, conn) -> None:
    """Chạy trong tiến trình con: đọc + chia đoạn, gửi kết quả qua pipe. Trang gửi về không kèm khối chữ / hình / bảng
    (store chỉ cần thông tin trang) cho gọn."""
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
    except OSError:                                           # tiến trình cha đã thôi chờ (mất giữ chỗ / quá giờ)
        pass
    finally:
        conn.close()


def parse_isolated(src: bytes | str, beat: Callable[[], None] = lambda: None, target=_child):
    """parse() trong tiến trình con (spawn – an toàn khi tiến trình cha có nhiều luồng). Trong lúc chờ: gia hạn giữ
    chỗ (beat), canh tiến trình con chết đột ngột và quá PARSE_TIMEOUT."""
    ctx = multiprocessing.get_context("spawn")
    recv, send = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=target, args=(src, send), name="rag-parse", daemon=True)
    proc.start()
    send.close()                                              # chỉ con giữ đầu ghi: con chết thì recv báo hết dữ liệu
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
    stamp = datetime.now().replace(microsecond=0)              # cột DATETIME lưu tới giây
    n = (db.query(SectionMaterial).filter(SectionMaterial.id == material_id, _claimable())
         .update({"status": "indexing", "claimed_at": stamp}, synchronize_session=False))
    db.commit()
    return stamp if n == 1 else None


def _still_mine(db: Session, material_id: int, stamp: datetime) -> SectionMaterial | None:
    # populate_existing: đối tượng đã nạp trong phiên (claimed_at lúc giữ chỗ) phải được GHI ĐÈ bằng dòng vừa khóa –
    # nếu không, sau khi beat() commit, SQLAlchemy trả lại bản cũ trong phiên và so nhầm lần giữ chỗ
    m = db.query(SectionMaterial).filter_by(id=material_id).with_for_update().populate_existing().first()
    return m if m and m.status == "indexing" and m.claimed_at == stamp else None


def index_material(db: Session, material_id: int, fetcher: Fetcher | None = None) -> str | None:
    """Nạp một học liệu đang chờ. Trả về trạng thái sau khi nạp, None nếu không phải việc của lần gọi này."""
    stamp = _claim(db, material_id)
    if not stamp:
        return None
    claim = {"stamp": stamp, "at": time.monotonic()}

    def beat() -> None:
        """Gia hạn giữ chỗ (tối đa một lần mỗi HEARTBEAT_S giây); bên khác đã giữ chỗ lại → _LostClaim."""
        if time.monotonic() - claim["at"] < HEARTBEAT_S:
            return
        new = datetime.now().replace(microsecond=0)
        if new <= claim["stamp"]:                             # cột lưu tới giây: chưa sang giây mới thì chưa cần gia hạn
            return
        # phiên RIÊNG, sống một câu lệnh: commit của nhịp không làm hết hạn / lệch đối tượng trong phiên nạp (lỗi
        # claimed_at cũ ở _still_mine từng do dùng chung phiên)
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
    db.expunge(m)            # giữ bản đọc được (fetch cần url / hash) rồi KẾT THÚC giao dịch đọc: suốt lúc tải / đọc PDF
    db.rollback()            # không giữ giao dịch mở, không chiếm kết nối của pool (beat() mở-commit giao dịch ngắn riêng)
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
    except lms.MoodleWSError as ex:                           # Moodle không trả lời được: để lần sau thử lại
        status, error = "pending", str(ex)[:1000]
    except MaterialError as ex:
        error = str(ex)[:1000]
    except Exception as ex:                                   # lỗi ngoài dự kiến của bộ đọc / chia đoạn
        log.exception("Nạp học liệu %s lỗi", material_id)
        error = f"Lỗi khi nạp: {type(ex).__name__}: {ex}"[:1000]
    db.rollback()                                             # bỏ ảnh chụp cũ, đọc lại bản ghi mới nhất
    m = _still_mine(db, material_id, claim["stamp"])
    if not m:                                                 # đã bị đồng bộ / GV đổi / bên khác giữ lại trong lúc nạp
        db.rollback()
        return None
    if result:
        sheets = {p.no for p in result[0] if p.sheet}         # đọc ở tiến trình con nên log của ingest không tới đây
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
    """Nạp các tệp chờ của một lớp – phiên CSDL riêng – rồi dựng sẵn chỉ mục tìm kiếm của lớp (dựng khi GHI: lần tìm
    sau không phải dựng)."""
    db = SessionLocal()
    try:
        index_pending(db, cs_id)
        db.rollback()
        search.warm(db, cs_id)
    except Exception:
        log.exception("Nạp học liệu lớp %s lỗi", cs_id)
    finally:
        db.close()


# ------------------------------------------------------------------ hàng đợi: một luồng nạp cho cả tiến trình
_jobs: "queue.Queue[int]" = queue.Queue()
_waiting: set[int] = set()
_guard = threading.Lock()
_worker: threading.Thread | None = None


def _work() -> None:
    clean_tmp()
    while True:
        cs_id = _jobs.get()
        with _guard:
            _waiting.discard(cs_id)       # bỏ khỏi danh sách TRƯỚC khi nạp: tệp mới thêm trong lúc nạp → xếp lại được
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
    """Đồng bộ học liệu của mọi lớp có gắn khóa học Moodle rồi xếp vào hàng đợi nạp (chạy định kỳ).
    Trả về False nếu worker khác đang chạy vòng này (khóa tên giữ trên MỘT kết nối riêng suốt vòng)."""
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
