// [đường dẫn, tên, [đường dẫn con cùng nhóm], mô tả ngắn (hiện khi rê chuột và ở trang Tổng quan)]
export const MENUS = {
  lecturer: [
    ['Bắt đầu', [['/', 'Tổng quan', [], 'Việc cần làm tiếp theo và đường tắt tới từng chức năng']]],
    ['Giảng dạy', [['/courses', 'Môn học của tôi', ['/sections', '/exams'], 'Các lớp bạn dạy: tạo bài kiểm tra, chấm điểm, xem kết quả, ôn tập cho sinh viên yếu'],
      ['/questions', 'Ngân hàng câu hỏi', [], 'Soạn, nhập từ Word/Excel và quản lý câu hỏi của môn']]],
    ['Tra cứu', [['/programs', 'Chương trình đào tạo', [], 'Xem chuẩn đầu ra, chỉ báo và các học phần của chương trình']]],
    ['Trợ giúp', [['/huong-dan', 'Hướng dẫn sử dụng', [], 'Cách làm từng việc, giải thích các thuật ngữ']]],
  ],
  admin: [
    ['Bắt đầu', [['/', 'Tổng quan', [], 'Mức hoàn thiện thiết lập và những việc còn thiếu']]],
    ['Đào tạo', [['/programs', 'Chương trình đào tạo', [], 'Khai báo chương trình, chuẩn đầu ra (PLO) và chỉ báo đo (PI)'],
      ['/courses', 'Học phần', [], 'Đề cương, chuẩn đầu ra môn học (CLO) và liên kết CLO với PI']]],
    ['Giảng dạy', [['/sections', 'Lớp học phần', ['/exams'], 'Mở lớp, phân công giảng viên, đưa danh sách sinh viên, nối với Moodle'],
      ['/questions', 'Ngân hàng câu hỏi', [], 'Kho câu hỏi dùng chung của các môn']]],
    ['Đánh giá', [['/pi-plans', 'Kế hoạch đo chỉ báo (PI)', [], 'Chọn môn và học kỳ lấy số liệu để đo từng chỉ báo'],
      ['/plo-summary', 'Kết quả chương trình (PLO)', [], 'Tỷ lệ đạt từng chuẩn đầu ra chương trình theo năm học, xuất biểu mẫu']]],
    ['Hệ thống', [['/system', 'Kết nối Moodle', [], 'Kiểm tra và cấu hình kết nối với Moodle'],
      ['/huong-dan', 'Hướng dẫn sử dụng', [], 'Cách làm từng việc, giải thích các thuật ngữ']]],
  ],
}
