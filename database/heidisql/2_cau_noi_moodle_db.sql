-- =============================================================
-- Chạy trong HeidiSQL SAU KHI đã có CSDL Moodle moodle_db (tiền tố mdl_)
-- và đã cài plugin Offline Quiz (3_CAI_GIAO_DIEN_MOODLE.bat) để đọc bài thi giấy.
-- Cài 6 view + thủ tục sp_sync_exam đọc dữ liệu Moodle (chỉ đọc).
-- Nếu CSDL Moodle có tên khác, thay 'moodle_db.' bằng tên đó.
-- (Hệ thống tự cài lại phần này mỗi lần khởi động – kể cả khi Moodle chưa có Offline Quiz.)
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
--    * Bài thi GIẤY: Moodle (plugin Offline Quiz – mod_offlinequiz) sinh đề/phiếu, nhận diện phiếu quét và chấm;
--      kết quả nằm ở mdl_offlinequiz_results (usageid -> question engine, cùng cấu trúc _order/answer như Quiz).
--      Khối giữa "-- >>> offlinequiz" và "-- <<< offlinequiz" chỉ được cài khi Moodle đã có plugin này.
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

-- 1b) Khóa học Moodle chứa hoạt động của từng bài KT (Quiz cho bài online, Offline Quiz cho bài giấy)
CREATE OR REPLACE VIEW v_mdl_exam_course AS
SELECT e.id AS exam_id, qz.course AS course_id
FROM exams e JOIN moodle_db.mdl_quiz qz ON qz.id = e.moodle_quiz_id
WHERE e.exam_type = 'online'
-- >>> offlinequiz
UNION ALL
SELECT e.id, oq.course
FROM exams e JOIN moodle_db.mdl_offlinequiz oq ON oq.id = e.moodle_offlinequiz_id
WHERE e.exam_type = 'paper'
-- <<< offlinequiz
;

-- 2) Lượt bài được tính điểm của mỗi SV (theo cách tính điểm của quiz) cho các đề online đã gắn quiz
CREATE OR REPLACE VIEW v_mdl_attempts AS
SELECT e.id AS exam_id, t.id AS moodle_attempt_id, t.userid AS mdl_user_id, t.uniqueid AS usage_id,
       FROM_UNIXTIME(t.timestart) AS started_at,
       FROM_UNIXTIME(NULLIF(t.timefinish, 0)) AS finished_at, t.grademethod,
       CAST(NULL AS CHAR(2) CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci AS group_code
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
WHERE e.exam_type = 'online'
-- >>> offlinequiz
UNION ALL
-- Bài giấy: phiếu đã được Offline Quiz nhận diện và chấm xong (status = complete); SV quét lại nhiều lần -> lấy lần cuối.
-- group_code = mã đề (nhóm A, B, C… của Offline Quiz).
SELECT e.id, t.id, t.userid, t.usageid,
       FROM_UNIXTIME(NULLIF(t.timestart, 0)), FROM_UNIXTIME(NULLIF(t.timefinish, 0)), NULL, t.group_code
FROM exams e
JOIN (
  SELECT r.id, r.offlinequizid, r.userid, r.usageid, r.timestart, r.timefinish,
         CHAR(64 + g.groupnumber USING utf8mb4) COLLATE utf8mb4_unicode_ci AS group_code,
         ROW_NUMBER() OVER (PARTITION BY r.offlinequizid, r.userid ORDER BY r.timemodified DESC, r.id DESC) AS rn
  FROM moodle_db.mdl_offlinequiz_results r
  JOIN moodle_db.mdl_offlinequiz_groups g ON g.id = r.offlinegroupid
  WHERE r.status = 'complete' AND COALESCE(r.preview, 0) = 0
) t ON t.offlinequizid = e.moodle_offlinequiz_id AND t.rn = 1
WHERE e.exam_type = 'paper'
-- <<< offlinequiz
;

-- 3) Câu trả lời thô: _order (bước 0) + answer (bước cuối có answer; -1 = xóa lựa chọn)
--    Viết bằng truy vấn con tương quan theo questionattemptid để dùng chỉ mục của Moodle
--    (chỉ đọc các bước của những câu thuộc bài đang đồng bộ, không quét toàn bộ bảng step_data).
CREATE OR REPLACE VIEW v_mdl_responses AS
SELECT a.exam_id, a.moodle_attempt_id, a.mdl_user_id,
       qat.slot, qat.questionid AS mdl_question_id,
       (SELECT d.value
          FROM moodle_db.mdl_question_attempt_steps s
          JOIN moodle_db.mdl_question_attempt_step_data d ON d.attemptstepid = s.id AND d.name = '_order'
         WHERE s.questionattemptid = qat.id AND s.sequencenumber = 0
         LIMIT 1) AS shuffled_order,
       (SELECT CAST(d.value AS SIGNED)
          FROM moodle_db.mdl_question_attempt_steps s
          JOIN moodle_db.mdl_question_attempt_step_data d ON d.attemptstepid = s.id AND d.name = 'answer'
         WHERE s.questionattemptid = qat.id
         ORDER BY s.sequencenumber DESC
         LIMIT 1) AS answer_index
