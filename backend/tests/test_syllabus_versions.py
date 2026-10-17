"""Góp ý F1: đề cương chi tiết có phiên bản – Bộ môn soạn bản nháp, kiểm tra, duyệt; GV chỉ xem bản đang áp dụng."""
from sqlalchemy import text

from app.database import engine


def _demo_course():
    with engine.connect() as c:
        return c.execute(text("SELECT id FROM courses WHERE course_code='DBMS330284'")).scalar()


def test_demo_syllabus_approved(client, gv):
    cid = _demo_course()
    s = client.get(f"/api/courses/{cid}/syllabus", headers=gv).json()
    assert s["doc"]["version_no"] == 1 and s["doc"]["status"] == "approved" and s["approved_version"] == 1
    assert sum(a["weight_pct"] for a in s["doc"]["assessments"]) == 100
    assert any(r["ref_type"] == "main" for r in s["doc"]["references"])
    assert all(o["clos"] and o["theory_hours"] is not None for o in s["outlines"])
    assert all(k["ok"] for k in s["checks"] if k["required"])
    st = client.get(f"/api/courses/{cid}/setup", headers=gv).json()
    assert next(x for x in st["steps"] if x["key"] == "syllabus")["ok"]


def test_syllabus_version_flow(client, admin, gv):
    cid = _demo_course()
    # bản đã duyệt không sửa trực tiếp; GV không soạn được
    assert client.put(f"/api/courses/{cid}/syllabus", headers=admin, json={"objectives": "x"}).status_code == 409
    assert client.post(f"/api/courses/{cid}/syllabus/versions", headers=gv).status_code == 403
    r = client.post(f"/api/courses/{cid}/syllabus/versions", headers=admin)
    assert r.status_code == 201 and r.json()["version_no"] == 2
    assert client.post(f"/api/courses/{cid}/syllabus/versions", headers=admin).status_code == 409      # đã có bản nháp

    # bản nháp chép nội dung bản 1; Bộ môn xem bản nháp, GV vẫn xem bản đang áp dụng
    a = client.get(f"/api/courses/{cid}/syllabus", headers=admin).json()
    assert a["doc"]["version_no"] == 2 and a["doc"]["status"] == "draft" and len(a["doc"]["assessments"]) == 3
    assert client.get(f"/api/courses/{cid}/syllabus", headers=gv).json()["doc"]["version_no"] == 1
    assert client.get(f"/api/courses/{cid}/syllabus?version=2", headers=gv).json()["doc"]["status"] == "draft"
    assert client.get(f"/api/courses/{cid}/syllabus?version=9", headers=gv).status_code == 404

    clo = {c["clo_code"]: c["id"] for c in a["clos"]}
    body = {"assessments": [{"component_code": "a1", "name": "Giữa kỳ", "weight_pct": 40, "clo_ids": [clo["CLO1"], clo["CLO2"]]},
                            {"component_code": "A1", "name": "Trùng mã", "weight_pct": 60, "clo_ids": []}]}
    assert client.put(f"/api/courses/{cid}/syllabus", headers=admin, json=body).status_code == 422
    with engine.connect() as c:
        other = c.execute(text("SELECT id FROM clos WHERE course_id<>:c LIMIT 1"), {"c": cid}).scalar()
    if other:
        assert client.put(f"/api/courses/{cid}/syllabus", headers=admin, json={"assessments": [
            {"component_code": "A1", "name": "Giữa kỳ", "weight_pct": 100, "clo_ids": [other]}]}).status_code == 422
    # tổng tỷ trọng 90% và CLO4 chưa được đánh giá -> chưa duyệt được
    body = {"objectives": "Mục tiêu bản 2", "assessments": [
        {"component_code": "A1", "name": "Giữa kỳ", "weight_pct": 40, "clo_ids": [clo["CLO1"], clo["CLO2"]]},
        {"component_code": "A2", "name": "Cuối kỳ", "weight_pct": 50, "clo_ids": [clo["CLO3"]]}]}
    assert client.put(f"/api/courses/{cid}/syllabus", headers=admin, json=body).status_code == 200
    r = client.post(f"/api/courses/{cid}/syllabus/approve", headers=admin)
    assert r.status_code == 422 and "100%" in r.json()["detail"] and "CLO4" in r.json()["detail"]
    body["assessments"][1].update(weight_pct=60, clo_ids=[clo["CLO3"], clo["CLO4"]])
    assert client.put(f"/api/courses/{cid}/syllabus", headers=admin, json=body).status_code == 200
    assert client.post(f"/api/courses/{cid}/syllabus/approve", headers=gv).status_code == 403
    assert client.post(f"/api/courses/{cid}/syllabus/approve", headers=admin).status_code == 200

    # bản 2 đang áp dụng, bản 1 đã thay thế; bản 1 vẫn xem lại được
    s = client.get(f"/api/courses/{cid}/syllabus", headers=gv).json()
    assert s["doc"]["version_no"] == 2 and s["doc"]["objectives"] == "Mục tiêu bản 2" and s["approved_version"] == 2
    assert [v["status"] for v in s["versions"]] == ["archived", "approved"]
    old = client.get(f"/api/courses/{cid}/syllabus?version=1", headers=gv).json()["doc"]
    assert old["status"] == "archived" and len(old["assessments"]) == 3
    assert client.post(f"/api/courses/{cid}/syllabus/approve", headers=admin).status_code == 409    # không còn bản nháp


