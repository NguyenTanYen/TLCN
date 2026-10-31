"""Bước 6: tìm đoạn học liệu bằng BM25 – tách từ tiếng Việt, chỉ trong học liệu 'ready' của đúng lớp học phần."""
import hashlib
import threading
import time
import unicodedata
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models import MaterialPage, MaterialPassage, SectionMaterial
from app.services.rag import search
from app.services.rag.search import Index, query_terms, tokens


def test_tokens_same_word_whatever_tone_placement_or_unicode_form():
    assert tokens("hoà") == tokens("hòa") == tokens(unicodedata.normalize("NFD", "hòa")) == ["hoaF"]
    assert tokens("thuỷ") == tokens("thủy")
    assert tokens("bàn") != tokens("bán") and tokens("cơ") != tokens("có")      # dấu khác → từ khác
    assert tokens("mã") != tokens("max") and tokens("thí") != tokens("this")     # dấu thanh không trùng từ tiếng Anh


def test_tokens_drop_function_words_and_pair_syllables_within_phrase():
    assert tokens("Khóa ngoại là gì?") == ["khoaS", "ngoaiJ", "khoaS_ngoaiJ"]
    assert "ngoaiJ_bangR" not in tokens("khóa ngoại, bảng")                      # cặp không vượt dấu câu
    assert "khoaS_ngoaiJ" not in tokens("khóa của ngoại")                        # cặp có hư từ bỏ
    assert tokens("B-tree") == ["b", "tree", "b_tree"]


def test_query_terms_balance_compound_words_against_single_terms():
    q = query_terms("NameNode có vai trò gì?")
    assert q == {"namenode": 1.0, "vai": 0.5, "troF": 0.5, "vai_troF": 0.5}


def test_bm25_phrase_beats_scattered_syllables_and_rare_term_beats_common():
    ix = Index.build([
        (1, "Khóa ngoại tham chiếu tới khóa chính của bảng khác."),
        (2, "Mỗi bảng có một khóa. Dữ liệu ngoại lai được loại bỏ."),             # "khóa" ... "ngoại" rời
        (3, "Bảng sinh viên lưu thông tin sinh viên."),
        (4, "Bảng lớp lưu thông tin lớp."),
    ])
    assert [i for i, _, _ in ix.score("khóa ngoại", 5)][:2] == [1, 2]
    assert [i for i, _, _ in ix.score("bảng sinh viên", 5)][0] == 3
    assert ix.score("là của các", 5) == [] and Index.build([]).score("khóa", 5) == []


def test_query_without_diacritics_searches_folded_index_only_then():
    ix = Index.build([
        (1, "Đặc trưng 5V của dữ liệu lớn: khối lượng, tốc độ, đa dạng."),
        (2, "Bàn phím và màn hình."),
        (3, "Bán hàng trực tuyến."),
    ])
    assert ix.folded is None                                                    # chưa cần thì chưa dựng
    assert [i for i, _, _ in ix.score("dac trung 5V du lieu lon", 5)][0] == 1
    assert {i for i, _, _ in ix.score("ban", 5)} == {2, 3}                     # không dấu: khớp mọi dấu
    assert [i for i, _, _ in ix.score("bàn", 5)] == [2]                        # có dấu: chỉ đúng dấu
    assert [i for i, _, _ in ix.score("HDFS", 5)] == []


def test_plain_query_function_words_only_count_inside_pairs():
    q = query_terms("co so du lieu la gi", plain_query=True)
    assert "co" not in q and "la" not in q and "gi" not in q and "la_gi" not in q    # hư từ bỏ dấu: không tính riêng
    assert q["co_so"] == 0.5 and q["du_lieu"] == 0.5 and q["so"] == 0.5             # ... nhưng "cơ sở" vẫn khớp cặp
    ix = Index.build([
        (1, "Cơ sở dữ liệu quan hệ lưu dữ liệu thành bảng."),
        (2, "Mốt thời trang năm nay."),                       # "mốt" hiếm → "mot" bỏ dấu IDF cao nếu được tính riêng
        (3, "Khóa ngoại là một ràng buộc tham chiếu."),
    ])
    assert [i for i, _, _ in ix.score("co so du lieu", 5)][0] == 1
    assert [i for i, _, _ in ix.score("khoa ngoai la mot rang buoc", 5)] == [3]


