"""Đề của môn: tạo bài kiểm tra ở trang môn học (chưa gắn lớp HP), khi xuất mới chọn giao cho lớp học phần nào."""
from sqlalchemy import text

from app.database import engine


def _course(client, gv):
    cs = [s for s in client.get("/api/class-sections", headers=gv).json() if s["section_code"] == "DBMS330284_01"][0]
    return cs["course_id"]


def _sections(client, gv, course_id):
    return {s["section_code"]: s["id"] for s in client.get("/api/class-sections", headers=gv).json() if s["course_id"] == course_id}


def test_course_exam_create_and_blocked_actions(client, gv, gv_other):
    c = _course(client, gv)
    # ma trận đề và sinh đề ở cấp môn
    pool = client.get(f"/api/courses/{c}/exam-blueprint/pool", headers=gv)
    assert pool.status_code == 200 and pool.json()["pool_size"] > 0
    gen = client.post(f"/api/courses/{c}/exam-blueprint", headers=gv, json={"n_questions": 10, "total_points": 10, "bloom_preset": "balanced"})
    assert gen.status_code == 200, gen.text
    items = gen.json()["items"]
    assert len(items) == 10
    r = client.post("/api/exams", headers=gv, json={"course_id": c, "exam_title": "Giữa kỳ – đề của môn", "exam_type": "online",
                                                    "assessment_type": "process", "duration_minutes": 30, "items": items})
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["is_template"] and e["class_section_id"] is None and e["course_id"] == c and e["deployments"] == []
    # xuất hiện ở danh sách đề của môn, kèm các lớp của GV để giao
    lst = client.get(f"/api/courses/{c}/exams", headers=gv).json()
    assert any(x["id"] == e["id"] for x in lst["exams"])
    assert {s["section_code"] for s in lst["sections"]} >= {"DBMS330284_01", "DBMS330284_02"}
    # thao tác cần lớp bị chặn với thông báo hướng dẫn chọn lớp; Moodle XML vẫn tải được
    for method, url, body in (("post", f"/api/exams/{e['id']}/moodle/create-quiz", {}), ("post", f"/api/exams/{e['id']}/sync", None),
                              ("get", f"/api/exams/{e['id']}/timing", None), ("get", f"/api/exams/{e['id']}/overview", None)):
        res = getattr(client, method)(url, headers=gv, **({"json": body} if body is not None else {}))
        assert res.status_code == 409 and "chưa giao cho lớp" in res.json()["detail"], (url, res.text)
    assert client.get(f"/api/exams/{e['id']}/moodle-xml", headers=gv).status_code == 200
    assert client.get(f"/api/exams/{e['id']}", headers=gv).json()["status"] == "Draft"
    # GV không dạy môn: không thấy, không tạo được
    assert client.get(f"/api/exams/{e['id']}", headers=gv_other).status_code == 403
    assert client.get(f"/api/courses/{c}/exams", headers=gv_other).status_code == 403
    assert client.post("/api/exams", headers=gv_other, json={"course_id": c, "exam_title": "Không được", "items": items[:1]}).status_code == 403
    # phải chọn đúng một trong lớp HP / môn học
    sec = _sections(client, gv, c)["DBMS330284_01"]
    assert client.post("/api/exams", headers=gv, json={"course_id": c, "class_section_id": sec, "exam_title": "Cả hai", "items": items[:1]}).status_code == 422
    assert client.post("/api/exams", headers=gv, json={"exam_title": "Không có", "items": items[:1]}).status_code == 422


