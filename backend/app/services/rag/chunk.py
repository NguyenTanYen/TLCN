"""Gom khối chữ của các trang (ingest.Page) thành ĐOẠN (Passage) – đơn vị để tìm kiếm và trích dẫn."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .ingest import BBox, Block, Page

TARGET = 400
MAX = 800
MIN = 80
HEAD_RATIO = 1.15
HEAD_MAX = 120
BOLD_HEAD_MAX = 80
NUMBERED_TITLE_MAX = 60
BOLD_HEAD_SIZE = 0.95
CAPTION_GAP = 40
OVERLAP_WORDS = 20
OVERLAP_CHARS = 150
OVERLAP_SENTENCE = MAX // 3
OVERLAP_SHARE = 4
TABLE_HEADER_SHARE = 2
CELL_KEEP_SHARE = 2
CONT_MARK = " (tiếp)"
CONT_LEAD = "… "
TITLE_ZONE = 0.25
SIZE_DEPTH = 3
CONTINUE_MAX = 300

_CAPTION = re.compile(r"^(hình|hinh|figure|fig\.?|bảng|bang|table|sơ đồ)\s*[\d.:–-]", re.I)
_CHAPTER = re.compile(r"^(chương|chuong|chapter|phần|phan|part|bài|bai|phụ lục|phu luc|appendix)\s+[\dIVXLC]+\b", re.I)
_AGENDA = re.compile(r"(?:^|\s)\d{1,2}\.\s+\S")
_SYMBOL_BULLET = re.compile(r"^\s*[•●○■□◆▪‣–\-*+]")
_BULLET = re.compile(r"^\s*(?:[•●○■□◆▪‣–\-*+]|\d{1,2}[.)]\s)")
_NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+\S")
_ROMAN = re.compile(r"^[IVXLC]+[.)]\s+\S")
_LETTER = re.compile(r"^[A-Z][.)]\s+\S")
_ORDER = ("chapter", "roman", "letter", "num1", "num2", "num3", "num4", "num5", "num6")
_SENT = re.compile(r"(?<=[.!?;])\s+")
_CONNECTOR = re.compile(r"(,|\b(là|và|của|các|những|như|gồm|bằng|với|cho|trong|để|nhằm|từ|theo|khi|nếu|mà|hoặc|hay|"
                        r"được|bởi|tới|đến|về|thì|có|tại|qua|trên|dưới|giữa|vào|sau|trước|thuộc|chứa|sử dụng|"
                        r"the|a|an|of|and|or|to|in|for|with|is|are|by|from|as|that|on|at|into|using|via|between|than))\s*$",
                        re.I)
_ABBR = re.compile(r"(?:^|[\s(.])(?:(?i:ThS|TS|PGS|GS|KS|BS|CN|TP|VD|v\.v|tr|No|Fig|Eq|e\.g|i\.e|etc|Mr|Mrs|Dr)|[A-ZĐ])\.$")


@dataclass
class Passage:
    page: int
    kind: str
    title: str
    body: str
    bboxes: list[BBox] = field(default_factory=list)
    caption: str = ""
    vlm_desc: str = ""
    breadcrumb: str = ""
    level: int = 0
    code: bool = False

    @property
    def text(self) -> str:
        """Chữ dùng để lập chỉ mục tìm kiếm."""
        return "\n".join(s for s in (self.breadcrumb or self.title, self.caption, self.body, self.vlm_desc) if s)

    @property
    def bbox(self) -> BBox:
        """Khung bao cả đoạn – để tô 'khúc cần đọc' trên ảnh trang."""
        xs0, ys0, xs1, ys1 = zip(*self.bboxes)
        return min(xs0), min(ys0), max(xs1), max(ys1)


def _inside(b: BBox, r: BBox) -> bool:
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    return r[0] <= cx <= r[2] and r[1] <= cy <= r[3]


def _near(b: BBox, r: BBox) -> bool:
    h_overlap = min(b[2], r[2]) - max(b[0], r[0]) > 0
    gap = max(b[1] - r[3], r[1] - b[3])
    return h_overlap and gap <= CAPTION_GAP


def sentences(text: str) -> list[str]:
    out: list[str] = []
    for piece in _SENT.split(text):
        if out and _ABBR.search(out[-1]):
            out[-1] += " " + piece
        elif piece:
            out.append(piece)
    return out


def _hard_split(s: str, limit: int = MAX) -> list[str]:
    """Câu dài hơn limit mà không có dấu câu (gạch đầu dòng liệt kê dài) → cắt theo từ, chồng lấn tối đa OVERLAP_WORDS từ (và không quá 1/4 phần, để giới hạn nhỏ không sinh ra quá nhiều phần lặp)."""
    words = [w[i:i + limit] for w in s.split() for i in range(0, len(w), limit)]
    parts, start = [], 0
    while start < len(words):
        end, size = start, 0
        while end < len(words) and size + len(words[end]) + 1 <= limit + 1:
            size += len(words[end]) + 1
            end += 1
        parts.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = max(start + 1, end - min(OVERLAP_WORDS, (end - start) // OVERLAP_SHARE))
    return parts


def _tail(s: str, limit: int) -> str:
    """Đuôi dài ≤ limit ký tự của s, bắt đầu ở ranh giới từ."""
    if len(s) <= limit:
        return s
    if limit <= 0:
        return ""
    cut = s[-limit:]
    i = cut.find(" ")
    return cut[i + 1:] if i >= 0 else ""


def _overlap(prev: str, nxt: str) -> str:
    """Phần lặp lại của prev ở đầu phần mới: cả câu nếu câu ngắn, nếu không thì OVERLAP_CHARS ký tự cuối; luôn chừa đủ chỗ cho câu tiếp theo trong MAX."""
    ov = prev if len(prev) <= OVERLAP_SENTENCE else _tail(prev, OVERLAP_CHARS)
    return _tail(ov, MAX - len(nxt) - 1)


def _split_long(text: str) -> list[str]:
    """Cắt theo câu thành các phần ≤ MAX; phần sau luôn mở đầu bằng phần chồng lấn của phần trước."""
    parts: list[str] = []
    cur: list[str] = []
    fresh = 0
    for s in sentences(text):
        if len(s) > MAX:
            if fresh:
                parts.append(" ".join(cur))
            pieces = _hard_split(s)
            parts += pieces
            carry = _tail(pieces[-1], OVERLAP_CHARS)
            cur = [carry] if carry else []
            fresh = 0
            continue
        if cur and len(" ".join(cur + [s])) > MAX:
            if fresh:
                parts.append(" ".join(cur))
            ov = _overlap(cur[-1], s)
            cur = [ov] if ov else []
            fresh = 0
        cur.append(s)
        fresh += 1
    if fresh:
        parts.append(" ".join(cur))
    return parts


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("|", "\\|")


def _cells(line: str) -> list[str]:
    """Nội dung các ô của một hàng Markdown (đã bỏ escape)."""
    cells: list[str] = []
    cur: list[str] = []
    escaped = False
    for ch in line:
        if escaped:
            cur.append(ch)
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == "|":
            cells.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    return cells[1:]


def _row(cells: list[str]) -> str:
    return "|" + "|".join(_esc(c) for c in cells) + "|"


def _split_row(line: str, budget: int) -> list[str]:
    """Hàng Markdown dài hơn budget → nhiều hàng con ĐÚNG CẤU TRÚC |..|..|: các ô ngắn (tổng ≤ nửa chỗ) lặp lại ở mọi hàng con, chỉ các ô dài bị chia; ô dài hết chữ thì để trống ở các hàng con sau."""
    cells = _cells(line)
    size = [len(_esc(c)) for c in cells]
    room = budget - (len(cells) + 1)
    keep, used = set(), 0
    for j in sorted(range(len(cells)), key=lambda j: size[j]):
        if used + size[j] + len(CONT_MARK) > room // CELL_KEEP_SHARE:
            break
        keep.add(j)
        used += size[j] + len(CONT_MARK)
    longs = [j for j in range(len(cells)) if j not in keep]
    limit = max(1, (room - used) // len(longs) - len(CONT_LEAD))
    pieces = {j: _hard_split(cells[j], max(1, limit // 2) if size[j] > len(cells[j]) else limit) for j in longs}
    n = max(len(v) for v in pieces.values())
    rows = []
    for i in range(n):
        row = []
        for j in range(len(cells)):
            if j in keep:
                row.append(cells[j] + (CONT_MARK if i and cells[j] else ""))
            elif i < len(pieces[j]):
                row.append((CONT_LEAD if i else "") + pieces[j][i])
            else:
                row.append("")
        rows.append(_row(row))
    return rows


def _table_parts(md: str, rows: list[BBox]) -> list[tuple[str, list[BBox]]]:
    """Bảng dài hơn MAX → cắt theo nhóm hàng; mỗi phần LẶP LẠI dòng header để giữ ngữ cảnh cột."""
    if len(md) <= MAX:
        return [(md, rows)]
    lines = md.split("\n")
    head, hrow = lines[:2], rows[:1]
    hlen = len("\n".join(head)) + 1
    if hlen > MAX // TABLE_HEADER_SHARE:
        head, hrow, hlen = [], [], 0
    body: list[tuple[str, list[BBox]]] = []
    for i, line in enumerate(lines[2:]):
        bb = rows[i + 1: i + 2]
        if hlen + len(line) > MAX:
            body += [(r, bb) for r in _split_row(line, MAX - hlen)]
        else:
            body.append((line, bb))
    parts: list[tuple[str, list[BBox]]] = []
    cur: list[str] = []
    cur_b: list[BBox] = []
    for line, bb in body:
        if cur and hlen + len("\n".join(cur + [line])) > MAX:
            parts.append(("\n".join(head + cur), hrow + cur_b))
            cur, cur_b = [], []
        cur.append(line)
        cur_b += bb
    if cur:
        parts.append(("\n".join(head + cur), hrow + cur_b))
    return parts


def _ends_sentence(s: str) -> bool:
    return s.rstrip().endswith((".", "!", "?", ":", ";"))


def _chapter_no(text: str) -> int | None:
    """Số của đề mục cấp chương ("Chapter 1 ..." → 1, "Chương IV" → 4); không phải đề mục chương → None."""
    m = _CHAPTER.match(text)
    if not m:
        return None
    token = text[m.end(1):].split()[0].rstrip(".:")
    if token.isdigit():
        return int(token)
    return _roman_value(token.upper()) if re.fullmatch(r"[IVXLCivxlc]+", token) else None


def _is_heading(b: Block, body_size: float) -> bool:
    if b.mono or body_size <= 0:
        return False
    if len(_AGENDA.findall(b.text)) >= 2:
        return False
    if _SYMBOL_BULLET.match(b.text):
        return False
    if len(b.text) <= HEAD_MAX and b.size >= HEAD_RATIO * body_size:
        return True
    return (b.bold and len(b.text) <= BOLD_HEAD_MAX and b.size >= BOLD_HEAD_SIZE * body_size
            and (not b.text.endswith((".", ",", ";")) or _numbered_title_with_period(b.text)))


def _numbered_title_with_period(text: str) -> bool:
    """Đề mục đánh số lỡ có dấu chấm cuối ("1."""
    if not (_NUMBERED.match(text) or _CHAPTER.match(text) or _ROMAN.match(text) or _LETTER.match(text)):
        return False
    title = text.split(None, 1)[1] if " " in text else ""
    return text.endswith(".") and len(text) <= NUMBERED_TITLE_MAX and not re.search(r"[.,;:!?]", title[:-1])


def _roman_value(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    for i, c in enumerate(s):
        v = vals[c]
        total += -v if i + 1 < len(s) and vals[s[i + 1]] > v else v
    return total


def _schemes(heads: list[Block]) -> dict[int, str | None]:
    """Kiểu đánh số của từng đề mục (theo id khối), xét theo THỨ TỰ trong tài liệu: "I." "V." "X." "L." "C." vừa là số La Mã vừa là chữ cái → là chữ cái nếu đề mục chữ cái liền trước là chữ đứng ngay trước nó (B."""
    out: dict[int, str | None] = {}
    last_letter, last_roman = "", 0
    for b in heads:
        t = b.text
        token = t.split(maxsplit=1)[0].rstrip(".)")
        scheme = None
        if _CHAPTER.match(t):
            scheme = "chapter"
        elif _ROMAN.match(t) and _LETTER.match(t):
            if last_letter and ord(token) == ord(last_letter) + 1:
                scheme = "letter"
            elif _roman_value(token) == last_roman + 1:
                scheme = "roman"
            else:
                scheme = "roman" if token == "I" else "letter"
        elif _ROMAN.match(t):
            scheme = "roman"
        elif _LETTER.match(t):
            scheme = "letter"
        elif m := _NUMBERED.match(t):
            scheme = f"num{min(m.group(1).count('.') + 1, 6)}"
        if scheme == "letter":
            last_letter = token
        elif scheme == "roman":
            last_roman = _roman_value(token)
        out[id(b)] = scheme
    return out


def _join_code(blocks: list[Block]) -> str:
    """Nối các khối code liền nhau bằng xuống dòng; dòng lùi vào (PyMuPDF tách thành khối riêng) được thêm thụt lề = (x của khối − x của khối lùi trái nhất) / bề rộng ký tự."""
    widths = sorted(b.char_w for b in blocks if b.char_w > 0)
    char_w = widths[len(widths) // 2] if widths else 0.0
    base = min(b.bbox[0] for b in blocks)
    out = []
    for b in blocks:
        pad = " " * round((b.bbox[0] - base) / char_w) if char_w else ""
        out.append("\n".join(pad + line for line in b.text.split("\n")))
    return "\n".join(out)


def _body_size(pages: list[Page]) -> float:
    """Cỡ chữ thân bài = cỡ chiếm NHIỀU KÝ TỰ nhất, không tính code (không dùng trung vị số khối: slide ít chữ thì tiêu đề chiếm nửa số khối; không tính code: slide nhiều code chữ nhỏ sẽ kéo mốc xuống)."""
    chars = Counter()
    for p in pages:
        for b in p.blocks:
            if not b.mono:
                chars[b.size] += len(b.text)
    return chars.most_common(1)[0][0] if chars else 0.0


class _Builder:
    """Duyệt các trang theo thứ tự, giữ chuỗi đề mục (stack) xuyên trang."""

    def __init__(self, pages: list[Page]):
        self.body_size = _body_size(pages)
        self.page_body = {id(p): self.local_body(p) for p in pages}
        self.page_title = {}
        for p in pages:
            sizes = [round(b.size) for b in p.blocks if not b.mono]
            top = max(sizes, default=0)
            self.page_title[id(p)] = next((id(b) for b in p.blocks if not b.mono and round(b.size) == top), None)
        heads = [b for p in pages for b in p.blocks if self.is_heading(b, p)]
        self.size_rank = {s: i + 1 for i, s in enumerate(sorted({round(b.size) for b in heads}, reverse=True))}
        self.schemes = _schemes(heads)
        present = set(self.schemes.values())
        self.scheme_level = {s: i + 1 for i, s in enumerate(s for s in _ORDER if s in present)}
        self.stack: list[tuple[int, str, bool]] = []
        self.page: Page | None = None
        self.page_out: list[Passage] = []
        self.buf: list[Block] = []
        self.pending: Passage | None = None

    def local_body(self, p: Page) -> float:
        """Mốc cỡ chữ thân bài của một trang: slide có ≥ 2 cỡ chữ → mốc riêng của trang; slide chỉ một cỡ chữ (slide chuyển chương "Chương 5."""
        sizes = {round(b.size) for b in p.blocks if not b.mono}
        if p.width > p.height and len(sizes) >= 2:
            return _body_size([p])
        return self.body_size

    def is_heading(self, b: Block, p: Page) -> bool:
        body = self.page_body[id(p)]
        if _is_heading(b, body):
            return True
        return (p.width > p.height and id(b) == self.page_title[id(p)] and b.bbox[1] < TITLE_ZONE * p.height
                and len(b.text) <= HEAD_MAX and (round(b.size) > round(body) or b.size >= HEAD_RATIO * self.body_size)
                and not _SYMBOL_BULLET.match(b.text) and len(_AGENDA.findall(b.text)) < 2)

    def ctx(self) -> tuple[str, str, int]:
        """(đề mục gần nhất, breadcrumb, cấp) đang hiệu lực ở vị trí hiện tại."""
        top = self.stack[0][1] if self.stack else None
        crumbs = [r for r in self.page.running if r != top] + [h for _, h, _ in self.stack]
        title = self.stack[-1][1] if self.stack else ""
        level = self.stack[-1][0] if self.stack else 0
        return title, " > ".join(crumbs), level

    def push_heading(self, b: Block, slide_title: bool = False, landscape: bool = False) -> None:
        scheme = self.schemes.get(id(b))
        if scheme:
            lv = self.scheme_level[scheme]
        else:
            base = max((lv for lv, _, numbered in self.stack if numbered), default=0)
            if slide_title:
                lv = base + 1
            elif landscape:
                rank = self.size_rank.get(round(b.size), len(self.size_rank))
                lv = base + 1 + min(rank, SIZE_DEPTH - 1)
            else:
                rank = self.size_rank.get(round(b.size), len(self.size_rank))
                lv = base + min(rank, SIZE_DEPTH)
        if scheme and scheme != "num1" and scheme.startswith("num"):
            major = int(b.text.split(".", 1)[0])
            for i, (_, text, _) in enumerate(self.stack):
                no = _chapter_no(text)
                if no is not None and no != major:
                    del self.stack[i:]
                    break
        while self.stack and self.stack[-1][0] >= lv:
            self.stack.pop()
        self.stack.append((lv, b.text, scheme is not None))

    def flush(self) -> None:
        if not self.buf:
            return
        title, crumb, lv = self.ctx()
        code = all(b.mono for b in self.buf)
        body = _join_code(self.buf) if code else " ".join(b.text for b in self.buf)
        self.page_out.append(Passage(self.page.no, "text", title, body,
                                     [b.bbox for b in self.buf], breadcrumb=crumb, level=lv, code=code))
        self.buf = []

    def add_block(self, b: Block) -> None:
        if self.buf and self.buf[0].mono != b.mono:
            self.flush()
        if b.mono:
            self.buf.append(b)
            return
        if len(b.text) > MAX:
            self.flush()
            title, crumb, lv = self.ctx()
            for part in _split_long(b.text):
                self.page_out.append(Passage(self.page.no, "text", title, part, [b.bbox], breadcrumb=crumb, level=lv))
            return
        size = len(" ".join(x.text for x in self.buf)) + 1 + len(b.text)
        if self.buf and (size > MAX or (size > TARGET and (_ends_sentence(self.buf[-1].text) or _BULLET.match(b.text)))):
            self.flush()
        self.buf.append(b)

    def split_objects(self, p: Page) -> tuple[list[Passage], list[Passage], list[Block]]:
        """Tách khối thuộc hình (chữ trong hình) và chú thích hình / bảng khỏi các khối chữ thường."""
        figs = [Passage(p.no, "figure", "", "", [r]) for r in p.figures]
        if p.scanned:
            figs.append(Passage(p.no, "figure", "", "", [(0.0, 0.0, p.width, p.height)]))
        tabs = [Passage(p.no, "table", "", t.markdown, [t.bbox]) for t in p.tables]
        text_blocks = []
        for b in p.blocks:
            fig = next((f for f in figs if _inside(b.bbox, f.bboxes[0])), None)
            if fig:
                fig.body = f"{fig.body} {b.text}".strip()
                fig.bboxes.append(b.bbox)
                continue
            obj = next((o for o in figs + tabs
                        if not o.caption and _CAPTION.match(b.text) and _near(b.bbox, o.bboxes[0])), None)
            if obj:
                obj.caption = b.text
                obj.bboxes.append(b.bbox)
                continue
            text_blocks.append(b)
        return figs, tabs, text_blocks

    def continue_sentence(self, text_blocks: list[Block]) -> None:
        """Câu vắt sang trang mới: nối phần còn thiếu (tới hết câu đầu tiên của trang này) vào cuối đoạn đang dở của trang trước."""
        pending, self.pending = self.pending, None
        if not pending or not text_blocks:
            return
        b = text_blocks[0]
        if self.is_heading(b, self.page) or b.mono:
            return
        first = next((c for c in b.text if c.isalpha()), "")
        if not (first.islower() or _CONNECTOR.search(pending.body)):
            return
        rest = sentences(b.text)[0]
        if len(rest) > CONTINUE_MAX:
            rest = rest[:CONTINUE_MAX].rsplit(" ", 1)[0] + " …"
        pending.body += " " + rest

    def title_first(self, p: Page, blocks: list[Block]) -> list[Block]:
        """Slide có dòng nhỏ NẰM TRÊN tiêu đề (tên phần "TIẾT 1 • BẢN CHẤT ETL", tên môn): xét tiêu đề trước – nếu không, các dòng đó bị gán vào đề mục của slide TRƯỚC."""
        t = next((b for b in blocks if id(b) == self.page_title[id(p)]), None)
        if p.width <= p.height or t is None or blocks[0] is t or not self.is_heading(t, p):
            return blocks
        above = blocks[:blocks.index(t)]
        if all(b.bbox[3] <= t.bbox[1] + 1 and len(b.text) <= HEAD_MAX for b in above):
            return [t] + [b for b in blocks if b is not t]
        return blocks

    def page_passages(self, p: Page) -> list[Passage]:
        self.page, self.page_out, self.buf = p, [], []
        figs, tabs, text_blocks = self.split_objects(p)
        text_blocks = self.title_first(p, text_blocks)
        self.continue_sentence(text_blocks)
        heads = [(float("-inf"), self.ctx())]
        landscape = p.width > p.height
        last_heading = False
        for b in text_blocks:
            last_heading = self.is_heading(b, p)
            if last_heading:
                self.flush()
                slide_title = landscape and len(heads) == 1 and b.bbox[1] < TITLE_ZONE * p.height
                self.push_heading(b, slide_title, landscape)
                heads.append((b.bbox[1], self.ctx()))
            else:
                self.add_block(b)
        self.flush()
        out = self.page_out
        if (len(out) >= 2 and len(out[-1].body) < MIN and out[-1].breadcrumb == out[-2].breadcrumb
                and out[-1].code == out[-2].code):
            last = out.pop()
            out[-1].body += ("\n" if last.code else " ") + last.body
            out[-1].bboxes += last.bboxes
        if (not landscape and out and not last_heading and out[-1].kind == "text" and not out[-1].code
                and out[-1].body and not out[-1].body.rstrip().endswith((".", "!", "?", ":", ";"))):
            self.pending = out[-1]
        for o in figs + tabs:
            o.title, o.breadcrumb, o.level = [c for y, c in heads if y <= o.bboxes[0][1]][-1]
        tabs = self.split_tables(p, tabs)
        if not out and not figs and not tabs and self.stack:
            hb = next((b for b in p.blocks if b.text == self.stack[-1][1]), None)
            if hb:
                title, crumb, lv = self.ctx()
                out.append(Passage(p.no, "text", title, "", [hb.bbox], breadcrumb=crumb, level=lv))
        return out + tabs + figs

    @staticmethod
    def split_tables(p: Page, tabs: list[Passage]) -> list[Passage]:
        result = []
        for o, t in zip(tabs, p.tables):
            parts = _table_parts(t.markdown, t.rows)
            if len(parts) == 1:
                result.append(o)
                continue
            for i, (md, bbs) in enumerate(parts):
                extra = o.bboxes[1:] if i == 0 else []
                result.append(Passage(p.no, "table", o.title, md, bbs + extra,
                                      caption=o.caption, breadcrumb=o.breadcrumb, level=o.level))
        return result


def build_passages(pages: list[Page]) -> list[Passage]:
    builder = _Builder(pages)
    out: list[Passage] = []
    for p in pages:
        ps = builder.page_passages(p)
        dx, dy = p.offset
        if dx or dy:
            for x in ps:
                x.bboxes = [tuple(round(v, 1) for v in (b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy)) for b in x.bboxes]
        out += ps
    return out
