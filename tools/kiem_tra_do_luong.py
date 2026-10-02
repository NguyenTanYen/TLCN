"""Kiểm tra độc lập các độ đo: tính lại từ dữ liệu bài làm gốc (item_level_results) theo đúng công thức
trong báo cáo, KHÔNG dùng mã của hệ thống, rồi so với số liệu hệ thống đã lưu."""
import math, sys
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import settings  # noqa: E402  (đọc DATABASE_URL trong backend/cau_hinh.env)
E = create_engine(sys.argv[1] if len(sys.argv) > 1 else settings.database_url)
q = lambda s: pd.read_sql(s, E)
bad = []
def chk(name, a, b, tol=0.011):
    ok = (a is None and b is None) or (a is not None and b is not None and abs(float(a) - float(b)) <= tol)
    if not ok: bad.append(f"{name}: tính lại={a} hệ thống={b}")
    return ok
n_checks = 0

att = q("SELECT id, exam_id, student_id, status, total_score FROM exam_attempts")
ilr = q("SELECT attempt_id, question_id, selected_option_id, response_status, is_correct, score_earned FROM item_level_results")
eq = q("SELECT exam_id, question_id, points FROM exam_questions")
opt = q("SELECT id, question_id, is_correct FROM question_options")
qb = q("SELECT id, is_cancelled FROM question_bank")
cm = q("SELECT question_id, clo_id, weight FROM question_clo_mapping")
ex = q("SELECT e.id, e.class_section_id, e.assessment_type, e.status FROM exams e")

# 1) Chấm lại từng câu: đúng ⇔ phương án chọn là phương án đúng; điểm = điểm câu nếu đúng
m = ilr.merge(att[["id", "exam_id", "status"]], left_on="attempt_id", right_on="id").merge(eq, on=["exam_id", "question_id"])
m = m.merge(opt.rename(columns={"id": "selected_option_id", "is_correct": "opt_correct"})[["selected_option_id", "opt_correct"]], on="selected_option_id", how="left")
fin = m[m.status == "finished"].copy()
fin["re_correct"] = fin.opt_correct.fillna(0).astype(int)
fin["re_score"] = fin.re_correct * fin.points
n_checks += len(fin)
wrong = fin[(fin.re_correct != fin.is_correct.astype(int)) | ((fin.re_score - fin.score_earned).abs() > 1e-9)]
if len(wrong): bad.append(f"{len(wrong)} câu chấm lệch")
# blank ⇔ không chọn
bl = fin[(fin.response_status == "blank") != fin.selected_option_id.isna()]
if len(bl): bad.append(f"{len(bl)} câu trạng thái bỏ trống không nhất quán")
# tổng điểm từng lượt
tot = fin.groupby("attempt_id").re_score.sum()
for aid, s in tot.items():
    n_checks += 1; chk(f"tổng điểm lượt {aid}", s, att.set_index("id").total_score[aid])

# Các bước 2–5 chỉ xét bài KT đã phân tích (bài vừa đồng bộ lại mà chưa phân tích thì chưa có số liệu để so)
fin = fin[fin.exam_id.isin(set(ex[ex.status == "Analyzed"].id))]
if fin.empty:
    print("Chưa có bài KT nào đã phân tích – không có gì để kiểm tra."); sys.exit(1)

# 2) p, DI (Kelley 27%) – loại câu đã Hủy, chỉ lượt finished; xếp theo tổng điểm giảm dần, hòa theo id lượt
st = q("SELECT exam_id, question_id, n_students, p_value, di_value FROM item_statistics")
for eid, g in fin.groupby("exam_id"):
    cancelled = set(qb[qb.is_cancelled == 1].id)
    g = g[~g.question_id.isin(cancelled)]
    order = att[(att.exam_id == eid) & (att.status == "finished")].sort_values(["total_score", "id"], ascending=[False, True]).id.tolist()
    N = len(order); ng = math.ceil(0.27 * N); up, lo = set(order[:ng]), set(order[-ng:])
    if not N: continue
    for qid, gq in g.groupby("question_id"):
        p = gq.re_correct.sum() / N
        di = (gq[gq.attempt_id.isin(up)].re_correct.sum() - gq[gq.attempt_id.isin(lo)].re_correct.sum()) / ng
        rows_ = st[(st.exam_id == eid) & (st.question_id == qid)]
        if rows_.empty: bad.append(f"thiếu item_statistics bài {eid} câu {qid}"); continue
        row = rows_.iloc[0]
        n_checks += 2; chk(f"p bài {eid} câu {qid}", round(p, 4), row.p_value, 1e-4); chk(f"DI bài {eid} câu {qid}", round(di, 4), row.di_value, 1e-4)

