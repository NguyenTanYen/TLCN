"""UC-04 (mở rộng): giảng viên xem hồ sơ kết quả từng sinh viên và thống kê lớp theo bài kiểm tra.

- Hồ sơ SV: điểm, mức đạt từng CLO (so với ngưỡng θ và trung bình lớp), chẩn đoán, các chương cần học lại
  (lộ trình cá nhân hóa) và chi tiết từng câu trả lời – cho mọi bài KT đã phân tích của lớp học phần.
- Thống kê lớp: chỉ số chung, tỷ lệ SV đạt từng CLO so với mục tiêu, chương cần ôn nhiều nhất, phân bố số CLO đạt,
  kết quả theo mức Bloom, bản đồ nhiệt SV × CLO, danh sách SV cần hỗ trợ.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import check_section_access, get_exam_for, require
from ..models import User
from ..services import lms
from .analytics import rows

router = APIRouter(prefix="/api", tags=["UC-04 Hồ sơ SV & thống kê lớp"])

def _analyzed_exams(db, cs_id):
    return rows(db, """SELECT id, exam_title, assessment_type, exam_type, exam_date, max_score, publish_flag
                       FROM exams WHERE class_section_id=:cs AND status='Analyzed' ORDER BY COALESCE(exam_date, created_at), id""",
                cs=cs_id)


# ------------------------------------------------------------------ hồ sơ từng sinh viên
@router.get("/class-sections/{cs_id}/students/{student_id}/profile")
def student_profile(cs_id: int, student_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    check_section_access(db, u, cs_id)
    st = db.execute(text("""SELECT s.id, s.student_code, s.full_name, s.class_name, s.moodle_user_id, e.status
                            FROM enrollments e JOIN students s ON s.id=e.student_id
                            WHERE e.class_section_id=:cs AND s.id=:s"""), {"cs": cs_id, "s": student_id}).mappings().first()
    if not st:
        raise HTTPException(404, "Sinh viên không thuộc lớp học phần này")
    roster = [r[0] for r in db.execute(text("""SELECT s.id FROM enrollments e JOIN students s ON s.id=e.student_id
                                               WHERE e.class_section_id=:cs ORDER BY s.student_code"""), {"cs": cs_id})]
    i = roster.index(student_id)

    exams = []
    for ex in _analyzed_exams(db, cs_id):
        mine = next((r for r in lms.student_results(db, ex["id"]) if r["student_code"] == st["student_code"]), None)
        if not mine:
            continue
        att = db.execute(text("SELECT id, source, version_id FROM exam_attempts WHERE exam_id=:e AND student_id=:s"),
                         {"e": ex["id"], "s": student_id}).mappings().first()
        scores = [float(r[0]) for r in db.execute(text("""SELECT total_score FROM exam_attempts
                                                          WHERE exam_id=:e AND status='finished'"""), {"e": ex["id"]})]
        rank = None
        answers = []
        if mine["status"] == "finished":
            my_raw = float(db.execute(text("SELECT total_score FROM exam_attempts WHERE id=:a"), {"a": att["id"]}).scalar())
            rank = 1 + sum(1 for s in scores if s > my_raw + 1e-9)
            answers = rows(db, """
                SELECT eq.order_index, q.id AS question_id, q.content, r.response_status, r.is_correct, r.score_earned, eq.points,
                       (SELECT o.opt_label FROM question_options o WHERE o.id=r.selected_option_id) AS chosen,
                       (SELECT GROUP_CONCAT(o.opt_label ORDER BY o.position SEPARATOR ',') FROM question_options o
                         WHERE o.question_id=q.id AND o.is_correct=1) AS correct,
                       (SELECT CONCAT('Chương ', o.chapter_number) FROM course_outlines o WHERE o.id=q.outline_id) AS chapter,
                       (SELECT GROUP_CONCAT(c.clo_code ORDER BY c.clo_code) FROM question_clo_mapping m JOIN clos c ON c.id=m.clo_id
                         WHERE m.question_id=q.id) AS clos,
                       b.name_vi AS bloom, st.p_value
                FROM item_level_results r JOIN exam_questions eq ON eq.exam_id=:e AND eq.question_id=r.question_id
                JOIN question_bank q ON q.id=r.question_id JOIN bloom_levels b ON b.id=q.bloom_level_id
                LEFT JOIN item_statistics st ON st.exam_id=:e AND st.question_id=q.id
                WHERE r.attempt_id=:a ORDER BY eq.order_index""", e=ex["id"], a=att["id"])
            for a in answers:
                a["result"] = "blank" if a["response_status"] == "blank" or not a["chosen"] else ("correct" if a["is_correct"] else "wrong")
                a["is_correct"] = bool(a["is_correct"])
        exams.append({**ex, "max_score": float(ex["max_score"]), "publish_flag": bool(ex["publish_flag"]),
                      "status": mine["status"], "score": mine["score"], "source": att["source"] if att else None,
                      "rank": rank, "n_finished": len(scores),
                      "class_mean": round(sum(scores) / len(scores) * float(ex["max_score"]) / _raw_max(db, ex["id"]), 2) if scores else None,
                      **mine["data"], "answers": answers})

    # tổng hợp CLO trên mọi bài KT đã phân tích (điểm đạt / điểm tối đa của các câu thuộc CLO)
    overall = rows(db, """
        SELECT c.clo_code AS code, c.description, ROUND(100*SUM(r.score_earned)/NULLIF(SUM(r.score_max),0), 2) AS pct,
               COUNT(*) AS n_exams, SUM(r.is_achieved) AS n_achieved,
               (SELECT COALESCE(p.pass_threshold_pct, :thr0) FROM class_sections cs
                  LEFT JOIN clo_assessment_plans p ON p.clo_id=c.id AND p.semester_id=cs.semester_id WHERE cs.id=:cs) AS threshold
        FROM attempt_clo_results r JOIN exam_attempts a ON a.id=r.attempt_id JOIN exams e ON e.id=a.exam_id
        JOIN clos c ON c.id=r.clo_id
        WHERE e.class_section_id=:cs AND e.status='Analyzed' AND a.student_id=:s AND a.status='finished'
        GROUP BY c.id, c.clo_code, c.description ORDER BY c.clo_code""", cs=cs_id, s=student_id,
        thr0=settings.default_pass_threshold)
    for o in overall:
        o["pct"] = float(o["pct"] or 0); o["threshold"] = float(o["threshold"])
        o["achieved"] = o["pct"] + 1e-9 >= o["threshold"]
        o["n_achieved"] = int(o["n_achieved"] or 0)

    # các chương cần học lại (gộp mọi bài KT; ưu tiên theo mức thiếu hụt lớn nhất)
    review: dict[str, dict] = {}
    for ex in exams:
        for it in ex.get("items") or []:
            key = it["chapter"] or f"(chưa gắn chương) {it['clo']}"
            r = review.setdefault(key, {"chapter": key, "clos": set(), "max_gap": 0.0, "exams": set()})
            r["clos"].add(it["clo"]); r["max_gap"] = max(r["max_gap"], it["gap"]); r["exams"].add(ex["exam_title"])
    review_list = sorted(({**r, "clos": sorted(r["clos"]), "exams": sorted(r["exams"])} for r in review.values()),
                         key=lambda r: -r["max_gap"])
    return {"student": dict(st), "prev_id": roster[i - 1] if i > 0 else None,
            "next_id": roster[i + 1] if i + 1 < len(roster) else None, "position": i + 1, "n_students": len(roster),
            "exams": exams, "overall_clos": overall, "review": review_list}


def _raw_max(db, exam_id):
    return float(db.execute(text("SELECT COALESCE(SUM(points),0) FROM exam_questions WHERE exam_id=:e"), {"e": exam_id}).scalar() or 1)


# ------------------------------------------------------------------ thống kê lớp theo bài kiểm tra
@router.get("/class-sections/{cs_id}/stats")
def section_stats(cs_id: int, exam_id: int | None = None, u: User = Depends(require("admin", "lecturer")),
                  db: Session = Depends(get_db)):
    cs = check_section_access(db, u, cs_id)
    exams = _analyzed_exams(db, cs_id)
    for e in exams:
        e["max_score"] = float(e["max_score"]); e["publish_flag"] = bool(e["publish_flag"])
    if not exams:
        return {"exams": [], "exam": None}
    ex = next((e for e in exams if e["id"] == exam_id), None) if exam_id else exams[-1]
    if not ex:
        raise HTTPException(404, "Bài kiểm tra chưa được phân tích hoặc không thuộc lớp này")
    get_exam_for(db, u, ex["id"])
    res = lms.student_results(db, ex["id"])
    sid = {r[0]: r[1] for r in db.execute(text("SELECT student_code, id FROM students WHERE student_code IN :c")
                                          .bindparams(bindparam("c", expanding=True)),
                                          {"c": [r["student_code"] for r in res] or [""]})}
    done = [r for r in res if r["status"] == "finished"]
    maxs = ex["max_score"]

    # CLO: tỷ lệ SV đạt so với mục tiêu, điểm % trung bình, ngưỡng
    clo_meta = {r["clo_code"]: r for r in rows(db, """
        SELECT c.clo_code, c.description, COALESCE(p.pass_threshold_pct, :thr0) AS threshold,
               COALESCE(p.target_pct, co.clo_target_pct) AS target
        FROM clos c JOIN courses co ON co.id=c.course_id
        LEFT JOIN clo_assessment_plans p ON p.clo_id=c.id AND p.semester_id=:s WHERE c.course_id=:c""",
        s=cs.semester_id, c=cs.course_id, thr0=settings.default_pass_threshold)}
    codes = sorted({c["code"] for r in done for c in r["data"].get("clos", [])})
    clos = []
    for code in codes:
        vals = [c for r in done for c in r["data"]["clos"] if c["code"] == code]
        m = clo_meta.get(code, {})
        n_ok = sum(1 for c in vals if c["achieved"])
        clos.append({"code": code, "description": m.get("description", ""), "n": len(vals), "n_achieved": n_ok,
                     "achieved_pct": round(100 * n_ok / len(vals), 2) if vals else None,
                     "avg_pct": round(sum(c["pct"] for c in vals) / len(vals), 2) if vals else None,
                     "threshold": float(m.get("threshold") or settings.default_pass_threshold), "target": float(m.get("target") or 0)})

    # chương cần ôn: số SV có chương đó trong lộ trình, mức thiếu hụt trung bình
    chap: dict[str, dict] = {}
    for r in done:
        seen = set()
        for it in r["data"].get("items", []):
            k = it["chapter"] or "(chưa gắn chương)"
            c = chap.setdefault(k, {"chapter": k, "students": set(), "gaps": [], "clos": set()})
            c["clos"].add(it["clo"]); c["gaps"].append(it["gap"])
            if k not in seen:
                c["students"].add(r["student_code"]); seen.add(k)
    chapters = sorted(({"chapter": c["chapter"], "n_students": len(c["students"]),
                        "pct_students": round(100 * len(c["students"]) / len(done), 2) if done else 0,
                        "avg_gap": round(sum(c["gaps"]) / len(c["gaps"]), 2), "clos": sorted(c["clos"])}
                       for c in chap.values()), key=lambda c: (-c["n_students"], c["chapter"]))

    # phân bố số CLO đạt / SV
    hist = [0] * (len(codes) + 1)
    heat = []
    for r in done:
        k = sum(1 for c in r["data"]["clos"] if c["achieved"])
        hist[k] += 1
        heat.append({"student_id": sid.get(r["student_code"]), "student_code": r["student_code"], "full_name": r["full_name"],
                     "score": r["score"], "n_achieved": k, "n_review": len({i["chapter"] for i in r["data"].get("items", [])}),
                     "clos": {c["code"]: {"pct": c["pct"], "ok": c["achieved"]} for c in r["data"]["clos"]}})
    at_risk = sorted([h for h in heat if h["score"] < maxs / 2 or h["n_achieved"] * 2 < len(codes)],
                     key=lambda h: (h["n_achieved"], h["score"]))

    # kết quả theo mức Bloom (tỷ lệ trả lời đúng)
    bloom = rows(db, """
        SELECT b.id, b.name_vi AS level, COUNT(DISTINCT r.question_id) AS n_items,
               ROUND(100*AVG(r.is_correct), 2) AS pct_correct
        FROM item_level_results r JOIN exam_attempts a ON a.id=r.attempt_id JOIN question_bank q ON q.id=r.question_id
        JOIN bloom_levels b ON b.id=q.bloom_level_id
        WHERE a.exam_id=:e AND a.status='finished' AND q.is_cancelled=0 GROUP BY b.id, b.name_vi ORDER BY b.id""", e=ex["id"])
    for b in bloom:
        b["pct_correct"] = float(b["pct_correct"] or 0)

    # phân bố điểm (10 khoảng)
    bins = [0] * 10
    for r in done:
        bins[min(9, int(r["score"] / maxs * 10))] += 1
    scores = [r["score"] for r in done]
    return {
        "exams": exams, "exam": ex,
        "kpi": {"n_students": len(res), "n_finished": len(done), "n_absent": len(res) - len(done),
                "mean": round(sum(scores) / len(scores), 2) if scores else None,
                "pass_rate": round(100 * sum(1 for s in scores if s >= maxs / 2) / len(scores), 2) if scores else None,
                "n_all_clo": hist[-1] if codes else 0, "n_at_risk": len(at_risk), "n_clos": len(codes)},
        "clos": clos, "chapters": chapters,
        "clo_count_hist": [{"k": k, "n": n} for k, n in enumerate(hist)],
        "bloom": bloom,
        "score_hist": [{"range": f"{i * maxs / 10:g}–{(i + 1) * maxs / 10:g}", "count": c} for i, c in enumerate(bins)],
        "heatmap": heat, "at_risk": at_risk,
        "absent": [{"student_id": sid.get(r["student_code"]), "student_code": r["student_code"], "full_name": r["full_name"]}
                   for r in res if r["status"] != "finished"],
    }
