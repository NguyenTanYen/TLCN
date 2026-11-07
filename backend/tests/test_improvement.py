"""Vòng cải tiến: hành động có người phụ trách/hạn/trạng thái, kiểm chứng, quyền, so sánh CLO qua các học kỳ."""
from datetime import date, timedelta


def _section(client, gv):
    cs = next(s for s in client.get("/api/class-sections", headers=gv).json() if s["section_code"] == "DBMS330284_01")
    return cs


def test_hanh_dong_cai_tien_vong_doi(client, gv):
    cs = _section(client, gv)
    url = f"/api/class-sections/{cs['id']}/improvement-actions"
    clo = client.get(f"/api/class-sections/{cs['id']}/clo-results", headers=gv).json()["clos"][0]["clo_id"]
    past = (date.today() - timedelta(days=3)).isoformat()
    r = client.post(url, headers=gv, json={"description": "Bổ sung 2 buổi bài tập truy vấn lồng", "clo_id": clo, "owner": "ThS. Sơn", "due_date": past})
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    rows = client.get(url, headers=gv).json()
    a = next(x for x in rows if x["id"] == aid)
    assert a["status"] == "open" and a["overdue"] is True and a["clo_code"]
    # kiểm chứng phải có kết quả
    assert client.patch(f"/api/improvement-actions/{aid}", headers=gv, json={"status": "verified"}).status_code == 422
    assert client.patch(f"/api/improvement-actions/{aid}", headers=gv, json={"status": "bogus"}).status_code == 422
    assert client.patch(f"/api/improvement-actions/{aid}", headers=gv, json={"status": "done"}).status_code == 200
    assert client.patch(f"/api/improvement-actions/{aid}", headers=gv, json={"status": "verified", "result": "CLO2 tăng từ 55% lên 72%"}).status_code == 200
    a = next(x for x in client.get(url, headers=gv).json() if x["id"] == aid)
    assert a["status"] == "verified" and a["overdue"] is False and "72%" in a["result"]
    # CLO của môn khác bị từ chối
    assert client.post(url, headers=gv, json={"description": "Sai CLO", "clo_id": 10**6}).status_code == 422
    assert client.delete(f"/api/improvement-actions/{aid}", headers=gv).status_code == 200
    assert all(x["id"] != aid for x in client.get(url, headers=gv).json())


def test_giang_vien_khac_khong_sua_duoc(client, gv, gv_other):
    cs = _section(client, gv)
    url = f"/api/class-sections/{cs['id']}/improvement-actions"
    aid = client.post(url, headers=gv, json={"description": "Chỉ giảng viên phụ trách được sửa"}).json()["id"]
    assert client.get(url, headers=gv_other).status_code == 403
    assert client.post(url, headers=gv_other, json={"description": "xâm nhập"}).status_code == 403
    assert client.patch(f"/api/improvement-actions/{aid}", headers=gv_other, json={"status": "done"}).status_code == 403
    assert client.delete(f"/api/improvement-actions/{aid}", headers=gv_other).status_code == 403
    assert client.post(url, json={"description": "không đăng nhập"}).status_code in (401, 403)


def test_so_sanh_hai_hoc_ky(client, gv):
    """Dựng thêm một học kỳ cũ có kết quả CLO rồi kiểm tra chênh lệch và chiều hướng."""
    from sqlalchemy import text
    from app.database import SessionLocal
    cs = _section(client, gv)
    db = SessionLocal()
    try:
        row = db.execute(text("SELECT lecturer_id, course_id FROM class_sections WHERE id=:i"), {"i": cs["id"]}).mappings().first()
        db.execute(text("INSERT INTO semesters (academic_year, term, name, start_date, end_date) VALUES ('2019-2020', 1, 'HKI 19-20', '2019-09-01', '2020-01-15')"))
        sid = db.execute(text("SELECT id FROM semesters WHERE academic_year='2019-2020' AND term=1")).scalar()
        db.execute(text("INSERT INTO class_sections (course_id, semester_id, lecturer_id, section_code) VALUES (:c,:s,:l,'DBMS_OLD_01')"),
                   {"c": row["course_id"], "s": sid, "l": row["lecturer_id"]})
        old = db.execute(text("SELECT id FROM class_sections WHERE section_code='DBMS_OLD_01'")).scalar()
        clo = db.execute(text("SELECT clo_id FROM clo_results WHERE class_section_id=:i LIMIT 1"), {"i": cs["id"]}).scalar()
        db.execute(text("INSERT INTO clo_results (class_section_id, clo_id, n_evaluated, n_achieved, achieved_pct, target_pct, is_achieved) VALUES (:o,:c,40,20,50,70,0)"),
                   {"o": old, "c": clo})
        db.commit()
    finally:
        db.close()
    try:
        d = client.get(f"/api/courses/{cs['course_id']}/clo-trend", headers=gv).json()
        c = next(x for x in d["clos"] if x["clo_id"] == clo)
        assert c["points"][0]["semester"] == "HKI 19-20" and c["points"][0]["achieved_pct"] == 50.0 and c["points"][0]["is_achieved"] is False
        assert len(c["points"]) >= 2
        assert c["change"] == round(c["points"][-1]["achieved_pct"] - 50.0, 2)
        assert c["trend"] in ("up", "down", "flat")

    finally:
        db = SessionLocal()
        try:  # dọn dữ liệu dựng thêm để không ảnh hưởng các bài kiểm thử khác
            db.execute(text("DELETE FROM class_sections WHERE section_code='DBMS_OLD_01'"))
            db.execute(text("DELETE FROM semesters WHERE academic_year='2019-2020' AND term=1"))
            db.commit()
        finally:
            db.close()


def test_clo_qua_cac_hoc_ky(client, gv):
    cs = _section(client, gv)
    t = client.get(f"/api/courses/{cs['course_id']}/clo-trend", headers=gv)
    assert t.status_code == 200, t.text
    d = t.json()
    assert d["clos"], "phải có CLO đã đo"
    for c in d["clos"]:
        for p in c["points"]:
            assert 0 <= p["achieved_pct"] <= 100 and p["n_achieved"] <= p["n_evaluated"]
            assert p["is_achieved"] == (p["achieved_pct"] + 1e-9 >= p["target_pct"])
        if len(c["points"]) >= 2:
            assert c["change"] == round(c["points"][-1]["achieved_pct"] - c["points"][-2]["achieved_pct"], 2)
        else:
            assert c["change"] is None and c["trend"] is None


def test_canh_bao_mau_nho(client, gv):
    cs = _section(client, gv)
    ex = client.get(f"/api/class-sections/{cs['id']}/exams", headers=gv).json()
    e = next(x for x in ex if x["status"] == "Analyzed")
    o = client.get(f"/api/exams/{e['id']}/overview", headers=gv).json()
    assert "warnings" in o and isinstance(o["warnings"], list)
    assert bool(o["warnings"]) == (0 < o["n_students"] < 30)
