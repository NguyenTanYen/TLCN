"""Kiểm thử đầu-cuối với Moodle THẬT (không dùng CSDL Moodle mô phỏng).

Yêu cầu: Moodle 4.x đã cài (CSDL `moodle`, cùng MySQL server với assessment_db), php-cli.
Chạy từ thư mục backend:  python ../tools/moodle_e2e/run_real_moodle_e2e.py /đường/dẫn/moodle

Các bước: dựng lại CSDL hệ thống + dữ liệu minh họa -> xuất Moodle XML của bài KT online -> PHP dùng API Moodle
nhập XML, tạo Quiz xáo trộn phương án, cho 38 SV làm bài (Moodle tự chấm) -> hệ thống đồng bộ qua sp_sync_exam
-> đối chiếu từng câu trả lời và tổng điểm với kết quả chấm của chính Moodle.
"""
import contextlib, io, json, os, random, shutil, subprocess, sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app import cli, demo_data as D  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.models import Exam  # noqa: E402
from app.services import lms, moodle, results, xml_export  # noqa: E402

MOODLE = Path(sys.argv[1] if len(sys.argv) > 1 else "/var/www/moodle").resolve()
HERE = Path(__file__).resolve().parent
WORK = HERE / "out"; WORK.mkdir(exist_ok=True)


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        cli.init_db(); cli.seed_demo(); cli.simulate_paper()
    db = SessionLocal()
    exam = db.query(Exam).filter_by(exam_type="online").order_by(Exam.id).first()
    (WORK / "exam.xml").write_text(xml_export.exam_to_moodle_xml(exam), encoding="utf-8")
    studs = db.execute(text("""SELECT s.student_code, s.full_name FROM enrollments e JOIN students s ON s.id=e.student_id
                               WHERE e.class_section_id=:cs ORDER BY s.student_code"""), {"cs": exam.class_section_id}).fetchall()
    theta, rng = cli._abilities(len(studs)), random.Random(99)
    meta = {c: (b, corr) for ch, bl, clo, c, opts, corr, b in D.Q}
    trap = D.Q[D.TRAP_QUESTION_INDEX][3]
    spec = {"course": {"shortname": "DBMS330284_01", "fullname": "Hệ quản trị cơ sở dữ liệu – DBMS330284_01"},
            "quiz": {"name": exam.exam_title, "grade": float(exam.max_score)},
            "teacher": {"username": "gv.son", "firstname": "Sơn", "lastname": "Nguyễn Thành", "role": "editingteacher", "password": "Gv@123456"},
            "students": [], "attempts": []}
    for i, (code, name) in enumerate(studs):
        last, first = name.rsplit(" ", 1)
        spec["students"].append({"username": code, "firstname": first, "lastname": last, "password": "Sv@123456"})
        if i in (3, 29):
            continue  # 2 SV vắng thi
        n_att = 2 if i % 13 == 0 else 1
        for k in range(1, n_att + 1):
            ans = {}
            for eq in exam.questions:
                q = eq.question
                b, corr = meta[q.content]
                ans[f"QB-{q.id}"] = cli._answer(rng, theta[i] - (0.4 if k < n_att else 0), b, len(q.options), corr, q.content == trap)
            spec["attempts"].append({"username": code, "answers": ans})
    (WORK / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    php = os.getenv("PHP_BIN") or shutil.which("php8.3") or shutil.which("php") or r"D:\xampp\php\php.exe"
    out = subprocess.run([php,
                          str(HERE / "moodle_build_quiz.php"), f"--moodle={MOODLE}", f"--spec={WORK / 'spec.json'}", f"--xml={WORK / 'exam.xml'}"],
                         capture_output=True, text=True)
    if out.returncode:
        sys.exit("PHP lỗi:\n" + out.stderr[-3000:] + out.stdout[-2000:])
    info = json.loads(out.stdout.strip().splitlines()[-1])
    print("Moodle:", info)

    exam.moodle_quiz_id = info["quiz_id"]; exam.class_section.moodle_course_id = info["course_id"]; db.commit()
    print("Cầu nối:", moodle.install_bridge(), "câu lệnh")
    print("Đồng bộ:", moodle.sync_exam(db, exam.id))
    print("Phân tích:", results.analyze_exam(db, exam.id))
    reports = {}
    for gm, label in ((4, "Lượt cuối"), (3, "Lượt đầu"), (1, "Điểm cao nhất (mặc định)")):
        with engine.begin() as c:  # đổi cách tính điểm của quiz như GV chỉnh trong Moodle
            c.execute(text(f"UPDATE {settings.moodle_db_name}.{settings.moodle_prefix}quiz SET grademethod=:g WHERE id=:q"),
                      {"g": gm, "q": info["quiz_id"]})
        moodle.sync_exam(db, exam.id); results.analyze_exam(db, exam.id)
        print(f"\n== grademethod={gm}: {label}")
        reports[label] = verify(exam.id, info["quiz_id"], spec, gm)
    reports["day_ket_qua_len_moodle"] = push_to_moodle(db, exam)
    (WORK / "verification.json").write_text(json.dumps({"moodle": info, "ket_qua": reports}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nĐẠT: với cả 3 cách tính điểm, dữ liệu đồng bộ khớp hoàn toàn với kết quả chấm của Moodle.")
    if reports.get("day_ket_qua_len_moodle"):
        print("ĐẠT: kết quả phân tích đã được đẩy lên Moodle – SV xem tại khóa học > Kết quả phân tích CĐR.")


def push_to_moodle(db, exam):
    """Công bố kết quả -> đẩy qua Web Service local_clo -> kiểm tra Moodle đã lưu đủ kết quả cho SV xem."""
    if not lms.configured():
        print("\n(Bỏ qua bước đẩy kết quả lên Moodle: chưa cấu hình MOODLE_URL / MOODLE_WS_TOKEN)")
        return None
    exam.publish_flag = True; db.commit()
    res = lms.push_results(db, exam)
    MDL = f"{settings.moodle_db_name}.{settings.moodle_prefix}"
    with engine.connect() as c:
        row = c.execute(text(f"""SELECT e.published, COUNT(r.id), SUM(r.status='absent') FROM {MDL}local_clo_exam e
                                 LEFT JOIN {MDL}local_clo_result r ON r.cloexamid=e.id WHERE e.examref=:x GROUP BY e.id"""),
                        {"x": exam.id}).fetchone()
    report = {"da_gui": res["sent"], "moodle_da_luu": int(row[1]), "sv_vang": int(row[2] or 0), "cong_bo": bool(row[0]),
              "khong_tim_thay": res["notfound"], "thong_bao_da_gui": res["notified"]}
    print("\n== Đẩy kết quả phân tích lên Moodle (Web Service)")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    assert report["moodle_da_luu"] == report["da_gui"] == 40 and report["sv_vang"] == 2 and report["cong_bo"] and not res["notfound"]
    return report


def verify(exam_id, quiz_id, spec, grademethod):
    MDL = f"{settings.moodle_db_name}.{settings.moodle_prefix}"
    with engine.connect() as c:
        q = lambda sql, **p: c.execute(text(sql), p).fetchall()  # noqa: E731
        # (1) tổng điểm = sumgrades Moodle tự chấm, trên lượt nộp cuối, không tính lượt xem trước
        rows = q(f"""SELECT s.student_code, a.total_score, ma.sumgrades, ma.attempt, ma.preview FROM exam_attempts a
                    JOIN students s ON s.id=a.student_id JOIN {MDL}quiz_attempts ma ON ma.id=a.moodle_attempt_id
                    WHERE a.exam_id=:e""", e=exam_id)
        diff = [r for r in rows if round(float(r[1]), 2) != round(float(r[2]), 2)]
        cond = {1: "COALESCE(y.sumgrades,0) > COALESCE(x.sumgrades,0) OR (COALESCE(y.sumgrades,0) = COALESCE(x.sumgrades,0) AND y.attempt < x.attempt)",
                3: "y.attempt < x.attempt", 4: "y.attempt > x.attempt"}[grademethod]
        graded = {r[0] for r in q(f"""SELECT x.id FROM {MDL}quiz_attempts x WHERE x.quiz=:q AND x.preview=0 AND x.state='finished'
                    AND NOT EXISTS (SELECT 1 FROM {MDL}quiz_attempts y WHERE y.quiz=x.quiz AND y.userid=x.userid
                                    AND y.preview=0 AND y.state='finished' AND ({cond}))""", q=quiz_id)}
        synced = {r[0] for r in q("SELECT moodle_attempt_id FROM exam_attempts WHERE exam_id=:e AND status='finished'", e=exam_id)}
        last = len(graded)
        preview = q(f"SELECT COUNT(*) FROM {MDL}quiz_attempts WHERE quiz=:q AND preview=1", q=quiz_id)[0][0]
        # (2) từng câu: đúng/sai của hệ thống = trạng thái chấm của Moodle (gradedright/gradedwrong/gaveup)
        items = q(f"""SELECT s.student_code, r.question_id, r.score_earned,
                            (SELECT st.fraction FROM {MDL}question_attempt_steps st WHERE st.questionattemptid=mqa.id
                              ORDER BY st.sequencenumber DESC LIMIT 1) AS moodle_fraction,
                            mqa.responsesummary, o.content
                     FROM item_level_results r JOIN exam_attempts a ON a.id=r.attempt_id JOIN students s ON s.id=a.student_id
                     JOIN {MDL}quiz_attempts ma ON ma.id=a.moodle_attempt_id
                     JOIN {MDL}question_attempts mqa ON mqa.questionusageid=ma.uniqueid
                     JOIN {MDL}question_versions qv ON qv.questionid=mqa.questionid
                     JOIN {MDL}question_bank_entries qbe ON qbe.id=qv.questionbankentryid AND qbe.idnumber=CONCAT('QB-', r.question_id)
                     LEFT JOIN question_options o ON o.id=r.selected_option_id
                     WHERE a.exam_id=:e""", e=exam_id)
        wrong_grade = [i for i in items if (float(i[2]) > 0) != (float(i[3] or 0) > 0)]
        wrong_choice = [i for i in items if (i[4] or None) != (i[5] or None) and not (i[4] is None and i[5] is None)]
        # (3) lựa chọn của hệ thống = phương án SV đã chọn trong đặc tả kiểm thử
        att_no = {r[0]: (r[1], r[2]) for r in q(f"""SELECT a.moodle_attempt_id, s.student_code, ma.attempt FROM exam_attempts a
                    JOIN students s ON s.id=a.student_id JOIN {MDL}quiz_attempts ma ON ma.id=a.moodle_attempt_id WHERE a.exam_id=:e""", e=exam_id)}
        by_user = {}
        for a in spec["attempts"]:
            by_user.setdefault(a["username"], []).append(a["answers"])
        spec_last = {u: by_user[u][n - 1] for u, n in att_no.values()}  # đáp án đặc tả của đúng lượt được chấm
        pos = {(r[0], r[1]): r[2] for r in q(f"""SELECT s.student_code, r.question_id, o.position - 1 FROM item_level_results r
                  JOIN exam_attempts a ON a.id=r.attempt_id JOIN students s ON s.id=a.student_id
                  LEFT JOIN question_options o ON o.id=r.selected_option_id WHERE a.exam_id=:e AND a.status='finished'""", e=exam_id)}
        spec_bad = [(u, k) for u, ans in spec_last.items() for k, v in ans.items() if pos.get((u, int(k[3:]))) != v]
        absent = q("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e AND status='absent'", e=exam_id)[0][0]
    report = {
        "bai_lam_dong_bo": len(rows), "luot_duoc_tinh_diem_tren_moodle": last, "chon_dung_luot_duoc_tinh_diem": synced == graded,
        "luot_xem_truoc_bi_loai": preview,
        "sv_vang": absent, "lech_tong_diem": len(diff), "so_o_cau_tra_loi": len(items),
        "lech_dung_sai_so_voi_moodle": len(wrong_grade), "lech_noi_dung_phuong_an": len(wrong_choice),
        "lech_so_voi_dac_ta": len(spec_bad),
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))
    assert synced == graded and not diff and not wrong_grade and not wrong_choice and not spec_bad and len(rows) == last == 38 and absent == 2
    return report


if __name__ == "__main__":
    main()
