"""Công cụ dòng lệnh: khởi tạo CSDL, tạo dữ liệu minh họa, mô phỏng bài làm.

    python -m app.cli bootstrap        # (container) chờ MySQL, tạo CSDL + dữ liệu minh họa nếu chưa có, cài cầu nối
    python -m app.cli init-db          # tạo 51 bảng + dữ liệu tham chiếu (BM2, phân công PIs)
    python -m app.cli seed-demo        # tài khoản, môn DBMS330284, CLO, câu hỏi, lớp HP, 2 bài KT
    python -m app.cli simulate-moodle  # (môi trường thử) dựng dữ liệu Moodle mô phỏng, đồng bộ & phân tích
    python -m app.cli install-bridge   # cài view/thủ tục cầu nối vào CSDL (khi đã có CSDL Moodle)
"""
from __future__ import annotations

import csv
import io
import math
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymysql
from sqlalchemy import text

from . import demo_data as D
from .config import settings
from .database import SessionLocal
from .models import (CLO, CLOAssessmentPlan, CLOPLOMapping, ClassSection, Course, CourseOutline, Enrollment, Exam,
                     ExamQuestion, Lecturer, PIAssessmentPlan, PIPlanCLO, Question, QuestionCLO, QuestionOption, Student, User)
from .security import hash_password
from .services import moodle, results

DB_DIR = Path(__file__).resolve().parents[2] / "database"
LABELS = "ABCDEFGHIJ"


def _raw_conn(database: str | None = None):
    u = urlparse(settings.database_url.replace("mysql+pymysql", "mysql"))
    return pymysql.connect(host=u.hostname or "127.0.0.1", port=u.port or 3306, user=unquote(u.username or "root"),
                           password=unquote(u.password or ""), database=database, charset="utf8mb4", autocommit=True)


def run_sql_file(path: Path, database: str | None = None) -> None:
    conn = _raw_conn(database)
    try:
        cur = conn.cursor()
        for stmt in moodle.split_statements(path.read_text(encoding="utf-8")):
            head = stmt.lstrip().upper()
            if head.startswith("CREATE DATABASE") or (database and head.startswith("USE ")):
                continue                          # tệp SQL ghi sẵn "assessment_db" – luôn chạy trên CSDL đích đã chọn
            cur.execute(stmt)
    finally:
        conn.close()


def init_db() -> None:
    name = settings.app_db_name                   # theo DATABASE_URL trong cau_hinh.env
    conn = _raw_conn(); conn.cursor().execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"); conn.close()
    run_sql_file(DB_DIR / "01_schema.sql", name)
    run_sql_file(DB_DIR / "03_seed_reference.sql", name)
    run_sql_file(DB_DIR / "04_ctdt_2026.sql", name)
    print(f"Đã tạo CSDL {name} (51 bảng), nạp dữ liệu tham chiếu và CTĐT CNTT 2026, KTDL 2026.")


