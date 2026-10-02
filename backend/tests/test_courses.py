"""UC-12: khai báo học phần mới – môn học, lớp HP, chương, CLO–PLO và bảng kiểm tra tình trạng."""
from sqlalchemy import text

from app.database import engine


def _ids():
    with engine.connect() as c:
        lec = c.execute(text("SELECT l.id FROM lecturers l JOIN users u ON u.id=l.user_id WHERE u.username='gv.son'")).scalar()
        sem = c.execute(text("SELECT MAX(id) FROM semesters")).scalar()
        plos = c.execute(text("SELECT id FROM plos ORDER BY id LIMIT 2")).scalars().all()
    return lec, sem, plos


def test_new_course_setup_flow(client, admin, gv, gv_other):
    lec, sem, plos = _ids()
    # 1. Bộ môn tạo môn học và lớp học phần
    assert client.post("/api/courses", headers=gv, json={"course_code": "TST9001", "course_name": "Môn thử", "credits": 3}).status_code == 403
    r = client.post("/api/courses", headers=admin, json={"course_code": "TST9001", "course_name": "Môn thử nghiệm", "credits": 3})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert client.post("/api/courses", headers=admin, json={"course_code": "TST9001", "course_name": "Trùng", "credits": 3}).status_code == 409
    assert client.get(f"/api/courses/{cid}/setup", headers=gv).status_code == 403          # GV chưa phụ trách lớp nào của môn
    sec = {"course_id": cid, "semester_id": sem, "lecturer_id": lec, "section_code": "TST9001_01"}
    assert client.post("/api/class-sections", headers=gv, json=sec).status_code == 403
    r = client.post("/api/class-sections", headers=admin, json=sec)
    assert r.status_code == 201, r.text
    cs = r.json()["id"]
    assert client.post("/api/class-sections", headers=admin, json=sec).status_code == 409
    assert client.post("/api/class-sections", headers=admin, json={**sec, "lecturer_id": 999999, "section_code": "X_02"}).status_code == 422
    assert any(s["id"] == cs for s in client.get("/api/class-sections", headers=gv).json())
    st = client.get(f"/api/courses/{cid}/setup", headers=gv).json()
    assert [s["ok"] for s in st["steps"]] == [True, False, False, False, False] and not st["ready"]

    # 2. GV phụ trách khai báo chương; GV khác không được sửa
    o1 = client.post(f"/api/courses/{cid}/outlines", headers=gv, json={"chapter_number": 1, "chapter_name": "Tổng quan"})
    assert o1.status_code == 201
    o2 = client.post(f"/api/courses/{cid}/outlines", headers=gv, json={"chapter_number": 2, "chapter_name": "Nâng cao"}).json()["id"]
    assert client.post(f"/api/courses/{cid}/outlines", headers=gv, json={"chapter_number": 1, "chapter_name": "Trùng"}).status_code == 409
    assert client.put(f"/api/outlines/{o2}", headers=gv, json={"chapter_number": 1, "chapter_name": "x"}).status_code == 409
    assert client.put(f"/api/outlines/{o2}", headers=gv, json={"chapter_number": 2, "chapter_name": "Chuyên đề nâng cao"}).status_code == 200
    assert client.post(f"/api/courses/{cid}/outlines", headers=gv_other, json={"chapter_number": 3, "chapter_name": "x"}).status_code == 403

    # 3. CLO và ánh xạ PLO
    r = client.post("/api/clos", headers=gv, json={"course_id": cid, "clo_code": "CLO1", "description": "Trình bày được khái niệm",
                                                   "bloom_level_id": 2, "plos": []})
    clo1 = r.json()["id"]
    st = client.get(f"/api/courses/{cid}/setup", headers=gv).json()
    assert not st["steps"][2]["ok"] and "chưa ánh xạ PLO" in st["steps"][2]["detail"]
    bad = {"clo_code": "CLO1", "description": "Trình bày được khái niệm", "bloom_level_id": 2}
    assert client.put(f"/api/clos/{clo1}", headers=gv, json={**bad, "plos": [{"plo_id": plos[0]}, {"plo_id": plos[0]}]}).status_code == 422
    assert client.put(f"/api/clos/{clo1}", headers=gv, json={**bad, "plos": [{"plo_id": 999999}]}).status_code == 422
    assert client.put(f"/api/clos/{clo1}", headers=gv, json={**bad, "plos": [{"plo_id": plos[0], "level": "X"}]}).status_code == 422
    assert client.put(f"/api/clos/{clo1}", headers=gv, json={**bad, "plos": [{"plo_id": plos[0], "level": "I"}, {"plo_id": plos[1], "level": "M"}]}).status_code == 200
    assert client.put(f"/api/clos/{clo1}", headers=gv_other, json={**bad, "plos": []}).status_code == 403
    c = client.get(f"/api/courses/{cid}", headers=gv).json()
    assert {(p["plo_id"], p["level"]) for p in c["clos"][0]["plos"]} == {(plos[0], "I"), (plos[1], "M")}
    assert [o["chapter_name"] for o in c["outlines"]] == ["Tổng quan", "Chuyên đề nâng cao"]
    st = client.get(f"/api/courses/{cid}/setup", headers=gv).json()
    assert [s["ok"] for s in st["steps"][:3]] == [True, True, True] and not st["ready"]   # còn thiếu câu hỏi

    # 4. Câu hỏi dùng chương/CLO → không xóa được; sau khi có câu hỏi đã gán thì học phần sẵn sàng
    q = client.post("/api/questions", headers=gv, json={"course_id": cid, "outline_id": o2, "bloom_level_id": 2, "content": "Câu thử UC-12?",
                                                         "options": [{"content": "Đúng", "is_correct": True}, {"content": "Sai", "is_correct": False}],
                                                         "clos": [{"clo_id": clo1, "weight": 1}]})
    assert q.status_code in (200, 201), q.text
    assert client.delete(f"/api/outlines/{o2}", headers=gv).status_code == 409
    assert client.delete(f"/api/clos/{clo1}", headers=gv).status_code == 409
    st = client.get(f"/api/courses/{cid}/setup", headers=gv).json()
    assert st["ready"] and not st["steps"][3]["ok"]                                        # BM6a chưa lập: không chặn
    assert client.delete(f"/api/outlines/{o1.json()['id']}", headers=gv).status_code == 200

    # 5. Môn học: GV phụ trách sửa được; lớp HP chưa có bài kiểm tra thì Bộ môn sửa/xóa được
    assert client.put(f"/api/courses/{cid}", headers=gv, json={"clo_target_pct": 70}).status_code == 200
    assert client.put(f"/api/courses/{cid}", headers=gv_other, json={"clo_target_pct": 70}).status_code == 403
    assert client.put(f"/api/class-sections/{cs}", headers=admin, json={**sec, "section_code": "TST9001_02"}).status_code == 200
    assert client.delete("/api/class-sections/1", headers=admin).status_code == 409                # lớp demo đã có bài kiểm tra
    assert client.put("/api/class-sections/1", headers=admin,
                      json={**sec, "section_code": "DBMS330284_01"}).status_code == 409             # đổi môn khi đã có đề
    assert client.delete(f"/api/class-sections/{cs}", headers=gv).status_code == 403
    assert client.delete(f"/api/class-sections/{cs}", headers=admin).status_code == 200
    assert client.get("/api/courses/999999/setup", headers=admin).status_code == 404


