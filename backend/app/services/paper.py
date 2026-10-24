"""Đề thi giấy do HỆ THỐNG sinh và chấm (không cần Moodle) – góp ý 15/10, tham khảo cách làm của TNMaker:

* Sinh nhiều mã đề: xáo trộn thứ tự câu và thứ tự phương án (mỗi câu 2–6 phương án tùy câu) → exam_versions,
  exam_version_questions, exam_version_options (Reverse Shuffle khi chấm).
* Xuất đề in (PDF, Word) một cột hoặc chia 2 cột trên một mặt giấy để tiết kiệm giấy; xuất đáp án từng mã đề.
* Phiếu trả lời có 4 ô định vị ở 4 góc, lưới tô MSSV và mã đề, mỗi câu đúng số ô bằng số phương án của câu;
  cùng một bộ tọa độ (sheet_layout) dùng để VẼ phiếu và để ĐỌC phiếu (services/omr.py).
"""
from __future__ import annotations

import html
import io
import math
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import Exam, ExamVersion, ExamVersionOption, ExamVersionQuestion

LABELS = "ABCDEFGHIJ"
FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
MM = 72 / 25.4            # 1 mm = 2.8346 pt
PAGE_W, PAGE_H = 210.0, 297.0


class PaperError(ValueError):
    pass


# ------------------------------------------------------------------ phông chữ (Times New Roman nếu máy có, nếu không DejaVu Serif)
_FONTS: dict | None = None


