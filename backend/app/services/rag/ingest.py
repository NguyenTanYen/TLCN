"""Đọc một tệp PDF học liệu (slide xuất PDF, giáo trình, tài liệu tham khảo) thành danh sách trang."""
from __future__ import annotations

import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

import pymupdf

log = logging.getLogger(__name__)

REPEAT_SHARE = 0.5
EDGE = 0.12
REPEAT_MIN_PAGES = 4
FEW_CHARS = 80
VISUAL_IMAGE_SHARE = 0.2
VISUAL_DRAWINGS = 15
SCAN_IMAGE_SHARE = 0.8
FIG_MIN_SHARE = 0.02
FIG_MAX_SHARE = 0.9
FIG_JOIN = 15
TABLE_MIN_DRAWINGS = 4
STYLE_SHARE = 0.8
SPACE_GAP = 0.15
HORIZONTAL = 0.99
PAGE_HEAD_MAX = 80
PAGE_HEAD_MIN_HITS = 3
DECOR_SHARE = 0.5
DECOR_IOU = 0.9
DECOR_EDGE = 0.2
PAGE_HEAD_LEAD_MAX = 50
TEXTBOX_SHARE = 0.5
FRAME_MIN_SHARE = 0.12
FRAME_MAX_SHARE = 0.6
FRAME_TABLE_IOU = 0.8
FRAME_RATIO = (1.25, 1.85)
FRAME_PAGES = 0.5
FRAME_TOL = 3.0

CODE_MIN_KW = 3
CODE_KW_DENSITY = 0.2
CODE_MAX_DIACRITIC = 0.05
CODEY_MAX = 300
INDENT_TOL = 2.0

_BOLD, _MONO = 16, 8
_MONO_FONT = re.compile(r"mono|courier|consolas|menlo|inconsolata|code", re.I)
_CODE_KW = re.compile(r"\b(SELECT|FROM|WHERE|JOIN|ON|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|ALTER|DROP|TABLE|VIEW|"
                      r"INDEX|PRIMARY|FOREIGN|KEY|REFERENCES|GROUP|ORDER|BY|HAVING|UNION|DISTINCT|BEGIN|END|DECLARE|"
                      r"PROCEDURE|FUNCTION|TRIGGER|EXEC|COMMIT|ROLLBACK|AND|OR|NOT|NULL|IN|AS)\b"
                      r"|\bdef \w+\(|\bclass \w+\s*[:({]|\bimport [\w.]+|\breturn\b|\bself\.\w+|\bfor \w+ in\b"
                      r"|\b\w+\([^()]*\)|\b\w+ = \w|[{};]\s*$|==|!=|<=|>=|\+=")


_STRONG_KW = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|DECLARE|EXEC|TRUNCATE|GRANT|REVOKE)\b"
                        r"|\bdef \w+\(|\bclass \w+\s*[:({]|^\s*(from [\w.]+ )?import [\w.]+|\bfunction \w*\("
                        r"|\b(public|private|static)\s+\w+[\s(]|#include\b", re.M)
_COMMENT = re.compile(r"/\*.*?\*/|(--|//|#(?!include)).*?$", re.M | re.S)


def looks_like_code(text: str) -> bool:
    """Code dán bằng font thường (Arial, Calibri) mất cờ monospace → nhận theo nội dung."""
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
_TRAIL_NO = re.compile(r"(?:^|\s)(\d{1,4})$")
_LEAD_NO = re.compile(r"^(\d{1,4})\s")
_TRAIL_ROMAN = re.compile(r"\s[ivxlc]{1,7}$")

BBox = tuple[float, float, float, float]


@dataclass
class Block:
    text: str
    bbox: BBox
    size: float = 0.0
    bold: bool = False
    mono: bool = False
    char_w: float = 0.0
    lines: list[tuple[float, str]] = field(default_factory=list)


@dataclass
class Table:
    bbox: BBox
    markdown: str
    rows: list[BBox] = field(default_factory=list)


