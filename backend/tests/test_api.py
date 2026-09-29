"""Kiểm thử tích hợp API theo các ca sử dụng UC-01 … UC-07 (kịch bản chính + ngoại lệ)."""
import io

from openpyxl import load_workbook
from sqlalchemy import text

from app.config import settings
from app.database import engine

M = settings.moodle_db_name

COURSE = 5  # DBMS330284


def q(sql, **p):
    with engine.connect() as c:
        return c.execute(text(sql), p).fetchall()


# ---------------------------------------------------------------- xác thực & phân quyền
def test_login_wrong_password(client):
    assert client.post("/api/auth/login", json={"username": "gv.son", "password": "sai"}).status_code == 401


def test_requires_token(client):
    assert client.get("/api/exams/2/item-stats").status_code == 401


def test_role_and_ownership(client, gv_other):
    from app.security import create_token
    uid = q("SELECT id FROM users WHERE role='student' LIMIT 1")[0][0]
    sv = {"Authorization": "Bearer " + create_token(uid, "student")}  # kể cả khi có token SV cũng không dùng được API GV
    assert client.get("/api/exams/2/item-stats", headers=gv_other).status_code == 403  # GV không phụ trách lớp
    assert client.get("/api/exams/2/item-stats", headers=sv).status_code == 403        # SV không xem thống kê lớp


# ---------------------------------------------------------------- UC-01 ngân hàng câu hỏi
def _question(**kw):
    body = {"course_id": COURSE, "outline_id": None, "bloom_level_id": 2, "content": "Câu hỏi kiểm thử về khóa chính?",
            "options": [{"content": "A1", "is_correct": True}, {"content": "B1"}, {"content": "C1"}, {"content": "D1"}],
            "clos": [{"clo_id": 1, "weight": 1.0}]}
    body.update(kw)
    return body


def test_question_validation(client, gv):
    bad_two_correct = _question(options=[{"content": "x", "is_correct": True}, {"content": "y", "is_correct": True}])
    assert client.post("/api/questions", json=bad_two_correct, headers=gv).status_code == 422
    bad_weights = _question(clos=[{"clo_id": 1, "weight": 0.5}, {"clo_id": 2, "weight": 0.3}])
    assert client.post("/api/questions", json=bad_weights, headers=gv).status_code == 422
    one_option = _question(options=[{"content": "x", "is_correct": True}])
    assert client.post("/api/questions", json=one_option, headers=gv).status_code == 422


def test_question_crud(client, gv):
    r = client.post("/api/questions", json=_question(clos=[{"clo_id": 1, "weight": 0.6}, {"clo_id": 2, "weight": 0.4}]), headers=gv)
    assert r.status_code == 201, r.text
    qid = r.json()["id"]
    r = client.put(f"/api/questions/{qid}", json=_question(content="Câu hỏi đã sửa nội dung?"), headers=gv)
    assert r.status_code == 200 and r.json()["content"].startswith("Câu hỏi đã sửa")
    assert client.delete(f"/api/questions/{qid}", headers=gv).status_code == 200


def test_question_with_results_is_locked(client, gv):
    # câu 24 đã có kết quả thi -> không được sửa (409), không được xóa (409), chỉ được Hủy
    assert client.put("/api/questions/24", json=_question(), headers=gv).status_code == 409
    assert client.delete("/api/questions/24", headers=gv).status_code == 409


# ---------------------------------------------------------------- UC-02 đề thi
def test_exam_online_xml(client, gv):
    r = client.post("/api/exams", headers=gv, json={"class_section_id": 1, "exam_title": "Quiz kiểm thử", "exam_type": "online",
                                                    "items": [{"question_id": 1, "points": 1}, {"question_id": 2, "points": 1}]})
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    x = client.get(f"/api/exams/{eid}/moodle-xml", headers=gv)
    assert x.status_code == 200 and b"<idnumber>QB-1</idnumber>" in x.content and x.content.count(b'<question type="multichoice">') == 2
    assert client.get(f"/api/exams/{eid}", headers=gv).json()["status"] == "Published"
    assert client.patch(f"/api/exams/{eid}/link-quiz", json={"moodle_quiz_id": 900}, headers=gv).status_code == 409  # quiz đã gắn bài #2
    assert client.post(f"/api/exams/{eid}/versions", json={"count": 2}, headers=gv).status_code == 422
    assert client.delete(f"/api/exams/{eid}", headers=gv).status_code == 200


def test_exam_rejects_foreign_question(client, gv):
    other = q("SELECT id FROM question_bank WHERE course_id<>:c LIMIT 1", c=COURSE)
    if other:
        r = client.post("/api/exams", headers=gv, json={"class_section_id": 1, "exam_title": "Sai môn", "items": [{"question_id": other[0][0], "points": 1}]})
        assert r.status_code == 422


