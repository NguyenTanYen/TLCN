"""Bước 6: tìm đoạn học liệu bằng BM25 – CHỈ trong học liệu đã nạp ('ready') của MỘT lớp học phần.

Tách từ tiếng Việt (tokens):
  - chữ thường, Unicode NFC; mỗi âm tiết một từ. Dấu THANH tách khỏi chữ và ghi thành một chữ IN HOA cuối kiểu Telex
    ("hoà" / "hòa" → "hoaF"): hai cách bỏ dấu cũ / mới, gõ tổ hợp / dựng sẵn đều ra cùng một từ; dấu của nguyên âm
    (â ê ô ơ ư ă) và đ giữ nguyên – "bàn" ≠ "bán", "cơ" ≠ "có". In HOA vì văn bản đã chuyển chữ thường: không trùng
    từ tiếng Anh nào (Telex chữ thường thì "mã" → "max" trùng hàm MAX, "thí" → "this", "còn" → "conf");
  - từ ghép tiếng Việt viết rời từng âm tiết → thêm CẶP âm tiết liền nhau (bigram "khoaS_ngoaiJ") trong cùng một cụm
    (không vượt dấu câu / xuống dòng): khớp cả cụm "khóa ngoại" được điểm cao hơn khớp rời "khóa" ... "ngoại";
  - bỏ hư từ (là, của, các, được, ...) khi chấm điểm; cặp có hư từ cũng bỏ.

Câu truy vấn KHÔNG DẤU ("dac trung 5V", gõ vội trên điện thoại) → tìm trên bản bỏ dấu của chỉ mục (fold: "đặc" →
"dac"), dựng lần đầu cần tới. Câu có dấu chỉ tìm trên bản có dấu – không trộn bản bỏ dấu vào ("bàn" không khớp
"bán" / "bạn").

Mỗi đoạn là một văn bản: tiêu đề (tính 2 lần – breadcrumb đã chứa tiêu đề) + đường dẫn đề mục + chú thích + nội dung
+ mô tả hình (VLM). BM25 (k1 = 1,2; b = 0,75), IDF kiểu Lucene (luôn dương – lớp ít tài liệu vẫn chấm được).

Chỉ mục giữ trong RAM theo lớp; khóa = (id, indexed_at) các học liệu 'ready' của lớp, kiểm với MySQL ở MỌI lần tìm –
nạp lại / bỏ chọn / đồng bộ mất tệp đều tự làm mới, nhiều worker không lệch nhau. DỰNG KHI GHI: luồng nạp (index)
dựng lại chỉ mục của lớp ngay sau khi nạp / bỏ chọn (warm). Lần tìm gặp chỉ mục cũ thì dùng BẢN CŨ ngay và dựng lại
ở nền (worker khác, hoặc trong lúc luồng nạp đang dựng) – không chờ; chỉ khi chưa từng có chỉ mục mới phải chờ dựng.
Bản cũ an toàn: kết quả lấy lại từ CSDL theo id đoạn, đoạn của học liệu đã bỏ chọn / nạp lại bị loại.

RAM: mỗi worker giữ bản riêng (đo: 2.849 đoạn của 8 PDF thật ~16 MB). Hiện chạy MỘT tiến trình uvicorn. BACKLOG – khi
chạy nhiều worker mà RAM của các bản sao chỉ mục vượt ~70%: lưu chỉ mục ra chỗ dùng chung (tệp / MySQL theo khóa
(id, indexed_at)), một worker dựng (khóa phân tán GET_LOCK), các worker khác nạp lên thay vì tự dựng.
"""
from __future__ import annotations

import logging
import math
import re
import threading
import unicodedata
from collections import Counter, OrderedDict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ...models import MaterialPage, MaterialPassage, SectionMaterial

log = logging.getLogger(__name__)

K1, B = 1.2, 0.75
TITLE_WEIGHT = 2            # tiêu đề đoạn tính 2 lần (breadcrumb chứa tiêu đề + thêm một lần)
CACHE_SECTIONS = 32         # số lớp giữ chỉ mục trong RAM (LRU)
SNIPPET = 300

