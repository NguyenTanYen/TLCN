"""Đề giấy sinh & chấm trên hệ thống: mã đề, xem trước, xuất PDF/Word, phiếu trả lời, chấm ảnh phiếu (OMR)."""
import io
import random
import zipfile

import fitz
import numpy as np
import cv2
from sqlalchemy import text

from app.database import engine
from app.services import paper as P


def _q(sql, **p):
    with engine.connect() as c:
        return c.execute(text(sql), p).fetchall()


def test_system_paper_exam_end_to_end(client, gv, gv_other):
    qs = [q for q in client.get("/api/questions?course_id=5", headers=gv).json() if q["tagged"] is not False][:12]
    r = client.post("/api/exams", headers=gv, json={"class_section_id": 1, "exam_title": "Kiểm tra giấy chấm trên hệ thống", "exam_type": "paper",
                                                    "assessment_type": "process", "max_score": 10,
                                                    "items": [{"question_id": q["id"], "points": 1} for q in qs]})
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    assert client.get(f"/api/exams/{eid}/paper", headers=gv).json()["mode"] is None
    assert client.post(f"/api/exams/{eid}/paper/versions", headers=gv_other, json={"n_versions": 2}).status_code == 403
    r = client.post(f"/api/exams/{eid}/paper/versions", headers=gv, json={"n_versions": 3, "seed": 5})
    assert r.status_code == 200, r.text
    st = client.get(f"/api/exams/{eid}/paper", headers=gv).json()
    assert st["mode"] == "system" and [v["version_code"] for v in st["versions"]] == ["01", "02", "03"]
    v1, v2 = st["versions"][0], st["versions"][1]
    # mã đề 02: cùng bộ câu, thứ tự khác; mỗi câu đúng một đáp án; nhãn in liên tục A, B, …
    assert {q["question_id"] for q in v1["questions"]} == {q["question_id"] for q in v2["questions"]}
    assert all(q["answer"] and [o["label"] for o in q["options"]] == list("ABCDEF"[:len(q["options"])]) for q in v2["questions"])
    # Moodle Offline Quiz bị chặn khi đã dùng chế độ hệ thống
    assert client.post(f"/api/exams/{eid}/moodle/create-offlinequiz", headers=gv, json={"moodle_course_id": 1}).status_code == 409
    # tùy chọn in: chia 2 cột, đổi cỡ chữ; xuất PDF (đủ 3 mã đề) và Word
    assert client.put(f"/api/exams/{eid}/paper/settings", headers=gv, json={"paper": {"columns": 2, "font_size": 11, "duration": "30 phút"},
                                                                          "sheet": {"student_digits": 8, "essay_lines": 0}}).status_code == 200
    pdf = client.get(f"/api/exams/{eid}/paper/exam.pdf", headers=gv)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    doc = fitz.open(stream=pdf.content, filetype="pdf")
    txt = "".join(p.get_text() for p in doc)
    assert all(f"MÃ ĐỀ: {c}" in txt for c in ("01", "02", "03")) and "Câu 12." in txt
    one = fitz.open(stream=client.get(f"/api/exams/{eid}/paper/exam.pdf?version=02&columns=1", headers=gv).content, filetype="pdf")
    assert "MÃ ĐỀ: 02" in one[0].get_text() and "MÃ ĐỀ: 01" not in "".join(p.get_text() for p in one)
    docx = client.get(f"/api/exams/{eid}/paper/exam.docx?version=01", headers=gv)
    assert docx.status_code == 200 and docx.content[:2] == b"PK"
    png = client.get(f"/api/exams/{eid}/paper/answer-sheet.png?student_digits=9", headers=gv)
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"
    key = fitz.open(stream=client.get(f"/api/exams/{eid}/paper/answer-key.pdf", headers=gv).content, filetype="pdf")[0].get_text()
    assert f"1.{v2['questions'][0]['answer']}" in key
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/exams/{eid}/paper/package.zip", headers=gv).content))
    assert {"phieu_tra_loi.pdf", "dap_an.pdf", "de_ma_01.pdf", "de_ma_03.docx"} <= set(z.namelist())

    # SV làm bài: tô phiếu (in thật ra PDF -> ảnh), một số chụp nghiêng bằng điện thoại
    studs = [r[0] for r in _q("""SELECT s.student_code FROM enrollments e JOIN students s ON s.id=e.student_id
                                 WHERE e.class_section_id=1 ORDER BY s.student_code LIMIT 6""")]
    rng = random.Random(2)
    fills, truth = [], {}
    for i, code in enumerate(studs):
        v = st["versions"][i % 3]
        ans = {q["position"]: (q["answer"] if rng.random() < 0.7 else rng.choice([o["label"] for o in q["options"]])) for q in v["questions"]}
        ans[1] = ""                                                      # bỏ trống câu 1
        fills.append({"student": code, "version": v["version_code"], "answers": ans})
        truth[code] = sum(1 for q in v["questions"] if ans[q["position"]] == q["answer"])
    from app.database import SessionLocal
    from app.models import Exam
    db = SessionLocal()
    o = P.sheet_options_for(db, db.get(Exam, eid), student_digits=8, essay_lines=0)
    db.close()
    filled = fitz.open(stream=P.sheet_pdf(o, prefills=fills), filetype="pdf")
    files = []
    for k, page in enumerate(filled):
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csGRAY)
        img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width).copy()
        if k % 2:      # ảnh chụp nghiêng
            h, w = img.shape
            M = cv2.getRotationMatrix2D((w / 2, h / 2), 5, 0.9)
            img = cv2.warpAffine(img, M, (w, h), borderValue=120)
        files.append(("files", (f"phieu_{k}.jpg", cv2.imencode(".jpg", img)[1].tobytes(), "image/jpeg")))
    sc = client.post(f"/api/exams/{eid}/scan", headers=gv, files=files)
    assert sc.status_code == 200, sc.text
    sheets = sc.json()["sheets"]
    assert len(sheets) == 6 and all("error" not in s for s in sheets)
    assert [s["student_code"] for s in sheets] == studs
    assert all(s["score"] == truth[s["student_code"]] for s in sheets)
    # GV sửa một phiếu trên màn hình soát (đổi đáp án câu 1) rồi lưu
    s0 = sheets[0]
    v0 = next(v for v in st["versions"] if v["version_code"] == s0["version_code"])
    s0["answers"]["1"] = v0["questions"][0]["answer"]
    r = client.post(f"/api/exams/{eid}/scan/commit", headers=gv, json={"sheets": [{k: s[k] for k in ("student_code", "version_code", "answers", "source_name")}
                                                                                  for s in sheets]})
    assert r.status_code == 200, r.text
    assert r.json()["saved"] == 6 and r.json()["absent"] == 34 and r.json()["analysis"]["n_students"] == 6
    tot = dict(_q("""SELECT s.student_code, a.total_score FROM exam_attempts a JOIN students s ON s.id=a.student_id
                     WHERE a.exam_id=:e AND a.status='finished'""", e=eid))
    assert float(tot[studs[0]]) == truth[studs[0]] + 1 and all(float(tot[c]) == truth[c] for c in studs[1:])
    assert client.get(f"/api/exams/{eid}", headers=gv).json()["status"] == "Analyzed"
    assert client.delete(f"/api/exams/{eid}/paper/versions", headers=gv).status_code == 409   # đã có kết quả
    with engine.begin() as c:     # dọn: bài thử không ảnh hưởng kiểm thử khác
        c.execute(text("DELETE FROM exams WHERE id=:e"), {"e": eid})
    from app.services import results
    db = SessionLocal(); results.recompute_class_section(db, 1); db.close()


