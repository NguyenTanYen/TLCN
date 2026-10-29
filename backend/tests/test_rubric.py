"""Rubric chấm điểm: tiêu chí × mức, gắn CLO, chấm sinh viên theo mức, điểm vào phân tích CLO như bài nhập điểm."""
import pytest

LEVELS = [{"label": "Tốt", "score_pct": 100}, {"label": "Khá", "score_pct": 75}, {"label": "Đạt", "score_pct": 50}, {"label": "Chưa đạt", "score_pct": 0}]


@pytest.fixture(scope="module")
def ctx(client, gv):
    cs = next(s for s in client.get("/api/class-sections", headers=gv).json() if s["section_code"] == "DBMS330284_01")
    clos = client.get(f"/api/class-sections/{cs['id']}/clo-results", headers=gv).json()["clos"]
    return {"cs": cs, "clos": [c["clo_id"] for c in clos]}


def _body(ctx, name="Rubric báo cáo đồ án"):
    return {"name": name, "description": "Chấm báo cáo", "criteria": [
        {"name": "Nội dung chuyên môn", "points": 6, "clo_id": ctx["clos"][0], "levels": LEVELS},
        {"name": "Trình bày và vấn đáp", "points": 4, "clo_id": ctx["clos"][1], "levels": LEVELS}]}


def test_tao_rubric_va_kiem_tra_du_lieu(client, gv, ctx):
    cid = ctx["cs"]["course_id"]
    bad = _body(ctx); bad["criteria"][0]["levels"] = [{"label": "A", "score_pct": 80}, {"label": "B", "score_pct": 40}]
    assert client.post(f"/api/courses/{cid}/rubrics", headers=gv, json=bad).status_code == 422          # không có mức 100%
    bad = _body(ctx); bad["criteria"][0]["levels"] = [{"label": "A", "score_pct": 100}, {"label": "B", "score_pct": 100}]
    assert client.post(f"/api/courses/{cid}/rubrics", headers=gv, json=bad).status_code == 422          # trùng tỷ lệ
    bad = _body(ctx); bad["criteria"][0]["clo_id"] = 10**6
    assert client.post(f"/api/courses/{cid}/rubrics", headers=gv, json=bad).status_code == 422          # CLO sai môn
    r = client.post(f"/api/courses/{cid}/rubrics", headers=gv, json=_body(ctx))
    assert r.status_code == 201, r.text
    d = client.get(f"/api/rubrics/{r.json()['id']}", headers=gv).json()
    assert d["total_points"] == 10 and d["in_use"] is False and [l["score_pct"] for l in d["criteria"][0]["levels"]] == [100, 75, 50, 0]
    ls = client.get(f"/api/courses/{cid}/rubrics", headers=gv).json()
    assert any(x["id"] == d["id"] and x["n_criteria"] == 2 for x in ls)