# dấu thanh (dạng tổ hợp sau NFD) → chữ Telex IN HOA; chr() thay vì viết thẳng ký tự tổ hợp cho dễ đọc
TONES = {chr(0x300): "F", chr(0x301): "S", chr(0x309): "R", chr(0x303): "X", chr(0x323): "J"}
_WORD = re.compile(r"[^\W_]+")
_BREAK = re.compile(r"[.,;:!?()\[\]{}|<>\"“”‘’'…/\\–—=+*•▪●◦\n]+")     # gạch nối KHÔNG ngắt cụm: "B-tree" → b, tree, b_tree

_STOP_TEXT = """
là của và các có được trong cho với những một này đó đây kia thì mà để khi từ theo như về ra vào nào gì
sau trước trên dưới bằng hay hoặc cũng đã sẽ đang rất nhiều ít mỗi cả chỉ còn nữa lại nên vì nếu tại do
bị nhưng hơn nhất thế vậy rằng ai đâu sao bao giờ lúc đều tới đến qua cùng việc sự cái chiếc nhau
the a an of and or to in on for is are be by with as at from that this these those it its which
"""


def _syllable(w: str) -> str:
    """Âm tiết → dạng chuẩn: bỏ dấu thanh, ghép ký tự Telex của dấu thanh vào cuối."""
    tone, out = "", []
    for ch in unicodedata.normalize("NFD", w):
        if ch in TONES:
            tone = TONES[ch]
        else:
            out.append(ch)
    return unicodedata.normalize("NFC", "".join(out)) + tone


STOP = frozenset(_syllable(w) for w in _STOP_TEXT.split())


def fold(s: str) -> str:
    """Bỏ hết dấu: dấu thanh (chữ in hoa của dạng chuẩn) và dấu nguyên âm, đ → d."""
    s = "".join(ch for ch in unicodedata.normalize("NFD", s) if not ch.isupper() and not unicodedata.combining(ch))
    return s.replace("đ", "d")


def plain(query: str) -> bool:
    """Câu truy vấn không có chữ nào mang dấu tiếng Việt."""
    q = query.lower()
    return fold(q) == unicodedata.normalize("NFD", q)


def tokens(text: str) -> list[str]:
    """Từ để chấm điểm: âm tiết (bỏ hư từ) + cặp âm tiết liền nhau trong cùng một cụm."""
    out: list[str] = []
    for part in _BREAK.split(unicodedata.normalize("NFC", text.lower())):
        ws = [_syllable(w) for w in _WORD.findall(part)]
        out += [w for w in ws if w not in STOP]
        out += [f"{a}_{b}" for a, b in zip(ws, ws[1:]) if a not in STOP and b not in STOP]
    return out


# hư từ gõ KHÔNG DẤU ("mot", "nhung", "ra") khớp bản bỏ dấu của từ HIẾM có dấu ("mốt", "nhúng", "rà" – bản có dấu
# của chính hư từ không có trong chỉ mục) → IDF CAO (đo trên 8 PDF thật: 7,0–7,5), kéo nhiễu lên; nhưng nhiều dạng lại trùng âm tiết quan trọng ("bang" – bảng, "ma" – mã, "qua" – kết quả, "co"
# – cơ sở) nên không chặn hẳn: câu không dấu KHÔNG tính chúng như một từ riêng, chỉ tính trong cặp ("co_so", "ket_qua")
STOP_PLAIN = frozenset(fold(w) for w in STOP)


def query_terms(text: str, plain_query: bool = False) -> dict[str, float]:
    """Từ của câu truy vấn kèm trọng số. Từ ghép tiếng Việt sinh 3 từ (2 âm tiết + 1 cặp) còn thuật ngữ một từ
    ("NameNode") chỉ 1 → từ ghép chung chung ("vai trò") lấn thuật ngữ chính. Cân lại: âm tiết NẰM TRONG cụm ≥ 2 âm
    tiết và mỗi cặp tính ½, âm tiết đứng riêng tính 1 – "vai trò" khớp đủ = 1,5, "NameNode" = 1.
    plain_query: câu không dấu – từ đã bỏ dấu; hư từ (bỏ dấu) không tính riêng, cặp chỉ bỏ khi CẢ HAI là hư từ."""
    out: Counter[str] = Counter()
    for part in _BREAK.split(unicodedata.normalize("NFC", text.lower())):
        ws = [_syllable(w) for w in _WORD.findall(part)]
        if plain_query:
            ws = [fold(w) for w in ws]
            single = [w not in STOP_PLAIN for w in ws]
            pairs = [single[i] or single[i + 1] for i in range(len(ws) - 1)]
        else:
            single = [w not in STOP for w in ws]
            pairs = [single[i] and single[i + 1] for i in range(len(ws) - 1)]
        for i, w in enumerate(ws):
            if single[i]:
                joined = (i > 0 and pairs[i - 1]) or (i < len(pairs) and pairs[i])
                out[w] += 0.5 if joined else 1.0
        for i, ok in enumerate(pairs):
            if ok:
                out[f"{ws[i]}_{ws[i + 1]}"] += 0.5
    return dict(out)


