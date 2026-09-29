-- =============================================================
-- Chạy trong HeidiSQL (F9) – tạo CSDL assessment_db: 39 bảng + dữ liệu tham chiếu
-- (tương đương lệnh: python -m app.cli init-db)
-- =============================================================
-- =====================================================================
--  HỆ THỐNG HỖ TRỢ GIẢNG VIÊN KIỂM TRA, ĐÁNH GIÁ VÀ PHÂN TÍCH
--  MỨC ĐỘ ĐẠT CHUẨN ĐẦU RA  –  CSDL phiên bản 2 (theo biểu mẫu HCMUTE)
--  Nhóm 01 – Tiểu luận chuyên ngành
--  DBMS: MySQL 8.0.16+
--
--  Căn cứ nghiệp vụ:
--   * BM2  : Kế hoạch & báo cáo tổng kết đo lường CĐR CTĐT (PLO, PI, chỉ tiêu, chu kỳ)
--   * BM3b : Kế hoạch KT-ĐG mức độ đạt cho từng CĐR CTĐT (PI, môn lấy minh chứng, GV)
--   * BM3c : Kết quả tổng hợp của từng PI cho CĐR CTĐT
--   * BM6a : Kế hoạch KT-ĐG mức độ đạt cho từng CĐR môn học (CLO)
--   * BM6b : Kết quả tổng hợp của từng CĐR môn học
--   * BM6c/6d : Bảng minh chứng đo lường từ kết quả kiểm tra (1 hoặc nhiều bài KT)
--   * Phân công đánh giá PIs theo học kỳ
--
--  39 bảng, 7 nhóm:
--   A. Người dùng & tổ chức      (4)  users, lecturers, students, semesters
--   B. Chương trình & CĐR CTĐT   (6)  programs, plos, plo_measurement_plans,
--                                     performance_indicators, program_courses, pi_courses
--   C. Học phần & CĐR môn học    (5)  courses, course_outlines, bloom_levels, clos, clo_plo_mapping
--   D. Kế hoạch đo lường         (4)  clo_assessment_plans, pi_assessment_plans,
--                                     pi_plan_clos, assessment_assignments
--   E. Lớp học phần & ngân hàng  (5)  class_sections, enrollments,
--                                     question_bank, question_options, question_clo_mapping
--   F. Đề thi                    (5)  exams, exam_questions, exam_versions,
--                                     exam_version_questions, exam_version_options
--   G. Kết quả & báo cáo         (10) exam_attempts, item_level_results, item_statistics,
--                                     attempt_clo_results, clo_results, pi_results, plo_results,
--                                     personalized_learning_paths, learning_path_items, sync_runs
-- =====================================================================

CREATE DATABASE IF NOT EXISTS assessment_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE assessment_db;

SET FOREIGN_KEY_CHECKS = 0;
DROP VIEW IF EXISTS v_question_integrity, v_clo_plo_matrix, v_course_clo_summary, v_student_clo_radar;
DROP TABLE IF EXISTS sync_runs, learning_path_items, personalized_learning_paths,
  plo_results, pi_results, clo_results, attempt_clo_results, item_statistics,
  item_level_results, exam_attempts,
  exam_version_options, exam_version_questions, exam_versions, exam_questions, exams,
  question_clo_mapping, question_options, question_bank, enrollments, class_sections,
  assessment_assignments, pi_plan_clos, pi_assessment_plans, clo_assessment_plans,
  clo_plo_mapping, clos, bloom_levels, course_outlines, courses,
  pi_courses, program_courses, performance_indicators, plo_measurement_plans, plos, programs,
  semesters, students, lecturers, users;
SET FOREIGN_KEY_CHECKS = 1;

-- =====================================================================
-- A. NGƯỜI DÙNG & TỔ CHỨC
-- =====================================================================
CREATE TABLE users (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  username       VARCHAR(50)  NOT NULL,
  password_hash  VARCHAR(255) NOT NULL,
  full_name      VARCHAR(100) NOT NULL,
  email          VARCHAR(150) NULL,
  role           VARCHAR(20)  NOT NULL COMMENT 'admin = Bộ môn/Trưởng BM; lecturer; student',
  is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_users_username UNIQUE (username),
  CONSTRAINT uq_users_email    UNIQUE (email),
  CONSTRAINT ck_users_role     CHECK (role IN ('admin','lecturer','student'))
) ENGINE=InnoDB COMMENT='Tài khoản đăng nhập';

CREATE TABLE lecturers (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  user_id        INT          NULL,
  lecturer_code  VARCHAR(20)  NOT NULL,
  full_name      VARCHAR(100) NOT NULL,
  department     VARCHAR(150) NULL COMMENT 'Bộ môn',
  CONSTRAINT fk_lecturer_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT uq_lecturer_user UNIQUE (user_id),
  CONSTRAINT uq_lecturer_code UNIQUE (lecturer_code)
) ENGINE=InnoDB COMMENT='Giảng viên';

CREATE TABLE students (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  user_id         INT          NULL,
  student_code    VARCHAR(20)  NOT NULL,
  full_name       VARCHAR(100) NOT NULL,
  class_name      VARCHAR(50)  NULL COMMENT 'Lớp sinh hoạt',
  moodle_user_id  BIGINT       NULL COMMENT 'mdl_user.id',
  CONSTRAINT fk_student_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT uq_student_user   UNIQUE (user_id),
  CONSTRAINT uq_student_code   UNIQUE (student_code),
  CONSTRAINT uq_student_moodle UNIQUE (moodle_user_id)
) ENGINE=InnoDB COMMENT='Sinh viên';

CREATE TABLE semesters (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  academic_year  VARCHAR(9)   NOT NULL COMMENT 'VD 2023-2024',
  term           TINYINT      NOT NULL COMMENT '1 = HKI, 2 = HKII, 3 = HK hè',
  name           VARCHAR(50)  NOT NULL COMMENT 'VD HKI 23-24',
  start_date     DATE         NOT NULL,
  end_date       DATE         NOT NULL,
  CONSTRAINT uq_semester UNIQUE (academic_year, term),
  CONSTRAINT ck_semester_term  CHECK (term IN (1,2,3)),
  CONSTRAINT ck_semester_year  CHECK (academic_year REGEXP '^[0-9]{4}-[0-9]{4}$'),
  CONSTRAINT ck_semester_dates CHECK (end_date > start_date)
) ENGINE=InnoDB COMMENT='Học kỳ';

-- =====================================================================
-- B. CHƯƠNG TRÌNH ĐÀO TẠO & CĐR CTĐT (BM2, BM3b)
-- =====================================================================
CREATE TABLE programs (
  id                 INT AUTO_INCREMENT PRIMARY KEY,
  code               VARCHAR(20)  NOT NULL,
  name               VARCHAR(255) NOT NULL,
  level              VARCHAR(20)  NOT NULL DEFAULT 'Đại học',
  department         VARCHAR(150) NULL COMMENT 'Bộ môn quản lý CTĐT',
  target_pct         DECIMAL(5,2) NOT NULL DEFAULT 75.00 COMMENT 'Chỉ tiêu đạt CĐR CTĐT (%)',
  CONSTRAINT uq_program_code UNIQUE (code),
  CONSTRAINT ck_program_target CHECK (target_pct BETWEEN 0 AND 100)
) ENGINE=InnoDB COMMENT='Chương trình đào tạo';

CREATE TABLE plos (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  program_id   INT          NOT NULL,
  group_no     TINYINT      NOT NULL COMMENT 'Nhóm CĐR 1..4 (Kiến thức, Kỹ năng, ...)',
  plo_code     VARCHAR(10)  NOT NULL COMMENT 'VD 1.2',
  description  TEXT         NOT NULL,
  target_pct   DECIMAL(5,2) NOT NULL DEFAULT 75.00 COMMENT 'Chỉ tiêu đạt CĐR (%)',
  CONSTRAINT fk_plo_program FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE CASCADE,
  CONSTRAINT uq_plo_code UNIQUE (program_id, plo_code),
  CONSTRAINT ck_plo_target CHECK (target_pct BETWEEN 0 AND 100)
) ENGINE=InnoDB COMMENT='CĐR chương trình đào tạo (PLO)';

