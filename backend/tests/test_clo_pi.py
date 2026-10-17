"""Góp ý F2a: CLO ánh xạ tới PI (PI thuộc PLO); ma trận CLO – PLO được suy ra; cây PLO → PI → CLO trong ngân hàng câu hỏi."""
from sqlalchemy import text

from app.database import engine
from app.services.outcomes import backfill_clo_pi


def _q(sql, **kw):
    with engine.connect() as c:
        return c.execute(text(sql), kw).all()


def _new_course(client, admin, code):
    r = client.post("/api/courses", headers=admin, json={"course_code": code, "course_name": "Môn thử CLO–PI", "credits": 3})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_seed_backfilled_clo_pi():
    # mọi CLO đã có ma trận CLO – PLO (và PLO có PI) đều có CLO → PI; PLO suy ra trùng ma trận cũ
    miss = _q("""SELECT m.clo_id FROM clo_plo_mapping m WHERE EXISTS (SELECT 1 FROM performance_indicators i WHERE i.plo_id=m.plo_id)
                 AND NOT EXISTS (SELECT 1 FROM clo_pi_mapping x WHERE x.clo_id=m.clo_id)""")
    assert not miss
    assert _q("SELECT COUNT(*) FROM clo_pi_mapping")[0][0] > 0
    wrong = _q("""SELECT x.clo_id FROM clo_pi_mapping x JOIN performance_indicators i ON i.id=x.pi_id
                  WHERE NOT EXISTS (SELECT 1 FROM clo_plo_mapping m WHERE m.clo_id=x.clo_id AND m.plo_id=i.plo_id)""")
    assert not wrong


def test_clo_pi_mapping_derives_plo(client, admin, gv):
    cid = _new_course(client, admin, "TST9101")
    # hai PI cùng một PLO, một PI của PLO khác
    plo_a, pi_a1, pi_a2 = _q("""SELECT i.plo_id, MIN(i.id), MAX(i.id) FROM performance_indicators i
                                GROUP BY i.plo_id HAVING COUNT(*) >= 2 ORDER BY i.plo_id LIMIT 1""")[0]
    pi_b, plo_b = _q("SELECT id, plo_id FROM performance_indicators WHERE plo_id <> :p ORDER BY id LIMIT 1", p=plo_a)[0]
    body = {"course_id": cid, "clo_code": "CLO1", "description": "Phân tích được bài toán", "bloom_level_id": 4,
            "pis": [{"pi_id": pi_a1, "level": "I"}, {"pi_id": pi_a2, "level": "M"}, {"pi_id": pi_b, "level": "R"}]}
    r = client.post("/api/clos", headers=admin, json=body)
    assert r.status_code in (200, 201), r.text
    clo = r.json()["id"]
    # PLO suy ra: mức cao nhất trong các PI của PLO đó
    assert set(_q("SELECT plo_id, level FROM clo_plo_mapping WHERE clo_id=:c", c=clo)) == {(plo_a, "M"), (plo_b, "R")}
    c = client.get(f"/api/courses/{cid}", headers=admin).json()
    assert {(p["pi_id"], p["level"]) for p in c["clos"][0]["pis"]} == {(pi_a1, "I"), (pi_a2, "M"), (pi_b, "R")}

    upd = {"clo_code": "CLO1", "description": "Phân tích được bài toán", "bloom_level_id": 4}
    assert client.put(f"/api/clos/{clo}", headers=admin, json={**upd, "pis": [{"pi_id": pi_a1}, {"pi_id": pi_a1}]}).status_code == 422
    assert client.put(f"/api/clos/{clo}", headers=admin, json={**upd, "pis": [{"pi_id": 999999}]}).status_code == 422
    assert client.put(f"/api/clos/{clo}", headers=admin, json={**upd, "pis": [{"pi_id": pi_a1, "level": "X"}]}).status_code == 422
    assert client.put(f"/api/clos/{clo}", headers=gv, json={**upd, "pis": [{"pi_id": pi_a1}]}).status_code == 403
    assert client.put(f"/api/clos/{clo}", headers=admin, json={**upd, "pis": [{"pi_id": pi_a2, "level": "I"}]}).status_code == 200
    assert set(_q("SELECT plo_id, level FROM clo_plo_mapping WHERE clo_id=:c", c=clo)) == {(plo_a, "I")}

    # học phần đã gán CTĐT thì chỉ chọn được PI của CTĐT đó
    prog_a = _q("SELECT program_id FROM plos WHERE id=:p", p=plo_a)[0][0]
    other = _q("SELECT i.id FROM performance_indicators i JOIN plos p ON p.id=i.plo_id WHERE p.program_id <> :g ORDER BY i.id LIMIT 1", g=prog_a)
    with engine.begin() as cn:
        cn.execute(text("DELETE FROM program_courses WHERE course_id=:c"), {"c": cid})      # môn mới có thể đã được gán sẵn CTĐT
        cn.execute(text("INSERT INTO program_courses (program_id, course_id) VALUES (:g, :c)"), {"g": prog_a, "c": cid})
    try:
        assert client.put(f"/api/clos/{clo}", headers=admin, json={**upd, "pis": [{"pi_id": pi_a1, "level": "R"}]}).status_code == 200
        if other:
            assert client.put(f"/api/clos/{clo}", headers=admin, json={**upd, "pis": [{"pi_id": other[0][0], "level": "R"}]}).status_code == 422
    finally:
        with engine.begin() as cn:
            cn.execute(text("DELETE FROM program_courses WHERE course_id=:c"), {"c": cid})

    # cách cũ (CLO → PLO trực tiếp) vẫn dùng được, khi đó CLO → PI bị xóa
    assert client.put(f"/api/clos/{clo}", headers=admin, json={**upd, "plos": [{"plo_id": plo_b, "level": "R"}]}).status_code == 200
    assert not _q("SELECT 1 FROM clo_pi_mapping WHERE clo_id=:c", c=clo)


