-- =============================================================
-- Chạy trong HeidiSQL (F9) – tạo CSDL assessment_db: 49 bảng + dữ liệu tham chiếu + CTĐT CNTT 2026, KTDL 2026
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
--  46 bảng, 7 nhóm:
--   A. Người dùng & tổ chức      (4)  users, lecturers, students, semesters
--   B. Chương trình & CĐR CTĐT   (6)  programs, plos, plo_measurement_plans,
--                                     performance_indicators, program_courses, pi_courses
--   C. Học phần & CĐR môn học    (11) courses, course_outlines, bloom_levels, clos, clo_plo_mapping,
--                                     clo_pi_mapping, course_syllabi, syllabus_references,
--                                     syllabus_assessments, syllabus_assessment_clos, outline_clos
--   D. Kế hoạch đo lường         (4)  clo_assessment_plans, pi_assessment_plans,
--                                     pi_plan_clos, assessment_assignments
--   E. Lớp học phần & ngân hàng  (6)  class_sections, enrollments,
--                                     question_bank, question_options, question_clo_mapping,
--                                     question_moodle_links
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
DROP TABLE IF EXISTS sync_runs, learning_reading_items, material_chunks, course_materials, learning_path_items, personalized_learning_paths,
  plo_results, pi_results, clo_results, attempt_clo_results, item_statistics,
  item_level_results, exam_attempts,
  exam_version_options, exam_version_questions, exam_versions, exam_questions, exams,
  question_moodle_links, question_clo_mapping, question_options, question_bank, enrollments, class_sections,
  assessment_assignments, pi_plan_clos, pi_assessment_plans, clo_assessment_plans,
  outline_clos, syllabus_assessment_clos, syllabus_assessments, syllabus_references, course_syllabi,
  clo_pi_mapping, clo_plo_mapping, clos, bloom_levels, course_outlines, courses,
  pi_courses, program_courses, performance_indicators, plo_measurement_plans, plos, programs,
  semesters, students, lecturers, users;
SET FOREIGN_KEY_CHECKS = 1;

-- =====================================================================
-- A. NGƯỜI DÙNG & TỔ CHỨC
-- =====================================================================
CREATE TABLE users (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  username       VARCHAR(50)  NOT NULL COMMENT 'Tên đăng nhập (trùng tài khoản Moodle để SSO)',
  password_hash  VARCHAR(255) NOT NULL COMMENT 'Mật khẩu băm PBKDF2-SHA256',
  full_name      VARCHAR(100) NOT NULL,
  email          VARCHAR(150) NULL COMMENT 'Thư điện tử',
  role           VARCHAR(20)  NOT NULL COMMENT 'admin = Bộ môn/Trưởng BM; lecturer; student',
  is_active      BOOLEAN      NOT NULL DEFAULT TRUE COMMENT '1 = tài khoản đang hoạt động',
  created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_users_username UNIQUE (username),
  CONSTRAINT uq_users_email    UNIQUE (email),
  CONSTRAINT ck_users_role     CHECK (role IN ('admin','lecturer','student'))
) ENGINE=InnoDB COMMENT='Tài khoản đăng nhập';

CREATE TABLE lecturers (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  user_id        INT          NULL,
  lecturer_code  VARCHAR(20)  NOT NULL COMMENT 'Mã giảng viên',
  full_name      VARCHAR(100) NOT NULL,
  department     VARCHAR(150) NULL COMMENT 'Bộ môn',
  CONSTRAINT fk_lecturer_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT uq_lecturer_user UNIQUE (user_id),
  CONSTRAINT uq_lecturer_code UNIQUE (lecturer_code)
) ENGINE=InnoDB COMMENT='Giảng viên';

CREATE TABLE students (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  user_id         INT          NULL,
  student_code    VARCHAR(100) NOT NULL COMMENT 'Mã số sinh viên (MSSV)',
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
  start_date     DATE         NOT NULL COMMENT 'Ngày bắt đầu học kỳ',
  end_date       DATE         NOT NULL COMMENT 'Ngày kết thúc học kỳ',
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
  code               VARCHAR(20)  NOT NULL COMMENT 'Mã CTĐT',
  name               VARCHAR(255) NOT NULL,
  level              VARCHAR(20)  NOT NULL DEFAULT 'Đại học' COMMENT 'Trình độ đào tạo',
  department         VARCHAR(150) NULL COMMENT 'Bộ môn quản lý CTĐT',
  target_pct         DECIMAL(5,2) NOT NULL DEFAULT 75.00 COMMENT 'Chỉ tiêu đạt CĐR CTĐT (%)',
  name_en            VARCHAR(255) NULL COMMENT 'Tên CTĐT tiếng Anh',
  faculty            VARCHAR(150) NULL COMMENT 'Khoa quản lý',
  major_code         VARCHAR(20)  NULL COMMENT 'Mã ngành, VD 7480201',
  cohort_year        SMALLINT     NULL COMMENT 'Áp dụng từ khóa tuyển sinh, VD 2026',
  total_credits      SMALLINT     NULL COMMENT 'Khối lượng học tập (tín chỉ)',
  decision_no        VARCHAR(100) NULL COMMENT 'Số quyết định ban hành CTĐT',
  objective          TEXT         NULL COMMENT 'Mục tiêu chung của CTĐT',
  CONSTRAINT uq_program_code UNIQUE (code),
  CONSTRAINT ck_program_target CHECK (target_pct BETWEEN 0 AND 100)
) ENGINE=InnoDB COMMENT='Chương trình đào tạo';

CREATE TABLE plos (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  program_id   INT          NOT NULL,
  group_no     TINYINT      NOT NULL COMMENT 'Nhóm CĐR: 1 Kiến thức, 2 Kỹ năng, 3 Mức tự chủ và trách nhiệm, 4 ...',
  plo_code     VARCHAR(10)  NOT NULL COMMENT 'VD 1.2',
  description  TEXT         NOT NULL,
  target_pct   DECIMAL(5,2) NOT NULL DEFAULT 75.00 COMMENT 'Chỉ tiêu đạt CĐR (%)',
  competency_level TINYINT  NULL COMMENT 'Trình độ năng lực của PLO (thang 1–6)',
  plo_type     VARCHAR(30)  NULL COMMENT 'CĐR chung hoặc CĐR chuyên biệt',
  CONSTRAINT fk_plo_program FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE CASCADE,
  CONSTRAINT uq_plo_code UNIQUE (program_id, plo_code),
  CONSTRAINT ck_plo_target CHECK (target_pct BETWEEN 0 AND 100)
) ENGINE=InnoDB COMMENT='CĐR chương trình đào tạo (PLO)';

CREATE TABLE plo_measurement_plans (
  plo_id         INT          NOT NULL,
  round_no       TINYINT      NOT NULL COMMENT 'Lần đo 1, 2, ...',
  academic_year  VARCHAR(9)   NOT NULL COMMENT 'Năm học đo lường',
  target_pct     DECIMAL(5,2) NOT NULL COMMENT 'Chỉ tiêu % của lần đo',
  PRIMARY KEY (plo_id, round_no),
  CONSTRAINT fk_pmp_plo FOREIGN KEY (plo_id) REFERENCES plos(id) ON DELETE CASCADE,
  CONSTRAINT uq_pmp_year UNIQUE (plo_id, academic_year),
  CONSTRAINT ck_pmp_target CHECK (target_pct BETWEEN 0 AND 100)
) ENGINE=InnoDB COMMENT='Kế hoạch đo CĐR CTĐT theo năm học (BM2 – mục I)';

CREATE TABLE performance_indicators (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  plo_id       INT          NOT NULL,
  pi_code      VARCHAR(10)  NOT NULL COMMENT 'VD PI 1, PI1.2',
  description  TEXT         NOT NULL,
  competency_level TINYINT  NULL COMMENT 'Trình độ năng lực của PI (thang 1–6)',
  CONSTRAINT fk_pi_plo FOREIGN KEY (plo_id) REFERENCES plos(id) ON DELETE CASCADE,
  CONSTRAINT uq_pi_code UNIQUE (plo_id, pi_code)
) ENGINE=InnoDB COMMENT='Chỉ số đánh giá (PI) của CĐR CTĐT';

-- =====================================================================
-- C. HỌC PHẦN & CĐR MÔN HỌC
-- =====================================================================
CREATE TABLE courses (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  course_code    VARCHAR(20)  NOT NULL COMMENT 'Mã môn học, VD DBMS330284',
  course_name    VARCHAR(255) NOT NULL COMMENT 'Tên môn học',
  credits        TINYINT      NOT NULL COMMENT 'Số tín chỉ',
  clo_target_pct DECIMAL(5,2) NOT NULL DEFAULT 75.00 COMMENT 'Chỉ tiêu đạt CĐR môn học (BM6a)',
  credits_theory   TINYINT    NULL COMMENT 'Số tín chỉ lý thuyết',
  credits_practice TINYINT    NULL COMMENT 'Số tín chỉ thí nghiệm/thực hành/thực tập',
  course_structure VARCHAR(30) NULL COMMENT 'Cấu trúc học phần, VD 3(2:1:6)',
  prerequisites  VARCHAR(255) NULL COMMENT 'Mã học phần trước, tiên quyết',
  description    TEXT         NULL COMMENT 'Mô tả vắn tắt học phần (đề cương)',
  created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_course_code UNIQUE (course_code),
  CONSTRAINT ck_course_credits CHECK (credits > 0),
  CONSTRAINT ck_course_target  CHECK (clo_target_pct BETWEEN 0 AND 100)
) ENGINE=InnoDB COMMENT='Học phần / môn học';

