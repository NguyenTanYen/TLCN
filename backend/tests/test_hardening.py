"""Kiểm thử các ràng buộc an toàn & toàn vẹn bổ sung: phân quyền theo môn học và khóa học Moodle,
áp dụng lại kế hoạch CLO, xử lý dữ liệu vào và lỗi HTTP chuẩn."""
from sqlalchemy import create_engine, text

from app.config import settings
from app.database import engine

M = settings.moodle_db_name
COURSE = 5


def q(sql, **p):
    with engine.connect() as c:
        return c.execute(text(sql), p).fetchall()


def ex(sql, **p):
    eng = create_engine(settings.database_admin_url) if settings.database_admin_url else engine
    with eng.begin() as c:
        c.execute(text(sql), p)


def test_course_level_access(client, gv, gv_other, admin):
    # GV không dạy môn → không xem/thêm câu hỏi, không sửa kế hoạch CLO của môn đó
    assert client.get(f"/api/questions?course_id={COURSE}", headers=gv_other).status_code == 403
    assert client.get(f"/api/questions?course_id={COURSE}", headers=gv).status_code == 200
    assert client.get(f"/api/questions?course_id={COURSE}", headers=admin).status_code == 200
    assert client.get(f"/api/questions/import-template?course_id={COURSE}", headers=gv_other).status_code == 403
    qid = q("SELECT id FROM question_bank WHERE course_id=:c LIMIT 1", c=COURSE)[0][0]
    assert client.get(f"/api/questions/{qid}", headers=gv_other).status_code == 403
    clo = q("SELECT id FROM clos WHERE course_id=:c LIMIT 1", c=COURSE)[0][0]
    r = client.put("/api/clo-plans", headers=gv_other, json={"clo_id": clo, "semester_id": 7})
    assert r.status_code == 403
    assert client.get("/api/questions?course_id=99999", headers=admin).status_code == 404


def test_clo_plan_change_reanalyzes(client, gv):
    clo = q("SELECT id FROM clos WHERE course_id=:c AND clo_code='CLO2'", c=COURSE)[0][0]
    plan = dict(q("""SELECT clo_id, semester_id, assessments_text, evidence_type, method, cycle, pass_threshold_pct, target_pct
                     FROM clo_assessment_plans WHERE clo_id=:c AND semester_id=7""", c=clo)[0]._mapping)
    before = q("SELECT n_achieved FROM clo_results WHERE class_section_id=1 AND clo_id=:c", c=clo)[0][0]
    body = {k: (float(v) if k.endswith("pct") else v) for k, v in plan.items()}
    r = client.put("/api/clo-plans", headers=gv, json={**body, "pass_threshold_pct": 0})
    assert r.status_code == 200 and r.json()["reanalyzed_exams"] >= 1
    n_eval, n_ok = q("SELECT n_evaluated, n_achieved FROM clo_results WHERE class_section_id=1 AND clo_id=:c", c=clo)[0]
    assert n_ok == n_eval  # ngưỡng 0% → mọi SV đạt: kết quả đã được tính lại ngay
    assert client.put("/api/clo-plans", headers=gv, json=body).status_code == 200
    assert q("SELECT n_achieved FROM clo_results WHERE class_section_id=1 AND clo_id=:c", c=clo)[0][0] == before


def test_link_quiz_must_belong_to_teacher_course(client, gv):
    e = client.post("/api/exams", headers=gv, json={"class_section_id": 1, "exam_title": "Quiz phụ", "exam_type": "online",
                                                   "items": [{"question_id": 1, "points": 1}]}).json()["id"]
    try:
        assert client.patch(f"/api/exams/{e}/link-quiz", headers=gv, json={"moodle_quiz_id": 424242}).status_code == 404
        ex(f"""INSERT INTO `{M}`.mdl_quiz (id, course, name, intro, preferredbehaviour, password, subnet, browsersecurity)
               VALUES (901, 50, 'Quiz phụ', '', 'deferredfeedback', '', '', '-')""")
        r = client.patch(f"/api/exams/{e}/link-quiz", headers=gv, json={"moodle_quiz_id": 901})
        assert r.status_code == 403, r.text  # gv.son chưa là giảng viên của khóa học Moodle 50
        ex(f"INSERT INTO `{M}`.mdl_role_assignments (id, roleid, contextid, userid) VALUES (9001, 3, 70, 99)")
        assert client.patch(f"/api/exams/{e}/link-quiz", headers=gv, json={"moodle_quiz_id": 901}).status_code == 200
        # lớp HP đã gắn khóa học 50: không được chuyển sang khóa khác
        assert client.patch("/api/class-sections/1/moodle-course", headers=gv, json={"moodle_course_id": 51}).status_code == 409
    finally:
        ex(f"DELETE FROM `{M}`.mdl_role_assignments WHERE id=9001")
        ex(f"DELETE FROM `{M}`.mdl_quiz WHERE id=901")
        client.delete(f"/api/exams/{e}", headers=gv)