FROM v_mdl_attempts a
JOIN moodle_db.mdl_question_attempts qat ON qat.questionusageid = a.usage_id
-- bỏ khối "Mô tả" (description) – không phải câu hỏi, không có câu trả lời
JOIN moodle_db.mdl_question mq ON mq.id = qat.questionid AND mq.qtype <> 'description';

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

-- 5) Danh sách lớp trên Moodle (vai trò student) của khóa học chứa Quiz / Offline Quiz
CREATE OR REPLACE VIEW v_mdl_exam_roster AS
SELECT ec.exam_id, u.id AS mdl_user_id,
       COALESCE(NULLIF(TRIM(u.idnumber), ''), u.username) AS student_code,
       TRIM(CONCAT(u.lastname, ' ', u.firstname))         AS full_name
FROM v_mdl_exam_course ec
JOIN moodle_db.mdl_enrol en ON en.courseid = ec.course_id AND en.status = 0
JOIN moodle_db.mdl_user_enrolments ue ON ue.enrolid = en.id AND ue.status = 0
JOIN moodle_db.mdl_user  u  ON u.id = ue.userid AND u.deleted = 0
JOIN moodle_db.mdl_context ctx ON ctx.contextlevel = 50 AND ctx.instanceid = ec.course_id
JOIN moodle_db.mdl_role_assignments ra ON ra.contextid = ctx.id AND ra.userid = u.id
JOIN moodle_db.mdl_role  ro ON ro.id = ra.roleid AND ro.shortname = 'student'
UNION
SELECT a.exam_id, u.id, COALESCE(NULLIF(TRIM(u.idnumber), ''), u.username),
       TRIM(CONCAT(u.lastname, ' ', u.firstname))
FROM v_mdl_attempts a JOIN moodle_db.mdl_user u ON u.id = a.mdl_user_id;