def test_omr_crossed_out_and_scribbles():
    """Gạch chéo ô cũ rồi tô ô mới → lấy ô mới; nét bút đè lên ô định vị không làm lệch phiếu; tô 2 ô → cảnh báo."""
    from app.services import omr
    o = P.SheetOptions(n_questions=10, student_digits=8, version_codes=["01", "02"])
    L = P.sheet_layout(o)
    page = fitz.open(stream=P.sheet_pdf(o, prefills=[{"student": "22130007", "version": "02", "answers": {}}]), filetype="pdf")[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(150 / 72, 150 / 72), colorspace=fitz.csGRAY)
    g = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width).copy()
    s = 150 / 25.4
    pos = {(b["q"], b["label"]): (int(b["x"] * s), int(b["y"] * s)) for b in L["answers"]}
    r = int(L["r"] * s)
    fill = lambda q, l: cv2.circle(g, pos[(q, l)], int(r * .9), 40, -1)
    for q, l in [(1, "A"), (2, "B"), (3, "C"), (4, "D"), (5, "A"), (5, "C")]:
        fill(q, l)
    x, y = pos[(1, "C")]
    cv2.line(g, (x - r, y - r), (x + r, y + r), 30, 2); cv2.line(g, (x - r, y + r), (x + r, y - r), 30, 2)   # gạch bỏ C, chọn A
    for (fx, fy) in P.fid_centers():                                            # nét bút chạy qua cả 4 ô định vị
        cx, cy = int(fx * s), int(fy * s)
        cv2.line(g, (cx - 60, cy - 25), (cx + 60, cy + 30), 20, 3)
    res = omr.read_sheet(g, o)
    assert res["student_code"] == "22130007" and res["version_code"] == "02"
    assert [res["answers"][q] for q in range(1, 7)] == ["A", "B", "C", "D", "AC", ""]
    assert any(i.startswith("Câu 5:") for i in res["issues"]) and not any(i.startswith("Câu 1:") for i in res["issues"])


def test_doc_anh_chup_that_phieu_ban_cu():
    """Ảnh chụp thật (nền tối dính ô định vị góc, ánh sáng không đều, phiếu in bản cũ không có vạch nhận chiều)."""
    import os
    import cv2
    from app.services import omr, paper as pp
    g = cv2.imread(os.path.join(os.path.dirname(__file__), "data", "anh_phieu_cu_chup_that.jpg"), cv2.IMREAD_GRAYSCALE)
    o = pp.SheetOptions(n_questions=10, student_digits=8, version_digits=2, version_codes=["01", "02"])
    r = omr.read_sheet(g, o)
    assert r["student_code"] == "23110369" and r["version_code"] == "01"
    assert "".join(r["answers"][q] for q in range(1, 11)) == "ABACDACACD"
