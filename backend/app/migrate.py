"""Nâng cấp CSDL assessment_db đã cài từ phiên bản trước (chạy tự động mỗi khi hệ thống khởi động, an toàn khi chạy lại).

- question_bank.bloom_level_id cho phép NULL: câu nhập hàng loạt ở trạng thái "chưa gán" (gán CLO/Bloom sau bằng file).
- exams.moodle_offlinequiz_id: bài thi giấy do Moodle (Offline Quiz) sinh đề, nhận diện phiếu và chấm.
- exam_attempts: moodle_attempt_id duy nhất theo từng bài KT (id lượt Quiz và id kết quả Offline Quiz có thể trùng nhau).
- students.student_code VARCHAR(100): khớp độ dài mã số (idnumber/username) của Moodle.
- Cài lại cầu nối đọc Moodle (view + sp_sync_exam) cho khớp phiên bản mã nguồn.
"""
from sqlalchemy import text

from .database import engine


def _col(c, table, col):
    return c.execute(text("""SELECT IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE()
                             AND TABLE_NAME=:t AND COLUMN_NAME=:c"""), {"t": table, "c": col}).scalar()


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