def seed_demo() -> None:
    db = SessionLocal()
    sem = db.execute(text("SELECT id FROM semesters WHERE academic_year='2024-2025' AND term=1")).scalar()
    course = db.query(Course).filter_by(course_code="DBMS330284").one()
    son = db.query(Lecturer).filter_by(full_name="Nguyễn Thành Sơn").one()
    binh = db.query(Lecturer).filter_by(full_name="Trần Trọng Bình").one()
    # --- tài khoản
    admin = User(username="admin", password_hash=hash_password("Admin@123"), full_name="Trưởng Bộ môn KTDL", role="admin")
    u_son = User(username="gv.son", password_hash=hash_password("Gv@123456"), full_name=son.full_name, role="lecturer")
    u_binh = User(username="gv.binh", password_hash=hash_password("Gv@123456"), full_name=binh.full_name, role="lecturer")
    db.add_all([admin, u_son, u_binh]); db.flush()
    son.user_id, binh.user_id = u_son.id, u_binh.id
    # --- đề cương, CLO, ma trận CLO-PLO, kế hoạch CLO (BM6a)
    outlines = {}
    for n, name in D.CHAPTERS:
        o = CourseOutline(course_id=course.id, chapter_number=n, chapter_name=name); db.add(o); db.flush(); outlines[n] = o.id
    plo_id = dict(db.execute(text("SELECT plo_code, id FROM plos WHERE program_id=1")).fetchall())
    clo_ids = {}
    for code, desc, bloom, maps in D.CLOS:
        c = CLO(course_id=course.id, clo_code=code, description=desc, bloom_level_id=bloom); db.add(c); db.flush(); clo_ids[code] = c.id
        for pc, lv in maps:
            db.add(CLOPLOMapping(clo_id=c.id, plo_id=plo_id[pc], level=lv))
    for code, txt, ev, method, thr, tgt in D.CLO_PLANS:
        db.add(CLOAssessmentPlan(clo_id=clo_ids[code], semester_id=sem, assessments_text=txt, evidence_type=ev, method=method,
                                 cycle="1 lần/HK", pass_threshold_pct=thr, target_pct=tgt))
    course.clo_target_pct = 75
    # --- kế hoạch đo PI minh họa (BM3b) dùng môn DBMS330284 làm minh chứng trong HKI 24-25
    for plo_code, pi_code, clos in [("1.3", "PI 1", ["CLO1", "CLO2"]), ("4.3", "PI 1", ["CLO3", "CLO4"])]:
        pi = db.execute(text("""SELECT pi.id FROM performance_indicators pi JOIN plos p ON p.id=pi.plo_id
                                WHERE p.plo_code=:p AND pi.pi_code=:c"""), {"p": plo_code, "c": pi_code}).scalar()
        db.execute(text("INSERT IGNORE INTO pi_courses (pi_id, course_id) VALUES (:p, :c)"), {"p": pi, "c": course.id})
        plan = PIAssessmentPlan(pi_id=pi, course_id=course.id, semester_id=sem, method="Bài thi trắc nghiệm (Moodle/giấy)",
                                cycle="2 năm/lần", target_pct=75, lecturer_id=son.id)
        db.add(plan); db.flush()
        for c in clos:
            db.add(PIPlanCLO(plan_id=plan.id, clo_id=clo_ids[c]))
    db.execute(text("""INSERT IGNORE INTO assessment_assignments (semester_id, course_id, lecturer_id, note)
                       VALUES (:s, :c, :l, 'Đánh giá theo 4 CĐR môn học')"""), {"s": sem, "c": course.id, "l": son.id})
    # --- CTĐT 2026 (CNTT, KTDL): CLO của môn đóng góp cho PLO1/PLO6/PLO7; KTDL 2026 đo PI6.2, PI7.1 tại môn này
    for prog in ("CNTT-2026", "KTDL-2026"):
        pid = db.execute(text("SELECT id FROM programs WHERE code=:c"), {"c": prog}).scalar()
        if not pid:
            continue
        p26 = dict(db.execute(text("SELECT plo_code, id FROM plos WHERE program_id=:p"), {"p": pid}).fetchall())
        for clo, plo, lv in (("CLO1", "PLO1", "R"), ("CLO2", "PLO6", "R"), ("CLO3", "PLO6", "M"), ("CLO4", "PLO7", "M")):
            if plo in p26:
                db.add(CLOPLOMapping(clo_id=clo_ids[clo], plo_id=p26[plo], level=lv))
        if prog == "KTDL-2026":
            for pi_code, clos in (("PI6.2", ["CLO2", "CLO3"]), ("PI7.1", ["CLO4"])):
                pi = db.execute(text("""SELECT pi.id FROM performance_indicators pi JOIN plos p ON p.id=pi.plo_id
                                        WHERE p.program_id=:p AND pi.pi_code=:c"""), {"p": pid, "c": pi_code}).scalar()
                plan = PIAssessmentPlan(pi_id=pi, course_id=course.id, semester_id=sem, method="Bài thi trắc nghiệm + bài tập lớn",
                                        cycle="2 năm/lần", target_pct=75, lecturer_id=son.id)
                db.add(plan); db.flush()
                for c in clos:
                    db.add(PIPlanCLO(plan_id=plan.id, clo_id=clo_ids[c]))
    # --- CLO → PI (góp ý F2a): mỗi cặp CLO–PLO gắn với PI mà kế hoạch đo lấy CLO làm minh chứng (hoặc PI đầu tiên của PLO)
    db.flush()
    from .services.outcomes import backfill_clo_pi
    backfill_clo_pi(db.connection(), course.id)
    # --- đề cương chi tiết phiên bản 1 đã duyệt (góp ý F1): nội dung chương, đánh giá học phần, tài liệu
    from .models import CourseSyllabus, SyllabusAssessment, SyllabusReference
    clo_obj = {c.clo_code: c for c in db.query(CLO).filter_by(course_id=course.id)}
    for o in db.query(CourseOutline).filter_by(course_id=course.id):
        content, lt, th, act, cl = D.CHAPTER_DETAIL[o.chapter_number]
        o.content, o.theory_hours, o.practice_hours, o.teaching_activities = content, lt, th, act
        o.clos = [clo_obj[x] for x in cl]
    syl = CourseSyllabus(course_id=course.id, version_no=1, status="approved", effective_semester_id=sem,
                         approved_by=admin.id, approved_at=datetime(2024, 8, 15), updated_by=admin.id, **D.SYLLABUS)
    for i, (code, name, method, timing, w, cl) in enumerate(D.SYL_ASSESS, 1):
        syl.assessments.append(SyllabusAssessment(component_code=code, name=name, method=method, timing=timing, weight_pct=w,
                                                  sort_order=i, clos=[clo_obj[x] for x in cl]))
    for i, (t, cit) in enumerate(D.SYL_REFS, 1):
        syl.references.append(SyllabusReference(ref_type=t, citation=cit, sort_order=i))
    db.add(syl)
    if not course.description:
        course.description = ("Học phần trình bày kiến trúc và hoạt động của hệ quản trị CSDL SQL Server: lập trình T-SQL, trigger, "
                              "giao tác và điều khiển đồng thời, chỉ mục và tối ưu truy vấn, bảo mật, sao lưu và phục hồi.")
    # --- lớp HP + sinh viên (mỗi SV có tài khoản: MSSV / Sv@123456)
    cs = ClassSection(course_id=course.id, semester_id=sem, lecturer_id=son.id, section_code="DBMS330284_01"); db.add(cs); db.flush()
    pw = hash_password("Sv@123456")
    for code, name in D.student_list(40):
        u = User(username=code, password_hash=pw, full_name=name, role="student"); db.add(u); db.flush()
        s = Student(user_id=u.id, student_code=code, full_name=name, class_name="22133A"); db.add(s); db.flush()
        db.add(Enrollment(class_section_id=cs.id, student_id=s.id))
    # --- ngân hàng câu hỏi
    qids = []
    for ch, bloom, clo, content, opts, correct, _b in D.Q:
        q = Question(course_id=course.id, outline_id=outlines[ch], bloom_level_id=bloom, content=content, created_by=u_son.id)
        for i, o in enumerate(opts):
            q.options.append(QuestionOption(position=i + 1, opt_label=LABELS[i], content=o, is_correct=(i == correct)))
        q.clo_links.append(QuestionCLO(clo_id=clo_ids[clo], weight=1))
        db.add(q); db.flush(); qids.append(q.id)
    # --- bài KT quá trình (giấy, 10 câu chương 1-3) và thi cuối kỳ (Moodle, 20 câu)
    e1 = Exam(class_section_id=cs.id, exam_title="Kiểm tra quá trình (giấy)", assessment_type="process", exam_type="paper",
              exam_date=date(2024, 10, 15), duration_minutes=30, max_score=10, created_by=u_son.id)
    for i, qi in enumerate([0, 1, 2, 3, 5, 6, 7, 10, 11, 14], 1):
        e1.questions.append(ExamQuestion(question_id=qids[qi], order_index=i, points=1))
    e2 = Exam(class_section_id=cs.id, exam_title="Thi cuối kỳ (Moodle)", assessment_type="final", exam_type="online",
              exam_date=date(2025, 1, 8), duration_minutes=60, max_score=10, created_by=u_son.id)
    for i, qi in enumerate([4, 8, 9, 12, 13, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29], 1):
        e2.questions.append(ExamQuestion(question_id=qids[qi], order_index=i, points=0.5))
    db.add_all([e1, e2]); db.commit()
    cs2 = _seed_second_section(db, course, sem, son, clo_ids, u_son.id)
    _seed_materials(db, course.id, outlines, u_son.id)
    print(f"Đã tạo dữ liệu minh họa: lớp HP {cs.section_code}, 40 SV, {len(qids)} câu hỏi, bài KT #{e1.id} (giấy) và #{e2.id} (Moodle); "
          f"lớp {cs2} (cùng GV, cùng môn) có bài nhập điểm.")