# ------------------------------------------------------------------ trên CSDL: phạm vi lớp, làm mới chỉ mục, API
@pytest.fixture()
def sections():
    db = SessionLocal()
    cs = db.execute(text("SELECT id FROM class_sections WHERE moodle_course_id = 50")).scalar()
    other = db.execute(text("SELECT MIN(id) FROM class_sections WHERE id <> :c"), {"c": cs}).scalar()
    db.close()
    yield cs, other
    db = SessionLocal()
    db.execute(text("DELETE FROM section_materials WHERE file_name LIKE 'test_search_%'"))
    db.commit()
    db.close()


def _warm(cs: int) -> None:
    """Như luồng nạp: dựng sẵn chỉ mục của lớp sau khi học liệu đổi."""
    db = SessionLocal()
    try:
        search.warm(db, cs)
    finally:
        db.close()


def _material(cs: int, name: str, passages: list[tuple[str, str]], status="ready", warm=True) -> int:
    db = SessionLocal()
    m = SectionMaterial(class_section_id=cs, title=name, file_name=f"test_search_{name}.pdf", content_hash=hashlib.sha1(name.encode()).hexdigest(),
                        status=status, indexed_at=datetime.now().replace(microsecond=0), n_pages=len(passages))
    db.add(m)
    db.flush()
    for no, (title, body) in enumerate(passages, 1):
        pg = MaterialPage(material_id=m.id, page_no=no, width=720, height=540)
        db.add(pg)
        db.flush()
        db.add(MaterialPassage(material_id=m.id, page_id=pg.id, seq=no, kind="text", title=title, breadcrumb=title,
                               body=body, bboxes=[[40, 80, 600, 200]]))
    db.commit()
    mid = m.id
    db.close()
    if warm:
        _warm(cs)
    return mid


def _search(cs, q, k=10):
    """Chỉ giữ học liệu của tệp test này (lớp có thể còn học liệu của test khác)."""
    db = SessionLocal()
    try:
        return [h for h in search.search(db, cs, q, k) if h.file_name.startswith("test_search_")]
    finally:
        db.close()


def test_search_only_ready_materials_of_the_section(sections):
    cs, other = sections
    a = _material(cs, "chuong3", [("Khóa ngoại", "Khóa ngoại tham chiếu tới khóa chính của bảng khác."),
                                  ("Chuẩn hóa", "Dạng chuẩn 3NF loại bỏ phụ thuộc bắc cầu.")])
    _material(cs, "nhap", [("Khóa ngoại nháp", "Khóa ngoại – bản nháp GV đã bỏ chọn.")], status="excluded")
    _material(other, "lopkhac", [("Khóa ngoại lớp khác", "Khóa ngoại của học liệu lớp khác.")])
    hits = _search(cs, "khóa ngoại tham chiếu")
    assert [(h.material_id, h.page_no, h.title) for h in hits] == [(a, 1, "Khóa ngoại")]
    h = hits[0]
    assert h.file_name == "test_search_chuong3.pdf" and h.bboxes == [[40, 80, 600, 200]] and h.score > 0
    assert {"khoaS", "ngoaiJ", "tham", "chiêuS"} <= set(h.matched)


def test_index_follows_reindex_and_exclusion(sections):
    cs, _ = sections
    a = _material(cs, "chuong4", [("Giao tác", "Giao tác bảo đảm tính nguyên tố.")])
    assert [h.material_id for h in _search(cs, "giao tác nguyên tố")] == [a]
    db = SessionLocal()                                        # GV sửa tệp → nạp lại: nội dung mới, indexed_at mới
    db.query(MaterialPassage).filter_by(material_id=a).update({"body": "Khóa chết (deadlock) giữa hai giao tác."})
    m = db.get(SectionMaterial, a)
    m.indexed_at = m.indexed_at + timedelta(seconds=5)
    db.commit()
    _warm(cs)
    assert [h.material_id for h in _search(cs, "khóa chết deadlock")] == [a]
    m = db.get(SectionMaterial, a)
    m.status = "excluded"                                      # GV bỏ chọn – CHƯA dựng lại chỉ mục
    db.commit()
    db.close()
    assert _search(cs, "khóa chết deadlock") == []            # bản cũ vẫn không trả đoạn của học liệu đã bỏ chọn