def _doc_text(title: str, breadcrumb: str, caption: str | None, body: str, vlm: str | None) -> str:
    return "\n".join([title] * (TITLE_WEIGHT - 1) + [breadcrumb or title, caption or "", body, vlm or ""])


@dataclass
class Index:
    ids: list[int] = field(default_factory=list)                  # id đoạn theo thứ tự văn bản
    lengths: list[int] = field(default_factory=list)
    postings: dict[str, list[tuple[int, int]]] = field(default_factory=dict)   # từ → [(thứ tự văn bản, tần suất)]
    avgdl: float = 0.0
    folded: dict[str, list[tuple[int, int]]] | None = None     # bản bỏ dấu – dựng khi có câu truy vấn không dấu

    @classmethod
    def build(cls, docs: list[tuple[int, str]]) -> "Index":
        ix = cls()
        for i, (pid, text) in enumerate(docs):
            tf = Counter(tokens(text))
            ix.ids.append(pid)
            ix.lengths.append(sum(tf.values()))
            for t, n in tf.items():
                ix.postings.setdefault(t, []).append((i, n))
        ix.avgdl = sum(ix.lengths) / len(ix.lengths) if ix.lengths else 0.0
        return ix

    def _folded(self) -> dict[str, list[tuple[int, int]]]:
        """Gộp các từ cùng dạng bỏ dấu ("banF", "banS", "banJ" → "ban"): tần suất cộng lại theo từng văn bản."""
        if self.folded is None:
            acc: dict[str, dict[int, int]] = {}
            for t, post in self.postings.items():
                d = acc.setdefault(fold(t), {})
                for i, n in post:
                    d[i] = d.get(i, 0) + n
            self.folded = {t: sorted(d.items()) for t, d in acc.items()}   # hai luồng cùng dựng: cùng kết quả
        return self.folded

    def score(self, query: str, k: int) -> list[tuple[int, float, list[str]]]:
        """[(id đoạn, điểm, các từ khớp)] cao nhất trước; chỉ đoạn có khớp."""
        n = len(self.ids)
        if not n:
            return []
        is_plain = plain(query)
        postings, terms = (self._folded() if is_plain else self.postings), query_terms(query, is_plain)
        acc: dict[int, float] = {}
        hit: dict[int, list[str]] = {}
        for t, qtf in terms.items():
            post = postings.get(t)
            if not post:
                continue
            idf = math.log(1 + (n - len(post) + 0.5) / (len(post) + 0.5))
            for i, tf in post:
                norm = tf * (K1 + 1) / (tf + K1 * (1 - B + B * self.lengths[i] / self.avgdl))
                acc[i] = acc.get(i, 0.0) + qtf * idf * norm
                hit.setdefault(i, []).append(t)
        best = sorted(acc.items(), key=lambda x: (-x[1], x[0]))[:k]
        return [(self.ids[i], s, hit[i]) for i, s in best]


@dataclass
class Hit:
    passage_id: int
    material_id: int
    material_title: str
    file_name: str
    moodle_file_url: str | None
    page_no: int
    kind: str
    title: str
    breadcrumb: str
    snippet: str
    bboxes: list
    score: float
    matched: list[str]


_cache: "OrderedDict[int, tuple[tuple, Index]]" = OrderedDict()
_lock = threading.Lock()
_building: dict[int, threading.Lock] = {}     # khóa dựng theo lớp (số lớp có hạn – không cần dọn)


def _ready(db: Session, cs_id: int) -> tuple:
    rows = (db.query(SectionMaterial.id, SectionMaterial.indexed_at)
            .filter_by(class_section_id=cs_id, status="ready").order_by(SectionMaterial.id).all())
    return tuple((i, str(t)) for i, t in rows)


