"""Bước 6: tìm đoạn học liệu bằng BM25 – CHỈ trong học liệu đã nạp ('ready') của MỘT lớp học phần."""
from __future__ import annotations

import logging
import math
import re
import threading
import unicodedata
from collections import Counter, OrderedDict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ...models import ClassSection, Course, MaterialPage, MaterialPassage, SectionMaterial

log = logging.getLogger(__name__)

K1, B = 1.2, 0.75
TITLE_WEIGHT = 2
CACHE_SECTIONS = 32
SNIPPET = 300

TONES = {chr(0x300): "F", chr(0x301): "S", chr(0x309): "R", chr(0x303): "X", chr(0x323): "J"}
_WORD = re.compile(r"[^\W_]+")
_BREAK = re.compile(r"[.,;:!?()\[\]{}|<>\"“”‘’'…/\\–—=+*•▪●◦\n]+")

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


_ENGLISH = frozenset("which what who whose whom why how does did is are was were of this these those following".split())


def looks_english(query: str) -> bool:
    return plain(query) and bool(_ENGLISH & set(_WORD.findall(query.lower())))


def tokens(text: str) -> list[str]:
    """Từ để chấm điểm: âm tiết (bỏ hư từ) + cặp âm tiết liền nhau trong cùng một cụm."""
    out: list[str] = []
    for part in _BREAK.split(unicodedata.normalize("NFC", text.lower())):
        ws = [_syllable(w) for w in _WORD.findall(part)]
        out += [w for w in ws if w not in STOP]
        out += [f"{a}_{b}" for a, b in zip(ws, ws[1:]) if a not in STOP and b not in STOP]
    return out


STOP_PLAIN = frozenset(fold(w) for w in STOP)
SYN_WEIGHT = 0.8


@dataclass
class Query:
    terms: dict[str, float]
    concepts: list[frozenset[str]]


def _weights(ws: list[str], plain_query: bool) -> tuple[list[float], list[bool]]:
    """Trọng số từng âm tiết + có tạo cặp với âm tiết sau hay không."""
    if plain_query:
        single = [w not in STOP_PLAIN for w in ws]
        pairs = [single[i] or single[i + 1] for i in range(len(ws) - 1)]
    else:
        single = [w not in STOP for w in ws]
        pairs = [single[i] and single[i + 1] for i in range(len(ws) - 1)]
    uni = [0.0 if not single[i] else 0.5 if (i > 0 and pairs[i - 1]) or (i < len(pairs) and pairs[i]) else 1.0
           for i in range(len(ws))]
    return uni, pairs


def _phrase_terms(ws: list[str], plain_query: bool) -> Counter:
    uni, pairs = _weights(ws, plain_query)
    out: Counter[str] = Counter()
    for w, x in zip(ws, uni):
        if x:
            out[w] += x
    for i, ok in enumerate(pairs):
        if ok:
            out[f"{ws[i]}_{ws[i + 1]}"] += 0.5
    return out


def syllables(text: str, plain_query: bool = False) -> list[list[str]]:
    """Các cụm (tách ở dấu câu / xuống dòng), mỗi cụm là dãy âm tiết dạng chuẩn (bỏ dấu nếu plain_query)."""
    out = []
    for part in _BREAK.split(unicodedata.normalize("NFC", text.lower())):
        ws = [_syllable(w) for w in _WORD.findall(part)]
        out.append([fold(w) for w in ws] if plain_query else ws)
    return out


def analyze(text: str, plain_query: bool = False, synonyms=None) -> Query:
    """Câu truy vấn → từ (kèm trọng số) + khái niệm."""
    terms: Counter[str] = Counter()
    concepts: list[frozenset[str]] = []
    for ws in syllables(text, plain_query):
        if not ws:
            continue
        own = _phrase_terms(ws, plain_query)
        terms.update(own)
        uni, _ = _weights(ws, plain_query)
        covered: set[int] = set()
        for i, j, alts in (synonyms.find(ws, plain_query) if synonyms else []):
            span = _phrase_terms(ws[i:j], plain_query)
            budget = SYN_WEIGHT * sum(span.values())
            extra: dict[str, float] = {}
            for alt in alts:
                at = _phrase_terms(alt, plain_query)
                total = sum(at.values()) or 1.0
                for t, x in at.items():
                    extra[t] = max(extra.get(t, 0.0), budget * x / total)
            for t, x in extra.items():
                if t not in span:
                    terms[t] = max(terms.get(t, 0.0), x)
            concepts.append(frozenset(span) | frozenset(extra))
            covered.update(range(i, j))
        concepts += [frozenset({w}) for i, w in enumerate(ws) if uni[i] and i not in covered]
    return Query(dict(terms), list(dict.fromkeys(concepts)))