def test_stale_index_served_at_once_while_rebuilding_in_background(sections, monkeypatch):
    cs, _ = sections
    a = _material(cs, "chuong7", [("Phục hồi", "Nhật ký ghi trước (WAL) giúp phục hồi sau sự cố.")])
    db = SessionLocal()                                        # nạp lại ở worker KHÁC: chỉ mục ở đây chưa dựng lại
    db.query(MaterialPassage).filter_by(material_id=a).update({"body": "Điểm kiểm tra (checkpoint) rút ngắn phục hồi."})
    m = db.get(SectionMaterial, a)
    m.indexed_at = m.indexed_at + timedelta(seconds=5)
    db.commit()
    db.close()
    build = Index.build.__func__
    monkeypatch.setattr(Index, "build", classmethod(lambda cls, docs: (time.sleep(1), build(cls, docs))[1]))
    t = time.monotonic()
    assert [h.material_id for h in _search(cs, "nhật ký ghi trước WAL")] == [a]      # bản cũ, trả ngay
    assert _search(cs, "checkpoint") == [] and time.monotonic() - t < 1
    deadline = time.monotonic() + 10
    while not _search(cs, "checkpoint") and time.monotonic() < deadline:            # dựng xong ở nền → bản mới
        time.sleep(0.2)
    assert [h.material_id for h in _search(cs, "điểm kiểm tra checkpoint")] == [a]


def test_concurrent_requests_build_section_index_once(sections, monkeypatch):
    cs, _ = sections
    _material(cs, "chuong6", [("Sao lưu", "Sao lưu và phục hồi dữ liệu.")], warm=False)
    search._cache.pop(cs, None)                                # lớp chưa từng có chỉ mục: phải chờ dựng
    calls, build = [], Index.build.__func__

    def slow_build(cls, docs):
        calls.append(1)
        time.sleep(0.3)                                         # dựng chậm: các yêu cầu khác đến trong lúc dựng
        return build(cls, docs)
    monkeypatch.setattr(Index, "build", classmethod(slow_build))
    got = []

    def ask():
        db = SessionLocal()
        try:
            got.append(search.section_index(db, cs))
        finally:
            db.close()
    ts = [threading.Thread(target=ask) for _ in range(6)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(calls) == 1 and len(got) == 6 and all(ix is got[0] for ix in got)


def test_search_api_for_lecturer_of_the_section(client, gv, gv_other, sections):
    cs, _ = sections
    _material(cs, "chuong5", [("Chỉ mục", "Chỉ mục B-tree giúp tìm kiếm nhanh theo khóa.")])
    url = f"/api/class-sections/{cs}/materials/search"
    r = client.get(url, params={"q": "chỉ mục B-tree", "k": 3}, headers=gv)
    assert r.status_code == 200, r.text
    assert [(x["title"], x["page_no"], x["kind"]) for x in r.json()
            if x["file_name"].startswith("test_search_")] == [("Chỉ mục", 1, "text")]
    assert client.get(url, params={"q": "chỉ mục"}, headers=gv_other).status_code == 403
    assert client.get(url, params={"q": ""}, headers=gv).status_code == 422


def test_indexer_thread_builds_section_index_after_indexing(sections, monkeypatch):
    from app.services.rag import index
    cs, _ = sections
    _material(cs, "chuong8", [("Phân quyền", "GRANT cấp quyền cho người dùng.")], warm=False)
    search._cache.pop(cs, None)
    monkeypatch.setattr(index, "index_pending", lambda db, cs_id: {})   # tệp chờ đã nạp xong (không gọi Moodle)
    index.run_section(cs)
    db = SessionLocal()
    try:
        assert search._cached(cs, search._ready(db, cs)) is not None       # lần tìm sau không phải dựng
    finally:
        db.close()
