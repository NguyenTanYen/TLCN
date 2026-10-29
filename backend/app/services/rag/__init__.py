"""Gợi ý học liệu từ những câu sinh viên làm sai (RAG – phần truy xuất).

Phạm vi tìm: chỉ học liệu của LỚP HỌC PHẦN mà sinh viên đang học (lấy từ course Moodle của lớp hoặc GV tải lên).
Các bước được xây dần:
  ingest  – đọc PDF thành trang và khối chữ có tọa độ (bbox) để chỉ đúng "khúc nào" trên trang.
  chunk   – gom khối chữ thành ĐOẠN để tìm kiếm (gắn tiêu đề, gộp khối nhỏ, cắt khối dài) + đoạn HÌNH cho sơ đồ/ảnh.
  store   – ghi trang + đoạn của một học liệu vào CSDL (section_materials → material_pages → material_passages).
"""