-- =====================================================================
-- 6) THỦ TỤC ĐỒNG BỘ MỘT BÀI KT: CALL sp_sync_exam(exam_id)
--    Bài online: đọc lượt làm Quiz. Bài giấy: đọc phiếu Offline Quiz đã chấm. Moodle là nơi chấm điểm duy nhất.
--    Một transaction, chạy lại an toàn; lỗi -> ROLLBACK + ghi sync_runs.
-- =====================================================================
DROP PROCEDURE IF EXISTS sp_sync_exam;
DELIMITER $$
CREATE PROCEDURE sp_sync_exam(IN p_exam_id INT)
BEGIN
  DECLARE v_quiz BIGINT; DECLARE v_oq BIGINT; DECLARE v_course BIGINT; DECLARE v_cs INT; DECLARE v_type VARCHAR(10);
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

  SELECT moodle_quiz_id, moodle_offlinequiz_id, class_section_id, exam_type INTO v_quiz, v_oq, v_cs, v_type
  FROM exams WHERE id = p_exam_id;
  IF (v_type = 'online' AND v_quiz IS NULL) OR (v_type = 'paper' AND v_oq IS NULL) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Bài KT chưa gắn hoạt động trên Moodle (Quiz cho bài online, Offline Quiz cho bài giấy)';
  END IF;
  SELECT course_id INTO v_course FROM v_mdl_exam_course WHERE exam_id = p_exam_id LIMIT 1;
  IF v_course IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Lỗi kết nối LMS: không tìm thấy Quiz / Offline Quiz trên Moodle';
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

  -- c2. Câu hỏi trên Moodle phải giữ nguyên cấu trúc của đề gốc (cùng số phương án, đáp án đúng cùng vị trí);
  --     nếu GV đã sửa câu trên Moodle thì dừng lại thay vì giải xáo trộn sai.
  SELECT COUNT(*) INTO v_bad
  FROM (SELECT DISTINCT r.mdl_question_id, m.question_id
          FROM v_mdl_responses r JOIN v_mdl_question_map m ON m.mdl_question_id = r.mdl_question_id
         WHERE r.exam_id = p_exam_id) u
  WHERE (SELECT COUNT(*) FROM moodle_db.mdl_question_answers a WHERE a.question = u.mdl_question_id)
        <> (SELECT COUNT(*) FROM question_options o WHERE o.question_id = u.question_id)
     OR (SELECT COUNT(*) + 1 FROM moodle_db.mdl_question_answers a2
          WHERE a2.question = u.mdl_question_id
            AND a2.id < (SELECT MIN(a.id) FROM moodle_db.mdl_question_answers a WHERE a.question = u.mdl_question_id AND a.fraction > 0.999))
        <> (SELECT MIN(o.position) FROM question_options o WHERE o.question_id = u.question_id AND o.is_correct = 1);
  IF v_bad > 0 THEN
    SET v_msg = CONCAT(v_bad, ' câu hỏi trên Moodle đã bị sửa khác đề gốc (số phương án hoặc đáp án đúng) – kiểm tra lại các câu QB-n trên Moodle');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;

  -- d. Sinh viên + danh sách lớp HP từ Moodle (2 bước: gắn tài khoản Moodle cho SV đã có mã, rồi thêm SV mới)
  UPDATE students s JOIN v_mdl_exam_roster ro ON ro.exam_id = p_exam_id AND ro.student_code = s.student_code
  SET s.moodle_user_id = ro.mdl_user_id
  WHERE s.moodle_user_id IS NULL
    AND NOT EXISTS (SELECT 1 FROM (SELECT moodle_user_id FROM students WHERE moodle_user_id IS NOT NULL) x
                     WHERE x.moodle_user_id = ro.mdl_user_id);

  INSERT INTO students (student_code, full_name, moodle_user_id)
  SELECT ro.student_code, ro.full_name, ro.mdl_user_id FROM v_mdl_exam_roster ro
  WHERE ro.exam_id = p_exam_id
    AND NOT EXISTS (SELECT 1 FROM students s WHERE s.moodle_user_id = ro.mdl_user_id OR s.student_code = ro.student_code);

  INSERT IGNORE INTO enrollments (class_section_id, student_id)
  SELECT v_cs, s.id FROM v_mdl_exam_roster ro JOIN students s ON s.moodle_user_id = ro.mdl_user_id
  WHERE ro.exam_id = p_exam_id;

  -- e. Mã đề của bài giấy = nhóm đề Offline Quiz (A, B, C…) – để thống kê theo mã đề
  INSERT IGNORE INTO exam_versions (exam_id, version_code)
  SELECT DISTINCT p_exam_id, a.group_code FROM v_mdl_attempts a WHERE a.exam_id = p_exam_id AND a.group_code IS NOT NULL;

  -- f. Lượt bài được tính điểm
  INSERT INTO exam_attempts (exam_id, student_id, version_id, moodle_attempt_id, source, started_at, finished_at, status)
  SELECT a.exam_id, s.id, v.id, a.moodle_attempt_id, 'moodle', a.started_at, a.finished_at, 'finished'
  FROM v_mdl_attempts a JOIN students s ON s.moodle_user_id = a.mdl_user_id
  LEFT JOIN exam_versions v ON v.exam_id = a.exam_id AND v.version_code = a.group_code
  WHERE a.exam_id = p_exam_id
  ON DUPLICATE KEY UPDATE
     exam_attempts.version_id        = VALUES(version_id),
     exam_attempts.moodle_attempt_id = VALUES(moodle_attempt_id),
     exam_attempts.source            = 'moodle',
     exam_attempts.started_at        = VALUES(started_at),
     exam_attempts.finished_at       = VALUES(finished_at),
     exam_attempts.status            = 'finished';

  -- g. Vắng thi: có trong danh sách lớp HP (active) nhưng không có bài được chấm trên Moodle
  INSERT INTO exam_attempts (exam_id, student_id, source, status, total_score)
  SELECT p_exam_id, en.student_id, 'moodle', 'absent', 0
  FROM enrollments en
  JOIN students s ON s.id = en.student_id
  WHERE en.class_section_id = v_cs AND en.status = 'active'
    AND NOT EXISTS (SELECT 1 FROM v_mdl_attempts a WHERE a.exam_id = p_exam_id AND a.mdl_user_id = s.moodle_user_id)
  ON DUPLICATE KEY UPDATE
     exam_attempts.version_id = NULL, exam_attempts.moodle_attempt_id = NULL, exam_attempts.source = 'moodle',
     exam_attempts.started_at = NULL, exam_attempts.finished_at = NULL,
     exam_attempts.status = 'absent', exam_attempts.total_score = 0;

  -- h. Làm mới kết quả từng câu
  DELETE r FROM item_level_results r JOIN exam_attempts a ON a.id = r.attempt_id
  WHERE a.exam_id = p_exam_id;

  INSERT INTO item_level_results (attempt_id, question_id, selected_option_id, response_status, is_correct, score_earned)
  SELECT a.id, v.question_id, v.selected_option_id, v.response_status, v.is_correct, IF(v.is_correct, eq.points, 0)
  FROM v_mdl_item_results v
  JOIN exam_attempts  a  ON a.exam_id = p_exam_id AND a.moodle_attempt_id = v.moodle_attempt_id
  JOIN exam_questions eq ON eq.exam_id = p_exam_id AND eq.question_id = v.question_id
  WHERE v.exam_id = p_exam_id;

  INSERT INTO item_level_results (attempt_id, question_id, response_status)
  SELECT a.id, eq.question_id, 'absent'
  FROM exam_attempts a JOIN exam_questions eq ON eq.exam_id = a.exam_id
  WHERE a.exam_id = p_exam_id AND a.status = 'absent';

  -- i. Tổng điểm & trạng thái
  UPDATE exam_attempts a
  LEFT JOIN (SELECT r.attempt_id, SUM(r.score_earned) sc FROM item_level_results r
               JOIN exam_attempts x ON x.id = r.attempt_id AND x.exam_id = p_exam_id
              GROUP BY r.attempt_id) t ON t.attempt_id = a.id
  SET a.total_score = COALESCE(t.sc, 0)
  WHERE a.exam_id = p_exam_id;

  -- dữ liệu vừa làm mới: kết quả phân tích cũ không còn hiệu lực cho tới khi phân tích lại
  UPDATE exams SET status = 'Synced', last_synced_at = NOW() WHERE id = p_exam_id;
  COMMIT;

  UPDATE sync_runs SET status = 'success', finished_at = NOW(),
         n_attempts = (SELECT COUNT(*) FROM exam_attempts WHERE exam_id = p_exam_id AND status = 'finished'),
         n_absent   = (SELECT COUNT(*) FROM exam_attempts WHERE exam_id = p_exam_id AND status = 'absent')
  WHERE id = v_run;
END$$
DELIMITER ;
