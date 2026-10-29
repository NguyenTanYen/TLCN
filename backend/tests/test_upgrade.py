"""Nâng cấp CSDL từ bản cũ và cài cầu nối khi Moodle chưa có plugin Offline Quiz."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import migrate
from app.database import engine
from app.services import moodle


def test_bridge_without_offlinequiz_plugin():
    sql = moodle.render_bridge_sql(with_offlinequiz=False)
    code = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    assert "offlinequiz_results" not in code and "offlinequiz_groups" not in code
    stmts = moodle.split_statements(sql)
    assert len(stmts) == len(moodle.split_statements(moodle.render_bridge_sql(True)))
    assert any("CREATE OR REPLACE VIEW v_mdl_attempts" in s for s in stmts)


def test_upgrade_old_database_adds_offlinequiz_column():
    with engine.begin() as c:
        oq = c.execute(text("SELECT moodle_offlinequiz_id FROM exams WHERE id=1")).scalar()
        c.execute(text("ALTER TABLE exams DROP CONSTRAINT ck_exam_paper"))
        c.execute(text("ALTER TABLE exams DROP INDEX uq_exam_moodle_oq, DROP COLUMN moodle_offlinequiz_id"))
        c.execute(text("UPDATE question_bank SET bloom_level_id=2 WHERE bloom_level_id IS NULL"))
        c.execute(text("ALTER TABLE question_bank MODIFY bloom_level_id TINYINT NOT NULL"))
        # bản trước 15/10: chưa có bài nhập điểm, chọn bài minh chứng, bài phụ đạo
        c.execute(text("ALTER TABLE exams DROP CONSTRAINT ck_exam_type"))       # CSDL cũ: ràng buộc chưa có 'manual' (giả lập: bỏ hẳn)
        c.execute(text("ALTER TABLE exams DROP FOREIGN KEY fk_exam_parent"))
        c.execute(text("ALTER TABLE exams DROP COLUMN target_students, DROP COLUMN parent_exam_id, DROP COLUMN counts_for_clo"))
        c.execute(text("ALTER TABLE courses DROP COLUMN description"))
        # bảng phân công phiên bản cũ: khóa chính (học kỳ, môn, GV) – không ghi được môn TLCN/KLTN "tất cả GV hướng dẫn"
        n_old = c.execute(text("SELECT COUNT(*) FROM assessment_assignments WHERE all_supervisors=0")).scalar()
        c.execute(text("CREATE TABLE aa_bak AS SELECT semester_id, course_id, lecturer_id, note FROM assessment_assignments WHERE all_supervisors=0"))
        c.execute(text("DROP TABLE assessment_assignments"))
        c.execute(text("""CREATE TABLE assessment_assignments (semester_id INT NOT NULL, course_id INT NOT NULL, lecturer_id INT NOT NULL,
                          note VARCHAR(255) NULL, PRIMARY KEY (semester_id, course_id, lecturer_id),
                          CONSTRAINT fk_aa_semester FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE CASCADE,
                          CONSTRAINT fk_aa_course FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
                          CONSTRAINT fk_aa_lecturer FOREIGN KEY (lecturer_id) REFERENCES lecturers(id) ON DELETE CASCADE)"""))
        c.execute(text("INSERT INTO assessment_assignments SELECT * FROM aa_bak")); c.execute(text("DROP TABLE aa_bak"))
        # CSDL từng bị bỏ 2 bảng mã đề – được tạo lại theo 01_schema.sql
        c.execute(text("DROP TABLE exam_version_options"))
        c.execute(text("DROP TABLE exam_version_questions"))
    done = migrate.upgrade_schema()
    assert "exams.moodle_offlinequiz_id" in done and "question_bank.bloom_level_id NULL" in done
    assert "tạo lại bảng exam_version_questions" in done and "tạo lại bảng exam_version_options" in done
    assert "assessment_assignments: phân công tất cả GV hướng dẫn" in done
    assert {"exams.counts_for_clo", "exams.parent_exam_id", "exams.target_students", "exams.ck_exam_type", "courses.description"} <= set(done)
    with engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM assessment_assignments WHERE all_supervisors=0")).scalar() == n_old
        tl = c.execute(text("""SELECT co.course_code FROM assessment_assignments a JOIN courses co ON co.id=a.course_id
                               WHERE a.all_supervisors=1 AND a.lecturer_id IS NULL ORDER BY 1""")).scalars().all()
    assert tl == ["PODE434277", "POIS431184"]
    assert migrate.upgrade_schema() == []          # chạy lại: không đổi gì
    with engine.begin() as c:
        c.execute(text("UPDATE exams SET moodle_offlinequiz_id=:v WHERE id=1"), {"v": oq})
    migrate.run()                                   # cài lại cầu nối theo lược đồ mới
    with engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM v_mdl_attempts WHERE exam_id=1")).scalar() == 38


def _fk_att_exam_rule(c):
    return c.execute(text("""SELECT DELETE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS
                             WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME='exam_attempts' AND CONSTRAINT_NAME='fk_att_exam'""")).scalar()


def test_db_rejects_deleting_exam_with_attempts(client, gv):
    """fk_att_exam = RESTRICT: xóa bài KT đã có kết quả bằng SQL trực tiếp bị CSDL từ chối (không xóa dây chuyền bài làm)."""
    with engine.connect() as c:
        assert _fk_att_exam_rule(c) == "RESTRICT"
        n1 = c.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=1")).scalar()
    assert n1 > 0
    with pytest.raises(IntegrityError), engine.begin() as c:
        c.execute(text("DELETE FROM exams WHERE id=1"))
    with engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=1")).scalar() == n1
    # bài KT mới: chưa có bài làm thì xóa qua API được; có một bài làm thì API trả 409 và SQL bị CSDL chặn
    qs = [x["id"] for x in client.get("/api/questions?course_id=5", headers=gv).json() if x["tagged"]][:3]
    body = {"class_section_id": 1, "exam_title": "Thử khóa ngoại bài làm", "exam_type": "paper",
            "items": [{"question_id": i, "points": 1} for i in qs]}
    e1 = client.post("/api/exams", headers=gv, json=body).json()["id"]
    r = client.delete(f"/api/exams/{e1}", headers=gv)
    assert r.status_code == 200 and r.json()["deleted"] == e1, r.text
    e2 = client.post("/api/exams", headers=gv, json=body).json()["id"]
    with engine.begin() as c:
        sid = c.execute(text("SELECT student_id FROM enrollments WHERE class_section_id=1 LIMIT 1")).scalar()
        c.execute(text("INSERT INTO exam_attempts (exam_id, student_id, source, status, total_score) VALUES (:e, :s, 'manual', 'absent', 0)"),
                  {"e": e2, "s": sid})
    assert client.delete(f"/api/exams/{e2}", headers=gv).status_code == 409
    with pytest.raises(IntegrityError), engine.begin() as c:
        c.execute(text("DELETE FROM exams WHERE id=:e"), {"e": e2})
    with engine.begin() as c:          # xóa tường minh bài làm trước thì xóa được bài KT
        c.execute(text("DELETE FROM exam_attempts WHERE exam_id=:e"), {"e": e2})
        assert c.execute(text("DELETE FROM exams WHERE id=:e"), {"e": e2}).rowcount == 1


def test_upgrade_fk_att_exam_cascade_to_restrict():
    """CSDL cũ (fk_att_exam ON DELETE CASCADE) được nâng cấp sang RESTRICT; chạy lại không đổi gì."""
    with engine.begin() as c:
        c.execute(text("ALTER TABLE exam_attempts DROP FOREIGN KEY fk_att_exam"))
        c.execute(text("ALTER TABLE exam_attempts ADD CONSTRAINT fk_att_exam FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE"))
        assert _fk_att_exam_rule(c) == "CASCADE"
    assert "exam_attempts.fk_att_exam ON DELETE RESTRICT" in migrate.upgrade_schema()
    with engine.connect() as c:
        assert _fk_att_exam_rule(c) == "RESTRICT"
    assert migrate.upgrade_schema() == []
