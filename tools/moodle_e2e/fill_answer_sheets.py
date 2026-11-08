"""Mô phỏng sinh viên làm bài thi giấy: tô phiếu trả lời do Moodle (Offline Quiz) sinh ra rồi xuất ảnh "quét"."""
from __future__ import annotations

import pymupdf

DPI = 200
BOX = 3.5 * 72 / 25.4


def _boxes(page):
    out = []
    for d in page.get_drawings():
        for it in d["items"]:
            r = it[1] if it[0] == "re" else None
            if r is not None and abs(r.width - BOX) < 0.6 and abs(r.height - BOX) < 0.6:
                if not any(abs(r.x0 - o.x0) < 1 and abs(r.y0 - o.y0) < 1 for o in out):
                    out.append(pymupdf.Rect(r))
    return out


def _rows(rects, tol=2.0):
    rows = []
    for r in sorted(rects, key=lambda r: (r.y0, r.x0)):
        if rows and abs(rows[-1][0].y0 - r.y0) < tol:
            rows[-1].append(r)
        else:
            rows.append([r])
    return [sorted(x, key=lambda r: r.x0) for x in rows]


def _cross(page, r):
    k = 1.1
    page.draw_line(pymupdf.Point(r.x0 + k, r.y0 + k), pymupdf.Point(r.x1 - k, r.y1 - k), width=1.1)
    page.draw_line(pymupdf.Point(r.x1 - k, r.y0 + k), pymupdf.Point(r.x0 + k, r.y1 - k), width=1.1)


def fill_sheet(answer_pdf: str, student_id: str, answers: list[int | None], out_png: str) -> None:
    doc = pymupdf.open(answer_pdf)
    page = doc[0]
    w = page.rect.width
    boxes = _boxes(page)
    idrows = _rows([b for b in boxes if b.x0 > 0.6 * w and b.y0 < 130 * 72 / 25.4])
    if len(idrows) != 10 or any(len(r) != len(student_id) for r in idrows):
        raise ValueError(f"Phiếu có ô MSSV {[len(r) for r in idrows]} – không khớp MSSV {student_id}")
    for col, d in enumerate(student_id):
        _cross(page, idrows[int(d)][col])
    arows = _rows([b for b in boxes if b.x0 < 0.6 * w and b.y0 > 100 * 72 / 25.4])
    if len(arows) < len(answers):
        raise ValueError(f"Phiếu có {len(arows)} câu, đặc tả có {len(answers)} câu")
    for i, a in enumerate(answers):
        if a is not None:
            _cross(page, arows[i][a])
    pix = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
    pix.save(out_png)