def query_terms(text: str, plain_query: bool = False) -> dict[str, float]:
    return analyze(text, plain_query).terms


def required(n: int, spec: str | None) -> int:
    """Số khái niệm phải khớp theo minimum_should_match dạng "2<70%": câu ≤ 2 khái niệm phải khớp hết, dài hơn khớp ít nhất 70% (làm tròn xuống, tối thiểu 1)."""
    if not spec or n == 0:
        return 0
    head, pct = spec.split("<")
    return n if n <= int(head) else max(1, math.floor(n * float(pct.rstrip("%")) / 100))


def _doc_text(title: str, breadcrumb: str, caption: str | None, body: str, vlm: str | None) -> str:
    return "\n".join([title] * (TITLE_WEIGHT - 1) + [breadcrumb or title, caption or "", body, vlm or ""])


@dataclass
class Index:
    ids: list[int] = field(default_factory=list)
    lengths: list[int] = field(default_factory=list)
    postings: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    avgdl: float = 0.0
    folded: dict[str, list[tuple[int, int]]] | None = None

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
            self.folded = {t: sorted(d.items()) for t, d in acc.items()}
        return self.folded

    def score(self, query: str, k: int, synonyms=None, msm: str | None = None) -> list[tuple[int, float, list[str]]]:
        """[(id đoạn, điểm, các từ khớp)] cao nhất trước; chỉ đoạn có khớp."""
        n = len(self.ids)
        if not n:
            return []
        is_plain = plain(query)
        q = analyze(query, is_plain, synonyms)
        postings, terms = (self._folded() if is_plain else self.postings), q.terms
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
        need = required(len(q.concepts), msm)
        if need:
            acc = {i: s for i, s in acc.items() if sum(1 for c in q.concepts if not c.isdisjoint(hit[i])) >= need}
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
_building: dict[int, threading.Lock] = {}


def _ready(db: Session, cs_id: int) -> tuple:
    rows = (db.query(SectionMaterial.id, SectionMaterial.indexed_at, SectionMaterial.vlm_model)
            .filter_by(class_section_id=cs_id, status="ready").order_by(SectionMaterial.id).all())
    return tuple((i, str(t), v) for i, t, v in rows)


def _cached(cs_id: int, key: tuple) -> Index | None:
    with _lock:
        got = _cache.get(cs_id)
        if got and got[0] == key:
            _cache.move_to_end(cs_id)
            return got[1]
    return None


def _build(db: Session, cs_id: int, key: tuple) -> Index:
    ids = [i for i, *_ in key]
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
    """Chỉ mục BM25 của lớp."""
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
        if (ix := _cached(cs_id, key)) is not None:
            return ix
        return _build(db, cs_id, key)


def warm(db: Session, cs_id: int) -> None:
    """Dựng sẵn chỉ mục của lớp sau khi học liệu đổi (luồng nạp gọi) – lần tìm sau không phải dựng."""
    section_index(db, cs_id, wait=True)


def search(db: Session, cs_id: int, query: str, k: int = 10, msm: str | None = None, floor: float | None = None) -> list[Hit]:
    """k đoạn học liệu của lớp khớp nhất với query (BM25 + từ điển đồng nghĩa của môn)."""
    from . import synonyms
    code = (db.query(Course.course_code).join(ClassSection, ClassSection.course_id == Course.id)
            .filter(ClassSection.id == cs_id).scalar())
    scored = section_index(db, cs_id).score(query, k, synonyms.for_course(code), msm)
    from . import semantic
    from .suggest import fuse
    try:
        dense = semantic.dense_top(db, cs_id, query, max(k, 10), floor=floor)
    except Exception:
        log.exception("Tìm theo nghĩa lỗi – chỉ dùng BM25")
        dense = []
    if dense:
        by_bm25 = {pid: (s, m) for pid, s, m in scored}
        by_cos = dict(dense)
        order = fuse([([pid for pid, _, _ in scored], 1.0), ([pid for pid, _ in dense], 1.0)])[:k]
        scored = [(pid, by_bm25[pid][0] if pid in by_bm25 else by_cos[pid], by_bm25[pid][1] if pid in by_bm25 else [])
                  for pid in order]
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
        if pid not in rows:
            continue
        p, pg, m = rows[pid]
        out.append(Hit(p.id, m.id, m.title, m.file_name, m.moodle_file_url, pg.page_no, p.kind, p.title, p.breadcrumb,
                       p.body[:SNIPPET], p.bboxes, round(s, 3), sorted({t for t in matched if "_" not in t})))
    return out
