"""Đọc một tệp PDF học liệu (slide xuất PDF, giáo trình, tài liệu tham khảo) thành danh sách trang.

Mỗi trang gồm các KHỐI CHỮ kèm tọa độ (bbox, đơn vị point, gốc ở góc trên trái) – về sau mỗi khối là một "đoạn" để
tìm kiếm, và bbox dùng để tô khung đúng khúc cần đọc trên ảnh trang. Không dùng mạng, không dùng CSDL.

Mỗi khối mang thêm cỡ chữ, in đậm (cờ font của PyMuPDF) và cờ code – để nhận tiêu đề và bảo vệ đoạn code. Code nhận
theo font monospace HOẶC theo nội dung (mật độ từ khóa SQL / cú pháp, ít chữ có dấu) vì GV hay dán code bằng font thường.
BẢNG kẻ ô được nhận bằng page.find_tables() và xuất thành Markdown (giữ hàng/cột); chữ trong bảng không còn là khối
rời, vùng bảng không bị coi là hình.

Làm sạch:
  - chuẩn hóa Unicode NFC (PDF tiếng Việt hay lưu chữ có dấu ở dạng tổ hợp), gộp khoảng trắng;
  - bỏ khối chỉ là số trang;
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

CODE_MIN_KW = 3         # nhận code theo nội dung: ≥ 3 từ khóa SQL / cú pháp Python-Java khác nhau ...
CODE_KW_DENSITY = 0.2   # ... chiếm ≥ 20% số từ ...
CODE_MAX_DIACRITIC = 0.05  # ... và < 5% chữ cái có dấu (câu giảng giải tiếng Việt nhắc tới WHERE không phải code)

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
_PAGE_NO = re.compile(r"^(trang|page|slide)?\s*\d{1,4}(\s*/\s*\d{1,4})?$", re.I)

BBox = tuple[float, float, float, float]   # x0, y0, x1, y1 (point, gốc góc trên trái)


@dataclass
class Block:
    text: str
    bbox: BBox
    size: float = 0.0           # cỡ chữ lớn nhất trong khối – để nhận ra tiêu đề
    bold: bool = False
    mono: bool = False          # code / câu lệnh SQL (font monospace HOẶC nội dung giống code) – không được cắt ngang
    char_w: float = 0.0         # khối code: bề rộng một ký tự (pt) – để dựng thụt lề giữa các khối code liền nhau


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


def _markdown(page: pymupdf.Page, t) -> str:
    # đọc chữ từng ô bằng get_textbox: extract()/to_markdown() của PyMuPDF tách sai chữ có dấu ("Kiể\nu")
    # escape "\" trước rồi "|": ô kết thúc bằng "\" (VD "C:\") không được nuốt dấu "|" phân cách phía sau
    rows = [[clean(page.get_textbox(c)).replace("\\", "\\\\").replace("|", "\\|") if c else "" for c in r.cells]
            for r in t.rows]
    keep = [j for j in range(len(rows[0])) if any(r[j] for r in rows)]   # cột rỗng do 2 đường kẻ sát nhau
    rows = [[r[j] for j in keep] for r in rows]
    lines = ["|" + "|".join(r) + "|" for r in rows]
    return "\n".join([lines[0], "|" + "---|" * len(keep)] + lines[1:])


def _tables(page: pymupdf.Page, drawings: list[dict]) -> list[Table]:
    if len(drawings) < TABLE_MIN_DRAWINGS:                # find_tables tốn ~0,5 s/trang → bỏ qua trang không có nét kẻ
        return []
    out = []
    for t in page.find_tables().tables:
        if t.row_count >= 2 and t.col_count >= 2:          # khung 1 ô (ô sơ đồ, hộp ghi chú) không phải bảng
            md = _markdown(page, t)
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
        text = "".join(s["text"] for s in ln["spans"])
        if text.strip():
            x0, _, x1, _ = ln["bbox"]
            rows.append((x0, (x1 - x0) / max(len(text), 1), _clean_code_line(text)))
    if not rows:
        return "", 0.0
    base = min(x for x, _, _ in rows)
    widths = sorted(w for _, w, _ in rows)
    char_w = widths[len(widths) // 2] or 1.0               # bề rộng ký tự: lấy trung vị các dòng
    return "\n".join(" " * round((x - base) / char_w) + text for x, _, text in rows), char_w


def _read_page(page: pymupdf.Page) -> Page:
    drawings = page.get_drawings()
    tables = _tables(page, drawings)
    d = page.get_text("dict", sort=True)    # sort: theo thứ tự đọc trên-xuống, trái-sang-phải
    blocks, images = [], []
    for b in d["blocks"]:
        if b["type"] == 1:
            images.append(pymupdf.Rect(b["bbox"]))
            continue
        if any(_center_in(b["bbox"], t.bbox) for t in tables):
            continue                                       # chữ trong bảng đã nằm trong Markdown của bảng
        spans = [s for ln in b["lines"] for s in ln["spans"]]
        raw = "\n".join("".join(s["text"] for s in ln["spans"]) for ln in b["lines"])
        t = clean(raw)
        if t and not _PAGE_NO.match(t):
            size = max((s["size"] for s in spans if s["text"].strip()), default=0.0)
            mono = _style(spans, _MONO, _MONO_FONT) or looks_like_code(raw)
            char_w = 0.0
            if mono:
                t, char_w = _code_text(b["lines"])
            blocks.append(Block(t, _round(b["bbox"]), round(size, 1),
                                bold=_style(spans, _BOLD, re.compile(r"bold|black|heavy", re.I)), mono=mono,
                                char_w=round(char_w, 2)))
    return Page(page.number + 1, page.rect.width, page.rect.height, blocks, _figures(page, images, drawings, tables),
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
    for p in pages:
        keep = []
        for b in p.blocks:
            where = _edge(b, p)
            if where and _repeat_key(b.text) in rep:
                if where == "top":
                    p.running.append(b.text)
            else:
                keep.append(b)
        p.blocks = keep


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
    for p in pages:
        _flag(p)
    return pages


def render_page(src: str | bytes, page_no: int, dpi: int = 110) -> bytes:
    """Ảnh PNG của một trang (page_no bắt đầu từ 1) – để hiển thị khung tô và cho VLM nhìn."""
    with _open(src) as doc:
        return doc[page_no - 1].get_pixmap(dpi=dpi).tobytes("png")
