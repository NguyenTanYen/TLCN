"""Nạp học liệu minh họa (slide 6 chương + giáo trình trích) vào học phần DBMS330284 và tạo gợi ý đọc cho các bài đã phân tích.

Dùng khi CSDL đã có dữ liệu demo từ trước (chưa có học liệu). Chạy lại không tạo trùng (học liệu cùng tên bỏ qua).
Chạy:  .venv\\Scripts\\python tools\\demo\\nap_hoc_lieu_mau.py      (từ thư mục gốc dự án; hệ thống/MariaDB có thể đang chạy hoặc không)
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.services import hoc_lieu_mau  # noqa: E402

COURSE = "DBMS330284"


def main():
    push = "--moodle" in sys.argv      # thêm --moodle: đẩy học liệu lên khóa học Moodle + cập nhật trang kết quả của sinh viên
    c = TestClient(app)
    tok = c.post("/api/auth/login", json={"username": "gv.son", "password": "Gv@123456"})
    tok.raise_for_status()
    c.headers["Authorization"] = f"Bearer {tok.json()['access_token']}"
    course = next((x for x in c.get("/api/courses").json() if x["course_code"] == COURSE), None)
    if not course:
        raise SystemExit(f"*** Chưa có học phần {COURSE}")
    cid = course["id"]
    outlines = {o["chapter_number"]: o["id"] for o in c.get(f"/api/courses/{cid}/syllabus").json()["outlines"]}
    have = {m["title"] for m in c.get(f"/api/courses/{cid}/materials").json()}
    for m in hoc_lieu_mau.samples(outlines):
        if m["title"] in have:
            print("Đã có:", m["title"])
            continue
        r = c.post(f"/api/courses/{cid}/materials", files={"file": (m["filename"], m["data"])},
                   data={"title": m["title"], "material_type": m["material_type"], **({"outline_id": m["outline_id"]} if m["outline_id"] else {})})
        print("Thêm:", m["title"], "→", r.json() if r.status_code < 400 else f"LỖI {r.status_code} {r.text[:200]}")
    if push:
        r = c.post(f"/api/courses/{cid}/moodle-sync-sections")      # gắn lớp HP với khóa học Moodle trùng mã (nếu có)
        print("Gắn lớp với Moodle:", r.json() if r.status_code < 400 else f"LỖI {r.status_code} {r.text[:160]}")
        for m in c.get(f"/api/courses/{cid}/materials").json():
            if m.get("moodle_cmid"):
                continue
            r = c.post(f"/api/materials/{m['id']}/push-moodle")
            print("Đẩy Moodle:", m["title"], "→", "OK" if r.status_code < 400 else f"LỖI {r.status_code} {r.text[:160]}")
    for cs in c.get("/api/class-sections").json():
        if cs["course_id"] != cid:
            continue
        for e in c.get(f"/api/class-sections/{cs['id']}/exams").json():
            if e["status"] == "Analyzed":
                r = c.post(f"/api/exams/{e['id']}/readings/rebuild")
                print(f"Gợi ý đọc bài #{e['id']} ({e['exam_title']}):", r.json() if r.status_code < 400 else r.text[:200])
                if push and not cs.get("moodle_course_id"):
                    print("   Bỏ qua gửi kết quả lên Moodle: lớp", cs.get("section_code"), "không gắn với khóa học Moodle (bài nhập điểm, SV xem trong hệ thống)")
                elif push:
                    r = c.post(f"/api/exams/{e['id']}/moodle/push-results")
                    print("   Đẩy kết quả lên Moodle:", "OK" if r.status_code < 400 else f"LỖI {r.status_code} {r.text[:160]}")


if __name__ == "__main__":
    main()
