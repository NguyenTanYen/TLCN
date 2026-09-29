"""Kiểm thử đơn vị Analysis Engine – đối chiếu với số liệu mẫu trong biểu mẫu BM06 của HCMUTE."""
import math

import pandas as pd
import pytest

from app.services.analysis import aggregate, attempt_clo_scores, item_statistics, learning_path

# BM6c_CDR1: 31 SV, câu hỏi tối đa 3,2 điểm, chỉ tiêu "đạt ≥ 60% điểm tối đa" -> COUNTIF(">=1.92")
BM6C_SCORES = [2.5, 2.7, 3.1, 3.2, 3, 2.8, 3.2, 2.3, 3.2, 1.1, 3.2, 3.2, 2.7, 3, 0.5, 2.4, 3.2, 2.4, 3.2, 3.2,
               2.8, 0.9, 3.2, 2.5, 3.1, 2.5, 2.6, 2.6, 3.2, 3.2, 3.1]
# BM6d_CDR2 – bài KT 1: 14 SV, tối đa 5 điểm, ngưỡng 65% -> COUNTIF(">=3.25"); SV số 12 được 0 điểm vẫn tính
BM6D_KT1 = [2.5, 3.5, 5, 2.8, 3.3, 4.2, 3.6, 4.5, 3.7, 3.9, 1.8, 0, 4.3, 4.7]


def _items(scores, max_points):
    return pd.DataFrame({"attempt_id": range(1, len(scores) + 1), "question_id": 1,
                         "points": max_points, "score_earned": scores})


def test_bm6c_single_test():
    res = attempt_clo_scores(_items(BM6C_SCORES, 3.2), pd.DataFrame({"question_id": [1], "clo_id": [1], "weight": [1.0]}), {1: 60})
    n_ok = int(res.is_achieved.sum())
    assert len(res) == 31
    assert n_ok == sum(1 for s in BM6C_SCORES if s >= 1.92) == 28
    agg = aggregate([(31, n_ok)], 80)
    assert agg.achieved_pct == 90.32 and agg.is_achieved  # BM6b: 90,32% ≥ 80% -> "Đạt"


def test_bm6d_zero_score_stays_in_denominator():
    res = attempt_clo_scores(_items(BM6D_KT1, 5), pd.DataFrame({"question_id": [1], "clo_id": [2], "weight": [1.0]}), {2: 65})
    assert len(res) == 14
    assert int(res.is_achieved.sum()) == 10


def test_bm6d_multi_test_aggregation():
    agg = aggregate([(14, 10), (15, 8), (12, 9)], 75)  # cộng dồn nhiều bài KT (BM6d)
    assert (agg.n_evaluated, agg.n_achieved) == (41, 27)
    assert agg.achieved_pct == 65.85 and not agg.is_achieved  # "Không đạt" như biểu mẫu


def test_threshold_boundary_is_inclusive():
    # 60% của 3,2 = 1,92 -> đúng biên phải "đạt" (COUNTIF ">=")
    res = attempt_clo_scores(_items([1.92, 1.91], 3.2), pd.DataFrame({"question_id": [1], "clo_id": [1], "weight": [1.0]}), {1: 60})
    assert res.is_achieved.tolist() == [True, False]


def test_weighted_clo_score():
    # câu 1 (2đ) thuộc CLO1 100%; câu 2 (2đ) chia CLO1 0,5 / CLO2 0,5
    items = pd.DataFrame({"attempt_id": [1, 1], "question_id": [1, 2], "points": [2, 2], "score_earned": [2, 0]})
    mapping = pd.DataFrame({"question_id": [1, 2, 2], "clo_id": [1, 1, 2], "weight": [1.0, 0.5, 0.5]})
    r = attempt_clo_scores(items, mapping, {}).set_index("clo_id")
    assert r.loc[1, "score_max"] == 3 and r.loc[1, "score_earned"] == 2 and r.loc[1, "score_pct"] == 66.67
    assert bool(r.loc[1, "is_achieved"]) and not bool(r.loc[2, "is_achieved"])


def _stats_frame(matrix):
    rows = []
    for a, answers in enumerate(matrix, 1):
        total = sum(answers)
        for q, c in enumerate(answers, 1):
            rows.append({"attempt_id": a, "question_id": q, "is_correct": c, "total_score": total})
    return pd.DataFrame(rows)


def test_p_and_di_kelley():
    # 10 SV -> n_g = ceil(2,7) = 3; câu 1 chỉ nhóm trên làm đúng, câu 2 chỉ nhóm dưới làm đúng
    m = [[1, 0, 1, 1, 1], [1, 0, 1, 1, 1], [1, 0, 1, 1, 0], [0, 0, 1, 1, 0], [0, 0, 1, 0, 1],
         [0, 0, 1, 0, 1], [0, 0, 0, 1, 1], [0, 1, 0, 0, 0], [0, 1, 0, 0, 0], [0, 1, 0, 0, 0]]
    s = item_statistics(_stats_frame(m)).set_index("question_id")
    assert math.ceil(0.27 * 10) == 3
    assert s.loc[1, "p_value"] == 0.3 and s.loc[1, "di_value"] == 1.0
    assert s.loc[2, "p_value"] == 0.3 and s.loc[2, "di_value"] == -1.0
    assert s.loc[3, "n_students"] == 10


def test_blank_counts_as_wrong():
    df = _stats_frame([[1, 1], [1, 0], [0, 0], [1, 0]])  # SV 3 bỏ trống cả hai câu -> is_correct = 0
    s = item_statistics(df).set_index("question_id")
    assert s.loc[1, "p_value"] == 0.75 and s.loc[2, "p_value"] == 0.25


def test_learning_path_priorities():
    clo = pd.DataFrame({"clo_id": [1, 2, 3], "score_pct": [30.0, 50.0, 90.0], "is_achieved": [False, False, True]})
    lost = pd.DataFrame({"clo_id": [1, 1, 1, 2], "outline_id": [10, 11, 12, 20], "lost_points": [1.0, 2.0, 0.5, 1.0]})
    p = learning_path(clo, lost, {1: 60, 2: 60})
    assert [x["priority"] for x in p] == [1, 1, 2]
    assert [x["outline_id"] for x in p] == [11, 10, 20]  # CLO1 hụt 30% ưu tiên trước, chương mất nhiều điểm trước
    assert p[0]["gap_pct"] == 30.0


def test_empty_inputs():
    assert item_statistics(pd.DataFrame(columns=["attempt_id", "question_id", "is_correct", "total_score"])).empty
    assert aggregate([], 70).achieved_pct == 0.0 and not aggregate([], 70).is_achieved
