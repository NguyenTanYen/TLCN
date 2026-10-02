"""Sinh đề theo ma trận (UC-02): hàm thuần và API."""
from sqlalchemy import text

from app.database import engine
from app.services import blueprint as bp


def _pool():
    # 3 chương × mức Bloom; CLO 1 ở chương 1, CLO 2 ở chương 2, CLO 3 ở chương 3
    qs, i = [], 0
    for ch, clo in ((1, 1), (2, 2), (3, 3)):
        for b in (1, 2, 3, 3):
            i += 1
            qs.append(bp.Q(id=i, outline_id=ch, bloom=b, clos={clo: 1.0}))
    return qs


def test_auto_matrix_covers_chapters_clos_and_respects_bank():
    r = bp.generate(_pool(), n=6, scope_clos=[1, 2, 3], seed=1)
    assert not r.errors and len(r.items) == 6 and len(set(r.items)) == 6
    by = {q.id: q for q in _pool()}
    assert {by[i].outline_id for i in r.items} == {1, 2, 3}            # đủ mọi chương
    assert all(sum(1 for i in r.items if c in by[i].clos) >= 1 for c in (1, 2, 3))  # đủ mọi CLO
    assert r.target and sum(r.target.values()) == 6
    assert bp.generate(_pool(), n=6, scope_clos=[1, 2, 3], seed=1).items == r.items   # cùng seed → cùng đề


def test_shortage_and_matrix_errors():
    r = bp.generate(_pool(), n=20)
    assert r.errors and "chỉ có 12 câu" in r.errors[0]
    r = bp.generate(_pool(), matrix={(1, 3): 3, (2, 1): 1}, names={"chapter": lambda c: f"chương {c}", "bloom": lambda b: f"mức {b}"})
    assert any("Chương 1 – mức 3: cần 3 câu, ngân hàng chỉ có 2 câu" in e for e in r.errors)
    assert len(r.items) == 3                                               # vẫn trả phần chọn được để GV chỉnh


def test_chapter_test_and_fixed_questions():
    pool = [q for q in _pool() if q.outline_id in (1, 2)]                  # kiểm tra chương 1–2
    r = bp.generate(pool, n=4, scope_clos=[1, 2, 3], fixed=[2])
    assert 2 in r.items and len(r.items) == 4
    assert any("không đo" in x for x in r.info) and not any("CLO 3" in w for w in r.warnings)


def test_largest_remainder_caps():
    assert bp.largest_remainder(10, {1: 20, 2: 30, 3: 30, 4: 15, 5: 5}) == {1: 2, 2: 3, 3: 3, 4: 2, 5: 0}
    out = bp.largest_remainder(10, {1: 50, 2: 50}, {1: 2, 2: 20})
    assert out == {1: 2, 2: 8}


def test_blueprint_api(client, gv, gv_other):
    r = client.post("/api/class-sections/1/exam-blueprint", headers=gv, json={"n_questions": 12, "seed": 3})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] and d["n_questions"] == 12 and abs(d["total_points"] - 10) < 1e-9
    assert all(c["selected"] >= 1 for c in d["clos"] if c["in_scope"])
    with engine.connect() as c:
        bad = c.execute(text(f"""SELECT COUNT(*) FROM question_bank WHERE id IN ({','.join(str(i['question_id']) for i in d['items'])})
                                 AND (course_id<>5 OR is_cancelled=1 OR bloom_level_id IS NULL)""")).scalar()
    assert bad == 0
    # lưu đề vừa sinh
    e = client.post("/api/exams", headers=gv, json={"class_section_id": 1, "exam_title": "Đề sinh theo ma trận", "items": d["items"]})
    assert e.status_code == 201
    assert len(e.json()["questions"]) == 12 and all(q["chapter"] for q in e.json()["questions"])
    assert client.delete(f"/api/exams/{e.json()['id']}", headers=gv).status_code == 200
    # kiểm tra chương: chỉ lấy câu của chương đã chọn
    with engine.connect() as c:
        o1 = c.execute(text("SELECT id FROM course_outlines WHERE course_id=5 AND chapter_number IN (1,2)")).scalars().all()
    d = client.post("/api/class-sections/1/exam-blueprint", headers=gv, json={"n_questions": 6, "outline_ids": o1}).json()
    with engine.connect() as c:
        outs = set(c.execute(text(f"SELECT outline_id FROM question_bank WHERE id IN ({','.join(str(i['question_id']) for i in d['items'])})")).scalars())
    assert outs <= set(o1) and any("không đo" in x for x in d["info"])
    # không đủ câu, quyền, dữ liệu sai
    d = client.post("/api/class-sections/1/exam-blueprint", headers=gv, json={"n_questions": 150}).json()
    assert not d["ok"] and "không đủ 150 câu" in d["errors"][0]
    assert client.post("/api/class-sections/1/exam-blueprint", headers=gv_other, json={"n_questions": 5}).status_code == 403
    assert client.post("/api/class-sections/1/exam-blueprint", headers=gv, json={"n_questions": 5, "outline_ids": [999999]}).status_code == 422
    assert client.post("/api/class-sections/1/exam-blueprint", headers=gv, json={}).status_code == 422
    p = client.get("/api/class-sections/1/exam-blueprint/pool", headers=gv).json()
    assert p["pool_size"] == sum(c["available"] for c in p["cells"]) and p["chapters"]
