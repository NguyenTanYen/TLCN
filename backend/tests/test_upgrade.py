"""Nâng cấp CSDL từ bản cũ và cài cầu nối khi Moodle chưa có plugin Offline Quiz."""
from sqlalchemy import text

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
        c.execute(text("ALTER TABLE question_bank MODIFY bloom_level_id TINYINT NOT NULL"))
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