def test_backfill_from_legacy_plo(client, admin):
    cid = _new_course(client, admin, "TST9102")
    plo, first_pi = _q("SELECT plo_id, MIN(id) FROM performance_indicators GROUP BY plo_id ORDER BY plo_id LIMIT 1")[0]
    r = client.post("/api/clos", headers=admin, json={"course_id": cid, "clo_code": "CLO1", "description": "Trình bày được",
                                                     "bloom_level_id": 2, "plos": [{"plo_id": plo, "level": "M"}]})
    clo = r.json()["id"]
    assert not _q("SELECT 1 FROM clo_pi_mapping WHERE clo_id=:c", c=clo)
    with engine.begin() as cn:
        assert backfill_clo_pi(cn, cid) == 1
        assert backfill_clo_pi(cn, cid) == 0          # chạy lại không sinh trùng
    assert _q("SELECT pi_id, level FROM clo_pi_mapping WHERE clo_id=:c", c=clo) == [(first_pi, "M")]


def test_question_outcome_tree(client, gv):
    cid = _q("""SELECT c.course_id FROM question_bank q JOIN question_clo_mapping m ON m.question_id=q.id JOIN clos c ON c.id=m.clo_id
                JOIN clo_pi_mapping x ON x.clo_id=c.id GROUP BY c.course_id ORDER BY COUNT(*) DESC LIMIT 1""")[0][0]
    t = client.get(f"/api/questions/tree?course_id={cid}", headers=gv)
    assert t.status_code == 200, t.text
    t = t.json()
    assert t["total"] > 0 and t["programs"]
    pl = t["programs"][0]["plos"][0]
    pi = pl["pis"][0]
    # số câu của PI = số câu lọc theo PI; mỗi câu đều có CLO đóng góp cho PI đó
    qs = client.get(f"/api/questions?course_id={cid}&pi_id={pi['id']}", headers=gv).json()
    assert len(qs) == pi["n"] > 0
    assert all(any(p["pi_id"] == pi["id"] for c in q["clos"] for p in c.get("pis", [])) for q in qs)
    assert len(client.get(f"/api/questions?course_id={cid}&plo_id={pl['id']}", headers=gv).json()) == pl["n"] >= pi["n"]
    c = pi["clos"][0]
    assert len(client.get(f"/api/questions?course_id={cid}&clo_id={c['id']}", headers=gv).json()) == c["n"]
