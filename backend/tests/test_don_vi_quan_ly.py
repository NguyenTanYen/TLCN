from sqlalchemy import text

from app import migrate
from app.database import engine
from app.services.units import FACULTY_UNIT


def q(sql, **p):
    with engine.connect() as c:
        return c.execute(text(sql), p).fetchall()


def _program(client, admin, code):
    return next(p for p in client.get("/api/programs", headers=admin).json() if p["code"] == code)


def test_only_2026_programs_remain(client, admin):
    codes = sorted(p["code"] for p in client.get("/api/programs", headers=admin).json())
    assert codes == ["ATTT-2026", "CNTT-2026", "KTDL-2026"]
    assert not q("SELECT 1 FROM programs WHERE code='KTDL'")


def test_external_courses_are_separated(client, admin):
    for code in ("CNTT-2026", "KTDL-2026", "ATTT-2026"):
        p = _program(client, admin, code)
        assert p["n_external_courses"] > 0 and p["n_courses"] > p["n_external_courses"]
        d = client.get(f"/api/programs/{p['id']}", headers=admin).json()
        ext = [c for c in d["courses"] if c["is_external"]]
        assert len(ext) == p["n_external_courses"]
        assert all(c["managing_unit"] != FACULTY_UNIT for c in ext)
        assert all(c["managing_unit"] == FACULTY_UNIT for c in d["courses"] if not c["is_external"])
    d = client.get(f"/api/programs/{_program(client, admin, 'KTDL-2026')['id']}", headers=admin).json()
    by = {c["course_code"]: c for c in d["courses"]}
    assert by["LLCT130105"]["managing_unit"] == "Khoa Lý luận chính trị"
    assert by["MATH132101"]["managing_unit"] == "Khoa Khoa học ứng dụng"
    assert by["ENCO140126"]["managing_unit"] == "Khoa Ngoại ngữ"
    assert not by["DBMS330284"]["is_external"]


def test_external_course_cannot_be_pi_evidence(client, admin):
    kid = _program(client, admin, "KTDL-2026")["id"]
    pi = q("SELECT pi.id FROM performance_indicators pi JOIN plos p ON p.id=pi.plo_id WHERE p.program_id=:k ORDER BY pi.id LIMIT 1", k=kid)[0][0]
    ext = q("SELECT id FROM courses WHERE course_code='LLCT130105'")[0][0]
    sem = q("SELECT id FROM semesters ORDER BY id LIMIT 1")[0][0]
    r = client.post("/api/pi-plans", headers=admin, json={"pi_id": pi, "course_id": ext, "semester_id": sem, "method": "Bài thi", "target_pct": 70, "clo_ids": []})
    assert r.status_code == 422 and "Khoa Lý luận chính trị" in r.json()["detail"]


def test_change_managing_unit(client, admin, gv):
    cid = q("SELECT id FROM courses WHERE course_code='ECOM430984'")[0][0]
    assert client.put(f"/api/courses/{cid}", headers=gv, json={"managing_unit": "Khoa Kinh tế"}).status_code == 403
    assert client.put(f"/api/courses/{cid}", headers=admin, json={"managing_unit": "Khoa Kinh tế"}).json()["ok"]
    assert q("SELECT managing_unit FROM courses WHERE id=:c", c=cid)[0][0] == "Khoa Kinh tế"
    assert client.put(f"/api/courses/{cid}", headers=admin, json={"managing_unit": FACULTY_UNIT}).json()["ok"]


def test_retire_legacy_program_on_upgrade():
    with engine.begin() as c:
        c.execute(text("INSERT INTO programs (code, name, level, target_pct) VALUES ('KTDL', 'Kỹ thuật dữ liệu', 'Đại học', 75)"))
        pid = c.execute(text("SELECT id FROM programs WHERE code='KTDL'")).scalar()
        c.execute(text("INSERT INTO plos (program_id, group_no, plo_code, description, target_pct) VALUES (:p, 1, '1.3', 'cũ', 75)"), {"p": pid})
        plo = c.execute(text("SELECT id FROM plos WHERE program_id=:p"), {"p": pid}).scalar()
        c.execute(text("INSERT INTO performance_indicators (plo_id, pi_code, description) VALUES (:l, 'PI 1', 'cũ')"), {"l": plo})
        pi = c.execute(text("SELECT id FROM performance_indicators WHERE plo_id=:l"), {"l": plo}).scalar()
        clo = c.execute(text("SELECT id FROM clos ORDER BY id LIMIT 1")).scalar()
        c.execute(text("INSERT INTO clo_pi_mapping (clo_id, pi_id) VALUES (:c, :p)"), {"c": clo, "p": pi})
    done = []
    with engine.begin() as c:
        migrate._retire_legacy_program(c, done)
    assert done == ["bỏ CTĐT KTDL cũ (giữ KTDL-2026)"]
    assert not q("SELECT 1 FROM programs WHERE code='KTDL'")
    assert not q("SELECT 1 FROM performance_indicators WHERE id=:p", p=pi)
    assert q("SELECT 1 FROM programs WHERE code='KTDL-2026'")
    with engine.begin() as c:
        migrate._retire_legacy_program(c, done)
    assert len(done) == 1


def test_attt_iot_and_firewall_mapping_fixed():
    iot = {r[0] for r in q("""SELECT i.pi_code FROM pi_courses pc JOIN courses c ON c.id=pc.course_id JOIN performance_indicators i ON i.id=pc.pi_id
                              JOIN plos l ON l.id=i.plo_id JOIN programs p ON p.id=l.program_id WHERE p.code='ATTT-2026' AND c.course_code='IOTS431780'""")}
    fw = {r[0] for r in q("""SELECT i.pi_code FROM pi_courses pc JOIN courses c ON c.id=pc.course_id JOIN performance_indicators i ON i.id=pc.pi_id
                             JOIN plos l ON l.id=i.plo_id JOIN programs p ON p.id=l.program_id WHERE p.code='ATTT-2026' AND c.course_code='FTPS433180'""")}
    assert iot == {"PI1.1", "PI1.2", "PI3.1", "PI5.2", "PI6.2"}
    assert fw == {"PI5.2", "PI6.3", "PI7.2"}


def test_measurement_plans_for_2026_programs():
    rows = q("""SELECT g.code, COUNT(*), MIN(m.academic_year), MIN(m.target_pct) FROM plo_measurement_plans m
                JOIN plos p ON p.id = m.plo_id JOIN programs g ON g.id = p.program_id GROUP BY g.code ORDER BY g.code""")
    assert [(r[0], r[1], r[2], float(r[3])) for r in rows] == [("ATTT-2026", 7, "2024-2025", 75.0), ("CNTT-2026", 7, "2024-2025", 75.0), ("KTDL-2026", 7, "2024-2025", 75.0)]


def test_bm2_header_falls_back_to_faculty(client, admin):
    import io
    from docx import Document
    kid = _program(client, admin, "KTDL-2026")["id"]
    r = client.get(f"/api/reports/programs/{kid}/bm2.docx?academic_year=2024-2025", headers=admin)
    assert r.status_code == 200
    text = "\n".join(p.text for p in Document(io.BytesIO(r.content)).paragraphs)
    tables = " ".join(c.text for t in Document(io.BytesIO(r.content)).tables for row in t.rows for c in row.cells)
    assert "KHOA CÔNG NGHỆ THÔNG TIN" in text + tables
    assert "2024-2025" in tables
