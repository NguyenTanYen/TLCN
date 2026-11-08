"""Học liệu lớp học phần lấy TỰ ĐỘNG từ khóa học Moodle của lớp (dữ liệu mô phỏng: cli._simulate_materials, course 50)."""
import time

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.rag import index, moodle_files

SLIDE = {"cmid": 800, "content_hash": "01" + "ab" * 19}
REVIEW = {"cmid": 801, "content_hash": "02" + "ab" * 19}
HIDDEN = {"cmid": 802, "content_hash": "03" + "ab" * 19}
BOOK = {"cmid": 810, "content_hash": "04" + "ab" * 19}
WORD = {"cmid": 810, "content_hash": "05" + "ab" * 19}
ANSWER = {"cmid": 803, "content_hash": "06" + "ab" * 19}
EXTRA = {"cmid": 805, "content_hash": "08" + "ab" * 19}


@pytest.fixture(scope="module")
def cs_id():
    db = SessionLocal()
    cid = db.execute(text("SELECT id FROM class_sections WHERE moodle_course_id = 50")).scalar()
    db.close()
    assert cid, "lớp học phần của bài online phải được cầu nối gắn với khóa học Moodle 50"
    yield cid
    db = SessionLocal()
    db.execute(text("DELETE FROM section_materials WHERE class_section_id = :c"), {"c": cid})
    db.commit()
    db.close()


@pytest.fixture(autouse=True)
def no_background_indexing(monkeypatch):
    """Tệp này kiểm logic ĐỒNG BỘ; việc tải + nạp ở nền (gọi Moodle thật) kiểm ở test_rag_index."""
    monkeypatch.setattr(index, "enqueue", lambda *a, **k: None)


def _url(cs):
    return f"/api/class-sections/{cs}/materials"


def _materials(client, gv, cs):
    return {m["file_name"]: m for m in client.get(_url(cs), headers=gv).json()["materials"]}


def _moodle(sql: str, **params) -> None:
    """Giả lập GV thao tác trên Moodle (CSDL Moodle mô phỏng)."""
    db = SessionLocal()
    db.execute(text(sql.format(files=moodle_files._t("files"), cm=moodle_files._t("course_modules"),
                               resource=moodle_files._t("resource"))), params)
    db.commit()
    db.close()


def test_lists_only_files_students_can_open(client, gv, cs_id):
    r = client.get(_url(cs_id), headers=gv)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["moodle_course_id"] == 50
    files = d["moodle_files"]
    assert [f["file_name"] for f in files] == ["slide_ch1.pdf", "slide_ch2.pdf", "giao_trinh csdl.pdf",
                                               "bai_tap_ch1.docx", "de_on_tap_giua_ky.pdf"]
    slide, slide2, book, word, review = files
    assert (slide["section"], slide["activity"], slide["supported"]) == ("Chương 1. Tổng quan",
                                                                         "Slide Chương 1 - Tổng quan CSDL", True)
    assert review["section"] == "Kiểm tra" and word["supported"] is False and word["path"] == "/bai_tap/"
    assert slide["url"].endswith("/pluginfile.php/1800/mod_resource/content/3/slide_ch1.pdf")
    assert book["url"].endswith("/pluginfile.php/1810/mod_folder/content/2/giao_trinh%20csdl.pdf")
    assert word["url"].endswith("/pluginfile.php/1810/mod_folder/content/2/bai_tap/bai_tap_ch1.docx")


def test_sync_takes_every_visible_pdf_automatically_and_is_idempotent(client, gv, cs_id):
    r = client.post(_url(cs_id) + "/sync", headers=gv)
    assert r.status_code == 200, r.text
    assert sorted(r.json()["added"]) == ["de_on_tap_giua_ky.pdf", "giao_trinh csdl.pdf", "slide_ch1.pdf",
                                         "slide_ch2.pdf"]
    ms = _materials(client, gv, cs_id)
    assert {k: (m["status"], m["material_type"], m["title"]) for k, m in ms.items()} == {
        "slide_ch1.pdf": ("pending", "slide", "Slide Chương 1 - Tổng quan CSDL"),
        "slide_ch2.pdf": ("pending", "slide", "Slide Chương 2 - Mô hình quan hệ"),
        "de_on_tap_giua_ky.pdf": ("pending", "slide", "Đề ôn tập giữa kỳ"),
        "giao_trinh csdl.pdf": ("pending", "reference", "giao_trinh csdl.pdf")}
    again = client.post(_url(cs_id) + "/sync", headers=gv).json()
    assert all(v == [] for v in again.values())