def _seed_materials(db, course_id: int, outlines: dict, user_id: int) -> None:
    """Học liệu minh họa của học phần (slide 6 chương + giáo trình trích): nguồn cho gợi ý đọc đúng trang khi phân tích bài KT."""
    from .services import hoc_lieu_mau, materials
    for m in hoc_lieu_mau.samples(outlines):
        materials.add_material(db, course_id=course_id, title=m["title"], filename=m["filename"], data=m["data"],
                               material_type=m["material_type"], outline_id=m["outline_id"], user_id=user_id)


def _seed_second_section(db, course, sem, lecturer, clo_ids, user_id) -> str:
    """GV dạy nhiều lớp của cùng một môn: lớp DBMS330284_02 (35 SV) với một bài tự luận nhập điểm từng câu."""
    from .services import manual
    cs = ClassSection(course_id=course.id, semester_id=sem, lecturer_id=lecturer.id, section_code="DBMS330284_02"); db.add(cs); db.flush()
    rng = random.Random(23)
    for i, (_, name) in enumerate(D.student_list(75)[40:]):
        s = Student(student_code=f"2213{101 + i:04d}", full_name=name, class_name="22133B"); db.add(s); db.flush()
        db.add(Enrollment(class_section_id=cs.id, student_id=s.id))
    e = Exam(class_section_id=cs.id, exam_title="Bài tập lớn: thiết kế và cài đặt CSDL (tự luận)", assessment_type="process",
             exam_type="manual", exam_date=date(2024, 11, 20), max_score=10, status="Published", created_by=user_id)
    db.add(e); db.flush()
    items = [("Câu 1 – Mô hình hóa yêu cầu, lược đồ quan hệ", 3, {"CLO1": 1}), ("Câu 2 – Cài đặt ràng buộc, chỉ mục", 3, {"CLO2": 1}),
             ("Câu 3 – Thủ tục, trigger và giao tác", 4, {"CLO3": 0.5, "CLO4": 0.5})]
    manual.add_items(db, e, course.id, [{"title": t, "points": p, "clos": [{"clo_id": clo_ids[c], "weight": w} for c, w in m.items()]}
                                         for t, p, m in items], user_id)
    db.flush()
    qids = [q.question_id for q in sorted(e.questions, key=lambda q: q.order_index)]
    rows = []
    for k, (sid,) in enumerate(db.execute(text("SELECT student_id FROM enrollments WHERE class_section_id=:c ORDER BY student_id"), {"c": cs.id})):
        if k in (5, 21):
            rows.append({"student_id": sid, "absent": True, "scores": {}}); continue
        ab = rng.gauss(0.68, 0.18)
        rows.append({"student_id": sid, "scores": {str(q): round(max(0, min(p, p * (ab + rng.gauss(0, 0.12)))) * 4) / 4
                                                   for q, (_, p, _m) in zip(qids, items)}})
    manual.save_grades(db, e, rows)
    results.analyze_exam(db, e.id)
    return cs.section_code


