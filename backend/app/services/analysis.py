"""Analysis Engine (Pandas) – tính chỉ số CTT và mức độ đạt CĐR theo biểu mẫu HCMUTE."""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


def item_statistics(items: pd.DataFrame) -> pd.DataFrame:
    """items: cột attempt_id, question_id, is_correct (0/1), total_score – chỉ SV dự thi."""
    if items.empty:
        return pd.DataFrame(columns=["question_id", "n_students", "p_value", "di_value"])
    scores = (items[["attempt_id", "total_score"]].drop_duplicates("attempt_id")
              .sort_values(["total_score", "attempt_id"], ascending=[False, True]).reset_index(drop=True))
    n = len(scores)
    n_g = math.ceil(0.27 * n) if n >= 2 else 0
    upper = set(scores.head(n_g).attempt_id) if n_g else set()
    lower = set(scores.tail(n_g).attempt_id) if n_g else set()
    rows = []
    items = items.copy()
    if {"score_earned", "points"} <= set(items.columns):
        items["_v"] = (items.score_earned.astype(float) / items.points.astype(float)).clip(0, 1)
    else:
        items["_v"] = items.is_correct.astype(float)
    for qid, g in items.groupby("question_id"):
        p = g._v.sum() / n
        di = None
        if n_g:
            di = (g[g.attempt_id.isin(upper)]._v.sum() - g[g.attempt_id.isin(lower)]._v.sum()) / n_g
        rows.append({"question_id": int(qid), "n_students": n, "p_value": round(float(p), 4),
                     "di_value": None if di is None else round(float(di), 4)})
    return pd.DataFrame(rows)


def attempt_clo_scores(items: pd.DataFrame, mapping: pd.DataFrame, thresholds: dict[int, float],
                       default_threshold: float = 60.0) -> pd.DataFrame:
    """Điểm từng CLO cho từng lượt thi (minh chứng BM6c)."""
    if items.empty or mapping.empty:
        return pd.DataFrame(columns=["attempt_id", "clo_id", "score_earned", "score_max", "score_pct", "is_achieved"])
    df = items.merge(mapping, on="question_id")
    df["earned_w"] = df.score_earned.astype(float) * df.weight.astype(float)
    df["max_w"] = df.points.astype(float) * df.weight.astype(float)
    g = df.groupby(["attempt_id", "clo_id"], as_index=False)[["earned_w", "max_w"]].sum()
    g = g[g.max_w > 0]
    g["score_pct"] = (100 * g.earned_w / g.max_w).round(2)
    thr = g.clo_id.map(lambda c: thresholds.get(int(c), default_threshold))
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
    """Khuyến nghị ôn tập cho MỘT lượt thi."""
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


def kr20(correct: "pd.DataFrame") -> float | None:
    """Độ tin cậy của đề (Kuder–Richardson 20) trên ma trận đúng/sai."""
    if correct is None or correct.empty:
        return None
    m = correct.pivot_table(index="attempt_id", columns="question_id", values="is_correct", aggfunc="max").fillna(0)
    k = m.shape[1]
    if k < 2 or m.shape[0] < 2:
        return None
    p = m.mean(axis=0)
    var = m.sum(axis=1).var(ddof=0)
    if var == 0:
        return None
    return round(float(k / (k - 1) * (1 - (p * (1 - p)).sum() / var)), 4)


def cronbach_alpha(scores: "pd.DataFrame") -> float | None:
    """Độ tin cậy Cronbach's alpha cho bài nhiều mức điểm (nhập điểm từng câu/ý)."""
    if scores is None or scores.empty:
        return None
    m = scores.pivot_table(index="attempt_id", columns="question_id", values="score_earned", aggfunc="max").fillna(0).astype(float)
    k = m.shape[1]
    if k < 2 or m.shape[0] < 2:
        return None
    var_t = m.sum(axis=1).var(ddof=0)
    if var_t == 0:
        return None
    return round(float(k / (k - 1) * (1 - m.var(axis=0, ddof=0).sum() / var_t)), 4)