@dataclass
class Page:
    no: int
    width: float
    height: float
    blocks: list[Block] = field(default_factory=list)
    figures: list[BBox] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    running: list[str] = field(default_factory=list)
    image_share: float = 0.0
    drawings: int = 0
    scanned: bool = False
    visual: bool = False
    offset: tuple[float, float] = (0.0, 0.0)
    sheet: tuple[float, float] | None = None

    @property
    def text(self) -> str:
        return "\n".join([b.text for b in self.blocks] + [t.markdown for t in self.tables])


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
    covered = sum(abs(r & page.rect) for r in image_rects)
    return min(1.0, covered / area)


def _horizontal(ln: dict) -> bool:
    return abs(ln["dir"][0]) >= HORIZONTAL


def _line_text(ln: dict) -> str:
    """Chữ của một dòng dựng lại từ TỪNG KÝ TỰ (rawdict): chèn dấu cách khi khoảng trống giữa hai ký tự lớn hơn (khoảng cách ký tự thường gặp của dòng + SPACE_GAP × cỡ chữ) mà PDF không có ký tự dấu cách ("Tìm hiểu vềApache" → "Tìm hiểu về Apache"; chữ giãn "H A D O O P" vẫn là "HADOOP")."""
    chars = [(c, s["size"]) for s in ln["spans"] for c in s["chars"]]
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
    """Chữ trong một ô: các ký tự có tâm nằm trong ô, giữ thứ tự đọc của trang (không sắp lại theo tọa độ y – dấu tiếng Việt hơi lệch dòng sẽ tách chữ "Kiể\\nu"); xuống dòng hoặc khoảng trống lớn → dấu cách."""
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
    tx0, ty0, tx1, ty1 = t.bbox
    in_table = [c for c in chars if tx0 <= (c[1][0] + c[1][2]) / 2 <= tx1 and ty0 <= (c[1][1] + c[1][3]) / 2 <= ty1]
    rows = []
    for r in t.rows:
        _, ry0, _, ry1 = r.bbox
        in_row = [c for c in in_table if ry0 <= (c[1][1] + c[1][3]) / 2 <= ry1]
        rows.append([_cell_text(in_row, c).replace("\\", "\\\\").replace("|", "\\|") if c else "" for c in r.cells])
    keep = [j for j in range(len(rows[0])) if any(r[j] for r in rows)]
    rows = [[r[j] for j in keep] for r in rows]
    lines = ["|" + "|".join(r) + "|" for r in rows]
    return "\n".join([lines[0], "|" + "---|" * len(keep)] + lines[1:])


def _tables(page: pymupdf.Page, drawings: list[dict], chars: list) -> list[Table]:
    if len(drawings) < TABLE_MIN_DRAWINGS:
        return []
    out = []
    for t in page.find_tables().tables:
        if t.row_count >= 2 and t.col_count >= 2:
            md = _markdown(chars, t)
            if md.count("---|") >= 2:
                out.append(Table(_round(t.bbox), md, [_round(r.bbox) for r in t.rows]))
    return out


