"""Chạy Analysis Engine trên CSDL: ghi item_statistics, attempt_clo_results, lộ trình học,
clo_results (BM6b), pi_results (BM3c) và plo_results (BM2)."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from . import analysis


def _df(db: Session, sql: str, **params) -> pd.DataFrame:
    res = db.execute(text(sql), params)
    return pd.DataFrame(res.fetchall(), columns=list(res.keys()))


def clo_thresholds(db: Session, class_section_id: int) -> tuple[dict[int, float], dict[int, float], dict[int, str]]:
    """Ngưỡng đạt, chỉ tiêu và loại bài KT minh chứng của từng CLO (BM6a) cho lớp HP."""
    df = _df(db, """
        SELECT c.id AS clo_id, p.pass_threshold_pct, p.target_pct, p.evidence_type, co.clo_target_pct
        FROM class_sections cs
        JOIN courses co ON co.id = cs.course_id
        JOIN clos c ON c.course_id = cs.course_id
        LEFT JOIN clo_assessment_plans p ON p.clo_id = c.id AND p.semester_id = cs.semester_id
        WHERE cs.id = :cs""", cs=class_section_id)
    thr, tgt, ev = {}, {}, {}
    for r in df.itertuples():
        thr[int(r.clo_id)] = float(r.pass_threshold_pct) if pd.notna(r.pass_threshold_pct) else settings.default_pass_threshold
        tgt[int(r.clo_id)] = float(r.target_pct) if pd.notna(r.target_pct) else float(r.clo_target_pct)
        ev[int(r.clo_id)] = r.evidence_type if isinstance(r.evidence_type, str) else "any"
    return thr, tgt, ev


def analyze_exam(db: Session, exam_id: int) -> dict:
    """Phân tích một bài KT (UC-03 bước 5–6) rồi cập nhật các tầng tổng hợp."""
    run_id = db.execute(text("INSERT INTO sync_runs (exam_id, kind) VALUES (:e, 'analyze')"), {"e": exam_id}).lastrowid
    db.commit()
    try:
        exam = db.execute(text("SELECT id, class_section_id FROM exams WHERE id = :e"), {"e": exam_id}).one()
        cs_id = exam.class_section_id
        thr, _, _ = clo_thresholds(db, cs_id)

        items = _df(db, """
            SELECT a.id AS attempt_id, a.total_score, r.question_id, r.is_correct, r.score_earned,
                   eq.points, q.is_cancelled, q.outline_id
            FROM exam_attempts a
            JOIN item_level_results r ON r.attempt_id = a.id
            JOIN exam_questions eq ON eq.exam_id = a.exam_id AND eq.question_id = r.question_id
            JOIN question_bank q ON q.id = r.question_id
            WHERE a.exam_id = :e AND a.status = 'finished'""", e=exam_id)
        mapping = _df(db, """
            SELECT m.question_id, m.clo_id, m.weight FROM question_clo_mapping m
            JOIN exam_questions eq ON eq.question_id = m.question_id AND eq.exam_id = :e""", e=exam_id)
        for col in ("total_score", "score_earned", "points"):
            if col in items:
                items[col] = items[col].astype(float)
        if not items.empty:
            items["is_correct"] = items.is_correct.astype(int)
        if not mapping.empty:
            mapping["weight"] = mapping.weight.astype(float)

        # 1) Độ khó, độ phân biệt
        stats = analysis.item_statistics(items)
        db.execute(text("DELETE FROM item_statistics WHERE exam_id = :e"), {"e": exam_id})
        for r in stats.itertuples():
            db.execute(text("""INSERT INTO item_statistics (exam_id, question_id, n_students, p_value, di_value)
                               VALUES (:e, :q, :n, :p, :d)"""),
                       {"e": exam_id, "q": r.question_id, "n": r.n_students, "p": r.p_value,
                        "d": None if pd.isna(r.di_value) else r.di_value})

        # 2) Minh chứng CLO từng SV (bỏ câu đã Hủy)
        valid = items[~items.is_cancelled.astype(bool)] if not items.empty else items
        clo = analysis.attempt_clo_scores(valid, mapping, thr, settings.default_pass_threshold)
        db.execute(text("""DELETE r FROM attempt_clo_results r JOIN exam_attempts a ON a.id = r.attempt_id
                           WHERE a.exam_id = :e"""), {"e": exam_id})
        for r in clo.itertuples():
            db.execute(text("""INSERT INTO attempt_clo_results (attempt_id, clo_id, score_earned, score_max, score_pct, is_achieved)
                               VALUES (:a, :c, :se, :sm, :sp, :ok)"""),
                       {"a": r.attempt_id, "c": r.clo_id, "se": round(r.score_earned, 2), "sm": round(r.score_max, 2),
                        "sp": r.score_pct, "ok": bool(r.is_achieved)})

        # 3) Lộ trình học cá nhân
        db.execute(text("""DELETE p FROM personalized_learning_paths p JOIN exam_attempts a ON a.id = p.attempt_id
                           WHERE a.exam_id = :e"""), {"e": exam_id})
        clo_names = dict(db.execute(text("SELECT id, clo_code FROM clos")).fetchall())
        ch_names = dict(db.execute(text("SELECT id, CONCAT('Chương ', chapter_number, ': ', chapter_name) FROM course_outlines")).fetchall())
        if not clo.empty:
            lost_all = valid.merge(mapping, on="question_id")
            lost_all["lost_points"] = (lost_all.points - lost_all.score_earned) * lost_all.weight
            for att, g in clo.groupby("attempt_id"):
                lost = lost_all[lost_all.attempt_id == att].groupby(["clo_id", "outline_id"], dropna=False, as_index=False).lost_points.sum()
                recs = analysis.learning_path(g, lost, thr, settings.default_pass_threshold)
                strong = [clo_names[c] for c in g[g.is_achieved].clo_id]
                weak = [clo_names[c] for c in g[~g.is_achieved].clo_id]
                summary = (f"Đạt {len(strong)}/{len(g)} CĐR môn học"
                           + (f"; chưa đạt: {', '.join(weak)}." if weak else "; đạt toàn bộ CĐR."))
                plan_lines = []
                for rec in recs:
                    ch = ch_names.get(rec["outline_id"], "các nội dung liên quan")
                    plan_lines.append(f"{rec['priority']}. {clo_names[rec['clo_id']]} (thiếu {rec['gap_pct']:.1f}% so với ngưỡng): ôn lại {ch}.")
                pid = db.execute(text("""INSERT INTO personalized_learning_paths (attempt_id, diagnostic_summary, recommended_study_plan)
                                         VALUES (:a, :s, :p)"""),
                                 {"a": int(att), "s": summary, "p": "\n".join(plan_lines) or "Tiếp tục duy trì kết quả."}).lastrowid
                seen = set()
                for rec in recs:
                    key = (rec["clo_id"], rec["outline_id"])
                    if key in seen:
                        continue
                    seen.add(key)
                    db.execute(text("""INSERT INTO learning_path_items (path_id, clo_id, outline_id, priority, gap_pct)
                                       VALUES (:p, :c, :o, :pr, :g)"""),
                               {"p": pid, "c": rec["clo_id"], "o": rec["outline_id"], "pr": rec["priority"], "g": rec["gap_pct"]})

        db.execute(text("UPDATE exams SET status = 'Analyzed' WHERE id = :e"), {"e": exam_id})
        db.commit()
        # 4) Tổng hợp các tầng
        recompute_class_section(db, cs_id)
        n_att = int(items.attempt_id.nunique()) if not items.empty else 0
        db.execute(text("UPDATE sync_runs SET status='success', finished_at=NOW(), n_attempts=:n WHERE id=:r"),
                   {"n": n_att, "r": run_id})
        db.commit()
        return {"exam_id": exam_id, "n_students": n_att, "n_questions": len(stats), "n_clo_rows": len(clo)}
    except Exception as exc:  # ghi nhật ký lỗi rồi ném lại
        db.rollback()
        db.execute(text("UPDATE sync_runs SET status='failed', finished_at=NOW(), message=:m WHERE id=:r"),
                   {"m": str(exc)[:1000], "r": run_id})
        db.commit()
        raise


def recompute_class_section(db: Session, cs_id: int) -> None:
    """BM6b: tổng hợp từng CLO của lớp HP từ các bài KT lấy minh chứng (cộng dồn – BM6d)."""
    thr, tgt, ev = clo_thresholds(db, cs_id)
    rows = _df(db, """
        SELECT r.clo_id, e.assessment_type, COUNT(*) AS n_eval, SUM(r.is_achieved) AS n_ok
        FROM attempt_clo_results r
        JOIN exam_attempts a ON a.id = r.attempt_id
        JOIN exams e ON e.id = a.exam_id
        WHERE e.class_section_id = :cs AND e.status = 'Analyzed'
        GROUP BY r.clo_id, e.assessment_type""", cs=cs_id)
    old = {r.clo_id: (r.analysis, r.improvement) for r in db.execute(
        text("SELECT clo_id, analysis, improvement FROM clo_results WHERE class_section_id = :cs"), {"cs": cs_id})}
    db.execute(text("DELETE FROM clo_results WHERE class_section_id = :cs"), {"cs": cs_id})
    for clo_id, g in rows.groupby("clo_id"):
        clo_id = int(clo_id)
        e_type = ev.get(clo_id, "any")
        g = g if e_type == "any" else g[g.assessment_type == e_type]
        if g.empty:
            continue
        agg = analysis.aggregate([(int(x.n_eval), int(x.n_ok)) for x in g.itertuples()], tgt.get(clo_id, settings.default_clo_target))
        a, i = old.get(clo_id, (None, None))
        db.execute(text("""INSERT INTO clo_results (class_section_id, clo_id, n_evaluated, n_achieved, achieved_pct,
                                  target_pct, is_achieved, analysis, improvement)
                           VALUES (:cs, :c, :n, :k, :p, :t, :ok, :a, :i)"""),
                   {"cs": cs_id, "c": clo_id, "n": agg.n_evaluated, "k": agg.n_achieved, "p": agg.achieved_pct,
                    "t": agg.target_pct, "ok": agg.is_achieved, "a": a, "i": i})
    db.commit()
    cs = db.execute(text("SELECT course_id, semester_id FROM class_sections WHERE id=:cs"), {"cs": cs_id}).one()
    recompute_pi_plans(db, course_id=cs.course_id, semester_id=cs.semester_id)


def recompute_pi_plans(db: Session, course_id: int | None = None, semester_id: int | None = None) -> None:
    """BM3c: kết quả từng PI = cộng dồn kết quả các CLO minh chứng ở môn/học kỳ kế hoạch."""
    plans = _df(db, """SELECT p.id, p.pi_id, p.course_id, p.semester_id, p.target_pct, pi.plo_id
                       FROM pi_assessment_plans p JOIN performance_indicators pi ON pi.id = p.pi_id
                       WHERE (:c IS NULL OR p.course_id = :c) AND (:s IS NULL OR p.semester_id = :s)""",
                c=course_id, s=semester_id)
    years = set()
    for p in plans.itertuples():
        clo_ids = [r[0] for r in db.execute(text("SELECT clo_id FROM pi_plan_clos WHERE plan_id=:p"), {"p": p.id})]
        if not clo_ids:  # mặc định: các CLO của môn có đóng góp cho PLO của PI
            clo_ids = [r[0] for r in db.execute(text("""SELECT c.id FROM clos c JOIN clo_plo_mapping m ON m.clo_id = c.id
                                                        WHERE c.course_id = :c AND m.plo_id = :plo"""),
                                                {"c": p.course_id, "plo": p.plo_id})]
        counts = []
        if clo_ids:
            q = text(f"""SELECT r.n_evaluated, r.n_achieved FROM clo_results r
                         JOIN class_sections cs ON cs.id = r.class_section_id
                         WHERE cs.course_id = :c AND cs.semester_id = :s AND r.clo_id IN ({','.join(map(str, clo_ids))})""")
            counts = [(int(a), int(b)) for a, b in db.execute(q, {"c": p.course_id, "s": p.semester_id})]
        db.execute(text("DELETE FROM pi_results WHERE plan_id = :p"), {"p": p.id})
        agg = analysis.aggregate(counts, float(p.target_pct))
        if agg.n_evaluated:
            db.execute(text("""INSERT INTO pi_results (plan_id, n_evaluated, n_achieved, achieved_pct, target_pct, is_achieved)
                               VALUES (:p, :n, :k, :pct, :t, :ok)"""),
                       {"p": p.id, "n": agg.n_evaluated, "k": agg.n_achieved, "pct": agg.achieved_pct,
                        "t": agg.target_pct, "ok": agg.is_achieved})
        y = db.execute(text("SELECT academic_year FROM semesters WHERE id=:s"), {"s": p.semester_id}).scalar()
        years.add((int(p.plo_id), y))
    db.commit()
    for plo_id, year in years:
        recompute_plo(db, plo_id, year)


def recompute_plo(db: Session, plo_id: int, academic_year: str) -> None:
    """BM3c dòng tổng + BM2: tổng hợp PLO trong năm học từ các PI đã đo."""
    counts = [(int(a), int(b)) for a, b in db.execute(text("""
        SELECT r.n_evaluated, r.n_achieved FROM pi_results r
        JOIN pi_assessment_plans p ON p.id = r.plan_id
        JOIN performance_indicators pi ON pi.id = p.pi_id
        JOIN semesters s ON s.id = p.semester_id
        WHERE pi.plo_id = :plo AND s.academic_year = :y"""), {"plo": plo_id, "y": academic_year})]
    target = db.execute(text("""SELECT COALESCE(
            (SELECT target_pct FROM plo_measurement_plans WHERE plo_id = :plo AND academic_year = :y),
            (SELECT target_pct FROM plos WHERE id = :plo))"""), {"plo": plo_id, "y": academic_year}).scalar()
    agg = analysis.aggregate(counts, float(target))
    if not agg.n_evaluated:
        db.execute(text("DELETE FROM plo_results WHERE plo_id=:plo AND academic_year=:y"), {"plo": plo_id, "y": academic_year})
    else:
        summary = f"Tổng hợp {len(counts)} PI: {agg.n_achieved}/{agg.n_evaluated} lượt SV đạt ({agg.achieved_pct:.2f}%)."
        db.execute(text("""INSERT INTO plo_results (plo_id, academic_year, n_evaluated, n_achieved, achieved_pct, target_pct,
                                  is_achieved, data_summary, computed_at)
                           VALUES (:plo, :y, :n, :k, :p, :t, :ok, :ds, NOW())
                           ON DUPLICATE KEY UPDATE n_evaluated=VALUES(n_evaluated), n_achieved=VALUES(n_achieved),
                             achieved_pct=VALUES(achieved_pct), target_pct=VALUES(target_pct), is_achieved=VALUES(is_achieved),
                             data_summary=VALUES(data_summary), computed_at=NOW()"""),
                   {"plo": plo_id, "y": academic_year, "n": agg.n_evaluated, "k": agg.n_achieved, "p": agg.achieved_pct,
                    "t": agg.target_pct, "ok": agg.is_achieved, "ds": summary})
    db.commit()


def now() -> datetime:
    return datetime.now()
