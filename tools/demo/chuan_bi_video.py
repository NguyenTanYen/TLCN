"""Chuẩn bị dữ liệu quay video demo – chạy SAU bước 4 (dữ liệu demo trên Moodle), MariaDB và Moodle đang chạy.

Bổ sung cho lớp DBMS330284_01 (chạy lại không tạo trùng – bài đã có thì bỏ qua):
  1. Bài "Kiểm tra giữa kỳ (giấy – chấm trên hệ thống)": 10 câu lấy từ bài thi cuối kỳ, 2 mã đề.
     Sinh sẵn ảnh phiếu trả lời ĐÃ TÔ của 8 SV vào demo_video/phieu_da_to/ (mỗi SV một mức làm đúng khác nhau)
     để khi quay chỉ cần mở bài → "In đề & chấm phiếu" → "4. Chấm phiếu" → tải các ảnh này lên.
  2. Bài ôn tập cho 2 SV làm sai nhiều nhất ở bài thi cuối kỳ, đã tạo Quiz trên Moodle (chỉ 2 SV đó làm được).
Bài "Thi cuối kỳ (Moodle)" đã đồng bộ, phân tích và công bố sẵn từ bước 4.

Chạy:  .venv\\Scripts\\python tools\\demo\\chuan_bi_video.py      (từ thư mục gốc dự án)
"""
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)                      # cấu hình backend đọc cau_hinh.env theo thư mục hiện tại

import fitz  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Exam  # noqa: E402
from app.services import paper  # noqa: E402

SECTION = "DBMS330284_01"
FINAL = "Thi cuối kỳ (Moodle)"
PAPER = "Kiểm tra giữa kỳ (giấy – chấm trên hệ thống)"
REMEDIAL = "Ôn tập – nhóm 2 SV làm sai nhiều nhất"
OUT = ROOT / "demo_video" / "phieu_da_to"
N_SHEETS = 8


def main():
    c = TestClient(app)
    tok = c.post("/api/auth/login", json={"username": "gv.son", "password": "Gv@123456"})
    tok.raise_for_status()
    c.headers["Authorization"] = f"Bearer {tok.json()['access_token']}"

    def call(method, url, **kw):
        r = c.request(method, url, **kw)
        if r.status_code >= 400:
            raise SystemExit(f"*** {method} {url} → {r.status_code}: {r.text[:300]}")
        return r.json()

    cs = next((s for s in call("GET", "/api/class-sections") if s["section_code"] == SECTION), None)
    if not cs:
        raise SystemExit(f"*** Chưa có lớp {SECTION} – chạy 4_TAO_DU_LIEU_DEMO_TREN_MOODLE.bat trước")
    exams = call("GET", f"/api/class-sections/{cs['id']}/exams")
    final = next((e for e in exams if e["exam_title"] == FINAL and e["status"] == "Analyzed"), None)
    if not final:
        raise SystemExit(f"*** Lớp {SECTION} chưa có bài \"{FINAL}\" đã phân tích – chạy bước 4 trước")
    print(f"Lớp {SECTION} (#{cs['id']}) · bài thi cuối kỳ #{final['id']} đã phân tích ({final['n_attempts']} bài làm)")

    # ---- 1. Bài giấy chấm trên hệ thống + ảnh phiếu đã tô
    pe = next((e for e in exams if e["exam_title"] == PAPER), None)
    if pe:
        print(f"Bài giấy #{pe['id']} đã có – bỏ qua bước tạo")
    else:
        qs = [q for q in sorted(final["questions"], key=lambda q: q["order_index"]) if not q["is_cancelled"]][::2][:10]
        pe = call("POST", "/api/exams", json={"class_section_id": cs["id"], "exam_title": PAPER, "exam_type": "paper", "assessment_type": "process",
                                              "duration_minutes": 30, "max_score": 10, "items": [{"question_id": q["question_id"], "points": 1} for q in qs]})
        call("POST", f"/api/exams/{pe['id']}/paper/versions", json={"n_versions": 2, "shuffle_questions": True, "shuffle_options": True, "seed": 7})
        print(f"Đã tạo bài giấy #{pe['id']} ({len(qs)} câu, 2 mã đề)")
    students = [s for s in call("GET", f"/api/class-sections/{cs['id']}/students") if s["status"] == "active"][:N_SHEETS]
    db = SessionLocal()
    try:
        e = db.get(Exam, pe["id"])
        versions = paper.versions_data(db, e)
        if not versions:
            raise SystemExit(f"*** Bài #{pe['id']} chưa có mã đề hệ thống (có thể đang dùng Moodle Offline Quiz)")
        o = paper.sheet_options_for(db, e)
        rng = random.Random(2026)
        prefills = []
        for i, s in enumerate(students):
            v = versions[i % len(versions)]
            acc = 0.35 + 0.6 * i / max(1, len(students) - 1)              # SV đầu làm kém, SV cuối làm tốt
            ans = {}
            for q in v["questions"]:
                labels = [x["label"] for x in q["options"]]
                ans[q["position"]] = q["answer"] if rng.random() < acc else rng.choice([x for x in labels if x != q["answer"]] or labels)
            prefills.append({"student": s["student_code"], "version": v["version_code"], "answers": ans})
        pdf = fitz.open(stream=paper.sheet_pdf(o, prefills=prefills), filetype="pdf")
    finally:
        db.close()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    for page, p in zip(pdf, prefills):
        page.get_pixmap(dpi=150).save(OUT / f"phieu_{p['student']}_ma{p['version']}.png")
    print(f"Đã sinh {len(prefills)} ảnh phiếu đã tô vào {OUT}")

    # ---- 2. Bài ôn tập cho 2 SV làm sai nhiều nhất, tạo Quiz trên Moodle
    re_ = next((e for e in exams if e["exam_title"] == REMEDIAL), None)
    if re_:
        print(f"Bài ôn tập #{re_['id']} đã có – bỏ qua")
    else:
        top = call("GET", f"/api/class-sections/{cs['id']}/remedial?exam_ids={final['id']}")["students"][:2]
        re_ = call("POST", f"/api/class-sections/{cs['id']}/remedial-exams", json={
            "student_ids": [s["student_id"] for s in top], "exam_ids": [final["id"]], "exam_title": REMEDIAL,
            "similar_per_question": 1, "max_questions": 15, "seed": 1})
        print(f"Đã tạo bài ôn tập #{re_['id']} cho {', '.join(s['student_code'] for s in top)} ({re_['n_questions']} câu)")
    if not call("GET", f"/api/exams/{re_['id']}").get("moodle_quiz_id"):
        r = c.post(f"/api/exams/{re_['id']}/moodle/create-quiz", json={"moodle_course_id": cs["moodle_course_id"]})
        print("Tạo Quiz ôn tập trên Moodle:", r.json() if r.status_code < 400 else f"LỖI {r.status_code} {r.text[:200]} (tạo lại ở trang bài KT)")

    print("\nXONG. Mở http://localhost:8000 (gv.son / Gv@123456):")
    print(f"  - Bài thi cuối kỳ đã phân tích : /exams/{final['id']}")
    print(f"  - Bài giấy để demo chấm phiếu  : /exams/{pe['id']}  (ảnh phiếu: {OUT})")
    print(f"  - Bài ôn tập đã giao 2 SV      : /exams/{re_['id']}")


if __name__ == "__main__":
    main()
