"""Gom khối chữ của các trang (ingest.Page) thành ĐOẠN (Passage) – đơn vị để tìm kiếm và trích dẫn.

Tiêu đề / đề mục:
  - khối ngắn có cỡ chữ ≥ HEAD_RATIO × cỡ chữ thân bài, HOẶC khối ngắn in đậm đứng riêng (đề mục giáo trình thường in đậm
    cùng cỡ chữ thân bài) – không tính khối code và câu in đậm kết thúc bằng dấu câu (câu nhấn mạnh, không phải đề mục);
  - CẤP đề mục: "Chương 3" → 1; đánh số "3.2" → 2, "3.2.1" → 3; không đánh số → (cấp của đề mục đánh số gần nhất) +
    thứ hạng cỡ chữ của các tiêu đề – nên tiêu đề slide "Ví dụ minh họa" nằm dưới "Chương 2" chứ không thay thế nó;
  - BREADCRUMB = đầu trang lặp lại (ingest.Page.running) + chuỗi đề mục cha → con, VD "Chương 3 > 3.2 Khóa ngoại";
    đề mục được giữ sang các trang sau cho tới khi gặp đề mục cùng cấp hoặc cấp cao hơn.
Đoạn chữ (kind="text"):
  - mang breadcrumb → không bị mất ngữ cảnh khi đứng một mình;
  - gộp các khối nhỏ liền nhau (gạch đầu dòng) tới khoảng TARGET ký tự – slide ít chữ thường thành đúng 1 đoạn;
  - khối dài hơn MAX ký tự được cắt theo câu (có xử lý từ viết tắt ThS., TS., TP., v.v.), hai đoạn liền nhau CHỒNG LẤN
    1 câu để không cắt đôi định nghĩa;
  - khối CODE (font monospace: câu lệnh SQL, hàm Python) không bao giờ bị cắt và không trộn với chữ thường; các dòng code
    liền nhau được gom thành một đoạn (code=True);
  - không bao giờ vượt qua ranh giới trang (trích dẫn luôn là "trang N").
Đoạn bảng (kind="table") – mỗi bảng kẻ ô (ingest.Page.tables): nội dung là Markdown giữ hàng/cột, kèm chú thích "Bảng ...";
  bảng dài hơn MAX được cắt theo nhóm hàng, mỗi phần lặp lại dòng header, khung tô là các hàng của phần đó.
Mọi đoạn chữ / bảng đều ≤ MAX ký tự (trừ code – không cắt; và chuỗi breadcrumb/chú thích đi kèm).
Đoạn hình (kind="figure") – mỗi vùng hình của trang (ingest.Page.figures) và mỗi trang scan:
  - chữ nằm TRONG vùng hình (nhãn ô của sơ đồ vẽ bằng shape) – chuyển hẳn sang đoạn hình, không lặp ở đoạn chữ;
  - chú thích gần hình ("Hình 3.2: ...") nằm ngay trên/dưới, cùng cột với vùng hình;
  - vlm_desc: để trống – giai đoạn VLM sẽ điền mô tả nội dung hình (chỉ đoạn hình, bảng đã là chữ).
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
CAPTION_GAP = 40    # pt: chú thích phải nằm cách vùng hình / bảng không quá khoảng này
OVERLAP_WORDS = 20  # cắt ép theo từ: hai phần liền nhau lặp lại 20 từ

_CAPTION = re.compile(r"^(hình|hinh|figure|fig\.?|bảng|bang|table|sơ đồ)\s*[\d.:–-]", re.I)
_CHAPTER = re.compile(r"^(chương|chuong|chapter|phần|phan|part|bài|bai)\s+[\dIVXLC]+\b", re.I)
_NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+\S")
_SENT = re.compile(r"(?<=[.!?;])\s+")
# câu kết thúc bằng từ viết tắt / chữ cái đầu tên → chưa phải hết câu
_ABBR = re.compile(r"(?:^|[\s(.])(?:ThS|TS|PGS|GS|KS|BS|CN|TP|Tp|VD|Vd|vd|v\.v|tr|Tr|No|Fig|Eq|e\.g|i\.e|etc|Mr|Mrs|Dr|[A-ZĐ])\.$")


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
    """Câu dài hơn limit mà không có dấu câu (gạch đầu dòng liệt kê dài) → cắt theo từ, chồng lấn OVERLAP_WORDS từ.
    Một "từ" tự nó dài hơn limit (URL, chuỗi base64, mã lỗi liền) bị cắt cưỡng chế theo ký tự."""
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
        start = max(start + 1, end - OVERLAP_WORDS)
    return parts


def _split_long(text: str) -> list[str]:
    """Cắt theo câu thành các phần ≤ MAX, phần sau lặp lại câu cuối của phần trước (nếu câu đó ngắn)."""
    parts, cur = [], []
    for s in sentences(text):
        if len(s) > MAX:
            if cur:
                parts.append(" ".join(cur))
            parts += _hard_split(s)
            cur = []
            continue
        if cur and len(" ".join(cur + [s])) > MAX:
            parts.append(" ".join(cur))
            last = cur[-1]
            cur = [last] if len(last) <= MAX // 3 and len(last) + 1 + len(s) <= MAX else []
        cur.append(s)
    if cur:
        parts.append(" ".join(cur))
    return parts


def _table_parts(md: str, rows: list[BBox]) -> list[tuple[str, list[BBox]]]:
    """Bảng dài hơn MAX → cắt theo nhóm hàng; mỗi phần LẶP LẠI dòng header để giữ ngữ cảnh cột.
    Trả về (markdown, khung các hàng của phần đó)."""
    lines = md.split("\n")
    if len(md) <= MAX or len(lines) <= 3:
        return [(md, rows)]
    head, body = lines[:2], lines[2:]
    hrow = rows[:1]
    hlen = len("\n".join(head)) + 1
    parts: list[tuple[str, list[BBox]]] = []
    cur, cur_b = [], []
    for i, line in enumerate(body):
        bb = rows[i + 1: i + 2]
        if cur and hlen + len("\n".join(cur + [line])) > MAX:
            parts.append(("\n".join(head + cur), hrow + cur_b))
            cur, cur_b = [], []
        if hlen + len(line) > MAX:                   # một hàng quá dài (ô chứa cả đoạn văn): cắt ép ...
            if hlen <= MAX // 2:                     # ... trong phần chỗ còn lại sau header, mỗi phần vẫn kèm header
                parts += [("\n".join(head + [x]), hrow + bb) for x in _hard_split(line, MAX - hlen)]
            else:                                    # header tự nó đã quá dài → bỏ header
                parts += [(x, bb) for x in _hard_split(line)]
            continue
        cur.append(line); cur_b += bb
    if cur:
        parts.append(("\n".join(head + cur), hrow + cur_b))
    return parts


def _is_heading(b: Block, body_size: float) -> bool:
    if b.mono or body_size <= 0:
        return False
    if len(b.text) <= HEAD_MAX and b.size >= HEAD_RATIO * body_size:
        return True
    return b.bold and len(b.text) <= BOLD_HEAD_MAX and not b.text.endswith((".", ",", ";")) and b.size >= 0.95 * body_size


def _numbered_level(text: str) -> int:
    """Cấp theo cách đánh số: "Chương 3" → 1, "3.2" → 2, "3.2.1" → 3; không đánh số → 0."""
    if _CHAPTER.match(text):
        return 1
    m = _NUMBERED.match(text)
    return m.group(1).count(".") + 1 if m else 0


def build_passages(pages: list[Page]) -> list[Passage]:
    # cỡ chữ thân bài = cỡ chiếm NHIỀU KÝ TỰ nhất (không dùng trung vị số khối: slide ít chữ thì tiêu đề chiếm nửa số khối)
    chars = Counter()
    for p in pages:
        for b in p.blocks:
            chars[b.size] += len(b.text)
    body_size = chars.most_common(1)[0][0] if chars else 0.0
    head_sizes = sorted({b.size for p in pages for b in p.blocks if _is_heading(b, body_size)}, reverse=True)
    size_rank = {s: i + 1 for i, s in enumerate(head_sizes)}

    out: list[Passage] = []
    stack: list[tuple[int, str, bool]] = []     # chuỗi đề mục (cấp, chữ, có đánh số) đang hiệu lực
    for p in pages:
        def ctx() -> tuple[str, str, int]:
            crumbs = [r for r in p.running if not stack or r != stack[0][1]] + [h for _, h, _ in stack]
            return (stack[-1][1] if stack else ""), " > ".join(crumbs), (stack[-1][0] if stack else 0)

        figs = [Passage(p.no, "figure", "", "", [r]) for r in p.figures]
        if p.scanned:
            figs.append(Passage(p.no, "figure", "", "", [(0.0, 0.0, p.width, p.height)]))
        tabs = [Passage(p.no, "table", "", t.markdown, [t.bbox]) for t in p.tables]
        text_blocks = []
        for b in p.blocks:
            fig = next((f for f in figs if _inside(b.bbox, f.bboxes[0])), None)
            if fig:
                fig.body = f"{fig.body} {b.text}".strip(); fig.bboxes.append(b.bbox)
                continue
            obj = next((o for o in figs + tabs if not o.caption and _CAPTION.match(b.text) and _near(b.bbox, o.bboxes[0])), None)
            if obj:
                obj.caption = b.text; obj.bboxes.append(b.bbox)
                continue
            text_blocks.append(b)

        page_out: list[Passage] = []
        buf: list[Block] = []
        heads = [(float("-inf"), ctx())]    # (tung độ, ngữ cảnh có hiệu lực từ đó) – để gán đề mục cho hình / bảng

        def flush():
            if buf:
                title, crumb, lv = ctx()
                page_out.append(Passage(p.no, "text", title, " ".join(b.text for b in buf), [b.bbox for b in buf],
                                        breadcrumb=crumb, level=lv, code=all(b.mono for b in buf)))
                buf.clear()

        for b in text_blocks:
            if _is_heading(b, body_size):
                flush()
                lv = _numbered_level(b.text)
                if not lv:
                    # đề mục không đánh số (tiêu đề slide, "Ví dụ minh họa") nằm DƯỚI đề mục đánh số gần nhất: không
                    # được đẩy "Chương 2" ra khỏi breadcrumb dù cùng cỡ chữ với nó
                    base = max((l for l, _, num in stack if num), default=0)
                    lv = base + size_rank.get(b.size, len(size_rank) + 1)
                while stack and stack[-1][0] >= lv:
                    stack.pop()
                stack.append((lv, b.text, _numbered_level(b.text) > 0))
                heads.append((b.bbox[1], ctx()))
                continue
            if buf and buf[0].mono != b.mono:          # không trộn code với chữ thường
                flush()
            if b.mono:                                 # code: gom các dòng liền nhau, không cắt, không giới hạn độ dài
                buf.append(b)
                continue
            if len(b.text) > MAX:
                flush()
                title, crumb, lv = ctx()
                page_out += [Passage(p.no, "text", title, part, [b.bbox], breadcrumb=crumb, level=lv)
                             for part in _split_long(b.text)]
                continue
            if buf and len(" ".join(x.text for x in buf)) + len(b.text) > TARGET:
                flush()
            buf.append(b)
        flush()
        # đoạn cuối quá ngắn → nhập vào đoạn trước nếu cùng ngữ cảnh và cùng loại (code / chữ)
        if (len(page_out) >= 2 and len(page_out[-1].body) < MIN and page_out[-1].breadcrumb == page_out[-2].breadcrumb
                and page_out[-1].code == page_out[-2].code):
            last = page_out.pop()
            page_out[-1].body += " " + last.body; page_out[-1].bboxes += last.bboxes
        for o in figs + tabs:
            o.title, o.breadcrumb, o.level = [c for y, c in heads if y <= o.bboxes[0][1]][-1]
        split_tabs = []
        for o, t in zip(tabs, p.tables):
            parts = _table_parts(t.markdown, t.rows)
            if len(parts) == 1:
                split_tabs.append(o)
                continue
            for i, (md, bbs) in enumerate(parts):     # khung chú thích chỉ đi cùng phần đầu
                split_tabs.append(Passage(p.no, "table", o.title, md, bbs + (o.bboxes[1:] if i == 0 else []),
                                          caption=o.caption, breadcrumb=o.breadcrumb, level=o.level))
        tabs = split_tabs
        # trang chỉ có tiêu đề (slide chuyển chương, slide "Ví dụ" toàn hình) vẫn tìm được theo tiêu đề
        if not page_out and not figs and not tabs and stack and any(b.text == stack[-1][1] for b in p.blocks):
            hb = next(b for b in p.blocks if b.text == stack[-1][1])
            title, crumb, lv = ctx()
            page_out.append(Passage(p.no, "text", title, "", [hb.bbox], breadcrumb=crumb, level=lv))
        out += page_out + tabs + figs
    return out
