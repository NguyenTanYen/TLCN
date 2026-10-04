"""Công cụ dòng lệnh: khởi tạo CSDL, tạo dữ liệu minh họa, mô phỏng bài làm.

    python -m app.cli bootstrap        # (container) chờ MySQL, tạo CSDL + dữ liệu minh họa nếu chưa có, cài cầu nối
    python -m app.cli init-db          # tạo 39 bảng + dữ liệu tham chiếu (BM2, phân công PIs)
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
    print(f"Đã tạo CSDL {name} (39 bảng) và nạp dữ liệu tham chiếu.")


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
    print(f"Đã tạo dữ liệu minh họa: lớp HP {cs.section_code}, 40 SV, {len(qids)} câu hỏi, bài KT #{e1.id} (giấy) và #{e2.id} (Moodle).")


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
        ids = []
        for o in sorted(q.options, key=lambda o: o.position):
            cur.execute("INSERT INTO mdl_question_answers (id, question, answer, fraction, feedback) VALUES (%s,%s,%s,%s,'')",
                        (next_ans, mq, o.content, 1 if o.is_correct else 0)); ids.append(next_ans); next_ans += 1
        qmap[q.id] = mq; ans_ids[q.id] = ids
    cur.execute("INSERT INTO mdl_quiz (id, course, name, intro, grade, sumgrades) VALUES (900,50,'Thi cuối kỳ HQTCSDL','',10,10)")
    meta = {c: (b, corr) for ch, bl, clo, c, opts, corr, b in D.Q}
    trap_content = D.Q[D.TRAP_QUESTION_INDEX][3]
    step = 100000
    t0 = int(datetime(2025, 1, 8, 7, 30).timestamp())
    for i, (code, name) in enumerate(studs):
        if i in (3, 29):  # 2 SV vắng thi
            continue
        uid, usage = 100 + i, 7000 + i
        attempts = 2 if i % 13 == 0 else 1  # vài SV nộp 2 lần -> lấy lượt cuối
        for att_no in range(1, attempts + 1):
            usage_id = usage * 10 + att_no
            cur.execute("INSERT INTO mdl_question_usages (id, contextid, component, preferredbehaviour) VALUES (%s,70,'mod_quiz','deferredfeedback')", (usage_id,))
            cur.execute("""INSERT INTO mdl_quiz_attempts (quiz, userid, attempt, uniqueid, layout, preview, state, timestart, timefinish, sumgrades)
                           VALUES (900,%s,%s,%s,'',0,'finished',%s,%s,0)""", (uid, att_no, usage_id, t0 + att_no * 4000, t0 + att_no * 4000 + 3000))
            qa_id = cur.lastrowid; sumgrades = 0.0
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
                    step += 1
                    if pick == corr:
                        sumgrades += 0.5  # Moodle tự chấm: maxmark 0.5 x fraction 1
            cur.execute("UPDATE mdl_quiz_attempts SET sumgrades=%s WHERE id=%s", (sumgrades, qa_id))
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