def test_excluded_file_is_not_taken_again_and_can_be_picked_back(client, gv, cs_id):
    client.post(_url(cs_id) + "/sync", headers=gv)
    mid = _materials(client, gv, cs_id)["de_on_tap_giua_ky.pdf"]["id"]
    assert client.delete(f"{_url(cs_id)}/{mid}", headers=gv).json() == {"excluded": mid}
    assert client.post(_url(cs_id) + "/sync", headers=gv).json()["added"] == []
    assert _materials(client, gv, cs_id)["de_on_tap_giua_ky.pdf"]["status"] == "excluded"
    r = client.post(_url(cs_id) + "/moodle", headers=gv, json=REVIEW)
    assert r.status_code == 201 and r.json()["status"] == "pending" and r.json()["id"] == mid
    assert client.post(_url(cs_id) + "/moodle", headers=gv, json=REVIEW).status_code == 409


def test_new_version_of_file_replaces_old_one(client, gv, cs_id):
    client.post(_url(cs_id) + "/sync", headers=gv)
    _moodle("UPDATE {files} SET contenthash=:h WHERE contextid=1800 AND filename='slide_ch1.pdf'", h="99" + "cd" * 19)
    try:
        r = client.post(_url(cs_id) + "/sync", headers=gv).json()
        assert (r["added"], r["replaced"]) == (["slide_ch1.pdf"], ["slide_ch1.pdf"])
        assert _materials(client, gv, cs_id)["slide_ch1.pdf"]["content_hash"] == "99" + "cd" * 19
    finally:
        _moodle("UPDATE {files} SET contenthash=:h WHERE contextid=1800 AND filename='slide_ch1.pdf'",
                h=SLIDE["content_hash"])
        client.post(_url(cs_id) + "/sync", headers=gv)


def test_new_version_of_excluded_single_file_stays_excluded(client, gv, cs_id):
    client.post(_url(cs_id) + "/sync", headers=gv)
    m = _materials(client, gv, cs_id)["de_on_tap_giua_ky.pdf"]
    if m["status"] != "excluded":
        client.delete(f"{_url(cs_id)}/{m['id']}", headers=gv)
    _moodle("UPDATE {files} SET contenthash=:h WHERE contextid=1801", h="98" + "cd" * 19)
    try:
        assert client.post(_url(cs_id) + "/sync", headers=gv).json()["added"] == []
    finally:
        _moodle("UPDATE {files} SET contenthash=:h WHERE contextid=1801", h=REVIEW["content_hash"])


def test_hidden_or_deleted_file_becomes_missing_and_comes_back(client, gv, cs_id):
    client.post(_url(cs_id) + "/sync", headers=gv)
    _moodle("UPDATE {cm} SET visible=0 WHERE id=804")
    try:
        r = client.post(_url(cs_id) + "/sync", headers=gv).json()
        assert r["missing"] == ["slide_ch2.pdf"]
        assert _materials(client, gv, cs_id)["slide_ch2.pdf"]["status"] == "missing"
    finally:
        _moodle("UPDATE {cm} SET visible=1 WHERE id=804")
    r = client.post(_url(cs_id) + "/sync", headers=gv).json()
    assert r["restored"] == ["slide_ch2.pdf"]
    assert _materials(client, gv, cs_id)["slide_ch2.pdf"]["status"] == "pending"


def test_rename_updates_file_name_link_and_title_unless_custom(client, gv, cs_id):
    client.post(_url(cs_id) + "/sync", headers=gv)
    _moodle("UPDATE {files} SET filename='slide_chuong_1.pdf' WHERE contextid=1800 AND filename='slide_ch1.pdf'")
    _moodle("UPDATE {resource} SET name='Chương 1 - Tổng quan' WHERE id=300")
    try:
        r = client.post(_url(cs_id) + "/sync", headers=gv).json()
        assert r["updated"] == ["slide_chuong_1.pdf"] and r["added"] == []
        m = _materials(client, gv, cs_id)["slide_chuong_1.pdf"]
        assert m["moodle_file_url"].endswith("/mod_resource/content/3/slide_chuong_1.pdf")
        assert m["title"] == "Chương 1 - Tổng quan"
        r = client.patch(f"{_url(cs_id)}/{m['id']}", headers=gv, json={"title": "Slide bài 1", "material_type": "reference"})
        assert r.status_code == 200 and (r.json()["title"], r.json()["title_custom"], r.json()["material_type"]) == (
            "Slide bài 1", True, "reference")
        _moodle("UPDATE {resource} SET name='Chương 1 (bản 2)' WHERE id=300")
        client.post(_url(cs_id) + "/sync", headers=gv)
        assert _materials(client, gv, cs_id)["slide_chuong_1.pdf"]["title"] == "Slide bài 1"
    finally:
        _moodle("UPDATE {files} SET filename='slide_ch1.pdf' WHERE contextid=1800 AND filename='slide_chuong_1.pdf'")
        _moodle("UPDATE {resource} SET name='Slide Chương 1 - Tổng quan CSDL' WHERE id=300")
        client.post(_url(cs_id) + "/sync", headers=gv)