CREATE TABLE plo_measurement_plans (
  plo_id         INT          NOT NULL,
  round_no       TINYINT      NOT NULL COMMENT 'Lần đo 1, 2, ...',
  academic_year  VARCHAR(9)   NOT NULL COMMENT 'Năm học đo lường',
  target_pct     DECIMAL(5,2) NOT NULL,
  PRIMARY KEY (plo_id, round_no),
  CONSTRAINT fk_pmp_plo FOREIGN KEY (plo_id) REFERENCES plos(id) ON DELETE CASCADE,
  CONSTRAINT uq_pmp_year UNIQUE (plo_id, academic_year),
  CONSTRAINT ck_pmp_target CHECK (target_pct BETWEEN 0 AND 100)
) ENGINE=InnoDB COMMENT='Kế hoạch đo CĐR CTĐT theo năm học (BM2 – mục I)';

CREATE TABLE performance_indicators (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  plo_id       INT          NOT NULL,
  pi_code      VARCHAR(10)  NOT NULL COMMENT 'VD PI 1',
  description  TEXT         NOT NULL,
  CONSTRAINT fk_pi_plo FOREIGN KEY (plo_id) REFERENCES plos(id) ON DELETE CASCADE,
  CONSTRAINT uq_pi_code UNIQUE (plo_id, pi_code)
) ENGINE=InnoDB COMMENT='Chỉ số đánh giá (PI) của CĐR CTĐT';

-- =====================================================================
-- C. HỌC PHẦN & CĐR MÔN HỌC
-- =====================================================================
CREATE TABLE courses (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  course_code    VARCHAR(20)  NOT NULL COMMENT 'Mã môn học, VD DBMS330284',
  course_name    VARCHAR(255) NOT NULL,
  credits        TINYINT      NOT NULL,
  clo_target_pct DECIMAL(5,2) NOT NULL DEFAULT 75.00 COMMENT 'Chỉ tiêu đạt CĐR môn học (BM6a)',
  created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_course_code UNIQUE (course_code),
  CONSTRAINT ck_course_credits CHECK (credits > 0),
  CONSTRAINT ck_course_target  CHECK (clo_target_pct BETWEEN 0 AND 100)
) ENGINE=InnoDB COMMENT='Học phần / môn học';