CREATE TABLE program_courses (
  program_id       INT          NOT NULL,
  course_id        INT          NOT NULL,
  semester_no      TINYINT      NULL COMMENT 'Học kỳ trong kế hoạch giảng dạy (1–8)',
  knowledge_block  VARCHAR(150) NULL COMMENT 'Khối kiến thức, VD Kiến thức cơ sở ngành',
  is_elective      BOOLEAN      NOT NULL DEFAULT FALSE COMMENT '1 = học phần tự chọn',
  PRIMARY KEY (program_id, course_id),
  CONSTRAINT fk_pc_program FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE CASCADE,
  CONSTRAINT fk_pc_course  FOREIGN KEY (course_id)  REFERENCES courses(id)  ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='Học phần thuộc CTĐT (học kỳ, khối kiến thức)';

CREATE TABLE pi_courses (
  pi_id      INT        NOT NULL,
  course_id  INT        NOT NULL,
  level      VARCHAR(2) NULL COMMENT 'Mức đáp ứng của học phần với PI: I, R, M hoặc trình độ 1–6 (Phụ lục II)',
  PRIMARY KEY (pi_id, course_id),
  CONSTRAINT fk_pic_pi     FOREIGN KEY (pi_id)     REFERENCES performance_indicators(id) ON DELETE CASCADE,
  CONSTRAINT fk_pic_course FOREIGN KEY (course_id) REFERENCES courses(id)                ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='Ma trận học phần – PI (Phụ lục II CTĐT, BM3b)';

CREATE TABLE course_outlines (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  course_id       INT          NOT NULL,
  chapter_number  TINYINT      NOT NULL COMMENT 'Số thứ tự chương',
  chapter_name    VARCHAR(255) NOT NULL COMMENT 'Tên chương',
  content             TEXT     NULL COMMENT 'Nội dung chi tiết của chương',
  theory_hours        SMALLINT NULL COMMENT 'Số tiết lý thuyết',
  practice_hours      SMALLINT NULL COMMENT 'Số tiết thực hành',
  teaching_activities TEXT     NULL COMMENT 'Hoạt động dạy và học',
  CONSTRAINT fk_outline_course FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
  CONSTRAINT uq_outline_chapter UNIQUE (course_id, chapter_number),
  CONSTRAINT ck_outline_chapter CHECK (chapter_number > 0)
) ENGINE=InnoDB COMMENT='Đề cương – chương';

CREATE TABLE bloom_levels (
  id       TINYINT      PRIMARY KEY,
  code     VARCHAR(20)  NOT NULL COMMENT 'Mã mức Bloom (1–6)',
  name_vi  VARCHAR(50)  NOT NULL COMMENT 'Tên mức Bloom tiếng Việt',
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

CREATE TABLE clo_pi_mapping (
  clo_id  INT     NOT NULL,
  pi_id   INT     NOT NULL,
  level   CHAR(1) NOT NULL DEFAULT 'R' COMMENT 'I = Giới thiệu, R = Củng cố, M = Thành thạo',
  PRIMARY KEY (clo_id, pi_id),
  CONSTRAINT fk_cpi_clo FOREIGN KEY (clo_id) REFERENCES clos(id)                   ON DELETE CASCADE,
  CONSTRAINT fk_cpi_pi  FOREIGN KEY (pi_id)  REFERENCES performance_indicators(id) ON DELETE RESTRICT,
  CONSTRAINT ck_cpi_level CHECK (level IN ('I','R','M'))
) ENGINE=InnoDB COMMENT='CLO đóng góp cho chỉ số PI nào của CĐR CTĐT (góp ý F2a); clo_plo_mapping được suy ra từ bảng này';
CREATE INDEX ix_cpi_pi ON clo_pi_mapping (pi_id);

-- Đề cương chi tiết học phần có phiên bản, Bộ môn soạn và duyệt; GV chỉ xem (góp ý F1).
-- Tên, mã, số tín chỉ, cấu trúc, học phần tiên quyết và mô tả vắn tắt vẫn nằm ở bảng courses.
CREATE TABLE course_syllabi (
  id                    INT AUTO_INCREMENT PRIMARY KEY,
  course_id             INT          NOT NULL,
  version_no            SMALLINT     NOT NULL DEFAULT 1 COMMENT 'Phiên bản đề cương của môn',
  english_name          VARCHAR(255) NULL     COMMENT 'Tên học phần tiếng Anh',
  self_study_hours      SMALLINT     NULL     COMMENT 'Số giờ tự học',
  objectives            TEXT         NULL     COMMENT 'Mục tiêu học phần',
  teaching_methods      TEXT         NULL     COMMENT 'Phương pháp giảng dạy',
  course_policy         TEXT         NULL     COMMENT 'Quy định của học phần',
  status                VARCHAR(10)  NOT NULL DEFAULT 'draft' COMMENT 'draft = bản nháp, approved = đang áp dụng, archived = đã thay thế',
  effective_semester_id INT          NULL     COMMENT 'Áp dụng từ học kỳ',
  approved_by           INT          NULL,
  approved_at           DATETIME     NULL,
  updated_by            INT          NULL,
  updated_at            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_syl_course   FOREIGN KEY (course_id)             REFERENCES courses(id)   ON DELETE CASCADE,
  CONSTRAINT fk_syl_semester FOREIGN KEY (effective_semester_id) REFERENCES semesters(id) ON DELETE SET NULL,
  CONSTRAINT fk_syl_approver FOREIGN KEY (approved_by)           REFERENCES users(id)     ON DELETE SET NULL,
  CONSTRAINT fk_syl_updater  FOREIGN KEY (updated_by)            REFERENCES users(id)     ON DELETE SET NULL,
  CONSTRAINT uq_syl_version  UNIQUE (course_id, version_no),
  CONSTRAINT ck_syl_status   CHECK (status IN ('draft','approved','archived')),
  CONSTRAINT ck_syl_approved CHECK (status = 'draft' OR approved_at IS NOT NULL),
  CONSTRAINT ck_syl_hours    CHECK (self_study_hours IS NULL OR self_study_hours >= 0)
) ENGINE=InnoDB COMMENT='Đề cương chi tiết học phần – phiên bản, mục tiêu, phương pháp, quy định (góp ý F1)';

CREATE TABLE syllabus_references (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  syllabus_id  INT         NOT NULL,
  ref_type     VARCHAR(10) NOT NULL DEFAULT 'main' COMMENT 'main = giáo trình chính, extra = tài liệu tham khảo',
  citation     TEXT        NOT NULL,
  sort_order   SMALLINT    NOT NULL DEFAULT 1,
  CONSTRAINT fk_ref_syllabus FOREIGN KEY (syllabus_id) REFERENCES course_syllabi(id) ON DELETE CASCADE,
  CONSTRAINT ck_ref_type CHECK (ref_type IN ('main','extra'))
) ENGINE=InnoDB COMMENT='Tài liệu học tập của đề cương';

CREATE TABLE syllabus_assessments (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  syllabus_id     INT          NOT NULL,
  component_code  VARCHAR(10)  NOT NULL COMMENT 'VD A1, A2, A3',
  name            VARCHAR(255) NOT NULL COMMENT 'VD Kiểm tra giữa kỳ',
  method          VARCHAR(150) NULL     COMMENT 'Hình thức: trắc nghiệm, tự luận, báo cáo ...',
  timing          VARCHAR(100) NULL     COMMENT 'Thời điểm: tuần 8, cuối kỳ ...',
  weight_pct      DECIMAL(5,2) NOT NULL COMMENT 'Tỷ lệ % trong điểm học phần',
  sort_order      SMALLINT     NOT NULL DEFAULT 1,
  CONSTRAINT fk_sas_syllabus FOREIGN KEY (syllabus_id) REFERENCES course_syllabi(id) ON DELETE CASCADE,
  CONSTRAINT uq_sas_code   UNIQUE (syllabus_id, component_code),
  CONSTRAINT ck_sas_weight CHECK (weight_pct > 0 AND weight_pct <= 100)
) ENGINE=InnoDB COMMENT='Đánh giá học phần trong đề cương: thành phần, hình thức, tỷ trọng';

CREATE TABLE syllabus_assessment_clos (
  assessment_id  INT NOT NULL,
  clo_id         INT NOT NULL,
  PRIMARY KEY (assessment_id, clo_id),
  CONSTRAINT fk_sac_assessment FOREIGN KEY (assessment_id) REFERENCES syllabus_assessments(id) ON DELETE CASCADE,
  CONSTRAINT fk_sac_clo        FOREIGN KEY (clo_id)        REFERENCES clos(id)                 ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='CLO được đánh giá ở từng thành phần';

CREATE TABLE outline_clos (
  outline_id  INT NOT NULL,
  clo_id      INT NOT NULL,
  PRIMARY KEY (outline_id, clo_id),
  CONSTRAINT fk_oc_outline FOREIGN KEY (outline_id) REFERENCES course_outlines(id) ON DELETE CASCADE,
  CONSTRAINT fk_oc_clo     FOREIGN KEY (clo_id)     REFERENCES clos(id)            ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='CLO mà chương góp phần đạt được';


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
  cycle               VARCHAR(30)  NOT NULL DEFAULT '1 lần/HK' COMMENT 'Chu kỳ lấy minh chứng (VD 1 lần/HK)',
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
  cycle        VARCHAR(30)  NOT NULL DEFAULT '2 năm/lần' COMMENT 'Chu kỳ lấy minh chứng',
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
  id               INT          AUTO_INCREMENT PRIMARY KEY,
  semester_id      INT          NOT NULL,
  course_id        INT          NOT NULL,
  lecturer_id      INT          NULL COMMENT 'GV được phân công (NULL khi giao cho tất cả GV hướng dẫn)',
  all_supervisors  TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '1 = Tất cả thầy/cô có hướng dẫn (TLCN, KLTN…)',
  note             VARCHAR(255) NULL COMMENT 'VD Đánh giá theo 7 CĐR',
  lecturer_key     INT GENERATED ALWAYS AS (IFNULL(lecturer_id, 0)) VIRTUAL COMMENT 'Khóa so trùng (0 = tất cả GV hướng dẫn)',
  CONSTRAINT fk_aa_semester FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE CASCADE,
  CONSTRAINT fk_aa_course   FOREIGN KEY (course_id)   REFERENCES courses(id)   ON DELETE CASCADE,
  CONSTRAINT fk_aa_lecturer FOREIGN KEY (lecturer_id) REFERENCES lecturers(id) ON DELETE CASCADE,
  CONSTRAINT uq_aa UNIQUE (semester_id, course_id, lecturer_key),
  CONSTRAINT ck_aa_assignee CHECK ((all_supervisors = 1 AND lecturer_id IS NULL) OR (all_supervisors = 0 AND lecturer_id IS NOT NULL))
) ENGINE=InnoDB COMMENT='Phân công đánh giá PIs theo học kỳ (một GV, hoặc tất cả GV hướng dẫn với môn TLCN/KLTN)';

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
  status            VARCHAR(10) NOT NULL DEFAULT 'active' COMMENT 'active = đang học, dropped = đã rút',
  enrolled_at       TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Thời điểm ghi danh',
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
  bloom_level_id      TINYINT      NULL COMMENT 'NULL = chưa gán (câu nhập hàng loạt)',
  question_type       VARCHAR(30)  NOT NULL DEFAULT 'multichoice' COMMENT 'multichoice = trắc nghiệm một đáp án; manual = câu/ý chấm tay, nhập điểm',
  content             TEXT         NOT NULL COMMENT 'Nội dung câu hỏi',
  moodle_question_id  BIGINT       NULL COMMENT 'mdl_question.id (phiên bản mới nhất)',
  is_cancelled        BOOLEAN      NOT NULL DEFAULT FALSE COMMENT '1 = câu đã Hủy, không tính điểm',
  cancel_reason       VARCHAR(255) NULL COMMENT 'Lý do hủy câu',
  created_by          INT          NULL COMMENT 'Người tạo câu hỏi',
  created_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_qb_course  FOREIGN KEY (course_id)      REFERENCES courses(id)         ON DELETE RESTRICT,
  CONSTRAINT fk_qb_outline FOREIGN KEY (outline_id)     REFERENCES course_outlines(id) ON DELETE SET NULL,
  CONSTRAINT fk_qb_bloom   FOREIGN KEY (bloom_level_id) REFERENCES bloom_levels(id)    ON DELETE RESTRICT,
  CONSTRAINT fk_qb_creator FOREIGN KEY (created_by)     REFERENCES users(id)           ON DELETE SET NULL,
  CONSTRAINT ck_qb_type CHECK (question_type IN ('multichoice','manual'))
) ENGINE=InnoDB COMMENT='Ngân hàng câu hỏi (idnumber Moodle = QB-{id})';
CREATE INDEX ix_qb_course_active ON question_bank (course_id, is_cancelled);
CREATE INDEX ix_qb_moodle ON question_bank (moodle_question_id);

CREATE TABLE question_options (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  question_id       INT      NOT NULL,
  position          TINYINT  NOT NULL COMMENT 'Thứ tự gốc 1..n (= thứ tự <answer> trong XML)',
  opt_label         CHAR(1)  NOT NULL COMMENT 'A, B, C, D ...',
  content           TEXT     NOT NULL COMMENT 'Nội dung phương án',
  is_correct        BOOLEAN  NOT NULL DEFAULT FALSE COMMENT '1 = đáp án đúng',
  moodle_answer_id  BIGINT   NULL COMMENT 'mdl_question_answers.id',
  correct_key       INT GENERATED ALWAYS AS (CASE WHEN is_correct THEN question_id END) VIRTUAL COMMENT 'Cột sinh: chỉ bằng question_id khi là đáp án đúng (bảo đảm một đáp án)',
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

-- Đồng bộ câu hỏi hai chiều (góp ý F3): mỗi câu có thể nằm trong ngân hàng câu hỏi của nhiều khóa học Moodle (nhiều lớp HP).
-- sync_hash = dấu vân tay nội dung + phương án lúc hai bên giống nhau lần cuối → biết bên nào đã sửa (hoặc cả hai = xung đột).
CREATE TABLE question_moodle_links (
  question_id         INT       NOT NULL,
  moodle_course_id    BIGINT    NOT NULL COMMENT 'mdl_course.id',
  moodle_question_id  BIGINT    NOT NULL COMMENT 'mdl_question.id của phiên bản đã đồng bộ',
  sync_hash           CHAR(64)  NOT NULL COMMENT 'SHA-256 nội dung + phương án lúc hai bên giống nhau lần cuối',
  synced_at           DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (question_id, moodle_course_id),
  CONSTRAINT fk_qml_question FOREIGN KEY (question_id) REFERENCES question_bank(id) ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='Trạng thái đồng bộ của câu hỏi với ngân hàng câu hỏi của từng khóa học Moodle';

-- =====================================================================
-- F. ĐỀ THI
-- =====================================================================
CREATE TABLE exams (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  class_section_id  INT          NULL COMMENT 'Lớp HP của bài KT; NULL = đề của môn chưa giao lớp (course_id)',
  course_id         INT          NULL COMMENT 'Đề của môn (tạo ở trang môn học): môn học; giao cho lớp HP khi xuất',
  exam_title        VARCHAR(255) NOT NULL COMMENT 'Tên bài kiểm tra',
  assessment_type   VARCHAR(10)  NOT NULL DEFAULT 'final' COMMENT 'process = Quá trình | final = Cuối kỳ',
  exam_type         VARCHAR(10)  NOT NULL DEFAULT 'online' COMMENT 'online (Moodle) | paper (giấy, trắc nghiệm) | manual (nhập điểm từng câu/ý)',
  exam_date         DATE         NULL COMMENT 'Ngày kiểm tra',
  duration_minutes  SMALLINT     NULL COMMENT 'Thời gian làm bài (phút)',
  max_score         DECIMAL(5,2) NOT NULL DEFAULT 10.00 COMMENT 'Thang điểm bài thi',
  moodle_quiz_id    BIGINT       NULL COMMENT 'mdl_quiz.id',
  moodle_offlinequiz_id BIGINT   NULL COMMENT 'mdl_offlinequiz.id (bài thi giấy chấm trên Moodle)',
  status            VARCHAR(20)  NOT NULL DEFAULT 'Draft' COMMENT 'Draft → Published → Synced → Analyzed',
  publish_flag      BOOLEAN      NOT NULL DEFAULT FALSE COMMENT '1 = SV đã xem được kết quả trên Moodle',
  last_synced_at    DATETIME     NULL COMMENT 'Lần đồng bộ Moodle gần nhất',
  counts_for_clo    BOOLEAN      NOT NULL DEFAULT TRUE COMMENT '1 = dùng làm minh chứng tổng hợp CLO của lớp (gộp các bài được chọn)',
  parent_exam_id    INT          NULL COMMENT 'Bài phụ đạo: bài KT gốc',
  target_students   TEXT         NULL COMMENT 'Bài phụ đạo: MSSV các SV được giao (cách nhau dấu phẩy)',
  paper_settings    TEXT         NULL COMMENT 'Bài giấy chấm trên hệ thống: JSON tùy chọn in đề và bố cục phiếu (phiếu quét được đọc theo đúng bố cục đã in)',
  source_exam_id    INT          NULL COMMENT 'Bài được giao/sao từ đề này (đề của môn hoặc bài của lớp khác)',
  created_by        INT          NULL COMMENT 'Người tạo bài KT',
  created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_exam_cs      FOREIGN KEY (class_section_id) REFERENCES class_sections(id) ON DELETE RESTRICT,
  CONSTRAINT fk_exam_creator FOREIGN KEY (created_by)       REFERENCES users(id)          ON DELETE SET NULL,
  CONSTRAINT fk_exam_parent  FOREIGN KEY (parent_exam_id)   REFERENCES exams(id)          ON DELETE SET NULL,
  CONSTRAINT fk_exam_course  FOREIGN KEY (course_id)        REFERENCES courses(id)        ON DELETE RESTRICT,
  CONSTRAINT fk_exam_source  FOREIGN KEY (source_exam_id)   REFERENCES exams(id)          ON DELETE SET NULL,
  CONSTRAINT uq_exam_moodle_quiz UNIQUE (moodle_quiz_id),
  CONSTRAINT uq_exam_moodle_oq UNIQUE (moodle_offlinequiz_id),
  CONSTRAINT ck_exam_assess   CHECK (assessment_type IN ('process','final')),
  CONSTRAINT ck_exam_type     CHECK (exam_type IN ('online','paper','manual')),
  CONSTRAINT ck_exam_status   CHECK (status IN ('Draft','Published','Synced','Analyzed')),
  CONSTRAINT ck_exam_duration CHECK (duration_minutes IS NULL OR duration_minutes > 0),
  CONSTRAINT ck_exam_online   CHECK (exam_type = 'online' OR moodle_quiz_id IS NULL),
  CONSTRAINT ck_exam_paper    CHECK (exam_type = 'paper' OR moodle_offlinequiz_id IS NULL)
) ENGINE=InnoDB COMMENT='Bài kiểm tra / đề thi';

CREATE TABLE exam_questions (
  exam_id      INT          NOT NULL,
  question_id  INT          NOT NULL,
  order_index  SMALLINT     NOT NULL COMMENT 'Thứ tự câu trong đề gốc',
  points       DECIMAL(5,2) NOT NULL DEFAULT 1.00 COMMENT 'Điểm của câu',
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
  version_id         INT          NULL COMMENT 'Mã đề = nhóm đề Offline Quiz (bài giấy)',
  moodle_attempt_id  BIGINT       NULL COMMENT 'mdl_quiz_attempts.id (online) / mdl_offlinequiz_results.id (giấy)',
  source             VARCHAR(10)  NOT NULL DEFAULT 'moodle' COMMENT 'moodle (Quiz) | paper (Offline Quiz) | scan (hệ thống chấm phiếu quét) | manual (nhập điểm)',
  started_at         DATETIME     NULL COMMENT 'Bắt đầu làm bài',
  finished_at        DATETIME     NULL COMMENT 'Nộp bài',
  status             VARCHAR(20)  NOT NULL COMMENT 'finished = có làm bài, absent = vắng',
  total_score        DECIMAL(6,2) NOT NULL DEFAULT 0.00 COMMENT 'Tổng điểm thô (Σ points)',
  time_limit_sec     INT          NULL COMMENT 'Giới hạn thời gian của Quiz khi làm bài (giây; NULL = không giới hạn)',
  last_answer_at     DATETIME     NULL COMMENT 'Lần cuối SV chọn/đổi một đáp án (từ các bước question engine của Moodle)',
  finished_by_timeout BOOLEAN     NULL COMMENT '1 = bài được nộp khi hết giờ (Moodle tự nộp), không do SV bấm nộp',
  CONSTRAINT fk_att_exam    FOREIGN KEY (exam_id)    REFERENCES exams(id)         ON DELETE CASCADE,
  CONSTRAINT fk_att_student FOREIGN KEY (student_id) REFERENCES students(id)      ON DELETE RESTRICT,
  CONSTRAINT fk_att_version FOREIGN KEY (version_id) REFERENCES exam_versions(id) ON DELETE RESTRICT,
  CONSTRAINT uq_att_exam_student UNIQUE (exam_id, student_id),
  CONSTRAINT uq_att_moodle UNIQUE (exam_id, moodle_attempt_id),
  CONSTRAINT ck_att_source CHECK (source IN ('moodle','paper','scan','manual')),
  CONSTRAINT ck_att_status CHECK (status IN ('finished','absent')),
  CONSTRAINT ck_att_score  CHECK (total_score >= 0),
  CONSTRAINT ck_att_absent CHECK (status <> 'absent' OR (started_at IS NULL AND total_score = 0))
) ENGINE=InnoDB COMMENT='Lượt thi được tính (1 SV / 1 bài KT)';

CREATE TABLE item_level_results (
  id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
  attempt_id          INT          NOT NULL,
  question_id         INT          NOT NULL,
  selected_option_id  INT          NULL COMMENT 'Phương án GỐC sau Reverse Shuffle',
  response_status     VARCHAR(20)  NOT NULL COMMENT 'answered | blank | absent | graded (điểm nhập tay)',
  is_correct          BOOLEAN      NOT NULL DEFAULT FALSE COMMENT '1 = trả lời đúng',
  score_earned        DECIMAL(5,2) NOT NULL DEFAULT 0.00 COMMENT 'Điểm đạt của câu',
  first_answer_at     DATETIME     NULL COMMENT 'Lần đầu SV chọn đáp án câu này (bài trên Moodle Quiz)',
  last_answer_at      DATETIME     NULL COMMENT 'Lần cuối SV chọn/đổi đáp án câu này',
  n_answer_saves      SMALLINT     NULL COMMENT 'Số lần lưu đáp án của câu (> 1 = có đổi đáp án)',
  response_time_sec   DECIMAL(8,1) NULL COMMENT 'Thời gian trả lời câu (giây) = khoảng cách tới lần chọn đáp án liền trước trong lượt làm',
  CONSTRAINT fk_ilr_attempt  FOREIGN KEY (attempt_id)         REFERENCES exam_attempts(id)    ON DELETE CASCADE,
  CONSTRAINT fk_ilr_question FOREIGN KEY (question_id)        REFERENCES question_bank(id)    ON DELETE RESTRICT,
  CONSTRAINT fk_ilr_option   FOREIGN KEY (selected_option_id) REFERENCES question_options(id) ON DELETE RESTRICT,
  CONSTRAINT uq_ilr UNIQUE (attempt_id, question_id),
  CONSTRAINT ck_ilr_status CHECK (response_status IN ('answered','blank','absent','graded')),
  CONSTRAINT ck_ilr_consistency CHECK (
        (response_status =  'answered' AND selected_option_id IS NOT NULL)
     OR (response_status =  'graded'   AND selected_option_id IS NULL AND score_earned >= 0)
     OR (response_status IN ('blank','absent') AND selected_option_id IS NULL
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
  score_pct     DECIMAL(5,2) NOT NULL COMMENT 'Tỷ lệ % = score_earned / score_max',
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
  achieved_pct      DECIMAL(5,2) NOT NULL COMMENT 'Tỷ lệ % SV đạt = n_achieved / n_evaluated',
  target_pct        DECIMAL(5,2) NOT NULL COMMENT 'Chỉ tiêu % SV đạt của CLO',
  is_achieved       BOOLEAN      NOT NULL COMMENT '1 = CLO đạt (achieved_pct ≥ target_pct)',
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
  n_evaluated   INT          NOT NULL COMMENT 'Số lượt SV được đánh giá',
  n_achieved    INT          NOT NULL COMMENT 'Số lượt SV đạt',
  achieved_pct  DECIMAL(5,2) NOT NULL COMMENT 'Tỷ lệ % đạt',
  target_pct    DECIMAL(5,2) NOT NULL COMMENT 'Chỉ tiêu % của PI',
  is_achieved   BOOLEAN      NOT NULL COMMENT '1 = PI đạt',
  computed_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (plan_id),
  CONSTRAINT fk_pr_plan FOREIGN KEY (plan_id) REFERENCES pi_assessment_plans(id) ON DELETE CASCADE,
  CONSTRAINT ck_pr_counts CHECK (n_evaluated > 0 AND n_achieved BETWEEN 0 AND n_evaluated)
) ENGINE=InnoDB COMMENT='Kết quả tổng hợp từng PI (BM3c)';

CREATE TABLE plo_results (
  plo_id                INT          NOT NULL,
  academic_year         VARCHAR(9)   NOT NULL COMMENT 'Năm học đo (VD 2024-2025)',
  n_evaluated           INT          NOT NULL COMMENT 'Số lượt SV được đánh giá (Σ các PI)',
  n_achieved            INT          NOT NULL COMMENT 'Số lượt SV đạt (Σ các PI)',
  achieved_pct          DECIMAL(5,2) NOT NULL COMMENT 'Tỷ lệ % đạt',
  target_pct            DECIMAL(5,2) NOT NULL COMMENT 'Chỉ tiêu % của PLO',
  is_achieved           BOOLEAN      NOT NULL COMMENT '1 = PLO đạt',
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
  generated_date          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Thời điểm sinh lộ trình',
  diagnostic_summary      TEXT     NULL COMMENT 'Nhận định mức đạt CLO của SV',
  recommended_study_plan  TEXT     NULL COMMENT 'Kế hoạch ôn tập đề xuất',
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
  kind         VARCHAR(10) NOT NULL DEFAULT 'moodle' COMMENT 'moodle | paper | scan | manual | analyze',
  started_at   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Bắt đầu đồng bộ/phân tích',
  finished_at  DATETIME    NULL COMMENT 'Kết thúc',
  status       VARCHAR(20) NOT NULL DEFAULT 'running' COMMENT 'running, success hoặc failed',
  n_attempts   INT         NULL COMMENT 'Số bài làm đọc được',
  n_absent     INT         NULL COMMENT 'Số SV vắng',
  message      TEXT        NULL COMMENT 'Thông báo lỗi/cảnh báo',
  CONSTRAINT fk_sync_exam FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
  CONSTRAINT ck_sync_kind   CHECK (kind IN ('moodle','paper','scan','manual','analyze')),
  CONSTRAINT ck_sync_status CHECK (status IN ('running','success','failed'))
) ENGINE=InnoDB COMMENT='Nhật ký đồng bộ / nhập kết quả / phân tích';

-- =====================================================================
-- VIEW
-- =====================================================================
-- Câu hỏi vi phạm ràng buộc nhiều dòng (tổng trọng số CLO ≠ 1; câu trắc nghiệm không đúng 1 đáp án đúng hoặc < 2 phương án)
CREATE OR REPLACE VIEW v_question_integrity AS
SELECT q.id AS question_id, q.question_type,
       (SELECT COALESCE(SUM(weight),0) FROM question_clo_mapping m WHERE m.question_id = q.id) AS total_weight,
       (SELECT COUNT(*) FROM question_options o WHERE o.question_id = q.id)                   AS n_options,
       (SELECT COUNT(*) FROM question_options o WHERE o.question_id = q.id AND o.is_correct)   AS n_correct
FROM question_bank q
HAVING total_weight <> 1.00 OR (question_type = 'multichoice' AND (n_options < 2 OR n_correct <> 1));

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

INSERT INTO assessment_assignments (semester_id, course_id, lecturer_id, all_supervisors, note) VALUES
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),1,1,0,'Đánh giá theo 7 CĐR'),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),2,1,0,'Đánh giá theo 19 CĐR'),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),3,2,0,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),4,2,0,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),5,3,0,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),6,2,0,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),7,NULL,1,'Tất cả thầy/cô có HD'),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),8,NULL,1,'Tất cả thầy/cô có HD'),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),9,4,0,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),9,5,0,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),9,6,0,NULL);

-- Hai chương trình đào tạo 2026 (CNTT, KTDL) đọc từ file PDF bằng tools/ctdt_2026/doc_ctdt.py.
-- Chạy lại an toàn: chỉ thêm phần còn thiếu, không ghi đè dữ liệu đã chỉnh trên hệ thống.

SET NAMES utf8mb4;

