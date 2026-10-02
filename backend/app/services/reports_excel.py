"""Xuất báo cáo đo lường CĐR theo đúng bố cục biểu mẫu HCMUTE.

* build_bm6(class_section_id)  -> BM6a (kế hoạch CLO), BM6b (kết quả CLO), BM6c/6d (minh chứng từng CLO)
* build_bm3(program_id, year)  -> BM2 tổng kết CTĐT, BM3b (kế hoạch PI) và BM3c (kết quả PI) cho từng CĐR
"""
from __future__ import annotations

import io
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings

FONT = "Times New Roman"
THIN = Side(style="thin", color="000000")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEAD_FILL = PatternFill("solid", fgColor="D9E2F3")
WRAP = Alignment(wrap_text=True, vertical="center")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _f(bold=False, size=12, italic=False):
    return Font(name=FONT, size=size, bold=bold, italic=italic)


def _header(ws, title: str, unit: str, last_col: int, lines: list[str]) -> int:
    lc = get_column_letter(last_col)
    mid = max(4, last_col // 2 + 1)
    ws.merge_cells(f"A1:{get_column_letter(mid - 1)}1")
    ws["A1"] = "TRƯỜNG ĐẠI HỌC SƯ PHẠM KỸ THUẬT\nTHÀNH PHỐ HỒ CHÍ MINH"
    ws.merge_cells(f"A2:{get_column_letter(mid - 1)}2")
    ws["A2"] = unit.upper()
    ws.merge_cells(f"{get_column_letter(mid)}1:{lc}1")
    ws[f"{get_column_letter(mid)}1"] = "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập – Tự do – Hạnh phúc"
    ws.merge_cells(f"{get_column_letter(mid)}3:{lc}3")
    d = date.today()
    ws[f"{get_column_letter(mid)}3"] = f"TP. Hồ Chí Minh, ngày {d.day} tháng {d.month} năm {d.year}"
    for c in ("A1", "A2", f"{get_column_letter(mid)}1"):
        ws[c].font = _f(True); ws[c].alignment = CENTER
    ws[f"{get_column_letter(mid)}3"].font = _f(italic=True); ws[f"{get_column_letter(mid)}3"].alignment = CENTER
    ws.row_dimensions[1].height = 32
    ws.merge_cells(f"A5:{lc}5")
    ws["A5"] = title; ws["A5"].font = _f(True, 13); ws["A5"].alignment = CENTER
    r = 6
    for line in lines:
        ws.merge_cells(f"A{r}:{lc}{r}")
        ws[f"A{r}"] = line; ws[f"A{r}"].font = _f(line.startswith("Kết luận"))
        r += 1
    return r + 1


def _table(ws, row: int, headers: list[str], rows: list[list], widths: list[int] | None = None) -> int:
    for j, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=j, value=h)
        c.font = _f(True); c.alignment = CENTER; c.border = BOX; c.fill = HEAD_FILL
    for i, r in enumerate(rows, row + 1):
        for j, v in enumerate(r, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.font = _f(); c.border = BOX
            c.alignment = CENTER if j != 2 else WRAP
            if isinstance(v, str) and v.startswith("=") and ("/" in v) and j >= 3:
                c.number_format = "0.00%"
            if isinstance(v, float) and v <= 1 and j >= 3:
                c.number_format = "0%"
    if widths:
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w
    return row + len(rows) + 1


def _narratives(ws, row: int, last_col: int, items: list[tuple[str, str | None]], signer: str) -> None:
    lc = get_column_letter(last_col)
    row += 1
    for title, body in items:
        ws.merge_cells(f"A{row}:{lc}{row}"); ws[f"A{row}"] = title; ws[f"A{row}"].font = _f(True)
        row += 1
        ws.merge_cells(f"A{row}:{lc}{row}"); ws[f"A{row}"] = body or ""; ws[f"A{row}"].font = _f(italic=not body)
        ws[f"A{row}"].alignment = WRAP; ws.row_dimensions[row].height = 45
        row += 2
    ws.merge_cells(f"{get_column_letter(max(2, last_col - 3))}{row + 1}:{lc}{row + 1}")
    c = ws[f"{get_column_letter(max(2, last_col - 3))}{row + 1}"]
    c.value = f"{signer}\n(Ký, ghi rõ Họ và Tên)"; c.font = _f(True); c.alignment = CENTER
    ws.row_dimensions[row + 1].height = 32


def _pct(x) -> float:
    return round(float(x) / 100, 4)


# =====================================================================================  BM6


def _print_setup(wb) -> None:
    """In ngang A4, vừa 1 trang bề ngang – giống cách trình bày biểu mẫu nộp đơn vị."""
    for ws in wb.worksheets:
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_options.horizontalCentered = True
        ws.page_margins.left = ws.page_margins.right = 0.4


def build_bm6(db: Session, cs_id: int) -> bytes:
    cs = db.execute(text("""SELECT cs.id, cs.section_code, co.id AS course_id, co.course_code, co.course_name, co.clo_target_pct,
                                   s.id AS semester_id, s.name AS sem_name, s.academic_year, l.full_name AS lecturer, l.department
                            FROM class_sections cs JOIN courses co ON co.id = cs.course_id
                            JOIN semesters s ON s.id = cs.semester_id JOIN lecturers l ON l.id = cs.lecturer_id
                            WHERE cs.id = :cs"""), {"cs": cs_id}).mappings().one()
    unit = cs["department"] or "Bộ môn"
    course_line = f"Tên môn học: {cs['course_name']} ({cs['course_code']}) – Lớp HP: {cs['section_code']} – {cs['sem_name']} – GV: {cs['lecturer']}"
    clos = db.execute(text("""SELECT c.id, c.clo_code, c.description, p.assessments_text, p.evidence_type, p.method, p.cycle,
                                     COALESCE(p.pass_threshold_pct, :thr0) AS thr, COALESCE(p.target_pct, :t) AS target
                              FROM clos c LEFT JOIN clo_assessment_plans p ON p.clo_id = c.id AND p.semester_id = :s
                              WHERE c.course_id = :c ORDER BY c.clo_code"""),
                      {"c": cs["course_id"], "s": cs["semester_id"], "t": cs["clo_target_pct"], "thr0": settings.default_pass_threshold}).mappings().all()
    ev_name = {"process": "Quá trình", "final": "Cuối kỳ", "any": "Quá trình + Cuối kỳ", None: ""}
    wb = Workbook()
    # ---------------- BM6a
    ws = wb.active; ws.title = "BM6a_KH CĐR môn học"
    r = _header(ws, "BẢNG KẾ HOẠCH KIỂM TRA, ĐÁNH GIÁ MỨC ĐỘ ĐẠT CHO TỪNG CHUẨN ĐẦU RA MÔN HỌC", unit, 8,
                [course_line, f"Chỉ tiêu đạt CĐR môn học: {float(cs['clo_target_pct']):.0f}%"])
    rows = [[i, f"{c['clo_code']}: {c['description']}", c["assessments_text"] or "", ev_name[c["evidence_type"]],
             c["method"] or "", c["cycle"] or "", cs["sem_name"], _pct(c["target"])] for i, c in enumerate(clos, 1)]
    rows.append(["", "CHỈ TIÊU MONG MUỐN ĐẠT CĐR MÔN HỌC", "", "", "", "", "", _pct(cs["clo_target_pct"])])
    r = _table(ws, r, ["STT", "Nội dung CĐR môn học", "Các bài KT có CĐR xuất hiện", "Bài KT sẽ lấy minh chứng",
                       "Phương pháp kiểm tra, đánh giá", "Chu kỳ lấy minh chứng", "Thời gian lấy minh chứng", "Chỉ tiêu mong muốn"],
               rows, [6, 48, 18, 16, 18, 14, 14, 12])
    # ---------------- BM6b
    res = {x["clo_id"]: x for x in db.execute(text("SELECT * FROM clo_results WHERE class_section_id = :cs"), {"cs": cs_id}).mappings()}
    tot_ok = sum(x["n_achieved"] for x in res.values()); tot_n = sum(x["n_evaluated"] for x in res.values())
    overall = (100 * tot_ok / tot_n) if tot_n else 0
    concl = "Đạt" if tot_n and overall + 1e-9 >= float(cs["clo_target_pct"]) else "Không đạt"
    ws = wb.create_sheet("BM6b_KQ CĐR môn học")
    r = _header(ws, "KẾT QUẢ TỔNG HỢP CỦA TỪNG CHUẨN ĐẦU RA MÔN HỌC", unit, 8,
                [course_line, f"Chỉ tiêu đạt CĐR môn học: {float(cs['clo_target_pct']):.0f}%", f"Kết luận: {concl}"])
    rows, first = [], r + 1
    for i, c in enumerate(clos, 1):
        x = res.get(c["id"])
        rr = first + i - 1
        if x:
            rows.append([i, f"{c['clo_code']}: {c['description']}", "Câu hỏi và đáp án", x["n_achieved"], x["n_evaluated"],
                         f"=D{rr}/E{rr}", _pct(x["target_pct"]), "Đạt" if x["is_achieved"] else "Không đạt"])
        else:
            rows.append([i, f"{c['clo_code']}: {c['description']}", "Câu hỏi và đáp án", "", "", "", _pct(c["target"]), "Chưa đo"])
    last = first + len(clos) - 1
    rows.append(["", "KẾT QUẢ ĐẠT ĐƯỢC CĐR MÔN HỌC", "", f"=SUM(D{first}:D{last})", f"=SUM(E{first}:E{last})",
                 f"=IF(E{last + 1}>0,D{last + 1}/E{last + 1},0)", _pct(cs["clo_target_pct"]), concl])
    r = _table(ws, r, ["STT", "Nội dung CĐR môn học", "Công cụ kiểm tra, đánh giá", "Tổng số SV đạt yêu cầu",
                       "Tổng số SV đánh giá", "Tỷ lệ % đạt yêu cầu", "Chỉ tiêu mong muốn", "Kết quả đạt được"],
               rows, [6, 48, 18, 14, 14, 14, 12, 14])
    notes = "\n".join(f"{c['clo_code']}: {res[c['id']]['analysis']}" for c in clos if c["id"] in res and res[c["id"]]["analysis"])
    impr = "\n".join(f"{c['clo_code']}: {res[c['id']]['improvement']}" for c in clos if c["id"] in res and res[c["id"]]["improvement"])
    _narratives(ws, r, 8, [
        ("Tổng hợp dữ liệu đã đánh giá cho CĐR này",
         f"Tổng hợp từ {tot_n} lượt SV được đánh giá trên các bài KT lấy minh chứng; {tot_ok} lượt đạt ({overall:.2f}%). "
         "Mỗi CLO: SV đạt khi điểm các câu hỏi của CLO ≥ ngưỡng % điểm tối đa (xem các sheet BM6c)."),
        ("Đánh giá kết quả của số liệu tổng hợp", notes or None),
        ("Những hành động cải tiến", impr or None),
        ("Kết quả của các cải tiến đã thực hiện", None),
        ("Công cụ đánh giá", "Bài KT trắc nghiệm (Moodle / giấy) – dữ liệu từng câu lưu trong hệ thống; đáp án và ma trận câu hỏi – CLO đính kèm."),
    ], "TRƯỞNG ĐƠN VỊ")
    # ---------------- BM6c / BM6d cho từng CLO
    exams = db.execute(text("""SELECT id, exam_title, assessment_type FROM exams
                               WHERE class_section_id = :cs AND status = 'Analyzed' ORDER BY id"""), {"cs": cs_id}).mappings().all()
    for c in clos:
        ev = c["evidence_type"] or "any"
        ex_list = [e for e in exams if ev == "any" or e["assessment_type"] == ev]
        data = []
        for e in ex_list:
            pts = db.execute(text("""SELECT r.score_earned, r.score_max, a.total_score, ex.max_score,
                                            (SELECT SUM(points) FROM exam_questions WHERE exam_id = ex.id) AS raw_max
                                     FROM attempt_clo_results r JOIN exam_attempts a ON a.id = r.attempt_id
                                     JOIN exams ex ON ex.id = a.exam_id
                                     WHERE a.exam_id = :e AND r.clo_id = :c ORDER BY a.id"""), {"e": e["id"], "c": c["id"]}).mappings().all()
            if pts:
                data.append((e, pts))
        sheet = f"BM6{'d' if len(data) > 1 else 'c'}_{c['clo_code']}"[:31]
        ws = wb.create_sheet(sheet)
        thr = float(c["thr"])
        r0 = _header(ws, "BẢNG MINH CHỨNG ĐO LƯỜNG TỪ KẾT QUẢ KIỂM TRA, ĐÁNH GIÁ", unit, max(7, 4 * len(data) - 1), [
            f"CĐR: {c['clo_code']} – {c['description']}",
            f"Chỉ tiêu: {float(c['target']):.0f}% SV đạt được {thr:.0f}% điểm tối đa của các câu hỏi kiểm tra có liên quan",
            f"Môn học lấy mẫu: {cs['course_name']} ({cs['course_code']})",
            "Bài kiểm tra lấy mẫu: " + ("; ".join(e["exam_title"] for e, _ in data) or "(chưa có)"),
            f"Năm học, HK lấy mẫu: {cs['sem_name']}",
            f"Kết luận: {'Đạt' if res.get(c['id']) and res[c['id']]['is_achieved'] else ('Không đạt' if res.get(c['id']) else 'Chưa đo')}"])
        if not data:
            continue
        top = r0
        count_rows, n_cells, ok_cells = [], [], []
        for k, (e, pts) in enumerate(data):
            col = 1 + 4 * k
            L = lambda j: get_column_letter(col + j)
            ws.merge_cells(f"{L(0)}{top}:{L(2)}{top}")
            ws[f"{L(0)}{top}"] = f"Bài KT {k + 1}: {e['exam_title']}"; ws[f"{L(0)}{top}"].font = _f(True)
            for j, h in enumerate(["TT", "Điểm câu hỏi", "Điểm bài thi/KT"]):
                cell = ws.cell(row=top + 1, column=col + j, value=h); cell.font = _f(True); cell.border = BOX; cell.alignment = CENTER; cell.fill = HEAD_FILL
            qmax = float(pts[0]["score_max"])
            emax = float(pts[0]["max_score"])
            ws.cell(row=top + 2, column=col + 1, value=f"Điểm tối đa: {qmax:g}").font = _f(italic=True)
            ws.cell(row=top + 2, column=col + 2, value=f"Điểm tối đa: {emax:g}").font = _f(italic=True)
            for i, p in enumerate(pts, 1):
                rr = top + 2 + i
                raw_max = float(p["raw_max"]) or 1
                vals = [i, float(p["score_earned"]), round(float(p["total_score"]) * emax / raw_max, 2)]
                for j, v in enumerate(vals):
                    cell = ws.cell(row=rr, column=col + j, value=v); cell.font = _f(); cell.border = BOX; cell.alignment = CENTER
            end = top + 2 + len(pts)
            cut = round(qmax * thr / 100, 4)
            ws.cell(row=end + 1, column=col + 1, value=f'=COUNTIF({L(1)}{top + 3}:{L(1)}{end},">={cut}")').font = _f(True)
            ws.cell(row=end + 2, column=col + 1, value=f"={L(1)}{end + 1}/{L(0)}{end}").number_format = "0.00%"
            labels = [("Tổng số SV thực hiện bài KT", f"={L(0)}{end}"), ("Tổng số SV đạt bài KT", f"={L(1)}{end + 1}"),
                      ("Tỷ lệ % đạt", f"={L(1)}{end + 2}")]
            count_rows.append((col, end))
            n_cells.append(f"{L(0)}{end}"); ok_cells.append(f"{L(1)}{end + 1}")
        base = max(end for _, end in count_rows) + 4
        for k, (col, end) in enumerate(count_rows):
            L = lambda j: get_column_letter(col + j)
            for i, (lab, f) in enumerate([("Tổng số SV thực hiện bài KT%d" % (k + 1), f"={L(0)}{end}"),
                                          ("Tổng số SV đạt bài KT%d" % (k + 1), f"={L(1)}{end + 1}"),
                                          ("Tỷ lệ %% đạt KT%d" % (k + 1), f"={L(1)}{end + 2}")]):
                ws.merge_cells(f"{L(0)}{base + i}:{L(1)}{base + i}")
                ws[f"{L(0)}{base + i}"] = lab; ws[f"{L(0)}{base + i}"].font = _f()
                ws[f"{L(2)}{base + i}"] = f; ws[f"{L(2)}{base + i}"].font = _f(True)
                if i == 2:
                    ws[f"{L(2)}{base + i}"].number_format = "0.00%"
        b = base + 4
        ws[f"A{b}"] = "Tổng kết cho CĐR"; ws[f"A{b}"].font = _f(True)
        ws[f"A{b + 1}"] = "Tổng số SV tham gia đánh giá:"; ws[f"A{b + 2}"] = "=" + "+".join(n_cells)
        ws[f"A{b + 3}"] = f"Tổng số SV đạt của {c['clo_code']}:"; ws[f"A{b + 4}"] = "=" + "+".join(ok_cells)
        ws[f"A{b + 5}"] = "Tỷ lệ %:"; ws[f"A{b + 6}"] = f"=A{b + 4}/A{b + 2}"; ws[f"A{b + 6}"].number_format = "0.00%"
        for rr in range(b + 1, b + 7):
            ws[f"A{rr}"].font = _f(rr % 2 == 0)
        for j in range(1, 4 * len(data)):
            ws.column_dimensions[get_column_letter(j)].width = 16
    _print_setup(wb)
    bio = io.BytesIO(); wb.save(bio)
    return bio.getvalue()


# =====================================================================================  BM2 / BM3


def build_bm3(db: Session, program_id: int, academic_year: str) -> bytes:
    prog = db.execute(text("SELECT * FROM programs WHERE id = :p"), {"p": program_id}).mappings().one()
    unit = prog["department"] or "Bộ môn"
    plos = db.execute(text("SELECT * FROM plos WHERE program_id = :p ORDER BY plo_code"), {"p": program_id}).mappings().all()
    wb = Workbook()
    ws = wb.active; ws.title = "BM2_TongHop"
    res = {x["plo_id"]: x for x in db.execute(text("SELECT * FROM plo_results WHERE academic_year = :y"), {"y": academic_year}).mappings()}
    r = _header(ws, f"BÁO CÁO TỔNG KẾT\nV/v triển khai đo lường mức độ đạt được chuẩn đầu ra CTĐT {prog['name']} năm học {academic_year}",
                unit, 8, [f"Tên CTĐT: {prog['name']} ({prog['code']}) – Chỉ tiêu đạt CĐR CTĐT: {float(prog['target_pct']):.0f}%"])
    ws.row_dimensions[5].height = 36
    rows, first = [], r + 1
    for i, p in enumerate(plos):
        x = res.get(p["id"])
        rows.append([p["plo_code"], p["description"], x["n_achieved"] if x else "", x["n_evaluated"] if x else "",
                     f"=IF(D{first + i}>0,C{first + i}/D{first + i},\"\")" if x else "", _pct(x["target_pct"] if x else p["target_pct"]),
                     ("Đạt" if x["is_achieved"] else "Không đạt") if x else "Chưa đo", academic_year if x else ""])
    last = first + len(plos) - 1
    tot_ok = sum(x["n_achieved"] for x in res.values() if x["plo_id"] in {p["id"] for p in plos})
    tot_n = sum(x["n_evaluated"] for x in res.values() if x["plo_id"] in {p["id"] for p in plos})
    overall = "Đạt" if tot_n and 100 * tot_ok / tot_n + 1e-9 >= float(prog["target_pct"]) else ("Không đạt" if tot_n else "Chưa đo")
    rows.append(["", "KẾT QUẢ ĐẠT ĐƯỢC CĐR CTĐT", f"=SUM(C{first}:C{last})", f"=SUM(D{first}:D{last})",
                 f"=IF(D{last + 1}>0,C{last + 1}/D{last + 1},0)", _pct(prog["target_pct"]), overall, ""])
    r = _table(ws, r, ["CĐR", "Nội dung của CĐR CTĐT", "Tổng số SV đã đạt", "Tổng số SV đã khảo sát", "Tỷ lệ % đã đạt",
                       "Chỉ tiêu", "Kết quả", "Năm học đo lường"], rows, [8, 55, 12, 14, 12, 10, 12, 14])
    weak = [p for p in plos if res.get(p["id"]) and not res[p["id"]]["is_achieved"]]
    lowest = sorted([p for p in plos if res.get(p["id"])], key=lambda p: float(res[p["id"]]["achieved_pct"]))[:2]
    _narratives(ws, r, 8, [
        (f"Nhận xét chung về kết quả đạt được trong năm học {academic_year}",
         f"Đã đo {len(res)} CĐR; {tot_ok}/{tot_n} lượt SV đạt. CĐR không đạt: " + (", ".join(p["plo_code"] for p in weak) or "không có") + "."),
        ("Đề xuất giải pháp cải tiến (CĐR không đạt và hai CĐR có tỷ lệ đạt thấp nhất)",
         "Hai CĐR có tỷ lệ đạt thấp nhất: " + (", ".join(f"{p['plo_code']} ({float(res[p['id']]['achieved_pct']):.1f}%)" for p in lowest) or "—")),
        ("Nhận xét và góp ý của Trưởng đơn vị", None),
    ], "TRƯỞNG BỘ MÔN")

    for p in plos:
        plans = db.execute(text("""
            SELECT pl.id, pi.pi_code, pi.description, co.course_name, s.name AS sem, pl.method, pl.cycle, pl.target_pct,
                   l.full_name AS lecturer,
                   (SELECT GROUP_CONCAT(c2.course_name SEPARATOR ', ') FROM pi_courses pc JOIN courses c2 ON c2.id = pc.course_id
                     WHERE pc.pi_id = pi.id) AS courses_text,
                   r.n_evaluated, r.n_achieved, r.is_achieved
            FROM performance_indicators pi
            LEFT JOIN pi_assessment_plans pl ON pl.pi_id = pi.id
                 AND pl.semester_id IN (SELECT id FROM semesters WHERE academic_year = :y)
            LEFT JOIN courses co ON co.id = pl.course_id
            LEFT JOIN semesters s ON s.id = pl.semester_id
            LEFT JOIN lecturers l ON l.id = pl.lecturer_id
            LEFT JOIN pi_results r ON r.plan_id = pl.id
            WHERE pi.plo_id = :plo ORDER BY pi.pi_code"""), {"plo": p["id"], "y": academic_year}).mappings().all()
        if not any(x["id"] for x in plans):
            continue
        x = res.get(p["id"])
        ws = wb.create_sheet(f"BM3b_{p['plo_code']}")
        r = _header(ws, "BẢNG KẾ HOẠCH KIỂM TRA, ĐÁNH GIÁ MỨC ĐỘ ĐẠT CHO TỪNG CHUẨN ĐẦU RA CTĐT", unit, 9,
                    [f"Tên CTĐT: {prog['name']}", f"CĐR {p['plo_code']} - {p['description']}", f"Chỉ tiêu đạt CĐR: {float(p['target_pct']):.0f} %"])
        rows = [[q["pi_code"], q["description"], q["courses_text"] or "", q["course_name"] or "", q["method"] or "", q["cycle"] or "",
                 q["sem"] or "", _pct(q["target_pct"]) if q["target_pct"] is not None else "", q["lecturer"] or ""] for q in plans]
        rows.append([f"CĐR {p['plo_code']}", "CHỈ TIÊU MONG MUỐN CỦA CHUẨN ĐẦU RA", "", "", "", "", "", _pct(p["target_pct"]), ""])
        r = _table(ws, r, ["TT", "Performance indicator (PI) cho CĐR này", "Các môn học có PI xuất hiện", "Môn học sẽ lấy minh chứng",
                           "Phương pháp kiểm tra, đánh giá", "Chu kỳ lấy minh chứng", "Thời gian lấy minh chứng", "Chỉ tiêu mong muốn",
                           "GV phụ trách"], rows, [8, 45, 26, 20, 20, 12, 12, 10, 18])
        pr = db.execute(text("SELECT * FROM plo_results WHERE plo_id=:p AND academic_year=:y"), {"p": p["id"], "y": academic_year}).mappings().first()
        _narratives(ws, r, 9, [
            ("Tổng hợp dữ liệu đã đánh giá cho CĐR này (bao gồm tất cả các PIs)", pr["data_summary"] if pr else None),
            ("Đánh giá kết quả của số liệu tổng hợp", pr["analysis"] if pr else None),
            ("Những hành động cải tiến", pr["improvement_actions"] if pr else None),
            ("Kết quả của các cải tiến đã thực hiện", pr["improvement_results"] if pr else None),
            ("Công cụ đánh giá", pr["evidence_tools"] if pr else None)], "TRƯỞNG ĐƠN VỊ")
        ws = wb.create_sheet(f"BM3c_{p['plo_code']}")
        r = _header(ws, "KẾT QUẢ TỔNG HỢP CỦA TỪNG PI CHO CHUẨN ĐẦU RA", unit, 8,
                    [f"Tên CTĐT: {prog['name']}", f"CĐR {p['plo_code']} - {p['description']}", f"Chỉ tiêu đạt CĐR: {float(p['target_pct']):.0f} %"])
        rows, first = [], r + 1
        measured = [q for q in plans if q["n_evaluated"]]
        for i, q in enumerate(measured):
            rows.append([q["pi_code"], q["description"], q["method"], q["n_achieved"], q["n_evaluated"], f"=D{first + i}/E{first + i}",
                         _pct(q["target_pct"]), "Đạt" if q["is_achieved"] else "Không đạt"])
        last = first + len(measured) - 1
        rows.append([f"CĐR {p['plo_code']}", "KẾT QUẢ ĐẠT ĐƯỢC CỦA CĐR", "", f"=SUM(D{first}:D{last})" if measured else 0,
                     f"=SUM(E{first}:E{last})" if measured else 0, f"=IF(E{last + 1}>0,D{last + 1}/E{last + 1},0)",
                     _pct(x["target_pct"] if x else p["target_pct"]), ("Đạt" if x["is_achieved"] else "Không đạt") if x else "Chưa đo"])
        r = _table(ws, r, ["TT", "Performance indicator (PI) cho CĐR này", "Phương pháp/ Công cụ đánh giá", "SL SV đạt yêu cầu",
                           "Tổng số SV đánh giá", "Tỷ lệ % đạt yêu cầu", "Chỉ tiêu mong muốn", "Kết quả đạt được"],
                   rows, [10, 45, 22, 12, 12, 12, 12, 12])
    _print_setup(wb)
    bio = io.BytesIO(); wb.save(bio)
    return bio.getvalue()