def test_cham_theo_rubric_ra_clo(client, gv, gv_other, ctx):
    cs, cid = ctx["cs"], ctx["cs"]["course_id"]
    rid = client.post(f"/api/courses/{cid}/rubrics", headers=gv, json=_body(ctx, "Rubric chấm thử")).json()["id"]
    assert client.post(f"/api/class-sections/{cs['id']}/rubric-exams", headers=gv_other,
                       json={"rubric_id": rid, "exam_title": "Không được"}).status_code == 403
    r = client.post(f"/api/class-sections/{cs['id']}/rubric-exams", headers=gv,
                    json={"rubric_id": rid, "exam_title": "Báo cáo đồ án (rubric)", "assessment_type": "process", "max_score": 10})
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    g = client.get(f"/api/exams/{eid}/rubric-grid", headers=gv).json()
    c1, c2 = g["rubric"]["criteria"]
    lv = lambda c, label: next(l["id"] for l in c["levels"] if l["label"] == label)
    s1, s2, s3 = (s["student_id"] for s in g["students"][:3])
    rows = [{"student_id": s1, "levels": {c1["id"]: lv(c1, "Tốt"), c2["id"]: lv(c2, "Tốt")}},          # 6 + 4 = 10
            {"student_id": s2, "levels": {c1["id"]: lv(c1, "Khá"), c2["id"]: lv(c2, "Đạt")}},          # 4,5 + 2 = 6,5
            {"student_id": s3, "levels": {c1["id"]: lv(c1, "Chưa đạt"), c2["id"]: lv(c2, "Chưa đạt")}}]  # 0
    # chấm thiếu tiêu chí bị từ chối
    assert client.put(f"/api/exams/{eid}/rubric-grades", headers=gv, json={"rows": [{"student_id": s1, "levels": {c1["id"]: lv(c1, "Tốt")}}]}).status_code == 422
    # mức không thuộc tiêu chí bị từ chối
    assert client.put(f"/api/exams/{eid}/rubric-grades", headers=gv,
                      json={"rows": [{"student_id": s1, "levels": {c1["id"]: lv(c2, "Tốt"), c2["id"]: lv(c2, "Tốt")}}]}).status_code == 422
    res = client.put(f"/api/exams/{eid}/rubric-grades", headers=gv, json={"rows": rows, "analyze": True})
    assert res.status_code == 200, res.text
    assert res.json()["saved"] == 3
    gb = client.get(f"/api/exams/{eid}/grades", headers=gv).json()
    tot = {s["student_id"]: s["total"] for s in gb["students"]}
    assert tot[s1] == 10 and tot[s2] == 6.5 and tot[s3] == 0
    # CLO của lớp: tiêu chí 1 đo CLO a, tiêu chí 2 đo CLO b → đạt khi ≥ 60% điểm của chính tiêu chí
    ev = client.get(f"/api/class-sections/{cs['id']}/clo-results/{ctx['clos'][0]}/evidence", headers=gv).json()["evidence"]
    mine = {e["student_code"]: e for e in ev if e["exam_title"] == "Báo cáo đồ án (rubric)"}
    assert len(mine) == 3
    pct = sorted(e["score_pct"] for e in mine.values())
    assert pct == [0.0, 75.0, 100.0]
    # lưu lại mức đã chọn
    g2 = client.get(f"/api/exams/{eid}/rubric-grid", headers=gv).json()
    assert g2["students"][0]["levels"][str(c1["id"])] == lv(c1, "Tốt")
    # đã dùng: không sửa/xóa rubric, không nhập điểm trực tiếp
    assert client.put(f"/api/rubrics/{rid}", headers=gv, json=_body(ctx)).status_code == 409
    assert client.delete(f"/api/rubrics/{rid}", headers=gv).status_code == 409
    assert client.put(f"/api/exams/{eid}/grades", headers=gv, json={"rows": []}).status_code == 409
    # nhân bản rồi sửa được
    new = client.post(f"/api/rubrics/{rid}/duplicate", headers=gv).json()["id"]
    assert client.put(f"/api/rubrics/{new}", headers=gv, json=_body(ctx, "Bản sao đã sửa")).status_code == 200
    assert client.delete(f"/api/rubrics/{new}", headers=gv).status_code == 200


def test_cham_vang(client, gv, ctx):
    cs, cid = ctx["cs"], ctx["cs"]["course_id"]
    rid = client.post(f"/api/courses/{cid}/rubrics", headers=gv, json=_body(ctx, "Rubric vắng")).json()["id"]
    eid = client.post(f"/api/class-sections/{cs['id']}/rubric-exams", headers=gv, json={"rubric_id": rid, "exam_title": "Bài vắng thử"}).json()["id"]
    g = client.get(f"/api/exams/{eid}/rubric-grid", headers=gv).json()
    sid = g["students"][0]["student_id"]
    r = client.put(f"/api/exams/{eid}/rubric-grades", headers=gv, json={"rows": [{"student_id": sid, "absent": True}]})
    assert r.status_code == 200 and r.json()["absent"] == 1
