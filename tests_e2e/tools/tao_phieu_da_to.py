"""Tạo ảnh phiếu trả lời ĐÃ TÔ cho một bài thi giấy (dùng trong kịch bản GV8 – tải phiếu quét lên để hệ thống chấm).

Dùng chính bộ vẽ phiếu của hệ thống (services/paper.py) nên bố cục khớp với phiếu in ra từ bài thi.
Chạy:  .venv\\Scripts\\python tests_e2e\\tools\\tao_phieu_da_to.py <exam_id> <mssv> <tệp_png_ra> [đáp_án_tô]
       đáp_án_tô mặc định "A" cho mọi câu; mã đề = mã đề đầu tiên của bài.
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)                      # cấu hình backend đọc cau_hinh.env theo thư mục hiện tại

import fitz  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Exam  # noqa: E402
from app.services import paper  # noqa: E402


def main():
    exam_id, student, out = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    answer = sys.argv[4] if len(sys.argv) > 4 else "A"
    db = SessionLocal()
    try:
        o = paper.sheet_options_for(db, db.get(Exam, exam_id))
        pdf = paper.sheet_pdf(o, prefills=[{"student": student, "version": o.version_codes[0],
                                            "answers": {q: answer for q in range(1, o.n_questions + 1)}}])
    finally:
        db.close()
    fitz.open(stream=pdf, filetype="pdf")[0].get_pixmap(dpi=150).save(out)
    print(out)


if __name__ == "__main__":
    main()
