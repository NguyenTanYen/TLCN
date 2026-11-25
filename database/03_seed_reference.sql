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

INSERT INTO lecturers (id, lecturer_code, full_name, department) VALUES
 (1,'GV001','Trần Trọng Bình','Bộ môn Kỹ thuật dữ liệu'),
 (2,'GV002','Lê Thị Minh Châu','Bộ môn Kỹ thuật dữ liệu'),
 (3,'GV003','Nguyễn Thành Sơn','Bộ môn Kỹ thuật dữ liệu'),
 (4,'GV004','Võ Xuân Thể','Bộ môn Kỹ thuật dữ liệu'),
 (5,'GV005','Phạm Chí Công','Bộ môn Kỹ thuật dữ liệu'),
 (6,'GV006','Nguyễn Văn Thành','Bộ môn Kỹ thuật dữ liệu'),
 (7,'GV007','Quách Đình Hoàng','Bộ môn Kỹ thuật dữ liệu');

INSERT INTO assessment_assignments (semester_id, course_id, lecturer_id, all_supervisors, note) VALUES
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),1,1,0,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),2,1,0,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),3,2,0,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),4,2,0,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),5,3,0,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),6,2,0,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),7,NULL,1,'Tất cả thầy/cô có HD'),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),8,NULL,1,'Tất cả thầy/cô có HD'),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),9,4,0,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),9,5,0,NULL),
 ((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),9,6,0,NULL);
