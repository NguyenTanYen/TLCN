"""Từ điển đồng nghĩa theo MÔN HỌC cho tìm kiếm học liệu (bước 7) – mở rộng câu truy vấn, KHÔNG đụng chỉ mục (sửa từ
điển có tác dụng ngay, không dựng lại chỉ mục).

Tệp synonyms/<mã môn>.txt, mỗi dòng một NHÓM cách nói tương đương, ngăn bằng "|" ("khóa ngoại | foreign key | fk");
dòng bắt đầu bằng "#" là chú thích. Nhóm (không phải khóa → danh sách): gõ bất kỳ cách nói nào cũng mở rộng ra các cách
còn lại. Riêng theo môn vì cùng một từ khác nghĩa ở môn khác ("khóa" – key trong CSDL, khóa học, khóa mã hóa).

Dò trong câu truy vấn: trie theo ÂM TIẾT dạng chuẩn (cùng hàm tách từ với chỉ mục – "khoá" / "khóa", dựng sẵn / tổ hợp
đều khớp), khớp DÀI NHẤT từ trái sang, không chồng nhau ("cơ sở dữ liệu quan hệ" trước "cơ sở dữ liệu"): mỗi bước
một lần tra dict → O(N × L), L = số âm tiết của cụm dài nhất (hằng nhỏ), không phụ thuộc cỡ từ điển. Câu không dấu dò
trên trie bỏ dấu (dựng khi cần).
"""
from __future__ import annotations

import threading
from pathlib import Path

from .search import fold, syllables

DIR = Path(__file__).with_name("synonyms")
_END = ""                                    # khóa đánh dấu hết cụm trong nút trie (âm tiết không bao giờ rỗng)


class Synonyms:
    def __init__(self, groups: list[list[str]]):
        # mỗi nhóm: các cách nói, mỗi cách nói là dãy âm tiết dạng chuẩn (cụm chứa dấu câu bị bỏ qua)
        self.groups = [[p[0] for p in (syllables(x) for x in g) if len(p) == 1 and p[0]] for g in groups]
        self.groups = [g for g in self.groups if len(g) >= 2]
        self._tries: dict[bool, dict] = {}

    def _phrases(self, g: int, plain_query: bool) -> list[list[str]]:
        return [[fold(w) for w in p] for p in self.groups[g]] if plain_query else self.groups[g]

    def _trie(self, plain_query: bool) -> dict:
        if plain_query not in self._tries:
            root: dict = {}
            for g in range(len(self.groups)):
                for p in self._phrases(g, plain_query):
                    node = root
                    for w in p:
                        node = node.setdefault(w, {})
                    node.setdefault(_END, g)              # cụm có ở nhiều nhóm: lấy nhóm khai báo trước
            self._tries[plain_query] = root               # hai luồng cùng dựng: cùng kết quả
        return self._tries[plain_query]

    def find(self, ws: list[str], plain_query: bool = False) -> list[tuple[int, int, list[list[str]]]]:
        """[(đầu, cuối, các cách nói KHÁC của nhóm)] – cụm khớp dài nhất từ trái sang, không chồng nhau."""
        root, out, i = self._trie(plain_query), [], 0
        while i < len(ws):
            node, best, j = root, None, i
            while j < len(ws) and ws[j] in node:
                node = node[ws[j]]
                j += 1
                if _END in node:
                    best = (j, node[_END])
            if best:
                end, g = best
                out.append((i, end, [p for p in self._phrases(g, plain_query) if p != ws[i:end]]))
                i = end
            else:
                i += 1
        return out


def parse(text: str) -> Synonyms:
    groups = [[x.strip() for x in line.split("|") if x.strip()]
              for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    return Synonyms(groups)


_cache: dict[str, tuple[float, Synonyms]] = {}
_lock = threading.Lock()


def for_course(course_code: str | None) -> Synonyms | None:
    """Từ điển của môn (None nếu môn chưa có). Đọc lại khi tệp đổi (mtime)."""
    if not course_code:
        return None
    path = DIR / f"{course_code}.txt"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    with _lock:
        got = _cache.get(course_code)
        if got and got[0] == mtime:
            return got[1]
    syn = parse(path.read_text(encoding="utf-8"))
    with _lock:
        _cache[course_code] = (mtime, syn)
    return syn
