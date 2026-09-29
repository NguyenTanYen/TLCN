-- =============================================================
-- Chạy trong HeidiSQL SAU KHI đã có CSDL Moodle moodle_db (tiền tố mdl_)
-- Cài 5 view + thủ tục sp_sync_exam đọc dữ liệu Moodle (chỉ đọc).
-- Nếu CSDL Moodle có tên khác, thay 'moodle_db.' bằng tên đó.
-- =============================================================
-- =====================================================================
--  CẦU NỐI CSDL HỆ THỐNG  <->  CSDL MOODLE 4.x (chỉ ĐỌC)
--  Hiện thực bước "lấy dữ liệu – Reverse Shuffle – ghi kết quả từng câu" của UC-03.
--  Phần phân tích (p, DI, CLO, lộ trình) do Analysis Engine (Pandas) đảm nhận.
--
--  Quy ước (backend tự thay "moodle_db.mdl_" theo cấu hình MOODLE_DB_NAME / MOODLE_PREFIX):
--    * Câu hỏi xuất XML có <idnumber>QB-{question_bank.id}</idnumber>
--    * Các <answer> xuất theo question_options.position tăng dần
--      => đáp án có id nhỏ thứ k trong mdl_question_answers ứng với position = k
--    * SV khớp theo mdl_user.idnumber (nếu có) hoặc mdl_user.username = student_code
--    * Mỗi SV lấy ĐÚNG lượt bài mà Moodle dùng để tính điểm, theo mdl_quiz.grademethod
--      (1 = điểm cao nhất – mặc định, 3 = lượt đầu, 4 = lượt cuối; 2 = trung bình -> lấy lượt cuối để phân tích câu hỏi),
--      chỉ xét lượt state = finished, preview = 0 (bỏ lượt xem thử của GV) – giống quiz_report_grade_method_sql() của Moodle
-- =====================================================================
USE assessment_db;

-- 1) Câu hỏi Moodle (mọi phiên bản) -> question_bank.id
CREATE OR REPLACE VIEW v_mdl_question_map AS
SELECT qv.questionid AS mdl_question_id, qv.version AS mdl_version,
       CAST(SUBSTRING(qbe.idnumber, 4) AS UNSIGNED) AS question_id
FROM moodle_db.mdl_question_versions     qv
JOIN moodle_db.mdl_question_bank_entries qbe ON qbe.id = qv.questionbankentryid
WHERE qbe.idnumber REGEXP '^QB-[0-9]+$';

-- 2) Lượt bài được tính điểm của mỗi SV (theo cách tính điểm của quiz) cho các đề online đã gắn quiz
CREATE OR REPLACE VIEW v_mdl_attempts AS
SELECT e.id AS exam_id, t.id AS moodle_attempt_id, t.userid AS mdl_user_id, t.uniqueid AS usage_id,
       FROM_UNIXTIME(t.timestart) AS started_at,
       FROM_UNIXTIME(NULLIF(t.timefinish, 0)) AS finished_at, t.grademethod
FROM exams e
JOIN (
  SELECT qa.*, qz.grademethod,
         ROW_NUMBER() OVER (PARTITION BY qa.quiz, qa.userid ORDER BY
           CASE WHEN qz.grademethod = 1 THEN COALESCE(qa.sumgrades, 0) END DESC,   -- điểm cao nhất (hòa: lượt sớm hơn)
           CASE WHEN qz.grademethod IN (1, 3) THEN qa.attempt END ASC,            -- lượt đầu
           qa.attempt DESC) AS rn                                                   -- lượt cuối / trung bình
  FROM moodle_db.mdl_quiz_attempts qa
  JOIN moodle_db.mdl_quiz qz ON qz.id = qa.quiz
  WHERE qa.preview = 0 AND qa.state = 'finished'
) t ON t.quiz = e.moodle_quiz_id AND t.rn = 1
WHERE e.exam_type = 'online';

-- 3) Câu trả lời thô: _order (bước 0) + answer (bước cuối có answer; -1 = xóa lựa chọn)
CREATE OR REPLACE VIEW v_mdl_responses AS
SELECT a.exam_id, a.moodle_attempt_id, a.mdl_user_id,
       qat.slot, qat.questionid AS mdl_question_id,
       ord.value AS shuffled_order, CAST(ans.value AS SIGNED) AS answer_index
