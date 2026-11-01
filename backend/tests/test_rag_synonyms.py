"""Bước 7: từ điển đồng nghĩa theo môn (nhóm cách nói, trie khớp dài nhất), minimum_should_match, công cụ đo."""
import json
import math
import os
import unicodedata

import pytest

from app.services.rag import evaluate, synonyms
from app.services.rag.search import Index, SYN_WEIGHT, _phrase_terms, analyze, required, syllables

DICT = """
# chú thích bị bỏ qua
khóa ngoại | foreign key | fk
cơ sở dữ liệu | database | csdl
cơ sở dữ liệu quan hệ | relational database
chỉ một cách nói
"""


@pytest.fixture()
def syn():
    return synonyms.parse(DICT)


def _ws(text, plain=False):
    return syllables(text, plain)[0]


def test_groups_parsed_and_single_phrase_lines_dropped(syn):
    assert len(syn.groups) == 3
    assert syn.groups[0] == [["khoaS", "ngoaiJ"], ["foreign", "key"], ["fk"]]


def test_find_longest_match_left_to_right_any_tone_form(syn):
    ws = _ws(unicodedata.normalize("NFD", "Thiết kế cơ sở dữ liệu quan hệ có khoá ngoại"))   # NFD + "khoá" kiểu cũ
    found = [(ws[i:j], alts) for i, j, alts in syn.find(ws)]
    assert found[0] == (_ws("cơ sở dữ liệu quan hệ"), [["relational", "database"]])          # dài nhất, không lấy
    assert found[1] == (_ws("khóa ngoại"), [["foreign", "key"], ["fk"]])                     # cụm ngắn bên trong
    assert len(found) == 2
    assert [alts for _, _, alts in syn.find(_ws("FK"))] == [[["khoaS", "ngoaiJ"], ["foreign", "key"]]]


def test_find_on_plain_query_uses_folded_trie(syn):
    ws = _ws("khoa ngoai la gi", plain=True)
    assert [(i, j, alts) for i, j, alts in syn.find(ws, True)] == [(0, 2, [["foreign", "key"], ["fk"]])]


def test_expansion_weight_capped_to_share_of_original_and_one_concept(syn):
    q = analyze("fk", synonyms=syn)
    own = sum(_phrase_terms(["fk"], False).values())
    expanded = {t: w for t, w in q.terms.items() if t != "fk"}
    # mỗi cách nói thêm vào (max, không cộng) tổng ≤ SYN_WEIGHT × trọng số từ gốc – "khóa ngoại" 4 từ không lấn "fk"
    alt = _phrase_terms(["khoaS", "ngoaiJ"], False)
    assert sum(expanded[t] for t in alt) == pytest.approx(SYN_WEIGHT * own)
    assert q.concepts == [frozenset({"fk"}) | frozenset(expanded)]


def test_bm25_finds_other_wording_but_ranks_typed_wording_first(syn):
    ix = Index.build([(1, "Foreign key tham chiếu tới primary key của bảng khác."),
                      (2, "Khóa ngoại tham chiếu tới khóa chính của bảng khác."),
                      (3, "Bảng lớp lưu thông tin lớp.")])
    assert [i for i, _, _ in ix.score("khóa ngoại", 5)] == [2]                     # không từ điển: chỉ đúng chữ
    assert [i for i, _, _ in ix.score("khóa ngoại", 5, syn)] == [2, 1]             # có từ điển: thêm cách nói khác
    assert [i for i, _, _ in ix.score("foreign key", 5, syn)] == [1, 2]


def test_required_minimum_should_match():
    assert [required(n, "2<70%") for n in (0, 1, 2, 3, 4, 10)] == [0, 1, 2, 2, 2, 7]
    assert required(5, None) == 0


