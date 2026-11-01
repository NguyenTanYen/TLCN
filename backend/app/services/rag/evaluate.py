"""Bước 7: đo chất lượng tìm học liệu trên bộ câu hỏi chuẩn (eval/rag_gold.json).

    python -m app.services.rag.evaluate <thư mục PDF> [eval/rag_gold.json] [--detail] [--semantic 0.5,0.55,0.59] [--vlm]

Thư mục PDF chứa các tệp trong "corpus" của bộ câu hỏi (học liệu không đưa vào kho mã). Mỗi câu hỏi có các TRANG đúng
(gán theo trang, không theo id đoạn – chia đoạn thay đổi thì bộ câu hỏi vẫn dùng được). Một kết quả "đúng" khi đoạn
trả về nằm trên một trang đúng.

Chỉ số (trên các câu CÓ đáp án trong tài liệu):
  Hit@k – tỷ lệ câu có ít nhất một đoạn đúng trong k kết quả đầu;  MRR – trung bình 1 / hạng của đoạn đúng đầu tiên
  (trong 10 kết quả đầu, không có thì 0);  nDCG@10 – các trang đúng có được xếp sớm không (mỗi trang đúng chỉ tính
  một lần ở đoạn đầu tiên của nó – trang nhiều đoạn không được cộng dồn; chuẩn hóa theo cách xếp lý tưởng).
Câu KHÔNG có đáp án (negative): "gợi ý sai" – tỷ lệ câu vẫn trả về kết quả (hệ thống đáng lẽ không gợi ý gì).
--vlm: đoạn hình kèm mô tả của VLM (vlm.py; mô tả lưu đệm cạnh PDF) – chạy cả có và không có để so.
--semantic: thêm các dòng "gợi ý theo trang" có cổng ngữ nghĩa (semantic.py) ở từng ngưỡng cos (cần sentence-transformers;
vector của các đoạn lưu đệm cạnh PDF).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass

import numpy as np
from pathlib import Path

from ...config import settings
from . import synonyms as synonym_files
from .chunk import build_passages
from .ingest import read_pdf
from .search import Index, _doc_text, plain

KS = (1, 3, 5, 10)
GOLD = Path(__file__).resolve().parents[3] / "eval" / "rag_gold.json"
CACHE = ".rag_eval_cache.json"


@dataclass
class Doc:
    file: str
    page: int
    text: str = ""


def load_corpus(pdf_dir: Path, files: list[str], vlm: bool = False) -> tuple[list[Doc], Index]:
    """Đọc + chia đoạn các PDF (lưu đệm theo cỡ / thời điểm sửa tệp – chạy lại không phải đọc PDF). vlm: thêm mô tả
    hình của VLM (describe_corpus) vào văn bản các đoạn hình – như sau vlm.describe_missing."""
    cache_path = pdf_dir / CACHE
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    dirty = False
    for f in files:
        st = (pdf_dir / f).stat()
        key = f"{st.st_size}:{int(st.st_mtime)}"
        if cache.get(f, {}).get("key") != key or cache[f].get("v") != 2:
            ps = build_passages(read_pdf(str(pdf_dir / f)))
            cache[f] = {"key": key, "v": 2, "passages": [[p.page, p.kind, p.title, p.breadcrumb, p.caption, p.body,
                                                          list(p.bboxes[0]) if p.bboxes else None] for p in ps]}
            dirty = True
    if dirty:
        cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    descs = describe_corpus(pdf_dir, files, cache) if vlm else {}
    docs, texts = [], []
    for f in files:
        for i, (page, _, title, crumb, caption, body, _) in enumerate(cache[f]["passages"]):
            text = _doc_text(title, crumb, caption, body, descs.get(f, {}).get(str(i)))
            texts.append((len(docs), text))
            docs.append(Doc(f, page, text))
    return docs, Index.build(texts)


def describe_corpus(pdf_dir: Path, files: list[str], cache: dict) -> dict[str, dict[str, str]]:
    """Mô tả VLM của các đoạn hình: {tệp: {thứ tự đoạn: mô tả}} – lưu đệm cạnh PDF theo model + tham số gọi + phiên bản tệp (mỗi
    tệp xong là ghi lại – dừng giữa chừng chạy lại không mất phần đã làm)."""
    from . import vlm
    from .ingest import render_regions
    path = pdf_dir / f".rag_eval_vlm_{''.join(c if c.isalnum() else '_' for c in vlm.model_name())}.json"
    try:
        out = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        out = {}
    for f in files:
        figs = [(i, pg, bb, crumb, body) for i, (pg, kind, _, crumb, _, body, bb) in enumerate(cache[f]["passages"])
                if kind == "figure" and bb]
        if (out.get(f, {}).get("key") == cache[f]["key"] and out[f].get("options") == vlm.OPTIONS
                and len(out[f]["descs"]) == len(figs)):
            continue
        if not vlm.available():
            sys.exit(f"--vlm: Ollama chưa chạy hoặc chưa có model {vlm.model_name()} (RAG_VLM_MODEL / RAG_VLM_URL)")
        t = time.monotonic()
        pngs = render_regions(str(pdf_dir / f), [(pg, tuple(bb)) for _, pg, bb, _, _ in figs])
        descs = {}
        for (i, _, _, crumb, body), png in zip(figs, pngs):
            descs[str(i)] = vlm.describe(png, vlm.prompt_for(Path(f).stem, True, crumb, body))
        out[f] = {"key": cache[f]["key"], "options": vlm.OPTIONS, "descs": descs, "seconds": round(time.monotonic() - t, 1)}
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  VLM {f}: {len(figs)} hình ({sum(not d for d in descs.values())} bị từ chối), "
              f"{time.monotonic() - t:.0f} s", flush=True)
    return {f: out[f]["descs"] for f in files}


def query_text(q: dict, mode: str) -> str:
    """stem – chỉ thân câu hỏi; stem+answer – thân câu + nội dung đáp án đúng."""
    return q["stem"] if mode == "stem" else f'{q["stem"]}\n{q["options"][q["answer"]]}'


def ndcg(pages: list[tuple[str, int]], rel: set[tuple[str, int]], k: int = 10) -> float:
    """nDCG@k nhị phân theo TRANG: mỗi trang đúng được tính ở lần xuất hiện đầu tiên (đoạn sau cùng trang = 0)."""
    seen, dcg = set(), 0.0
    for r, pg in enumerate(pages[:k], 1):
        if pg in rel and pg not in seen:
            seen.add(pg)
            dcg += 1 / math.log2(r + 1)
    ideal = sum(1 / math.log2(r + 1) for r in range(1, min(len(rel), k) + 1))
    return dcg / ideal if ideal else 0.0


def run(questions: list[dict], docs: list[Doc], ix: Index, mode: str = "stem+answer", synonyms=None,
        msm: str | None = None, k: int = 10) -> dict:
    per: dict[str, list[tuple[int | None, float]]] = {}             # loại câu → [(hạng đoạn đúng đầu tiên, nDCG)]
    neg, detail = [], []
    for q in questions:
        res = ix.score(query_text(q, mode), k, synonyms, msm)
        rel = {(f, p) for f, pages in q["relevant"].items() for p in pages}
        if not rel:
            neg.append(bool(res))
            detail.append((q["id"], "negative", len(res)))
            continue
        pages = [(docs[i].file, docs[i].page) for i, _, _ in res]
        rank = next((r for r, pg in enumerate(pages, 1) if pg in rel), None)
        for t in (q["type"], "all"):
            per.setdefault(t, []).append((rank, ndcg(pages, rel, k)))
        detail.append((q["id"], q["type"], rank, pages[:3]))
    out = {t: {"n": len(v), "mrr": sum(1 / r for r, _ in v if r) / len(v), "ndcg": sum(g for _, g in v) / len(v),
               **{f"hit@{kk}": sum(bool(r and r <= kk) for r, _ in v) / len(v) for kk in KS}}
           for t, v in per.items()}
    out["negative"] = {"n": len(neg), "wrong": sum(neg) / len(neg) if neg else 0.0}
    out["detail"] = detail
    return out


def embeddings(pdf_dir: Path, docs: list[Doc], questions: list[dict]) -> tuple[np.ndarray, dict] | None:
    """Vector MiniLM của các đoạn (lưu đệm theo model + nội dung) và của từng câu hỏi; None nếu chưa cài thư viện."""
    from . import semantic, suggest
    if not semantic.enabled():
        return None
    import hashlib
    key = hashlib.sha1((semantic.model_name() + "".join(d.text for d in docs)).encode()).hexdigest()
    path = pdf_dir / f".rag_eval_emb_{key[:12]}.npy"
    if path.exists():
        D = np.load(path)
    else:
        D = semantic.encode([d.text for d in docs])
        np.save(path, D)
    texts = [suggest.query_text(q["stem"], [q["options"][q["answer"]]]) for q in questions]
    return D, dict(zip((q["id"] for q in questions), semantic.encode(texts)))


def run_suggest(questions: list[dict], docs: list[Doc], ix: Index, synonyms=None,
                wrong_weight: float | None = None, gate: tuple | None = None, margin: float | None = None,
                floor: float | None = None) -> dict:
    """Bước 8 – gợi ý theo TRANG cho từng cặp (câu, phương án SAI sinh viên chọn). wrong_weight None: không dùng
    truy vấn phương án sai. gate = (vector đoạn, vector câu hỏi, ngưỡng, lọc từng đoạn?): theo câu – như
    semantic.related, không đoạn ứng viên nào đạt ngưỡng thì không gợi ý; từng đoạn – bỏ đoạn dưới ngưỡng (đã thử, bỏ).
    margin / floor (cần gate): bỏ trang có cos thấp hơn trang gần nhất quá margin / thấp hơn floor (suggest.close_pages).
    Chỉ số theo trang: Hit@1, Hit@3 (số trang gợi ý), MRR; P@3 – tỷ lệ trang ĐÚNG trong các trang được gợi ý (tối đa 3;
    bị chặn hết thì 0) – trang thừa làm giảm P@3; "trang/câu" – số trang trung bình được gợi ý."""
    from . import suggest
    ranks, neg, prec, shown = [], [], [], []
    for q in questions:
        rel = {(f, p) for f, pages in q["relevant"].items() for p in pages}
        correct = [q["options"][q["answer"]]]
        for label, wrong in q["options"].items():
            if label == q["answer"]:
                continue
            ranked = suggest.rank_passages(ix, q["stem"], correct, wrong if wrong_weight else None, synonyms,
                                           wrong_weight or 0)
            if gate:
                D, Q, thr, per_passage = gate
                cos = {i: float(D[i] @ Q[q["id"]]) for i in ranked}
                if per_passage:
                    ranked = [i for i in ranked if cos[i] >= thr]
                elif ranked and not plain(suggest.query_text(q["stem"], correct)) and max(cos.values()) < thr:   # như semantic.related
                    ranked = []
            page_of = lambda i: (docs[i].file, docs[i].page)
            pages = [pg for pg, _ in suggest.pages_of(ranked, page_of)]
            if gate and (margin is not None or floor is not None) and pages:
                best = {}
                for i in ranked:
                    best[page_of(i)] = max(best.get(page_of(i), -1.0), cos[i])
                pages = suggest.close_pages([(pg, best[pg]) for pg in pages[:suggest.PAGES]], margin, floor)
            if not rel:
                neg.append(bool(pages))
                continue
            ranks.append(next((r for r, pg in enumerate(pages[:10], 1) if pg in rel), None))
            top = pages[:suggest.PAGES]
            prec.append(sum(pg in rel for pg in top) / len(top) if top else 0.0)
            shown.append(len(top))
    n = len(ranks)
    return {"n": n, "hit@1": sum(bool(r and r <= 1) for r in ranks) / n,
            "hit@3": sum(bool(r and r <= suggest.PAGES) for r in ranks) / n,
            "mrr": sum(1 / r for r in ranks if r) / n, "p@3": sum(prec) / n, "pages": sum(shown) / n,
            "wrong": sum(neg) / len(neg) if neg else 0.0}


SUGGEST_VARIANTS = [                         # "bỏ từ khuôn mẫu của đề" đã thử: không đổi chỉ số → bỏ (xem suggest.py)
    ("thân câu + đáp án", {}),
    ("+ RRF phương án sai ×1", {"wrong_weight": 1.0}),
    ("+ RRF phương án sai ×0,5", {"wrong_weight": 0.5}),
    ("+ RRF phương án sai ×0,25", {"wrong_weight": 0.25}),
]

VARIANTS = [
    ("BM25, chỉ thân câu", {"mode": "stem"}),
    ("BM25, thân câu + đáp án", {}),
    ("+ từ điển đồng nghĩa", {"synonyms": True}),
    ("+ minimum_should_match 2<70%", {"msm": "2<70%"}),
    ("+ đồng nghĩa + msm 2<70%", {"synonyms": True, "msm": "2<70%"}),
]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pdf_dir", type=Path)
    ap.add_argument("gold", type=Path, nargs="?", default=GOLD)
    ap.add_argument("--detail", action="store_true", help="in hạng của từng câu")
    ap.add_argument("--msm", default="", help='thử thêm các mức minimum_should_match, vd "2<30%%,2<50%%"')
    ap.add_argument("--semantic", default="", help='các ngưỡng cos của cổng ngữ nghĩa, vd "0.5,0.55,0.59"')
    ap.add_argument("--vlm", action="store_true", help="thêm mô tả hình của VLM (Ollama, RAG_VLM_MODEL) vào đoạn hình")
    a = ap.parse_args(argv)
    variants = VARIANTS + [(f"+ đồng nghĩa + msm {m}", {"synonyms": True, "msm": m}) for m in a.msm.split(",") if m]
    sys.stdout.reconfigure(encoding="utf-8")
    gold = json.loads(a.gold.read_text(encoding="utf-8"))
    t = time.monotonic()
    docs, ix = load_corpus(a.pdf_dir, gold["corpus"], a.vlm)
    print(f"{len(docs)} đoạn / {len(gold['corpus'])} tệp, dựng chỉ mục {time.monotonic() - t:.1f} s; "
          f"{len(gold['questions'])} câu hỏi")
    syn = synonym_files.for_course(gold.get("course_code"))
    types = ["all", "lexical", "paraphrase", "crosslingual", "plain"]
    w = 29
    print(f"{'biến thể':32} " + "  ".join(f"{t[:12]:>{w}}" for t in types) + f"  {'gợi ý sai':>9}")
    print(f"{'':32} " + "  ".join(f"{'Hit@1 @5 @10  MRR nDCG':>{w}}" for _ in types))
    for name, v in variants:
        r = run(gold["questions"], docs, ix, v.get("mode", "stem+answer"), syn if v.get("synonyms") else None,
                v.get("msm"))
        cells = []
        for t in types:
            m = r.get(t)
            cells.append(f"{m['hit@1']:.2f} {m['hit@5']:.2f} {m['hit@10']:.2f} {m['mrr']:.2f} {m['ndcg']:.2f} "
                         f"({m['n']:>2})" if m else "-")
        print(f"{name:32} " + "  ".join(f"{c:>{w}}" for c in cells) + f"  {r['negative']['wrong']:>9.0%}")
        if a.detail:
            for d in r["detail"]:
                print("    ", d)
    print("\nGỢI Ý THEO TRANG (bước 8) – mỗi cặp (câu, phương án sai), từ điển đồng nghĩa bật")
    print(f"{'biến thể':36} {'Hit@1':>6} {'Hit@3':>6} {'MRR':>6} {'P@3':>6} {'trang/câu':>9}  {'gợi ý sai':>9}")

    def row(name, r):
        print(f"{name:36} {r['hit@1']:>6.2f} {r['hit@3']:>6.2f} {r['mrr']:>6.2f} {r['p@3']:>6.2f} {r['pages']:>9.2f}  "
              f"{r['wrong']:>9.0%}  ({r['n']} cặp)")
    for name, v in SUGGEST_VARIANTS:
        row(name, run_suggest(gold["questions"], docs, ix, syn, v.get("wrong_weight")))
    if a.semantic:
        emb = embeddings(a.pdf_dir, docs, gold["questions"])
        if emb is None:
            print("--semantic: chưa cài sentence-transformers (requirements-semantic.txt)")
            return
        thrs = [float(x) for x in a.semantic.split(",")]
        for per_passage, how in ((False, "theo câu"), (True, "từng đoạn")):
            for thr in thrs:
                row(f"+ cổng {how} cos ≥ {thr:g}", run_suggest(gold["questions"], docs, ix, syn,
                                                                gate=(*emb, thr, per_passage)))
        thr = settings.rag_min_similarity
        for m in (0.05, 0.1, 0.15, 0.2):
            row(f"  cổng {thr:g} + bỏ trang kém nhất > {m:g}", run_suggest(gold["questions"], docs, ix, syn,
                                                                          gate=(*emb, thr, False), margin=m))
        for fl in (0.4, 0.45, 0.5):
            row(f"  cổng {thr:g} + bỏ trang cos < {fl:g}", run_suggest(gold["questions"], docs, ix, syn,
                                                                    gate=(*emb, thr, False), floor=fl))


if __name__ == "__main__":
    main()