def fonts() -> dict:
    global _FONTS
    if _FONTS:
        return _FONTS
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.fonts import addMapping
    win = Path("C:/Windows/Fonts")
    cands = [("TNR", {"": win / "times.ttf", "B": win / "timesbd.ttf", "I": win / "timesi.ttf", "BI": win / "timesbi.ttf"}),
             ("DJS", {"": FONT_DIR / "DejaVuSerif.ttf", "B": FONT_DIR / "DejaVuSerif-Bold.ttf",
                      "I": FONT_DIR / "DejaVuSerif-Italic.ttf", "BI": FONT_DIR / "DejaVuSerif-BoldItalic.ttf"})]
    for name, files in cands:
        if all(p.exists() for p in files.values()):
            for k, p in files.items():
                pdfmetrics.registerFont(TTFont(name + k, str(p)))
            addMapping(name, 0, 0, name); addMapping(name, 1, 0, name + "B"); addMapping(name, 0, 1, name + "I"); addMapping(name, 1, 1, name + "BI")
            sans = "DJSANS"
            pdfmetrics.registerFont(TTFont(sans, str(FONT_DIR / "DejaVuSans.ttf")))
            pdfmetrics.registerFont(TTFont(sans + "B", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
            _FONTS = {"serif": name, "serifB": name + "B", "serifI": name + "I", "sans": sans, "sansB": sans + "B"}
            return _FONTS
    raise PaperError("Không tìm thấy phông chữ tiếng Việt để xuất PDF")


def plain(s: str) -> str:
    """Nội dung câu hỏi (có thể là HTML từ Moodle) -> văn bản thuần."""
    s = re.sub(r"<\s*br\s*/?>|</p>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def para(s: str) -> str:
    """Văn bản thuần -> markup an toàn cho Paragraph của ReportLab."""
    return html.escape(plain(s)).replace("\n", "<br/>")


# ------------------------------------------------------------------ mã đề
def generate_versions(db: Session, exam: Exam, n_versions: int, shuffle_questions: bool = True, shuffle_options: bool = True,
                      seed: int | None = None, first_code: int = 1) -> list[dict]:
    if exam.exam_type != "paper":
        raise PaperError("Chỉ bài thi giấy mới sinh mã đề")
    if exam.moodle_offlinequiz_id:
        raise PaperError("Bài đã tạo đề giấy trên Moodle (Offline Quiz) – mã đề do Moodle quản lý")
    if db.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e"), {"e": exam.id}).scalar():
        raise PaperError("Bài đã có kết quả chấm – không sinh lại mã đề được")
    qs = [eq.question for eq in exam.questions]
    if not qs:
        raise PaperError("Bài kiểm tra chưa có câu hỏi")
    if any(q.question_type != "multichoice" for q in qs):
        raise PaperError("Đề giấy chấm phiếu chỉ gồm câu trắc nghiệm")
    if any(not (2 <= len(q.options) <= 6) for q in qs):
        raise PaperError("Mỗi câu trên phiếu trả lời có từ 2 đến 6 phương án")
    rng = random.Random(seed if seed is not None else exam.id * 7919)
    exam.versions.clear(); db.flush()
    out = []
    for k in range(n_versions):
        code = f"{first_code + k:02d}"
        order = list(qs)
        if shuffle_questions and k > 0:
            rng.shuffle(order)
        v = ExamVersion(exam_id=exam.id, version_code=code)
        db.add(v); db.flush()
        for pos, q in enumerate(order, 1):
            vq = ExamVersionQuestion(version_id=v.id, question_id=q.id, position=pos)
            opts = sorted(q.options, key=lambda o: o.position)
            if shuffle_options and k > 0:
                opts = list(opts); rng.shuffle(opts)
            db.add(vq); db.flush()
            for i, o in enumerate(opts):
                db.add(ExamVersionOption(version_id=v.id, question_id=q.id, displayed_label=LABELS[i], option_id=o.id))
        out.append({"id": v.id, "version_code": code})
    db.flush()
    return out


def version_view(db: Session, version_id: int) -> list[dict]:
    """Câu hỏi của một mã đề theo thứ tự in, phương án theo nhãn in (A, B, …) và đáp án đúng."""
    rows = db.execute(text("""SELECT vq.position, q.id AS question_id, q.content, eq.points, vo.displayed_label, o.content AS opt, o.is_correct, o.id AS option_id
                              FROM exam_version_questions vq JOIN question_bank q ON q.id=vq.question_id
                              JOIN exam_versions v ON v.id=vq.version_id
                              JOIN exam_questions eq ON eq.exam_id=v.exam_id AND eq.question_id=q.id
                              JOIN exam_version_options vo ON vo.version_id=vq.version_id AND vo.question_id=vq.question_id
                              JOIN question_options o ON o.id=vo.option_id
                              WHERE vq.version_id=:v ORDER BY vq.position, vo.displayed_label"""), {"v": version_id}).mappings()
    out: dict[int, dict] = {}
    for r in rows:
        q = out.setdefault(r["position"], {"position": r["position"], "question_id": r["question_id"], "content": plain(r["content"]),
                                           "points": float(r["points"]), "options": [], "answer": None})
        q["options"].append({"label": r["displayed_label"], "content": plain(r["opt"]), "option_id": r["option_id"]})
        if r["is_correct"]:
            q["answer"] = r["displayed_label"]
    return [out[k] for k in sorted(out)]


def versions_data(db: Session, exam: Exam) -> list[dict]:
    return [{"id": v.id, "version_code": v.version_code, "questions": version_view(db, v.id)} for v in exam.versions]


# ------------------------------------------------------------------ bố cục phiếu trả lời (đơn vị mm, gốc tọa độ góc trên-trái)
@dataclass
class SheetOptions:
    title: str = "PHIẾU TRẢ LỜI TRẮC NGHIỆM"
    school: str = "TRƯỜNG ĐẠI HỌC CÔNG NGHỆ KỸ THUẬT TP. HỒ CHÍ MINH"
    subtitle: str = ""                      # VD: tên môn + mã môn
    exam_title: str = ""
    n_questions: int = 40
    options_per_question: list[int] = field(default_factory=list)   # số ô của từng câu (2–6); rỗng = 4
    student_digits: int = 8
    version_digits: int = 2
    version_codes: list[str] = field(default_factory=list)
    essay_lines: int = 0                    # số dòng phần tự luận / ghi chú cuối phiếu
    note: str = "Dùng bút chì hoặc bút mực đen tô kín một ô cho mỗi câu. Muốn đổi đáp án: tẩy sạch (bút chì) hoặc gạch chéo ô cũ và tô ô mới."


FID = 7.0                                  # cạnh ô định vị (mm)
FID_POS = [(10.0, 10.0), (PAGE_W - 10.0 - FID, 10.0), (PAGE_W - 10.0 - FID, PAGE_H - 10.0 - FID), (10.0, PAGE_H - 10.0 - FID)]   # TL, TR, BR, BL
R_BUBBLE = 2.15


def fid_centers() -> list[tuple[float, float]]:
    return [(x + FID / 2, y + FID / 2) for x, y in FID_POS]


def sheet_layout(o: SheetOptions) -> dict:
    n = o.n_questions
    if not 1 <= n <= 120:
        raise PaperError("Phiếu trả lời hỗ trợ 1–120 câu")
    opts = (o.options_per_question or [4] * n)[:n] + [4] * max(0, n - len(o.options_per_question or []))
    max_opt = max(opts)
    # khối định danh: MSSV + mã đề
    top = 58.0
    dx_digit, dy_digit = 5.2, 4.6
    sx = 16.0
    student = []
    for c in range(o.student_digits):
        for v in range(10):
            student.append({"col": c, "value": v, "x": sx + 3 + c * dx_digit, "y": top + 9.5 + v * dy_digit})
    vx = sx + 3 + o.student_digits * dx_digit + 10
    version = []
    for c in range(o.version_digits):
        for v in range(10):
            version.append({"col": c, "value": v, "x": vx + c * dx_digit, "y": top + 9.5 + v * dy_digit})
    id_bottom = top + 9.5 + 9 * dy_digit + 6
    # vùng trả lời
    ncols = 4 if max_opt <= 4 else 3
    if n <= 10:
        ncols = 1
    elif n <= 20:
        ncols = 2
    elif n <= 45 and max_opt > 4:
        ncols = 3
    rows_per_col = math.ceil(n / ncols)
    a_top = id_bottom + 8
    bottom_limit = PAGE_H - 20 - (o.essay_lines * 7 + 10 if o.essay_lines else 0)
    groups = math.ceil(rows_per_col / 5) - 1
    dy = min(6.8, (bottom_limit - a_top - 6 - groups * 1.6) / max(rows_per_col, 1))
    if dy < 4.6:
        raise PaperError("Quá nhiều câu cho một phiếu A4 – giảm số câu, số phương án hoặc bỏ phần tự luận")
    col_w = (PAGE_W - 30) / ncols
    dx_opt = min(6.4, (col_w - 10) / max_opt)
    answers = []
    for i in range(n):
        c, r = divmod(i, rows_per_col)
        y = a_top + 6 + r * dy + (r // 5) * 1.6
        x0 = 15 + c * col_w
        for j in range(opts[i]):
            answers.append({"q": i + 1, "label": LABELS[j], "x": x0 + 10 + j * dx_opt, "y": y})
    a_bottom = max(b["y"] for b in answers) + 5
    return {"options": opts, "student": student, "version": version, "answers": answers, "ncols": ncols, "rows_per_col": rows_per_col,
            "col_w": col_w, "dy": dy, "dx_opt": dx_opt, "top": top, "id_bottom": id_bottom, "a_top": a_top, "a_bottom": a_bottom,
            "sx": sx, "vx": vx, "dx_digit": dx_digit, "dy_digit": dy_digit, "r": R_BUBBLE, "fids": fid_centers()}


def sheet_options_for(db: Session, exam: Exam, **kw) -> SheetOptions:
    cs = exam.class_section
    vs = versions_data(db, exam) if exam.versions else []
    n = len(exam.questions)
    per = []
    for pos in range(1, n + 1):
        cnt = [len(v["questions"][pos - 1]["options"]) for v in vs if len(v["questions"]) >= pos]
        per.append(max(cnt) if cnt else len(sorted(exam.questions, key=lambda q: q.order_index)[pos - 1].question.options))
    o = SheetOptions(subtitle=f"{cs.course.course_name} ({cs.course.course_code}) – Lớp {cs.section_code}", exam_title=exam.exam_title,
                     n_questions=n, options_per_question=per, version_codes=[v["version_code"] for v in vs])
    for k, v in kw.items():
        if v is not None and hasattr(o, k):
            setattr(o, k, v)
    if o.version_codes and max(len(c) for c in o.version_codes) > o.version_digits:
        o.version_digits = max(len(c) for c in o.version_codes)
    return o


# ------------------------------------------------------------------ vẽ phiếu trả lời
def _y(v: float) -> float:            # mm từ trên xuống -> pt từ dưới lên
    return (PAGE_H - v) * MM


def draw_sheet(c, o: SheetOptions, L: dict, prefill: dict | None = None) -> None:
    """Vẽ một phiếu lên canvas ReportLab. prefill (chỉ dùng cho dữ liệu thử): {'student': '2213...', 'version': '01', 'answers': {1:'A'}}."""
    from reportlab.lib.colors import Color, black
    F = fonts()
    grey = Color(0.45, 0.45, 0.45)
    c.setFillColor(black)
    for x, y in FID_POS:
        c.rect(x * MM, _y(y + FID), FID * MM, FID * MM, stroke=0, fill=1)
    c.setFont(F["serifB"], 9); c.drawCentredString(PAGE_W / 2 * MM, _y(14), o.school)
    c.setFont(F["serifB"], 15); c.drawCentredString(PAGE_W / 2 * MM, _y(21.5), o.title)
    c.setFont(F["serifB"], 10.5)
    if o.subtitle:
        c.drawCentredString(PAGE_W / 2 * MM, _y(27), o.subtitle[:95])
    c.setFont(F["serif"], 9.5)
    vtxt = f"Mã đề: {', '.join(o.version_codes)}" if o.version_codes else ""
    line = " • ".join(x for x in (o.exam_title, f"{o.n_questions} câu", vtxt) if x)
    c.drawCentredString(PAGE_W / 2 * MM, _y(32), line[:120])
    c.setFont(F["serif"], 10)
    c.drawString(16 * MM, _y(41), "Họ và tên: " + "." * 70)
    c.drawString(130 * MM, _y(41), "Ngày thi: ....../....../.........")
    c.drawString(16 * MM, _y(48), "Lớp: " + "." * 40)
    c.drawString(90 * MM, _y(48), "Phòng thi: " + "." * 18)
    c.drawString(140 * MM, _y(48), "Chữ ký SV: " + "." * 16)
    # khối MSSV và mã đề
    top, dxd, dyd, r = L["top"], L["dx_digit"], L["dy_digit"], L["r"]

    def grid(title, cells, x0, ncol):
        w = ncol * dxd + 2
        c.setLineWidth(0.6); c.setStrokeColor(black)
        c.rect((x0 - 1) * MM, _y(L["id_bottom"] - 1.5), w * MM, (L["id_bottom"] - 1.5 - (top - 1.2)) * MM, stroke=1, fill=0)
        c.setFont(F["sansB"], 7.6); c.drawCentredString((x0 - 1 + w / 2) * MM, _y(top - 2.2), title)
        for k in range(ncol):     # ô viết số
            c.rect((x0 + k * dxd) * MM, _y(top + 7.3), (dxd - 0.6) * MM, 4.4 * MM, stroke=1, fill=0)
        for b in cells:
            c.setStrokeColor(grey); c.setLineWidth(0.5)
            c.circle(b["x"] * MM, _y(b["y"]), (r - 0.25) * MM, stroke=1, fill=0)
            c.setFillColor(grey); c.setFont(F["sans"], 6.2)
            c.drawCentredString(b["x"] * MM, _y(b["y"] + 0.95), str(b["value"]))
            c.setFillColor(black)
    grid("MÃ SỐ SINH VIÊN", L["student"], L["sx"] + 3 - dxd / 2 + 0.3, o.student_digits)
    grid("MÃ ĐỀ", L["version"], L["vx"] - dxd / 2 + 0.3, o.version_digits)
    # hướng dẫn tô
    hx = L["vx"] + o.version_digits * dxd + 6
    c.setFont(F["sansB"], 8.5); c.drawString(hx * MM, _y(top + 3), "HƯỚNG DẪN")
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    st = ParagraphStyle("n", fontName=F["serif"], fontSize=8.6, leading=10.6)
    items = ["1. Ghi MSSV, mã đề vào các ô trống rồi tô ô số tương ứng ở mỗi cột.",
             "2. " + o.note,
             "3. Không gấp, làm nhòe hoặc viết vào 4 ô vuông đen ở góc phiếu.",
             "4. Phiếu được chấm bằng máy quét hoặc ảnh chụp điện thoại."]
    yy = top + 5
    for t in items:
        p = Paragraph(html.escape(t), st)
        w, h = p.wrap((PAGE_W - 16 - hx) * MM, 100 * MM)
        p.drawOn(c, hx * MM, _y(yy) - h)
        yy += h / MM + 1.2
    ex_y = yy + 4
    c.setFont(F["serif"], 8.6); c.drawString(hx * MM, _y(ex_y + 1), "Tô đúng:")
    c.setFillColor(black); c.circle((hx + 17) * MM, _y(ex_y), r * MM, stroke=0, fill=1)
    c.drawString((hx + 24) * MM, _y(ex_y + 1), "Tô sai:")
    for k, mark in enumerate(("✓", "✗", "•")):
        cx = hx + 38 + k * 7
        c.setStrokeColor(grey); c.circle(cx * MM, _y(ex_y), (r - 0.25) * MM, stroke=1, fill=0)
        c.setFillColor(black); c.setFont(F["sans"], 7.5); c.drawCentredString(cx * MM, _y(ex_y + 1), mark)
    # vùng trả lời
    c.setStrokeColor(black); c.setLineWidth(0.6)
    c.setFont(F["sansB"], 9); c.drawString(16 * MM, _y(L["a_top"] + 1.2), "PHẦN TRẢ LỜI TRẮC NGHIỆM")
    c.rect(14 * MM, _y(L["a_bottom"]), (PAGE_W - 28) * MM, (L["a_bottom"] - L["a_top"] - 2.5) * MM, stroke=1, fill=0)
    for k in range(1, L["ncols"]):
        x = 15 + k * L["col_w"] - 1.5
        c.setLineWidth(0.3); c.line(x * MM, _y(L["a_top"] + 2.5), x * MM, _y(L["a_bottom"]))
    by_q = {}
    for b in L["answers"]:
        by_q.setdefault(b["q"], []).append(b)
    for q, bs in by_q.items():
        c.setFillColor(black); c.setFont(F["sansB"], 8.2)
        c.drawRightString((bs[0]["x"] - 3.6) * MM, _y(bs[0]["y"] + 1.05), f"{q:02d}")
        for b in bs:
            c.setStrokeColor(grey); c.setLineWidth(0.5)
            c.circle(b["x"] * MM, _y(b["y"]), (r - 0.25) * MM, stroke=1, fill=0)
            c.setFillColor(grey); c.setFont(F["sans"], 6.2); c.drawCentredString(b["x"] * MM, _y(b["y"] + 0.95), b["label"])
        if q % 5 == 0 and q % L["rows_per_col"]:
            y = bs[0]["y"] + L["dy"] / 2 + 0.8
            c.setStrokeColor(Color(0.75, 0.75, 0.75)); c.setLineWidth(0.25); c.setDash(1, 1.5)
            c.line((bs[0]["x"] - 9) * MM, _y(y), (bs[-1]["x"] + 3) * MM, _y(y)); c.setDash()
    if o.essay_lines:
        y0 = L["a_bottom"] + 6
        c.setFillColor(black); c.setFont(F["sansB"], 9); c.drawString(16 * MM, _y(y0), "PHẦN TỰ LUẬN / GHI CHÚ")
        c.setStrokeColor(Color(0.6, 0.6, 0.6)); c.setLineWidth(0.3); c.setDash(0.6, 1.4)
        for k in range(o.essay_lines):
            y = y0 + 6 + k * 7
            c.line(16 * MM, _y(y), (PAGE_W - 16) * MM, _y(y))
        c.setDash()
    c.setFillColor(grey); c.setFont(F["serifI"], 7.5)
    c.drawRightString((PAGE_W - 19) * MM, _y(PAGE_H - 12), f"{o.subtitle[:70]} • {o.exam_title[:40]}")
    if prefill:
        c.setFillColor(Color(0.1, 0.1, 0.1))
        for b in L["student"]:
            s = prefill.get("student", "")
            if b["col"] < len(s) and s[b["col"]] == str(b["value"]):
                c.circle(b["x"] * MM, _y(b["y"]), (r - 0.2) * MM, stroke=0, fill=1)
        for b in L["version"]:
            s = prefill.get("version", "")
            if b["col"] < len(s) and s[b["col"]] == str(b["value"]):
                c.circle(b["x"] * MM, _y(b["y"]), (r - 0.2) * MM, stroke=0, fill=1)
        for b in L["answers"]:
            if b["label"] in (prefill.get("answers", {}).get(b["q"]) or ""):
                c.circle(b["x"] * MM, _y(b["y"]), (r - 0.2) * MM, stroke=0, fill=1)


def sheet_pdf(o: SheetOptions, copies: int = 1, prefills: list[dict] | None = None) -> bytes:
    from reportlab.pdfgen.canvas import Canvas
    L = sheet_layout(o)
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=(PAGE_W * MM, PAGE_H * MM))
    c.setTitle(o.title)
    for k in range(len(prefills) if prefills else copies):
        draw_sheet(c, o, L, prefills[k] if prefills else None)
        c.showPage()
    c.save()
    return buf.getvalue()


def sheet_png(o: SheetOptions, zoom: float = 1.4) -> bytes:
    import fitz
    doc = fitz.open(stream=sheet_pdf(o), filetype="pdf")
    return doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom)).tobytes("png")


# ------------------------------------------------------------------ đề in (PDF/Word) 1 hoặc 2 cột
@dataclass
class PaperOptions:
    columns: int = 1                      # 1 = để nguyên; 2 = chia đôi mặt giấy
    font_size: float = 11.5
    school: str = "TRƯỜNG ĐẠI HỌC CÔNG NGHỆ KỸ THUẬT TP. HỒ CHÍ MINH"
    faculty: str = "KHOA CÔNG NGHỆ THÔNG TIN"
    exam_name: str = ""                   # VD ĐỀ THI CUỐI KỲ HỌC KỲ I NĂM HỌC 2025-2026
    duration: str = ""                    # VD 60 phút
    notes: str = "Sinh viên không được sử dụng tài liệu. Làm bài trên phiếu trả lời."
    show_points: bool = False
    option_layout: str = "auto"           # auto | 1 (mỗi dòng 1 phương án) | 2 | 4


def _option_cols(opts: list[dict], mode: str, width_pt: float, font: str, size: float) -> int:
    """Số cột phương án: đặt 4 (hoặc 2) phương án trên một dòng khi đủ chỗ – đo bằng độ rộng chữ thật của phông."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    if mode in ("1", "2", "4"):
        return min(int(mode), len(opts))
    longest = max(stringWidth(f"{o['label']}. {o['content']}", font, size) for o in opts) + 8
    n = len(opts)
    if n <= 4 and longest * n <= width_pt:
        return n
    if longest * 2 <= width_pt:
        return 2 if n > 2 else n
    return 1


def exam_pdf(exam: Exam, version: dict, p: PaperOptions, semester_name: str = "") -> bytes:
    from reportlab.lib.colors import black
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle
    F = fonts()
    cs = exam.class_section
    W, H = PAGE_W * MM, PAGE_H * MM
    margin = 15 * MM
    gap = 7 * MM
    head_h = (40 if p.notes else 35) * MM
    ncol = 2 if p.columns == 2 else 1
    fw = (W - 2 * margin - (gap if ncol == 2 else 0)) / ncol
    fs = p.font_size if ncol == 1 else min(p.font_size, 10.5)
    st_q = ParagraphStyle("q", fontName=F["serif"], fontSize=fs, leading=fs * 1.28, spaceBefore=fs * 0.45)
    st_o = ParagraphStyle("o", fontName=F["serif"], fontSize=fs, leading=fs * 1.22)
    st_h = ParagraphStyle("h", fontName=F["serifB"], fontSize=10.5, leading=13, alignment=1)
    st_hl = ParagraphStyle("hl", fontName=F["serif"], fontSize=10, leading=13, alignment=1)

    def header(c, doc):
        c.saveState()
        c.setFont(F["serif"], 8.5)
        c.drawRightString(W - margin, 9 * MM, f"Mã đề {version['version_code']} – Trang {doc.page}")
        c.drawString(margin, 9 * MM, f"{cs.course.course_code} – {exam.exam_title}"[:90])
        if ncol == 2:
            top = H - margin - (head_h if doc.page == 1 else 0)
            c.setLineWidth(0.4); c.line(W / 2, top, W / 2, 15 * MM)
        if doc.page == 1:
            t = Table([[Paragraph(f"<b>{html.escape(p.school)}</b><br/>{html.escape(p.faculty)}", st_hl),
                        Paragraph(f"<b>{html.escape(p.exam_name or exam.exam_title.upper())}</b><br/>"
                                  f"Môn: {html.escape(cs.course.course_name)} – Mã môn: {cs.course.course_code}<br/>"
                                  + (f"Thời gian: {html.escape(p.duration)} – " if p.duration else "")
                                  + f"{len(version['questions'])} câu – {html.escape(semester_name)}", st_hl)]],
                      colWidths=[(W - 2 * margin) * 0.42, (W - 2 * margin) * 0.58])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
            w, h = t.wrap(W - 2 * margin, 40 * MM)
            t.drawOn(c, margin, H - margin - h)
            y = H - margin - h - 6 * MM
            c.setFont(F["serifB"], 12); c.drawString(margin, y, f"MÃ ĐỀ: {version['version_code']}")
            c.setFont(F["serif"], 10.5)
            c.drawString(margin + 38 * MM, y, "Họ tên SV: " + "." * 48 + "  MSSV: " + "." * 22)
            if p.notes:
                c.setFont(F["serifI"], 9.5); c.drawString(margin, y - 6 * MM, p.notes[:150])
            c.setLineWidth(0.6); c.line(margin, H - margin - head_h + 2 * MM, W - margin, H - margin - head_h + 2 * MM)
        c.restoreState()

    first = [Frame(margin + i * (fw + gap), 15 * MM, fw, H - margin - head_h - 15 * MM, leftPadding=0, rightPadding=0, topPadding=2, id=f"f{i}")
             for i in range(ncol)]
    later = [Frame(margin + i * (fw + gap), 15 * MM, fw, H - 2 * margin, leftPadding=0, rightPadding=0, topPadding=0, id=f"g{i}")
             for i in range(ncol)]
    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=(W, H), title=f"{exam.exam_title} – mã đề {version['version_code']}")
    doc.addPageTemplates([PageTemplate("first", first, onPage=header, autoNextPageTemplate="later"),
                          PageTemplate("later", later, onPage=header)])
    story = []
    for q in version["questions"]:
        pts = f" <i>({q['points']:g} điểm)</i>" if p.show_points else ""
        block = [Paragraph(f"<b>Câu {q['position']}.</b>{pts} {para(q['content'])}", st_q)]
        k = _option_cols(q["options"], p.option_layout, fw - 4 * MM, F["serif"], fs)
        cells = [Paragraph(f"<b>{o['label']}.</b> {para(o['content'])}", st_o) for o in q["options"]]
        rows = [cells[i:i + k] + [""] * (k - len(cells[i:i + k])) for i in range(0, len(cells), k)]
        t = Table(rows, colWidths=[(fw - 4 * MM) / k] * k)
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                               ("TOPPADDING", (0, 0), (-1, -1), 0.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        t.hAlign = "LEFT"
        block += [Spacer(1, 1), t]
        story.append(KeepTogether(block))
    story += [Spacer(1, 8), Paragraph("<b>--- HẾT ---</b>", ParagraphStyle("end", parent=st_q, alignment=1))]
    doc.build(story)
    _ = black
    return buf.getvalue()


def exam_docx(exam: Exam, versions: list[dict], p: PaperOptions, semester_name: str = "") -> bytes:
    """Đề thi dạng Word (sửa được trước khi in); chia 2 cột bằng section 2 cột của Word."""
    from docx import Document
    from docx.enum.section import WD_SECTION
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Mm, Pt
    cs = exam.class_section
    d = Document()
    stl = d.styles["Normal"]; stl.font.name = "Times New Roman"; stl.font.size = Pt(p.font_size if p.columns == 1 else min(p.font_size, 11))
    stl.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    sec = d.sections[0]
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Mm(15))

    def cols(section, n):
        el = section._sectPr.find(qn("w:cols"))
        if el is None:
            el = OxmlElement("w:cols"); section._sectPr.append(el)
        el.set(qn("w:num"), str(n)); el.set(qn("w:space"), "400")
        if n == 2:
            el.set(qn("w:sep"), "1")
    for vi, v in enumerate(versions):
        if vi:
            sec = d.add_section(WD_SECTION.NEW_PAGE); cols(sec, 1)
        t = d.add_table(rows=1, cols=2)
        a, b = t.rows[0].cells
        a.paragraphs[0].add_run(p.school).bold = True
        a.add_paragraph(p.faculty)
        b.paragraphs[0].add_run(p.exam_name or exam.exam_title.upper()).bold = True
        b.add_paragraph(f"Môn: {cs.course.course_name} – Mã môn: {cs.course.course_code}")
        b.add_paragraph((f"Thời gian: {p.duration} – " if p.duration else "") + f"{len(v['questions'])} câu – {semester_name}")
        for cell in (a, b):
            for par in cell.paragraphs:
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = d.add_paragraph().add_run(f"MÃ ĐỀ: {v['version_code']}"); r.bold = True
        d.add_paragraph("Họ tên SV: ................................................  MSSV: ......................")
        if p.notes:
            d.add_paragraph().add_run(p.notes).italic = True
        sec = d.add_section(WD_SECTION.CONTINUOUS)
        cols(sec, 2 if p.columns == 2 else 1)
        for q in v["questions"]:
            par = d.add_paragraph()
            par.add_run(f"Câu {q['position']}. ").bold = True
            if p.show_points:
                par.add_run(f"({q['points']:g} điểm) ").italic = True
            par.add_run(q["content"])
            par.paragraph_format.space_before = Pt(4); par.paragraph_format.space_after = Pt(1)
            par.paragraph_format.keep_with_next = True
            for o in q["options"]:
                op = d.add_paragraph()
                op.add_run(f"{o['label']}. ").bold = True
                op.add_run(o["content"])
                op.paragraph_format.left_indent = Mm(5); op.paragraph_format.space_after = Pt(0)
        e = d.add_paragraph(); e.alignment = WD_ALIGN_PARAGRAPH.CENTER; e.add_run("--- HẾT ---").bold = True
    buf = io.BytesIO(); d.save(buf)
    return buf.getvalue()


def answer_key_pdf(exam: Exam, versions: list[dict]) -> bytes:
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib.colors import Color, black
    F = fonts()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=(PAGE_W * MM, PAGE_H * MM), leftMargin=15 * MM, rightMargin=15 * MM, topMargin=15 * MM, bottomMargin=15 * MM,
                            title=f"Đáp án – {exam.exam_title}")
    h = ParagraphStyle("h", fontName=F["serifB"], fontSize=13, leading=16, alignment=1)
    s = ParagraphStyle("s", fontName=F["serif"], fontSize=10, leading=13, alignment=1)
    story = [Paragraph(f"ĐÁP ÁN – {html.escape(exam.exam_title)}", h),
             Paragraph(f"{html.escape(exam.class_section.course.course_name)} – lớp {exam.class_section.section_code}", s), Spacer(1, 8)]
    for v in versions:
        story.append(Paragraph(f"Mã đề {v['version_code']}", ParagraphStyle("v", fontName=F["serifB"], fontSize=11.5, leading=15, spaceBefore=6)))
        cells = [f"{q['position']}.{q['answer'] or '?'}" for q in v["questions"]]
        if not cells:
            story.append(Paragraph("(Mã đề chưa có câu hỏi)", s))
            continue
        per = 10
        rows = [cells[i:i + per] + [""] * (per - len(cells[i:i + per])) for i in range(0, len(cells), per)]
        t = Table(rows, colWidths=[18 * MM] * per)
        t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), F["sans"]), ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                               ("GRID", (0, 0), (-1, -1), 0.4, Color(0.6, 0.6, 0.6)), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(t)
    doc.build(story)
    _ = black
    return buf.getvalue()
