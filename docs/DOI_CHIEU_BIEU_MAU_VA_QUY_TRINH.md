# Đối chiếu quy tắc tính với biểu mẫu và quy trình của trường

Tài liệu này ghi lại các nguồn đã đối chiếu để chốt quy tắc tính mức độ đạt CLO, PI, PLO và CTĐT của hệ thống, nhằm trả lời khi phản biện.

## 1. Nguồn đã đối chiếu

| Nguồn | Nội dung dùng để đối chiếu |
|---|---|
| Quy trình đo lường mức độ đạt chuẩn đầu ra CTĐT của người học, số hiệu QT-PĐBCL-ĐLCĐR, ngày hiệu lực 05/09/2022 (bản scan 49 trang, gồm hướng dẫn và các biểu mẫu BM1 đến BM6) | Nguồn chính thống của trường: định nghĩa từng bước, từng biểu mẫu và ghi chú công thức đi kèm |
| BM3b, BM3c (tệp BM03b_c.xlsx) | Mẫu chung kế hoạch và kết quả PI cho một CĐR |
| BM6a đến BM6d (tệp BM06a_d.xlsx) | Mẫu chung kế hoạch và minh chứng CLO của môn học |
| BM3_ATTT.xlsx (17 sheet PI, các sheet 3c, BM3f) | Số liệu thật của CTĐT An toàn thông tin: kết quả PI, CĐR và tổng hợp CTĐT |
| Mau06_ATTT.xlsx (các sheet 6b, 6c) | Số liệu thật của các môn học An toàn thông tin: CLO và PI theo từng môn |
| BM2_KTDL.docx, bảng phân công đánh giá PI | Ánh xạ môn học, CLO, PI và người phụ trách |

## 2. Quy tắc rút ra (giống nhau ở mọi nguồn)

1. **Đơn vị đếm là sinh viên.** Mỗi sinh viên có một cột "Điểm câu hỏi" (điểm các câu hỏi liên quan đến CLO hoặc PI) và "Điểm tối đa" của các câu đó. Sinh viên đạt khi điểm ≥ x% điểm tối đa. Mẫu trong quy trình dùng 60%, 65%, 70% tùy biểu mẫu, nên ngưỡng là tham số của từng kế hoạch. Phép so sánh là ≥, sinh viên 0 điểm vẫn nằm trong số được đánh giá.
2. **CLO (BM6c, BM6d).** Mỗi bài kiểm tra (Bài KT 1, 2, 3) đếm riêng số SV thực hiện và số SV đạt. Kết quả CLO là tổng số SV đạt chia tổng số SV thực hiện qua các bài. Sinh viên làm nhiều bài thì được tính ở từng bài (lượt).
3. **Môn học (BM6b).** Dòng "Kết quả đạt được CĐR môn học" bằng tổng SV đạt chia tổng SV đánh giá của các CLO.
4. **PI (BM3d, BM3e).** Mỗi môn lấy mẫu (Môn 1, 2, 3) có một cột "Điểm câu hỏi PI". Số SV đạt của PI là tổng số SV đạt của các môn, chia tổng số SV đánh giá của các môn.
5. **CĐR CTĐT (BM3c).** Kết quả CĐR bằng tổng SV đạt chia tổng SV đánh giá của các PI thuộc CĐR đó (công thức `SUM(D)/SUM(E)`).
6. **CTĐT (BM3f, BM2b).** Dòng "Kết quả đạt được CĐR CTĐT" cũng là `SUM(D)/SUM(E)` trên tất cả các dòng PI.
7. **Đánh giá Đạt hay Không đạt.** Mỗi mức (CLO, PI, CĐR, CTĐT) so tỷ lệ với chỉ tiêu mong muốn riêng của mức đó (≥ chỉ tiêu thì Đạt).
8. **Chu kỳ đo.** Mỗi CĐR được đo ít nhất 2 năm một lần, đủ tất cả CĐR trong một chu kỳ đào tạo (BM2a, BM2b).

## 3. Cách hệ thống cài đặt

| Quy tắc | Nơi cài đặt |
|---|---|
| Ngưỡng và chỉ tiêu theo kế hoạch (`pass_threshold_pct`, `target_pct`) | bảng `clo_assessment_plans`, `pi_assessment_plans`, `plo_measurement_plans` |
| Kết quả CLO theo lượt | `analysis.attempt_clo_scores`, bảng `attempt_clo_results`, `clo_results` |
| PI tính theo từng sinh viên, cộng điểm các CLO của kế hoạch PI | `results._student_counts`, `results.recompute_pi_plans`, bảng `pi_results` |
| PLO và CTĐT cộng dồn số SV | `results.recompute_plo`, `analysis.aggregate`, bảng `plo_results` |
| Xuất BM2, BM3, BM6 | `reports_excel.py`, `reports_word.py` |

Khi một PI có nhiều CLO trong cùng một môn, biểu mẫu chỉ có một cột "Điểm câu hỏi PI". Hệ thống cộng điểm đạt được và điểm tối đa của các CLO đó, ngưỡng của sinh viên là tổng của (điểm tối đa nhân ngưỡng của từng CLO).

## 4. Kiểm chứng bằng số liệu thật của biểu mẫu

Tệp `backend/tests/test_pi_per_student.py` và `backend/tests/data/bieu_mau_goc.json` nạp điểm từng sinh viên trong các sheet của thầy cô và đếm bằng hàm của hệ thống:

| Sheet | Ngưỡng | Biểu mẫu ghi | Hệ thống tính |
|---|---|---|---|
| BM3_ATTT, CDR1 PI1 | 60% của 0,8 | 64/83 | 64/83 |
| Mau06_ATTT, 6c CDR1 PI1 | ≥ 1,2 của 2 | 62/76 | 62/76 |
| Mau06_ATTT, 6c CDR2 PI2 | ≥ 0,75 của 1,3 | 50/54 | 50/54 |
| Mau06_ATTT, 6c CDR3 PI1 | ≥ 0,5 của 1 | 66/87 | 66/87 |
| BM6c mẫu, CĐR1 | 60% của 3,2 | 28/31 | 28/31 |
| BM6d mẫu, CĐR2 và CĐR3, Bài KT 1 | 65% và 70% của 5 | 10/14 | 10/14 |

Các tổng cộng dồn cũng khớp: BM6b 195/271, BM6d 27/41 và 27/38, 3c CĐR4 172/198, BM3f CTĐT 1660/1832 = 90,61%.

## 5. Lưu ý khi đối chiếu

- Ngưỡng của từng sheet trong các tệp thầy cô không cố định: có sheet dùng 60%, có sheet dùng 50% hoặc 57,7% của điểm tối đa. Vì vậy hệ thống cho đặt ngưỡng riêng cho từng kế hoạch.
- Một số ô trong tệp thầy cô nhập tay (số SV đạt gõ trực tiếp, công thức `#DIV/0!`) nên không dùng làm chuẩn so sánh, chỉ dùng các sheet có công thức đếm rõ ràng.
- Các khối Bài KT 2 và Bài KT 3 trong BM6d mẫu để dấu "…" (dữ liệu rút gọn), nên chỉ dùng tổng ghi sẵn của các khối này để kiểm tra phép cộng dồn.