# ------------------------------------------------------------------ mô phỏng bài làm (mô hình IRT 2 tham số)
def _abilities(n: int, seed: int = 7) -> list[float]:
    rng = random.Random(seed)
    return [rng.gauss(0.75, 0.9) for _ in range(n)]


def _answer(rng: random.Random, theta: float, b: float, n_opts: int, correct: int, trap: bool) -> int | None:
    if rng.random() < 0.03:
        return None  # bỏ trống
    p = 1 / (1 + math.exp(-1.7 * (theta - b)))
    if trap:  # câu "bẫy": SV khá hay chọn nhầm phương án A
        if theta > 0.8 and rng.random() < 0.92:
            return 0
    if rng.random() < p:
        return correct
    wrong = [i for i in range(n_opts) if i != correct]
    return rng.choice(wrong)


# ------------------------------------------------------------------ mô phỏng THỜI GIAN làm bài trên Quiz (dữ liệu minh họa)
QUIZ_TIME_LIMIT = 45 * 60           # Quiz cuối kỳ: 45 phút, hết giờ Moodle tự nộp
RAPID_GUESSERS = (16, 17)           # SV thứ 17, 18 (22130017, 22130018): chọn đại 20 câu trong khoảng 1 phút rồi nộp
IDLE_UNTIL_TIMEOUT = (5, 22)        # SV thứ 6, 23 (22130006, 22130023): chọn xong trong ~6 phút, không nộp, để hết giờ tự nộp


def timing_plan(trng: random.Random, i: int, n_answered: int, limit: int = QUIZ_TIME_LIMIT, last_attempt: bool = True):
    """Thời điểm (giây kể từ lúc bắt đầu) SV thứ i chọn đáp án từng câu đã trả lời và lúc nộp bài.
    Trả về (offsets, finish, kiểu). Dùng chung cho Moodle mô phỏng và kịch bản tạo dữ liệu trên Moodle thật."""
    t, offs = 0.0, []
    if last_attempt and i in RAPID_GUESSERS:
        for _ in range(n_answered):
            t += trng.uniform(1.5, 4.0); offs.append(round(t))
        return offs, round(t + trng.uniform(5, 20)), "chon_dai"
    if last_attempt and i in IDLE_UNTIL_TIMEOUT:
        for _ in range(n_answered):
            t += trng.uniform(10, 25); offs.append(round(t))
        return offs, limit, "treo_may"
    gaps = [min(300.0, max(12.0, trng.lognormvariate(math.log(70), 0.5))) for _ in range(n_answered)]
    scale = min(1.0, limit * 0.85 / max(1.0, sum(gaps)))
    for g in gaps:
        t += g * scale; offs.append(round(t))
    return offs, min(limit - 30, round(t + trng.uniform(20, 240))), "binh_thuong"


