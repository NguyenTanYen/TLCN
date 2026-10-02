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
    done = migrate.upgrade_schema()
    assert "exams.moodle_offlinequiz_id" in done and "question_bank.bloom_level_id NULL" in done
    assert migrate.upgrade_schema() == []          # chạy lại: không đổi gì
    with engine.begin() as c:
        c.execute(text("UPDATE exams SET moodle_offlinequiz_id=:v WHERE id=1"), {"v": oq})
    migrate.run()                                   # cài lại cầu nối theo lược đồ mới
    with engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM v_mdl_attempts WHERE exam_id=1")).scalar() == 38
