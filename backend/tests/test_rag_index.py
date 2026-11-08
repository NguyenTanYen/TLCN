"""Nạp học liệu (services/rag/index): đồng bộ → hàng đợi nạp → đọc PDF → chia đoạn → 'ready' / 'failed' / thử lại."""
import contextlib
import hashlib
import os
import threading
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pymupdf
import pytest
from sqlalchemy import text

from app.database import SessionLocal, engine
from app.models import MaterialPassage, SectionMaterial
from app.services import lms
from app.services.rag import index

FONT = os.path.join(os.path.dirname(__file__), "..", "app", "assets", "fonts", "DejaVuSans.ttf")


def _pdf(text_on_page: bool = True) -> bytes:
    doc = pymupdf.open()
    for title, body in [("Chương 1: Tổng quan", "Cơ sở dữ liệu là tập hợp dữ liệu có cấu trúc."),
                        ("Hệ quản trị CSDL", "Hệ quản trị CSDL quản lý việc lưu trữ và truy xuất dữ liệu.")]:
        pg = doc.new_page(width=720, height=540)
        if text_on_page:
            pg.insert_text((40, 90), title, fontsize=28, fontfile=FONT, fontname="dv")
            pg.insert_text((60, 160), body, fontsize=18, fontfile=FONT, fontname="dv")
        else:
            pg.draw_rect(pymupdf.Rect(0, 0, 720, 540), fill=(0.8, 0.8, 0.8))
    return doc.tobytes()


PDF = _pdf()
REAL_ENQUEUE = index.enqueue


@pytest.fixture(autouse=True)
def index_now(monkeypatch):
    monkeypatch.setattr(index, "enqueue", index.run_section)


@pytest.fixture(scope="module")
def cs_id():
    db = SessionLocal()
    cid = db.execute(text("SELECT id FROM class_sections WHERE moodle_course_id = 50")).scalar()
    db.close()
    assert cid
    yield cid
    db = SessionLocal()
    db.execute(text("DELETE FROM section_materials WHERE class_section_id = :c"), {"c": cid})
    db.commit()
    db.close()


@pytest.fixture()
def moodle(monkeypatch):
    """Moodle giả: tên tệp → nội dung trả về (bytes) hoặc ngoại lệ."""
    files = {}

    def fake_fetch(m, beat=None):
        v = files[m.file_name]
        if isinstance(v, Exception):
            raise v
        return v() if callable(v) else v
    monkeypatch.setattr(index, "fetch", fake_fetch)
    return files


def _url(cs):
    return f"/api/class-sections/{cs}/materials"


def _materials(client, gv, cs):
    return {m["file_name"]: m for m in client.get(_url(cs), headers=gv).json()["materials"]}


def _n_passages(material_id):
    db = SessionLocal()
    n = db.query(MaterialPassage).filter_by(material_id=material_id).count()
    db.close()
    return n


def test_sync_indexes_in_background_each_file_independently(client, gv, cs_id, moodle):
    moodle.update({"slide_ch1.pdf": PDF,
                   "slide_ch2.pdf": b"%PDF-1.7 hong giua chung",
                   "de_on_tap_giua_ky.pdf": _pdf(text_on_page=False),
                   "giao_trinh csdl.pdf": lms.MoodleWSError("Lỗi kết nối LMS: timed out")})
    r = client.post(_url(cs_id) + "/sync", headers=gv)
    assert r.status_code == 200, r.text
    ms = _materials(client, gv, cs_id)
    s1 = ms["slide_ch1.pdf"]
    assert (s1["status"], s1["n_pages"], s1["error"]) == ("ready", 2, None) and s1["indexed_at"]
    assert _n_passages(s1["id"]) >= 2
    assert ms["slide_ch2.pdf"]["status"] == "failed" and "Không đọc được PDF" in ms["slide_ch2.pdf"]["error"]
    assert ms["de_on_tap_giua_ky.pdf"]["status"] == "failed" and "OCR" in ms["de_on_tap_giua_ky.pdf"]["error"]
    book = ms["giao_trinh csdl.pdf"]
    assert book["status"] == "pending" and "timed out" in book["error"]


def test_next_sync_retries_pending_but_not_failed(client, gv, cs_id, moodle):
    moodle.update({"giao_trinh csdl.pdf": PDF, "slide_ch2.pdf": PDF, "de_on_tap_giua_ky.pdf": PDF})
    client.post(_url(cs_id) + "/sync", headers=gv)
    ms = _materials(client, gv, cs_id)
    assert (ms["giao_trinh csdl.pdf"]["status"], ms["giao_trinh csdl.pdf"]["error"]) == ("ready", None)
    assert ms["slide_ch2.pdf"]["status"] == "failed"


