"""Xuất đề cương chi tiết học phần ra PDF theo mẫu đề cương của Trường (15 mục: tên môn học, mô tả, mục tiêu, chuẩn đầu ra,
nội dung chi tiết, đánh giá, tài liệu, phê duyệt, tiến trình cập nhật) để in và ký – không phải ảnh chụp trang web."""
import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle

from .paper import fonts, para

SCHOOL = "TRƯỜNG ĐẠI HỌC<br/>CÔNG NGHỆ KỸ THUẬT TP. HỒ CHÍ MINH"
FACULTY = "KHOA CÔNG NGHỆ THÔNG TIN"
HEAD_BG = colors.HexColor("#FFF2A8")      # nền tiêu đề bảng giống mẫu đề cương
HEAD_FG = "#1F3FBF"
ETHICS = ("Các bài tập ở nhà và dự án phải được thực hiện từ chính bản thân sinh viên. Nếu bị phát hiện có sao chép thì xử lý các sinh viên "
          "có liên quan bằng hình thức đánh giá 0 (không) điểm quá trình và cuối kỳ.")


def build(s: dict) -> bytes:
    F = fonts(); R, B, I = F["serif"], F["serifB"], F["serifI"]
    BI = R + "BI"
    d = s.get("doc") or {}
    mk = lambda n, **k: ParagraphStyle(n, fontName=k.pop("fontName", R), fontSize=k.pop("fontSize", 11), leading=k.pop("leading", 14.5), **k)
    body = mk("b", alignment=TA_JUSTIFY)
    item = mk("i", fontName=B, spaceBefore=5, spaceAfter=2, keepWithNext=1)
    ind = mk("ind", leftIndent=14 * mm)
    cell, cellc = mk("c", fontSize=10, leading=12.2), mk("cc", fontSize=10, leading=12.2, alignment=TA_CENTER)
    th = mk("th", fontName=B, fontSize=10, leading=12.2, alignment=TA_CENTER, textColor=colors.HexColor(HEAD_FG))
    hdr_l, hdr_r = mk("hl", fontSize=10, leading=13, alignment=TA_CENTER), mk("hr", fontName=B, fontSize=10, leading=13)
    P = lambda t, st=cell: Paragraph(para(str(t if t not in (None, "") else "")), st)
    story = []

    progs = s["programs"]
    pnames = ", ".join(dict.fromkeys(p["name"] for p in progs)) or "—"
    top = Table([[Paragraph(f"{SCHOOL}<br/>{FACULTY}", hdr_l),
                  Paragraph(para(f"Ngành đào tạo: {progs[0]['name'] if progs else '—'}") + "<br/>Trình độ đào tạo: Đại học<br/>"
                            + para(f"Chương trình đào tạo: {pnames}"), hdr_r)]], colWidths=[84 * mm, 86 * mm])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [top, Spacer(1, 8), Paragraph("Đề Cương Chi Tiết Học Phần", mk("t", fontName=BI, fontSize=20, leading=26, alignment=TA_CENTER)), Spacer(1, 8)]

    def tbl(rows, widths, repeat=1):
        t = Table(rows, colWidths=[w * mm for w in widths], repeatRows=repeat)
        sty = [("GRID", (0, 0), (-1, -1), .5, colors.black), ("VALIGN", (0, 0), (-1, -1), "TOP"),
               ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
        if repeat:
            sty += [("BACKGROUND", (0, 0), (-1, 0), HEAD_BG), ("VALIGN", (0, 0), (-1, 0), "MIDDLE")]
        t.setStyle(TableStyle(sty)); return t

    H = lambda *c: [Paragraph(x, th) for x in c]
    PL = lambda lines, st=cellc: Paragraph("<br/>".join(para(str(x)) for x in lines) or "—", st)
    outl = s["outlines"]
    lt = sum(float(o.get("theory_hours") or 0) for o in outl); thh = sum(float(o.get("practice_hours") or 0) for o in outl)
    credit = f"{s['credits']} tín chỉ"
    if s.get("credits_theory") is not None or s.get("credits_practice") is not None:
        credit += f" ({s.get('credits_theory') or 0} tín chỉ lý thuyết, {s.get('credits_practice') or 0} tín chỉ thực hành/thí nghiệm)"
    dist = f"{lt:g} tiết lý thuyết + {thh:g} tiết thực hành" + (f" + {d['self_study_hours']} tiết tự học" if d.get("self_study_hours") is not None else "")

    story.append(Paragraph(f"<b>1.  Tên môn học:</b> {para(s['course_name'])} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <b>Mã môn học:</b> {para(s['course_code'])}", body))
    story.append(Paragraph(f"<b>2.  Tên Tiếng Anh:</b> {para(d.get('english_name') or '—')}", body))
    story.append(Paragraph(f"<b>3.  Số tín chỉ:</b> {para(credit)}" + (f" – cấu trúc {para(s['course_structure'])}" if s.get("course_structure") else ""), body))
    story.append(Paragraph(f"Phân bố thời gian: {para(dist)}", ind))
    story.append(Paragraph("<b>4.  Các giảng viên phụ trách môn học:</b>", body))
    lecs = s.get("lecturers") or []
    for i, n in enumerate(lecs, 1):
        story.append(Paragraph(para(f"{i}/ {n}"), ind))
    if not lecs:
        story.append(Paragraph("—", ind))
    story.append(Paragraph("<b>5.  Điều kiện tham gia học môn học</b>", body))
    pre = ", ".join(f"{p['course_name'] or ''} ({p['course_code']})" if p.get("course_name") else p["course_code"] for p in s["prerequisite_list"])
    story.append(Paragraph(para(f"Môn tiên quyết: {pre or 'Không'}"), ind))
    story.append(Paragraph("<b>6.  Mô tả môn học</b> (Course Description)", body))
    story.append(Paragraph(para(s.get("description") or "—"), body))

    story.append(Paragraph("<b>7.  Mục tiêu môn học</b> (Course Goals)", item))
    story.append(Paragraph(para(d.get("objectives") or "—"), body))

    story.append(Paragraph("<b>8.  Chuẩn đầu ra của môn học</b>", item))
    rows = [H("Chuẩn đầu ra MH", "Mô tả<br/>(Sau khi học xong môn học này, người học có thể:)", "Chuẩn đầu ra CTĐT (PLO/PI)", "Trình độ năng lực")]
    for c in s["clos"]:
        pis = [f"{p['plo_code']}({p['pi_code']}) – {p['level']}" for p in c.get("pis", [])] or [f"{p['plo_code']} – {p['level']}" for p in c.get("plos", [])]
        rows.append([Paragraph(f"<b>{para(c['clo_code'])}</b>", cellc), P(c["description"]), PL(pis), P(c.get("bloom") or "—", cellc)])
    story.append(tbl(rows, [22, 80, 46, 22]) if s["clos"] else Paragraph("Chưa khai báo chuẩn đầu ra.", body))

    story.append(Paragraph("<b>9.  Đạo đức khoa học:</b>", item))
    story.append(Paragraph(ETHICS, mk("e", alignment=TA_JUSTIFY, firstLineIndent=10 * mm)))

    story.append(Paragraph("<b>10.  Nội dung chi tiết môn học:</b>", item))
    if outl:
        rows = [H("Chương", "Nội dung", "Chuẩn đầu ra môn học", "Số tiết<br/>LT / TH", "Phương pháp dạy học")]
        for o in outl:
            content = f"<b>Chương {o['chapter_number']}: {para(o['chapter_name']).upper()}</b>"
            if o.get("content"):
                content += "<br/>" + "<br/>".join("- " + para(x.strip().lstrip('-+•* ')) for x in o["content"].splitlines() if x.strip())
            rows.append([P(o["chapter_number"], cellc), Paragraph(content, cell), PL([x["clo_code"] for x in o["clos"]]),
                         P(f"{o['theory_hours'] if o.get('theory_hours') is not None else '—'} / {o['practice_hours'] if o.get('practice_hours') is not None else '—'}", cellc),
                         P(o.get("teaching_activities") or (d.get("teaching_methods") or "").split("\n")[0][:80] or "—", cellc)])
        rows.append([P(""), Paragraph("<b>Tổng số tiết</b>", cell), P(""), Paragraph(f"<b>{lt:g} / {thh:g}</b>", cellc), P("")])
        story.append(tbl(rows, [18, 80, 24, 18, 30]))
    else:
        story.append(Paragraph("Chưa khai báo nội dung chi tiết.", body))
    if d.get("teaching_methods"):
        story += [Spacer(1, 3), Paragraph("<b>Phương pháp giảng dạy – học tập:</b> " + para(d["teaching_methods"]), body)]

    story.append(Paragraph("<b>11.  Đánh giá kết quả học tập:</b>", item))
    story.append(Paragraph("- Thang điểm: <b>10</b>", ind)); story.append(Paragraph("- Kế hoạch kiểm tra như sau:", ind)); story.append(Spacer(1, 3))
    asm = d.get("assessments") or []
    if asm:
        rows = [H("Hình thức KT", "Nội dung", "Thời điểm", "Chuẩn đầu ra đánh giá", "Phương pháp đánh giá", "Tỉ lệ (%)")]
        for a in asm:
            rows.append([P(a["component_code"], cellc), P(a["name"]), P(a.get("timing") or "—", cellc), PL([x["clo_code"] for x in a["clos"]]),
                         P(a.get("method") or "—", cellc), P(f"{a['weight_pct']:g}", cellc)])
        rows.append([P(""), Paragraph("<b>Tổng</b>", cell), P(""), P(""), P(""), Paragraph(f"<b>{sum(a['weight_pct'] for a in asm):g}</b>", cellc)])
        story.append(tbl(rows, [20, 52, 22, 28, 28, 20]))
        story.append(Spacer(1, 6))
        codes = [a["component_code"] for a in asm]
        w = 14.0
        rows = [H("CĐR môn học", *codes)]
        rows[0] = [Paragraph("CĐR<br/>môn học", th)] + [Paragraph(para(c), th) for c in codes]
        for c in s["clos"]:
            rows.append([Paragraph(f"<b>{para(c['clo_code'])}</b>", cellc)] + [P("x" if any(x["id"] == c["id"] for x in a["clos"]) else "", cellc) for a in asm])
        story.append(tbl(rows, [26] + [min(w, (144 / max(len(codes), 1)))] * len(codes)))
    else:
        story.append(Paragraph("Chưa có kế hoạch đánh giá học phần.", body))

    story.append(Paragraph("<b>12.  Tài liệu học tập</b>", item))
    refs = [r for t in ("main", "extra") for r in d.get("references", []) if r["ref_type"] == t]
    for i, r in enumerate(refs, 1):
        story.append(Paragraph(para(f"{i}.  {r['citation']}"), mk("r", leftIndent=14 * mm, firstLineIndent=-5 * mm, alignment=TA_JUSTIFY)))
    if not refs:
        story.append(Paragraph("—", ind))
    if d.get("course_policy"):
        story += [Paragraph("<b>Quy định của học phần:</b> " + para(d["course_policy"]), body)]

    vers = s.get("versions") or []
    first = next((v for v in vers if v.get("approved_at")), None)
    from datetime import datetime
    fmt = lambda x: datetime.fromisoformat(x).strftime("%d/%m/%Y") if x else "…/…/……"
    story.append(Paragraph(f"<b>13.  Ngày phê duyệt lần đầu:</b> {fmt(first['approved_at']) if first else '…/…/……'}", item))
    story.append(KeepTogether([Paragraph("<b>14.  Cấp phê duyệt:</b>", item), Spacer(1, 3),
                               Table([[Paragraph("<b>Trưởng khoa</b>", cellc), Paragraph("<b>Trưởng BM</b>", cellc), Paragraph("<b>Nhóm biên soạn</b>", cellc)]],
                                     colWidths=[56 * mm] * 3, rowHeights=[28 * mm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]))
    story.append(Paragraph("15.  Tiến trình cập nhật ĐCCT", item))
    rows = []
    for v in vers:
        rows.append([Paragraph(f"<b>Lần {v['version_no']}:</b> Nội dung cập nhật ĐCCT lần {v['version_no']}: ngày {fmt(v.get('approved_at')).replace('/', ' tháng ', 1).replace('/', ' năm ')}"
                               f" – {para(v['status_label'])}", cell),
                     Paragraph("&lt;người cập nhật ký và ghi rõ họ tên&gt;<br/><br/><br/>Tổ trưởng Bộ môn:", cell)])
    if not rows:
        rows = [[P("Lần 1: Nội dung cập nhật ĐCCT lần 1: ngày    tháng    năm"), P("<người cập nhật ký và ghi rõ họ tên>")]]
    story.append(tbl(rows, [112, 58], repeat=0))

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                          title=f"Đề cương chi tiết {s['course_code']}", author="Trường Đại học Công nghệ Kỹ thuật TP. Hồ Chí Minh")

    def footer(c, _):
        c.saveState(); c.setFont(R, 10); c.drawCentredString(105 * mm, 10 * mm, str(c.getPageNumber())); c.restoreState()
    doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")], onPage=footer)])
    doc.build(story)
    return buf.getvalue()
