"""Nâng cấp CSDL assessment_db đã cài từ phiên bản trước (chạy tự động mỗi khi hệ thống khởi động, an toàn khi chạy lại).

- question_bank.bloom_level_id cho phép NULL: câu nhập hàng loạt ở trạng thái "chưa gán" (gán CLO/Bloom sau bằng file).
- exams.moodle_offlinequiz_id: bài thi giấy do Moodle (Offline Quiz) sinh đề, nhận diện phiếu và chấm.
- exam_attempts: moodle_attempt_id duy nhất theo từng bài KT (id lượt Quiz và id kết quả Offline Quiz có thể trùng nhau).
- students.student_code VARCHAR(100): khớp độ dài mã số (idnumber/username) của Moodle.
- Tạo lại exam_version_questions, exam_version_options nếu thiếu (bản thử nghiệm từng bỏ 2 bảng này).
- assessment_assignments: cho phép phân công "Tất cả thầy/cô có hướng dẫn" (TLCN, KLTN) – khóa chính id, lecturer_id NULL,
  cột all_supervisors; bổ sung 2 dòng phân công TLCN/KLTN của dữ liệu tham chiếu.
- Quản lý theo CTĐT (bản 15/10): thông tin CTĐT, trình độ năng lực PLO/PI, cấu trúc + mô tả học phần, học kỳ/khối kiến thức
  của học phần trong CTĐT, mức đáp ứng PI của học phần; nạp CTĐT CNTT 2026 và KTDL 2026 (database/04_ctdt_2026.sql).
- Bài KT nhập điểm (exam_type = manual, câu/ý chấm tay question_type = manual, response_status = graded), chấm phiếu
  trên hệ thống (source = scan), chọn bài gộp minh chứng CLO (counts_for_clo), bài phụ đạo (parent_exam_id, target_students).
- Đề của môn: exams.class_section_id cho phép NULL, thêm course_id và source_exam_id (bài giao/sao từ đề nào).
- clo_pi_mapping (góp ý F2a): CLO → PI → PLO; dữ liệu cũ được sinh CLO → PI từ ma trận CLO – PLO đang có.
- Đề cương chi tiết có phiên bản (góp ý F1): course_syllabi, syllabus_references, syllabus_assessments,
  syllabus_assessment_clos, outline_clos; nội dung, số tiết và hoạt động dạy học của từng chương (course_outlines).
- question_moodle_links (góp ý F3): trạng thái đồng bộ câu hỏi theo từng khóa học Moodle, phát hiện câu bị sửa ở cả hai bên.
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


NEW_COLUMNS = [
    ("programs", "name_en", "VARCHAR(255) NULL COMMENT 'Tên CTĐT tiếng Anh'"),
    ("programs", "faculty", "VARCHAR(150) NULL COMMENT 'Khoa quản lý'"),
    ("programs", "major_code", "VARCHAR(20) NULL COMMENT 'Mã ngành, VD 7480201'"),
    ("programs", "cohort_year", "SMALLINT NULL COMMENT 'Áp dụng từ khóa tuyển sinh, VD 2026'"),
    ("programs", "total_credits", "SMALLINT NULL COMMENT 'Khối lượng học tập (tín chỉ)'"),
    ("programs", "decision_no", "VARCHAR(100) NULL COMMENT 'Số quyết định ban hành CTĐT'"),
    ("programs", "objective", "TEXT NULL COMMENT 'Mục tiêu chung của CTĐT'"),
    ("plos", "competency_level", "TINYINT NULL COMMENT 'Trình độ năng lực của PLO (thang 1–6)'"),
    ("plos", "plo_type", "VARCHAR(30) NULL COMMENT 'CĐR chung hoặc CĐR chuyên biệt'"),
    ("performance_indicators", "competency_level", "TINYINT NULL COMMENT 'Trình độ năng lực của PI (thang 1–6)'"),
    ("courses", "credits_theory", "TINYINT NULL COMMENT 'Số tín chỉ lý thuyết'"),
    ("courses", "credits_practice", "TINYINT NULL COMMENT 'Số tín chỉ thí nghiệm/thực hành/thực tập'"),
    ("courses", "course_structure", "VARCHAR(30) NULL COMMENT 'Cấu trúc học phần, VD 3(2:1:6)'"),
    ("courses", "prerequisites", "VARCHAR(255) NULL COMMENT 'Mã học phần trước, tiên quyết'"),
    ("courses", "description", "TEXT NULL COMMENT 'Mô tả vắn tắt học phần (đề cương)'"),
    ("program_courses", "semester_no", "TINYINT NULL COMMENT 'Học kỳ trong kế hoạch giảng dạy (1–8)'"),
    ("program_courses", "knowledge_block", "VARCHAR(150) NULL COMMENT 'Khối kiến thức, VD Kiến thức cơ sở ngành'"),
    ("program_courses", "is_elective", "BOOLEAN NOT NULL DEFAULT FALSE COMMENT '1 = học phần tự chọn'"),
    ("pi_courses", "level", "VARCHAR(2) NULL COMMENT 'Mức đáp ứng của học phần với PI: I, R, M hoặc trình độ 1–6 (Phụ lục II)'"),
    ("exams", "counts_for_clo", "BOOLEAN NOT NULL DEFAULT TRUE COMMENT '1 = dùng làm minh chứng tổng hợp CLO của lớp (gộp các bài được chọn)' AFTER last_synced_at"),
    ("exams", "parent_exam_id", "INT NULL COMMENT 'Bài phụ đạo: bài KT gốc' AFTER counts_for_clo"),
    ("exams", "target_students", "TEXT NULL COMMENT 'Bài phụ đạo: MSSV các SV được giao (cách nhau dấu phẩy)' AFTER parent_exam_id"),
    ("exam_attempts", "time_limit_sec", "INT NULL COMMENT 'Giới hạn thời gian của Quiz khi làm bài (giây; NULL = không giới hạn)'"),
    ("exam_attempts", "last_answer_at", "DATETIME NULL COMMENT 'Lần cuối SV chọn/đổi một đáp án (từ các bước question engine của Moodle)'"),
    ("exam_attempts", "finished_by_timeout", "BOOLEAN NULL COMMENT '1 = bài được nộp khi hết giờ (Moodle tự nộp), không do SV bấm nộp'"),
    ("item_level_results", "first_answer_at", "DATETIME NULL COMMENT 'Lần đầu SV chọn đáp án câu này (bài trên Moodle Quiz)'"),
    ("item_level_results", "last_answer_at", "DATETIME NULL COMMENT 'Lần cuối SV chọn/đổi đáp án câu này'"),
    ("item_level_results", "n_answer_saves", "SMALLINT NULL COMMENT 'Số lần lưu đáp án của câu (> 1 = có đổi đáp án)'"),
    ("item_level_results", "response_time_sec", "DECIMAL(8,1) NULL COMMENT 'Thời gian trả lời câu (giây) = khoảng cách tới lần chọn đáp án liền trước trong lượt làm'"),
    ("exams", "course_id", "INT NULL COMMENT 'Đề của môn (tạo ở trang môn học): môn học; giao cho lớp HP khi xuất' AFTER class_section_id"),
    ("exams", "paper_settings", "TEXT NULL COMMENT 'Bài giấy chấm trên hệ thống: JSON tùy chọn in đề và bố cục phiếu (phiếu quét được đọc theo đúng bố cục đã in)' AFTER target_students"),
    ("exams", "source_exam_id", "INT NULL COMMENT 'Bài được giao/sao từ đề này (đề của môn hoặc bài của lớp khác)' AFTER paper_settings"),
    ("course_outlines", "content", "TEXT NULL COMMENT 'Nội dung chi tiết của chương' AFTER chapter_name"),
    ("course_outlines", "theory_hours", "SMALLINT NULL COMMENT 'Số tiết lý thuyết' AFTER content"),
    ("course_outlines", "practice_hours", "SMALLINT NULL COMMENT 'Số tiết thực hành' AFTER theory_hours"),
    ("course_outlines", "teaching_activities", "TEXT NULL COMMENT 'Hoạt động dạy và học' AFTER practice_hours"),
]

NEW_TABLES = ("question_moodle_links", "course_syllabi", "syllabus_references", "syllabus_assessments", "syllabus_assessment_clos", "outline_clos")

# (bảng, tên ràng buộc CHECK, biểu thức mới, chuỗi nhận biết bản mới trong biểu thức đang có)
NEW_CHECKS = [
    ("question_bank", "ck_qb_type", "question_type IN ('multichoice','manual')", "manual"),
    ("exams", "ck_exam_type", "exam_type IN ('online','paper','manual')", "manual"),
    ("exam_attempts", "ck_att_source", "source IN ('moodle','paper','scan','manual')", "scan"),
    ("item_level_results", "ck_ilr_status", "response_status IN ('answered','blank','absent','graded')", "graded"),
    ("item_level_results", "ck_ilr_consistency",
     "(response_status = 'answered' AND selected_option_id IS NOT NULL) "
     "OR (response_status = 'graded' AND selected_option_id IS NULL AND score_earned >= 0) "
     "OR (response_status IN ('blank','absent') AND selected_option_id IS NULL AND is_correct = FALSE AND score_earned = 0)", "graded"),
    ("sync_runs", "ck_sync_kind", "kind IN ('moodle','paper','scan','manual','analyze')", "scan"),
]


def _check_clause(c, table, name):
    return c.execute(text("""SELECT cc.CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS cc
                             JOIN information_schema.TABLE_CONSTRAINTS tc ON tc.CONSTRAINT_SCHEMA = cc.CONSTRAINT_SCHEMA
                               AND tc.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
                             WHERE cc.CONSTRAINT_SCHEMA = DATABASE() AND tc.TABLE_NAME = :t AND cc.CONSTRAINT_NAME = :n"""),
                     {"t": table, "n": name}).scalar()


def _upgrade_clo_pi(c, done: list) -> None:
    """Góp ý F2a: thêm bảng clo_pi_mapping; CLO cũ (chỉ có CLO → PLO) được gắn PI tương ứng để ma trận CLO – PLO không đổi."""
    from .services.outcomes import backfill_clo_pi
    if not c.execute(text("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='clo_pi_mapping'")).scalar():
        c.execute(text(_ddl("clo_pi_mapping")))
        c.execute(text("CREATE INDEX ix_cpi_pi ON clo_pi_mapping (pi_id)"))
        n = backfill_clo_pi(c)
        done.append(f"clo_pi_mapping (sinh {n} ánh xạ CLO → PI từ CLO → PLO)")


def _upgrade_new_tables(c, done: list) -> None:
    """Bảng mới: đồng bộ câu hỏi theo khóa Moodle (F3), đề cương có phiên bản (F1; cột mới của course_outlines ở NEW_COLUMNS)."""
    for t in NEW_TABLES:
        if not c.execute(text("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:t"), {"t": t}).scalar():
            c.execute(text(_ddl(t)))
            done.append(f"bảng {t}")


def _upgrade_v3(c, done: list) -> None:
    """Các cột/ràng buộc của bản quản lý theo CTĐT, nhập điểm, chấm phiếu, phụ đạo."""
    for table, col, ddl in NEW_COLUMNS:
        if _col(c, table, col) is None:
            c.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
            done.append(f"{table}.{col}")
    if not c.execute(text("""SELECT 1 FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE()
                             AND TABLE_NAME='exams' AND CONSTRAINT_NAME='fk_exam_parent'""")).scalar():
        c.execute(text("ALTER TABLE exams ADD CONSTRAINT fk_exam_parent FOREIGN KEY (parent_exam_id) REFERENCES exams(id) ON DELETE SET NULL"))
        done.append("exams.fk_exam_parent")
    # đề của môn: bài KT chưa giao lớp HP (class_section_id NULL, course_id = môn) – giao cho các lớp khi xuất
    if _col(c, "exams", "class_section_id") == "NO":
        c.execute(text("ALTER TABLE exams MODIFY class_section_id INT NULL COMMENT 'Lớp HP của bài KT; NULL = đề của môn chưa giao lớp (course_id)'"))
        done.append("exams.class_section_id NULL")
    for name, ddl in (("fk_exam_course", "FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT"),
                      ("fk_exam_source", "FOREIGN KEY (source_exam_id) REFERENCES exams(id) ON DELETE SET NULL")):
        if not c.execute(text("""SELECT 1 FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE()
                                 AND TABLE_NAME='exams' AND CONSTRAINT_NAME=:n"""), {"n": name}).scalar():
            c.execute(text(f"ALTER TABLE exams ADD CONSTRAINT {name} {ddl}"))
            done.append(f"exams.{name}")
    for table, name, clause, marker in NEW_CHECKS:
        cur = _check_clause(c, table, name)
        if cur is not None and marker in cur:
            continue
        if cur is not None:
            c.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT {name}"))
        c.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({clause})"))
        done.append(f"{table}.{name}")
    view = c.execute(text("""SELECT VIEW_DEFINITION FROM information_schema.VIEWS WHERE TABLE_SCHEMA=DATABASE()
                             AND TABLE_NAME='v_question_integrity'""")).scalar()
    if view is not None and "question_type" not in view:
        import re
        sql = (_schema_sql())
        c.execute(text(re.search(r"CREATE OR REPLACE VIEW v_question_integrity AS.*?;", sql, re.S).group(0).rstrip(";")))
        done.append("v_question_integrity")


def _schema_sql() -> str:
    from pathlib import Path
    return (Path(__file__).resolve().parents[2] / "database" / "01_schema.sql").read_text(encoding="utf-8")


def load_ctdt_2026() -> int:
    """Nạp hai CTĐT 2026 (CNTT, KTDL) nếu CSDL chưa có – chạy lại an toàn (INSERT IGNORE / không ghi đè)."""
    from pathlib import Path
    from .services.moodle import split_statements
    f = Path(__file__).resolve().parents[2] / "database" / "04_ctdt_2026.sql"
    if not f.exists():
        return 0
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        n = 0
        for st in split_statements(f.read_text(encoding="utf-8")):
            cur.execute(st); n += 1
        raw.commit()
        return n
    finally:
        raw.close()


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
        _upgrade_v3(c, done)
        _upgrade_clo_pi(c, done)
        _upgrade_new_tables(c, done)
        need_ctdt = not c.execute(text("SELECT 1 FROM programs WHERE code IN ('CNTT-2026','KTDL-2026') LIMIT 1")).scalar()
    if need_ctdt and load_ctdt_2026():
        done.append("nạp CTĐT CNTT 2026 và KTDL 2026")
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
