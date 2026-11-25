import pandas as pd
from sqlalchemy import text

from app.database import engine
from app.services import results


def _ev(rows):
    df = pd.DataFrame(rows, columns=["student_id", "clo_id", "earned", "smax", "thr"])
    df["need"] = df.smax * df.thr / 100
    return df


def test_student_counted_once_per_pi_across_clos():
    ev = _ev([(1, 10, 3, 5, 60), (1, 11, 2, 5, 60), (2, 10, 5, 5, 60), (2, 11, 4, 5, 60), (3, 10, 1, 5, 60), (3, 11, 1, 5, 60)])
    assert results._student_counts(ev, [10, 11]) == (3, 1)
    assert results._student_counts(ev, [10]) == (3, 2)
    assert results._student_counts(ev, [11]) == (3, 1)


def test_student_threshold_is_weighted_by_clo_threshold():
    ev = _ev([(1, 10, 4, 10, 40), (1, 11, 8, 10, 80), (2, 10, 3, 10, 40), (2, 11, 8, 10, 80)])
    assert results._student_counts(ev, [10, 11]) == (2, 1)


def test_boundary_exactly_at_threshold_is_achieved():
    ev = _ev([(1, 10, 3, 5, 60), (2, 10, 2.99, 5, 60)])
    assert results._student_counts(ev, [10]) == (2, 1)


def test_empty_and_unmatched_clos():
    assert results._student_counts(pd.DataFrame(), [1]) == (0, 0)
    assert results._student_counts(_ev([(1, 10, 3, 5, 60)]), [99]) == (0, 0)


def test_pi_result_counts_each_student_once():
    with engine.connect() as c:
        rows = c.execute(text("""SELECT r.plan_id, r.n_evaluated, pl.course_id, pl.semester_id
                                 FROM pi_results r JOIN pi_assessment_plans pl ON pl.id=r.plan_id""")).all()
        assert rows
        for plan_id, n, course_id, sem in rows:
            n_students = c.execute(text("""SELECT COUNT(DISTINCT a.student_id) FROM exam_attempts a JOIN exams e ON e.id=a.exam_id
                                           JOIN class_sections cs ON cs.id=e.class_section_id
                                           WHERE cs.course_id=:c AND cs.semester_id=:s AND a.status='finished'"""),
                                   {"c": course_id, "s": sem}).scalar()
            assert n <= n_students


import json
from pathlib import Path

from app.services import analysis

_BM = json.loads((Path(__file__).parent / "data" / "bieu_mau_goc.json").read_text(encoding="utf-8"))


def _form_ids():
    return [k for k in _BM if not k.startswith("_")]


def test_reproduce_counts_of_real_form_sheets():
    for key in _form_ids():
        sh = _BM[key]
        thr = 100 * sh["diem_can_dat"] / sh["diem_toi_da"]
        ev = _ev([(i, 1, s, sh["diem_toi_da"], thr) for i, s in enumerate(sh["diem"])])
        n_eval, n_ok = results._student_counts(ev, [1])
        assert (n_ok, n_eval) == (sh["bieu_mau_ghi"]["dat"], sh["bieu_mau_ghi"]["danh_gia"]), (key, sh["nguon"])


def test_pooling_matches_form_totals():
    for key, sh in _BM["_tong_hop"].items():
        rows = sh.get("cdr") or sh.get("luot") or sh["pi"]
        agg = analysis.aggregate([(b, a) for a, b in rows], sh["chi_tieu"])
        assert (agg.n_achieved, agg.n_evaluated) == tuple(sh["tong"]), (key, sh["nguon"])
    f = _BM["_tong_hop"]["BM3f_attt_ctdt"]
    agg = analysis.aggregate([(b, a) for a, b in f["pi"]], f["chi_tieu"])
    assert agg.achieved_pct == 90.61 and agg.is_achieved


def test_threshold_decision_is_greater_or_equal_with_zero_scores_counted():
    ev = _ev([(1, 1, 0.0, 2.0, 60), (2, 1, 1.2, 2.0, 60), (3, 1, 1.19, 2.0, 60), (4, 1, 2.0, 2.0, 60)])
    assert results._student_counts(ev, [1]) == (4, 2)