# 3) Điểm CLO từng lượt: Σ w·điểm đạt / Σ w·điểm tối đa; đạt ⇔ ≥ ngưỡng% (so sánh ≥)
plans = q("SELECT p.clo_id, p.pass_threshold_pct, p.target_pct, p.evidence_type, cs.id AS class_section_id FROM clo_assessment_plans p JOIN class_sections cs ON cs.semester_id=p.semester_id")
acr = q("SELECT attempt_id, clo_id, score_earned, score_max, is_achieved FROM attempt_clo_results")
fc = fin[~fin.question_id.isin(set(qb[qb.is_cancelled == 1].id))].merge(cm, on="question_id")
fc["w_earn"] = fc.weight * fc.re_score; fc["w_max"] = fc.weight * fc.points
agg = fc.groupby(["attempt_id", "exam_id", "clo_id"])[["w_earn", "w_max"]].sum().reset_index()
agg = agg.merge(ex[["id", "class_section_id"]], left_on="exam_id", right_on="id").merge(plans, on=["clo_id", "class_section_id"])
agg["ach"] = (agg.w_earn + 1e-9 >= agg.pass_threshold_pct / 100 * agg.w_max).astype(int)
for _, r in agg.iterrows():
    s = acr[(acr.attempt_id == r.attempt_id) & (acr.clo_id == r.clo_id)]
    n_checks += 2
    if s.empty: bad.append(f"thiếu attempt_clo_results lượt {r.attempt_id} CLO {r.clo_id}"); continue
    chk(f"điểm CLO {r.clo_id} lượt {r.attempt_id}", r.w_earn, s.iloc[0].score_earned, 1e-6)
    if int(s.iloc[0].is_achieved) != r.ach: bad.append(f"đạt CLO {r.clo_id} lượt {r.attempt_id} lệch")

# 4) BM6b: lấy các bài KT phù hợp loại minh chứng; Σ đạt / Σ đánh giá; đạt ⇔ tỷ lệ ≥ chỉ tiêu
cr = q("SELECT class_section_id, clo_id, n_evaluated, n_achieved, achieved_pct, target_pct, is_achieved FROM clo_results")
agg = agg.merge(ex[["id", "assessment_type"]].rename(columns={"id": "exam_id"}), on="exam_id")
course_n = {}
for (cs, clo), g in agg.groupby(["class_section_id", "clo_id"]):
    et = g.evidence_type.iloc[0]
    g2 = g[g.apply(lambda r: et == "any" or r.assessment_type == et, axis=1)]
    if g2.empty: continue
    ne, na = len(g2), int(g2.ach.sum()); pct = round(100 * na / ne, 2); tgt = float(g.target_pct.iloc[0])
    rows_ = cr[(cr.class_section_id == cs) & (cr.clo_id == clo)]
    if rows_.empty: bad.append(f"thiếu clo_results lớp {cs} CLO {clo}"); continue
    row = rows_.iloc[0]
    n_checks += 3; chk(f"CLO {clo} n_đánh giá", ne, row.n_evaluated, 0); chk(f"CLO {clo} n_đạt", na, row.n_achieved, 0); chk(f"CLO {clo} tỷ lệ", pct, row.achieved_pct)
    if int(row.is_achieved) != int(pct + 1e-9 >= tgt): bad.append(f"kết luận CLO {clo} lệch")
    course_n.setdefault(cs, [0, 0]); course_n[cs][0] += ne; course_n[cs][1] += na
    print(f"  CLO {clo}: {na}/{ne} = {pct}% (chỉ tiêu {tgt}%) → {'Đạt' if pct >= tgt else 'Không đạt'}")
