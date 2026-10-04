"""Nâng cấp CSDL assessment_db đã cài từ phiên bản trước (chạy tự động mỗi khi hệ thống khởi động, an toàn khi chạy lại).

- question_bank.bloom_level_id cho phép NULL: câu nhập hàng loạt ở trạng thái "chưa gán" (gán CLO/Bloom sau bằng file).
- exams.moodle_offlinequiz_id: bài thi giấy do Moodle (Offline Quiz) sinh đề, nhận diện phiếu và chấm.
- exam_attempts: moodle_attempt_id duy nhất theo từng bài KT (id lượt Quiz và id kết quả Offline Quiz có thể trùng nhau).
- students.student_code VARCHAR(100): khớp độ dài mã số (idnumber/username) của Moodle.
- Tạo lại exam_version_questions, exam_version_options nếu thiếu (bản thử nghiệm từng bỏ 2 bảng này).
- assessment_assignments: cho phép phân công "Tất cả thầy/cô có hướng dẫn" (TLCN, KLTN) – khóa chính id, lecturer_id NULL,
  cột all_supervisors; bổ sung 2 dòng phân công TLCN/KLTN của dữ liệu tham chiếu.
- Cài lại cầu nối đọc Moodle (view + sp_sync_exam) cho khớp phiên bản mã nguồn.
"""
from sqlalchemy import text

from .database import engine


def _col(c, table, col):
    return c.execute(text("""SELECT IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE()
                             AND TABLE_NAME=:t AND COLUMN_NAME=:c"""), {"t": table, "c": col}).scalar()


def _ddl(name: str) -> str:
    """Lấy câu CREATE TABLE của một bảng từ database/01_schema.sql (một nguồn duy nhất cho lược đồ)."""
    from pathlib import Path
    import re
    sql = (Path(__file__).resolve().parents[2] / "database" / "01_schema.sql").read_text(encoding="utf-8")
    return re.search(rf"CREATE TABLE {name} \(.*?\) ENGINE=InnoDB[^;]*;", sql, re.S).group(0).rstrip(";")


def upgrade_schema() -> list[str]:
    done = []
    with engine.begin() as c:
        if not c.execute(text("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='exams'")).scalar():
            return done
        if _col(c, "question_bank", "bloom_level_id") == "NO":
            c.execute(text("ALTER TABLE question_bank MODIFY bloom_level_id TINYINT NULL COMMENT 'NULL = chưa gán (câu nhập hàng loạt)'"))
            done.append("question_bank.bloom_level_id NULL")
        if _col(c, "exams", "moodle_offlinequiz_id") is None:
            c.execute(text("""ALTER TABLE exams
                ADD COLUMN moodle_offlinequiz_id BIGINT NULL COMMENT 'mdl_offlinequiz.id (bài thi giấy chấm trên Moodle)' AFTER moodle_quiz_id,
                ADD CONSTRAINT uq_exam_moodle_oq UNIQUE (moodle_offlinequiz_id),
                ADD CONSTRAINT ck_exam_paper CHECK (exam_type = 'paper' OR moodle_offlinequiz_id IS NULL)"""))
            done.append("exams.moodle_offlinequiz_id")
        cols = [r[0] for r in c.execute(text("""SELECT COLUMN_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE()
                   AND TABLE_NAME='exam_attempts' AND INDEX_NAME='uq_att_moodle' ORDER BY SEQ_IN_INDEX"""))]
        if cols == ["moodle_attempt_id"]:
            c.execute(text("ALTER TABLE exam_attempts DROP INDEX uq_att_moodle, ADD CONSTRAINT uq_att_moodle UNIQUE (exam_id, moodle_attempt_id)"))
            done.append("exam_attempts.uq_att_moodle (exam_id, moodle_attempt_id)")
        n = c.execute(text("""SELECT CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE()
                               AND TABLE_NAME='students' AND COLUMN_NAME='student_code'""")).scalar()
        if n is not None and n < 100:
            c.execute(text("ALTER TABLE students MODIFY student_code VARCHAR(100) NOT NULL"))
            done.append("students.student_code VARCHAR(100)")
        if _col(c, "assessment_assignments", "all_supervisors") is None:
            c.execute(text("""ALTER TABLE assessment_assignments
                DROP PRIMARY KEY,
                ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY FIRST,
                MODIFY lecturer_id INT NULL COMMENT 'GV được phân công (NULL khi giao cho tất cả GV hướng dẫn)',
                ADD COLUMN all_supervisors TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1 = Tất cả thầy/cô có hướng dẫn (TLCN, KLTN…)' AFTER lecturer_id,
                ADD COLUMN lecturer_key INT GENERATED ALWAYS AS (IFNULL(lecturer_id, 0)) VIRTUAL COMMENT 'Khóa so trùng (0 = tất cả GV hướng dẫn)',
                ADD CONSTRAINT uq_aa UNIQUE (semester_id, course_id, lecturer_key),
                ADD CONSTRAINT ck_aa_assignee CHECK ((all_supervisors = 1 AND lecturer_id IS NULL) OR (all_supervisors = 0 AND lecturer_id IS NOT NULL))"""))
            c.execute(text("""INSERT IGNORE INTO assessment_assignments (semester_id, course_id, lecturer_id, all_supervisors, note)
                SELECT s.id, co.id, NULL, 1, 'Tất cả thầy/cô có HD' FROM semesters s JOIN courses co
                WHERE s.academic_year='2023-2024' AND s.term=1 AND co.course_code IN ('PODE434277', 'POIS431184')"""))
            done.append("assessment_assignments: phân công tất cả GV hướng dẫn")
        for t in ("exam_version_questions", "exam_version_options"):
            if not c.execute(text("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:t"), {"t": t}).scalar():
                c.execute(text(_ddl(t)))
                done.append(f"tạo lại bảng {t}")
    return done


def run() -> None:
    from .services import moodle
    try:
        done = upgrade_schema()
        if done:
            print("Đã nâng cấp CSDL:", "; ".join(done))
    except Exception as ex:  # noqa: BLE001 – CSDL chưa khởi tạo: bước 2 sẽ tạo đúng lược đồ
        print("Bỏ qua nâng cấp CSDL:", ex)
        return
    try:
        if moodle.moodle_available():
            n = moodle.install_bridge()
            print(f"Cầu nối Moodle: {n} câu lệnh" + ("" if moodle.offlinequiz_available()
                  else " (Moodle chưa cài Offline Quiz – chưa đọc được bài thi giấy)"))
    except Exception as ex:  # noqa: BLE001
        print("Chưa cài được cầu nối Moodle:", ex)
