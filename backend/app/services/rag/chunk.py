"""Gom khối chữ của các trang (ingest.Page) thành ĐOẠN (Passage) – đơn vị để tìm kiếm và trích dẫn.

Tiêu đề / đề mục:
  - khối ngắn có cỡ chữ ≥ HEAD_RATIO × cỡ chữ thân bài, HOẶC khối ngắn in đậm đứng riêng (đề mục giáo trình thường in đậm
    cùng cỡ chữ thân bài) – không tính khối code và câu in đậm kết thúc bằng . , ; (câu nhấn mạnh). Đề mục kết thúc bằng
    ":" hoặc "?" ("Ví dụ:", "Câu hỏi thảo luận?") vẫn là đề mục;
  - cỡ chữ thân bài = cỡ chiếm nhiều ký tự nhất trong tài liệu, KHÔNG tính khối code (slide nhiều code chữ nhỏ không được
    kéo mốc xuống làm gạch đầu dòng thành tiêu đề);
  - CẤP đề mục theo kiểu đánh số, thứ tự chuẩn: Chương > I. II. > A. B. > 1. > 1.1 > 1.1.1; chỉ các kiểu CÓ trong tài liệu
    được xếp cấp (tài liệu chỉ có "1.1" thì "1.1" là cấp 1). Đề mục không đánh số → (cấp của đề mục đánh số gần nhất) +
    thứ hạng cỡ chữ (làm tròn 1 pt, tối đa SIZE_DEPTH cấp) – nên tiêu đề slide "Ví dụ minh họa" nằm dưới "Chương 2" chứ
    không thay thế nó. Trang ngang (slide): đề mục đầu tiên ở 25% trên cùng là TIÊU ĐỀ SLIDE, luôn cùng một cấp dù
    PowerPoint tự thu nhỏ cỡ chữ cho vừa khung;
  - BREADCRUMB = đầu trang lặp lại (ingest.Page.running) + chuỗi đề mục cha → con, VD "Chương 3 > 3.2 Khóa ngoại";
    đề mục được giữ sang các trang sau cho tới khi gặp đề mục cùng cấp hoặc cấp cao hơn.
Đoạn chữ (kind="text"):
  - mang breadcrumb → không bị mất ngữ cảnh khi đứng một mình;
  - gộp các khối nhỏ liền nhau (gạch đầu dòng) tới khoảng TARGET ký tự – slide ít chữ thường thành đúng 1 đoạn;
  - khối dài hơn MAX ký tự được cắt theo câu (có xử lý từ viết tắt ThS., TS., TP., v.v.); phần sau luôn CHỒNG LẤN phần
    trước: cả câu cuối nếu câu ngắn, nếu không thì OVERLAP_CHARS ký tự cuối (cắt ở ranh giới từ);
  - khối CODE (font monospace hoặc nội dung giống code) không bao giờ bị cắt và không trộn với chữ thường; các dòng code
    liền nhau được gom thành một đoạn (code=True);
  - không bao giờ vượt qua ranh giới trang (trích dẫn luôn là "trang N").
Đoạn bảng (kind="table") – mỗi bảng kẻ ô (ingest.Page.tables): nội dung là Markdown giữ hàng/cột, kèm chú thích "Bảng ...";
  bảng dài hơn MAX được cắt theo nhóm hàng, mỗi phần lặp lại dòng header; một hàng quá dài được tách thành nhiều hàng con
  VẪN ĐÚNG CẤU TRÚC |..|..| (ô ngắn lặp lại, chỉ ô dài bị chia) – không bao giờ cắt ngang ký tự "|".
Đoạn hình (kind="figure") – mỗi vùng hình của trang (ingest.Page.figures) và mỗi trang scan:
  - chữ nằm TRONG vùng hình (nhãn ô của sơ đồ vẽ bằng shape) – chuyển hẳn sang đoạn hình, không lặp ở đoạn chữ;
  - chú thích gần hình ("Hình 3.2: ...") nằm ngay trên/dưới, cùng cột với vùng hình;
  - vlm_desc: để trống – giai đoạn VLM sẽ điền mô tả nội dung hình (chỉ đoạn hình, bảng đã là chữ).
Mọi đoạn chữ / bảng đều ≤ MAX ký tự (trừ code – không cắt; và chuỗi breadcrumb/chú thích đi kèm).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .ingest import BBox, Block, Page

TARGET = 400        # ký tự: gộp khối nhỏ tới khoảng này thì chốt đoạn
MAX = 800           # ký tự: khối dài hơn thì cắt theo câu (trừ code)
MIN = 80            # ký tự: đoạn cuối trang ngắn hơn thì nhập vào đoạn trước (cùng tiêu đề)
HEAD_RATIO = 1.15   # khối có cỡ chữ ≥ 1,15 × cỡ chữ thân bài của tài liệu và ngắn → tiêu đề / đề mục
HEAD_MAX = 120      # ký tự tối đa của một tiêu đề
BOLD_HEAD_MAX = 80  # ký tự tối đa của đề mục chỉ nhận ra nhờ in đậm
BOLD_HEAD_SIZE = 0.95  # đề mục in đậm có cỡ chữ ≥ 0,95 × thân bài (không nhận chữ in đậm nhỏ như chú thích)
CAPTION_GAP = 40    # pt: chú thích phải nằm cách vùng hình / bảng không quá khoảng này
OVERLAP_WORDS = 20  # cắt ép theo từ: hai phần liền nhau lặp lại tối đa 20 từ
OVERLAP_CHARS = 150  # cắt theo câu mà câu cuối dài: phần sau lặp lại ~150 ký tự cuối của phần trước
OVERLAP_SENTENCE = MAX // 3  # câu cuối ngắn hơn ngần này thì lặp lại cả câu
OVERLAP_SHARE = 4   # cắt ép theo từ: phần chồng lấn không quá 1/4 số từ của phần
TABLE_HEADER_SHARE = 2  # header bảng dài hơn MAX/2 thì các phần không kèm header
CELL_KEEP_SHARE = 2     # tách hàng bảng: các ô ngắn được giữ nguyên ở mọi hàng con nếu tổng ≤ 1/2 chỗ
CONT_MARK = " (tiếp)"   # tách hàng bảng: ô ngắn ở hàng con thứ 2 trở đi
CONT_LEAD = "… "        # tách hàng bảng: phần tiếp theo của ô dài
TITLE_ZONE = 0.25   # trang ngang (slide): đề mục đầu tiên nằm trong 25% trên cùng là TIÊU ĐỀ SLIDE
SIZE_DEPTH = 3      # đề mục không đánh số: tối đa 3 cấp theo cỡ chữ dưới đề mục đánh số gần nhất
CONTINUE_MAX = 300  # câu vắt trang: nối tối đa 300 ký tự đầu trang sau vào đoạn cuối trang trước

_CAPTION = re.compile(r"^(hình|hinh|figure|fig\.?|bảng|bang|table|sơ đồ)\s*[\d.:–-]", re.I)
_CHAPTER = re.compile(r"^(chương|chuong|chapter|phần|phan|part|bài|bai)\s+[\dIVXLC]+\b", re.I)
_NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+\S")
_ROMAN = re.compile(r"^[IVXLC]+[.)]\s+\S")
_LETTER = re.compile(r"^[A-Z][.)]\s+\S")
# thứ tự cấp chuẩn của các kiểu đánh số
_ORDER = ("chapter", "roman", "letter", "num1", "num2", "num3", "num4", "num5", "num6")
_SENT = re.compile(r"(?<=[.!?;])\s+")
# đoạn dừng ở từ nối / dấu phẩy → câu chắc chắn còn tiếp (dùng cho câu vắt trang mà nửa sau mở đầu bằng chữ hoa).
# Cố ý KHÔNG có "dùng" ("người dùng" hay đứng cuối gạch đầu dòng). Giới hạn đã biết: câu dừng ở danh từ thường
# ("... biểu diễn thực thể" + "Student và Course ...") không nhận ra được bằng luật – để lại cho dữ liệu thật quyết định.
_CONNECTOR = re.compile(r"(,|\b(là|và|của|các|những|như|gồm|bằng|với|cho|trong|để|nhằm|từ|theo|khi|nếu|mà|hoặc|hay|"
                        r"được|bởi|tới|đến|về|thì|có|tại|qua|trên|dưới|giữa|vào|sau|trước|thuộc|chứa|sử dụng|"
                        r"the|a|an|of|and|or|to|in|for|with|is|are|by|from|as|that|on|at|into|using|via|between|than))\s*$",
                        re.I)
# câu kết thúc bằng từ viết tắt / chữ cái đầu tên → chưa phải hết câu
#   từ viết tắt so khớp KHÔNG phân biệt hoa thường (ThS / Ths / ths, PGS / pgs); riêng chữ cái đơn chỉ nhận chữ HOA
#   (câu kết thúc bằng "... cột a." vẫn được cắt)
_ABBR = re.compile(r"(?:^|[\s(.])(?:(?i:ThS|TS|PGS|GS|KS|BS|CN|TP|VD|v\.v|tr|No|Fig|Eq|e\.g|i\.e|etc|Mr|Mrs|Dr)|[A-ZĐ])\.$")


@dataclass
class Passage:
    page: int
    kind: str                       # "text" | "table" | "figure"
    title: str                      # đề mục gần nhất
    body: str
    bboxes: list[BBox] = field(default_factory=list)   # các khối tạo nên đoạn (bảng / hình: vùng bảng / hình trước tiên)
    caption: str = ""
    vlm_desc: str = ""
    breadcrumb: str = ""            # "Chương 3 > 3.2 Khóa ngoại"
    level: int = 0                  # cấp của đề mục gần nhất (0 = chưa có đề mục)
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


# ---------------------------------------------------------------- cắt chữ


def _inside(b: BBox, r: BBox) -> bool:
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    return r[0] <= cx <= r[2] and r[1] <= cy <= r[3]


def _near(b: BBox, r: BBox) -> bool:
    h_overlap = min(b[2], r[2]) - max(b[0], r[0]) > 0  # cùng cột: tài liệu 2 cột không ghép nhầm chú thích sang cột kia
    gap = max(b[1] - r[3], r[1] - b[3])          # khoảng cách theo chiều dọc (âm = chồng nhau)
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
    """Câu dài hơn limit mà không có dấu câu (gạch đầu dòng liệt kê dài) → cắt theo từ, chồng lấn tối đa OVERLAP_WORDS
    từ (và không quá 1/4 phần, để giới hạn nhỏ không sinh ra quá nhiều phần lặp). Một "từ" tự nó dài hơn limit (URL,
    chuỗi base64, mã lỗi liền) bị cắt cưỡng chế theo ký tự."""
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
    """Phần lặp lại của prev ở đầu phần mới: cả câu nếu câu ngắn, nếu không thì OVERLAP_CHARS ký tự cuối; luôn chừa đủ chỗ
    cho câu tiếp theo trong MAX."""
    ov = prev if len(prev) <= OVERLAP_SENTENCE else _tail(prev, OVERLAP_CHARS)
    return _tail(ov, MAX - len(nxt) - 1)


def _split_long(text: str) -> list[str]:
    """Cắt theo câu thành các phần ≤ MAX; phần sau luôn mở đầu bằng phần chồng lấn của phần trước."""
    parts: list[str] = []
    cur: list[str] = []
    fresh = 0                          # số câu MỚI trong cur (không tính phần chồng lấn)
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


# ---------------------------------------------------------------- bảng


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("|", "\\|")


def _cells(line: str) -> list[str]:
    """Nội dung các ô của một hàng Markdown (đã bỏ escape). Đọc từng ký tự: "\\x" là ký tự x, "|" là dấu phân cách."""
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
    return cells[1:]                                  # phần trước dấu "|" đầu tiên luôn rỗng


def _row(cells: list[str]) -> str:
    return "|" + "|".join(_esc(c) for c in cells) + "|"


def _split_row(line: str, budget: int) -> list[str]:
    """Hàng Markdown dài hơn budget → nhiều hàng con ĐÚNG CẤU TRÚC |..|..|: các ô ngắn (tổng ≤ nửa chỗ) lặp lại ở mọi hàng
    con, chỉ các ô dài bị chia; ô dài hết chữ thì để trống ở các hàng con sau. Chia trên nội dung ĐÃ BỎ escape rồi escape
    lại → không bao giờ cắt đôi "\\|".
    Hàng con thứ 2 trở đi được ĐÁNH DẤU là phần tiếp theo (ô ngắn thêm CONT_MARK, ô dài mở đầu bằng "… ") để LLM hiểu
    đó là cùng một bản ghi bị chia, không phải nhiều bản ghi trùng tên."""
    cells = _cells(line)
    size = [len(_esc(c)) for c in cells]
    room = budget - (len(cells) + 1)                 # trừ các ký tự "|"
    keep, used = set(), 0
    for j in sorted(range(len(cells)), key=lambda j: size[j]):
        if used + size[j] + len(CONT_MARK) > room // CELL_KEEP_SHARE:
            break
        keep.add(j)
        used += size[j] + len(CONT_MARK)             # chừa chỗ cho dấu "(tiếp)" ở hàng con sau
    longs = [j for j in range(len(cells)) if j not in keep]
    limit = max(1, (room - used) // len(longs) - len(CONT_LEAD))
    # ô có "\" hoặc "|" dài thêm tối đa gấp đôi khi escape → chia nhỏ hơn cho chắc
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
    """Bảng dài hơn MAX → cắt theo nhóm hàng; mỗi phần LẶP LẠI dòng header để giữ ngữ cảnh cột.
    Trả về (markdown, khung các hàng của phần đó)."""
    if len(md) <= MAX:
        return [(md, rows)]
    lines = md.split("\n")
    head, hrow = lines[:2], rows[:1]
    hlen = len("\n".join(head)) + 1
    if hlen > MAX // TABLE_HEADER_SHARE:                              # header tự nó đã quá dài → các phần không kèm header
        head, hrow, hlen = [], [], 0
    body: list[tuple[str, list[BBox]]] = []
    for i, line in enumerate(lines[2:]):
        bb = rows[i + 1: i + 2]
        if hlen + len(line) > MAX:                   # một hàng quá dài (ô chứa cả đoạn văn) → các hàng con
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


# ---------------------------------------------------------------- đề mục


def _is_heading(b: Block, body_size: float) -> bool:
    if b.mono or body_size <= 0:
        return False
    if len(b.text) <= HEAD_MAX and b.size >= HEAD_RATIO * body_size:
        return True
    # TODO(slide thật): câu nhấn mạnh in đậm ngắn kết thúc bằng ":" vẫn bị nhận là đề mục – nếu gặp, thêm điều kiện khối
    # đứng riêng một dòng và cách đoạn bên dưới một khoảng (gap) như đề mục thật
    return (b.bold and len(b.text) <= BOLD_HEAD_MAX and not b.text.endswith((".", ",", ";"))
            and b.size >= BOLD_HEAD_SIZE * body_size)


def _roman_value(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    for i, c in enumerate(s):
        v = vals[c]
        total += -v if i + 1 < len(s) and vals[s[i + 1]] > v else v
    return total


def _schemes(heads: list[Block]) -> dict[int, str | None]:
    """Kiểu đánh số của từng đề mục (theo id khối), xét theo THỨ TỰ trong tài liệu: "I." "V." "X." "L." "C." vừa là số La
    Mã vừa là chữ cái → là chữ cái nếu đề mục chữ cái liền trước là chữ đứng ngay trước nó (B. → C.), là số La Mã nếu số
    La Mã liền trước nhỏ hơn đúng 1 (IV. → V.); không rõ thì "I." là La Mã, còn lại là chữ cái."""
    out: dict[int, str | None] = {}
    last_letter, last_roman = "", 0
    for b in heads:
        t = b.text
        token = t.split(maxsplit=1)[0].rstrip(".)")
        scheme = None
        if _CHAPTER.match(t):
            scheme = "chapter"
        elif _ROMAN.match(t) and _LETTER.match(t):        # một ký tự nhập nhằng
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
    """Nối các khối code liền nhau bằng xuống dòng; dòng lùi vào (PyMuPDF tách thành khối riêng) được thêm thụt lề =
    (x của khối − x của khối lùi trái nhất) / bề rộng ký tự."""
    widths = sorted(b.char_w for b in blocks if b.char_w > 0)
    char_w = widths[len(widths) // 2] if widths else 0.0
    base = min(b.bbox[0] for b in blocks)
    out = []
    for b in blocks:
        pad = " " * round((b.bbox[0] - base) / char_w) if char_w else ""
        out.append("\n".join(pad + line for line in b.text.split("\n")))
    return "\n".join(out)


def _body_size(pages: list[Page]) -> float:
    """Cỡ chữ thân bài = cỡ chiếm NHIỀU KÝ TỰ nhất, không tính code (không dùng trung vị số khối: slide ít chữ thì tiêu đề
    chiếm nửa số khối; không tính code: slide nhiều code chữ nhỏ sẽ kéo mốc xuống)."""
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
        heads = [b for p in pages for b in p.blocks if _is_heading(b, self.body_size)]
        # cỡ chữ làm tròn tới 1 pt: PDF hay sinh cỡ lẻ (17,9 / 18,0) cho cùng một kiểu đề mục
        self.size_rank = {s: i + 1 for i, s in enumerate(sorted({round(b.size) for b in heads}, reverse=True))}
        self.schemes = _schemes(heads)
        present = set(self.schemes.values())
        self.scheme_level = {s: i + 1 for i, s in enumerate(s for s in _ORDER if s in present)}
        self.stack: list[tuple[int, str, bool]] = []    # chuỗi đề mục (cấp, chữ, có đánh số) đang hiệu lực
        self.page: Page | None = None
        self.page_out: list[Passage] = []
        self.buf: list[Block] = []
        self.pending: Passage | None = None             # đoạn cuối trang trước kết thúc giữa câu

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
            # đề mục không đánh số nằm DƯỚI đề mục đánh số gần nhất: không được đẩy "Chương 2" ra khỏi breadcrumb dù
            # cùng cỡ chữ với nó
            base = max((lv for lv, _, numbered in self.stack if numbered), default=0)
            if slide_title:
                # tiêu đề slide luôn cùng một cấp dù PowerPoint tự thu nhỏ chữ cho vừa khung (40 → 36 → 32 pt):
                # slide sau thay slide trước chứ không lồng vào nhau
                lv = base + 1
            elif landscape:                              # đề mục phụ trong slide: luôn dưới tiêu đề slide
                rank = self.size_rank.get(round(b.size), len(self.size_rank))
                lv = base + 1 + min(rank, SIZE_DEPTH - 1)
            else:
                rank = self.size_rank.get(round(b.size), len(self.size_rank))
                lv = base + min(rank, SIZE_DEPTH)
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
        if self.buf and self.buf[0].mono != b.mono:          # không trộn code với chữ thường
            self.flush()
        if b.mono:                                           # code: gom các dòng liền nhau, không cắt, không giới hạn
            self.buf.append(b)
            return
        if len(b.text) > MAX:
            self.flush()
            title, crumb, lv = self.ctx()
            for part in _split_long(b.text):
                self.page_out.append(Passage(self.page.no, "text", title, part, [b.bbox], breadcrumb=crumb, level=lv))
            return
        if self.buf and len(" ".join(x.text for x in self.buf)) + len(b.text) > TARGET:
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
        """Câu vắt sang trang mới: nối phần còn thiếu (tới hết câu đầu tiên của trang này) vào cuối đoạn đang dở của
        trang trước. Chỉ nối CHỮ – khung tô của mỗi đoạn vẫn nằm trên trang của nó, trích dẫn vẫn đúng "trang N"."""
        pending, self.pending = self.pending, None
        if not pending or not text_blocks:
            return
        b = text_blocks[0]
        if _is_heading(b, self.body_size) or b.mono:
            return
        # trang sau mở đầu bằng chữ thường → chắc chắn là câu nối tiếp; mở đầu chữ HOA (tên riêng "Oracle", "SQL Server")
        # thì chỉ nối khi trang trước dừng ở từ nối / dấu phẩy ("... hiện nay là") – nếu không, chữ hoa thường là câu mới
        # (gạch đầu dòng cuối trang không có dấu chấm như "• Khóa ngoại" không được nuốt câu đầu trang sau)
        first = next((c for c in b.text if c.isalpha()), "")
        if not (first.islower() or _CONNECTOR.search(pending.body)):
            return
        rest = sentences(b.text)[0]
        if len(rest) > CONTINUE_MAX:                       # câu rất dài: chỉ lấy phần đầu, cắt ở ranh giới từ
            rest = rest[:CONTINUE_MAX].rsplit(" ", 1)[0] + " …"
        pending.body += " " + rest

    def page_passages(self, p: Page) -> list[Passage]:
        self.page, self.page_out, self.buf = p, [], []
        figs, tabs, text_blocks = self.split_objects(p)
        self.continue_sentence(text_blocks)
        heads = [(float("-inf"), self.ctx())]      # (tung độ, ngữ cảnh có hiệu lực từ đó) – để gán đề mục cho hình / bảng
        landscape = p.width > p.height
        last_heading = False
        for b in text_blocks:
            last_heading = _is_heading(b, self.body_size)
            if last_heading:
                self.flush()
                slide_title = landscape and len(heads) == 1 and b.bbox[1] < TITLE_ZONE * p.height
                self.push_heading(b, slide_title, landscape)
                heads.append((b.bbox[1], self.ctx()))
            else:
                self.add_block(b)
        self.flush()
        out = self.page_out
        # đoạn cuối quá ngắn → nhập vào đoạn trước nếu cùng ngữ cảnh và cùng loại (code / chữ)
        if (len(out) >= 2 and len(out[-1].body) < MIN and out[-1].breadcrumb == out[-2].breadcrumb
                and out[-1].code == out[-2].code):
            last = out.pop()
            out[-1].body += ("\n" if last.code else " ") + last.body
            out[-1].bboxes += last.bboxes
        # trang dọc (giáo trình) kết thúc giữa câu → chờ trang sau nối tiếp; slide (trang ngang) là đơn vị độc lập
        if (not landscape and out and not last_heading and out[-1].kind == "text" and not out[-1].code
                and out[-1].body and not out[-1].body.rstrip().endswith((".", "!", "?", ":", ";"))):
            self.pending = out[-1]
        for o in figs + tabs:
            o.title, o.breadcrumb, o.level = [c for y, c in heads if y <= o.bboxes[0][1]][-1]
        tabs = self.split_tables(p, tabs)
        # trang chỉ có tiêu đề (slide chuyển chương, slide "Ví dụ" toàn hình) vẫn tìm được theo tiêu đề
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
            for i, (md, bbs) in enumerate(parts):     # khung chú thích chỉ đi cùng phần đầu
                extra = o.bboxes[1:] if i == 0 else []
                result.append(Passage(p.no, "table", o.title, md, bbs + extra,
                                      caption=o.caption, breadcrumb=o.breadcrumb, level=o.level))
        return result


def build_passages(pages: list[Page]) -> list[Passage]:
    builder = _Builder(pages)
    out: list[Passage] = []
    for p in pages:
        out += builder.page_passages(p)
    return out