def test_msm_drops_passages_matching_too_few_concepts(syn):
    ix = Index.build([(1, "Khóa ngoại bảo đảm toàn vẹn tham chiếu giữa hai bảng."),
                      (2, "Mỗi bảng có một khóa chính."),
                      (3, "Toàn vẹn dữ liệu.")])
    q = "toàn vẹn tham chiếu khóa ngoại"                      # 4 âm tiết + "khóa ngoại" (cả cụm đồng nghĩa = 1)
    assert len(analyze(q, synonyms=syn).concepts) == 5
    assert {i for i, _, _ in ix.score(q, 5, syn)} == {1, 2, 3}
    assert [i for i, _, _ in ix.score(q, 5, syn, "2<70%")] == [1]


def test_for_course_reads_file_and_reloads_on_change(tmp_path, monkeypatch):
    monkeypatch.setattr(synonyms, "DIR", tmp_path)
    assert synonyms.for_course("XX1") is None and synonyms.for_course(None) is None
    f = tmp_path / "XX1.txt"
    f.write_text("phân vùng | partition\n", encoding="utf-8")
    assert len(synonyms.for_course("XX1").groups) == 1
    f.write_text("phân vùng | partition\nthùng | bucket\n", encoding="utf-8")
    os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 5))
    assert len(synonyms.for_course("XX1").groups) == 2


def test_course_dictionary_files_parse():
    for f in synonyms.DIR.glob("*.txt"):
        s = synonyms.parse(f.read_text(encoding="utf-8"))
        assert s.groups, f.name


def test_evaluate_metrics_on_tiny_corpus():
    docs = [evaluate.Doc("a.pdf", 1), evaluate.Doc("a.pdf", 2), evaluate.Doc("b.pdf", 1)]
    ix = Index.build([(0, "Khóa ngoại tham chiếu khóa chính."), (1, "Giao tác bảo đảm tính nguyên tố."),
                      (2, "Chỉ mục B-tree tìm kiếm nhanh.")])
    qs = [{"id": "1", "type": "lexical", "stem": "Khóa ngoại là gì?", "options": {"A": "tham chiếu"}, "answer": "A",
           "relevant": {"a.pdf": [1]}},
          {"id": "2", "type": "lexical", "stem": "Tính nguyên tố của giao tác", "options": {"A": "x"}, "answer": "A",
           "relevant": {"b.pdf": [1]}},                                    # trang đúng không nằm trong kết quả
          {"id": "3", "type": "negative", "stem": "Định luật Ohm", "options": {"A": "U = IR"}, "answer": "A",
           "relevant": {}}]
    r = evaluate.run(qs, docs, ix)
    assert r["all"]["n"] == 2 and r["all"]["hit@1"] == 0.5 and r["all"]["mrr"] == 0.5 and r["all"]["ndcg"] == 0.5
    assert r["negative"] == {"n": 1, "wrong": 0.0}


def test_ndcg_counts_each_relevant_page_once():
    a1, a2, b1 = ("a", 1), ("a", 2), ("b", 1)
    assert evaluate.ndcg([a1, a2], {a1, a2}) == pytest.approx(1.0)                 # xếp lý tưởng
    assert evaluate.ndcg([a1, a1, a1], {a1, a2}) == pytest.approx(1 / (1 + 1 / math.log2(3)))   # cùng trang: 1 lần
    assert evaluate.ndcg([b1, a1], {a1}) == pytest.approx(1 / math.log2(3))        # trang đúng ở hạng 2
    assert evaluate.ndcg([b1], {a1}) == 0.0


def test_gold_set_is_well_formed():
    gold = json.loads(evaluate.GOLD.read_text(encoding="utf-8"))
    ids = [q["id"] for q in gold["questions"]]
    assert len(ids) == len(set(ids)) and len(ids) >= 50
    for q in gold["questions"]:
        assert q["answer"] in q["options"] and q["type"] in {"lexical", "paraphrase", "crosslingual", "plain",
                                                               "negative"}
        assert set(q["relevant"]) <= set(gold["corpus"]) and bool(q["relevant"]) == (q["type"] != "negative")