for cs, (ne, na) in course_n.items():
    print(f"  CĐR môn học lớp {cs}: {na}/{ne} = {round(100*na/ne,2)}%")

# 5) PI = Σ kết quả CLO minh chứng; PLO (năm học) = Σ PI; CTĐT = Σ PLO
pi = q("""SELECT p.id plan_id, p.target_pct, pr.n_evaluated, pr.n_achieved, pr.achieved_pct, pr.is_achieved,
          GROUP_CONCAT(pc.clo_id) clos, p.course_id, p.semester_id, pi.plo_id, s.academic_year
          FROM pi_assessment_plans p JOIN performance_indicators pi ON pi.id=p.pi_id JOIN semesters s ON s.id=p.semester_id
          LEFT JOIN pi_results pr ON pr.plan_id=p.id LEFT JOIN pi_plan_clos pc ON pc.plan_id=p.id GROUP BY p.id""")
cs_info = q("SELECT id, course_id, semester_id FROM class_sections")
plo_sum = {}
for _, r in pi.iterrows():
    if pd.isna(r.n_evaluated): continue
    if r.clos: clos = [int(x) for x in str(r.clos).split(",")]
    else:
        clos = q(f"""SELECT DISTINCT m.clo_id FROM clo_plo_mapping m JOIN clos c ON c.id=m.clo_id WHERE m.plo_id={r.plo_id} AND c.course_id={r.course_id}""").clo_id.tolist()
    css = cs_info[(cs_info.course_id == r.course_id) & (cs_info.semester_id == r.semester_id)].id.tolist()
    sub = cr[cr.class_section_id.isin(css) & cr.clo_id.isin(clos)]
    ne, na = int(sub.n_evaluated.sum()), int(sub.n_achieved.sum())
    n_checks += 2; chk(f"PI plan {r.plan_id} n_đánh giá", ne, r.n_evaluated, 0); chk(f"PI plan {r.plan_id} n_đạt", na, r.n_achieved, 0)
    k = (r.plo_id, r.academic_year); plo_sum.setdefault(k, [0, 0]); plo_sum[k][0] += ne; plo_sum[k][1] += na
pr = q("SELECT p.plo_code, r.plo_id, r.academic_year, r.n_evaluated, r.n_achieved, r.achieved_pct, r.target_pct, r.is_achieved FROM plo_results r JOIN plos p ON p.id=r.plo_id")
prog = {}
for (plo, y), (ne, na) in plo_sum.items():
    rows_ = pr[(pr.plo_id == plo) & (pr.academic_year == y)]
    if not ne: continue
    if rows_.empty: bad.append(f"thiếu plo_results PLO {plo} năm {y}"); continue
    row = rows_.iloc[0]
    pct = round(100 * na / ne, 2)
    n_checks += 3; chk(f"PLO {row.plo_code} n", ne, row.n_evaluated, 0); chk(f"PLO {row.plo_code} đạt", na, row.n_achieved, 0); chk(f"PLO {row.plo_code} %", pct, row.achieved_pct)
    if int(row.is_achieved) != int(pct + 1e-9 >= float(row.target_pct)): bad.append(f"kết luận PLO {row.plo_code} lệch")
    print(f"  PLO {row.plo_code} ({y}): {na}/{ne} = {pct}% (chỉ tiêu {row.target_pct}%) → {'Đạt' if pct >= float(row.target_pct) else 'Không đạt'}")
    prog.setdefault(y, [0, 0]); prog[y][0] += ne; prog[y][1] += na
for y, (ne, na) in prog.items(): print(f"  CTĐT ({y}): {na}/{ne} = {round(100*na/ne,2)}%")

print(f"\nSố phép so sánh: {n_checks}; lệch: {len(bad)}")
print("KẾT LUẬN: các độ đo của hệ thống KHỚP với tính lại độc lập." if not bad else "KẾT LUẬN: CÓ SAI LỆCH – xem danh sách dưới.")
for b in bad[:30]: print(" -", b)
sys.exit(1 if bad else 0)