def test_paper_versions_are_permutations():
    rows = q("""SELECT v.version_code, GROUP_CONCAT(vq.question_id ORDER BY vq.position) FROM exam_versions v
                JOIN exam_version_questions vq ON vq.version_id=v.id WHERE v.exam_id=1 GROUP BY v.id""")
    assert len(rows) == 2
    a, b = [r[1].split(",") for r in rows]
    assert sorted(a) == sorted(b) and a != b
    # mỗi câu trong mỗi mã đề có đúng một phương án đúng được hiển thị
    bad = q("""SELECT evo.version_id, evo.question_id, SUM(o.is_correct) FROM exam_version_options evo
               JOIN question_options o ON o.id=evo.option_id GROUP BY evo.version_id, evo.question_id HAVING SUM(o.is_correct)<>1""")
    assert bad == []


def test_paper_docx_and_key(client, gv):
    vid = q("SELECT id FROM exam_versions WHERE exam_id=1 ORDER BY id LIMIT 1")[0][0]
    d = client.get(f"/api/exams/1/versions/{vid}/paper.docx", headers=gv)
    assert d.status_code == 200 and d.content[:2] == b"PK"
    k = client.get("/api/exams/1/answer-key.xlsx", headers=gv)
    wb = load_workbook(io.BytesIO(k.content))
    assert k.status_code == 200 and len(wb.sheetnames) >= 1


# ---------------------------------------------------------------- UC-03 đồng bộ / nhập phiếu
def test_moodle_sync_matches_moodle_grades():
    rows = q(f"""SELECT a.total_score, ma.sumgrades FROM exam_attempts a JOIN {M}.mdl_quiz_attempts ma ON ma.id=a.moodle_attempt_id
                WHERE a.exam_id=2""")
    assert len(rows) == 38 and all(round(float(x), 2) == round(float(y), 2) for x, y in rows)


def test_moodle_sync_follows_grade_method_and_skips_preview():
    # quiz mô phỏng dùng grademethod = 1 (điểm cao nhất, hòa -> lượt sớm hơn) như mặc định của Moodle
    graded = {r[0] for r in q(f"""SELECT x.id FROM {M}.mdl_quiz_attempts x WHERE x.quiz=900 AND x.preview=0 AND x.state='finished'
              AND NOT EXISTS (SELECT 1 FROM {M}.mdl_quiz_attempts y WHERE y.quiz=x.quiz AND y.userid=x.userid AND y.preview=0
              AND y.state='finished' AND (y.sumgrades > x.sumgrades OR (y.sumgrades = x.sumgrades AND y.attempt < x.attempt)))""")}
    synced = {r[0] for r in q("SELECT moodle_attempt_id FROM exam_attempts WHERE exam_id=2 AND status='finished'")}
    assert synced == graded and len(synced) == 38


def test_absent_students_recorded():
    assert q("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=2 AND status='absent'")[0][0] == 2
    assert q("""SELECT COUNT(*) FROM item_level_results r JOIN exam_attempts a ON a.id=r.attempt_id
                WHERE a.status='absent' AND r.response_status<>'absent'""")[0][0] == 0


def test_resync_is_idempotent(client, gv):
    before = q("SELECT COUNT(*), SUM(total_score) FROM exam_attempts WHERE exam_id=2")[0]
    r = client.post("/api/exams/2/sync", headers=gv)
    assert r.status_code == 200, r.text
    assert q("SELECT COUNT(*), SUM(total_score) FROM exam_attempts WHERE exam_id=2")[0] == before


def test_paper_import_errors(client, gv):
    csv = "student_code,version_code,Q1\n99999999,101,A\n22130001,999,A\n".encode()
    r = client.post("/api/exams/1/paper-import?analyze=false", headers=gv, files={"file": ("x.csv", csv, "text/csv")})
    assert r.status_code == 200
    warns = r.json()["import"]["warnings"]
    assert any("99999999" in w for w in warns) and any("999" in w for w in warns)
    # nạp lại phiếu đúng để các kiểm thử sau có dữ liệu
    with open("demo_phieu_tra_loi.csv", "rb") as f:
        r = client.post("/api/exams/1/paper-import", headers=gv, files={"file": ("phieu.csv", f.read(), "text/csv")})
    assert r.status_code == 200 and r.json()["import"]["imported"] == 38


def test_sync_rejects_paper_exam(client, gv):
    assert client.post("/api/exams/1/sync", headers=gv).status_code == 422


# ---------------------------------------------------------------- UC-04 thống kê
def test_item_stats_flags_trap_question(client, gv):
    items = {x["question_id"]: x for x in client.get("/api/exams/2/item-stats", headers=gv).json()}
    trap = items[24]
    assert float(trap["di_value"]) < 0 and trap["classification"] == "Cần loại bỏ/kiểm tra đáp án"
    assert sum(d["n"] for d in trap["distribution"]) == 38


def test_clo_results_bm6b(client, gv):
    r = client.get("/api/class-sections/1/clo-results", headers=gv).json()
    assert r["has_data"] and len(r["clos"]) == 4
    for c in r["clos"]:
        assert round(100 * c["n_achieved"] / c["n_evaluated"], 2) == float(c["achieved_pct"])
        assert bool(c["is_achieved"]) == (float(c["achieved_pct"]) >= float(c["target_pct"]))
    clo1 = next(c for c in r["clos"] if c["clo_code"] == "CLO1")
    assert clo1["n_evaluated"] == 76  # evidence_type 'any': cộng dồn 2 bài KT (BM6d)


