"""Analysis Engine (Pandas) – tính chỉ số CTT và mức độ đạt CĐR theo biểu mẫu HCMUTE.

Quy ước tính toán (xem Chương 1, mục cơ sở lý thuyết):

* SV dự thi  : lượt thi có status = 'finished'. SV vắng ('absent') không nằm trong mẫu số.
* Câu bỏ trống ('blank') được 0 điểm và VẪN nằm trong mẫu số (giống BM6c: SV 0 điểm vẫn được đếm).
* Độ khó        p_j  = số SV làm đúng câu j / số SV dự thi.
* Độ phân biệt  DI_j = (Đúng_nhóm_trên − Đúng_nhóm_dưới) / n_g, n_g = ⌈0,27·N⌉ (Kelley, 1939).
* Điểm CLO của SV trong một bài KT:
      điểm_đạt_c = Σ_j w_jc · điểm_đạt_j ,  điểm_tối_đa_c = Σ_j w_jc · điểm_j
      SV đạt CLO c  ⇔  điểm_đạt_c ≥ ngưỡng% · điểm_tối_đa_c      (BM6c: "đạt ≥ 60% điểm tối đa")
* CLO của lớp HP (BM6b/6d): cộng dồn số SV đạt và số SV đánh giá qua các bài KT lấy minh chứng;
      tỷ lệ = Σ đạt / Σ đánh giá ; CLO đạt ⇔ tỷ lệ ≥ chỉ tiêu mong muốn.
* PI (BM3c) : cộng dồn kết quả các CLO minh chứng của môn học trong học kỳ kế hoạch.
* PLO (BM3c/BM2): cộng dồn kết quả các PI đo trong năm học; tỷ lệ so với chỉ tiêu CĐR.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

# ------------------------------------------------------------------ hàm thuần (kiểm thử đơn vị)


def item_statistics(items: pd.DataFrame) -> pd.DataFrame:
    """items: cột attempt_id, question_id, is_correct (0/1), total_score – chỉ SV dự thi.

    Trả về DataFrame: question_id, n_students, p_value, di_value.
    """
    if items.empty:
        return pd.DataFrame(columns=["question_id", "n_students", "p_value", "di_value"])
    scores = (items[["attempt_id", "total_score"]].drop_duplicates("attempt_id")
              .sort_values(["total_score", "attempt_id"], ascending=[False, True]).reset_index(drop=True))
    n = len(scores)
    n_g = math.ceil(0.27 * n) if n >= 2 else 0
    upper = set(scores.head(n_g).attempt_id) if n_g else set()
    lower = set(scores.tail(n_g).attempt_id) if n_g else set()
    rows = []
    for qid, g in items.groupby("question_id"):
        p = g.is_correct.sum() / n
        di = None
        if n_g:
            di = (g[g.attempt_id.isin(upper)].is_correct.sum() - g[g.attempt_id.isin(lower)].is_correct.sum()) / n_g
        rows.append({"question_id": int(qid), "n_students": n, "p_value": round(float(p), 4),
                     "di_value": None if di is None else round(float(di), 4)})
    return pd.DataFrame(rows)


def attempt_clo_scores(items: pd.DataFrame, mapping: pd.DataFrame, thresholds: dict[int, float],
                       default_threshold: float = 60.0) -> pd.DataFrame:
    """Điểm từng CLO cho từng lượt thi (minh chứng BM6c).

    items   : attempt_id, question_id, points, score_earned  (chỉ SV dự thi, bỏ câu đã Hủy)
    mapping : question_id, clo_id, weight
    thresholds : {clo_id: ngưỡng %}
    """
    if items.empty or mapping.empty:
        return pd.DataFrame(columns=["attempt_id", "clo_id", "score_earned", "score_max", "score_pct", "is_achieved"])
    df = items.merge(mapping, on="question_id")
    df["earned_w"] = df.score_earned.astype(float) * df.weight.astype(float)
    df["max_w"] = df.points.astype(float) * df.weight.astype(float)
    g = df.groupby(["attempt_id", "clo_id"], as_index=False)[["earned_w", "max_w"]].sum()
    g = g[g.max_w > 0]
    g["score_pct"] = (100 * g.earned_w / g.max_w).round(2)
    thr = g.clo_id.map(lambda c: thresholds.get(int(c), default_threshold))
    # so sánh trên điểm (không làm tròn) để khớp COUNTIF(">= ngưỡng") của BM6c
    g["is_achieved"] = g.earned_w + 1e-9 >= g.max_w * thr / 100
    return g.rename(columns={"earned_w": "score_earned", "max_w": "score_max"})[
        ["attempt_id", "clo_id", "score_earned", "score_max", "score_pct", "is_achieved"]]


@dataclass
class Aggregate:
    n_evaluated: int
    n_achieved: int
    target_pct: float

    @property
    def achieved_pct(self) -> float:
        return round(100 * self.n_achieved / self.n_evaluated, 2) if self.n_evaluated else 0.0

    @property
    def is_achieved(self) -> bool:
        return self.n_evaluated > 0 and self.achieved_pct + 1e-9 >= self.target_pct


def aggregate(counts: list[tuple[int, int]], target_pct: float) -> Aggregate:
    """Cộng dồn (số đánh giá, số đạt) – quy tắc chung của BM6d, BM3c và BM2."""
    return Aggregate(sum(c[0] for c in counts), sum(c[1] for c in counts), float(target_pct))


def learning_path(clo_scores: pd.DataFrame, lost: pd.DataFrame, thresholds: dict[int, float],
                  default_threshold: float = 60.0) -> list[dict]:
    """Khuyến nghị ôn tập cho MỘT lượt thi.

    clo_scores : clo_id, score_pct, is_achieved
    lost       : clo_id, outline_id, lost_points (điểm bị mất theo chương, đã nhân trọng số)
    Trả về danh sách {clo_id, outline_id, gap_pct, priority} – CLO chưa đạt, ưu tiên khoảng cách lớn.
    """
    weak = clo_scores[~clo_scores.is_achieved.astype(bool)].copy()
    if weak.empty:
        return []
    weak["gap_pct"] = weak.apply(lambda r: round(thresholds.get(int(r.clo_id), default_threshold) - float(r.score_pct), 2), axis=1)
    weak = weak[weak.gap_pct > 0].sort_values("gap_pct", ascending=False)
    out, prio = [], 1
    for _, w in weak.iterrows():
        chapters = lost[(lost.clo_id == w.clo_id) & (lost.lost_points > 0)].sort_values("lost_points", ascending=False)
        outline_ids = [None if pd.isna(x) else int(x) for x in chapters.outline_id.head(2)] or [None]
        for oid in outline_ids:
            out.append({"clo_id": int(w.clo_id), "outline_id": oid, "gap_pct": float(w.gap_pct), "priority": prio})
        prio += 1
    return out
