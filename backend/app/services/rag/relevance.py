from __future__ import annotations

import hashlib
import threading
from collections import defaultdict

from sqlalchemy.orm import Session

from ...models import CLO, ClassSection, Course, MaterialPassage, Question, SectionMaterial
from .search import tokens

MIN_FINGERPRINT = 20
MIN_DOCS = 15
MAX_DF = 0.15
PAGE_HITS = 2
OK_SHARE = 0.25
OFF_SHARE = 0.08
MAX_PAGES = 400

_cache: dict[tuple, float | None] = {}
_lock = threading.Lock()


def specific(t: str) -> bool:
    return all(w.isascii() and w.isalpha() and w.islower() and len(w) >= 3 for w in t.split("_")) and len(t) >= 5


def fingerprint(db: Session, course_id: int) -> frozenset[str]:
    docs = [c.description for c in db.query(CLO).filter_by(course_id=course_id)]
    for q in db.query(Question).filter_by(course_id=course_id, is_cancelled=False):
        docs.append(q.content + "\n" + "\n".join(o.content for o in q.options))
    if len(docs) < MIN_DOCS:
        return frozenset()
    df: dict[str, int] = defaultdict(int)
    for d in docs:
        for t in set(tokens(d)):
            df[t] += 1
    return frozenset(t for t, c in df.items() if specific(t) and c / len(docs) <= MAX_DF)


def share_of(pages: list[set[str]], terms: frozenset[str]) -> float | None:
    sample = pages[:MAX_PAGES]
    return sum(len(p & terms) >= PAGE_HITS for p in sample) / len(sample) if sample else None


def page_share(db: Session, material_id: int, terms: frozenset[str]) -> float | None:
    rows = (db.query(MaterialPassage.page_id, MaterialPassage.title, MaterialPassage.body)
            .filter_by(material_id=material_id).order_by(MaterialPassage.page_id).all())
    pages: dict[int, set[str]] = defaultdict(set)
    for pid, title, body in rows:
        pages[pid].update(tokens(f"{title} {body}"))
    return share_of(list(pages.values()), terms)


def level(share: float | None) -> str | None:
    if share is None:
        return None
    return "ok" if share >= OK_SHARE else "low" if share >= OFF_SHARE else "off"


def assess(db: Session, cs_id: int) -> dict[int, dict]:
    course_id = db.query(ClassSection.course_id).filter_by(id=cs_id).scalar()
    mats = db.query(SectionMaterial.id, SectionMaterial.indexed_at).filter_by(class_section_id=cs_id, status="ready").all()
    if not course_id or not mats:
        return {}
    terms = fingerprint(db, course_id)
    if len(terms) < MIN_FINGERPRINT:
        return {}
    digest = hashlib.sha1("\n".join(sorted(terms)).encode()).hexdigest()
    out: dict[int, dict] = {}
    for mid, at in mats:
        key = (mid, str(at), digest)
        with _lock:
            known = key in _cache
            share = _cache.get(key)
        if not known:
            share = page_share(db, mid, terms)
            with _lock:
                _cache[key] = share
        lv = level(share)
        if lv:
            out[mid] = {"share": round(share, 3), "level": lv}
    return out


def off_topic_ids(db: Session, cs_id: int) -> set[int]:
    return {mid for mid, r in assess(db, cs_id).items() if r["level"] == "off"}


def _reason(db: Session, course_id: int, share: float | None, hint: str) -> str | None:
    if level(share) != "off":
        return None
    code = db.query(Course.course_code).filter_by(id=course_id).scalar()
    return (f"Tài liệu có vẻ không thuộc môn {code}: chỉ {share:.0%} số trang chứa nội dung liên quan đến CLO và "
            f"ngân hàng câu hỏi của môn. {hint}")


def _terms(db: Session, cs_id: int) -> tuple[int | None, frozenset[str]]:
    course_id = db.query(ClassSection.course_id).filter_by(id=cs_id).scalar()
    terms = fingerprint(db, course_id) if course_id else frozenset()
    return course_id, (terms if len(terms) >= MIN_FINGERPRINT else frozenset())


def verdict(db: Session, m: SectionMaterial) -> str | None:
    course_id, terms = _terms(db, m.class_section_id)
    if not terms:
        return None
    return _reason(db, course_id, page_share(db, m.id, terms),
                   'Hãy kiểm tra lại tệp; nếu đúng là tài liệu của môn, bấm "Vẫn dùng".')


def check_upload(db: Session, cs_id: int, pages: list[str]) -> str | None:
    course_id, terms = _terms(db, cs_id)
    if not terms:
        return None
    return _reason(db, course_id, share_of([set(tokens(t)) for t in pages], terms),
                   "Tệp chưa được đăng lên Moodle. Hãy kiểm tra lại đã chọn đúng tệp của môn này chưa.")