@pytest.mark.parametrize("body, status", [(WORD, 422),
                                          (HIDDEN, 404),
                                          (ANSWER, 404),
                                          (EXTRA, 404),
                                          ({**SLIDE, "cmid": 801}, 404),
                                          ({"cmid": 800, "content_hash": "x"}, 422)])
def test_pick_rejects_unsupported_hidden_restricted_or_foreign_files(client, gv, cs_id, body, status):
    assert client.post(_url(cs_id) + "/moodle", headers=gv, json=body).status_code == status


def test_permissions(client, gv, gv_other, admin, cs_id):
    assert client.get(_url(cs_id), headers=admin).status_code == 200
    assert client.post(_url(cs_id) + "/sync", headers=admin).status_code == 403
    assert client.post(_url(cs_id) + "/moodle", headers=admin, json=SLIDE).status_code == 403
    assert client.patch(f"{_url(cs_id)}/1", headers=admin, json={"title": "x"}).status_code == 403
    assert client.get(_url(cs_id), headers=gv_other).status_code == 403
    assert client.post(_url(cs_id) + "/sync", headers=gv_other).status_code == 403
    assert client.delete(f"{_url(cs_id)}/999999", headers=gv).status_code == 404
    assert client.patch(f"{_url(cs_id)}/999999", headers=gv, json={"title": "x"}).status_code == 404
    assert client.patch(f"{_url(cs_id)}/999999", headers=gv, json={}).status_code == 422


def test_pdf_detected_by_extension_when_moodle_mimetype_is_wrong():
    assert moodle_files.supported("application/octet-stream", "Slide_Chuong2.PDF")
    assert moodle_files.supported("application/pdf", "khong_duoi")
    assert not moodle_files.supported("application/octet-stream", "bai_tap.docx")


def test_availability_tree_evaluation():
    now = time.time()
    past, future = int(now) - 3600, int(now) + 3600
    date = lambda d, t: {"type": "date", "d": d, "t": t}                                  # noqa: E731
    tree = lambda op, *c: __import__("json").dumps({"op": op, "c": list(c), "showc": [True] * len(c)})  # noqa: E731
    ok = moodle_files.available_now
    assert ok(None) and ok("") and ok(tree("&"))
    assert ok(tree("&", date(">=", past)), now)
    assert not ok(tree("&", date(">=", future)), now)
    assert ok(tree("&", date(">=", past), date("<", future)), now)
    assert not ok(tree("&", date("<", past)), now)
    assert not ok(tree("&", {"type": "completion", "cm": 1, "e": 1}), now)
    assert ok(tree("|", {"type": "grade", "id": 1}, date(">=", past)), now)
    assert not ok(tree("!&", date(">=", past)), now)
    assert not ok("{hỏng", now)
    nested = '{"op":"&","c":[{"op":"|","c":[{"type":"date","d":">=","t":%d}]}]}' % past
    assert ok(nested, now)


def test_new_content_and_new_name_in_same_file_activity_is_a_replacement(client, gv, cs_id):
    """Kịch bản reviewer: GV tải bản PDF sửa lỗi (nội dung khác) VÀ đổi tên tệp trong cùng hoạt động File → vẫn là THAY THẾ (bản cũ bị bỏ, liên kết mới đúng), không có bản cũ 'missing' treo lại."""
    client.post(_url(cs_id) + "/sync", headers=gv)
    _moodle("UPDATE {files} SET contenthash=:h, filename='slide_ch1_sua_loi.pdf' WHERE contextid=1800 "
            "AND filename='slide_ch1.pdf'", h="97" + "cd" * 19)
    try:
        r = client.post(_url(cs_id) + "/sync", headers=gv).json()
        assert (r["added"], r["replaced"], r["missing"]) == (["slide_ch1_sua_loi.pdf"], ["slide_ch1.pdf"], [])
        ms = _materials(client, gv, cs_id)
        assert "slide_ch1.pdf" not in ms
        assert ms["slide_ch1_sua_loi.pdf"]["moodle_file_url"].endswith("/content/3/slide_ch1_sua_loi.pdf")
    finally:
        _moodle("UPDATE {files} SET contenthash=:h, filename='slide_ch1.pdf' WHERE contextid=1800 "
                "AND filename='slide_ch1_sua_loi.pdf'", h=SLIDE["content_hash"])
        client.post(_url(cs_id) + "/sync", headers=gv)