def _figures(page: pymupdf.Page, images: list[pymupdf.Rect], drawings: list[dict], tables: list[Table]) -> list[BBox]:
    area = abs(page.rect)
    lines = [d for d in drawings if abs(d["rect"]) < FIG_MAX_SHARE * area
             and not any(_center_in(d["rect"], t.bbox) for t in tables)]
    rects = [r & page.rect for r in images]
    if lines:
        rects += page.cluster_drawings(drawings=lines, x_tolerance=FIG_JOIN, y_tolerance=FIG_JOIN)
    rects = [pymupdf.Rect(r) for r in rects if FIG_MIN_SHARE * area <= abs(r) < FIG_MAX_SHARE * area]
    merged: list[pymupdf.Rect] = []
    for r in sorted(rects, key=lambda r: (r.y0, r.x0)):
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
    """Khối code: giữ XUỐNG DÒNG và dựng lại THỤT LỀ."""
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
    char_w = widths[len(widths) // 2] or 1.0
    return "\n".join(" " * round((x - base) / char_w) + text for x, _, text in rows), char_w


def _codey(text: str) -> bool:
    """Khối CÓ THỂ là một phần của code (dấu hiệu yếu): ít chữ có dấu, có từ khóa hoặc ký hiệu lập trình."""
    if len(text) > CODEY_MAX:
        return False
    code = _COMMENT.sub(" ", text)
    letters = [c for c in code if c.isalpha()]
    if not letters:
        return code.strip() != text.strip()
    diacritic = sum(not c.isascii() for c in letters) / len(letters)
    return diacritic < CODE_MAX_DIACRITIC and bool(_CODE_KW.search(code) or re.search(r"[=():;{}\[\]]", code))


def _indent_levels(lines: list[tuple[float, str]]) -> str:
    """Code font THƯỜNG (Arial, Calibri): bề rộng ký tự thay đổi (i hẹp, W rộng) nên không chia tọa độ x cho bề rộng ký tự được – mỗi mức lùi x khác nhau là một CẤP thụt lề (4 dấu cách): 50 pt → 0, 64 pt → 4, 78 pt → 8 ..."""
    levels: list[float] = []
    for x in sorted(x for x, _ in lines):
        if not levels or x - levels[-1] > INDENT_TOL:
            levels.append(x)
    def level(x: float) -> int:
        return max(i for i, lv in enumerate(levels) if x >= lv - INDENT_TOL)
    return "\n".join("    " * level(x) + text for x, text in lines if text.strip())


def _mark_code_runs(blocks: list[Block]) -> None:
    """Code dán bằng font thường mất cờ monospace, và dòng lùi vào bị PyMuPDF tách thành khối riêng – từng khối lẻ ("tong = 0", "for x in ds:") không đủ dấu hiệu."""
    def candidate(b: Block) -> bool:
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
        else:
            for b in run:
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


def _frame_candidates(page: pymupdf.Page, drawings: list[dict], whole: bool = False) -> list[pymupdf.Rect]:
    """Hình chữ nhật đơn lẻ tỷ lệ slide, đủ lớn – ứng viên khung slide của bản in handout."""
    area, out = abs(page.rect), []
    lo, hi = (FRAME_MAX_SHARE, FIG_MAX_SHARE) if whole else (FRAME_MIN_SHARE, FRAME_MAX_SHARE)
    for d in drawings:
        r = d["rect"]
        if len(d["items"]) != 1 or d["items"][0][0] != "re" or not r.height:
            continue
        share = abs(r) / area
        if (lo < share < hi if whole else lo <= share <= hi) and FRAME_RATIO[0] <= r.width / r.height <= FRAME_RATIO[1]:
            if not any(_same_rect(r, o) for o in out):
                out.append(pymupdf.Rect(r))
    return out


def _same_rect(a, b) -> bool:
    return all(abs(x - y) <= FRAME_TOL for x, y in zip(a, b))


def _handout_frames(cands: list[list[pymupdf.Rect]]) -> list[list[pymupdf.Rect]]:
    """Khung của TỪNG TRANG: ứng viên của chính trang đó lặp cùng vị trí trên ≥ 2 trang và ≥ FRAME_PAGES số trang có ứng viên – trang không có khung (bài tập A4 gộp chung tệp) không bị cắt."""
    with_cands = [rs for rs in cands if rs]
    out = []
    for rs in cands:
        keep = [r for r in rs if sum(any(_same_rect(r, o) for o in other) for other in with_cands)
                >= max(2, FRAME_PAGES * len(with_cands))]
        if any(a.intersects(b) for i, a in enumerate(keep) for b in keep[i + 1:]):
            keep = []
        out.append(sorted(keep, key=lambda r: (r.y0, r.x0)))
    return out


def _sub_page(p: Page, region: BBox, images: list[pymupdf.Rect], drawings: list[dict], taken: list[Block]) -> Page:
    """Trang con của bản in handout: phần của trang p nằm trong khung slide region, tọa độ tính từ góc khung."""
    dx, dy = region[0], region[1]
    w, h = region[2] - region[0], region[3] - region[1]
    def move(b):
        return _round((b[0] - dx, b[1] - dy, b[2] - dx, b[3] - dy))
    blocks = []
    for b in p.blocks:
        if _center_in(b.bbox, region):
            taken.append(b)
            blocks.append(Block(b.text, move(b.bbox), b.size, b.bold, b.mono, b.char_w, [(x - dx, t) for x, t in b.lines]))
    covered = sum(abs(r & pymupdf.Rect(region)) for r in images)
    return Page(p.no, w, h, blocks, [move(f) for f in p.figures if _center_in(f, region)],
                [Table(move(t.bbox), t.markdown, [move(r) for r in t.rows]) for t in p.tables if _center_in(t.bbox, region)],
                image_share=round(min(1.0, covered / (w * h)), 3),
                drawings=sum(1 for d in drawings if _center_in(d["rect"], region)), offset=(dx, dy), sheet=(p.width, p.height))


def _read_page(page: pymupdf.Page, drawings: list[dict] | None = None,
               frames: list[pymupdf.Rect] | None = None, borders: list[pymupdf.Rect] | None = None) -> list[Page]:
    """Một trang PDF → một Page; bản in handout (frames) → mỗi khung slide một trang con + phần còn lại ngoài khung."""
    if drawings is None:
        drawings = page.get_drawings()
    d = page.get_text("rawdict", sort=True, flags=pymupdf.TEXTFLAGS_RAWDICT | pymupdf.TEXT_INHIBIT_SPACES)
    chars = _chars(d)
    tables = _tables(page, drawings, chars)
    frames = [f for f in frames or [] if not any(_iou(tuple(f), t.bbox) >= FRAME_TABLE_IOU for t in tables)]
    borders = [f for f in borders or [] if not any(_iou(tuple(f), t.bbox) >= FRAME_TABLE_IOU for t in tables)]
    if frames or borders:
        drawings = [d for d in drawings if not any(_same_rect(d["rect"], f) for f in frames + borders)]
    blocks, images = [], []
    for b in d["blocks"]:
        if b["type"] == 1:
            images.append(pymupdf.Rect(b["bbox"]))
            continue
        if any(_center_in(b["bbox"], t.bbox) for t in tables):
            continue
        lines = [ln for ln in b["lines"] if _horizontal(ln)]
        if not lines:
            continue
        spans = [s for ln in lines for s in ln["spans"]]
        for s in spans:
            s["text"] = "".join(c["c"] for c in s["chars"])
        raw = "\n".join(_line_text(ln) for ln in lines)
        t = clean(raw)
        if t and not _PAGE_NO.match(t):
            size = max((s["size"] for s in spans if s["text"].strip()), default=0.0)
            mono = _style(spans, _MONO, _MONO_FONT)
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
    _mark_code_runs(blocks)
    figures = [r for r in _figures(page, images, drawings, tables) if not _textbox(r, blocks)]
    p = Page(page.number + 1, page.rect.width, page.rect.height, blocks, figures,
             tables, image_share=round(_image_share(page, images), 3), drawings=len(drawings))
    if not frames:
        return [p]
    taken: list[Block] = []
    subs = [_sub_page(p, _round(f), images, drawings, taken) for f in frames]
    rest = Page(p.no, p.width, p.height, [b for b in p.blocks if id(b) not in {id(t) for t in taken}],
                [f for f in p.figures if not any(_center_in(f, _round(r)) for r in frames)],
                [t for t in p.tables if not any(_center_in(t.bbox, _round(r)) for r in frames)])
    return subs + ([rest] if rest.blocks or rest.figures or rest.tables else [])


def _repeat_key(s: str) -> str:
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
                if where == "top" and any(c.isalpha() for c in b.text) and len(variants[key]) == 1:
                    p.running.append(b.text)
            else:
                keep.append(b)
        p.blocks = keep


def _strip_page_heads(pages: list[Page]) -> None:
    """Đầu / chân trang MANG SỐ TRANG mà không lặp đủ nhiều để _strip_running nhận ra (sách đổi đầu trang chẵn/lẻ và theo từng chương: "3 NoSQL Database 54", "3.7 NoSQL Not Only SQL 61")."""
    cands = []
    for p in pages:
        for b in p.blocks:
            if not _edge(b, p) or len(b.text) > PAGE_HEAD_MAX or b.text.endswith((".", "!", "?", ";", ":")):
                continue
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
    """Vùng hình lặp ở CÙNG VỊ TRÍ trên ≥ DECOR_SHARE số trang là trang trí của mẫu slide (logo, banner chứa tiêu đề) → bỏ, để chữ nằm trên đó (tiêu đề slide) trở về luồng chữ thường và được nhận là tiêu đề."""
    if len(pages) < REPEAT_MIN_PAGES:
        return
    def at_edge(r: BBox, p: Page) -> bool:
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        return (cy < DECOR_EDGE * p.height or cy > (1 - DECOR_EDGE) * p.height
                or cx < DECOR_EDGE / 2 * p.width or cx > (1 - DECOR_EDGE / 2) * p.width)

    decor = [[at_edge(r, p) and sum(any(_iou(r, s) >= DECOR_IOU for s in q.figures) for q in pages)
              >= DECOR_SHARE * len(pages) for r in p.figures] for p in pages]
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
        drawings = [pg.get_drawings() for pg in doc]
        frames = _handout_frames([_frame_candidates(pg, d) for pg, d in zip(doc, drawings)])
        borders = _handout_frames([_frame_candidates(pg, d, whole=True) for pg, d in zip(doc, drawings)])
        pages = [sp for pg, d, f, b in zip(doc, drawings, frames, borders) for sp in _read_page(pg, d, f, b)]
    sheets = {p.no for p in pages if p.sheet}
    if sheets:
        log.info("PDF dạng bản in handout: %d/%d trang, tách thành %d slide (trang %s)", len(sheets),
                 len({p.no for p in pages}), sum(1 for p in pages if p.sheet), sorted(sheets))
    for p in pages:
        if not p.sheet and p.no in sheets:
            p.blocks = [b for b in p.blocks if not (_edge(b, p) and len(b.text) <= PAGE_HEAD_MAX)]
    for group in ([p for p in pages if p.sheet], [p for p in pages if not p.sheet]):
        if group:
            _strip_running(group)
            _strip_page_heads(group)
            _drop_decorations(group)
    for p in pages:
        _flag(p)
    return pages


def render_page(src: str | bytes, page_no: int, dpi: int = 110) -> bytes:
    """Ảnh PNG của một trang (page_no bắt đầu từ 1) – để hiển thị khung tô và cho VLM nhìn."""
    with _open(src) as doc:
        return doc[page_no - 1].get_pixmap(dpi=dpi).tobytes("png")


def render_regions(src: str | bytes, regions: list[tuple[int, BBox]], dpi: int = 144,
                   max_side: int = 1280) -> list[bytes]:
    """Ảnh PNG của từng vùng (số trang, bbox tọa độ trang thật) – mở PDF MỘT lần cho cả học liệu."""
    out = []
    with _open(src) as doc:
        for page_no, (x0, y0, x1, y1) in regions:
            page = doc[page_no - 1]
            clip = pymupdf.Rect(x0, y0, x1, y1) & page.rect
            side = max(clip.width, clip.height, 1.0)
            zoom = min(dpi / 72, max_side / side)
            out.append(page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip).tobytes("png"))
    return out
