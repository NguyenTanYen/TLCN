"""Đọc một tệp PDF học liệu (slide xuất PDF, giáo trình, tài liệu tham khảo) thành danh sách trang.

Mỗi trang gồm các KHỐI CHỮ kèm tọa độ (bbox, đơn vị point, gốc ở góc trên trái) – về sau mỗi khối là một "đoạn" để
tìm kiếm, và bbox dùng để tô khung đúng khúc cần đọc trên ảnh trang. Không dùng mạng, không dùng CSDL.

Mỗi khối mang thêm cỡ chữ, in đậm (cờ font của PyMuPDF) và cờ code – để nhận tiêu đề và bảo vệ đoạn code. Code nhận
theo font monospace HOẶC theo nội dung (mật độ từ khóa SQL / cú pháp, ít chữ có dấu) vì GV hay dán code bằng font thường.
BẢNG kẻ ô được nhận bằng page.find_tables() và xuất thành Markdown (giữ hàng/cột); chữ trong bảng không còn là khối
rời, vùng bảng không bị coi là hình.

Chữ được dựng lại từ TỪNG KÝ TỰ (rawdict): PDF xuất từ PowerPoint không lưu dấu cách giữa các từ, chỉ đặt từ sau cách
xa → chèn dấu cách theo khoảng trống. Dòng chữ xoay (dấu arXiv dọc lề, watermark) bị bỏ.

Làm sạch:
  - chuẩn hóa Unicode NFC (PDF tiếng Việt hay lưu chữ có dấu ở dạng tổ hợp), gộp khoảng trắng;
  - bỏ khối chỉ là số trang; bỏ đầu/chân trang mang số trang dù không lặp nhiều (sách đổi đầu trang theo chương
    và trang chẵn/lẻ) – nhận theo độ lệch cố định giữa số trang in và số thứ tự trang;
  - vùng hình lặp cùng vị trí ở ≥ DECOR_SHARE số trang (logo, banner của mẫu slide) và vùng "hình" thực ra là hộp chữ
    có nền không còn là hình – tiêu đề slide nằm trên banner trở về luồng chữ và được nhận là tiêu đề;
  - khối lặp lại (cùng nội dung, bỏ qua chữ số) ở ≥ REPEAT_SHARE số trang VÀ nằm trong dải đầu/chân trang (EDGE):
      đầu trang  ("Chương 2: Thiết kế CSDL" ở góc mọi slide của chương) → chuyển thành NGỮ CẢNH của trang (Page.running),
                 không mất thông tin nhưng cũng không lặp trong thân từng đoạn;
      chân trang (tên trường, tên môn, số trang) → bỏ.
    Khối lặp nằm giữa trang được giữ nguyên (là nội dung).

Đánh dấu trang cần xử lý thêm (dùng ở giai đoạn VLM/OCR, chưa xử lý ở đây):
  scanned – gần như không có chữ nhưng có ảnh phủ phần lớn trang (PDF scan) → cần OCR / VLM đọc;
  visual  – ít chữ nhưng nhiều hình (ảnh hoặc hình vẽ vector như sơ đồ ER, cây B-tree) → cần VLM mô tả.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

import pymupdf

REPEAT_SHARE = 0.5      # khối lặp ở ≥ 50% số trang ...
EDGE = 0.12             # ... và nằm trong 12% trên cùng / dưới cùng của trang thì là đầu / chân trang
REPEAT_MIN_PAGES = 4    # tài liệu ít trang hơn thì không lọc lặp (dễ xóa nhầm nội dung)
FEW_CHARS = 80          # trang có ít hơn ngần này ký tự coi là "ít chữ"
VISUAL_IMAGE_SHARE = 0.2  # ảnh chiếm ≥ 20% diện tích trang
VISUAL_DRAWINGS = 15    # hoặc có ≥ 15 nét vẽ vector (sơ đồ vẽ bằng shape trong PowerPoint)
SCAN_IMAGE_SHARE = 0.8  # ảnh phủ ≥ 80% trang mà không có chữ → trang scan
FIG_MIN_SHARE = 0.02    # vùng hình nhỏ hơn 2% trang (đường kẻ, icon, gạch chân) thì bỏ qua
FIG_MAX_SHARE = 0.9     # nét vẽ / ảnh phủ ≥ 90% trang là nền slide, không phải hình
FIG_JOIN = 15           # các nét vẽ cách nhau ≤ 15 pt được gom chung một hình (ô sơ đồ + đường nối)
TABLE_MIN_DRAWINGS = 4  # bảng kẻ ô cần ít nhất 4 nét vẽ (2×2 ô) – trang ít hơn thì không dò bảng
STYLE_SHARE = 0.8      # khối có ≥ 80% ký tự in đậm / monospace thì coi cả khối là in đậm / code
SPACE_GAP = 0.15        # PDF của PowerPoint không lưu dấu cách, chỉ đặt từ sau cách xa: khoảng trống > 0,15 × cỡ chữ → dấu cách
HORIZONTAL = 0.99       # dòng có hướng lệch khỏi phương ngang (chữ xoay dọc lề như dấu arXiv, watermark) thì bỏ
PAGE_HEAD_MAX = 80      # đầu/chân trang mang số trang: khối ngắn ≤ 80 ký tự ở dải đầu/chân trang ...
PAGE_HEAD_MIN_HITS = 3  # ... mà (số trang in − số thứ tự trang) giống nhau ở ≥ 3 trang (sách đổi đầu trang theo chương)
DECOR_SHARE = 0.5       # vùng hình lặp CÙNG VỊ TRÍ ở ≥ 50% số trang = trang trí (logo, banner tiêu đề) → không phải hình
DECOR_IOU = 0.9         # hai vùng coi là cùng vị trí khi tỷ lệ giao/hợp ≥ 0,9
DECOR_EDGE = 0.2        # ... và tâm vùng nằm ở rìa trang (20% trên/dưới, 10% trái/phải): sơ đồ GIỮA trang lặp lại qua
                        # nhiều slide (giảng từng bước) là nội dung, không phải trang trí
PAGE_HEAD_LEAD_MAX = 50  # số đứng ĐẦU khối chỉ coi là số trang khi khối ngắn và không kết thúc bằng dấu câu (khác chú thích
                         # cuối trang "1 Xem thêm tài liệu về Hadoop.")
TEXTBOX_SHARE = 0.5     # vùng "hình" mà chữ bên trong phủ ≥ 50% diện tích = hộp chữ có nền → không phải hình

CODE_MIN_KW = 3         # nhận code theo nội dung: ≥ 3 từ khóa SQL / cú pháp Python-Java khác nhau ...
CODE_KW_DENSITY = 0.2   # ... chiếm ≥ 20% số từ ...
CODE_MAX_DIACRITIC = 0.05  # ... và < 5% chữ cái có dấu (câu giảng giải tiếng Việt nhắc tới WHERE không phải code)
CODEY_MAX = 300         # khối dài hơn thì không xét là mảnh code (code dán bằng font thường bị tách theo dòng lùi)
INDENT_TOL = 2.0        # pt: hai dòng code font thường có x đầu dòng chênh ≤ 2 pt là cùng cấp thụt lề

_BOLD, _MONO = 16, 8    # bit cờ font của span trong PyMuPDF
_MONO_FONT = re.compile(r"mono|courier|consolas|menlo|inconsolata|code", re.I)
# từ khóa SQL viết HOA (quy ước khi viết câu lệnh) + mẫu cú pháp Python/Java/C
_CODE_KW = re.compile(r"\b(SELECT|FROM|WHERE|JOIN|ON|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|ALTER|DROP|TABLE|VIEW|"
                      r"INDEX|PRIMARY|FOREIGN|KEY|REFERENCES|GROUP|ORDER|BY|HAVING|UNION|DISTINCT|BEGIN|END|DECLARE|"
                      r"PROCEDURE|FUNCTION|TRIGGER|EXEC|COMMIT|ROLLBACK|AND|OR|NOT|NULL|IN|AS)\b"
                      r"|\bdef \w+\(|\bclass \w+\s*[:({]|\bimport [\w.]+|\breturn\b|\bself\.\w+|\bfor \w+ in\b"
                      r"|\b\w+\([^()]*\)|\b\w+ = \w|[{};]\s*$|==|!=|<=|>=|\+=")


# từ khóa "mạnh": gần như chỉ xuất hiện trong code – bắt buộc có ít nhất một (AND, OR, IN, AS... thì câu tiếng Anh cũng có)
_STRONG_KW = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|DECLARE|EXEC|TRUNCATE|GRANT|REVOKE)\b"
                        r"|\bdef \w+\(|\bclass \w+\s*[:({]|^\s*(from [\w.]+ )?import [\w.]+|\bfunction \w*\("
                        r"|\b(public|private|static)\s+\w+[\s(]|#include\b", re.M)
_COMMENT = re.compile(r"/\*.*?\*/|(--|//|#(?!include)).*?$", re.M | re.S)


def looks_like_code(text: str) -> bool:
    """Code dán bằng font thường (Arial, Calibri) mất cờ monospace → nhận theo nội dung.
    text giữ xuống dòng của khối: comment (-- // # /* */) được bỏ trước khi đếm, để comment tiếng Việt có dấu không
    làm khối code bị coi là chữ thường."""
    code = _COMMENT.sub(" ", text)
    if not _STRONG_KW.search(code):
        return False
    words = code.split()
    letters = [c for c in code if c.isalpha()]
    if not words or not letters:
        return False
    kws = [m.group(0) for m in _CODE_KW.finditer(code)]
    diacritic = sum(not c.isascii() for c in letters) / len(letters)
    return len(set(kws)) >= CODE_MIN_KW and len(kws) >= CODE_KW_DENSITY * len(words) and diacritic < CODE_MAX_DIACRITIC
_PAGE_NO = re.compile(r"^(?:(?i:trang|page|slide)\s*)?(?:\d{1,4}(?:\s*/\s*\d{1,4})?|[ivxlc]{1,7})$")
_TRAIL_NO = re.compile(r"(?:^|\s)(\d{1,4})$")          # "3 NoSQL Database 54", "Khoa CNTT 12"
_LEAD_NO = re.compile(r"^(\d{1,4})\s")                  # "54 Big Data Concepts" (trang chẵn)
_TRAIL_ROMAN = re.compile(r"\s[ivxlc]{1,7}$")           # "Contents x" (phần mở đầu sách đánh số La Mã thường)

BBox = tuple[float, float, float, float]   # x0, y0, x1, y1 (point, gốc góc trên trái)


@dataclass
class Block:
    text: str
    bbox: BBox
    size: float = 0.0           # cỡ chữ lớn nhất trong khối – để nhận ra tiêu đề
    bold: bool = False
    mono: bool = False          # code / câu lệnh SQL (font monospace HOẶC nội dung giống code) – không được cắt ngang
    char_w: float = 0.0         # khối code font monospace: bề rộng một ký tự (pt) – dựng thụt lề giữa các khối liền nhau
    lines: list[tuple[float, str]] = field(default_factory=list)   # (x đầu dòng, chữ của dòng) – để dựng lại code


@dataclass
class Table:
    bbox: BBox
    markdown: str               # dòng 1 = header, dòng 2 = |---|, dòng i+2 ↔ rows[i+1]
    rows: list[BBox] = field(default_factory=list)   # khung từng hàng – bảng dài bị cắt vẫn tô đúng các hàng


@dataclass
class Page:
    no: int                     # số trang, bắt đầu từ 1 (đúng số dùng cho liên kết #page=N)
    width: float
    height: float
    blocks: list[Block] = field(default_factory=list)
    figures: list[BBox] = field(default_factory=list)   # vùng hình: ảnh nhúng hoặc cụm nét vẽ vector (sơ đồ)
    tables: list[Table] = field(default_factory=list)
    running: list[str] = field(default_factory=list)    # đầu trang lặp lại (tên chương...) – ngữ cảnh của trang
    image_share: float = 0.0    # tỷ lệ diện tích trang bị ảnh phủ
    drawings: int = 0           # số nét vẽ vector
    scanned: bool = False
    visual: bool = False

    @property
    def text(self) -> str:
        return "\n".join([b.text for b in self.blocks] + [t.markdown for t in self.tables])


# ký tự rác hay gặp khi xuất slide/giáo trình ra PDF:
#   zero-width space giữa hai âm tiết → khoảng trắng; soft hyphen, ZWJ/ZWNJ, word joiner, BOM → bỏ;
#   ký tự vùng riêng (Private Use) = bullet của font Wingdings/Symbol ("\uf0b7", "\uf0a7"...) → "•";
#   glyph không có mã Unicode (PDF thiếu bảng ToUnicode) ra "\x00" hoặc "\ufffd" → bỏ
_DIRTY = str.maketrans({"\u200b": " ", "\xad": None, "\u200c": None, "\u200d": None, "\u2060": None, "\ufeff": None})
_PUA = re.compile("[\ue000-\uf8ff]")
_CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufffd]")


def clean(s: str) -> str:
    s = unicodedata.normalize("NFC", s).translate(_DIRTY)
    s = _CONTROL.sub("", _PUA.sub("• ", s))
    return re.sub(r"\s+", " ", s).strip()


def _round(r) -> BBox:
    return tuple(round(v, 1) for v in r)


def _center_in(b, r) -> bool:
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    return r[0] <= cx <= r[2] and r[1] <= cy <= r[3]


def _image_share(page: pymupdf.Page, image_rects: list[pymupdf.Rect]) -> float:
    area = abs(page.rect)
    if not area or not image_rects:
        return 0.0
    covered = sum(abs(r & page.rect) for r in image_rects)   # các ảnh chồng nhau hiếm gặp → cộng xấp xỉ là đủ
    return min(1.0, covered / area)


def _horizontal(ln: dict) -> bool:
    return abs(ln["dir"][0]) >= HORIZONTAL


def _line_text(ln: dict) -> str:
    """Chữ của một dòng dựng lại từ TỪNG KÝ TỰ (rawdict): chèn dấu cách khi khoảng trống giữa hai ký tự lớn hơn
    (khoảng cách ký tự thường gặp của dòng + SPACE_GAP × cỡ chữ) mà PDF không có ký tự dấu cách
    ("Tìm hiểu vềApache" → "Tìm hiểu về Apache"; chữ giãn "H A D O O P" vẫn là "HADOOP")."""
    chars = [(c, s["size"]) for s in ln["spans"] for c in s["chars"]]
    # khoảng cách thường gặp giữa hai ký tự LIỀN NHAU của chính dòng này (trung vị): chữ giãn (tracking, "H A D O O P")
    # có khoảng cách ký tự lớn đều → ngưỡng dấu cách phải cộng thêm mức này, không chỉ so với cỡ chữ
    gaps = sorted(b[0]["bbox"][0] - a[0]["bbox"][2] for a, b in zip(chars, chars[1:])
                  if a[0]["c"] != " " and b[0]["c"] != " ")
    base = max(0.0, gaps[len(gaps) // 2]) if gaps else 0.0
    out: list[str] = []
    prev_x1 = None
    for c, size in chars:
        ch = c["c"]
        if (prev_x1 is not None and ch != " " and out and out[-1] != " "
                and c["bbox"][0] - prev_x1 > base + SPACE_GAP * size):
            out.append(" ")
        out.append(ch)
        prev_x1 = c["bbox"][2]
    return "".join(out)


def _chars(raw: dict) -> list[tuple[str, tuple, float, int]]:
    """Mọi ký tự của trang (ký tự, bbox, cỡ chữ, số thứ tự dòng) theo thứ tự đọc – để chia chữ vào các ô bảng."""
    out, n = [], 0
    for b in raw["blocks"]:
        for ln in b.get("lines", []):
            if not _horizontal(ln):
                continue
            n += 1
            for s in ln["spans"]:
                out += [(c["c"], c["bbox"], s["size"], n) for c in s["chars"]]
    return out


def _cell_text(chars: list, rect) -> str:
    """Chữ trong một ô: các ký tự có tâm nằm trong ô, giữ thứ tự đọc của trang (không sắp lại theo tọa độ y – dấu tiếng
    Việt hơi lệch dòng sẽ tách chữ "Kiể\\nu"); xuống dòng hoặc khoảng trống lớn → dấu cách."""
    x0, y0, x1, y1 = rect
    out: list[str] = []
    prev = None
    for ch, bb, size, line in chars:
        if not (x0 <= (bb[0] + bb[2]) / 2 <= x1 and y0 <= (bb[1] + bb[3]) / 2 <= y1):
            continue
        if prev and (line != prev[1] or bb[0] - prev[0] > SPACE_GAP * size):
            out.append(" ")
        out.append(ch)
        prev = (bb[2], line)
    return clean("".join(out))


def _markdown(chars: list, t) -> str:
    # escape "\" trước rồi "|": ô kết thúc bằng "\" (VD "C:\") không được nuốt dấu "|" phân cách phía sau.
    # Ký tự của trang được lọc theo vùng bảng rồi theo từng hàng một lần – trước đây get_textbox() trích lại chữ CẢ TRANG
    # cho mỗi ô (trang CTĐT 300 ô mất vài giây)
    tx0, ty0, tx1, ty1 = t.bbox
    in_table = [c for c in chars if tx0 <= (c[1][0] + c[1][2]) / 2 <= tx1 and ty0 <= (c[1][1] + c[1][3]) / 2 <= ty1]
    rows = []
    for r in t.rows:
        _, ry0, _, ry1 = r.bbox
        in_row = [c for c in in_table if ry0 <= (c[1][1] + c[1][3]) / 2 <= ry1]
        rows.append([_cell_text(in_row, c).replace("\\", "\\\\").replace("|", "\\|") if c else "" for c in r.cells])
    keep = [j for j in range(len(rows[0])) if any(r[j] for r in rows)]   # cột rỗng do 2 đường kẻ sát nhau
    rows = [[r[j] for j in keep] for r in rows]
    lines = ["|" + "|".join(r) + "|" for r in rows]
    return "\n".join([lines[0], "|" + "---|" * len(keep)] + lines[1:])


def _tables(page: pymupdf.Page, drawings: list[dict], chars: list) -> list[Table]:
    if len(drawings) < TABLE_MIN_DRAWINGS:                # find_tables tốn ~0,3 s/trang → bỏ qua trang không có nét kẻ
        return []
    out = []
    for t in page.find_tables().tables:
        if t.row_count >= 2 and t.col_count >= 2:          # khung 1 ô (ô sơ đồ, hộp ghi chú) không phải bảng
            md = _markdown(chars, t)
            if md.count("---|") >= 2:
                out.append(Table(_round(t.bbox), md, [_round(r.bbox) for r in t.rows]))
    return out


def _figures(page: pymupdf.Page, images: list[pymupdf.Rect], drawings: list[dict], tables: list[Table]) -> list[BBox]:
    area = abs(page.rect)
    # bỏ hình nền phủ cả trang và đường kẻ của bảng TRƯỚC khi gom, nếu không chúng nuốt các nét vẽ khác thành một vùng
    lines = [d for d in drawings if abs(d["rect"]) < FIG_MAX_SHARE * area
             and not any(_center_in(d["rect"], t.bbox) for t in tables)]
    rects = [r & page.rect for r in images]
    if lines:
        rects += page.cluster_drawings(drawings=lines, x_tolerance=FIG_JOIN, y_tolerance=FIG_JOIN)
    rects = [pymupdf.Rect(r) for r in rects if FIG_MIN_SHARE * area <= abs(r) < FIG_MAX_SHARE * area]
    merged: list[pymupdf.Rect] = []
    for r in sorted(rects, key=lambda r: (r.y0, r.x0)):    # gộp các vùng chồng nhau (ảnh nằm trên khung vẽ...)
        for m in merged:
            if m.intersects(r):
                m |= r
                break
        else:
            merged.append(r)
    return [_round(r) for r in merged]


def _style(spans: list[dict], bit: int, name: re.Pattern | None = None) -> bool:
    total = sum(len(s["text"].strip()) for s in spans)
    hit = sum(len(s["text"].strip()) for s in spans
              if s["flags"] & bit or (name is not None and name.search(s["font"])))
    return total > 0 and hit >= STYLE_SHARE * total


def _clean_code_line(s: str) -> str:
    """Như clean() nhưng GIỮ khoảng trắng đầu dòng và giữa dòng (thụt lề, căn cột của code)."""
    s = unicodedata.normalize("NFC", s).translate(_DIRTY).replace("\t", "    ").replace(chr(0xA0), " ")
    return _CONTROL.sub("", _PUA.sub("• ", s)).rstrip()


def _code_text(lines: list[dict]) -> tuple[str, float]:
    """Khối code: giữ XUỐNG DÒNG và dựng lại THỤT LỀ. PDF thường không lưu khoảng trắng đầu dòng mà đặt dòng lùi vào bằng
    tọa độ x → thụt lề = (x của dòng − x của dòng lùi trái nhất) / bề rộng một ký tự, cộng khoảng trắng đầu dòng nếu có.
    Trả về (chữ, bề rộng ký tự). Dòng lùi vào thường bị PyMuPDF tách thành khối riêng → thụt lề GIỮA các khối do
    chunk dựng tiếp từ bbox + bề rộng ký tự."""
    rows = []
    for ln in lines:
        text = _line_text(ln)
        if text.strip():
            x0, _, x1, _ = ln["bbox"]
            rows.append((x0, (x1 - x0) / max(len(text), 1), _clean_code_line(text)))
    if not rows:
        return "", 0.0
    base = min(x for x, _, _ in rows)
    widths = sorted(w for _, w, _ in rows)
    char_w = widths[len(widths) // 2] or 1.0               # bề rộng ký tự: lấy trung vị các dòng
    return "\n".join(" " * round((x - base) / char_w) + text for x, _, text in rows), char_w


def _codey(text: str) -> bool:
    """Khối CÓ THỂ là một phần của code (dấu hiệu yếu): ít chữ có dấu, có từ khóa hoặc ký hiệu lập trình."""
    if len(text) > CODEY_MAX:
        return False
    code = _COMMENT.sub(" ", text)                  # comment tiếng Việt có dấu ("-- Lấy danh sách") không tính
    letters = [c for c in code if c.isalpha()]
    if not letters:
        return code.strip() != text.strip()         # khối chỉ toàn comment vẫn thuộc chuỗi code
    diacritic = sum(not c.isascii() for c in letters) / len(letters)
    return diacritic < CODE_MAX_DIACRITIC and bool(_CODE_KW.search(code) or re.search(r"[=():;{}\[\]]", code))


def _indent_levels(lines: list[tuple[float, str]]) -> str:
    """Code font THƯỜNG (Arial, Calibri): bề rộng ký tự thay đổi (i hẹp, W rộng) nên không chia tọa độ x cho bề rộng ký
    tự được – mỗi mức lùi x khác nhau là một CẤP thụt lề (4 dấu cách): 50 pt → 0, 64 pt → 4, 78 pt → 8 ..."""
    levels: list[float] = []
    for x in sorted(x for x, _ in lines):
        if not levels or x - levels[-1] > INDENT_TOL:
            levels.append(x)
    def level(x: float) -> int:
        return max(i for i, lv in enumerate(levels) if x >= lv - INDENT_TOL)
    return "\n".join("    " * level(x) + text for x, text in lines if text.strip())


def _mark_code_runs(blocks: list[Block]) -> None:
    """Code dán bằng font thường mất cờ monospace, và dòng lùi vào bị PyMuPDF tách thành khối riêng – từng khối lẻ
    ("tong = 0", "for x in ds:") không đủ dấu hiệu. Xét CHUỖI khối liền nhau có dấu hiệu code: nếu cả chuỗi giống code
    (looks_like_code) thì đánh dấu cả chuỗi là code và dựng thụt lề theo cấp cho chung cả chuỗi."""
    def candidate(b: Block) -> bool:                # mảnh code (dấu hiệu yếu) hoặc tự nó đã giống code (khối SQL dài)
        return not b.mono and (_codey(b.text) or _looks_like_code_lines(b.lines))

    i = 0
    while i < len(blocks):
        if not candidate(blocks[i]):
            i += 1
            continue
        j = i
        while j < len(blocks) and candidate(blocks[j]):
            j += 1
        run = blocks[i:j]
        if _looks_like_code_lines([ln for b in run for ln in b.lines]):
            _set_code(run)
        else:                                       # câu dẫn tiếng Anh ngay trước khối SQL kéo cả chuỗi xuống ngưỡng
            for b in run:                           # → xét lại từng khối riêng
                if _looks_like_code_lines(b.lines):
                    _set_code([b])
        i = j


def _looks_like_code_lines(lines: list[tuple[float, str]]) -> bool:
    return looks_like_code("\n".join(text for _, text in lines))


def _set_code(run: list[Block]) -> None:
    levels = _indent_levels([ln for b in run for ln in b.lines]).split("\n")
    k = 0
    for b in run:
        n = sum(1 for _, text in b.lines if text.strip())
        b.text, b.mono, b.char_w = "\n".join(levels[k:k + n]), True, 0.0
        k += n


def _textbox(region: BBox, blocks: list[Block]) -> bool:
    """Vùng "hình" mà chữ bên trong phủ phần lớn diện tích là HỘP CHỮ CÓ NỀN (tiêu đề slide trong shape) – không phải hình."""
    area = (region[2] - region[0]) * (region[3] - region[1])
    covered = sum((b.bbox[2] - b.bbox[0]) * (b.bbox[3] - b.bbox[1]) for b in blocks if _center_in(b.bbox, region))
    return area > 0 and covered >= TEXTBOX_SHARE * area


def _read_page(page: pymupdf.Page) -> Page:
    drawings = page.get_drawings()
    # rawdict: từng ký tự kèm tọa độ – dựng lại dấu cách bị thiếu, chia chữ vào ô bảng; sort: thứ tự đọc
    # TEXT_INHIBIT_SPACES: PyMuPDF không tự chèn dấu cách ở khoảng trống lớn (chữ giãn ra "H A D O O P") – việc
    # chèn dấu cách do _line_text quyết định theo khoảng cách thường gặp của từng dòng
    d = page.get_text("rawdict", sort=True, flags=pymupdf.TEXTFLAGS_RAWDICT | pymupdf.TEXT_INHIBIT_SPACES)
    chars = _chars(d)
    tables = _tables(page, drawings, chars)
    blocks, images = [], []
    for b in d["blocks"]:
        if b["type"] == 1:
            images.append(pymupdf.Rect(b["bbox"]))
            continue
        if any(_center_in(b["bbox"], t.bbox) for t in tables):
            continue                                       # chữ trong bảng đã nằm trong Markdown của bảng
        lines = [ln for ln in b["lines"] if _horizontal(ln)]   # bỏ chữ xoay (dấu arXiv dọc lề, watermark)
        if not lines:
            continue
        spans = [s for ln in lines for s in ln["spans"]]
        for s in spans:
            s["text"] = "".join(c["c"] for c in s["chars"])
        raw = "\n".join(_line_text(ln) for ln in lines)
        t = clean(raw)
        if t and not _PAGE_NO.match(t):
            size = max((s["size"] for s in spans if s["text"].strip()), default=0.0)
            mono = _style(spans, _MONO, _MONO_FONT)           # code font monospace: thụt lề theo bề rộng ký tự
            char_w = 0.0
            if mono:
                t, char_w = _code_text(lines)
            bbox = pymupdf.Rect(lines[0]["bbox"])
            for ln in lines[1:]:
                bbox |= ln["bbox"]
            blocks.append(Block(t, _round(bbox), round(size, 1),
                                bold=_style(spans, _BOLD, re.compile(r"bold|black|heavy", re.I)), mono=mono,
                                char_w=round(char_w, 2),
                                lines=[(ln["bbox"][0], _clean_code_line(_line_text(ln))) for ln in lines]))
    _mark_code_runs(blocks)                                # code dán bằng font thường: nhận theo cả chuỗi khối
    figures = [r for r in _figures(page, images, drawings, tables) if not _textbox(r, blocks)]
    return Page(page.number + 1, page.rect.width, page.rect.height, blocks, figures,
                tables, image_share=round(_image_share(page, images), 3), drawings=len(drawings))


def _repeat_key(s: str) -> str:
    # chân trang thường dính số trang trên cùng dòng ("Cơ sở dữ liệu – Khoa CNTT 12") → bỏ chữ số khi so lặp
    return re.sub(r"\d+", "#", s.lower())


def _edge(b: Block, p: Page) -> str:
    if b.bbox[3] <= EDGE * p.height:
        return "top"
    if b.bbox[1] >= (1 - EDGE) * p.height:
        return "bottom"
    return ""


def _strip_running(pages: list[Page]) -> None:
    if len(pages) < REPEAT_MIN_PAGES:
        return
    seen = Counter(k for p in pages for k in {_repeat_key(b.text) for b in p.blocks if _edge(b, p)})
    rep = {k for k, n in seen.items() if n >= REPEAT_SHARE * len(pages)}
    # cùng mẫu nhưng phần số THAY ĐỔI giữa các trang ("52 Big Data Concepts", "54 Big Data Concepts") = số trang → bỏ;
    # phần số cố định ("Chương 2: Thiết kế CSDL") = tên chương → giữ làm ngữ cảnh
    variants: dict[str, set[str]] = {}
    for p in pages:
        for b in p.blocks:
            if _edge(b, p) and _repeat_key(b.text) in rep:
                variants.setdefault(_repeat_key(b.text), set()).add(b.text)
    for p in pages:
        keep = []
        for b in p.blocks:
            where = _edge(b, p)
            if where and _repeat_key(b.text) in rep:
                key = _repeat_key(b.text)
                # đầu trang chỉ là ngày tháng hoặc mang số trang: bỏ hẳn, không làm ngữ cảnh
                if where == "top" and any(c.isalpha() for c in b.text) and len(variants[key]) == 1:
                    p.running.append(b.text)
            else:
                keep.append(b)
        p.blocks = keep


def _strip_page_heads(pages: list[Page]) -> None:
    """Đầu / chân trang MANG SỐ TRANG mà không lặp đủ nhiều để _strip_running nhận ra (sách đổi đầu trang chẵn/lẻ và theo
    từng chương: "3 NoSQL Database 54", "3.7 NoSQL Not Only SQL 61"). Nhận theo số trang: khối ngắn ở dải đầu/chân
    trang có số ở đầu hoặc cuối mà (số đó − số thứ tự trang) giống nhau ở ≥ PAGE_HEAD_MIN_HITS trang – độ lệch cố định
    giữa số trang in và số thứ tự trang của tệp. Số La Mã thường ở cuối ("Contents x") là trang mở đầu sách → bỏ luôn."""
    cands = []
    for p in pages:
        for b in p.blocks:
            if not _edge(b, p) or len(b.text) > PAGE_HEAD_MAX or b.text.endswith((".", "!", "?", ";", ":")):
                continue                                   # đầu/chân trang không kết thúc bằng dấu câu; chú thích thì có
            for rx in (_TRAIL_NO, _LEAD_NO):
                m = rx.search(b.text)
                if m and (rx is _TRAIL_NO or len(b.text) <= PAGE_HEAD_LEAD_MAX):
                    cands.append((id(b), int(m.group(1)) - p.no))
    hits = Counter(delta for _, delta in cands)
    drop = {bid for bid, delta in cands if hits[delta] >= PAGE_HEAD_MIN_HITS}
    for p in pages:
        p.blocks = [b for b in p.blocks
                    if id(b) not in drop and not (_edge(b, p) and len(b.text) <= PAGE_HEAD_MAX and _TRAIL_ROMAN.search(b.text))]


def _iou(a: BBox, b: BBox) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _drop_decorations(pages: list[Page]) -> None:
    """Vùng hình lặp ở CÙNG VỊ TRÍ trên ≥ DECOR_SHARE số trang là trang trí của mẫu slide (logo, banner chứa tiêu đề) →
    bỏ, để chữ nằm trên đó (tiêu đề slide) trở về luồng chữ thường và được nhận là tiêu đề."""
    if len(pages) < REPEAT_MIN_PAGES:
        return
    def at_edge(r: BBox, p: Page) -> bool:
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        return (cy < DECOR_EDGE * p.height or cy > (1 - DECOR_EDGE) * p.height
                or cx < DECOR_EDGE / 2 * p.width or cx > (1 - DECOR_EDGE / 2) * p.width)

    decor = [[at_edge(r, p) and sum(any(_iou(r, s) >= DECOR_IOU for s in q.figures) for q in pages)
              >= DECOR_SHARE * len(pages) for r in p.figures] for p in pages]   # quyết định cho mọi trang TRƯỚC rồi mới lọc
    for p, flags in zip(pages, decor):
        p.figures = [r for r, is_decor in zip(p.figures, flags) if not is_decor]


def _flag(p: Page) -> None:
    chars = len(p.text)
    p.scanned = chars == 0 and p.image_share >= SCAN_IMAGE_SHARE
    p.visual = not p.scanned and chars < FEW_CHARS and (p.image_share >= VISUAL_IMAGE_SHARE or p.drawings >= VISUAL_DRAWINGS)


def _open(src: str | bytes) -> pymupdf.Document:
    return pymupdf.open(stream=src, filetype="pdf") if isinstance(src, bytes) else pymupdf.open(src)


def read_pdf(src: str | bytes) -> list[Page]:
    """src: đường dẫn tệp hoặc nội dung PDF (bytes)."""
    with _open(src) as doc:
        pages = [_read_page(pg) for pg in doc]
    _strip_running(pages)
    _strip_page_heads(pages)
    _drop_decorations(pages)
    for p in pages:
        _flag(p)
    return pages


def render_page(src: str | bytes, page_no: int, dpi: int = 110) -> bytes:
    """Ảnh PNG của một trang (page_no bắt đầu từ 1) – để hiển thị khung tô và cho VLM nhìn."""
    with _open(src) as doc:
        return doc[page_no - 1].get_pixmap(dpi=dpi).tobytes("png")