FROM v_mdl_attempts a
JOIN moodle_db.mdl_question_attempts qat ON qat.questionusageid = a.usage_id
LEFT JOIN (
  SELECT s.questionattemptid, d.value
  FROM moodle_db.mdl_question_attempt_steps s
  JOIN moodle_db.mdl_question_attempt_step_data d ON d.attemptstepid = s.id AND d.name = '_order'
  WHERE s.sequencenumber = 0
) ord ON ord.questionattemptid = qat.id
LEFT JOIN (
  SELECT questionattemptid, value FROM (
    SELECT s.questionattemptid, d.value,
           ROW_NUMBER() OVER (PARTITION BY s.questionattemptid ORDER BY s.sequencenumber DESC) AS rn
    FROM moodle_db.mdl_question_attempt_steps s
    JOIN moodle_db.mdl_question_attempt_step_data d ON d.attemptstepid = s.id AND d.name = 'answer'
  ) x WHERE rn = 1
) ans ON ans.questionattemptid = qat.id;

-- 4) REVERSE SHUFFLE: chỉ số hiển thị -> id đáp án Moodle -> vị trí gốc -> question_options.id
CREATE OR REPLACE VIEW v_mdl_item_results AS
SELECT r1.exam_id, r1.moodle_attempt_id, r1.mdl_user_id, r1.question_id,
       r1.selected_mdl_answer_id, o.id AS selected_option_id,
       CASE WHEN o.id IS NULL THEN 'blank' ELSE 'answered' END AS response_status,
       COALESCE(o.is_correct, FALSE) AS is_correct
FROM (
  -- (b) id đáp án Moodle -> vị trí gốc = số đáp án có id nhỏ hơn + 1 (NULL nếu bỏ trống)
  SELECT r2.*,
         CASE WHEN r2.selected_mdl_answer_id IS NULL THEN NULL ELSE
           (SELECT COUNT(*) + 1 FROM moodle_db.mdl_question_answers qa2
             WHERE qa2.question = r2.mdl_question_id AND qa2.id < r2.selected_mdl_answer_id)
         END AS orig_position
  FROM (
    -- (a) chỉ số hiển thị -> id đáp án Moodle (phần tử thứ answer_index+1 của _order)
    --     viết bằng bảng dẫn xuất lồng nhau thay cho LATERAL để chạy được trên MariaDB 10.4
    SELECT r.*, m.question_id,
           CASE WHEN r.answer_index IS NULL OR r.answer_index < 0 OR r.shuffled_order IS NULL THEN NULL
                ELSE CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(r.shuffled_order, ',', r.answer_index + 1), ',', -1) AS UNSIGNED)
           END AS selected_mdl_answer_id
    FROM v_mdl_responses r
    LEFT JOIN v_mdl_question_map m ON m.mdl_question_id = r.mdl_question_id
  ) r2
) r1
LEFT JOIN question_options o ON o.question_id = r1.question_id AND o.position = r1.orig_position;

-- 5) Danh sách lớp trên Moodle (vai trò student) của khóa học chứa quiz
CREATE OR REPLACE VIEW v_mdl_exam_roster AS
SELECT e.id AS exam_id, u.id AS mdl_user_id,
       COALESCE(NULLIF(TRIM(u.idnumber), ''), u.username) AS student_code,
       TRIM(CONCAT(u.lastname, ' ', u.firstname))         AS full_name
FROM exams e
JOIN moodle_db.mdl_quiz  qz ON qz.id = e.moodle_quiz_id
JOIN moodle_db.mdl_enrol en ON en.courseid = qz.course AND en.status = 0
JOIN moodle_db.mdl_user_enrolments ue ON ue.enrolid = en.id AND ue.status = 0
JOIN moodle_db.mdl_user  u  ON u.id = ue.userid AND u.deleted = 0
JOIN moodle_db.mdl_context ctx ON ctx.contextlevel = 50 AND ctx.instanceid = qz.course
JOIN moodle_db.mdl_role_assignments ra ON ra.contextid = ctx.id AND ra.userid = u.id
JOIN moodle_db.mdl_role  ro ON ro.id = ra.roleid AND ro.shortname = 'student'
UNION
SELECT a.exam_id, u.id, COALESCE(NULLIF(TRIM(u.idnumber), ''), u.username),
       TRIM(CONCAT(u.lastname, ' ', u.firstname))