def test_clo_narrative(client, gv):
    r = client.put("/api/class-sections/1/clo-results/2", headers=gv, json={"analysis": "SV yếu phần giao tác", "improvement": "Bổ sung bài tập"})
    assert r.status_code == 200


# ---------------------------------------------------------------- UC-05: SV xem kết quả trên Moodle
def test_student_cannot_login(client):
    r = client.post("/api/auth/login", json={"username": "22130001", "password": "Sv@123456"})
    assert r.status_code == 403 and "Moodle" in r.json()["detail"]


def test_results_for_moodle(client, gv):
    rows = client.get("/api/exams/2/moodle/results-preview", headers=gv).json()
    done = [r for r in rows if r["status"] == "finished"]
    absent = [r for r in rows if r["status"] == "absent"]
    assert done and absent and all(r["data"] == {} and r["score"] is None for r in absent)  # E2 – chưa đủ bằng chứng
    d = done[0]["data"]
    assert len(d["clos"]) == 4 and all({"code", "pct", "threshold", "class_avg", "achieved"} <= set(c) for c in d["clos"])
    weak = next(r for r in done if r["data"]["items"])
    assert all(i["gap"] > 0 and i["clo"] for i in weak["data"]["items"])
    assert 0 <= done[0]["score"] <= done[0]["max_score"]


def test_push_requires_moodle_config(client, gv, monkeypatch):
    monkeypatch.setattr(settings, "moodle_ws_token", "")
    r = client.post("/api/exams/2/moodle/push-results", headers=gv)
    assert r.status_code == 502 and "Chưa cấu hình" in r.json()["detail"]


def test_publish_requires_analyzed(client, gv):
    r = client.post("/api/exams", headers=gv, json={"class_section_id": 1, "exam_title": "Chưa phân tích", "items": [{"question_id": 3, "points": 1}]})
    eid = r.json()["id"]
    assert client.patch(f"/api/exams/{eid}/publish", json={"publish": True}, headers=gv).status_code == 409
    client.delete(f"/api/exams/{eid}", headers=gv)


# ---------------------------------------------------------------- UC-06/07 CTĐT, PLO/PI, báo cáo
def test_program_structure(client, admin):
    p = client.get("/api/programs/1", headers=admin).json()
    assert len(p["plos"]) == 19  # BM2 KTDL: 19 CĐR (5 nhóm)
    plans = client.get("/api/pi-plans?academic_year=2024-2025", headers=admin).json()
    assert any(x["plo_code"] == "1.3" for x in plans)


def test_plo_summary_is_sum_of_pi(client, admin):
    s = client.get("/api/reports/programs/1/plo-summary?academic_year=2024-2025", headers=admin).json()
    measured = [p for p in s["plos"] if p["n_evaluated"]]
    assert measured
    pr = s["program_result"]
    assert pr["n_evaluated"] == sum(p["n_evaluated"] for p in measured)
    pis = q("""SELECT pi.plo_id, SUM(r.n_evaluated), SUM(r.n_achieved) FROM pi_results r JOIN pi_assessment_plans pl ON pl.id=r.plan_id
               JOIN performance_indicators pi ON pi.id=pl.pi_id JOIN semesters se ON se.id=pl.semester_id
               WHERE se.academic_year='2024-2025' GROUP BY pi.plo_id""")
    by_plo = {p["plo_id"]: p for p in measured}
    for plo_id, n, ok in pis:
        assert by_plo[plo_id]["n_evaluated"] == n and by_plo[plo_id]["n_achieved"] == ok


def test_bm6_workbook(client, gv):
    r = client.get("/api/reports/class-sections/1/bm6.xlsx", headers=gv)
    wb = load_workbook(io.BytesIO(r.content))
    assert r.status_code == 200
    assert any(n.startswith("BM6a") for n in wb.sheetnames) and any(n.startswith("BM6b") for n in wb.sheetnames)
    assert sum(1 for n in wb.sheetnames if n.startswith("BM6c") or n.startswith("BM6d")) == 4


def test_bm3_workbook(client, admin, gv):
    assert client.get("/api/reports/programs/1/bm3.xlsx?academic_year=2024-2025", headers=gv).status_code == 403
    r = client.get("/api/reports/programs/1/bm3.xlsx?academic_year=2024-2025", headers=admin)
    wb = load_workbook(io.BytesIO(r.content))
    assert r.status_code == 200 and len(wb.sheetnames) >= 2


def test_plo_narrative(client, admin):
    plo_id = q("SELECT plo_id FROM plo_results LIMIT 1")[0][0]
    r = client.put(f"/api/reports/plo-results/{plo_id}/2024-2025", headers=admin,
                   json={"analysis": "a", "improvement_actions": "b", "improvement_results": "c", "evidence_tools": "d"})
    assert r.status_code == 200