def test_reindex_failed_or_ready_material(client, gv, gv_other, cs_id, moodle):
    moodle.update({"slide_ch2.pdf": PDF, "slide_ch1.pdf": PDF})
    ms = _materials(client, gv, cs_id)
    failed, ready, book = ms["slide_ch2.pdf"], ms["slide_ch1.pdf"], ms["giao_trinh csdl.pdf"]
    assert client.post(f"{_url(cs_id)}/{failed['id']}/reindex", headers=gv_other).status_code == 403
    r = client.post(f"{_url(cs_id)}/{failed['id']}/reindex", headers=gv)
    assert r.status_code == 200, r.text
    assert _materials(client, gv, cs_id)["slide_ch2.pdf"]["status"] == "ready"
    n = _n_passages(ready["id"])
    assert client.post(f"{_url(cs_id)}/{ready['id']}/reindex", headers=gv).status_code == 200
    assert _n_passages(ready["id"]) == n
    client.delete(f"{_url(cs_id)}/{book['id']}", headers=gv)
    assert client.post(f"{_url(cs_id)}/{book['id']}/reindex", headers=gv).status_code == 409
    assert _n_passages(book["id"]) == 0


def test_picking_back_an_excluded_file_indexes_it(client, gv, cs_id, moodle):
    moodle["giao_trinh csdl.pdf"] = PDF
    r = client.post(_url(cs_id) + "/moodle", headers=gv,
                    json={"cmid": 810, "content_hash": "04" + "ab" * 19, "material_type": "reference"})
    assert r.status_code == 201, r.text
    assert _materials(client, gv, cs_id)["giao_trinh csdl.pdf"]["status"] == "ready"


def _set_status(material_id, status):
    db = SessionLocal()
    db.query(SectionMaterial).filter_by(id=material_id).update({"status": status})
    db.commit()
    db.close()


def test_result_discarded_if_material_changed_while_indexing(client, gv, cs_id):
    mid = _materials(client, gv, cs_id)["slide_ch1.pdf"]["id"]
    _set_status(mid, "pending")

    def gv_excludes_meanwhile(m):
        _set_status(m.id, "excluded")
        return PDF
    db = SessionLocal()
    db.execute(text("DELETE FROM material_passages WHERE material_id = :m"), {"m": mid})
    db.commit()
    assert index.index_material(db, mid, gv_excludes_meanwhile) is None
    db.close()
    assert _n_passages(mid) == 0
    assert _materials(client, gv, cs_id)["slide_ch1.pdf"]["status"] == "excluded"


def test_only_one_caller_claims_a_material(client, gv, cs_id):
    mid = _materials(client, gv, cs_id)["slide_ch1.pdf"]["id"]
    _set_status(mid, "pending")
    seen = []

    def second_request_meanwhile(m):
        other = SessionLocal()
        seen.append(index.index_material(other, m.id, lambda _m: PDF))
        other.close()
        return PDF
    db = SessionLocal()
    assert index.index_material(db, mid, second_request_meanwhile) == "ready"
    db.close()
    assert seen == [None]


def _claim_at(material_id, when):
    db = SessionLocal()
    db.query(SectionMaterial).filter_by(id=material_id).update({"status": "indexing", "claimed_at": when})
    db.commit()
    db.close()


def test_stale_claim_is_taken_over_and_late_result_discarded(client, gv, cs_id):
    mid = _materials(client, gv, cs_id)["slide_ch1.pdf"]["id"]
    _claim_at(mid, datetime.now() - index.CLAIM_TTL / 2)
    db = SessionLocal()
    assert index.index_material(db, mid, lambda _m: PDF) is None
    _claim_at(mid, datetime.now() - index.CLAIM_TTL - timedelta(minutes=1))
    seen = []

    def old_worker_finishes_meanwhile(m):
        other = SessionLocal()
        seen.append(index._still_mine(other, m.id, datetime(2000, 1, 1)))
        other.rollback()
        other.close()
        return PDF
    assert index.index_material(db, mid, old_worker_finishes_meanwhile) == "ready"
    db.close()
    assert seen == [None]
    m = _materials(client, gv, cs_id)["slide_ch1.pdf"]
    assert m["status"] == "ready"


def test_queue_runs_in_one_background_thread_and_dedupes(monkeypatch):
    started, release, done = threading.Event(), threading.Event(), []

    def slow(cs):
        done.append((cs, threading.current_thread().name))
        started.set()
        release.wait(5)
    monkeypatch.setattr(index, "run_section", slow)
    REAL_ENQUEUE(901)
    assert started.wait(5)
    REAL_ENQUEUE(902)
    REAL_ENQUEUE(902)
    REAL_ENQUEUE(901)
    release.set()
    for _ in range(50):
        if len(done) == 3:
            break
        threading.Event().wait(0.1)
    assert [cs for cs, _ in done] == [901, 902, 901]
    assert {name for _, name in done} == {"rag-indexer"}