FROM v_mdl_attempts a JOIN moodle_db.mdl_user u ON u.id = a.mdl_user_id;

-- =====================================================================
-- 6) THỦ TỤC ĐỒNG BỘ MỘT BÀI KT ONLINE: CALL sp_sync_exam(exam_id)
--    Một transaction, chạy lại an toàn; lỗi -> ROLLBACK + ghi sync_runs.
-- =====================================================================
DROP PROCEDURE IF EXISTS sp_sync_exam;
DELIMITER $$
CREATE PROCEDURE sp_sync_exam(IN p_exam_id INT)
BEGIN
  DECLARE v_quiz BIGINT; DECLARE v_course BIGINT; DECLARE v_cs INT; DECLARE v_type VARCHAR(10);
  DECLARE v_run BIGINT; DECLARE v_bad INT; DECLARE v_msg TEXT;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_msg = MESSAGE_TEXT;
    ROLLBACK;
    UPDATE sync_runs SET status = 'failed', finished_at = NOW(), message = v_msg WHERE id = v_run;
    RESIGNAL;
  END;

  INSERT INTO sync_runs (exam_id, kind) VALUES (p_exam_id, 'moodle');
  SET v_run = LAST_INSERT_ID();

  SELECT moodle_quiz_id, class_section_id, exam_type INTO v_quiz, v_cs, v_type FROM exams WHERE id = p_exam_id;
  IF v_type <> 'online' OR v_quiz IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Bài KT không phải online hoặc chưa gắn moodle_quiz_id';
  END IF;
  SELECT course INTO v_course FROM moodle_db.mdl_quiz WHERE id = v_quiz;
  IF v_course IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Lỗi kết nối LMS: không tìm thấy quiz trên Moodle';
  END IF;

  START TRANSACTION;

  -- a. Ghi nhận khóa học Moodle của lớp HP
  UPDATE class_sections SET moodle_course_id = v_course WHERE id = v_cs AND moodle_course_id IS NULL;

  -- b. Liên kết câu hỏi và đáp án với Moodle (phiên bản mới nhất)
  UPDATE question_bank q
  JOIN exam_questions eq ON eq.question_id = q.id AND eq.exam_id = p_exam_id
  JOIN (SELECT question_id, mdl_question_id,
               ROW_NUMBER() OVER (PARTITION BY question_id ORDER BY mdl_version DESC) rn
          FROM v_mdl_question_map) m ON m.question_id = q.id AND m.rn = 1
  SET q.moodle_question_id = m.mdl_question_id;

  UPDATE question_options o
  JOIN exam_questions eq ON eq.question_id = o.question_id AND eq.exam_id = p_exam_id
  JOIN question_bank q ON q.id = o.question_id
  JOIN (SELECT qa.id, qa.question,
               ROW_NUMBER() OVER (PARTITION BY qa.question ORDER BY qa.id) AS pos
          FROM moodle_db.mdl_question_answers qa) ma
    ON ma.question = q.moodle_question_id AND ma.pos = o.position
  SET o.moodle_answer_id = ma.id;

  -- c. Mọi câu trả lời trên Moodle phải thuộc đề này
  SELECT COUNT(*) INTO v_bad
  FROM v_mdl_responses r
  LEFT JOIN v_mdl_question_map m ON m.mdl_question_id = r.mdl_question_id
  LEFT JOIN exam_questions eq ON eq.exam_id = p_exam_id AND eq.question_id = m.question_id
  WHERE r.exam_id = p_exam_id AND eq.question_id IS NULL;
  IF v_bad > 0 THEN
    SET v_msg = CONCAT(v_bad, ' câu trả lời trên Moodle không ánh xạ được về đề thi (kiểm tra idnumber QB-n)');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;

  -- d. Sinh viên + danh sách lớp HP từ Moodle
  INSERT INTO students (student_code, full_name, moodle_user_id)
  SELECT student_code, full_name, mdl_user_id FROM v_mdl_exam_roster WHERE exam_id = p_exam_id
  ON DUPLICATE KEY UPDATE moodle_user_id = VALUES(moodle_user_id);

  INSERT IGNORE INTO enrollments (class_section_id, student_id)
  SELECT v_cs, s.id FROM v_mdl_exam_roster ro JOIN students s ON s.moodle_user_id = ro.mdl_user_id
  WHERE ro.exam_id = p_exam_id;

  -- e. Lượt nộp cuối (không ghi đè bài giấy)
  INSERT INTO exam_attempts (exam_id, student_id, moodle_attempt_id, source, started_at, finished_at, status)
  SELECT a.exam_id, s.id, a.moodle_attempt_id, 'moodle', a.started_at, a.finished_at, 'finished'
  FROM v_mdl_attempts a JOIN students s ON s.moodle_user_id = a.mdl_user_id
  WHERE a.exam_id = p_exam_id
  ON DUPLICATE KEY UPDATE
     exam_attempts.moodle_attempt_id = IF(exam_attempts.source = 'paper', exam_attempts.moodle_attempt_id, VALUES(moodle_attempt_id)),
     exam_attempts.started_at        = IF(exam_attempts.source = 'paper', exam_attempts.started_at,        VALUES(started_at)),
     exam_attempts.finished_at       = IF(exam_attempts.source = 'paper', exam_attempts.finished_at,       VALUES(finished_at)),
     exam_attempts.status            = IF(exam_attempts.source = 'paper', exam_attempts.status,            'finished');

  -- f. Vắng thi: có trong danh sách lớp HP (active) nhưng không có lượt nộp
  INSERT INTO exam_attempts (exam_id, student_id, source, status, total_score)
  SELECT p_exam_id, en.student_id, 'moodle', 'absent', 0
  FROM enrollments en
  JOIN students s ON s.id = en.student_id
  WHERE en.class_section_id = v_cs AND en.status = 'active'
    AND NOT EXISTS (SELECT 1 FROM v_mdl_attempts a WHERE a.exam_id = p_exam_id AND a.mdl_user_id = s.moodle_user_id)
  ON DUPLICATE KEY UPDATE
     exam_attempts.moodle_attempt_id = IF(exam_attempts.source = 'paper', exam_attempts.moodle_attempt_id, NULL),
     exam_attempts.started_at        = IF(exam_attempts.source = 'paper', exam_attempts.started_at, NULL),
     exam_attempts.finished_at       = IF(exam_attempts.source = 'paper', exam_attempts.finished_at, NULL),
     exam_attempts.status            = IF(exam_attempts.source = 'paper', exam_attempts.status, 'absent');

  -- g. Làm mới kết quả từng câu
  DELETE r FROM item_level_results r JOIN exam_attempts a ON a.id = r.attempt_id
  WHERE a.exam_id = p_exam_id AND a.source = 'moodle';

  INSERT INTO item_level_results (attempt_id, question_id, selected_option_id, response_status, is_correct, score_earned)
  SELECT a.id, v.question_id, v.selected_option_id, v.response_status, v.is_correct, IF(v.is_correct, eq.points, 0)
  FROM v_mdl_item_results v
  JOIN exam_attempts  a  ON a.moodle_attempt_id = v.moodle_attempt_id AND a.source = 'moodle'
  JOIN exam_questions eq ON eq.exam_id = p_exam_id AND eq.question_id = v.question_id
  WHERE v.exam_id = p_exam_id;

  INSERT INTO item_level_results (attempt_id, question_id, response_status)
  SELECT a.id, eq.question_id, 'absent'
  FROM exam_attempts a JOIN exam_questions eq ON eq.exam_id = a.exam_id
  WHERE a.exam_id = p_exam_id AND a.source = 'moodle' AND a.status = 'absent';

  -- h. Tổng điểm & trạng thái
  UPDATE exam_attempts a
  LEFT JOIN (SELECT attempt_id, SUM(score_earned) sc FROM item_level_results GROUP BY attempt_id) t ON t.attempt_id = a.id
  SET a.total_score = COALESCE(t.sc, 0)
  WHERE a.exam_id = p_exam_id AND a.source = 'moodle';

  UPDATE exams SET status = IF(status = 'Analyzed', status, 'Synced'), last_synced_at = NOW() WHERE id = p_exam_id;
  COMMIT;

  UPDATE sync_runs SET status = 'success', finished_at = NOW(),
         n_attempts = (SELECT COUNT(*) FROM exam_attempts WHERE exam_id = p_exam_id AND status = 'finished'),
         n_absent   = (SELECT COUNT(*) FROM exam_attempts WHERE exam_id = p_exam_id AND status = 'absent')
  WHERE id = v_run;
END$$
DELIMITER ;