def test_outline_detail(client, admin, gv):
    cid = _demo_course()
    s = client.get(f"/api/courses/{cid}/syllabus", headers=admin).json()
    o = s["outlines"][0]
    clo_ids = [c["id"] for c in s["clos"]][:2]
    base = {"chapter_number": o["chapter_number"], "chapter_name": o["chapter_name"]}
    assert client.put(f"/api/outlines/{o['id']}", headers=gv, json={**base, "content": "x"}).status_code == 403
    assert client.put(f"/api/outlines/{o['id']}", headers=admin, json={**base, "theory_hours": -1}).status_code == 422
    assert client.put(f"/api/outlines/{o['id']}", headers=admin, json={**base, "clo_ids": [999999]}).status_code == 422
    r = client.put(f"/api/outlines/{o['id']}", headers=admin, json={**base, "content": "Nội dung mới", "theory_hours": 6, "clo_ids": clo_ids})
    assert r.status_code == 200
    # chỉ gửi số + tên (trình sửa nhanh) thì nội dung chi tiết giữ nguyên
    assert client.put(f"/api/outlines/{o['id']}", headers=admin, json=base).status_code == 200
    o2 = next(x for x in client.get(f"/api/courses/{cid}/syllabus", headers=gv).json()["outlines"] if x["id"] == o["id"])
    assert o2["content"] == "Nội dung mới" and o2["theory_hours"] == 6 and sorted(x["id"] for x in o2["clos"]) == sorted(clo_ids)
    assert client.get(f"/api/courses/{cid}", headers=gv).json()["outlines"][0]["clos"]


def test_new_course_without_syllabus(client, admin):
    r = client.post("/api/courses", headers=admin, json={"course_code": "TST9201", "course_name": "Môn chưa có đề cương", "credits": 2})
    cid = r.json()["id"]
    s = client.get(f"/api/courses/{cid}/syllabus", headers=admin).json()
    assert s["doc"] is None and s["versions"] == [] and s["approved_version"] is None
    assert client.post(f"/api/courses/{cid}/syllabus/approve", headers=admin).status_code == 409
    # lưu lần đầu tạo bản nháp phiên bản 1
    r = client.put(f"/api/courses/{cid}/syllabus", headers=admin, json={"english_name": "Test", "references": [{"citation": "Giáo trình A"}]})
    assert r.status_code == 200 and r.json() == {"version_no": 1, "status": "draft"}
    assert client.put(f"/api/courses/{cid}/syllabus", headers=admin, json={"effective_semester_id": 999999}).status_code == 422
    r = client.post(f"/api/courses/{cid}/syllabus/approve", headers=admin)
    assert r.status_code == 422 and "CLO" in r.json()["detail"]
