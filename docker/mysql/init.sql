-- Khởi tạo MySQL dùng chung cho Moodle và hệ thống (cầu nối đọc chéo schema `moodle`)
CREATE DATABASE IF NOT EXISTS moodle        CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS assessment_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'moodle'@'%' IDENTIFIED WITH mysql_native_password BY 'moodle_pass';
GRANT ALL PRIVILEGES ON moodle.* TO 'moodle'@'%';
CREATE USER IF NOT EXISTS 'tlcn'@'%' IDENTIFIED WITH mysql_native_password BY 'tlcn_pass';
GRANT ALL PRIVILEGES ON assessment_db.* TO 'tlcn'@'%';
GRANT SELECT ON moodle.* TO 'tlcn'@'%';            -- hệ thống CHỈ ĐỌC dữ liệu Moodle
GRANT CREATE ROUTINE, ALTER ROUTINE, EXECUTE ON assessment_db.* TO 'tlcn'@'%';
FLUSH PRIVILEGES;