def simulate_moodle() -> None:
    """Chỉ dùng cho môi trường thử: tạo CSDL `moodle` mô phỏng (bảng Moodle 4.4 + Offline Quiz) có bài làm đã xáo đáp án.

    - Bài online: Quiz 900 – lượt làm bài của SV (Moodle tự chấm).
    - Bài giấy: Offline Quiz 910 – 2 mã đề A/B (xáo câu và phương án theo mã đề), phiếu đã được Moodle quét & chấm.
    """
    conn = _raw_conn(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_name=%s",
                (settings.moodle_db_name, f"{settings.moodle_prefix}config"))
    if cur.fetchone()[0]:  # có bảng mdl_config -> đây là Moodle thật, tuyệt đối không xóa
        conn.close()
        raise SystemExit(f"CSDL `{settings.moodle_db_name}` là Moodle thật – đặt MOODLE_DB_NAME khác để chạy mô phỏng.")
    cur.execute(f"DROP DATABASE IF EXISTS `{settings.moodle_db_name}`")
    cur.execute(f"CREATE DATABASE `{settings.moodle_db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"); conn.close()
    run_sql_file(DB_DIR / "00_moodle_subset_for_test.sql", settings.moodle_db_name)
    db = SessionLocal()
    exam = db.query(Exam).filter_by(exam_type="online").order_by(Exam.id).first()
    studs = db.execute(text("""SELECT s.student_code, s.full_name FROM enrollments e JOIN students s ON s.id=e.student_id
                               WHERE e.class_section_id=:cs ORDER BY s.student_code"""), {"cs": exam.class_section_id}).fetchall()
    theta = _abilities(len(studs))
    rng = random.Random(99)
    conn = _raw_conn(settings.moodle_db_name); cur = conn.cursor()
    cur.execute("SET SESSION sql_mode=''")
    cur.execute("INSERT INTO mdl_course (id, category, fullname, shortname, summary) VALUES (50,1,'Hệ quản trị CSDL','DBMS330284_01','')")
    cur.execute("INSERT INTO mdl_context (id, contextlevel, instanceid, path, depth) VALUES (70,50,50,'/1/70',2)")
    cur.execute("INSERT INTO mdl_role (id,name,shortname,description,sortorder,archetype) VALUES (3,'','editingteacher','',3,'editingteacher'),(5,'','student','',5,'student')")
    cur.execute("INSERT INTO mdl_enrol (id, enrol, status, courseid) VALUES (60,'manual',0,50)")
    for i, (code, name) in enumerate(studs):
        uid = 100 + i
        last, first = name.rsplit(" ", 1)
        cur.execute("INSERT INTO mdl_user (id, username, idnumber, firstname, lastname, email, deleted, description) VALUES (%s,%s,'',%s,%s,%s,0,'')",
                    (uid, code, first, last, f"{code}@student.hcmute.edu.vn"))
        cur.execute("INSERT INTO mdl_user_enrolments (status, enrolid, userid) VALUES (0,60,%s)", (uid,))
        cur.execute("INSERT INTO mdl_role_assignments (roleid, contextid, userid) VALUES (5,70,%s)", (uid,))
    cur.execute("INSERT INTO mdl_user (id, username, idnumber, firstname, lastname, email, deleted, description) VALUES (99,'gv.son','','Sơn','Nguyễn Thành','son@hcmute.edu.vn',0,'')")
    cur.execute("INSERT INTO mdl_question_categories (id,name,contextid,info,stamp,parent) VALUES (80,'Thi cuối kỳ',70,'','s',0)")
    # "import XML": mỗi câu (của cả đề online và đề giấy) -> bank entry (idnumber QB-n), question, answers theo position
    pexam = db.query(Exam).filter_by(exam_type="paper").order_by(Exam.id).first()
    qmap, ans_ids = {}, {}
    next_ans = 5000
    allq = {eq.question_id: eq.question for eq in list(exam.questions) + list(pexam.questions)}
    for k, q in enumerate(allq.values()):
        be, mq = 300 + k, 1000 + k
        cur.execute("INSERT INTO mdl_question_bank_entries (id, questioncategoryid, idnumber) VALUES (%s,80,%s)", (be, f"QB-{q.id}"))
        cur.execute("INSERT INTO mdl_question (id,name,questiontext,generalfeedback,qtype,stamp) VALUES (%s,%s,%s,'','multichoice',%s)",
                    (mq, f"QB-{q.id}", q.content, f"st{mq}"))
        cur.execute("INSERT INTO mdl_question_versions (questionbankentryid, version, questionid, status) VALUES (%s,1,%s,'ready')", (be, mq))
        cur.execute("INSERT INTO mdl_qtype_multichoice_options (questionid, single, correctfeedback, partiallycorrectfeedback, incorrectfeedback) "
                    "VALUES (%s,1,'','','')", (mq,))
        ids = []
        for o in sorted(q.options, key=lambda o: o.position):
            cur.execute("INSERT INTO mdl_question_answers (id, question, answer, fraction, feedback) VALUES (%s,%s,%s,%s,'')",
                        (next_ans, mq, o.content, 1 if o.is_correct else 0)); ids.append(next_ans); next_ans += 1
        qmap[q.id] = mq; ans_ids[q.id] = ids
    cur.execute("INSERT INTO mdl_quiz (id, course, name, intro, grade, sumgrades, timelimit, overduehandling) "
                "VALUES (900,50,'Thi cuối kỳ HQTCSDL','',10,10,%s,'autosubmit')", (QUIZ_TIME_LIMIT,))
    meta = {c: (b, corr) for ch, bl, clo, c, opts, corr, b in D.Q}
    trap_content = D.Q[D.TRAP_QUESTION_INDEX][3]
    step = 100000
    t0 = int(datetime(2025, 1, 8, 7, 30).timestamp())
    trng = random.Random(4242)          # thời gian làm bài: bộ sinh riêng, không làm đổi đáp án của dữ liệu minh họa
    for i, (code, name) in enumerate(studs):
        if i in (3, 29):  # 2 SV vắng thi
            continue
        uid, usage = 100 + i, 7000 + i
        attempts = 2 if i % 13 == 0 else 1  # vài SV nộp 2 lần -> lấy lượt cuối
        for att_no in range(1, attempts + 1):
            usage_id = usage * 10 + att_no
            cur.execute("INSERT INTO mdl_question_usages (id, contextid, component, preferredbehaviour) VALUES (%s,70,'mod_quiz','deferredfeedback')", (usage_id,))
            tstart = t0 + att_no * 4000
            cur.execute("""INSERT INTO mdl_quiz_attempts (quiz, userid, attempt, uniqueid, layout, preview, state, timestart, timefinish, sumgrades)
                           VALUES (900,%s,%s,%s,'',0,'finished',%s,%s,0)""", (uid, att_no, usage_id, tstart, tstart))
            qa_id = cur.lastrowid; sumgrades = 0.0
            answer_steps = []                 # (bước chọn đáp án, câu Moodle, số phương án, chỉ số đã chọn) -> gán thời điểm sau vòng lặp
            for slot, eq in enumerate(exam.questions, 1):
                q = eq.question
                b, corr = meta[q.content]
                ids = ans_ids[q.id][:]
                order = ids[:]; rng.shuffle(order)
                pick = _answer(rng, theta[i] - (0.4 if att_no < attempts else 0), b, len(ids), corr, q.content == trap_content)
                cur.execute("""INSERT INTO mdl_question_attempts (questionusageid, slot, behaviour, questionid, maxmark, minfraction, flagged,
                               questionsummary, rightanswer, responsesummary, timemodified) VALUES (%s,%s,'deferredfeedback',%s,0.5,0,0,'','','',0)""",
                            (usage_id, slot, qmap[q.id]))
                qa = cur.lastrowid
                cur.execute("INSERT INTO mdl_question_attempt_steps (id, questionattemptid, sequencenumber, state, timecreated) VALUES (%s,%s,0,'todo',0)", (step, qa))
                cur.execute("INSERT INTO mdl_question_attempt_step_data (attemptstepid, name, value) VALUES (%s,'_order',%s)", (step, ",".join(map(str, order))))
                step += 1
                if pick is not None:
                    cur.execute("INSERT INTO mdl_question_attempt_steps (id, questionattemptid, sequencenumber, state, timecreated) VALUES (%s,%s,1,'complete',0)", (step, qa))
                    cur.execute("INSERT INTO mdl_question_attempt_step_data (attemptstepid, name, value) VALUES (%s,'answer',%s)", (step, str(order.index(ids[pick]))))
                    answer_steps.append((step, qa, len(ids), order.index(ids[pick])))
                    step += 1
                    if pick == corr:
                        sumgrades += 0.5  # Moodle tự chấm: maxmark 0.5 x fraction 1
            # thời điểm chọn đáp án và nộp bài (Quiz 45 phút); vài SV bình thường đổi đáp án một lần trước khi chốt
            offs, finish, kind = timing_plan(trng, i, len(answer_steps), last_attempt=att_no == attempts)
            for (st, qa, nopt, idx), off in zip(answer_steps, offs):
                if kind == "binh_thuong" and trng.random() < 0.12 and off > 20:
                    cur.execute("UPDATE mdl_question_attempt_steps SET sequencenumber=2 WHERE id=%s", (st,))
                    cur.execute("INSERT INTO mdl_question_attempt_steps (id, questionattemptid, sequencenumber, state, timecreated) VALUES (%s,%s,1,'complete',%s)",
                                (step, qa, tstart + off - trng.randint(5, 15)))
                    cur.execute("INSERT INTO mdl_question_attempt_step_data (attemptstepid, name, value) VALUES (%s,'answer',%s)",
                                (step, str((idx + 1) % nopt)))
                    step += 1
                    off += trng.randint(30, 400) if trng.random() < 0.5 else 0      # đổi lại sau khi xem các câu khác
                cur.execute("UPDATE mdl_question_attempt_steps SET timecreated=%s WHERE id=%s", (tstart + min(off, finish), st))
            cur.execute("UPDATE mdl_question_attempt_steps s JOIN mdl_question_attempts q ON q.id=s.questionattemptid SET s.timecreated=%s "
                        "WHERE q.questionusageid=%s AND s.sequencenumber=0", (tstart, usage_id))
            cur.execute("UPDATE mdl_quiz_attempts SET sumgrades=%s, timefinish=%s WHERE id=%s", (sumgrades, tstart + finish, qa_id))
    # một lượt làm thử của GV (phải bị loại)
    cur.execute("INSERT INTO mdl_question_usages (id, contextid, component, preferredbehaviour) VALUES (999999,70,'mod_quiz','deferredfeedback')")
    cur.execute("INSERT INTO mdl_quiz_attempts (quiz, userid, attempt, uniqueid, layout, preview, state, timestart, timefinish) VALUES (900,99,1,999999,'',1,'finished',%s,%s)", (t0, t0 + 60))
    _simulate_offlinequiz(cur, pexam, studs, qmap, ans_ids, meta, step + 1000, t0)
    conn.close()
    exam.moodle_quiz_id = 900; pexam.moodle_offlinequiz_id = 910; db.commit()
    print("Cài cầu nối:", moodle.install_bridge(), "câu lệnh")
    for e in (pexam, exam):
        print(f"Đồng bộ bài #{e.id}:", moodle.sync_exam(db, e.id))
        print("Phân tích:", results.analyze_exam(db, e.id))