def _cached(cs_id: int, key: tuple) -> Index | None:
    with _lock:
        got = _cache.get(cs_id)
        if got and got[0] == key:
            _cache.move_to_end(cs_id)
            return got[1]
    return None


def _build(db: Session, cs_id: int, key: tuple) -> Index:
    ids = [i for i, _ in key]
    rows = (db.query(MaterialPassage.id, MaterialPassage.title, MaterialPassage.breadcrumb, MaterialPassage.caption,
                     MaterialPassage.body, MaterialPassage.vlm_desc)
            .filter(MaterialPassage.material_id.in_(ids)).order_by(MaterialPassage.id).all()) if ids else []
    ix = Index.build([(r.id, _doc_text(r.title, r.breadcrumb, r.caption, r.body, r.vlm_desc)) for r in rows])
    with _lock:
        _cache[cs_id] = (key, ix)
        _cache.move_to_end(cs_id)
        while len(_cache) > CACHE_SECTIONS:
            _cache.popitem(last=False)
    return ix


def _refresh(bind, cs_id: int) -> None:
    """Dựng lại ở nền (phiên CSDL riêng); đang có bên khác dựng thì thôi."""
    building = _building_lock(cs_id)
    if not building.acquire(blocking=False):
        return
    try:
        with Session(bind=bind) as db:
            key = _ready(db, cs_id)
            if _cached(cs_id, key) is None:
                _build(db, cs_id, key)
    except Exception:
        log.exception("Dựng chỉ mục tìm kiếm của lớp %s lỗi", cs_id)
    finally:
        building.release()


def _building_lock(cs_id: int) -> threading.Lock:
    with _lock:
        return _building.setdefault(cs_id, threading.Lock())


def section_index(db: Session, cs_id: int, wait: bool = False) -> Index:
    """Chỉ mục BM25 của lớp. Học liệu 'ready' của lớp đã đổi: có bản cũ thì trả bản cũ NGAY và dựng lại ở nền (một
    luồng dựng, yêu cầu khác không chờ); chưa có bản nào (hoặc wait – luồng nạp dựng sẵn) thì dựng / chờ dựng xong."""
    key = _ready(db, cs_id)
    if (ix := _cached(cs_id, key)) is not None:
        return ix
    building = _building_lock(cs_id)
    with _lock:
        stale = _cache.get(cs_id)
    if stale is not None and not wait:
        if not building.locked():
            threading.Thread(target=_refresh, args=(db.get_bind(), cs_id), name="rag-search-index", daemon=True).start()
        return stale[1]
    with building:
        if (ix := _cached(cs_id, key)) is not None:                # bên khác vừa dựng xong
            return ix
        return _build(db, cs_id, key)


def warm(db: Session, cs_id: int) -> None:
    """Dựng sẵn chỉ mục của lớp sau khi học liệu đổi (luồng nạp gọi) – lần tìm sau không phải dựng."""
    section_index(db, cs_id, wait=True)


def search(db: Session, cs_id: int, query: str, k: int = 10) -> list[Hit]:
    """k đoạn học liệu của lớp khớp nhất với query (BM25)."""
    scored = section_index(db, cs_id).score(query, k)
    if not scored:
        return []
    rows = {p.id: (p, pg, m) for p, pg, m in
            db.query(MaterialPassage, MaterialPage, SectionMaterial)
            .join(MaterialPage, MaterialPage.id == MaterialPassage.page_id)
            .join(SectionMaterial, SectionMaterial.id == MaterialPassage.material_id)
            .filter(MaterialPassage.id.in_([pid for pid, _, _ in scored]),
                    SectionMaterial.class_section_id == cs_id, SectionMaterial.status == "ready")}
    out = []
    for pid, s, matched in scored:
        if pid not in rows:                                       # vừa bị nạp lại / bỏ chọn
            continue
        p, pg, m = rows[pid]
        out.append(Hit(p.id, m.id, m.title, m.file_name, m.moodle_file_url, pg.page_no, p.kind, p.title, p.breadcrumb,
                       p.body[:SNIPPET], p.bboxes, round(s, 3), sorted({t for t in matched if "_" not in t})))
    return out