CREATE TABLE program_courses (
  program_id  INT NOT NULL,
  course_id   INT NOT NULL,
  PRIMARY KEY (program_id, course_id),
  CONSTRAINT fk_pc_program FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE CASCADE,
  CONSTRAINT fk_pc_course  FOREIGN KEY (course_id)  REFERENCES courses(id)  ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='Môn học thuộc CTĐT';

CREATE TABLE pi_courses (
  pi_id      INT NOT NULL,
  course_id  INT NOT NULL,
  PRIMARY KEY (pi_id, course_id),
  CONSTRAINT fk_pic_pi     FOREIGN KEY (pi_id)     REFERENCES performance_indicators(id) ON DELETE CASCADE,
  CONSTRAINT fk_pic_course FOREIGN KEY (course_id) REFERENCES courses(id)                ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='Các môn học có PI xuất hiện (BM3b)';

CREATE TABLE course_outlines (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  course_id       INT          NOT NULL,
  chapter_number  TINYINT      NOT NULL,
  chapter_name    VARCHAR(255) NOT NULL,
  CONSTRAINT fk_outline_course FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
  CONSTRAINT uq_outline_chapter UNIQUE (course_id, chapter_number),
  CONSTRAINT ck_outline_chapter CHECK (chapter_number > 0)
) ENGINE=InnoDB COMMENT='Đề cương – chương';

CREATE TABLE bloom_levels (
  id       TINYINT      PRIMARY KEY,
  code     VARCHAR(20)  NOT NULL,
  name_vi  VARCHAR(50)  NOT NULL,
  CONSTRAINT uq_bloom_code UNIQUE (code),
  CONSTRAINT ck_bloom_id CHECK (id BETWEEN 1 AND 6)
) ENGINE=InnoDB COMMENT='Thang Bloom (Anderson & Krathwohl, 2001)';

CREATE TABLE clos (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  course_id       INT          NOT NULL,
  clo_code        VARCHAR(10)  NOT NULL COMMENT 'VD G1.1, CLO1',
  description     TEXT         NOT NULL,
  bloom_level_id  TINYINT      NULL COMMENT 'Mức nhận thức mục tiêu',
  CONSTRAINT fk_clo_course FOREIGN KEY (course_id)      REFERENCES courses(id)      ON DELETE CASCADE,
  CONSTRAINT fk_clo_bloom  FOREIGN KEY (bloom_level_id) REFERENCES bloom_levels(id) ON DELETE SET NULL,
  CONSTRAINT uq_clo_code UNIQUE (course_id, clo_code)
) ENGINE=InnoDB COMMENT='CĐR môn học (CLO)';

CREATE TABLE clo_plo_mapping (
  clo_id  INT     NOT NULL,
  plo_id  INT     NOT NULL,
  level   CHAR(1) NOT NULL COMMENT 'I = Giới thiệu, R = Củng cố, M = Thành thạo',
  PRIMARY KEY (clo_id, plo_id),
  CONSTRAINT fk_cpm_clo FOREIGN KEY (clo_id) REFERENCES clos(id) ON DELETE CASCADE,
  CONSTRAINT fk_cpm_plo FOREIGN KEY (plo_id) REFERENCES plos(id) ON DELETE CASCADE,
  CONSTRAINT ck_cpm_level CHECK (level IN ('I','R','M'))
) ENGINE=InnoDB COMMENT='Ma trận đóng góp CLO – PLO';

-- =====================================================================
-- D. KẾ HOẠCH ĐO LƯỜNG
-- =====================================================================
CREATE TABLE clo_assessment_plans (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  clo_id              INT          NOT NULL,
  semester_id         INT          NOT NULL COMMENT 'Thời gian lấy minh chứng',
  assessments_text    VARCHAR(255) NULL     COMMENT 'Các bài KT có CĐR xuất hiện, VD Quiz 1, 2',
  evidence_type       VARCHAR(10)  NOT NULL DEFAULT 'final' COMMENT 'Bài KT lấy minh chứng: process | final | any',
  method              VARCHAR(100) NOT NULL DEFAULT 'Bài KT trắc nghiệm' COMMENT 'Phương pháp KT-ĐG',
  cycle               VARCHAR(30)  NOT NULL DEFAULT '1 lần/HK',
  pass_threshold_pct  DECIMAL(5,2) NOT NULL DEFAULT 60.00 COMMENT 'SV đạt khi ≥ x% điểm tối đa các câu của CLO (BM6c)',
  target_pct          DECIMAL(5,2) NOT NULL DEFAULT 70.00 COMMENT 'Chỉ tiêu mong muốn: % SV đạt',
  CONSTRAINT fk_cap_clo      FOREIGN KEY (clo_id)      REFERENCES clos(id)      ON DELETE CASCADE,
  CONSTRAINT fk_cap_semester FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE RESTRICT,
  CONSTRAINT uq_cap UNIQUE (clo_id, semester_id),
  CONSTRAINT ck_cap_evidence  CHECK (evidence_type IN ('process','final','any')),
  CONSTRAINT ck_cap_threshold CHECK (pass_threshold_pct BETWEEN 0 AND 100),
  CONSTRAINT ck_cap_target    CHECK (target_pct BETWEEN 0 AND 100)
) ENGINE=InnoDB COMMENT='Kế hoạch KT-ĐG mức độ đạt CĐR môn học (BM6a)';

CREATE TABLE pi_assessment_plans (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  pi_id        INT          NOT NULL,
  course_id    INT          NOT NULL COMMENT 'Môn học sẽ lấy minh chứng',
  semester_id  INT          NOT NULL COMMENT 'Thời gian lấy minh chứng',
  method       VARCHAR(150) NOT NULL COMMENT 'Phương pháp kiểm tra, đánh giá',
  cycle        VARCHAR(30)  NOT NULL DEFAULT '2 năm/lần',
  target_pct   DECIMAL(5,2) NOT NULL DEFAULT 75.00 COMMENT 'Chỉ tiêu mong muốn',
  lecturer_id  INT          NULL COMMENT 'GV phụ trách',
  CONSTRAINT fk_pap_pi       FOREIGN KEY (pi_id)       REFERENCES performance_indicators(id) ON DELETE CASCADE,
  CONSTRAINT fk_pap_course   FOREIGN KEY (course_id)   REFERENCES courses(id)   ON DELETE RESTRICT,
  CONSTRAINT fk_pap_semester FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE RESTRICT,
  CONSTRAINT fk_pap_lecturer FOREIGN KEY (lecturer_id) REFERENCES lecturers(id) ON DELETE SET NULL,
  CONSTRAINT uq_pap UNIQUE (pi_id, semester_id),
  CONSTRAINT ck_pap_target CHECK (target_pct BETWEEN 0 AND 100)
) ENGINE=InnoDB COMMENT='Kế hoạch đo PI của CĐR CTĐT (BM2 – mục II, BM3b)';

CREATE TABLE pi_plan_clos (
  plan_id  INT NOT NULL,
  clo_id   INT NOT NULL,
  PRIMARY KEY (plan_id, clo_id),
  CONSTRAINT fk_ppc_plan FOREIGN KEY (plan_id) REFERENCES pi_assessment_plans(id) ON DELETE CASCADE,
  CONSTRAINT fk_ppc_clo  FOREIGN KEY (clo_id)  REFERENCES clos(id)                ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='CLO của môn lấy minh chứng cung cấp dữ liệu cho PI';

CREATE TABLE assessment_assignments (
  semester_id  INT          NOT NULL,
  course_id    INT          NOT NULL,
  lecturer_id  INT          NOT NULL,
  note         VARCHAR(255) NULL COMMENT 'VD Đánh giá theo 7 CĐR',
  PRIMARY KEY (semester_id, course_id, lecturer_id),
  CONSTRAINT fk_aa_semester FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE CASCADE,
  CONSTRAINT fk_aa_course   FOREIGN KEY (course_id)   REFERENCES courses(id)   ON DELETE CASCADE,
  CONSTRAINT fk_aa_lecturer FOREIGN KEY (lecturer_id) REFERENCES lecturers(id) ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='Phân công đánh giá PIs theo học kỳ';

-- =====================================================================
-- E. LỚP HỌC PHẦN & NGÂN HÀNG CÂU HỎI
-- =====================================================================
CREATE TABLE class_sections (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  course_id         INT          NOT NULL,
  semester_id       INT          NOT NULL,
  lecturer_id       INT          NOT NULL,
  section_code      VARCHAR(30)  NOT NULL COMMENT 'Mã lớp học phần, VD DBMS330284_01',
  moodle_course_id  BIGINT       NULL COMMENT 'mdl_course.id',
  CONSTRAINT fk_cs_course   FOREIGN KEY (course_id)   REFERENCES courses(id)   ON DELETE RESTRICT,
  CONSTRAINT fk_cs_semester FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE RESTRICT,
  CONSTRAINT fk_cs_lecturer FOREIGN KEY (lecturer_id) REFERENCES lecturers(id) ON DELETE RESTRICT,
  CONSTRAINT uq_cs_code   UNIQUE (semester_id, section_code),
  CONSTRAINT uq_cs_moodle UNIQUE (moodle_course_id)
) ENGINE=InnoDB COMMENT='Lớp học phần';

CREATE TABLE enrollments (
  class_section_id  INT         NOT NULL,
  student_id        INT         NOT NULL,
  status            VARCHAR(10) NOT NULL DEFAULT 'active',
  enrolled_at       TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (class_section_id, student_id),
  CONSTRAINT fk_enr_cs      FOREIGN KEY (class_section_id) REFERENCES class_sections(id) ON DELETE CASCADE,
  CONSTRAINT fk_enr_student FOREIGN KEY (student_id)       REFERENCES students(id)       ON DELETE CASCADE,
  CONSTRAINT ck_enr_status CHECK (status IN ('active','dropped'))
) ENGINE=InnoDB COMMENT='Danh sách lớp học phần';
CREATE INDEX ix_enr_student ON enrollments (student_id);

CREATE TABLE question_bank (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  course_id           INT          NOT NULL,
  outline_id          INT          NULL COMMENT 'Chương chứa kiến thức',
  bloom_level_id      TINYINT      NOT NULL,
  question_type       VARCHAR(30)  NOT NULL DEFAULT 'multichoice',
  content             TEXT         NOT NULL,
  moodle_question_id  BIGINT       NULL COMMENT 'mdl_question.id (phiên bản mới nhất)',
  is_cancelled        BOOLEAN      NOT NULL DEFAULT FALSE,
  cancel_reason       VARCHAR(255) NULL,
  created_by          INT          NULL,
  created_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_qb_course  FOREIGN KEY (course_id)      REFERENCES courses(id)         ON DELETE RESTRICT,
  CONSTRAINT fk_qb_outline FOREIGN KEY (outline_id)     REFERENCES course_outlines(id) ON DELETE SET NULL,
  CONSTRAINT fk_qb_bloom   FOREIGN KEY (bloom_level_id) REFERENCES bloom_levels(id)    ON DELETE RESTRICT,
  CONSTRAINT fk_qb_creator FOREIGN KEY (created_by)     REFERENCES users(id)           ON DELETE SET NULL,
  CONSTRAINT ck_qb_type CHECK (question_type IN ('multichoice'))
) ENGINE=InnoDB COMMENT='Ngân hàng câu hỏi (idnumber Moodle = QB-{id})';
CREATE INDEX ix_qb_course_active ON question_bank (course_id, is_cancelled);
CREATE INDEX ix_qb_moodle ON question_bank (moodle_question_id);

CREATE TABLE question_options (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  question_id       INT      NOT NULL,
  position          TINYINT  NOT NULL COMMENT 'Thứ tự gốc 1..n (= thứ tự <answer> trong XML)',
  opt_label         CHAR(1)  NOT NULL COMMENT 'A, B, C, D ...',
  content           TEXT     NOT NULL,
  is_correct        BOOLEAN  NOT NULL DEFAULT FALSE,
  moodle_answer_id  BIGINT   NULL COMMENT 'mdl_question_answers.id',
  correct_key       INT GENERATED ALWAYS AS (CASE WHEN is_correct THEN question_id END) VIRTUAL,
  CONSTRAINT fk_opt_question FOREIGN KEY (question_id) REFERENCES question_bank(id) ON DELETE CASCADE,
  CONSTRAINT uq_opt_position    UNIQUE (question_id, position),
  CONSTRAINT uq_opt_label       UNIQUE (question_id, opt_label),
  CONSTRAINT uq_opt_one_correct UNIQUE (correct_key),
  CONSTRAINT uq_opt_moodle      UNIQUE (moodle_answer_id),
  CONSTRAINT ck_opt_position CHECK (position BETWEEN 1 AND 10)
) ENGINE=InnoDB COMMENT='Phương án (mỗi câu tối đa 1 phương án đúng)';

CREATE TABLE question_clo_mapping (
  question_id  INT          NOT NULL,
  clo_id       INT          NOT NULL,
  weight       DECIMAL(3,2) NOT NULL DEFAULT 1.00 COMMENT 'Tỷ lệ điểm câu hỏi phân bổ cho CLO; tổng = 1.00',
  PRIMARY KEY (question_id, clo_id),
  CONSTRAINT fk_qcm_question FOREIGN KEY (question_id) REFERENCES question_bank(id) ON DELETE CASCADE,
  CONSTRAINT fk_qcm_clo      FOREIGN KEY (clo_id)      REFERENCES clos(id)          ON DELETE RESTRICT,
  CONSTRAINT ck_qcm_weight CHECK (weight > 0 AND weight <= 1)
) ENGINE=InnoDB COMMENT='Câu hỏi đo CLO nào (ma trận đề thi)';

-- =====================================================================
-- F. ĐỀ THI
-- =====================================================================
CREATE TABLE exams (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  class_section_id  INT          NOT NULL,
  exam_title        VARCHAR(255) NOT NULL,
  assessment_type   VARCHAR(10)  NOT NULL DEFAULT 'final' COMMENT 'process = Quá trình | final = Cuối kỳ',
  exam_type         VARCHAR(10)  NOT NULL DEFAULT 'online' COMMENT 'online (Moodle) | paper (giấy)',
  exam_date         DATE         NULL,
  duration_minutes  SMALLINT     NULL,
  max_score         DECIMAL(5,2) NOT NULL DEFAULT 10.00 COMMENT 'Thang điểm bài thi',
  moodle_quiz_id    BIGINT       NULL COMMENT 'mdl_quiz.id',
  status            VARCHAR(20)  NOT NULL DEFAULT 'Draft',
  publish_flag      BOOLEAN      NOT NULL DEFAULT FALSE,
  last_synced_at    DATETIME     NULL,
  created_by        INT          NULL,
  created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_exam_cs      FOREIGN KEY (class_section_id) REFERENCES class_sections(id) ON DELETE RESTRICT,
  CONSTRAINT fk_exam_creator FOREIGN KEY (created_by)       REFERENCES users(id)          ON DELETE SET NULL,
  CONSTRAINT uq_exam_moodle_quiz UNIQUE (moodle_quiz_id),
  CONSTRAINT ck_exam_assess   CHECK (assessment_type IN ('process','final')),
  CONSTRAINT ck_exam_type     CHECK (exam_type IN ('online','paper')),
  CONSTRAINT ck_exam_status   CHECK (status IN ('Draft','Published','Synced','Analyzed')),
  CONSTRAINT ck_exam_duration CHECK (duration_minutes IS NULL OR duration_minutes > 0),
  CONSTRAINT ck_exam_online   CHECK (exam_type = 'online' OR moodle_quiz_id IS NULL)
) ENGINE=InnoDB COMMENT='Bài kiểm tra / đề thi';

CREATE TABLE exam_questions (
  exam_id      INT          NOT NULL,
  question_id  INT          NOT NULL,
  order_index  SMALLINT     NOT NULL,
  points       DECIMAL(5,2) NOT NULL DEFAULT 1.00,
  PRIMARY KEY (exam_id, question_id),
  CONSTRAINT fk_eq_exam     FOREIGN KEY (exam_id)     REFERENCES exams(id)         ON DELETE CASCADE,
  CONSTRAINT fk_eq_question FOREIGN KEY (question_id) REFERENCES question_bank(id) ON DELETE RESTRICT,
  CONSTRAINT uq_eq_order  UNIQUE (exam_id, order_index),
  CONSTRAINT ck_eq_points CHECK (points > 0)
) ENGINE=InnoDB COMMENT='Câu hỏi trong đề (thứ tự gốc)';

CREATE TABLE exam_versions (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  exam_id       INT         NOT NULL,
  version_code  VARCHAR(10) NOT NULL COMMENT 'Mã đề, VD 101',
  CONSTRAINT fk_ev_exam FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
  CONSTRAINT uq_ev_code UNIQUE (exam_id, version_code)
) ENGINE=InnoDB COMMENT='Mã đề (bài thi giấy)';

CREATE TABLE exam_version_questions (
  version_id   INT      NOT NULL,
  question_id  INT      NOT NULL,
  position     SMALLINT NOT NULL COMMENT 'Số thứ tự câu trên mã đề',
  PRIMARY KEY (version_id, question_id),
  CONSTRAINT fk_evq_version  FOREIGN KEY (version_id)  REFERENCES exam_versions(id) ON DELETE CASCADE,
  CONSTRAINT fk_evq_question FOREIGN KEY (question_id) REFERENCES question_bank(id) ON DELETE RESTRICT,
  CONSTRAINT uq_evq_position UNIQUE (version_id, position)
) ENGINE=InnoDB COMMENT='Thứ tự câu hỏi trong từng mã đề';

CREATE TABLE exam_version_options (
  version_id       INT     NOT NULL,
  question_id      INT     NOT NULL,
  displayed_label  CHAR(1) NOT NULL COMMENT 'Nhãn in trên mã đề',
  option_id        INT     NOT NULL COMMENT 'Phương án gốc',
  PRIMARY KEY (version_id, question_id, displayed_label),
  CONSTRAINT fk_evo_evq    FOREIGN KEY (version_id, question_id)
    REFERENCES exam_version_questions(version_id, question_id) ON DELETE CASCADE,
  CONSTRAINT fk_evo_option FOREIGN KEY (option_id) REFERENCES question_options(id) ON DELETE RESTRICT,
  CONSTRAINT uq_evo_option UNIQUE (version_id, option_id)
) ENGINE=InnoDB COMMENT='Hoán vị phương án của từng mã đề';

-- =====================================================================
-- G. KẾT QUẢ & BÁO CÁO
-- =====================================================================
CREATE TABLE exam_attempts (
  id                 INT AUTO_INCREMENT PRIMARY KEY,
  exam_id            INT          NOT NULL,
  student_id         INT          NOT NULL,
  version_id         INT          NULL COMMENT 'Mã đề (bài giấy)',
  moodle_attempt_id  BIGINT       NULL COMMENT 'mdl_quiz_attempts.id',
  source             VARCHAR(10)  NOT NULL DEFAULT 'moodle',
  started_at         DATETIME     NULL,
  finished_at        DATETIME     NULL,
  status             VARCHAR(20)  NOT NULL,
  total_score        DECIMAL(6,2) NOT NULL DEFAULT 0.00 COMMENT 'Tổng điểm thô (Σ points)',
  CONSTRAINT fk_att_exam    FOREIGN KEY (exam_id)    REFERENCES exams(id)         ON DELETE CASCADE,
  CONSTRAINT fk_att_student FOREIGN KEY (student_id) REFERENCES students(id)      ON DELETE RESTRICT,
  CONSTRAINT fk_att_version FOREIGN KEY (version_id) REFERENCES exam_versions(id) ON DELETE RESTRICT,
  CONSTRAINT uq_att_exam_student UNIQUE (exam_id, student_id),
  CONSTRAINT uq_att_moodle UNIQUE (moodle_attempt_id),
  CONSTRAINT ck_att_source CHECK (source IN ('moodle','paper')),
  CONSTRAINT ck_att_status CHECK (status IN ('finished','absent')),
  CONSTRAINT ck_att_score  CHECK (total_score >= 0),
  CONSTRAINT ck_att_absent CHECK (status <> 'absent' OR (started_at IS NULL AND total_score = 0))
) ENGINE=InnoDB COMMENT='Lượt thi được tính (1 SV / 1 bài KT)';

CREATE TABLE item_level_results (
  id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
  attempt_id          INT          NOT NULL,
  question_id         INT          NOT NULL,
  selected_option_id  INT          NULL COMMENT 'Phương án GỐC sau Reverse Shuffle',
  response_status     VARCHAR(20)  NOT NULL COMMENT 'answered | blank | absent',
  is_correct          BOOLEAN      NOT NULL DEFAULT FALSE,
  score_earned        DECIMAL(5,2) NOT NULL DEFAULT 0.00,
  CONSTRAINT fk_ilr_attempt  FOREIGN KEY (attempt_id)         REFERENCES exam_attempts(id)    ON DELETE CASCADE,
  CONSTRAINT fk_ilr_question FOREIGN KEY (question_id)        REFERENCES question_bank(id)    ON DELETE RESTRICT,
  CONSTRAINT fk_ilr_option   FOREIGN KEY (selected_option_id) REFERENCES question_options(id) ON DELETE RESTRICT,
  CONSTRAINT uq_ilr UNIQUE (attempt_id, question_id),
  CONSTRAINT ck_ilr_status CHECK (response_status IN ('answered','blank','absent')),
  CONSTRAINT ck_ilr_consistency CHECK (
        (response_status =  'answered' AND selected_option_id IS NOT NULL)
     OR (response_status <> 'answered' AND selected_option_id IS NULL
         AND is_correct = FALSE AND score_earned = 0))
) ENGINE=InnoDB COMMENT='Kết quả từng câu';
CREATE INDEX ix_ilr_question ON item_level_results (question_id);

CREATE TABLE item_statistics (
  exam_id      INT          NOT NULL,
  question_id  INT          NOT NULL,
  n_students   INT          NOT NULL COMMENT 'Số SV dự thi',
  p_value      DECIMAL(5,4) NULL COMMENT 'Độ khó p',
  di_value     DECIMAL(5,4) NULL COMMENT 'Độ phân biệt DI (nhóm 27%)',
  computed_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (exam_id, question_id),
  CONSTRAINT fk_is_eq FOREIGN KEY (exam_id, question_id)
    REFERENCES exam_questions(exam_id, question_id) ON DELETE CASCADE,
  CONSTRAINT ck_is_p  CHECK (p_value  BETWEEN 0 AND 1),
  CONSTRAINT ck_is_di CHECK (di_value BETWEEN -1 AND 1)
) ENGINE=InnoDB COMMENT='Chỉ số CTT của câu hỏi trong bài KT';

CREATE TABLE attempt_clo_results (
  attempt_id    INT          NOT NULL,
  clo_id        INT          NOT NULL,
  score_earned  DECIMAL(6,2) NOT NULL COMMENT 'Điểm các câu thuộc CLO',
  score_max     DECIMAL(6,2) NOT NULL COMMENT 'Điểm tối đa các câu thuộc CLO',
  score_pct     DECIMAL(5,2) NOT NULL,
  is_achieved   BOOLEAN      NOT NULL COMMENT 'score_pct ≥ pass_threshold_pct',
  PRIMARY KEY (attempt_id, clo_id),
  CONSTRAINT fk_acr_attempt FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id) ON DELETE CASCADE,
  CONSTRAINT fk_acr_clo     FOREIGN KEY (clo_id)     REFERENCES clos(id)          ON DELETE RESTRICT,
  CONSTRAINT ck_acr_score CHECK (score_max > 0 AND score_earned BETWEEN 0 AND score_max),
  CONSTRAINT ck_acr_pct   CHECK (score_pct BETWEEN 0 AND 100)
) ENGINE=InnoDB COMMENT='Minh chứng từng SV cho từng CLO (BM6c/6d)';

CREATE TABLE clo_results (
  class_section_id  INT          NOT NULL,
  clo_id            INT          NOT NULL,
  n_evaluated       INT          NOT NULL COMMENT 'Tổng số SV đánh giá (cộng dồn các bài KT)',
  n_achieved        INT          NOT NULL COMMENT 'Tổng số SV đạt yêu cầu',
  achieved_pct      DECIMAL(5,2) NOT NULL,
  target_pct        DECIMAL(5,2) NOT NULL,
  is_achieved       BOOLEAN      NOT NULL,
  analysis          TEXT         NULL COMMENT 'Đánh giá kết quả số liệu tổng hợp',
  improvement       TEXT         NULL COMMENT 'Những hành động cải tiến',
  computed_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (class_section_id, clo_id),
  CONSTRAINT fk_cr_cs  FOREIGN KEY (class_section_id) REFERENCES class_sections(id) ON DELETE CASCADE,
  CONSTRAINT fk_cr_clo FOREIGN KEY (clo_id)           REFERENCES clos(id)           ON DELETE RESTRICT,
  CONSTRAINT ck_cr_counts CHECK (n_evaluated > 0 AND n_achieved BETWEEN 0 AND n_evaluated)
) ENGINE=InnoDB COMMENT='Kết quả tổng hợp CĐR môn học theo lớp HP (BM6b)';

CREATE TABLE pi_results (
  plan_id       INT          NOT NULL,
  n_evaluated   INT          NOT NULL,
  n_achieved    INT          NOT NULL,
  achieved_pct  DECIMAL(5,2) NOT NULL,
  target_pct    DECIMAL(5,2) NOT NULL,
  is_achieved   BOOLEAN      NOT NULL,
  computed_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (plan_id),
  CONSTRAINT fk_pr_plan FOREIGN KEY (plan_id) REFERENCES pi_assessment_plans(id) ON DELETE CASCADE,
  CONSTRAINT ck_pr_counts CHECK (n_evaluated > 0 AND n_achieved BETWEEN 0 AND n_evaluated)
) ENGINE=InnoDB COMMENT='Kết quả tổng hợp từng PI (BM3c)';

CREATE TABLE plo_results (
  plo_id                INT          NOT NULL,
  academic_year         VARCHAR(9)   NOT NULL,
  n_evaluated           INT          NOT NULL,
  n_achieved            INT          NOT NULL,
  achieved_pct          DECIMAL(5,2) NOT NULL,
  target_pct            DECIMAL(5,2) NOT NULL,
  is_achieved           BOOLEAN      NOT NULL,
  data_summary          TEXT         NULL COMMENT 'Tổng hợp dữ liệu đã đánh giá',
  analysis              TEXT         NULL COMMENT 'Đánh giá kết quả số liệu tổng hợp',
  improvement_actions   TEXT         NULL COMMENT 'Những hành động cải tiến',
  improvement_results   TEXT         NULL COMMENT 'Kết quả của các cải tiến đã thực hiện',
  evidence_tools        TEXT         NULL COMMENT 'Công cụ đánh giá, lưu trữ minh chứng',
  computed_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (plo_id, academic_year),
  CONSTRAINT fk_plr_plo FOREIGN KEY (plo_id) REFERENCES plos(id) ON DELETE CASCADE,
  CONSTRAINT ck_plr_counts CHECK (n_evaluated > 0 AND n_achieved BETWEEN 0 AND n_evaluated)
) ENGINE=InnoDB COMMENT='Kết quả đo CĐR CTĐT theo năm học (BM2 báo cáo tổng kết, BM3b)';

CREATE TABLE personalized_learning_paths (
  id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
  attempt_id              INT      NOT NULL,
  generated_date          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  diagnostic_summary      TEXT     NULL,
  recommended_study_plan  TEXT     NULL,
  CONSTRAINT fk_plp_attempt FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id) ON DELETE CASCADE,
  CONSTRAINT uq_plp_attempt UNIQUE (attempt_id)
) ENGINE=InnoDB COMMENT='Lộ trình học tập cá nhân';

CREATE TABLE learning_path_items (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  path_id     BIGINT       NOT NULL,
  clo_id      INT          NOT NULL,
  outline_id  INT          NULL COMMENT 'Chương cần ôn',
  priority    TINYINT      NOT NULL COMMENT '1 = cần ôn trước nhất',
  gap_pct     DECIMAL(5,2) NOT NULL COMMENT 'Khoảng cách tới ngưỡng đạt',
  CONSTRAINT fk_lpi_path    FOREIGN KEY (path_id)    REFERENCES personalized_learning_paths(id) ON DELETE CASCADE,
  CONSTRAINT fk_lpi_clo     FOREIGN KEY (clo_id)     REFERENCES clos(id)            ON DELETE RESTRICT,
  CONSTRAINT fk_lpi_outline FOREIGN KEY (outline_id) REFERENCES course_outlines(id) ON DELETE SET NULL,
  CONSTRAINT uq_lpi UNIQUE (path_id, clo_id, outline_id),
  CONSTRAINT ck_lpi_gap CHECK (gap_pct > 0)
) ENGINE=InnoDB COMMENT='Mục khuyến nghị ôn tập (CLO chưa đạt)';

CREATE TABLE sync_runs (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  exam_id      INT         NOT NULL,
  kind         VARCHAR(10) NOT NULL DEFAULT 'moodle' COMMENT 'moodle | paper | analyze',
  started_at   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at  DATETIME    NULL,
  status       VARCHAR(20) NOT NULL DEFAULT 'running',
  n_attempts   INT         NULL,
  n_absent     INT         NULL,
  message      TEXT        NULL,
  CONSTRAINT fk_sync_exam FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
  CONSTRAINT ck_sync_kind   CHECK (kind IN ('moodle','paper','analyze')),
  CONSTRAINT ck_sync_status CHECK (status IN ('running','success','failed'))
) ENGINE=InnoDB COMMENT='Nhật ký đồng bộ / nhập kết quả / phân tích';

-- =====================================================================
-- VIEW
-- =====================================================================
-- Câu hỏi vi phạm ràng buộc nhiều dòng (tổng trọng số CLO ≠ 1; không đúng 1 đáp án đúng; < 2 phương án)
CREATE OR REPLACE VIEW v_question_integrity AS
SELECT q.id AS question_id,
       (SELECT COALESCE(SUM(weight),0) FROM question_clo_mapping m WHERE m.question_id = q.id) AS total_weight,
       (SELECT COUNT(*) FROM question_options o WHERE o.question_id = q.id)                   AS n_options,
       (SELECT COUNT(*) FROM question_options o WHERE o.question_id = q.id AND o.is_correct)   AS n_correct
FROM question_bank q
HAVING total_weight <> 1.00 OR n_options < 2 OR n_correct <> 1;

-- Ma trận CLO – PLO của một môn
CREATE OR REPLACE VIEW v_clo_plo_matrix AS
SELECT c.course_id, c.clo_code, p.plo_code, m.level
FROM clo_plo_mapping m JOIN clos c ON c.id = m.clo_id JOIN plos p ON p.id = m.plo_id;

-- Tổng hợp CĐR môn học theo học phần + học kỳ (gộp các lớp HP) – BM6b cấp môn
CREATE OR REPLACE VIEW v_course_clo_summary AS
SELECT cs.course_id, cs.semester_id, r.clo_id, c.clo_code,
       SUM(r.n_evaluated) AS n_evaluated, SUM(r.n_achieved) AS n_achieved,
       ROUND(100 * SUM(r.n_achieved) / SUM(r.n_evaluated), 2) AS achieved_pct,
       MAX(r.target_pct) AS target_pct
FROM clo_results r
JOIN class_sections cs ON cs.id = r.class_section_id
JOIN clos c ON c.id = r.clo_id
GROUP BY cs.course_id, cs.semester_id, r.clo_id, c.clo_code;

-- Dữ liệu Radar Chart của SV: điểm từng CLO so với ngưỡng đạt
CREATE OR REPLACE VIEW v_student_clo_radar AS
SELECT a.id AS attempt_id, a.exam_id, a.student_id, c.clo_code, r.score_pct, r.is_achieved,
       COALESCE(p.pass_threshold_pct, 60.00) AS pass_threshold_pct
FROM attempt_clo_results r
JOIN exam_attempts a ON a.id = r.attempt_id
JOIN exams e ON e.id = a.exam_id
JOIN class_sections cs ON cs.id = e.class_section_id
JOIN clos c ON c.id = r.clo_id
LEFT JOIN clo_assessment_plans p ON p.clo_id = r.clo_id AND p.semester_id = cs.semester_id;

-- Dữ liệu tham chiếu sinh tự động từ BM2 (KTDL) và bảng phân công đánh giá PIs HKI 2023-2024

USE assessment_db;

SET NAMES utf8mb4;

INSERT INTO bloom_levels (id, code, name_vi) VALUES (1,'Remember','Nhớ'),(2,'Understand','Hiểu'),(3,'Apply','Vận dụng'),(4,'Analyze','Phân tích'),(5,'Evaluate','Đánh giá'),(6,'Create','Sáng tạo');

INSERT INTO semesters (academic_year, term, name, start_date, end_date) VALUES
 ('2021-2022',1,'HKI 21-22','2021-09-05','2022-01-20'),
 ('2021-2022',2,'HKII 21-22','2022-02-10','2022-06-30'),
 ('2022-2023',1,'HKI 22-23','2022-09-05','2023-01-20'),
 ('2022-2023',2,'HKII 22-23','2023-02-10','2023-06-30'),
 ('2023-2024',1,'HKI 23-24','2023-09-05','2024-01-20'),
 ('2023-2024',2,'HKII 23-24','2024-02-10','2024-06-30'),
 ('2024-2025',1,'HKI 24-25','2024-09-05','2025-01-20'),
 ('2024-2025',2,'HKII 24-25','2025-02-10','2025-06-30');

INSERT INTO programs (id, code, name, level, department, target_pct) VALUES (1,'KTDL','Kỹ thuật dữ liệu','Đại học','Bộ môn Kỹ thuật dữ liệu',75.00);

INSERT INTO plos (id, program_id, group_no, plo_code, description, target_pct) VALUES
 (1,1,1,'1.1','Các môn thuộc Khoa khác quản',75.00),
 (2,1,1,'1.2','Áp dụng các kiến thức cơ sở ngành vào lĩnh vực KTDL',75.00),
 (3,1,1,'1.3','Áp dụng kiến thức chuyên ngành vào lĩnh vực KTDL vào các lĩnh vực liên quan',75.00),
 (4,1,2,'2.1','Phân tích, lập luận kỹ thuật và giải quyết vấn đề',75.00),
 (5,1,2,'2.2','Có thể tiến hành kiểm tra và thực nghiệm các vấn đề liên quan việc ứng dụng KTDL',75.00),
 (6,1,2,'2.3','Có tư duy hệ thống và toàn diện về KTDL',75.00),
 (7,1,2,'2.4','Thể hiện kỹ năng và thái độ cá nhân như sự tự tin, nhiệt tình, tư duy sáng tạo và phản biện, khả năng học tập suốt đời và quản lý thời gian tốt',75.00),
 (8,1,2,'2.5','Thể hiện kỹ năng và thái độ nghề nghiệp như đạo đức nghề nghiệp, tác phong chuyên nghiệp, hoạch định nghề nghiệp',75.00),
 (9,1,3,'3.1','Làm việc hiệu quả theo nhóm',75.00),
 (10,1,3,'3.2','Giao tiếp hiệu quả bằng nhiều hình thức khác nhau như văn bản, đồ họa và thuyết trình',75.00),
 (11,1,3,'3.3','Sử dụng được tiếng Anh chuyên ngành KTDL',75.00),
 (12,1,4,'4.1','Nhận thức được tầm quan trọng của môi trường xã hội đối với hoạt động của hệ thống CSDL và các hệ thống xử lý quy mô lớn',75.00),
 (13,1,4,'4.2','Thích nghi với sự khác biệt của môi trường làm việc khác nhau',75.00),
 (14,1,4,'4.3','Có khả năng hình thành ý tưởng, thiết lập yêu cầu, xác định chức năng, lập mô hình cho các hệ thống CSDL và hệ thống xử lý quy mô lớn',75.00),
 (15,1,4,'4.4','Thiết kế các hệ thống mạng, phần mềm và hệ thống thông tin',75.00),
 (16,1,4,'4.5','Có khả năng triển khai phần cứng và/hoặc phần mềm cho các hệ thống CSDL và các hệ thống xử lý quy mô lớn',75.00),
 (17,1,4,'4.6','Có khả năng vận hành và quản lý công tác vận hành các hệ thống CSDL và các hệ thống xử lý quy mô lớn',75.00),
 (18,1,4,'4.7','Vận dụng kiến thức về lãnh đạo vào các vấn đề kỹ thuật trong KTDL',75.00),
 (19,1,4,'4.8','Trình bày được các kiến thức về khởi nghiệp và kinh doanh trong lĩnh vực KTDL',75.00);

INSERT INTO plo_measurement_plans (plo_id, round_no, academic_year, target_pct) VALUES
 (1,1,'2020-2021',75.00),
 (1,2,'2022-2023',75.00),
 (1,3,'2024-2025',75.00),
 (2,1,'2020-2021',75.00),
 (2,2,'2022-2023',75.00),
 (2,3,'2024-2025',75.00),
 (3,1,'2020-2021',75.00),
 (3,2,'2022-2023',75.00),
 (3,3,'2024-2025',75.00),
 (4,1,'2020-2021',75.00),
 (4,2,'2022-2023',75.00),
 (4,3,'2024-2025',75.00),
 (5,1,'2020-2021',75.00),
 (5,2,'2022-2023',75.00),
 (5,3,'2024-2025',75.00),
 (6,1,'2020-2021',75.00),
 (6,2,'2022-2023',75.00),
 (6,3,'2024-2025',75.00),
 (7,1,'2020-2021',75.00),
 (7,2,'2022-2023',75.00),
 (7,3,'2024-2025',75.00),
 (8,1,'2020-2021',75.00),
 (8,2,'2022-2023',75.00),
 (8,3,'2024-2025',75.00),
 (9,1,'2020-2021',75.00),
 (9,2,'2022-2023',75.00),
 (9,3,'2024-2025',75.00),
 (10,1,'2020-2021',75.00),
 (10,2,'2022-2023',75.00),
 (10,3,'2024-2025',75.00),
 (11,1,'2020-2021',75.00),
 (11,2,'2022-2023',75.00),
 (11,3,'2024-2025',75.00),
 (12,1,'2020-2021',75.00),
 (12,2,'2022-2023',75.00),
 (12,3,'2024-2025',75.00),
 (13,1,'2020-2021',75.00),
 (13,2,'2022-2023',75.00),
 (13,3,'2024-2025',75.00),
 (14,1,'2020-2021',75.00),
 (14,2,'2022-2023',75.00),
 (14,3,'2024-2025',75.00),
 (15,1,'2020-2021',75.00),
 (15,2,'2022-2023',75.00),
 (15,3,'2024-2025',75.00),
 (16,1,'2020-2021',75.00),
 (16,2,'2022-2023',75.00),
 (16,3,'2024-2025',75.00),
 (17,1,'2020-2021',75.00),
 (17,2,'2022-2023',75.00),
 (17,3,'2024-2025',75.00),
 (18,1,'2020-2021',75.00),
 (18,2,'2022-2023',75.00),
 (18,3,'2024-2025',75.00),
 (19,1,'2020-2021',75.00),
 (19,2,'2022-2023',75.00),
 (19,3,'2024-2025',75.00);

INSERT INTO performance_indicators (id, plo_id, pi_code, description) VALUES
 (1,2,'PI 1','Sử dụng được các cấu trúc dữ liệu và các giải thuật thích hợp với những dữ liệu có trong ngôn ngữ lập trình'),
 (2,2,'PI 2','Xây dựng được các thuật toán xử lý trên các cấu trúc dữ liệu'),
 (3,2,'PI 3','Xây dựng được các cấu trúc dữ liệu bao gồm danh sách, hàng đợi, ngăn xếp, cây nhị phân tìm kiếm, bảng băm'),
 (4,3,'PI 1','Trình bày được đặc điểm của hạ tầng mạng, CSDL, Công nghệ phần mềm'),
 (5,3,'PI 2','Vận dụng được mô hình mạng Workgroup và Domain'),
 (6,3,'PI 3','Trình bày được các thư viện phân tích dữ liệu phổ biến'),
 (7,4,'PI 1','Tìm ra giải thuật thích hợp hoặc hình thành giải thuật mới cho bài toán từ những phân tích, đánh giá các giải pháp/giải thuật đã có'),
 (8,4,'PI 2','Sử dụng được một số hàm có sẵn để phân tích dữ liệu hỗ trợ cho các bài toán xác suất, thống kê'),
 (9,4,'PI 3','Sử dụng được ngôn ngữ R trong phân tích dữ liệu lớn'),
 (10,5,'PI 1','Xây dựng các luật lọc và cấu hình'),
 (11,5,'PI 2','Chứng tỏ được kỹ năng vận dụng các kỹ thuật mã trong các giao thức truyền dữ liệu'),
 (12,5,'PI 3','Phân tích được các ứng dụng thông tin quản lý trên máy tính.'),
 (13,6,'PI 1','Cài đặt được các giải thuật (BFS, DFS, Prim, Kruskal, Dijkstra, Ford-Bellman, Floyd...) trong LTĐT.'),
 (14,6,'PI 2','Khả năng tư duy có hệ thống và toàn diện'),
 (15,6,'PI 3','Mô tả và áp dụng các phương pháp thiết kế kho dữ liệu'),
 (16,7,'PI 1','Sử dụng nhuần nhuyễn phần mềm hỗ trợ trong việc thực hiện các bài tập và các đồ án, tiểu luận chuyên ngành.'),
 (17,7,'PI 2','Xây dựng được các chương trình thể hiện tính chất căn bản của môn học'),
 (18,7,'PI 3','Đánh giá và lựa chọn các mô hình trong môn học để phù hợp cho bài toán thực tế.'),
 (19,8,'PI 1','Trình bày được các nguyên tắc đạo đức trong học tập, đạo đức cá nhân và nghề nghiệp. Có trách nhiệm với nghề nghiệp và đạo đức trong thực hành kỹ thuật'),
 (20,8,'PI 2','Có kiến thức và kỹ năng liên quan đến học tập bậc đại học'),
 (21,8,'PI 3','Áp dụng, thực nghiệm và đánh giá được các thuật toán phân tích ngoại biên'),
 (22,9,'PI 1','Vận dụng được các phương pháp làm việc nhóm hiệu quả'),
 (23,9,'PI 2','Tự hoạch định kế hoạch nghiên cứu.'),
 (24,10,'PI 1','Lập kế hoạch về thời gian, kế hoạch làm việc nhóm'),
 (25,10,'PI 2','Hoạch định phương pháp trao đổi, thảo luận'),
 (26,10,'PI 3','Tổng hợp tài liệu và viết báo cáo'),
 (27,11,'PI 1','Viết một báo cáo khoa học có sử dụng tiếng Anh chuyên ngành'),
 (28,11,'PI 2','Tìm kiếm tài liệu và đọc tài liệu chuyên ngành bằng tiếng Anh.'),
 (29,11,'PI 3','Thuyết trình có sử dụng tiếng Anh'),
 (30,12,'PI 1','Mô tả được các yêu cầu để xây dựng được ứng dụng real-time streaming'),
 (31,12,'PI 2','Thực hiện vai trò của một người phân tích, thiết kế trong quá trình phát triển phần mềm'),
 (32,12,'PI 3','Khảo sát, xác định, phân tích và lập mô hình yêu cầu cho một hệ thống phần mềm theo mô hình hướng đối tượng.'),
 (33,13,'PI 1','Quan sát và Xác định các yêu cầu cụ thể của từng môi trường làm việc'),
 (34,13,'PI 2','Thực hiện theo các yêu cầu Có thể dễ dàng thích ngh i và làm việc trong các môi trường khác nhau'),
 (35,13,'PI 3','Trao đổi, rút kinh nghiệm, Triển khai phần cứng, phần mềm cho các hệ thống CNTT'),
 (36,14,'PI 1','Thu thập các yêu cầu và phân tích phục vụ cho các hệ thống về CNTT,'),
 (37,14,'PI 2','Trình bày tổng quát một hệ điều hành cụ thể'),
 (38,14,'PI 3','Cài đặt được các giải thuật'),
 (39,15,'PI 1','Phân tích và hiện thực các bước thiết kế cho các hệ thống về CNTT,Thiết kế, đánh giá và lựa chọn các mô hình trong lập trình web phù hợp cho bài toán thực tế.'),
 (40,15,'PI 2','Vận dụng mô hình thiết kế vào trong thực tế thông qua các chương trình, công cụ'),
 (41,15,'PI 3','Đánh giá và lựa chọn các mô hình trong lập trình trực quan và tương tác trực quan với dữ liệu để phù hợp cho bài toán thực tế'),
 (42,16,'PI 1','Khả năng dung hợp ngữ để giải quyết một số bài toán'),
 (43,16,'PI 2','Triển khai phần cứng, phần mềm cho các hệ thống CNTT'),
 (44,16,'PI 3','KIểm thử, sửa sai, khắc phục các lỗi xảy ra, Hình thành ý tưởng, thiết kế, và hiện thực hóa một phần hệ thống xử lý dữ liệu lớn'),
 (45,17,'PI 1','Lựa chọn giải pháp triển khai một hệ thống mạng đơn giản phù hợp cho yêu cầu thực tế'),
 (46,17,'PI 2','Vận hành, xử lý các lỗi trong quá trình cài đặt và cấu hình các kỹ thuật hạ tầng mạng, dịch vụ mạng căn bản'),
 (47,17,'PI 3','Phân tích, thiết kế, phân hoạch chức năng phần cứng, phần mềm, dữ liệu'),
 (48,18,'PI 1','Hình thành kỹ năng lãnh đạo, kỹ năng kinh doanh trong lãnh vực công nghệ thông tin'),
 (49,18,'PI 2','Khả năng phân tích thiết kế, triển khai (phần cứng, phần mềm), vận hành về mặt vật lý cho vấn đề cần giải quyết.'),
 (50,18,'PI 3','Khả năng triển khai phần mềm, dữ liệu cho hệ thống.'),
 (51,19,'PI 1','Kỹ năng khởi nghiệp'),
 (52,19,'PI 2','Phân tích, thiết kế, phân hoạch chức năng phần cứng, phần mềm.'),
 (53,19,'PI 3','Cài đặt, cấu hình phần cứng. Triển khai phần mềm cho hệ thống.');

INSERT INTO courses (id, course_code, course_name, credits) VALUES
 (1,'INDE131777','Nhập môn ngành Kỹ thuật dữ liệu',3),
 (2,'RPAN233577','Lập trình R cho phân tích',3),
 (3,'BDAN333977','Big Data Analysis (Phân tích dữ liệu lớn)',3),
 (4,'BDES333877','Nhập môn dữ liệu lớn',3),
 (5,'DBMS330284','Hệ quản trị cơ sở dữ liệu',3),
 (6,'DBSE431284','Bảo mật cơ sở dữ liệu',3),
 (7,'PODE434277','Tiểu luận chuyên ngành Kỹ thuật dữ liệu',3),
 (8,'POIS431184','Tiểu luận chuyên ngành Hệ thống thông tin',3),
 (9,'ECOM430984','Thương mại điện tử',3);

INSERT INTO program_courses (program_id, course_id) VALUES (1,1),(1,2),(1,3),(1,4),(1,5),(1,6),(1,7),(1,8),(1,9);

INSERT INTO lecturers (id, lecturer_code, full_name, department) VALUES
 (1,'GV001','Trần Trọng Bình','Bộ môn Kỹ thuật dữ liệu'),
 (2,'GV002','Lê Thị Minh Châu','Bộ môn Kỹ thuật dữ liệu'),
 (3,'GV003','Nguyễn Thành Sơn','Bộ môn Kỹ thuật dữ liệu'),
 (4,'GV004','Võ Xuân Thể','Bộ môn Kỹ thuật dữ liệu'),
 (5,'GV005','Phạm Chí Công','Bộ môn Kỹ thuật dữ liệu'),
 (6,'GV006','Nguyễn Văn Thành','Bộ môn Kỹ thuật dữ liệu'),
 (7,'GV007','Quách Đình Hoàng','Bộ môn Kỹ thuật dữ liệu');

INSERT INTO pi_courses (pi_id, course_id) VALUES (4,5),(7,4),(8,2),(9,2),(19,1),(20,1),(21,1),(26,4),(27,3),(28,3),(29,3),(42,3),(43,3),(44,3),(45,7),(46,7),(47,7),(51,7),(52,7),(53,7);

INSERT INTO pi_assessment_plans (pi_id, course_id, semester_id, method, cycle, target_pct, lecturer_id) VALUES
 (8,2,(SELECT id FROM semesters WHERE academic_year='2022-2023' AND term=1),'Báo cáo (report)','2 năm/lần',75.00,7),
 (9,2,(SELECT id FROM semesters WHERE academic_year='2022-2023' AND term=1),'Báo cáo (report)','2 năm/lần',75.00,7),
 (19,1,(SELECT id FROM semesters WHERE academic_year='2021-2022' AND term=1),'Báo cáo trước lớp','2 năm/lần',75.00,3),
 (20,1,(SELECT id FROM semesters WHERE academic_year='2021-2022' AND term=1),'Đánh giá qua thực hiện Dự án học tập nhóm + vấn đáp','2 năm/lần',75.00,3),
 (26,4,(SELECT id FROM semesters WHERE academic_year='2021-2022' AND term=1),'Đánh giá qua thực hiện dự án học tập.','2 năm/lần',75.00,2),
 (27,3,(SELECT id FROM semesters WHERE academic_year='2021-2022' AND term=2),'Báo cáo trước lớp','2 năm/lần',75.00,2),
 (29,3,(SELECT id FROM semesters WHERE academic_year='2021-2022' AND term=2),'Báo cáo trước lớp','2 năm/lần',75.00,2),
 (44,3,(SELECT id FROM semesters WHERE academic_year='2021-2022' AND term=2),'Báo cáo trước lớp','2 năm/lần',75.00,2),
 (47,7,(SELECT id FROM semesters WHERE academic_year='2022-2023' AND term=1),'Đánh giá qua thực hiện dự án học tập','2 năm/lần',75.00,NULL),
 (52,7,(SELECT id FROM semesters WHERE academic_year='2022-2023' AND term=1),'Báo cáo trước lớp','2 năm/lần',75.00,NULL),
 (53,7,(SELECT id FROM semesters WHERE academic_year='2022-2023' AND term=1),'Báo cáo trước lớp','2 năm/lần',75.00,NULL);

INSERT INTO assessment_assignments (semester_id, course_id, lecturer_id, note) VALUES
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),1,1,'Đánh giá theo 7 CĐR'),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),2,1,'Đánh giá theo 19 CĐR'),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),3,2,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),4,2,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),5,3,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),6,2,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),9,4,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),9,5,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),9,6,NULL);