def _simulate_offlinequiz(cur, pexam, studs, qmap, ans_ids, meta, step, t0) -> None:
    """Offline Quiz 910: Moodle sinh 2 mã đề (A, B) – mỗi mã đề một thứ tự câu và thứ tự phương án (template usage);
    phiếu quét của mỗi SV được Moodle nhận diện thành bước 'answer' trên bản sao usage của mã đề, rồi chấm (status=complete)."""
    rng = random.Random(11)
    theta = _abilities(len(studs))
    cur.execute("""INSERT INTO mdl_offlinequiz (id, course, name, intro, grade, numgroups, shufflequestions, shuffleanswers, docscreated)
                   VALUES (910, 50, %s, '', 10, 2, 1, 1, 1)""", (pexam.exam_title,))
    layouts = {}
    for g in (1, 2):
        cur.execute("INSERT INTO mdl_offlinequiz_groups (id, offlinequizid, groupnumber, sumgrades, numberofpages, templateusageid) VALUES (%s,910,%s,10,1,0)",
                    (90 + g, g))
        eqs = list(pexam.questions); rng.shuffle(eqs)
        layouts[g] = [(eq, rng.sample(ans_ids[eq.question_id], len(ans_ids[eq.question_id]))) for eq in eqs]
    t1 = int(datetime(2024, 10, 15, 9, 0).timestamp())

    def result(uid, g, picks, status, when):
        nonlocal step
        usage = 60000 + uid * 10 + (1 if status == 'complete' else 2) + (5 if when < t1 else 0)
        cur.execute("INSERT INTO mdl_question_usages (id, contextid, component, preferredbehaviour) VALUES (%s,70,'mod_offlinequiz','immediatefeedback')", (usage,))
        total = 0.0
        for slot, ((eq, order), pick) in enumerate(zip(layouts[g], picks), 1):
            cur.execute("""INSERT INTO mdl_question_attempts (questionusageid, slot, behaviour, questionid, maxmark, minfraction, flagged,
                           questionsummary, rightanswer, responsesummary, timemodified) VALUES (%s,%s,'immediatefeedback',%s,%s,0,0,'','','',0)""",
                        (usage, slot, qmap[eq.question_id], float(eq.points)))
            qa = cur.lastrowid
            cur.execute("INSERT INTO mdl_question_attempt_steps (id, questionattemptid, sequencenumber, state, timecreated) VALUES (%s,%s,0,'todo',0)", (step, qa))
            cur.execute("INSERT INTO mdl_question_attempt_step_data (attemptstepid, name, value) VALUES (%s,'_order',%s)", (step, ",".join(map(str, order))))
            step += 1
            if pick is not None:
                cur.execute("INSERT INTO mdl_question_attempt_steps (id, questionattemptid, sequencenumber, state, timecreated) VALUES (%s,%s,1,'complete',0)", (step, qa))
                cur.execute("INSERT INTO mdl_question_attempt_step_data (attemptstepid, name, value) VALUES (%s,'answer',%s)",
                            (step, str(order.index(ans_ids[eq.question_id][pick]))))
                step += 1
                if pick == meta[eq.question.content][1]:
                    total += float(eq.points)
        cur.execute("""INSERT INTO mdl_offlinequiz_results (offlinequizid, offlinegroupid, userid, sumgrades, usageid, teacherid, attendant,
                       status, timestart, timefinish, timemodified) VALUES (910,%s,%s,%s,%s,99,'scanonly',%s,%s,%s,%s)""",
                    (90 + g, uid, total if status == 'complete' else None, usage, status, when, when, when))

    for k, _ in enumerate(studs):
        if k in (5, 17):  # 2 SV vắng thi
            continue
        g = 1 if k % 2 == 0 else 2
        picks = [_answer(rng, theta[k], meta[eq.question.content][0], len(order), meta[eq.question.content][1], False)
                 for eq, order in layouts[g]]
        if k == 1:  # phiếu quét lần đầu bị tô sai MSSV/nhận diện lại -> Moodle giữ kết quả mới nhất
            result(100 + k, g, [0] * len(picks), 'complete', t1 - 3600)
        result(100 + k, g, picks, 'complete', t1)
        if k == 2:  # một phiếu quét thiếu trang còn ở trạng thái partial -> không được tính
            result(100 + k, g, [None] * len(picks), 'partial', t1 + 60)