def test_periodic_sync_skipped_while_another_worker_holds_the_lock():
    with engine.connect() as other:
        assert other.execute(text("SELECT GET_LOCK(:n, 0)"), {"n": index.SYNC_LOCK}).scalar() == 1
        try:
            assert index.run_all() is False
        finally:
            other.execute(text("SELECT RELEASE_LOCK(:n)"), {"n": index.SYNC_LOCK})


def test_fetch_streams_to_temp_file_and_checks_size_hash_pdf(monkeypatch):
    monkeypatch.setattr(index.settings, "moodle_url", "http://moodle.test/moodle")
    got = {}

    @contextlib.contextmanager
    def stream(url):
        got["url"] = url
        data = got["data"]
        yield iter([data[i:i + 1000] for i in range(0, len(data), 1000)])
    monkeypatch.setattr(index.lms, "stream", stream)

    def m(data, **kw):
        return SimpleNamespace(content_hash=hashlib.sha1(data).hexdigest(), file_size=len(data),
                               moodle_file_url="http://moodle.test/moodle/pluginfile.php/81/mod_resource/content/1/ETL.pdf",
                               **kw)
    got["data"] = PDF
    path = index.fetch(m(PDF))
    with open(path, "rb") as f:
        assert f.read() == PDF
    os.unlink(path)
    assert got["url"] == "http://moodle.test/moodle/webservice/pluginfile.php/81/mod_resource/content/1/ETL.pdf"
    tmp = set(os.listdir(index.tmp_dir()))
    with pytest.raises(index.MaterialError, match="SHA-1"):
        index.fetch(m(PDF + b" "))
    got["data"] = b"PK\x03\x04 pptx"
    with pytest.raises(index.MaterialError, match="không phải PDF"):
        index.fetch(m(got["data"]))
    got["data"] = PDF
    monkeypatch.setattr(index, "MAX_BYTES", 5000)
    with pytest.raises(index.MaterialError, match="quá lớn"):
        index.fetch(SimpleNamespace(**{**vars(m(PDF)), "file_size": 10}))
    assert set(os.listdir(index.tmp_dir())) == tmp
    with pytest.raises(index.MaterialError, match="quá lớn"):
        index.fetch(SimpleNamespace(content_hash="x", file_size=5001, moodle_file_url=""))
    with pytest.raises(index.MaterialError, match="không thuộc Moodle"):
        index.fetch(SimpleNamespace(content_hash="x", file_size=1,
                                    moodle_file_url="http://evil.test/moodle/pluginfile.php/1/a.pdf"))


def _die(src, conn):
    os._exit(137)


def _hang(src, conn):
    time.sleep(60)


def test_parse_runs_in_child_process_and_survives_crash_or_hang(monkeypatch):
    pages, passages = index.parse_isolated(PDF)
    assert len(pages) == 2 and passages and not pages[0].blocks
    with pytest.raises(index.MaterialError, match="Không đọc được PDF"):
        index.parse_isolated(b"%PDF-1.7 hong")
    with pytest.raises(index.MaterialError, match="dừng đột ngột"):
        index.parse_isolated(PDF, target=_die)
    monkeypatch.setattr(index, "PARSE_TIMEOUT", 3)
    monkeypatch.setattr(index, "HEARTBEAT_S", 0.5)
    beats = []
    t = time.monotonic()
    with pytest.raises(index.MaterialError, match="quá"):
        index.parse_isolated(PDF, lambda: beats.append(1), target=_hang)
    assert time.monotonic() - t < 20 and len(beats) >= 2


def test_heartbeat_extends_claim_and_stops_when_claim_taken(client, gv, cs_id, monkeypatch):
    mid = _materials(client, gv, cs_id)["slide_ch1.pdf"]["id"]
    _set_status(mid, "pending")
    monkeypatch.setattr(index, "HEARTBEAT_S", 0)

    def taken_by_other_worker(m):
        _claim_at(m.id, datetime(2030, 1, 1))
        return PDF
    db = SessionLocal()
    assert index.index_material(db, mid, taken_by_other_worker) is None
    db.close()
    db = SessionLocal()
    assert db.get(SectionMaterial, mid).claimed_at == datetime(2030, 1, 1)
    db.close()
    _set_status(mid, "pending")
    db = SessionLocal()

    def no_open_transaction(m):
        assert not db.in_transaction() and m.file_name == "slide_ch1.pdf"
        return PDF
    assert index.index_material(db, mid, no_open_transaction) == "ready"
    assert db.get(SectionMaterial, mid).claimed_at is None
    db.close()


def test_clean_tmp_removes_only_old_leftovers():
    old, new = (os.path.join(index.tmp_dir(), f"hoc_lieu_test_{k}.pdf") for k in ("old", "new"))
    for f in (old, new):
        with open(f, "wb") as fh:
            fh.write(b"%PDF")
    os.utime(old, (time.time() - index.TMP_MAX_AGE - 10,) * 2)
    index.clean_tmp()
    assert not os.path.exists(old) and os.path.exists(new)
    os.unlink(new)