-- ===================== CNTT-2026: Công nghệ thông tin
INSERT IGNORE INTO programs (code, name, name_en, level, department, faculty, major_code, cohort_year, total_credits, decision_no, objective, target_pct) VALUES ('CNTT-2026', 'Công nghệ thông tin', 'Information Technology', 'Đại học', NULL, 'Khoa Công nghệ Thông Tin', '7480201', 2026, 150, '3052/QĐ-ĐHCNKT ngày 14/8/2026', 'Đào tạo kỹ sư ngành Công nghệ thông tin (CNTT) phát triển toàn diện, có đạo đức, tri thức, sức khỏe, thẩm mỹ, trung thành với lý tưởng dân tộc và chủ nghĩa xã hội, có kiến thức khoa học cơ bản, kiến thức cơ sở và chuyên ngành về CNTT, có khả năng phân tích, giải quyết vấn đề, có khả năng đánh giá và lựa chọn các giải pháp phù hợp, có năng lực xây dựng và quản trị các hệ thống dữ liệu lớn, có kỹ năng giao tiếp và làm việc nhóm, có thái độ nghề nghiệp phù hợp và năng lực tự học để đáp ứng được các yêu cầu phát triển của ngành và xã hội. Với kiến thức cơ sở ngành và chuyên ngành Công nghệ thông tin được trang bị, học viên có khả năng nghiên cứu một cách độc lập, sáng tạo, có năng lực phát hiện và giải quyết vấn đề kỹ thuật phức tạp. Ngoài ra, chương trình cung cấp nền tảng kiến thức vững chắc để học viên có thể tiếp tục nâng cao và mở rộng kiến thức nhằm thích ứng với nhu cầu phát triển kinh tế - xã hội trong nước và quốc tế.', 75.00);
SET @p := (SELECT id FROM programs WHERE code = 'CNTT-2026');
INSERT IGNORE INTO plos (program_id, group_no, plo_code, description, target_pct, competency_level, plo_type) VALUES (@p, 1, 'PLO1', 'Khả năng áp dụng các nguyên tắc toán học, thuật toán, cũng như khoa học để xác định giải pháp cho vấn đề trong công nghệ thông tin.', 75.00, 3, 'CĐR chung');
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI1.1', 'Xác định vấn đề tính toán trong lĩnh vực CNTT.', 2 FROM plos WHERE program_id = @p AND plo_code = 'PLO1';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI1.2', 'Áp dụng các nguyên tắc toán học, thuật toán, và khoa học để xác định giải pháp trong lĩnh vực CNTT', 3 FROM plos WHERE program_id = @p AND plo_code = 'PLO1';
INSERT IGNORE INTO plos (program_id, group_no, plo_code, description, target_pct, competency_level, plo_type) VALUES (@p, 3, 'PLO2', 'Khả năng nhận biết trách nhiệm nghề nghiệp và đưa ra những đánh giá sáng suốt trong xây dựng giải pháp Công nghệ thông tin dựa trên các nền tảng pháp lý và đạo đức.', 75.00, 4, 'CĐR chung');
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI2.1', 'Nhận thức trách nhiệm nghề nghiệp và đạo đức liên quan đến vấn đề về Công nghệ thông tin.', 2 FROM plos WHERE program_id = @p AND plo_code = 'PLO2';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI2.2', 'Đánh giá tác động của các giải pháp kỹ thuật cho bài toán đến cộng đồng và xã hội.', 4 FROM plos WHERE program_id = @p AND plo_code = 'PLO2';
INSERT IGNORE INTO plos (program_id, group_no, plo_code, description, target_pct, competency_level, plo_type) VALUES (@p, 3, 'PLO3', 'Khả năng tiếp thu và áp dụng kiến thức mới, sử dụng các chiến lược học tập phù hợp.', 75.00, 3, 'CĐR chuyên biệt');
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI3.1', 'Kỹ năng áp dụng kiến thức mới để giải quyết vấn đề về Công nghệ thông tin.', 3 FROM plos WHERE program_id = @p AND plo_code = 'PLO3';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI3.2', 'Kỹ năng áp dụng những chiến lược học tập hiệu quả', 3 FROM plos WHERE program_id = @p AND plo_code = 'PLO3';
INSERT IGNORE INTO plos (program_id, group_no, plo_code, description, target_pct, competency_level, plo_type) VALUES (@p, 2, 'PLO4', 'Khả năng hoạt động hiệu quả trong một nhóm mà các thành viên cùng nhau lãnh đạo, tạo ra một môi trường hợp tác và hòa nhập, thiết lập các mục tiêu, lập kế hoạch nhiệm vụ và đáp ứng các mục tiêu.', 75.00, 3, 'CĐR chung');
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI4.1', 'Áp dụng những kiến thức cho việc thiết lập một môi trường làm việc nhóm hiệu quả.', 3 FROM plos WHERE program_id = @p AND plo_code = 'PLO4';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI4.2', 'Vận dụng được các phương pháp làm việc nhóm hiệu quả.', 3 FROM plos WHERE program_id = @p AND plo_code = 'PLO4';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI4.3', 'Thể hiện trách nhiệm công việc được giao và đóng góp vào sự thành công của nhóm.', 3 FROM plos WHERE program_id = @p AND plo_code = 'PLO4';
INSERT IGNORE INTO plos (program_id, group_no, plo_code, description, target_pct, competency_level, plo_type) VALUES (@p, 2, 'PLO5', 'Khả năng giao tiếp hiệu quả với nhiều đối tượng, và giao tiếp bằng tiếng Anh.', 75.00, 4, 'CĐR chuyên biệt');
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI5.1', 'Khả năng giải thích, truyền đạt nội dung công việc dưới dạng văn bản', 3 FROM plos WHERE program_id = @p AND plo_code = 'PLO5';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI5.2', 'Khả năng giải thích, truyền đạt những hiểu biết đến mọi người bằng lời nói', 4 FROM plos WHERE program_id = @p AND plo_code = 'PLO5';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI5.3', 'Khả năng đọc, hiểu, viết sử dụng tiếng Anh trong Công nghệ Thông tin', 4 FROM plos WHERE program_id = @p AND plo_code = 'PLO5';
INSERT IGNORE INTO plos (program_id, group_no, plo_code, description, target_pct, competency_level, plo_type) VALUES (@p, 1, 'PLO6', 'Khả năng thiết kế, cài đặt, và đánh giá giải pháp để đáp ứng các yêu cầu cụ thể trong lĩnh vực Công nghệ thông tin.', 75.00, 6, 'CĐR chuyên biệt');
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI6.1', 'Thiết lập yêu cầu, xác định chức năng cho các vấn đề liên quan đến Công nghệ thông tin', 4 FROM plos WHERE program_id = @p AND plo_code = 'PLO6';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI6.2', 'Phân tích, thiết kế và cài đặt các bài toán trong lĩnh vực Công nghệ thông tin', 6 FROM plos WHERE program_id = @p AND plo_code = 'PLO6';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI6.3', 'Đánh giá các giải pháp về mức độ đáp ứng các yêu cầu của bài toán', 5 FROM plos WHERE program_id = @p AND plo_code = 'PLO6';
INSERT IGNORE INTO plos (program_id, group_no, plo_code, description, target_pct, competency_level, plo_type) VALUES (@p, 1, 'PLO7', 'Khả năng áp dụng các công nghệ phù hợp để tạo ra các giải pháp về Công nghệ thông tin.', 75.00, 6, 'CĐR chuyên biệt');
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI7.1', 'Áp dụng các công nghệ về phần mềm, hệ thống thông tin, và trí tuệ nhân tạo để tạo ra giải pháp CNTT.', 6 FROM plos WHERE program_id = @p AND plo_code = 'PLO7';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI7.2', 'Áp dụng công nghệ mạng máy tính để tạo ra giải pháp CNTT', 6 FROM plos WHERE program_id = @p AND plo_code = 'PLO7';

INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('LLCT130105', 'Triết học Mác - Lênin', 3, 3, NULL, '3(3/0/6)', NULL, 'Học phần gồm 3 chương, cung cấp cho sinh viên kiến thức: Chương 1 trình bày những nét khái quát nhất về triết học, triết học Mác - Lênin, và vai trò của triết học Mác - Lênin trong đời sống xã hội. Chương 2 trình bày những nội dung cơ bản của chủ nghĩa duy vật biện chứng, gồm vấn đề vật chất và ý thức; phép biện chứng duy vật; lý luận nhận thức của chủ nghĩa duy vật biện chứng. Chương 3 trình bày những nội dung cơ bản của chủ nghĩa duy vật lịch sử, gồm vấn đề hình thái kinh tế xã hội; giai cấp và dân tộc; nhà nước và cách mạng xã hội; ý thức xã hội; triết học về con người.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 1, 'Lý luận chính trị + Pháp luật đại cương', 0 FROM courses WHERE course_code = 'LLCT130105';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT130105' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT130105' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('LLCT120205', 'Kinh tế chính trị Mác - Lênin', 2, 2, NULL, '2(2/0/4)', 'LLCT130105', 'Học phần gồm 6 chương, cung cấp cho sinh viên kiến thức: Chương 1 trình bày về đối tượng, phương pháp nghiên cứu và chức năng của kinh tế chính trị Mác - Lênin. Từ chương 2 đến chương 6 trình bày nội dung cốt lõi của kinh tế chính trị Mác - Lênin theo mục tiêu của môn học. Cụ thể các vấn đề như: Hàng hóa, thị trường và vai trò của các chủ thể trong nền kinh tế thị trường; Sản xuất giá trị thặng dư trong nền kinh tế thị trường; Cạnh tranh và độc quyền trong nền kinh tế thị trường; Kinh tế thị trường định hướng xã hội chủ nghĩa và các quan hệ lợi ích kinh tế ở Việt Nam; Công nghiệp hóa, hiện đại hóa và hội nhập kinh tế quốc tế của Việt Nam.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 1, 'Lý luận chính trị + Pháp luật đại cương', 0 FROM courses WHERE course_code = 'LLCT120205';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120205' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120205' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('LLCT120405', 'Chủ nghĩa xã hội khoa học', 2, 2, NULL, '2(2/0/4)', 'LLCT130105', 'Học phần gồm 7 chương, cung cấp cho sinh viên kiến thức: Chương 1, trình bày những vấn đề cơ bản có tính nhập môn của Chủ nghĩa xã hội khoa học (quá trình hình thành, phát triển của Chủ nghĩa xã hội khoa học); từ chương 2 đến chương 7 trình bày những nội dung cơ bản của Chủ nghĩa xã hội khoa học theo mục tiêu môn học.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Lý luận chính trị + Pháp luật đại cương', 0 FROM courses WHERE course_code = 'LLCT120405';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120405' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120405' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('LLCT120314', 'Tư tưởng Hồ Chí Minh', 2, 2, NULL, '2(2:0:4)', 'LLCT130105', 'Học phần gồm 6 chương, cung cấp cho sinh viên kiến thức: Khái niệm, đối tượng, phương pháp nghiên cứu và ý nghĩa học tập môn tư tưởng Hồ Chí Minh; về cơ sở, quá trình hình thành và phát triển tư tưởng Hồ Chí Minh; Tư tưởng Hồ Chí Minh về: Độc lập dân tộc và chủ nghĩa xã hội; Đảng Cộng sản Việt Nam và Nhà nước của nhân dân, do nhân dân, vì nhân dân; Đại đoàn kết dân tộc và đoàn kết quốc tế; Văn hóa, con người; Đạo đức.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Lý luận chính trị + Pháp luật đại cương', 0 FROM courses WHERE course_code = 'LLCT120314';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120314' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120314' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('LLCT220514', 'Lịch sử Đảng Cộng sản Việt Nam', 2, 2, NULL, '2(2/0/4)', 'LLCT120205, LLCT120314, LLCT120405, LLCT130105', 'Học phần gồm 3 chương, cung cấp cho sinh viên sự hiểu biết về đối tượng, mục đích, nhiệm vụ, phương pháp nghiên cứu, học tập môn Lịch sử Đảng và những kiến thức cơ bản, cốt lõi, hệ thống về sự ra đời của Đảng (1920-1930), quá trình Đảng lãnh đạo cuộc đấu tranh giành chính quyền (1930- 1945), lãnh đạo hai cuộc kháng chiến chông thực dân Pháp và đế quốc Mỹ xâm lược, hoàn thành giải phóng dân tộc, thống nhất đất nước (1945-1975), lãnh đạo cả nước quá độ lên chủ nghĩa xã hội và tiến hành công cuộc đổi mới (1975-2018). Qua đó khẳng định các thành công, nêu lên các hạn chế, tổng kết những kinh nghiệm về sự lãnh đạo cách mạng của Đảng để giúp người học nâng cao nhận thức, niềm tin đối với Đảng và khả năng vận dụng kiến thức đã học vào thực tiễn công tác, góp phần xây dựng và bảo vệ Tổ quốc Việt Nam xã hội chủ nghĩa.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Lý luận chính trị + Pháp luật đại cương', 0 FROM courses WHERE course_code = 'LLCT220514';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT220514' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT220514' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('GELA236939', 'Pháp luật đại cương', 3, 3, NULL, '3(3:0:6)', NULL, 'Học phần trang bị cho sinh viên các kiến thức cơ bản nhất về nhà nước và pháp luật, bao gồm: lý luận chung về nhà nước và pháp luật (nguồn gốc, bản chất, chức năng, đặc trưng cơ bản của nhà nước; nguồn gốc, hình thức, khái niệm, thuộc tính của pháp luật); hệ thống pháp luật và quan hệ pháp luật, vi phạm pháp luật và trách nhiệm pháp lý; các chế định luật cơ bản của một số ngành luật quan trọng.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Lý luận chính trị + Pháp luật đại cương', 0 FROM courses WHERE course_code = 'GELA236939';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GELA236939' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GELA236939' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('INPR130285', 'Nhập môn lập trình', 3, 2, 1, '3(2:1:6)', NULL, 'Học phần này trang bị cho người học những kiến thức cơ bản về cách biểu diễn dữ liệu trên máy tính, hệ thống số với các phép toán nhị phân, bát phân, thập lục phân, các bước giải một bài toán lập trình. Ngoài ra môn học này còn định hướng phương pháp tư duy, phong cách lập trình, cách giải quyết bài toán tin học bằng lưu đồ khối, lập trình các bài toán tin học đơn giản bằng ngôn ngữ lập trình C/C++.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 1, 'Tin học', 0 FROM courses WHERE course_code = 'INPR130285';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INPR130285' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INPR130285' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INPR130285' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ENCO140126', 'Kỹ năng giao tiếp tiếng Anh sơ cấp', 4, NULL, NULL, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 1, 'Kiến thức ngoại ngữ', 0 FROM courses WHERE course_code = 'ENCO140126';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ENCO140126' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ENCO140126' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ENCO140126' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ENCO240226', 'Kỹ năng giao tiếp tiếng Anh trung cấp', 4, NULL, NULL, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Kiến thức ngoại ngữ', 0 FROM courses WHERE course_code = 'ENCO240226';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ENCO240226' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ENCO240226' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ENCO240226' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('VNCD130615', 'Văn hóa và phát triển', 3, 3, 0, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Khối tự chọn Khoa học xã hội nhân văn/ kỹ năng học tập/ mục tiêu nghề nghiệp – Nhóm 1:Văn hoá - xã hội và phát triển', 1 FROM courses WHERE course_code = 'VNCD130615';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ASCD130605', 'Xã hội học ứng dụng và phát triển cộng đồng', 3, 3, 0, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Khối tự chọn Khoa học xã hội nhân văn/ kỹ năng học tập/ mục tiêu nghề nghiệp – Nhóm 1:Văn hoá - xã hội và phát triển', 1 FROM courses WHERE course_code = 'ASCD130605';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ENBP334808', 'Khởi nghiệp và lập kế hoạch kinh doanh', 3, 3, 0, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Khối tự chọn Khoa học xã hội nhân văn/ kỹ năng học tập/ mục tiêu nghề nghiệp – Nhóm 2: Khởi nghiệp - Kinh doanh', 1 FROM courses WHERE course_code = 'ENBP334808';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('MACU330909', 'Marketing và quản trị quan hệ khách hàng', 3, 3, 0, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Khối tự chọn Khoa học xã hội nhân văn/ kỹ năng học tập/ mục tiêu nghề nghiệp – Nhóm 2: Khởi nghiệp - Kinh doanh', 1 FROM courses WHERE course_code = 'MACU330909';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('CLET337339', 'Pháp luật hợp đồng trong kỹ thuật và công nghệ', 3, 3, 0, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Khối tự chọn Khoa học xã hội nhân văn/ kỹ năng học tập/ mục tiêu nghề nghiệp – Nhóm 3: Pháp Luật trong môi trường kỹ thuật', 1 FROM courses WHERE course_code = 'CLET337339';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('IPTT337439', 'Pháp luật về sở hữu trí tuệ và chuyển giao công nghệ', 3, 3, 0, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Khối tự chọn Khoa học xã hội nhân văn/ kỹ năng học tập/ mục tiêu nghề nghiệp – Nhóm 3: Pháp Luật trong môi trường kỹ thuật', 1 FROM courses WHERE course_code = 'IPTT337439';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('MATH132101', 'Giải tích 1', 3, 3, NULL, '3(3:0:6)', NULL, 'Môn học này cung cấp cho các kiến thức cơ bản về Phép tính vi tích phân hàm một biến được chia thành 5 chương: - Chương 1: Hàm số - Giới hạn hàm số - Chương 2: Phép tính vi phân - Chương 3: Ứng dụng phép tính vi phân - Chương 4: Phép tích tích phân - Chương 5: Ứng dụng phép tính tích phân') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 1, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'MATH132101';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132101' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132101' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT INTO course_outlines (course_id, chapter_number, chapter_name) SELECT c.id, 1, 'Hàm số - Giới hạn hàm số' FROM courses c WHERE c.course_code = 'MATH132101' AND NOT EXISTS (SELECT 1 FROM course_outlines o WHERE o.course_id = c.id AND o.chapter_number = 1);
INSERT INTO course_outlines (course_id, chapter_number, chapter_name) SELECT c.id, 2, 'Phép tính vi phân' FROM courses c WHERE c.course_code = 'MATH132101' AND NOT EXISTS (SELECT 1 FROM course_outlines o WHERE o.course_id = c.id AND o.chapter_number = 2);
INSERT INTO course_outlines (course_id, chapter_number, chapter_name) SELECT c.id, 3, 'Ứng dụng phép tính vi phân' FROM courses c WHERE c.course_code = 'MATH132101' AND NOT EXISTS (SELECT 1 FROM course_outlines o WHERE o.course_id = c.id AND o.chapter_number = 3);
INSERT INTO course_outlines (course_id, chapter_number, chapter_name) SELECT c.id, 4, 'Phép tích tích phân' FROM courses c WHERE c.course_code = 'MATH132101' AND NOT EXISTS (SELECT 1 FROM course_outlines o WHERE o.course_id = c.id AND o.chapter_number = 4);
INSERT INTO course_outlines (course_id, chapter_number, chapter_name) SELECT c.id, 5, 'Ứng dụng phép tính tích phân' FROM courses c WHERE c.course_code = 'MATH132101' AND NOT EXISTS (SELECT 1 FROM course_outlines o WHERE o.course_id = c.id AND o.chapter_number = 5);
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('MATH133601', 'Giải tích 2', 3, 3, NULL, '3(3:0:6)', NULL, 'Môn học này cung cấp các kiến thức cơ bản về hàm vectơ, hàm nhiều biến, đạo hàm riêng, tích phân bội, tích phân đường, tích phân mặt, trường véc tơ. Ứng dụng các kiến thức này vào việc định hướng và giải quyết một số bài toán thực tế. Học phần gồm 4 chương - Chương 1: Đạo hàm riêng - Chương 2: Tích phân bội - Chương 3: Hàm vector - Chương 4: Giải tích Vector') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'MATH133601';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH133601' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH133601' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT INTO course_outlines (course_id, chapter_number, chapter_name) SELECT c.id, 1, 'Đạo hàm riêng' FROM courses c WHERE c.course_code = 'MATH133601' AND NOT EXISTS (SELECT 1 FROM course_outlines o WHERE o.course_id = c.id AND o.chapter_number = 1);
INSERT INTO course_outlines (course_id, chapter_number, chapter_name) SELECT c.id, 2, 'Tích phân bội' FROM courses c WHERE c.course_code = 'MATH133601' AND NOT EXISTS (SELECT 1 FROM course_outlines o WHERE o.course_id = c.id AND o.chapter_number = 2);
INSERT INTO course_outlines (course_id, chapter_number, chapter_name) SELECT c.id, 3, 'Hàm vector' FROM courses c WHERE c.course_code = 'MATH133601' AND NOT EXISTS (SELECT 1 FROM course_outlines o WHERE o.course_id = c.id AND o.chapter_number = 3);
INSERT INTO course_outlines (course_id, chapter_number, chapter_name) SELECT c.id, 4, 'Giải tích Vector' FROM courses c WHERE c.course_code = 'MATH133601' AND NOT EXISTS (SELECT 1 FROM course_outlines o WHERE o.course_id = c.id AND o.chapter_number = 4);
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('MATH143001', 'Đại số tuyến tính và cấu trúc đại số', 4, 4, NULL, '4(4:0:8)', NULL, 'Môn học này bao gồm các kiến thức: Tập hợp, ánh xạ, quan hệ tương đương, quy nạp toán học; ma trận, định thức, hệ phương trình tuyến tính; không gian vectơ, không gian Euclide, ánh xạ tuyến tính, chéo hóa ma trận, dạng toàn phương; lý thuyết về một số cấu trúc đại số như nhóm, vành, trường; và một số ứng dụng như các mô hình tuyến tính, đồ họa máy tính, mã hóa, mật mã,….') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 1, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'MATH143001';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH143001' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH143001' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('MATH132901', 'Xác suất thống kê ứng dụng', 3, 3, NULL, '3(3:0:6)', NULL, 'Môn học này bao gồm thống kê mô tả, xác suất sơ cấp, biến ngẫu nhiên và luật phân phối xác suất, các số đặc trưng của biến ngẫu nhiên, ước lượng tham số, kiểm định giả thuyết, tương quan và hồi quy tuyến tính.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'MATH132901';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132901' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132901' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132901' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('PHYS130902', 'Vật lý 1', 3, 3, NULL, '3(3:0:6)', NULL, 'Học phần này cung cấp cho sinh viên những nội dung cơ bản của vật lý bao gồm các phần cơ học và nhiệt học làm cơ sở cho việc tiếp cận các môn học chuyên ngành trình độ đại học các ngành khoa học, kỹ thuật và công nghệ. Sinh viên sẽ được trang bị các kiến thức về vật lý để khảo sát sự chuyển động, năng lượng và các hiện tượng vật lý liên quan đến các đối tượng trong tự nhiên có kích thước từ phân tử đến cỡ hành tinh. Sau khi học xong học phần sinh viên sẽ có khả năng ứng dụng những kiến thức đã học trong nghiên cứu khoa học cũng như trong phát triển kỹ thuật và công nghệ hiện đại. Nội dung của học phần gồm các chương từ 1 đến 22 trong sách Physics for Scientists and Engineers with Modern Physics, 9th Edition của các tác giả R.A. Serway và J.W. Jewett. Các nội dung của học phần này nhằm giúp sinh viên làm quen với phương pháp khoa học, các định luật cơ bản của vật lý, phát triển hiểu biết về khoa học vật lý nói chung và kỹ năng lập luận cũng như các chiến lược để chuẩn bị cho việc học tập các lớp khoa học chuyên ngành trong chương trình dành cho kỹ sư. Để đạt mục tiêu này, học phần sẽ chú trọng vào việc kết hợp cung cấp những hiểu biết về các khái niệm với các kỹ năng giải các bài tập dạng chuẩn (làm ở nhà) ở cuối mỗi chương. Bên cạnh đó, học phần sẽ giúp sinh viên hiểu cách xây dựng các mô hình toán học dựa trên các kết quả thực nghiệm, biết cách ghi nhận, trình bày, phân tích số liệu và phát triển một mô hình dựa trên các dữ liệu và có thể sử dụng mô hình này để phán đoán kết quả của các thí nghiệm khác. Đồng thời, sinh viên sẽ biết được giới hạn của mô hình và có thể sử dụng chúng trong việc phán đoán.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 1, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'PHYS130902';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS130902' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS130902' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('PHYS111202', 'Thí nghiệm vật lý 1', 1, 1, NULL, '1(0:1:2)', NULL, 'Thí nghiệm Vật lý 1 gồm một đơn vị học phần có 9 bài thí nghiệm về động học, động lực học chất điểm và động lực học vật rắn. Đây là môn học bổ sung cho sinh viên thuộc khối ngành công nghệ hệ cao đẳng và đại học những kiến thức về bản chất các hiện tượng vật lý xảy ra trong tự nhiên, kiểm tra lại các lý thuyết vật lý đã được học trong chương trình nhằm rèn luyện cho các kỹ sư tương lai kỹ năng quan sát, tiến hành thí nghiệm, đo đạc và tính toán, phân tích, xử lý số liệu.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'PHYS111202';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS111202' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS111202' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('EEEN234162', 'Điện tử căn bản', 3, 3, NULL, '3(3:0:6)', NULL, 'Cung cấp cho sinh viên ngành công nghệ thông tin các kiến thức chung cơ bản và phương pháp phân tích, tính toán các mạch điện và mạch điện tử căn bản thường sử dụng trong thực tế như: mạch điện một chiều, mạch điện xoay chiều, mạch chỉnh lưu, mạch ổn áp, mạch ngắt dẫn dùng BJT, mạch khuếch đại tín hiệu, mạch dao động ... 15. Thực tập điện tử căn bản Môn học này hướng dẫn sinh viên thực hành các mạch kỹ thuật điện tử như mạch chỉnh lưu, mạch xén, mạch nguồn DC, mạch khuếch đại tín hiệu nhỏ, mạch transistor ngắt dẫn, mạch dao động, các mạch điều khiển dùng SCR, TRAC, DIAC, quang trở, op-to, các mạch đếm và thanh ghi và các mạch điện tử ứng dụng trong thực tế. B- Bộ môn Trí tuệ nhân tạo') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'EEEN234162';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'EEEN234162' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'EEEN234162' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('PRBE214262', 'Thực tập điện tử căn bản', 1, 1, NULL, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'PRBE214262';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('INIS130180', 'Nhập môn ngành', 3, 2, 1, '3(2:1:6)', NULL, 'Học phần Nhập Môn Ngành Công Nghệ Thông Tin được thiết kế để giúp sinh viên năm thứ nhất làm quen với môi trường học đại học, các kiến thức cơ bản của ngành, đồng thời hình thành các kỹ năng mềm và các chuẩn mực đạo đức, ứng xử cần có để sinh viên tiến bước thành công trong vai trò kỹ sư công nghệ thông tin. Cụ thể, học phần này trang bị cho người học các kiến thức cơ bản của ngành, như phần cứng, phần mềm, lập trình, mạng máy tính, cũng như các hiểu biết về lịch sử phát triển máy tính, các lĩnh vực nghiên cứu, xu hướng phát triển của ngành. Học phần cũng giúp người học phát triển các kỹ năng mềm hữu ích, như kỹ năng giải quyết vấn đề, phương pháp hiểu bản thân, kỹ năng tìm kiếm thông tin, kỹ năng làm việc nhóm, kỹ năng thuyết trình; và hiểu biết về các chuẩn mực đạo đức, phẩm chất cần có, như trung thực, kỷ luật, vị tha, khiêm tốn.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 1, 'Nhập môn ngành', 0 FROM courses WHERE course_code = 'INIS130180';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INIS130180' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INIS130180' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INIS130180' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INIS130180' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DIGR230485', 'Toán rời rạc và lý thuyết đồ thị', 3, 2, 1, '3(2:1:6)', NULL, 'Phần “Toán rời rạc” trang bị cho người học những kiến thức cơ bản về logic mệnh đề, logic vị từ, suy diễn logic, quan hệ tương đương, quan hệ thứ tự, dàn và đại số Bool. Cung cấp cho người học kiến thức và kỹ năng trong việc phân tích, nhìn nhận vấn đề, trong việc xác định công thức đa thức tối tiểu bằng phương pháp biểu đồ Karnaugh. Phần “Lý thuyết đồ thị” (LTĐT) trang bị cho người học những kiến thức cơ bản về lý thuyết đồ thị và sự hiểu biết về các lĩnh vực ứng dụng của lý thuyết đồ thị, cung cấp kiến thức nền tảng về lý thuyết đồ thị ứng dụng trong tin học. Cung cấp các thuật toán, kỹ thuật và kỹ năng lập trình các giải thuật trong lý thuyết đồ thị.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'DIGR230485';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DIGR230485' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DIGR230485' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DIGR230485' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DASA230179', 'Cấu trúc dữ liệu và giải thuật', 3, 2, 1, '3(2:1:6)', 'INPR130285', 'Học phần này cung cấp cho sinh viên kiến thức về các cấu trúc dữ liệu và giải thuật thông dụng trên máy tính. Giúp sinh viên có khả năng phân tích và xây dựng giải thuật bằng mã giả và hiện thực giải thuật trên máy tính bằng một ngôn ngữ lập trình C/C++. Ngoài ra, học phần này cũng cung cấp khả năng vận dụng cấu trúc dữ liệu và giải thuật đã học để giải quyết bài toán trong thực tế. Bên cạnh đó, sinh viên được làm việc trong các nhóm và thuyết trình các vấn đề nâng cao sử dụng các phương tiện trình chiếu.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'DASA230179';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DASA230179' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DASA230179' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DASA230179' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('OOPR230279', 'Lập trình hướng đối tượng', 3, 2, 1, '3(2:1:6)', 'INPR130285', 'Học phần nhằm cung cấp cho người học các kiến thức về công nghệ Visual .NET 2015/2017 của Microsoft, các thành phần chính của .NET framework; các thành phần cơ bản và cú pháp của ngôn ngữ C#; phương pháp luận trong lập trình OOP: lớp, đối tượng, thuộc tính, phương thức, sự thừa kế, tính đa hình, giao diện. Bên cạnh đó, môn học cung trang bị kiến thức và kỹ năng sử dụng cơ chế ủy quyền và việc đáp ứng của nó theo các sự kiện; xây dựng Generic với lớp, giao diện, phương thức; kiến thức cơ bản về LINQ và kỹ năng sử dụng các lớp dựng sẵn trong C# để xây dựng các chương trình WinForm đơn giản.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'OOPR230279';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OOPR230279' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OOPR230279' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OOPR230279' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OOPR230279' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('WIPR230579', 'Lập trình trên Windows', 3, 2, 1, '3(2:1:6)', 'OOPR230279', 'Môn học này cung cấp cho sinh viên kiến thức nền tảng và phương pháp lập trình trên môi trường windows. Sinh viên cũng được trang bị kiến thức về ADO.NET để làm việc với hệ quản trị cơ sở dữ liệu. Hơn nữa, sinh viên có khả năng phát triển các loại ứng dụng winform sử dựng các công nghệ như: windows form controls, graphic controls, LINQ to SQL, Entity framework, Microsoft report. Môn học này cũng cung cấp cho sinh viên khả năng áp dụng công nghệ .NET để giải quyết vấn đề thực tế. Ngoài ra, sinh viên có cơ hội làm việc nhóm và phát triển kỹ năng trình bày vấn đề trong môn học.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 4, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'WIPR230579';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'WIPR230579' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'WIPR230579' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('INSE330380', 'An toàn thông tin', 3, 2, 1, '3(2:1:6)', NULL, 'Môn học cung cấp cho sinh viên chuyên ngành Công nghệ Thông tin kiến thức cơ bản về An toàn thông tin trên máy tính như CIA, An toàn trên phần mềm, An toàn trên HĐH, An toàn trên Cơ sở dữ liệu; các vấn đề về An toàn trên mạng máy tính như Malware, Firewall, IDS/IPS; các vấn đề về mã hoá thông tin, các thuật toán hash, MAC, RSA, quản lý khóa trong các giao thức truyền trên mạng.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 4, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'INSE330380';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INSE330380' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INSE330380' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INSE330380' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INSE330380' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('WEPR330479', 'Lập trình Web', 3, 2, 1, '3(2:1:6)', 'OOPR230279', 'Môn học này cung cấp kiến thức nền tảng về các ứng dụng web được xây dựng bằng công nghệ Servlet và JSP trên nền tảng J2EE framework. Nội dung chủ yếu tập trung vào hai thành phần sau, thứ nhất, thư viện thẻ chuẩn JSTL (JavaServer Pages Standard Tag Library): tập các thẻ JSP với các chức năng chung hỗ trợ cho nhiều ứng dụng JSP, thứ hai, mô hình MVC (Model-View-Controller Pattern). Sau khi học xong môn học này, sinh viên được trang bị các kỹ năng phân tích và thiết kế; có khả năng ứng dụng mô hình MVC để phát triển một ứng dụng web hoàn chỉnh dựa trên công nghệ Servlet và JSP. Ngoài ra, các kỹ năng mềm như làm việc nhóm, trình bày báo cáo cũng được đưa vào môn học này.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 5, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'WEPR330479';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'WEPR330479' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'WEPR330479' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'WEPR330479' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('SOEN330679', 'Công nghệ phần mềm', 3, 3, 1, '3(2:1:6)', 'OOPR230279', 'Môn học cung cấp cho người học các kiến thức cơ bản về quy trình phát triển một sản phẩm phần mềm nói chung cũng như quy trình phát triển phần mềm theo phương pháp hướng đối tượng nói riêng. Người học được trang bị các kiến thức về ngôn ngữ mô hình hóa hợp nhất (UML), kỹ năng thiết kế và vẽ các loại lược đồ UML trên công cụ thiết kế. Bên cạnh đó, người học cũng được trang bị các kỹ năng về từng khâu trong quy trình như khảo sát hiện trạng, xác định yêu cầu, phân tích, thiết kế, cài đặt, kiểm thử, đóng gói và triển khai một sản phẩm phần mềm. Song song với các kỹ năng nghề nghiệp, người học còn được rèn luyện kỹ năng làm việc nhóm, kỹ năng viết báo cáo và sưu liệu phần mềm.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 5, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'SOEN330679';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SOEN330679' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SOEN330679' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SOEN330679' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SOEN330679' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SOEN330679' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('CAAL230180', 'Kiến trúc máy tính và hợp ngữ', 3, 2, 1, '3(2:1:6)', 'DASA230179, DIGR230485', 'Học phần cung cấp cho người học những kiến thức liên quan tới kiến trúc của máy tính cũng như tập lệnh của vi xử lý và lập trình hợp ngữ cho vi xử lý, cụ thể: - Cung cấp kiến thức về các hệ số đếm dùng trong máy tính - Kiến trúc tổng quát của bộ xử lý, hiệu suất máy tính, các loại bộ nhớ, các loại xuất nhập, ngắt - Cung cấp kiến thức về các cách biểu diễn dữ liệu trong máy tính - Giới thiệu kiến trúc một số họ vi xử lý của Intel : thanh ghi của họ x86, x86-64 - Cung cấp các kiến thức về việc sử dụng tập lệnh x86, x86-64 - Cung cấp kiến thức về lập trình hợp ngữ trên linux x64, các lời gọi hệ thống, gọi hợp ngữ từ ngôn ngữ cấp cao.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'CAAL230180';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'CAAL230180' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'CAAL230180' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('OPSY330280', 'Hệ điều hành', 3, 2, 1, '3(2:1:6)', 'CAAL230180', 'Học phần này trang bị cho người học những kiến thức cơ bản về Hệ điều hành, bao gồm: Mô hình tổng quát, cấu trúc, chức năng, các thành phần cơ bản của hệ điều hành. Các nguyên lý cơ bản để xây dựng Hệ điều hành. Tìm hiểu cấu trúc và việc ứng dụng các nguyên lý cơ bản trong các hệ điều hành cụ thể. Tìm hiểu và mô phỏng điều khiển thiết bị của Hệ điều hành thông qua lập trình hệ thống.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 4, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'OPSY330280';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OPSY330280' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OPSY330280' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OPSY330280' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('NEES330380', 'Mạng máy tính căn bản', 3, 2, 1, '3(2:1:6)', NULL, 'Môn học này cung các các khái niệm cơ bản trong mạng máy tính, đặc điểm cơ bản của các loại mạng; kiến thức về nguyên lý hoạt động của các thiết bị mạng, các kỹ thuật phổ biến triển khai trên hạ tầng mạng, các giao thức phổ biến hoạt động trong hệ thống mạng; các kiến thức về thiết kế, cấu hình và vận hành hệ thống mạng đơn giản.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'NEES330380';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'NEES330380' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'NEES330380' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'NEES330380' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DBSY230184', 'Cơ sở dữ liệu', 3, 2, 1, '3(2:1:6)', NULL, 'Học phần này trang bị cho người học những kiến thức cơ bản về cơ sở dữ liệu và kiến thức chuyên sâu về mô hình dữ liệu quan hệ: quan hệ, phụ thuộc hàm, các ràng buộc trên quan hệ, siêu khóa, khóa chính, khóa dự tuyển, khóa ngoại, bao đóng của tập phụ thuộc hàm, bao đóng của tập thuộc tính, phủ tối tiểu của tập phụ thuộc hàm, thuật toán tìm bao đóng của tập thuộc tính, thuật toán xác định khóa, các dạng chuẩn và tính chất tương ứng. Trang bị cho người học kiến thức về mô hình thực thể kết hợp để thiết kế CSDL.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 4, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'DBSY230184';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBSY230184' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBSY230184' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBSY230184' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBSY230184' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DBMS330284', 'Hệ quản trị cơ sở dữ liệu', 3, 2, 1, '3(2:1:6)', 'DBSY230184', 'Học phần này trang bị cho người học về nguyên lý của DBMS. Cách sử dụng ngôn ngữ lập trình PL/SQL, các định nghĩa và ứng dụng của thủ tục nội tại, bẫy lỗi, chỉ mục, lập trình CSDL, các quản lý truy cập trong DBMS, các nguyên lý quản lý giao tác, quản lý truy xuất cạnh tranh, phục hồi sau sự cố.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 5, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'DBMS330284';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBMS330284' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBMS330284' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBMS330284' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ARIN330585', 'Trí tuệ nhân tạo', 3, 2, 1, '3(2:1:6)', 'DASA230179', 'Môn học này giới thiệu tới người học các vấn đề, ý tưởng và giải thuật nền tảng trong lĩnh vực trí tuệ nhân tạo (artificial intelligence), bao gồm các giải thuật giải quyết vấn đề bằng tìm kiếm (solving problems by searching), và học củng cố (reinforcement learning). Việc nắm bắt được các ý tưởng và giải thuật này không chỉ giúp người học có khả năng giải quyết các vấn đề bằng AI, mà còn giúp người học có thể tiếp thu những thành tựu tiên tiến trong lĩnh vực dễ dàng hơn.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 4, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'ARIN330585';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ARIN330585' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ARIN330585' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ARIN330585' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ARIN330585' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('IPPA233277', 'Lập trình Python', 3, 2, 1, '3(2:1:6)', 'INPR130285', 'Python là một trong những ngôn ngữ lập trình đa dụng phổ biến hiện nay. Ngôn ngữ này đang ngày càng trở nên phổ biến hơn trong lĩnh vực kỹ thuật dữ liệu. Học phần này trang bị các kiến thức và kỹ năng cơ bản về lập trình sử dụng ngôn ngữ Python. Các kiến thức bao gồm cú pháp ngôn ngữ, các kiểu dữ liệu và cấu trúc dữ liệu thường sử dụng, các hàm tiện ích thường dùng, khái niệm lập trình hướng đối tượng trên Python. Ngoài ra, học phần còn cung cấp các kiến thức chuyên sâu về việc sử dụng các tiện ích mở rộng của Python trong xử lý dữ liệu, bao gồm phần tích khai phá dữ liệu, tiền xử lý dữ liệu, và xây dựng mô hình dự báo đơn giản.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'IPPA233277';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'IPPA233277' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'IPPA233277' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'IPPA233277' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'IPPA233277' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('INOT231780', 'Vạn Vật Kết Nối', 3, 2, 1, '3(2:1:6)', NULL, 'Học phần này cung cấp cho sinh viên những kiến thức về Hệ thống IoT, cụ thể: các khái niệm liên quan tới hệ thống IoT, kiến trúc hệ thống IoT, chồng giao thức cho IoT, các thành phần hardware, software, một số platform cho hệ thống IoT, công nghệ RFID, sensor…') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 4, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'INOT231780';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INOT231780' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INOT231780' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INOT231780' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('MALE431985', 'Học máy', 3, 2, 1, '3(2:1:6)', 'ARIN330585', 'Môn học giới thiệu cho sinh viên về lĩnh vực học máy và các giải thuật học máy phổ biến. Sinh viên sẽ thực hiện các bài tập lập trình bằng ngôn ngữ lập trình Python, và phân tích, đánh giá các giải thuật này. Sinh viên cũng sẽ thực tập hình thành ý tưởng, thiết kế và hiện thực hóa một hệ thống học máy đơn giản trong đồ án môn học xuyên suốt học kỳ.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 5, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'MALE431985';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MALE431985' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MALE431985' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MALE431985' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MALE431985' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MALE431985' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('MOPR331279', 'Lập trình di động', 3, 2, 1, '3(2:1:6)', 'OOPR230279', 'Học phần cung cấp cho sinh viên kiến thức và kĩ năng lập trình trên nền tảng Android. Đồng thời, còn cung cấp thông tin về kiến trúc và cách thức làm việc chung để sinh viên có thể tự nghiên cứu và tìm hiểu nhiều nền tảng di động khác.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 5, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'MOPR331279';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MOPR331279' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MOPR331279' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MOPR331279' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('PRTE230385', 'Kỹ thuật lập trình', 3, 2, 1, '3(2:1:6)', 'INPR130285', 'Môn học trang bị cho sinh viên những kiến thức về phân tích, đánh giá độ phức tạp của giải thuật, đồng thời cũng cung cấp các giải thuật và kỹ thuật lập trình để giải quyết bài toán thực tế cũng như nâng cao hiệu quả của các chương trình máy tính.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Kiến thức cơ sở ngành – Kiến thức bắt buộc', 0 FROM courses WHERE course_code = 'PRTE230385';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRTE230385' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'I' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRTE230385' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRTE230385' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DIPR430685', 'Xử lý ảnh số', 3, NULL, NULL, '3(2:1:6)', 'PRTE230385', 'Học phần này cung cấp cho người học những kiến thức và kỹ năng để viết được các chương trình xử lý ảnh số cơ bản. Trên cơ sở này, sinh viên có thể giải quyết được các bài toán như nâng cao chất lượng ảnh, mô tả thông tin đặc trưng của đối tượng trên ảnh và nhận dạng đối tượng trên ảnh.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức cơ sở ngành – Kiến thức tự chọn (chọn 3)', 1 FROM courses WHERE course_code = 'DIPR430685';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ESYS431080', 'Hệ thống nhúng', 3, NULL, NULL, '3(2:1:6)', 'PRTE230385', 'Học phần này cung cấp cho người học những kiến thức liên quan tới hệ thống nhúng, bao gồm: Những khái niệm tổng quan về mô hình hệ thống nhúng, tính chất, các ứng dụng của hệ thống nhúng; Các thành phần cơ bản của một hệ thống nhúng; Các phương pháp thiết kế hệ thống nhúng; Vi điều khiển ARM; Tập lệnh của vi điều khiển ARM; Kiến thức về nguyên tắc lập trình nhúng, các công cụ lập trình phần mềm nhúng.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức cơ sở ngành – Kiến thức tự chọn (chọn 3)', 1 FROM courses WHERE course_code = 'ESYS431080';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('FOIT331380', 'Lý thuyết thông tin', 3, NULL, NULL, '3(2:1:6)', NULL, 'Học phần cung cấp cho người học những kiến thức cơ bản của lý thuyết thông tin, bao gồm: Độ đo lượng tin (Measure of Information); Sinh mã tách được (Decypherable Coding); Kênh truyền tin rời rạc không nhớ (Discrete Memoryless Channel); Sửa lỗi kênh truyền (Error Correcting Coding).') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức cơ sở ngành – Kiến thức tự chọn (chọn 3)', 1 FROM courses WHERE course_code = 'FOIT331380';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ECOM430984', 'Thương mại điện tử', 3, NULL, NULL, '3(2:1:6)', NULL, 'Học phần giới thiệu về thương mại điện tử và cung cấp cho người học ba mảng kiến thức chủ đạo: các mô hình kinh doanh thương mại điện tử, các hoạt động marketing cho thương mại điện tử, và các vấn đề chủ đạo khi thiết kế, xây dựng, và vận hành nền tảng thương mại điện tử.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức cơ sở ngành – Kiến thức tự chọn (chọn 3)', 1 FROM courses WHERE course_code = 'ECOM430984';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('CLCO332779', 'Điện toán đám mây', 3, NULL, NULL, '3(2:1:6)', 'OOPR230279', 'Amazon Web Services, Google App Engine, Microsoft Azure, và các dịch vụ đám mây khác cho phép cá cá nhân và tổ chức có thể sử dụng được sức mạnh của những nguồn tài nguyên tính toán vô hạn theo mô hình pay-as-you-go mà không cần phải đầu tư quá nhiều ngay từ đầu. Trong môn học này, sinh viên sẽ được trang bị kiến thức về các APIs quan trọng của như những dịch vụ được cung cấp bởi Google, Amazon, và Microsoft Cloud, bao gồm các kỹ thuật xây dựng và triển khai các ứng dụng cũng như việc duy trì các máy ảo. Sinh viên sẽ được học: Cách sử dụng các mô hình đám mây như: Cloud as the infrastructure, Cloud as the platform, và Cloud ad the software services; Cách sử dụng các RESTFul Web services; Cách sử dụng cả Web interfaces và chế độ dòng lệnh (CLI) thông qua Linux/Unix terminal để làm việc với các Cloud service.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức cơ sở ngành – Kiến thức tự chọn (chọn 3)', 1 FROM courses WHERE course_code = 'CLCO332779';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('SPPR330885', 'Xử lý tiếng nói', 3, NULL, NULL, '3(2:1:6)', 'PRTE230385', 'Học phần này cung cấp cho người học những kiến thức và kỹ năng để viết được các chương trình xử lý tiếng nói cơ bản. Trên cơ sở này, sinh viên có thể giải quyết được các bài toán cơ bản của xử lý tiếng nói là nhận dạng và tổng hợp tiếng nói có bộ từ vựng nhỏ.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức cơ sở ngành – Kiến thức tự chọn (chọn 3)', 1 FROM courses WHERE course_code = 'SPPR330885';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('WESE331479', 'Bảo mật web', 3, 2, 1, '3(2:1:6)', 'SOEN330679', 'Học phần trang bị cho người học các kiến thức cơ bản về các rủi ro hàng đầu (OWASP Top 10) đối với ứng dụng Web, các hình thức tấn công phía Client: lừa đảo (phishing), session hijacking, browser extension exploration...; các hình thức tấn công phía Server: directory traversal, file inclusion...; một số hình thức tấn công khác: buffer overflow, SQL Injection. Học phần cũng trang bị cho người học kỹ năng tìm hiểu các giải pháp phòng chống, bảo vệ và sử dụng các kỹ thuật, công cụ hỗ trợ để xây dựng ứng dụng Web an toàn. D- Bộ môn Hệ thống thông tin') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành – Công Nghệ Phần Mềm', 0 FROM courses WHERE course_code = 'WESE331479';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'WESE331479' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'WESE331479' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'WESE331479' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('OOSD330879', 'Thiết kế phần mềm hướng đối tượng', 3, 2, 1, '3(2:1:6)', 'SOEN330679', 'Học phần nhằm cung cấp cho người học các kiến thức về công nghệ Visual .NET 2015/2017 của Microsoft, các thành phần chính của .NET framework; các thành phần cơ bản và cú pháp của ngôn ngữ C#; phương pháp luận trong lập trình OOP: lớp, đối tượng, thuộc tính, phương thức, sự thừa kế, tính đa hình, giao diện. Bên cạnh đó, môn học cung trang bị kiến thức và kỹ năng sử dụng cơ chế ủy quyền và việc đáp ứng của nó theo các sự kiện; xây dựng Generic với lớp, giao diện, phương thức; kiến thức cơ bản về LINQ và kỹ năng sử dụng các lớp dựng sẵn trong C# để xây dựng các chương trình WinForm đơn giản.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành – Công Nghệ Phần Mềm', 0 FROM courses WHERE course_code = 'OOSD330879';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OOSD330879' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OOSD330879' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OOSD330879' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('SOTE431079', 'Kiểm thử phần mềm', 3, 2, 1, '3(2:1:6)', 'SOEN330679', 'Học phần nhằm cung cấp cho người học kiến thức cơ bản về kiểm thử phần mềm, quy trình kiểm thử phần mềm, phân tích, thiết kế và cài đặt những kĩ thuật kiểm thử, mô hình CMMi. Sau khi kết thúc khoá học, sinh viên có thể nắm vững những thuật ngữ, định nghĩa, khái niệm trong kiểm thử phần mềm, có khả năng áp dụng kiến thức để thiết kế, thực thi và đánh giá chất lượng phần mềm. Ngoài ra, sinh viên còn có thể sử dụng những công cụ quản lí lỗi, và công cụ kiểm thử tự động.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành – Công Nghệ Phần Mềm', 0 FROM courses WHERE course_code = 'SOTE431079';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SOTE431079' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SOTE431079' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SOTE431079' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('MTSE431179', 'Các công nghệ phần mềm mới', 3, 2, 1, '3(2:1:6)', 'SOEN330679', 'Sinh viên sẽ xây dựng các ứng dụng web-based dựa trên 2 công nghệ Struts (1.x hay 2.x) MVC và Spring MVC trên nền J2EE framework.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành – Công Nghệ Phần Mềm', 0 FROM courses WHERE course_code = 'MTSE431179';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MTSE431179' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MTSE431179' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MTSE431179' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('POSE451479', 'Tiểu luận chuyên ngành CNPM', 5, 4, 1, '5', 'SOEN330679', 'Học phần này sinh viên sẽ được làm một dự án về chuyên ngành CNTT với sự hướng dẫn của GVHD trong suốt một học kỳ. Các chủ đề sẽ bao phủ một số học phần đã được học, liên quan đến các vấn đề phát triển các ứng dụng, mạng, hệ thống thông tin.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 7, 'Kiến thức chuyên ngành – Công Nghệ Phần Mềm', 0 FROM courses WHERE course_code = 'POSE451479';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ISAD330384', 'Phân tích và thiết kế hệ thống thông tin', 3, 2, 1, NULL, 'DBSY230184', NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành – Chuyên ngành Hệ thống Thông tin', 0 FROM courses WHERE course_code = 'ISAD330384';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ISAD330384' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ISAD330384' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ISAD330384' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DAMI330484', 'Khai phá dữ liệu', 3, 2, 1, '3(2:1:6)', 'DBSY230184', 'Học phần này trang bị cho người học những kiến thức cơ bản về các khái niệm, thuật toán và ứng dụng của khai phá dữ liệu. Ngoài ra, người học còn có cơ hội trải nghiệm các thư viện, công cụ mã nguồn mở để cài đặt và thử nghiệm thuật toán khai phá dữ liệu. Các chủ đề được đề cập đến trong học phần bao gồm: các khái niệm cơ bản, các ứng dụng và quá trình khai phá dữ liệu, các vấn đề liên quan đến quá trình tiền xử lý dữ liệu, các thuật toán khai phá luật kết hợp (Apriori, FP-Growth, …), các thuật toán phân loại (k-NN, cây quyết định, Naive Bayes, ...), các thuật toán gom cụm (gom cụm phân hoạch k-means, gom cụm phân cấp gộp AGNES, gom cụm dựa trên mật độ DBSCAN, …), các thuật toán phân tích ngoại biên (dựa trên thống kê, dựa trên xấp xỉ, dựa trên gom cụm, dựa trên phân loại), và các độ đo và phương pháp đánh giá các thuật toán khai phá dữ liệu.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành – Chuyên ngành Hệ thống Thông tin', 0 FROM courses WHERE course_code = 'DAMI330484';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAMI330484' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAMI330484' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAMI330484' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.3';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('BDES333877', 'Nhập môn dữ liệu lớn (Big data essential)', 3, 2, 1, '3(2:1:6)', 'DBSY230184', 'Môn học này thuộc nhóm môn học cơ sở ngành, nhằm cung cấp cho người học các kiến thức tổng quan về cơ sở dữ liệu lớn, những ứng dụng của cở sở dữ liệu lớn. Ngoài ra, người học còn được cung cấp những kiến thức về các kỹ thuật cơ bản trong lưu trữ và xử lý, phân tích cơ sở dữ liệu lớn. Về mặt kỹ năng, người học được trang bị khả năng sử dụng một số công cụ phân tích cơ sở dữ liệu lớn thông dụng. Bên cạnh đó, người học cũng được trang bị một số kỹ năng mềm bao gồm: kỹ năng tìm kiếm, chọn lọc và tổng hợp tài liệu, kỹ năng viết và trình bày báo cáo, kỹ năng làm việc nhóm.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành – Chuyên ngành Hệ thống Thông tin', 0 FROM courses WHERE course_code = 'BDES333877';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'BDES333877' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'BDES333877' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'BDES333877' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DBSE431284', 'Bảo mật CSDL', 3, 2, 1, NULL, 'DBSY230184', NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành – Chuyên ngành Hệ thống Thông tin', 0 FROM courses WHERE course_code = 'DBSE431284';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBSE431284' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBSE431284' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBSE431284' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('POIS451184', 'Tiểu luận chuyên ngành HTTT', 5, 4, 1, '5', 'DBSY230184', 'Học phần này sinh viên sẽ được làm một dự án về chuyên ngành CNTT với sự hướng dẫn của GVHD trong suốt một học kỳ. Các chủ đề sẽ bao phủ một số học phần đã được học, liên quan đến các vấn đề phát triển các ứng dụng, mạng, hệ thống thông tin.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 7, 'Kiến thức chuyên ngành – Chuyên ngành Hệ thống Thông tin', 0 FROM courses WHERE course_code = 'POIS451184';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('MAAI330985', 'Toán cho trí tuệ nhân tạo', 3, 2, 1, '3(2:1:6)', 'ARIN330585', 'Học phần này cung cấp cho người học hai phần: Phần 1 là những kiến thức cơ bản toán học như đại số tuyến tính, giải tích vector, hình học giải tích, phân tích ma trận, xác suất, phân phối và tối ưu. Phần 2 là áp dụng những kiến toán ở phần 1 để giải quyết các vấn đề cơ bản của trí tuệ nhân tạo như hồi quy, giảm bớt số chiều, ước lượng hàm mật độ và phân lớp Trên cơ sở này, sinh viên có thể vận dụng kiến thức của học phần này để học các môn tiếp theo về trí tuệ nhân tạo như học máy và học sâu.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành – Chuyên ngành Trí tuệ nhân tạo', 0 FROM courses WHERE course_code = 'MAAI330985';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MAAI330985' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MAAI330985' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MAAI330985' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('INDS331085', 'Nhập môn Khoa học dữ liệu', 3, 2, 1, '3(2:1:6)', 'ARIN330585', 'Học phần này trang bị cho người học những kiến thức cơ bản về các khái niệm, thuật toán và ứng dụng của khoa học dữ liệu. Người học còn có cơ hội trải nghiệm các thư viên, công cụ mã nguồn mở để cài đặt và thử nghiệm thuật toán để phân tích dữ liệu. Các chủ đề được đề cập đến trong học phần bao gồm: các khái niệm cơ bản và các ứng dụng của khoa học dữ liệu, các vấn đề liên quan đến quá trình tiền xử lý dữ liệu, các thuật toán phân loại, hồi quy (linear and logistic regression, k-NN, decision tree, random forest, neural network), các thuật toán gom cụm (gom cụm phân hoạch k-means, mixture models, gom cụm phân cấp gộp AGNES, gom cụm dựa trên mật độ DBSCAN), các phương pháp thu giảm số chiều (PCA, LDA, Autoencoder), và các độ đo, phương pháp đánh giá các thuật toán.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành – Chuyên ngành Trí tuệ nhân tạo', 0 FROM courses WHERE course_code = 'INDS331085';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INDS331085' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INDS331085' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INDS331085' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.3';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('BDPR431385', 'Xử lý dữ liệu lớn', 3, 2, 1, '3(2:1:6)', 'ARIN330585', 'Học phần này trang bị cho người học những kiến thức cơ bản về các khái niệm và kỹ thuật xử lý dữ liệu lớn. Người học còn có cơ hội trải nghiệm các thư viên, công cụ mã nguồn mở như Hadoop, Hive, Pig, và Spark để xử lý và phân tích dữ liệu lớn. Các chủ đề được đề cập đến trong học phần bao gồm: các khái niệm cơ bản về dữ liệu lớn, các vấn đề liên quan đến xử lý, lưu trữ, truy vấn, và phân tích dữ liệu lớn.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành – Chuyên ngành Trí tuệ nhân tạo', 0 FROM courses WHERE course_code = 'BDPR431385';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'BDPR431385' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'BDPR431385' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'BDPR431385' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DLEA432085', 'Học sâu', 3, 2, 1, '3(2:1:6)', 'ARIN330585', 'Học phần này cung cấp kiến thức nền tảng và giúp xây dựng kỹ năng sử dụng các kỹ thuật deep learning để giải quyết các bài toán học máy. Các nội dung chính bao gồm: căn bản về mạng neuron, cài đặt ANNs sử dụng Tensorflow APIs, tiền xử lý dữ liệu, huấn luyện deep ANNs, mạng neurons tích chập (CNNs), mạng neuron hồi quy (RNNs).') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành – Chuyên ngành Trí tuệ nhân tạo', 0 FROM courses WHERE course_code = 'DLEA432085';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DLEA432085' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DLEA432085' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DLEA432085' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DLEA432085' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('POAI451485', 'Tiểu luận chuyên ngành TTNT', 5, 4, 1, '5', 'ARIN330585', 'Học phần này sinh viên sẽ được làm một dự án về chuyên ngành CNTT với sự hướng dẫn của GVHD trong suốt một học kỳ. Các chủ đề sẽ bao phủ một số học phần đã được học, liên quan đến các vấn đề phát triển các ứng dụng, mạng, hệ thống thông tin.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức chuyên ngành – Chuyên ngành Trí tuệ nhân tạo', 0 FROM courses WHERE course_code = 'POAI451485';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('TOEN430979', 'Công cụ và môi trường phát triển PM', 3, 2, 1, '3(2:1:6)', 'SOEN330679', 'Môn học nhằm mục đích cung cấp cho người học các kiến thức về cú pháp, ý nghĩa và công dụng và các lĩnh vực ứng dụng của ngôn ngữ mô hình hóa hợp nhất UML; mô hình hướng đối tượng và các loại lược đồ trong UML; các quy trình phát triển phần mềm, tiêu biểu là quy trình hợp nhất của Rational (RUP) và quy trình phát triển phần mềm linh hoạt (agile methodology). Ngoài ra, môn học còn trang bị cho người học kỹ năng sử dụng công cụ thiết kế phần mềm để lập các lược đồ bằng UML; kỹ năng sử dụng một số công cụ phát triển để phục vụ cho quá trình phát triển một sản phẩm phần mềm hoàn chỉnh. Bên cạnh đó còn có các kỹ năng mềm gồm kỹ năng làm việc nhóm và đọc tài liệu chuyên ngành bằng tiếng Anh; kỹ năng viết báo cáo và trình bày báo cáo.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức chuyên ngành – Công Nghệ Phần Mềm', 1 FROM courses WHERE course_code = 'TOEN430979';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('SOPM431679', 'Quản lý dự án phần mềm', 3, 2, 1, '3(2:1:6)', 'SOEN330679', 'Môn học cung cấp cho người học các kiến thức về các khái niệm trong quản lý dự án công nghệ thông tin đặc biệt là dự án công nghệ phần mềm; các mảng công việc trong quản lý dự án công nghệ phần mềm; các kiến thức và kỹ năng lập kế hoạch cho dự án, quản lý yêu cầu của dự án,, quản lý thời gian và chi phí thực hiện dự án, quản lý nguồn nhân lực của dự án, quản lý rủi ro cũng như kiểm soát chất lượng của dự án. Ngoài ra, môn học còn trang bị cho người học các kỹ năng mềm như kỹ năng làm việc nhóm và trình bày trước đám đông.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức chuyên ngành – Công Nghệ Phần Mềm', 1 FROM courses WHERE course_code = 'SOPM431679';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ADMP431879', 'Lập trình di động nâng cao', 3, 2, 1, '3(2:1:6)', 'SOEN330679', 'Ionic là một framework dùng để phát triển một ứng dụng hybrid cho thiết bị di động. Ionic giúp cho các nhà phát triển web cách thức xây dựng ứng dụng dành cho thiết bị di động đa nền tảng cho điện thoại và máy tính bảng trên iOS và Android. Sinh viên sẽ tìm hiểu cách mở rộng các kỹ năng phát triển Web của mình để xây dựng các ứng dụng đa nền tảng (cross-platform).') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức chuyên ngành – Công Nghệ Phần Mềm', 1 FROM courses WHERE course_code = 'ADMP431879';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ADPL331379', 'Ngôn ngữ Lập trình tiên tiến', 3, 2, 1, '3(2:1:6)', 'SOEN330679', 'Sinh viên sẽ nắm vững phương pháp luận trong lập trình hướng đối tượng qua ngôn ngữ lập trình Java , sử dụng trong việc tạo ra các ứng dụng quản lý trên nền Winform, WebForm hoặc trên các thiết bị điện thoại di động và xây dựng giao diện người dùng đẹp và thân thiện. Đồng thời, sinh viên có khả năng tương tác với các loại cơ sở dữ liệu như MySQL, PostgreSQL, DB2 và SQL Server và trình bày dữ liệu theo nhiều hình thức khác nhau. Vận dụng tốt ngôn ngữ Java trong các bài tập, đề án môn học và đề tài tốt nghiệp.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức chuyên ngành – Công Nghệ Phần Mềm', 1 FROM courses WHERE course_code = 'ADPL331379';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ADDB331784', 'Cơ sở dữ liệu Nâng cao', 3, 2, 1, '3(2:1:6)', 'DBSY230184', 'Học phần này giới thiệu những kiến thức tổng quát về một số loại cơ sở dữ liệu (CSDL) mở rộng: CSDL hướng đối tượng, CSDL bán cấu trúc XML, CSDL NoSQL, CSDL phân cấp (blockchain)... Học phần tập trung vào Big Data và CSDL NoSQL, so sánh CSDL quan hệ truyền thống với CSDL NoSQL, phân loại các loại CSDL NoSQL (key-value, document-based, column- based, graph), cài đặt một CSDL NoSQL cụ thể (VD: MongoDB, Cassandra, CouchDB...), thực hiện tạo lập, lưu trữ, quản lý và thao tác dữ liệu trên cơ sở dữ liệu này.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức chuyên ngành – Chuyên ngành Hệ thống Thông tin', 1 FROM courses WHERE course_code = 'ADDB331784';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DAWH430784', 'Kho dữ liệu', 3, 2, 1, '3(2:1:6)', 'DBSY230184', 'Môn học cung cấp cho sinh viên những kiến thức cơ bản về kho dữ liệu. Trong khóa học này, người học sẽ học các khái niệm cơ bản về kho dữ liệu, kiến trúc kho dữ liệu và các mô hình đa chiều. Họ sẽ được thực hành về thiết kế kho dữ liệu và sử dụng các công cụ phổ biến tạo các luồng công việc tích hợp dữ liệu (data integration workflows). Bên cạnh đó, những người học cũng sẽ học cách sử dụng các phần mở rộng của SQL được hỗ trợ bởi các hệ quản trị cơ sở dữ liệu quan hệ để trả lời các câu hỏi phân tích trong kinh doanh.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức chuyên ngành – Chuyên ngành Hệ thống Thông tin', 1 FROM courses WHERE course_code = 'DAWH430784';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('INRE431084', 'Truy tìm thông tin', 3, 2, 1, '3(2:1:6)', 'DBSY230184', 'Học phần cung cấp kiến thức nền tảng giúp người học hiểu được cách làm việc cũng như cách xây dựng một hệ thống truy tìm (tìm kiếm) thông tin, đặc biệt là thông tin ở dạng văn bản. Cụ thể, sau khi hoàn thành học phần, người học sẽ trình bày được kiến trúc tổng quát của một hệ thống truy tìm thông tin, quá trình tiền xử lý và xây dựng chỉ mục tài liệu. Đặt biệt, người học sẽ có cơ hội được cài đặt các mô hình truy tìm thông tin quan trọng (như mô hình không gian vector, mô hình xác suất, mô hình ngôn ngữ) và các kỹ thuật phản hồi và mở rộng truy vấn. Người học cũng sẽ được trang bị kiến thức về phương pháp đánh giá thực nghiệm một hệ thống truy tìm thông tin để có thể đánh giá và so sánh các thuật toán, mô hình. Ngoài ra, cách hoạt động của một hệ thống tìm kiếm thông tin trên web (web search engine) cũng sẽ được trình bày.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức chuyên ngành – Chuyên ngành Hệ thống Thông tin', 1 FROM courses WHERE course_code = 'INRE431084';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DAAN436277', 'Phân tích dữ liệu (Data analytics)', 3, 2, 1, '3(2:1:6)', 'DBSY230184', 'Học phần cung cấp cho sinh viên kiến thức về kiến trúc của các hệ thống và các công cụ phục vụ cho hoạt động phân tích dữ liệu lớn. Với mỗi công cụ, môn học giới thiệu các kiến thức cơ bản và nâng cao cũng như phương thức tối ưu hóa hiệu suất hệ thống sử dụng công cụ này. Cùng với các bài tập lập trình, môn học hướng đến mục tiêu giúp người học có thể hình thành ý tưởng, thiết kế và hiện thực hóa hoạt động phân tích dữ liệu trong các hệ thống dữ liệu lớn.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức chuyên ngành – Chuyên ngành Hệ thống Thông tin', 1 FROM courses WHERE course_code = 'DAAN436277';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('AIOT331185', 'Trí tuệ nhân tạo cho IOT', 3, 2, 1, '3(2:1:6)', 'ARIN330585', 'Môn học này cung cấp cho sinh viên kiến thức nền tảng và phương pháp ứng dụng AI trong IoT. Sinh viên có khả năng xây dựng các ứng dụng IoT và làm cho ứng dụng trở nên thông minh hơn bằng cách bổ sung nhưng kiến thức vể artificial intelligence, machine learning, deep learning. Sinh viên cũng biết cách sử dụng các công cụ như TensorFlow và Keras.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức chuyên ngành – Chuyên ngành Trí tuệ nhân tạo', 1 FROM courses WHERE course_code = 'AIOT331185';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('PCOM331285', 'Tính toán song song', 3, 2, 1, '3(2:1:6)', 'ARIN330585', 'Học phần này cung cấp kiến thức nền tảng về kỹ thuật thiết kế và xây dựng ứng dụng song song. Bên cạnh đó, sinh viên được trang bị kỹ năng xây dựng ứng dụng song song với các công nghệ MPI (Message Passing Interface), OpenMP, lập trình song song với GPU (Graphic Processing Unit) sử dụng thư viện CUDA.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức chuyên ngành – Chuyên ngành Trí tuệ nhân tạo', 1 FROM courses WHERE course_code = 'PCOM331285';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('NLPR431585', 'Xử lý ngôn ngữ tự nhiên', 3, 2, 1, '3(2:1:6)', 'ARIN330585', 'Học phần này trang bị cho người học những kiến thức cơ bản về các khái niệm và kỹ thuật xử lý ngôn ngữ tự nhiên. Người học có cơ hội trải nghiệm các thư viên, công cụ mã nguồn mở để để xử lý ngôn ngữ tự nhiên. Các chủ đề được đề cập đến trong học phần bao gồm: các ứng dụng và thách thức của xử lý ngôn ngữ tự nhiên, các bài toán và mô hình xử lý ngôn ngữ tự nhiên như: phân loại biểu cảm, tìm kiếm văn bản, biểu diễn văn bản, dịch ngôn ngữ tự động, và các chủ đề liên quan khác.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức chuyên ngành – Chuyên ngành Trí tuệ nhân tạo', 1 FROM courses WHERE course_code = 'NLPR431585';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('RELE431685', 'Học tăng cường', 3, 2, 1, '3(2:1:6)', 'ARIN330585', 'Học phần này cung cấp kiến thức nền tảng và giúp xây dựng kỹ năng sử dụng các kỹ thuật reinforcement learning để giải quyết các bài toán trí tuệ nhân tạo. Các nội dung chính bao gồm: căn bản về reinforcement learning, thư viện OpenAI Gym và Pytorch, phương pháp Cross-Entropy, Deep Q-learning, Policy gradients, REINFORCE, Actor-Critic. C- Bộ môn Công nghệ phần mềm') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức chuyên ngành – Chuyên ngành Trí tuệ nhân tạo', 1 FROM courses WHERE course_code = 'RELE431685';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ITIN421085', 'Thực tập Tốt Nghiệp', 2, NULL, NULL, '2(2:0:4)', NULL, 'Môn học này trang bị cho sinh viên các kiến thức thực tế liên quan tới môi trường làm việc tại doanh nghiệp, sử dụng kiến thức đã học trong việc tham gia các dự án thực tế tại doanh nghiệp, hoặc tiếp thu một số công nghệ mới và vận dụng chúng trong việc triển khai, vận hành hệ thống công nghệ thông tin. Đồng thời qua việc thực tập sinh viên có thể phát triển tư duy trong tương lai với vai trò quản lý.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 7, 'Thực tập tốt nghiệp', 0 FROM courses WHERE course_code = 'ITIN421085';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ITIN421085' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ITIN421085' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ITIN421085' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ITIN421085' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ITIN421085' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ITIN421085' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ITIN421085' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ITIN421085' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ITIN421085' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('GRPR473880', 'Khóa luận tốt nghiệp', 7, NULL, NULL, '7', NULL, 'Học phần này sinh viên sẽ được làm một dự án về chuyên ngành CNTT với sự hướng dẫn của GVHD trong suốt một học kỳ. Các chủ đề sẽ bao phủ hầu hết các học phần đã được học liên quan đến phát triển ứng dụng ứng dụng, mạng, hệ thống thông tin, đồng thời mở rộng hay đi sâu thêm kiến thức về CNTT.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 8, 'Khoá luận tốt nghiệp', 0 FROM courses WHERE course_code = 'GRPR473880';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR473880' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR473880' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR473880' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR473880' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR473880' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR473880' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR473880' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR473880' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR473880' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('SEMI310026', 'Chuyên đề Doanh nghiệp', 1, NULL, NULL, '1(1:0:2)', NULL, 'Môn học này trang bị cho sinh viên các kiến thức cập nhật thực tế về các công nghệ mới trong lĩnh vực công nghệ thông tin, cũng như một số kiến thức về kỹ năng mềm, kỹ năng làm việc trong môi trường doanh nghiệp, dưới hình thức chuyên đề khách mời – là những chuyên gia có kinh nghiệm làm việc trong các doanh nghiệp.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 7, 'Chuyên đề bổ trợ', 0 FROM courses WHERE course_code = 'SEMI310026';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SEMI310026' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SEMI310026' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'R' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SEMI310026' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, 'M' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SEMI310026' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DICO132585', 'Chuyên đề nâng cao năng lực số', 3, NULL, NULL, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Chuyên đề bổ trợ', 0 FROM courses WHERE course_code = 'DICO132585';

-- ===================== KTDL-2026: Kỹ thuật dữ liệu
INSERT IGNORE INTO programs (code, name, name_en, level, department, faculty, major_code, cohort_year, total_credits, decision_no, objective, target_pct) VALUES ('KTDL-2026', 'Kỹ thuật dữ liệu', 'Data Engineering', 'Đại học', NULL, 'Khoa Công nghệ thông tin', '7480203', 2026, 150, '3050/QĐ-ĐHCNKT ngày 14/8/2026', 'Đào tạo kỹ sư ngành Kỹ thuật dữ liệu (KTDL) phát triển toàn diện, có đạo đức, tri thức, sức khỏe, thẩm mỹ, trung thành với lý tưởng dân tộc và chủ nghĩa xã hội, có kiến thức khoa học cơ bản, kiến thức cơ sở và chuyên ngành về KTDL, có khả năng phân tích, giải quyết vấn đề, có khả năng đánh giá và lựa chọn các giải pháp phù hợp, có năng lực xây dựng và quản trị các hệ thống dữ liệu lớn, có kỹ năng giao tiếp và làm việc nhóm, có thái độ nghề nghiệp phù hợp và năng lực tự học để đáp ứng được các yêu cầu phát triển của ngành và xã hội. Với kiến thức cơ sở ngành và chuyên ngành Kỹ thuật dữ liệu được trang bị, học viên có khả năng nghiên cứu một cách độc lập, sáng tạo, có năng lực phát hiện và giải quyết vấn đề kỹ thuật phức tạp. Ngoài ra, chương trình cung cấp nền tảng kiến thức vững chắc để học viên có thể tiếp tục nâng cao và mở rộng kiến thức nhằm thích ứng với nhu cầu phát triển kinh tế - xã hội trong nước và quốc tế.', 75.00);
SET @p := (SELECT id FROM programs WHERE code = 'KTDL-2026');
INSERT IGNORE INTO plos (program_id, group_no, plo_code, description, target_pct, competency_level, plo_type) VALUES (@p, 1, 'PLO1', 'Khả năng áp dụng các nguyên tắc toán học, thuật toán, cũng như khoa học để xác định giải pháp cho vấn đề trong công nghệ thông tin.', 75.00, 3, 'CĐR chung');
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI1.1', 'Xác định vấn đề tính toán trong lĩnh vực CNTT.', 2 FROM plos WHERE program_id = @p AND plo_code = 'PLO1';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI1.2', 'Áp dụng các nguyên tắc toán học, thuật toán, và khoa học để xác định giải pháp trong lĩnh vực CNTT', 3 FROM plos WHERE program_id = @p AND plo_code = 'PLO1';
INSERT IGNORE INTO plos (program_id, group_no, plo_code, description, target_pct, competency_level, plo_type) VALUES (@p, 3, 'PLO2', 'Khả năng nhận biết trách nhiệm nghề nghiệp và đưa ra những đánh giá sáng suốt trong xây dựng giải pháp kỹ thuật dữ liệu dựa trên các nền tảng pháp lý và đạo đức.', 75.00, 4, 'CĐR chung');
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI2.1', 'Nhận thức trách nhiệm nghề nghiệp và đạo đức liên quan đến vấn đề về Kỹ thuật dữ liệu.', 2 FROM plos WHERE program_id = @p AND plo_code = 'PLO2';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI2.2', 'Đánh giá tác động của các giải pháp kỹ thuật cho bài toán đến cộng đồng và xã hội.', 4 FROM plos WHERE program_id = @p AND plo_code = 'PLO2';
INSERT IGNORE INTO plos (program_id, group_no, plo_code, description, target_pct, competency_level, plo_type) VALUES (@p, 1, 'PLO3', 'Khả năng tiếp thu và áp dụng kiến thức mới, sử dụng các chiến lược học tập phù hợp.', 75.00, 3, 'CĐR chuyên biệt');
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI3.1', 'Kỹ năng áp dụng kiến thức mới để giải quyết vấn đề về Công nghệ thông tin.', 3 FROM plos WHERE program_id = @p AND plo_code = 'PLO3';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI3.2', 'Kỹ năng áp dụng những chiến lược học tập hiệu quả.', 3 FROM plos WHERE program_id = @p AND plo_code = 'PLO3';
INSERT IGNORE INTO plos (program_id, group_no, plo_code, description, target_pct, competency_level, plo_type) VALUES (@p, 2, 'PLO4', 'Khả năng hoạt động hiệu quả trong một nhóm mà các thành viên cùng nhau lãnh đạo, tạo ra một môi trường hợp tác và hòa nhập, thiết lập các mục tiêu, lập kế hoạch nhiệm vụ và đáp ứng các mục tiêu.', 75.00, 3, 'CĐR chung');
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI4.1', 'Áp dụng những kiến thức cho việc thiết lập một môi trường làm việc nhóm hiệu quả.', 3 FROM plos WHERE program_id = @p AND plo_code = 'PLO4';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI4.2', 'Vận dụng được các phương pháp làm việc nhóm hiệu quả.', 3 FROM plos WHERE program_id = @p AND plo_code = 'PLO4';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI4.3', 'Thể hiện trách nhiệm công việc được giao và đóng góp vào sự thành công của nhóm.', 3 FROM plos WHERE program_id = @p AND plo_code = 'PLO4';
INSERT IGNORE INTO plos (program_id, group_no, plo_code, description, target_pct, competency_level, plo_type) VALUES (@p, 2, 'PLO5', 'Khả năng giao tiếp hiệu quả với nhiều đối tượng, và giao tiếp bằng tiếng Anh.', 75.00, 4, 'CĐR chuyên biệt');
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI5.1', 'Khả năng giải thích, truyền đạt nội dung công việc dưới dạng văn bản', 3 FROM plos WHERE program_id = @p AND plo_code = 'PLO5';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI5.2', 'Khả năng giải thích, truyền đạt những hiểu biết đến mọi người bằng lời nói', 4 FROM plos WHERE program_id = @p AND plo_code = 'PLO5';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI5.3', 'Khả năng đọc, hiểu, viết sử dụng tiếng Anh trong Công nghệ Thông tin', 4 FROM plos WHERE program_id = @p AND plo_code = 'PLO5';
INSERT IGNORE INTO plos (program_id, group_no, plo_code, description, target_pct, competency_level, plo_type) VALUES (@p, 2, 'PLO6', 'Khả năng thiết kế, cài đặt, và đánh giá giải pháp để đáp ứng các yêu cầu cụ thể trong lĩnh vực Kỹ thuật dữ liệu.', 75.00, 6, 'CĐR chuyên biệt');
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI6.1', 'Thiết lập yêu cầu, xác định chức năng cho các vấn đề liên quan đến Kỹ thuật dữ liệu', 4 FROM plos WHERE program_id = @p AND plo_code = 'PLO6';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI6.2', 'Phân tích, thiết kế và cài đặt các bài toán trong lĩnh vực Kỹ thuật dữ liệu', 6 FROM plos WHERE program_id = @p AND plo_code = 'PLO6';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI6.3', 'Đánh giá các giải pháp về mức độ đáp ứng các yêu cầu của bài toán.', 5 FROM plos WHERE program_id = @p AND plo_code = 'PLO6';
INSERT IGNORE INTO plos (program_id, group_no, plo_code, description, target_pct, competency_level, plo_type) VALUES (@p, 2, 'PLO7', 'Khả năng áp dụng các công nghệ phù hợp để tạo ra các giải pháp về kỹ thuật dữ liệu.', 75.00, 6, 'CĐR chuyên biệt');
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI7.1', 'Áp dụng các công nghệ về phần mềm, hệ thống thông tin, và trí tuệ nhân tạo để tạo ra giải pháp KTDL.', 6 FROM plos WHERE program_id = @p AND plo_code = 'PLO7';
INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) SELECT id, 'PI7.2', 'Áp dụng công nghệ dữ liệu lớn để tạo ra giải pháp KTDL.', 6 FROM plos WHERE program_id = @p AND plo_code = 'PLO7';

INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('LLCT130105', 'Triết học Mác - Lênin', 3, 3, NULL, '3(3/0/6)', NULL, 'Học phần gồm 3 chương, cung cấp cho sinh viên kiến thức: Chương 1 trình bày những nét khái quát nhất về triết học, triết học Mác - Lênin, và vai trò của triết học Mác - Lênin trong đời sống xã hội. Chương 2 trình bày những nội dung cơ bản của chủ nghĩa duy vật biện chứng, gồm vấn đề vật chất và ý thức; phép biện chứng duy vật; lý luận nhận thức của chủ nghĩa duy vật biện chứng. Chương 3 trình bày những nội dung cơ bản của chủ nghĩa duy vật lịch sử, gồm vấn đề hình thái kinh tế xã hội; giai cấp và dân tộc; nhà nước và cách mạng xã hội; ý thức xã hội; triết học về con người.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 1, 'Lý luận chính trị + Pháp luật đại cương', 0 FROM courses WHERE course_code = 'LLCT130105';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT130105' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT130105' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT130105' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT130105' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT130105' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT130105' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT130105' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT130105' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT130105' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('LLCT120205', 'Kinh tế chính trị Mác - Lênin', 2, 2, NULL, '2(2/0/4)', 'LLCT130105', 'Học phần gồm 6 chương, cung cấp cho sinh viên kiến thức: Chương 1 trình bày về đối tượng, phương pháp nghiên cứu và chức năng của kinh tế chính trị Mác - Lênin. Từ chương 2 đến chương 6 trình bày nội dung cốt lõi của kinh tế chính trị Mác - Lênin theo mục tiêu của môn học. Cụ thể các vấn đề như: Hàng hóa, thị trường và vai trò của các chủ thể trong nền kinh tế thị trường; Sản xuất giá trị thặng dư trong nền kinh tế thị trường; Cạnh tranh và độc quyền trong nền kinh tế thị trường; Kinh tế thị trường định hướng xã hội chủ nghĩa và các quan hệ lợi ích kinh tế ở Việt Nam; Công nghiệp hóa, hiện đại hóa và hội nhập kinh tế quốc tế của Việt Nam.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Lý luận chính trị + Pháp luật đại cương', 0 FROM courses WHERE course_code = 'LLCT120205';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120205' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120205' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120205' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120205' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120205' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120205' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120205' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120205' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120205' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('LLCT120405', 'Chủ nghĩa xã hội khoa học', 2, 2, NULL, '2(2/0/4)', 'LLCT130105', 'Học phần gồm 7 chương, cung cấp cho sinh viên kiến thức: Chương 1, trình bày những vấn đề cơ bản có tính nhập môn của Chủ nghĩa xã hội khoa học (quá trình hình thành, phát triển của Chủ nghĩa xã hội khoa học); từ chương 2 đến chương 7 trình bày những nội dung cơ bản của Chủ nghĩa xã hội khoa học theo mục tiêu môn học.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Lý luận chính trị + Pháp luật đại cương', 0 FROM courses WHERE course_code = 'LLCT120405';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('LLCT120314', 'Tư tưởng Hồ Chí Minh', 2, 2, NULL, '2(2:0:4)', 'LLCT130105', 'Học phần gồm 6 chương, cung cấp cho sinh viên kiến thức: Khái niệm, đối tượng, phương pháp nghiên cứu và ý nghĩa học tập môn tư tưởng Hồ Chí Minh; về cơ sở, quá trình hình thành và phát triển tư tưởng Hồ Chí Minh; Tư tưởng Hồ Chí Minh về: Độc lập dân tộc và chủ nghĩa xã hội; Đảng Cộng sản Việt Nam và Nhà nước của nhân dân, do nhân dân, vì nhân dân; Đại đoàn kết dân tộc và đoàn kết quốc tế; Văn hóa, con người; Đạo đức.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Lý luận chính trị + Pháp luật đại cương', 0 FROM courses WHERE course_code = 'LLCT120314';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120314' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120314' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120314' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120314' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120314' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120314' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120314' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120314' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'LLCT120314' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('LLCT220514', 'Lịch sử Đảng Cộng sản Việt Nam', 2, 2, NULL, '2(2/0/4)', 'LLCT120205, LLCT120314, LLCT120405, LLCT130105', 'Học phần gồm 3 chương, cung cấp cho sinh viên sự hiểu biết về đối tượng, mục đích, nhiệm vụ, phương pháp nghiên cứu, học tập môn Lịch sử Đảng và những kiến thức cơ bản, cốt lõi, hệ thống về sự ra đời của Đảng (1920-1930), quá trình Đảng lãnh đạo cuộc đấu tranh giành chính quyền (1930- 1945), lãnh đạo hai cuộc kháng chiến chống thực dân Pháp và đế quốc Mỹ xâm lược, hoàn thành giải phóng dân tộc, thống nhất đất nước (1945-1975), lãnh đạo cả nước quá độ lên chủ nghĩa xã hội và tiến hành công cuộc đổi mới (1975-2018). Qua đó khẳng định các thành công, nêu lên các hạn chế, tổng kết những kinh nghiệm về sự lãnh đạo cách mạng của Đảng để giúp người học nâng cao nhận thức, niềm tin đối với Đảng và khả năng vận dụng kiến thức đã học vào thực tiễn công tác, góp phần xây dựng và bảo vệ Tổ quốc Việt Nam xã hội chủ nghĩa.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Lý luận chính trị + Pháp luật đại cương', 0 FROM courses WHERE course_code = 'LLCT220514';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('GELA236939', 'Pháp luật đại cương', 3, 3, NULL, '3(3:0:6)', 'GELA220405', 'Học phần trang bị cho sinh viên các kiến thức cơ bản nhất về nhà nước và pháp luật, bao gồm: lý luận chung về nhà nước và pháp luật (nguồn gốc, bản chất, chức năng, đặc trưng cơ bản của nhà nước; nguồn gốc, hình thức, khái niệm, thuộc tính của pháp luật); hệ thống pháp luật và quan hệ pháp luật, vi phạm pháp luật và trách nhiệm pháp lý; các chế định luật cơ bản của một số ngành luật quan trọng.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Lý luận chính trị + Pháp luật đại cương', 0 FROM courses WHERE course_code = 'GELA236939';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GELA236939' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GELA236939' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GELA236939' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GELA236939' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('INPR130285', 'Nhập môn lập trình', 3, 2, 1, '3(2:1:6)', NULL, 'Học phần này trang bị cho người học những kiến thức cơ bản về cách biểu diễn dữ liệu trên máy tính, hệ thống số với các phép toán nhị phân, bát phân, thập lục phân, các bước giải một bài toán lập trình. Ngoài ra môn học này còn định hướng phương pháp tư duy, phong cách lập trình, cách giải quyết bài toán tin học bằng lưu đồ khối, lập trình các bài toán tin học đơn giản bằng ngôn ngữ lập trình C/C++.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 1, 'Tin học', 0 FROM courses WHERE course_code = 'INPR130285';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INPR130285' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INPR130285' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INPR130285' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ENCO140126', 'Kỹ năng giao tiếp tiếng Anh sơ cấp', 4, NULL, NULL, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 1, 'Kiến thức ngoại ngữ', 0 FROM courses WHERE course_code = 'ENCO140126';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ENCO240226', 'Kỹ năng giao tiếp tiếng Anh trung cấp', 4, NULL, NULL, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Kiến thức ngoại ngữ', 0 FROM courses WHERE course_code = 'ENCO240226';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('VNCD130615', 'Văn hóa Việt Nam và phát triển', 3, 3, 0, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Khối tự chọn Khoa học xã hội nhân văn/ kỹ năng học tập/ mục tiêu nghề nghiệp – Nhóm 1:Văn hoá - xã hội và phát triển', 1 FROM courses WHERE course_code = 'VNCD130615';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ASCD130605', 'Xã hội học ứng dụng và phát triển cộng đồng', 3, 3, 0, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Khối tự chọn Khoa học xã hội nhân văn/ kỹ năng học tập/ mục tiêu nghề nghiệp – Nhóm 1:Văn hoá - xã hội và phát triển', 1 FROM courses WHERE course_code = 'ASCD130605';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ENBP334808', 'Khởi nghiệp và lập kế hoạch kinh doanh', 3, 3, 0, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Khối tự chọn Khoa học xã hội nhân văn/ kỹ năng học tập/ mục tiêu nghề nghiệp – Nhóm 2: Khởi nghiệp - Kinh doanh', 1 FROM courses WHERE course_code = 'ENBP334808';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('MACU330909', 'Marketing và quản trị quan hệ khách hàng', 3, 3, 0, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Khối tự chọn Khoa học xã hội nhân văn/ kỹ năng học tập/ mục tiêu nghề nghiệp – Nhóm 2: Khởi nghiệp - Kinh doanh', 1 FROM courses WHERE course_code = 'MACU330909';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('EEEN234162', 'Kỹ thuật điện-điện tử', 3, NULL, NULL, '3(3:0:6)', NULL, 'Cung cấp cho sinh viên ngành công nghệ thông tin các kiến thức chung cơ bản và phương pháp phân tích, tính toán các mạch điện và mạch điện tử căn bản thường sử dụng trong thực tế như: mạch điện một chiều, mạch điện xoay chiều, mạch chỉnh lưu, mạch ổn áp, mạch ngắt dẫn dùng BJT, mạch khuếch đại tín hiệu, mạch dao động ...') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'EEEN234162';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'EEEN234162' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'EEEN234162' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'EEEN234162' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'EEEN234162' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'EEEN234162' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'EEEN234162' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'EEEN234162' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'EEEN234162' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'EEEN234162' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'EEEN234162' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'EEEN234162' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'EEEN234162' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DISY230165', 'Kỹ thuật số', 3, NULL, NULL, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Khối tự chọn Khoa học xã hội nhân văn/ kỹ năng học tập/ mục tiêu nghề nghiệp – Nhóm 3: Điện - Điện tử', 1 FROM courses WHERE course_code = 'DISY230165';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('CLET337339', 'Pháp luật hợp đồng trong kỹ thuật và công nghệ', 3, 3, 0, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Khối tự chọn Khoa học xã hội nhân văn/ kỹ năng học tập/ mục tiêu nghề nghiệp – Nhóm 4: Pháp Luật trong môi trường kỹ thuật', 1 FROM courses WHERE course_code = 'CLET337339';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('IPTT337439', 'Pháp luật về sở hữu trí tuệ và chuyển giao công nghệ', 3, 3, 0, NULL, NULL, NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Khối tự chọn Khoa học xã hội nhân văn/ kỹ năng học tập/ mục tiêu nghề nghiệp – Nhóm 4: Pháp Luật trong môi trường kỹ thuật', 1 FROM courses WHERE course_code = 'IPTT337439';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('MATH132101', 'Giải tích một biến số', 3, 3, NULL, '3(3:0:6)', NULL, 'Học phần Toán 1 cung cấp các kiến thức cơ bản về giới hạn, tính liên tục và phép tính vi tích phân của hàm một biến.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 1, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'MATH132101';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132101' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132101' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132101' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132101' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132101' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132101' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132101' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132101' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132101' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132101' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.3';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('MATH133601', 'Giải tích nhiều biến số', 3, 3, NULL, '3(3:0:6)', NULL, 'Học phần Toán 2 cung cấp các kiến thức cơ bản về phép tính tích phân của hàm nhiều biến, chuỗi số, chuỗi lũy thừa, véc-tơ trong mặt phẳng và trong không gian.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'MATH133601';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH133601' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH133601' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH133601' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH133601' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH133601' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH133601' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH133601' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH133601' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH133601' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH133601' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.3';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('MATH143001', 'Đại số tuyến tính và cấu trúc đại số', 4, 4, NULL, '4(4:0:8)', NULL, 'Môn học này bao gồm các kiến thức: Tập hợp, ánh xạ, quan hệ tương đương, quy nạp toán học; ma trận, định thức, hệ phương trình tuyến tính; không gian vectơ, không gian Euclide, ánh xạ tuyến tính, chéo hóa ma trận, dạng toàn phương; lý thuyết về một số cấu trúc đại số như nhóm, vành, trường; và một số ứng dụng như các mô hình tuyến tính, đồ họa máy tính, mã hóa, mật mã,….') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 1, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'MATH143001';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH143001' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH143001' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH143001' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH143001' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH143001' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH143001' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH143001' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH143001' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH143001' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH143001' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.3';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('MATH132901', 'Xác suất thống kê ứng dụng', 3, 3, NULL, '3(3:0:6)', NULL, 'Môn học này bao gồm thống kê mô tả, xác suất sơ cấp, biến ngẫu nhiên và luật phân phối xác suất, các số đặc trưng của biến ngẫu nhiên, ước lượng tham số, kiểm định giả thuyết, tương quan và hồi quy tuyến tính.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'MATH132901';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132901' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132901' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132901' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132901' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132901' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132901' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132901' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MATH132901' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.3';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('PHYS130902', 'Vật lý 1', 3, 3, NULL, '3(3:0:6)', NULL, 'Học phần này cung cấp cho sinh viên những nội dung cơ bản của vật lý bao gồm các phần cơ học và nhiệt học làm cơ sở cho việc tiếp cận các môn học chuyên ngành trình độ đại học các ngành khoa học, kỹ thuật và công nghệ. Sinh viên sẽ được trang bị các kiến thức về vật lý để khảo sát sự chuyển động, năng lượng và các hiện tượng vật lý liên quan đến các đối tượng trong tự nhiên có kích thước từ phân tử đến cỡ hành tinh. Sau khi học xong học phần sinh viên sẽ có khả năng ứng dụng những kiến thức đã học trong nghiên cứu khoa học cũng như trong phát triển kỹ thuật và công nghệ hiện đại. Nội dung của học phần gồm các chương từ 1 đến 22 trong sách Physics for Scientists and Engineers with Modern Physics, 9th Edition của các tác giả R.A. Serway và J.W. Jewett. Các nội dung của học phần này nhằm giúp sinh viên làm quen với phương pháp khoa học, các định luật cơ bản của vật lý, phát triển hiểu biết về khoa học vật lý nói chung và kỹ năng lập luận cũng như các chiến lược để chuẩn bị cho việc học tập các lớp khoa học chuyên ngành trong chương trình dành cho kỹ sư. Để đạt mục tiêu này, học phần sẽ chú trọng vào việc kết hợp cung cấp những hiểu biết về các khái niệm với các kỹ năng giải các bài tập dạng chuẩn (làm ở nhà) ở cuối mỗi chương. Bên cạnh đó, học phần sẽ giúp sinh viên hiểu cách xây dựng các mô hình toán học dựa trên các kết quả thực nghiệm, biết cách ghi nhận, trình bày, phân tích số liệu và phát triển một mô hình dựa trên các dữ liệu và có thể sử dụng mô hình này để phán đoán kết quả của các thí nghiệm khác. Đồng thời, sinh viên sẽ biết được giới hạn của mô hình và có thể sử dụng chúng trong việc phán đoán.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 1, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'PHYS130902';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS130902' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS130902' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS130902' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS130902' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS130902' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS130902' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS130902' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS130902' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS130902' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS130902' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS130902' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PHYS130902' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.3';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('PHYS111202', 'Thí nghiệm vật lý 1', 1, 1, NULL, '1(0:1:2)', NULL, 'Thí nghiệm Vật lý 1 gồm một đơn vị học phần có 9 bài thí nghiệm về động học, động lực học chất điểm và động lực học vật rắn. Đây là môn học bổ sung cho sinh viên thuộc khối ngành công nghệ hệ cao đẳng và đại học những kiến thức về bản chất các hiện tượng vật lý xảy ra trong tự nhiên, kiểm tra lại các lý thuyết vật lý đã được học trong chương trình nhằm rèn luyện cho các kỹ sư tương lai kỹ năng quan sát, tiến hành thí nghiệm, đo đạc và tính toán, phân tích, xử lý số liệu.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'PHYS111202';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('PRBE214262', 'Thực tập điện tử căn bản', 1, 1, NULL, '1(0:1:2)', NULL, 'Môn học này hướng dẫn sinh viên thực hành các mạch kỹ thuật điện tử như mạch chỉnh lưu, mạch xén, mạch nguồn DC, mạch khuếch đại tín hiệu nhỏ, mạch transistor ngắt dẫn, mạch dao động, các mạch điều khiển dùng SCR, TRAC, DIAC, quang trở, op-to, các mạch đếm và thanh ghi và các mạch điện tử ứng dụng trong thực tế.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Toán học và Khoa học cơ bản/ Toán học và Hình họa/ Toán học và Khoa học cơ bản/Mỹ thuật/ Khoa học xã hội nhân văn (* Theo khung CTĐT ĐHCQ tiếng Việt 2', 0 FROM courses WHERE course_code = 'PRBE214262';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRBE214262' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.3';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('INDE131777', 'Nhập môn ngành KTDL', 3, 2, 1, '3(2:1:6)', NULL, 'Học phần nhập môn ngành Kỹ thuật dữ liệu được thiết kế để giúp sinh viên năm thứ nhất nhanh chóng làm quen và hòa nhập với môi trường mới tại Trường Đại học Sư phạm Kỹ thuật TPHCM Học phần cũng giới thiệu tổng quát chương trình học và định hướng về nghề nghiệp, giúp sinh viên hiểu rõ nhiệm vụ, vai trò, trách nhiệm của người Kỹ sư ngành Kỹ thuật dữ liệu trong tương lai. Học phần này cũng trang bị cho sinh viên về các kỹ năng mềm cũng như nền tảng đạo đức nghề nghiệp.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 1, 'Nhập môn ngành', 0 FROM courses WHERE course_code = 'INDE131777';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INDE131777' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INDE131777' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INDE131777' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DIGR230485', 'Toán rời rạc và lý thuyết đồ thị', 3, 2, 1, '3(2:1:6)', 'INPR130285', 'Phần “Toán rời rạc” trang bị cho người học những kiến thức cơ bản về logic mệnh đề, logic vị từ, suy diễn logic, quan hệ tương đương, quan hệ thứ tự, dàn và đại số Bool. Cung cấp cho người học kiến thức và kỹ năng trong việc phân tích, nhìn nhận vấn đề, trong việc xác định công thức đa thức tối tiểu bằng phương pháp biểu đồ Karnaugh. Phần “Lý thuyết đồ thị” (LTĐT) trang bị cho người học những kiến thức cơ bản về lý thuyết đồ thị và sự hiểu biết về các lĩnh vực ứng dụng của lý thuyết đồ thị, cung cấp kiến thức nền tảng về lý thuyết đồ thị ứng dụng trong tin học. Cung cấp các thuật toán, kỹ thuật và kỹ năng lập trình các giải thuật trong lý thuyết đồ thị.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'DIGR230485';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DIGR230485' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DIGR230485' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DIGR230485' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DIGR230485' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DIGR230485' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DIGR230485' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DIGR230485' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DIGR230485' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DASA230179', 'Cấu trúc dữ liệu và giải thuật', 3, 2, 1, '3(2:1:6)', 'PRTE230385', 'Học phần này cung cấp cho sinh viên kiến thức về các cấu trúc dữ liệu và giải thuật thông dụng trên máy tính. Giúp sinh viên có khả năng phân tích và xây dựng giải thuật bằng mã giả và hiện thực giải thuật trên máy tính bằng một ngôn ngữ lập trình C/C++. Ngoài ra, học phần này cũng cung cấp khả năng vận dụng cấu trúc dữ liệu và giải thuật đã học để giải quyết bài toán trong thực tế. Bên cạnh đó, sinh viên được làm việc trong các nhóm và thuyết trình các vấn đề nâng cao sử dụng các phương tiện trình chiếu.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'DASA230179';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DASA230179' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DASA230179' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DASA230179' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DASA230179' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('OOPR230279', 'Lập trình hướng đối tượng', 3, 2, 1, '3(2:1:6)', 'INPR130285, PRTE230385', 'Học phần nhằm cung cấp cho người học các kiến thức về công nghệ Visual .NET 2015/2017 của Microsoft, các thành phần chính của .NET framework; các thành phần cơ bản và cú pháp của ngôn ngữ C#; phương pháp luận trong lập trình OOP: lớp, đối tượng, thuộc tính, phương thức, sự thừa kế, tính đa hình, giao diện. Bên cạnh đó, môn học cung trang bị kiến thức và kỹ năng sử dụng cơ chế ủy quyền và việc đáp ứng của nó theo các sự kiện; xây dựng Generic với lớp, giao diện, phương thức; kiến thức cơ bản về LINQ và kỹ năng sử dụng các lớp dựng sẵn trong C# để xây dựng các chương trình WinForm đơn giản.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'OOPR230279';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OOPR230279' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OOPR230279' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OOPR230279' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('MALE431985', 'Học máy', 3, 2, 1, NULL, 'DIGR230485, MATH132901, MATH143001', NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 5, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'MALE431985';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MALE431985' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'MALE431985' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.3';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('INSE330380', 'An toàn thông tin', 3, 2, 1, '3(2:1:6)', 'DBSY230184, INPR130285, NEES330380', 'Học phần này cung cấp cho sinh viên những kiến thức về an toàn thông tin, bao gồm: Cơ bản : tư duy về bảo mật, các khái niệm cơ bản (chính sách CIA,…) An toàn phần mềm : lỗ hổng bảo mật và phần mềm độc hại, phân tích chương trình Mật mã học ứng dụng : mã hóa, xác thực, hàm băm, mã hóa đối xứng và không đối xứng Mạng : mạng có dây và không dây, các giao thức, tấn công và các biện pháp đối phó.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 4, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'INSE330380';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INSE330380' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INSE330380' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'INSE330380' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('WEPR330479', 'Lập trình Web', 3, 2, 1, '3(2:1:6)', 'DASA230179, DBSY230184, OOPR230279, PRTE230385', 'Môn học này cung cấp kiến thức nền tảng về các ứng dụng web được xây dựng bằng công nghệ Servlet và JSP trên nền tảng J2EE framework. Nội dung chủ yếu tập trung vào hai thành phần sau, thứ nhất, thư viện thẻ chuẩn JSTL (JavaServer Pages Standard Tag Library): tập các thẻ JSP với các chức năng chung hỗ trợ cho nhiều ứng dụng JSP, thứ hai, mô hình MVC (Model-View-Controller Pattern). Sau khi học xong môn học này, sinh viên được trang bị các kỹ năng phân tích và thiết kế; có khả năng ứng dụng mô hình MVC để phát triển một ứng dụng web hoàn chỉnh dựa trên công nghệ Servlet và JSP. Ngoài ra, các kỹ năng mềm như làm việc nhóm, trình bày báo cáo cũng được đưa vào môn học này.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 5, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'WEPR330479';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'WEPR330479' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'WEPR330479' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'WEPR330479' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('SOEN330679', 'Công nghệ phần mềm', 3, 3, 1, NULL, 'DASA230179, DBSY230184, INPR130285, OOPR230279, PRTE230385', NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 5, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'SOEN330679';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SOEN330679' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SOEN330679' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '6' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SOEN330679' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('CAAL230180', 'Kiến trúc máy tính và hợp ngữ', 3, 2, 1, '3(2:1:6)', 'EEEN234162', 'Học phần cung cấp cho người học những kiến thức liên quan tới tổ chức logic của máy tính cũng như các thành phần phần cứng cơ bản tạo nên, bao gồm: - Cung cấp kiến thức về các hệ số đếm dùng trong máy tính - Cung cấp kiến thức về các cách biểu diễn dữ liệu trong máy tính - Cung cấp kiến thức về một số kiến trúc mẫu của máy tính cũng như các thành phần chính và nhiệm vụ của chúng. - Cung cấp kiến thức về kiến trúc phần mềm của hệ thống máy tính 8086/8088 - Cung cấp các kiến thức về việc sử dụng tập lệnh 80x86 - Cung cấp kiến thức về lập trình hợp ngữ') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'CAAL230180';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'CAAL230180' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'CAAL230180' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'CAAL230180' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('OPSY330280', 'Hệ điều hành', 3, 2, 1, '3(2:1:6)', 'CAAL230180, PRTE230385', 'Cung cấp kiến thức về các phương pháp giao tiếp và điều khiển thiết bị cơ bản của hệ thống máy tính Cung cấp kiến thức về cấu trúc cơ bản của một Hệ điều hành Cung cấp kiến thức về các nguyên lý cơ bản về việc tạo ra các thành phần và các dịch vụ của Hệ điều hành Giới thiệu một vài thành phần của Hệ điều hành cụ thể là cơ sở để nghiên cứu toàn bộ hệ điều hành') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 4, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'OPSY330280';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OPSY330280' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OPSY330280' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'OPSY330280' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('NEES330380', 'Mạng máy tính căn bản', 3, 2, 1, '3(2:1:6)', NULL, 'Cung các các khái niệm cơ bản trong mạng máy tính, đặc điểm cơ bản của các loại mạng. Cung cấp kiến thức về nguyên lý hoạt động của các thiết bị mạng, các giao thức phổ biến hoạt động trong hệ thống mạng. Cung cấp các kiến thức về thiết kế, cấu hình và vận hành hệ thống mạng đơn giản trên Windows Cung cấp các kiến thức về thiết kế, cấu hình và vận hành hệ thống mạng đơn giản trên Linux.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 3, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'NEES330380';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'NEES330380' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'NEES330380' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'NEES330380' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DBSY230184', 'Cơ sở dữ liệu', 3, 2, 1, '3(2:1:6)', 'DASA230179, PRTE230385', 'Học phần này trang bị cho người học những kiến thức cơ bản về cơ sở dữ liệu và kiến thức chuyên sâu về mô hình dữ liệu quan hệ: quan hệ, phụ thuộc hàm, các ràng buộc trên quan hệ, siêu khóa, khóa chính, khóa dự tuyển, khóa ngoại, bao đóng của tập phụ thuộc hàm, bao đóng của tập thuộc tính, phủ tối tiểu của tập phụ thuộc hàm, thuật toán tìm bao đóng của tập thuộc tính, thuật toán xác định khóa, các dạng chuẩn và tính chất tương ứng. Trang bị cho người học kiến thức về mô hình thực thể kết hợp để thiết kế CSDL.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 4, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'DBSY230184';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBSY230184' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBSY230184' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBSY230184' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DBMS330284', 'Hệ quản trị cơ sở dữ liệu', 3, 2, 1, '3(2:1:6)', 'DBSY230184', 'Học phần này trang bị cho người học về nguyên lý của DBMS. Cách sử dụng ngôn ngữ lập trình PL/SQL, các định nghĩa và ứng dụng của thủ tục nội tại, bẫy lỗi, chỉ mục, lập trình CSDL, các quản lý truy cập trong DBMS, các nguyên lý quản lý giao tác, quản lý truy xuất cạnh tranh, phục hồi sau sự cố.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 5, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'DBMS330284';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBMS330284' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBMS330284' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBMS330284' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ARIN330585', 'Trí tuệ nhân tạo', 3, 2, 1, '3(2:1:6)', 'DASA230179, DIGR130485, PRTE130385', 'Môn học này giới thiệu tới người học các vấn đề, ý tưởng và giải thuật nền tảng trong lĩnh vực trí tuệ nhân tạo (artificial intelligence), bao gồm các giải thuật giải quyết vấn đề bằng tìm kiếm (solving problems by searching), quá trình quyết định Markov (Markov decision processes), học củng cố (reinforcement learning), mạng quyết định (decision networks), phân cụm (clustering), và phân loại sử dụng naïve Bayes. Việc nắm bắt được các ý tưởng và giải thuật này không chỉ giúp người học có khả năng giải quyết các vấn đề thực tế bằng AI, mà còn giúp người học có thể tiếp thu những thành tựu tiên tiến trong lĩnh vực dễ dàng hơn.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 4, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'ARIN330585';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ARIN330585' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ARIN330585' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DIPR430685', 'Xử lý ảnh số', 3, 2, 1, '3(2:1:6)', 'DASA230179, DIGR230485', 'Học phần này cung cấp cho người học những kiến thức và kỹ năng để viết được các chương trình xử lý ảnh số cơ bản. Trên cơ sở này, sinh viên có thể giải quyết được các bài toán như nâng cao chất lượng ảnh, mô tả thông tin đặc trưng của đối tượng trên ảnh và nhận dạng đối tượng trên ảnh.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 5, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'DIPR430685';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DIPR430685' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DIPR430685' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '6' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DIPR430685' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('IPPA233277', 'Lập trình Python', 3, 2, 1, '3(2:1:6)', NULL, 'Python là một trong những ngôn ngữ lập trình đa dụng phổ biến hiện nay. Ngôn ngữ này đang ngày càng trở nên phổ biến hơn trong lĩnh vực kỹ thuật dữ liệu. Học phần này trang bị các kiến thức và kỹ năng cơ bản về lập trình sử dụng ngôn ngữ Python. Các kiến thức bao gồm cú pháp ngôn ngữ, các kiểu dữ liệu và cấu trúc dữ liệu thường sử dụng, các hàm tiện ích thường dùng, khái niệm lập trình hướng đối tượng trên Python. Ngoài ra, học phần còn cung cấp các kiến thức chuyên sâu về việc sử dụng các tiện ích mở rộng của Python trong xử lý dữ liệu, bao gồm phần tích khai phá dữ liệu, tiền xử lý dữ liệu, và xây dựng mô hình dự báo đơn giản.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 4, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'IPPA233277';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'IPPA233277' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'IPPA233277' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'IPPA233277' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('PRTE230385', 'Kỹ thuật lập trình', 3, 2, 1, '3(2:1:6)', 'INPR130285', 'Môn học trang bị cho sinh viên những kiến thức về phân tích, đánh giá độ phức tạp của giải thuật, đồng thời cũng cung cấp các giải thuật và kỹ thuật lập trình để giải quyết bài toán thực tế cũng như nâng cao hiệu quả của các chương trình máy tính.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 2, 'Kiến thức cơ sở nhóm ngành và ngành', 0 FROM courses WHERE course_code = 'PRTE230385';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRTE230385' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRTE230385' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRTE230385' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '2' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRTE230385' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRTE230385' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PRTE230385' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DBSE431284', 'Bảo mật CSDL', 3, 2, 1, '3(2:1:6)', 'DBMS330284, DBSY230184', 'Học phần này trang bị cho người học những kiến thức nền tảng về cả lý thuyết lẫn thực hành để có thể hiểu được những cơ chế, mô hình và kỹ thuật bảo mật cơ sở dữ liệu, cụ thể: các kiểu tấn công, các cấp độ bảo mật và các phương pháp bảo vệ tương ứng; bảo mật cơ sở dữ liệu bằng phương pháp kiểm soát truy cập (Access Control) với các mô hình DAC, MAC, RBAC; bảo mật bằng phương pháp mã hóa dữ liệu; vấn đề kiểm định (Audit); cách thức hiện thực các mô hình và các công nghệ hỗ trợ bảo mật trong các hệ quản trị cơ sở dữ liệu; nguyên lý thiết kế và cài đặt các cơ chế bảo mật; các mô hình bảo vệ tính toàn vẹn dữ liệu') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành', 0 FROM courses WHERE course_code = 'DBSE431284';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBSE431284' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBSE431284' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DBSE431284' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('CLCO332779', 'Điện toán đám mây', 3, 2, 1, '3(2:1:6)', NULL, 'Amazon Web Services, Google App Engine, Microsoft Azure, và các dịch vụ đám mây khác cho phép cá cá nhân và tổ chức có thể sử dụng được sức mạnh của những nguồn tài nguyên tính toán vô hạn theo mô hình pay-as-you-go mà không cần phải đầu tư quá nhiều ngay từ đầu. Trong môn học này, sinh viên sẽ được trang bị kiến thức về các APIs quan trọng của như những dịch vụ được cung cấp bởi Google, Amazon, và Microsoft Cloud, bao gồm các kỹ thuật xây dựng và triển khai các ứng dụng cũng như việc duy trì các máy ảo. Sinh viên sẽ được học: Cách sử dụng các mô hình đám mây như: Cloud as the infrastructure, Cloud as the platform, và Cloud ad the software services; Cách sử dụng các RESTFul Web services; Cách sử dụng cả Web interfaces và chế độ dòng lệnh (CLI) thông qua Linux/Unix terminal để làm việc với các Cloud service.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành', 0 FROM courses WHERE course_code = 'CLCO332779';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'CLCO332779' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'CLCO332779' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '6' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'CLCO332779' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('RPAN233577', 'Lập trình R cho phân tích', 3, 2, 1, '3(2:1:6)', NULL, 'Học phần này trang bị cho người học các kiến thức, kĩ năng, và phương pháp dùng ngôn ngữ lập trình R trong phân tích dữ liệu. Học phần cung cấp kiến thức về các khái niệm cơ bản về các kiểu dữ liệu, các phép toán, cú pháp, và các hàm tiện ích để lập trình trên môi trường R. Về hoạt động phân tích dữ liệu, học phần học phần này trình bày một số ứng dụng của ngôn ngữ R trong lĩnh vực phân tích dữ liệu bao gồm: các hàm phân tích, ứng dụng các mô hình xác suất, thống kê trong R, làm việc với dữ liệu theo chuỗi thời gian, vẽ và sử dụng các đồ thị thường dùng trong thống kê, và kiểm định giả thiết thống kê cho tập dữ liệu.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 4, 'Kiến thức chuyên ngành', 0 FROM courses WHERE course_code = 'RPAN233577';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'RPAN233577' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'RPAN233577' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'RPAN233577' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'RPAN233577' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('IDVI333677', 'Tương tác dữ liệu trực quan', 3, 2, 1, '3(2:1:6)', NULL, 'Việc nhìn thấy hình dạng của dữ liệu dưới các hình thức trực quan thay vì những số liệu là một trong những công cụ rất hữu ích trong việc phân tích và xử lý dữ liệu. Bên cạnh đó, việc trình bày kết quả xử lý phân tích dữ liệu dưới dạng các hình ảnh trực quan giúp người xem có thể rút trích những thông tin quan trọng một cách nhanh chóng và hiệu quả. Học phần này cung cấp các khái niệm cơ bản, tầm quan trọng của trực quan hóa dữ liệu, và tương tác với dữ liệu trực quan. Đồng thời, học phần cung cấp kiến thức một số phương pháp cơ bản giúp cho việc trực quan hóa và tương tác với dữ liệu.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 5, 'Kiến thức chuyên ngành', 0 FROM courses WHERE course_code = 'IDVI333677';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'IDVI333677' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'IDVI333677' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'IDVI333677' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DAMI330484', 'Khai phá dữ liệu', 3, 2, 1, '3(2:1:6)', 'DBMS330284', 'Học phần này trang bị cho người học những kiến thức cơ bản về các khái niệm, thuật toán và ứng dụng của khai phá dữ liệu. Ngoài ra, người học còn có cơ hội trải nghiệm các thư viện, công cụ mã nguồn mở để cài đặt và thử nghiệm thuật toán khai phá dữ liệu. Các chủ đề được đề cập đến trong học phần bao gồm: - Các khái niệm cơ bản và quá trình về khai phá dữ liệu - Các vấn đề liên quan đến quá trình tiền xử lý dữ liệu - Các thuật toán khai phá luật kết hợp: Apriori, FP-Growth, ... - Các thuật toán phân loại: k lân cận gần nhất (k-NN), cây quyết định, Naive Bayes - Các thuật toán gom cụm: gom cụm phân hoạch k-means, gom cụm phân cấp gộp AGNES - Các thuật toán phân tích ngoại biên: dựa trên thống kê, dựa trên xấp xỉ, dựa trên gom cụm, dựa trên phân loại - Các độ đo và phương pháp đánh giá các thuật toán khai phá dữ liệu') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành', 0 FROM courses WHERE course_code = 'DAMI330484';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAMI330484' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAMI330484' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAMI330484' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAMI330484' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAMI330484' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.3';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('BDES333877', 'Nhập môn dữ liệu lớn (Big Data Essentials)', 3, 2, 1, '3(2:1:6)', NULL, 'Môn học này thuộc nhóm môn học cơ sở ngành, nhằm cung cấp cho người học các kiến thức tổng quan về cơ sở dữ liệu lớn, những ứng dụng của cơ sở dữ liệu lớn. Ngoài ra, người học còn được cung cấp những kiến thức về các kỹ thuật cơ bản trong lưu trữ và xử lý, phân tích cơ sở dữ liệu lớn. Về mặt kỹ năng, người học được trang bị khả năng sử dụng một số công cụ phân tích cơ sở dữ liệu lớn thông dụng. Bên cạnh đó, người học cũng được trang bị một số kỹ năng mềm bao gồm: kỹ năng tìm kiếm, chọn lọc và tổng hợp tài liệu, kỹ năng viết và trình bày báo cáo, kỹ năng làm việc nhóm.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 5, 'Kiến thức chuyên ngành', 0 FROM courses WHERE course_code = 'BDES333877';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'BDES333877' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'BDES333877' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'BDES333877' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('BDAN333977', 'Phân tích dữ liệu lớn (Big Data Analysis)', 3, 2, 1, '3(2:1:6)', 'BDES333877, DBMS330284', 'Môn học cung cấp cho sinh viên kiến thức về kiến trúc của các hệ thống và các công cụ phục vụ cho hoạt động phân tích dữ liệu lớn. Với mỗi công cụ, môn học giới thiệu các kiến thức cơ bản và nâng cao cũng như phương thức tối ưu hóa hiệu suất hệ thống sử dụng công cụ này. Cùng với các bài tập lập trình, môn học hướng đến mục tiêu giúp người học có thể hình thành ý tưởng, thiết kế và hiện thực hóa hoạt động phân tích dữ liệu trong các hệ thống dữ liệu lớn.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành', 0 FROM courses WHERE course_code = 'BDAN333977';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'BDAN333977' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'BDAN333977' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'BDAN333977' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DLEA432085', 'Học sâu (Deep Learning)', 3, 2, 1, NULL, 'MALE431985', NULL) ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành', 0 FROM courses WHERE course_code = 'DLEA432085';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DLEA432085' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DLEA432085' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DLEA432085' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DLEA432085' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DAWH430784', 'Kho dữ liệu', 3, 2, 1, '3(2:1:6)', 'DBMS330284', 'Môn học cung cấp cho sinh viên những kiến thức cơ bản về kho dữ liệu. Trong khóa học này, người học sẽ học các khái niệm cơ bản về kho dữ liệu, kiến trúc kho dữ liệu và các mô hình đa chiều. Họ sẽ được thực hành về thiết kế kho dữ liệu và sử dụng các công cụ phổ biến để quản lý các bảng tổng hợp (pivot table) và tạo các luồng công việc tích hợp dữ liệu (data integration workflows). Bên cạnh đó, những người học cũng sẽ học cách sử dụng các phần mở rộng của SQL được hỗ trợ bởi các hệ quản trị cơ sở dữ liệu quan hệ để trả lời các câu hỏi phân tích trong kinh doanh.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành', 0 FROM courses WHERE course_code = 'DAWH430784';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAWH430784' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAWH430784' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAWH430784' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAWH430784' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAWH430784' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('BDAS436177', 'Ứng dụng dữ liệu lớn: Truyền dữ liệu theo thời gian thực (Big Data Applications: Real-Time Streaming)', 3, 2, 1, '3(2:1:6)', 'BDES333877, DBMS330284', 'Học phần này cung cấp cho sinh viên các kiến thức không những về các ứng dụng trong lĩnh vực Big Data đặc biệt là real-time streaming mà còn am hiểu về Spark và các kỹ thuật liên quan như NoSQL, Kafka và Flume.Ngoài ra, sinh viên được trang bị kỹ năng sử dụng các công cụ để tạo ra các ứng dụng về Real-Time Streaming. Sau khi học xong học phần này, sinh viên có khả năng phân tích, thiết kế và xây dựng các ứng dụng Big Data để xử lý các luồng dữ liệu trong thời gian thực.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Kiến thức chuyên ngành', 0 FROM courses WHERE course_code = 'BDAS436177';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'BDAS436177' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '5' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'BDAS436177' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '6' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'BDAS436177' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DAAN436277', 'Phân tích dữ liệu (Data analytics)', 3, 2, 1, '3(2:1:6)', 'DBMS330284', 'Học phần cung cấp cho sinh viên kiến thức về kiến trúc của các hệ thống và các công cụ phục vụ cho hoạt động phân tích dữ liệu lớn. Với mỗi công cụ, môn học giới thiệu các kiến thức cơ bản và nâng cao cũng như phương thức tối ưu hóa hiệu suất hệ thống sử dụng công cụ này. Cùng với các bài tập lập trình, môn học hướng đến mục tiêu giúp người học có thể hình thành ý tưởng, thiết kế và hiện thực hóa hoạt động phân tích dữ liệu trong các hệ thống dữ liệu lớn.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 6, 'Kiến thức chuyên ngành', 0 FROM courses WHERE course_code = 'DAAN436277';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAAN436277' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAAN436277' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAAN436277' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'DAAN436277' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('PODE454277', 'Tiểu luận chuyên ngành KTDL', 5, 4, 1, '5(5:0:10)', NULL, 'Học phần này sinh viên sẽ được làm một dự án về chuyên ngành KTDL với sự hướng dẫn của GVHD trong suốt một học kỳ. Các chủ đề sẽ bao phủ một số học phần đã được học, liên quan đến các vấn đề dữ liệu lớn.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 7, 'Kiến thức chuyên ngành', 0 FROM courses WHERE course_code = 'PODE454277';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PODE454277' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PODE454277' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PODE454277' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PODE454277' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PODE454277' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '5' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PODE454277' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '5' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'PODE454277' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('ITIN421085', 'Thực tập Tốt Nghiệp', 2, NULL, NULL, '2(2:0:4)', NULL, 'Môn học này trang bị cho sinh viên các kiến thức thực tế liên quan tới môi trường làm việc tại doanh nghiệp, sử dụng kiến thức đã học trong việc tham gia các dự án thực tế tại doanh nghiệp, hoặc tiếp thu một số công nghệ mới và vận dụng chúng trong việc triển khai, vận hành hệ thống công nghệ thông tin. Đồng thời qua việc thực tập sinh viên có thể phát triển tư duy trong tương lai với vai trò quản lý.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 7, 'Thực tập tốt nghiệp', 0 FROM courses WHERE course_code = 'ITIN421085';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ITIN421085' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ITIN421085' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ITIN421085' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'ITIN421085' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('GRPR474377', 'Khóa luận tốt nghiệp', 7, NULL, NULL, '7', NULL, 'Học phần này sinh viên sẽ được làm một dự án về chuyên ngành KTDL với sự hướng dẫn của GVHD trong suốt một học kỳ. Các chủ đề sẽ bao phủ hầu hết các học phần đã được học liên quan đến các vấn đề về dữ liệu.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 8, 'Khóa luận tốt nghiệp', 0 FROM courses WHERE course_code = 'GRPR474377';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR474377' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR474377' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR474377' WHERE pl.program_id = @p AND pi.pi_code = 'PI3.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR474377' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '5' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR474377' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '5' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR474377' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '6' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR474377' WHERE pl.program_id = @p AND pi.pi_code = 'PI6.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '6' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR474377' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '6' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'GRPR474377' WHERE pl.program_id = @p AND pi.pi_code = 'PI7.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('SEMI310026', 'Chuyên đề Doanh nghiệp', 1, NULL, NULL, '1(1:0:2)', NULL, 'Môn học này trang bị cho sinh viên các kiến thức cập nhật thực tế về các công nghệ mới trong lĩnh vực công nghệ thông tin, cũng như một số kiến thức về kỹ năng mềm, kỹ năng làm việc trong môi trường doanh nghiệp, dưới hình thức chuyên đề khách mời – là những chuyên gia có kinh nghiệm làm việc trong các doanh nghiệp.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, 7, 'Chuyên đề bổ trợ', 0 FROM courses WHERE course_code = 'SEMI310026';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SEMI310026' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SEMI310026' WHERE pl.program_id = @p AND pi.pi_code = 'PI1.2';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SEMI310026' WHERE pl.program_id = @p AND pi.pi_code = 'PI2.1';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '3' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SEMI310026' WHERE pl.program_id = @p AND pi.pi_code = 'PI4.3';
INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, '4' FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = 'SEMI310026' WHERE pl.program_id = @p AND pi.pi_code = 'PI5.2';
INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES ('DICO132585', 'Chuyên đề nâng cao năng lực số', 3, NULL, NULL, '3(3:0:6)', NULL, 'Học phần Nâng cao năng lực số trang bị cho người học hệ thống kiến thức, kỹ năng và thái độ cần thiết để học tập, làm việc và tham gia hiệu quả trong môi trường số. Nội dung học phần được xây dựng theo định hướng Khung năng lực số của Bộ Giáo dục và Đào tạo, bao gồm các lĩnh vực: khai thác dữ liệu và thông tin; giao tiếp và hợp tác trong môi trường số; sáng tạo nội dung số; bảo đảm an toàn, an ninh số; giải quyết vấn đề trong môi trường số; và ứng dụng trí tuệ nhân tạo (Al) một cách hiệu quả, có trách nhiệm và tuân thủ các quy định của pháp luật. Sau khi hoàn thành học phần, người học có khả năng vận dụng năng lực số để học tập suốt đời, thích ứng với quá trình chuyển đổi số, đáp ứng yêu cầu của thị trường lao động và trở thành công dân số có trách nhiệm, sáng tạo, an toàn và có đạo đức trong môi trường số.') ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));
INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) SELECT @p, id, NULL, 'Chuyên đề bổ trợ', 0 FROM courses WHERE course_code = 'DICO132585';