def bootstrap() -> None:
    """Dùng khi khởi động container: chờ MySQL, tạo CSDL nếu chưa có, (tùy chọn) nạp dữ liệu minh họa, cài cầu nối Moodle."""
    import os, time
    for _ in range(60):
        try:
            _raw_conn().close(); break
        except pymysql.err.OperationalError:
            print("Chờ MySQL…"); time.sleep(3)
    conn = _raw_conn(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_name='exams'", (settings.app_db_name,))
    fresh = cur.fetchone()[0] == 0; conn.close()
    if fresh:
        init_db()
        if os.getenv("DEMO_DATA", "1") == "1":
            seed_demo()
    if moodle.moodle_available():
        print("Cài cầu nối Moodle:", moodle.install_bridge(), "câu lệnh")
    else:
        print(f"Chưa thấy CSDL Moodle `{settings.moodle_db_name}` – cài cầu nối sau tại trang Kết nối Moodle.")


def _install_bridge() -> None:
    from . import migrate
    migrate.upgrade_schema()   # CSDL từ bản cũ: thêm cột/ràng buộc mới trước khi tạo view
    print(moodle.install_bridge(), "câu lệnh" + ("" if moodle.offlinequiz_available()
          else " (Moodle chưa có Offline Quiz: phần bài thi giấy sẽ được cài khi chạy hệ thống sau bước 3)"))


def main(argv: list[str]) -> None:
    cmds = {"bootstrap": bootstrap, "init-db": init_db, "seed-demo": seed_demo,
            "simulate-moodle": simulate_moodle, "install-bridge": _install_bridge}
    if len(argv) < 2 or argv[1] not in cmds:
        print(__doc__); sys.exit(1)
    cmds[argv[1]]()


if __name__ == "__main__":
    main(sys.argv)