def test_question_edit_rules(client, gv):
    # Câu thuộc đề đã gắn Moodle: được sửa CLO/Bloom, không được sửa nội dung
    qid = q("""SELECT eq.question_id FROM exam_questions eq JOIN exams e ON e.id=eq.exam_id
               WHERE e.moodle_quiz_id IS NOT NULL LIMIT 1""")[0][0]
    cur = client.get(f"/api/questions/{qid}", headers=gv).json()
    body = {"course_id": COURSE, "outline_id": cur["outline_id"], "bloom_level_id": cur["bloom_level_id"], "content": cur["content"] + " (sửa)",
            "options": [{"content": o["content"], "is_correct": o["is_correct"]} for o in cur["options"]],
            "clos": [{"clo_id": c["clo_id"], "weight": c["weight"]} for c in cur["clos"]]}
    assert client.put(f"/api/questions/{qid}", headers=gv, json=body).status_code == 409
    assert client.put(f"/api/questions/{qid}", headers=gv, json={**body, "course_id": 1}).status_code in (403, 422)


def test_http_errors_and_inputs(client, gv, admin):
    assert client.get("/api/khong-ton-tai", headers=gv).status_code == 404
    assert client.delete("/api/pi-plans/987654", headers=admin).status_code == 404
    assert client.get("/api/pi-plans?program_id=999", headers=admin).status_code == 404
    clo = q("SELECT clo_code FROM clos WHERE course_id=:c LIMIT 1", c=COURSE)[0][0]
    r = client.post("/api/clos", headers=gv, json={"course_id": COURSE, "clo_code": clo, "description": "Trùng mã"})
    assert r.status_code == 409
    r = client.post("/api/exams", headers=gv, json={"class_section_id": 1, "exam_title": "x" * 300, "items": [{"question_id": 1, "points": 1}]})
    assert r.status_code == 422
    # Tên tệp tải về: ASCII an toàn + filename* UTF-8
    cd = client.get("/api/reports/class-sections/1/bm6.xlsx", headers=gv).headers["content-disposition"]
    assert 'filename="BM6_' in cd and "filename*=UTF-8''" in cd


def test_import_students_csv_semicolon(client, gv):
    import unicodedata  # Excel lưu CSV theo Windows-1258: nguyên âm có mũ/móc + dấu thanh tổ hợp

    def cp1258(t):
        out = b""
        for ch in t:
            try:
                out += ch.encode("cp1258")
            except UnicodeEncodeError:
                d = unicodedata.normalize("NFD", ch)
                for k in range(len(d), 0, -1):  # ghép phần đầu dài nhất mã hóa được, phần còn lại là dấu tổ hợp
                    try:
                        out += unicodedata.normalize("NFC", d[:k]).encode("cp1258") + d[k:].encode("cp1258"); break
                    except UnicodeEncodeError:
                        continue
        return out
    data = cp1258("student_code;full_name;class_name\nTEST_CSV_01;Nguyễn Văn Kiểm Thử;22110CL\n")
    assert data.decode("cp1258") != "Nguyễn"
    r = client.post("/api/class-sections/1/students/import", headers=gv,
                    files={"file": ("ds.csv", data, "text/csv")})
    try:
        assert r.status_code == 200 and r.json()["added"] == 1, r.text
        assert q("SELECT full_name FROM students WHERE student_code='TEST_CSV_01'")[0][0] == "Nguyễn Văn Kiểm Thử"
    finally:
        ex("DELETE e FROM enrollments e JOIN students s ON s.id=e.student_id WHERE s.student_code='TEST_CSV_01'")
        ex("DELETE FROM students WHERE student_code='TEST_CSV_01'")
    bad = client.post("/api/class-sections/1/students/import", headers=gv, files={"file": ("x.csv", b"ma,ten\n1,2\n", "text/csv")})
    assert bad.status_code == 422


def test_import_parsers_edge_cases():
    from app.services import question_import as qi
    lv = [{"id": i, "name_vi": n, "code": c} for i, (n, c) in
          enumerate([("Nhớ", "R"), ("Hiểu", "U"), ("Vận dụng", "Ap"), ("Phân tích", "An"), ("Đánh giá", "E"), ("Sáng tạo", "C")], 1)]
    assert qi.parse_bloom("3 - Vận dụng", lv) == (3, None)
    assert qi.parse_bloom("30", lv)[0] is None
    clos = {"clo1": 1, "clo2": 2, "clo3": 3}
    assert qi.parse_clos("CLO1:0,6; CLO3:0,4", clos) == ([(1, 0.6), (3, 0.4)], None)
    assert qi.parse_clos("CLO1:0.6.1", clos)[0] is None
    links, _ = qi.parse_clos("CLO1; CLO2; CLO3", clos)
    assert abs(sum(w for _, w in links) - 1) < 1e-9