def test_course_exam_deploy_to_sections(client, gv):
    c = _course(client, gv)
    secs = _sections(client, gv, c)
    tpl = client.post("/api/exams", headers=gv, json={"course_id": c, "exam_title": "Cuối kỳ – đề chung", "exam_type": "paper",
                                                      "items": [{"question_id": q, "points": 1} for q in range(1, 9)]}).json()
    r = client.post(f"/api/exams/{tpl['id']}/copy", headers=gv, json={"class_section_ids": [secs["DBMS330284_01"], secs["DBMS330284_02"]], "create_moodle": False})
    assert r.status_code == 200, r.text
    copies = {x["section_code"]: x for x in r.json()["copies"]}
    assert set(copies) == {"DBMS330284_01", "DBMS330284_02"} and not any(x.get("skipped") for x in copies.values())
    for code, x in copies.items():
        b = client.get(f"/api/exams/{x['exam_id']}", headers=gv).json()
        assert b["section_code"] == code and b["source_exam_id"] == tpl["id"] and not b["is_template"]
        assert [q["question_id"] for q in b["questions"]] == list(range(1, 9)) and b["exam_type"] == "paper"
    # bài của lớp làm được các thao tác cần lớp (VD sinh mã đề giấy)
    v = client.post(f"/api/exams/{copies['DBMS330284_02']['exam_id']}/paper/versions", headers=gv, json={"n_versions": 2})
    assert v.status_code in (200, 201), v.text
    # giao lại cho lớp đã có: bỏ qua, không tạo bài trùng
    again = client.post(f"/api/exams/{tpl['id']}/copy", headers=gv, json={"class_section_ids": [secs["DBMS330284_01"]], "create_moodle": False}).json()
    assert again["copies"][0]["skipped"] and again["copies"][0]["exam_id"] == copies["DBMS330284_01"]["exam_id"]
    deps = client.get(f"/api/exams/{tpl['id']}", headers=gv).json()["deployments"]
    assert {d["section_code"] for d in deps} == {"DBMS330284_01", "DBMS330284_02"}
    # xóa đề của môn: bài đã giao vẫn còn (source_exam_id về NULL)
    assert client.delete(f"/api/exams/{tpl['id']}", headers=gv).status_code == 200
    b = client.get(f"/api/exams/{copies['DBMS330284_01']['exam_id']}", headers=gv).json()
    assert b["source_exam_id"] is None
    client.delete(f"/api/exams/{copies['DBMS330284_02']['exam_id']}/paper/versions", headers=gv)
    for x in copies.values():
        assert client.delete(f"/api/exams/{x['exam_id']}", headers=gv).status_code == 200


def test_course_manual_exam_deploy_and_grade(client, gv):
    c = _course(client, gv)
    secs = _sections(client, gv, c)
    clos = client.get(f"/api/courses/{c}", headers=gv).json()["clos"]
    body = {"exam_title": "Bài tập lớn – đề của môn", "assessment_type": "process", "max_score": 10,
            "items": [{"title": "Thiết kế CSDL", "points": 4, "clos": [{"clo_id": clos[0]["id"], "weight": 1}]},
                      {"title": "Cài đặt thủ tục", "points": 6, "clos": [{"clo_id": clos[1]["id"], "weight": 1}]}]}
    r = client.post(f"/api/courses/{c}/manual-exams", headers=gv, json=body)
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    t = client.get(f"/api/exams/{tid}", headers=gv).json()
    assert t["is_template"] and t["exam_type"] == "manual" and len(t["questions"]) == 2
    assert client.get(f"/api/exams/{tid}/grades", headers=gv).status_code == 409        # nhập điểm cần lớp
    d = client.post(f"/api/exams/{tid}/copy", headers=gv, json={"class_section_ids": [secs["DBMS330284_02"]]}).json()["copies"][0]
    g = client.get(f"/api/exams/{d['exam_id']}/grades", headers=gv)
    assert g.status_code == 200 and len(g.json()["students"]) == 35
    st = g.json()["students"][0]["student_id"]
    keys = [str(i["question_id"]) for i in g.json()["items"]]
    s = client.put(f"/api/exams/{d['exam_id']}/grades", headers=gv, json={"rows": [{"student_id": st, "scores": {keys[0]: 3, keys[1]: 5}}], "analyze": False})
    assert s.status_code == 200, s.text
    with engine.connect() as cn:
        assert cn.execute(text("SELECT class_section_id, source_exam_id FROM exams WHERE id=:e"), {"e": d["exam_id"]}).one() == (secs["DBMS330284_02"], tid)
    with engine.begin() as cn:   # dọn bài vừa thử để không ảnh hưởng các kiểm thử sau
        cn.execute(text("DELETE r FROM item_level_results r JOIN exam_attempts a ON a.id=r.attempt_id WHERE a.exam_id=:e"), {"e": d["exam_id"]})
        cn.execute(text("DELETE FROM exam_attempts WHERE exam_id=:e"), {"e": d["exam_id"]})
    assert client.delete(f"/api/exams/{d['exam_id']}", headers=gv).status_code == 200
    assert client.delete(f"/api/exams/{tid}", headers=gv).status_code == 200