def test_import_moodle_course(client, admin, gv, gv_other):
    """Khóa học mới tạo trên Moodle (gv.son là giảng viên) xuất hiện ở hệ thống và được đưa vào thành lớp HP kèm danh sách SV."""
    from app.config import settings
    from tests.test_hardening import ex
    M = settings.moodle_db_name
    _, sem, _ = _ids()
    ex(f"INSERT INTO `{M}`.mdl_course (id, category, fullname, shortname, idnumber, summary, startdate) VALUES (52, 1, 'Hệ QTCSDL – lớp 09', 'DBMS330284_09', '', '', UNIX_TIMESTAMP('2027-09-20'))")
    ex(f"INSERT INTO `{M}`.mdl_context (id, contextlevel, instanceid, path, depth) VALUES (72, 50, 52, '/1/72', 2)")
    ex(f"INSERT INTO `{M}`.mdl_role_assignments (id, roleid, contextid, userid) VALUES (9101, 3, 72, 99)")
    ex(f"INSERT INTO `{M}`.mdl_enrol (id, enrol, status, courseid) VALUES (62, 'manual', 0, 52)")
    ex(f"""INSERT INTO `{M}`.mdl_user (id, username, idnumber, firstname, lastname, email, deleted, description)
           VALUES (150, 'svmoi01', '23130999', 'Mới', 'Trần Văn', 'svmoi@x.vn', 0, '')""")
    for i, uid in enumerate((100, 101, 102, 150)):
        ex(f"INSERT INTO `{M}`.mdl_user_enrolments (id, status, enrolid, userid) VALUES ({9200 + i}, 0, 62, {uid})")
        ex(f"INSERT INTO `{M}`.mdl_role_assignments (id, roleid, contextid, userid) VALUES ({9110 + i}, 5, 72, {uid})")
    cs = None
    try:
        mine = {c["moodle_course_id"]: c for c in client.get("/api/moodle/my-courses", headers=gv).json()}
        c = mine[52]
        assert c["section"] is None and c["n_students"] == 4 and c["teachers"][0]["username"] == "gv.son"
        assert c["suggest"]["course_id"] == 5 and c["suggest"]["section_code"] == "DBMS330284_09"
        # khóa học bắt đầu 20/9/2027 – học kỳ chưa có: gợi ý tạo HKI 27-28
        assert c["suggest"]["semester_id"] is None and c["suggest"]["new_semester"] == {"academic_year": "2027-2028", "term": 1, "name": "HKI 27-28"}
        assert 52 not in {x["moodle_course_id"] for x in client.get("/api/moodle/my-courses", headers=gv_other).json()}
        assert 52 in {x["moodle_course_id"] for x in client.get("/api/moodle/my-courses", headers=admin).json()}
        body = {"course_id": 5, "semester_id": sem, "section_code": "DBMS330284_09"}
        assert client.post("/api/moodle/courses/52/import", headers=gv_other, json=body).status_code == 403   # không dạy khóa này
        assert client.post("/api/moodle/courses/52/import", headers=admin, json=body).status_code == 422      # Bộ môn phải chọn GV
        assert client.post("/api/moodle/courses/52/import", headers=gv, json={**body, "course_id": 999999}).status_code == 404
        assert client.post("/api/moodle/courses/424242/import", headers=gv, json=body).status_code == 404
        assert client.post("/api/moodle/courses/52/import", headers=gv, json={**body, "semester_id": None}).status_code == 422
        r = client.post("/api/moodle/courses/52/import", headers=gv,
                        json={**body, "semester_id": None, "new_semester": {"academic_year": "2027-2028", "term": 1}})
        assert r.status_code == 201, r.text
        cs = r.json()["id"]
        with engine.connect() as con:
            assert con.execute(text("SELECT s.name FROM class_sections cs JOIN semesters s ON s.id=cs.semester_id WHERE cs.id=:c"),
                               {"c": cs}).scalar() == "HKI 27-28"
        assert r.json()["n_students"] == 4
        assert client.post("/api/moodle/courses/52/import", headers=gv, json={**body, "section_code": "X_10"}).status_code == 409
        s = next(x for x in client.get("/api/class-sections", headers=gv).json() if x["id"] == cs)
        assert s["moodle_course_id"] == 52 and s["n_students"] == 4 and s["lecturer"] == "Nguyễn Thành Sơn"
        with engine.connect() as con:
            assert con.execute(text("SELECT full_name FROM students WHERE student_code='23130999'")).scalar() == "Trần Văn Mới"
        assert client.get("/api/moodle/my-courses", headers=gv).json() and \
            next(x for x in client.get("/api/moodle/my-courses", headers=gv).json() if x["moodle_course_id"] == 52)["section"]["id"] == cs
        # SV ghi danh thêm trên Moodle → cập nhật danh sách lớp
        ex(f"INSERT INTO `{M}`.mdl_user_enrolments (id, status, enrolid, userid) VALUES (9210, 0, 62, 103)")
        ex(f"INSERT INTO `{M}`.mdl_role_assignments (id, roleid, contextid, userid) VALUES (9120, 5, 72, 103)")
        r = client.post(f"/api/class-sections/{cs}/moodle-roster", headers=gv).json()
        assert r == {"added": 1, "n_students": 5}
        assert client.post(f"/api/class-sections/{cs}/moodle-roster", headers=gv_other).status_code == 403
    finally:
        if cs:
            client.delete(f"/api/class-sections/{cs}", headers=admin)
        ex("DELETE FROM students WHERE student_code='23130999'")
        ex("DELETE FROM semesters WHERE academic_year='2027-2028'")
        ex(f"DELETE FROM `{M}`.mdl_role_assignments WHERE id BETWEEN 9101 AND 9120")
        ex(f"DELETE FROM `{M}`.mdl_user_enrolments WHERE id BETWEEN 9200 AND 9210")
        ex(f"DELETE FROM `{M}`.mdl_enrol WHERE id=62")
        ex(f"DELETE FROM `{M}`.mdl_user WHERE id=150")
        ex(f"DELETE FROM `{M}`.mdl_context WHERE id=72")
        ex(f"DELETE FROM `{M}`.mdl_course WHERE id=52")
