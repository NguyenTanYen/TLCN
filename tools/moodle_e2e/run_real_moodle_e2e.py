"""Kiểm thử đầu-cuối với Moodle THẬT (không dùng CSDL Moodle mô phỏng).

Yêu cầu: Moodle 4.x đã cài (CSDL `moodle`, cùng MySQL server với assessment_db), php-cli.
Chạy từ thư mục backend:  python ../tools/moodle_e2e/run_real_moodle_e2e.py /đường/dẫn/moodle

Các bước: dựng lại CSDL hệ thống + dữ liệu minh họa -> xuất Moodle XML của bài KT online -> PHP dùng API Moodle
nhập XML, tạo Quiz xáo trộn phương án, cho 38 SV làm bài (Moodle tự chấm) -> hệ thống đồng bộ qua sp_sync_exam
-> đối chiếu từng câu trả lời và tổng điểm với kết quả chấm của chính Moodle.

Bài thi GIẤY (cần Web Service local_clo + plugin Offline Quiz): hệ thống tạo Offline Quiz 2 mã đề qua API -> tải phiếu trả lời
Moodle sinh ra -> tô phiếu cho 38 SV (fill_answer_sheets.py) và đưa ảnh vào hàng đợi quét -> MOODLE nhận diện & chấm
(local_clo_process_scans) -> hệ thống đồng bộ, đối chiếu với điểm Moodle chấm và với phương án SV đã tô.
"""
import contextlib, io, json, os, random, shutil, subprocess, sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app import cli, demo_data as D  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from app.models import Exam  # noqa: E402
from app.services import lms, moodle, results, xml_export  # noqa: E402

MOODLE = Path(sys.argv[1] if len(sys.argv) > 1 else "/var/www/moodle").resolve()
HERE = Path(__file__).resolve().parent
WORK = HERE / "out"; WORK.mkdir(exist_ok=True)


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        cli.init_db(); cli.seed_demo()
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
        # đổi cách tính điểm của quiz như GV chỉnh trong Moodle (chỉ trong kịch bản minh họa; cần tài khoản quản trị CSDL
        # vì tài khoản của hệ thống chỉ được đọc CSDL Moodle)
        with (create_engine(settings.database_admin_url) if settings.database_admin_url else engine).begin() as c:
            c.execute(text(f"UPDATE {settings.moodle_db_name}.{settings.moodle_prefix}quiz SET grademethod=:g WHERE id=:q"),
                      {"g": gm, "q": info["quiz_id"]})
        moodle.sync_exam(db, exam.id); results.analyze_exam(db, exam.id)
        print(f"\n== grademethod={gm}: {label}")
        reports[label] = verify(exam.id, info["quiz_id"], spec, gm)
    reports["day_ket_qua_len_moodle"] = push_to_moodle(db, exam)
    reports["bai_thi_giay"] = paper_on_moodle(db, info, php)
    (WORK / "verification.json").write_text(json.dumps({"moodle": info, "ket_qua": reports}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nĐẠT: với cả 3 cách tính điểm, dữ liệu đồng bộ khớp hoàn toàn với kết quả chấm của Moodle.")
    if reports.get("day_ket_qua_len_moodle"):
        print("ĐẠT: kết quả phân tích đã được đẩy lên Moodle – SV xem tại khóa học > Kết quả phân tích CĐR.")
    if reports.get("bai_thi_giay"):
        print("ĐẠT: bài thi giấy – Moodle sinh đề/phiếu, nhận diện & chấm 38 phiếu quét; hệ thống kéo về khớp hoàn toàn.")


def paper_on_moodle(db, info, php):
    """Bài thi giấy: Moodle (Offline Quiz) sinh đề + phiếu, nhận diện phiếu quét và chấm; hệ thống chỉ ra đề và kéo kết quả."""
    from fill_answer_sheets import fill_sheet
    if not lms.configured():
        print("\n(Bỏ qua bài thi giấy: chưa cấu hình MOODLE_URL / MOODLE_WS_TOKEN)")
        return None
    if not moodle.offlinequiz_available():
        print("\n(Bỏ qua bài thi giấy: Moodle chưa cài plugin Offline Quiz – chạy 3_CAI_GIAO_DIEN_MOODLE.bat)")
        return None
    exam = db.query(Exam).filter_by(exam_type="paper").order_by(Exam.id).first()
    print(f"\n== Bài thi giấy #{exam.id}: tạo Offline Quiz 2 mã đề trên Moodle (Web Service)")
    oq = lms.create_offlinequiz(exam, info["course_id"], numgroups=2, intro="<p>Thời gian làm bài: 30 phút. Không sử dụng tài liệu.</p>")
    exam.moodle_offlinequiz_id = oq["offlinequizid"]; exam.class_section.moodle_course_id = info["course_id"]
    exam.status = "Published"; db.commit()
    scans = WORK / "phieu_quet"; shutil.rmtree(scans, ignore_errors=True); scans.mkdir()
    forms = {}
    for g in oq["groups"]:
        for f in g["files"]:
            data, _ = lms.download(f["url"])
            (scans.parent / f"{f['kind']}_{g['letter']}.{f['filename'].rsplit('.', 1)[-1]}").write_bytes(data)
            if f["kind"] == "answer":
                forms[g["groupnumber"]] = str(scans.parent / f"answer_{g['letter']}.pdf")
    # Bố cục từng mã đề do Moodle xáo: câu ở mỗi ô + thứ tự phương án in trên phiếu (đọc CSDL Moodle – chỉ đọc)
    MDL = f"{settings.moodle_db_name}.{settings.moodle_prefix}"
    with engine.connect() as c:
        rows = c.execute(text(f"""SELECT g.groupnumber, qa.slot, CAST(SUBSTRING(qbe.idnumber, 4) AS UNSIGNED), d.value
            FROM {MDL}offlinequiz_groups g JOIN {MDL}question_attempts qa ON qa.questionusageid = g.templateusageid
            JOIN {MDL}question_attempt_steps s ON s.questionattemptid = qa.id AND s.sequencenumber = 0
            JOIN {MDL}question_attempt_step_data d ON d.attemptstepid = s.id AND d.name = '_order'
            JOIN {MDL}question_versions qv ON qv.questionid = qa.questionid
            JOIN {MDL}question_bank_entries qbe ON qbe.id = qv.questionbankentryid
            WHERE g.offlinequizid = :oq ORDER BY g.groupnumber, qa.slot"""), {"oq": oq["offlinequizid"]}).fetchall()
        answers = {}
        for g, slot, qid, order in rows:
            ids = [r[0] for r in c.execute(text(f"""SELECT a.id FROM {MDL}question_answers a JOIN {MDL}question_attempts qa
                   ON qa.questionid = a.question JOIN {MDL}offlinequiz_groups gg ON gg.templateusageid = qa.questionusageid
                   WHERE gg.offlinequizid = :oq AND gg.groupnumber = :g AND qa.slot = :s ORDER BY a.id"""),
                   {"oq": oq["offlinequizid"], "g": g, "s": slot})]
            answers.setdefault(g, []).append((qid, ids, [int(x) for x in order.split(",")]))
    studs = db.execute(text("""SELECT s.student_code FROM enrollments e JOIN students s ON s.id=e.student_id
                               WHERE e.class_section_id=:cs ORDER BY s.student_code"""), {"cs": exam.class_section_id}).scalars().all()
    theta, rng = cli._abilities(len(studs)), random.Random(11)
    meta = {c: (b, corr) for ch, bl, clo, c, opts, corr, b in D.Q}
    content = {q.question_id: q.question.content for q in exam.questions}
    spec, files = {}, []
    # Lựa chọn cố định của bộ dữ liệu minh họa (nhãn phương án gốc A, B, …; null = bỏ trống) – giữ cho số liệu
    # giống nhau ở mọi lần chạy, vì Moodle xáo thứ tự câu trong mã đề ngẫu nhiên mỗi khi tạo đề.
    fixed_file = HERE / "lua_chon_bai_giay.json"
    fixed = json.loads(fixed_file.read_text(encoding="utf-8")) if fixed_file.exists() else {}
    for k, code in enumerate(studs):
        if k in (5, 17):  # 2 SV vắng thi
            continue
        g = 1 if k % 2 == 0 else 2
        picks, sheet = {}, []
        for qid, ids, order in answers[g]:
            b, corr = meta[content[qid]]
            if code in fixed and str(qid) in fixed[code]:
                lab = fixed[code][str(qid)]
                p = None if lab is None else ord(lab) - ord("A")
            else:
                p = cli._answer(rng, theta[k], b, len(ids), corr, False)  # phương án gốc SV chọn (None = bỏ trống)
            picks[qid] = p
            sheet.append(None if p is None else order.index(ids[p]))      # ô tương ứng trên phiếu đã xáo của mã đề
        fill_sheet(forms[g], code, sheet, str(scans / f"{code}.png"))
        spec[code] = picks; files.append(str(scans / f"{code}.png"))
    out = subprocess.run([php, str(HERE / "moodle_enqueue_scans.php"), f"--moodle={MOODLE}", f"--oq={oq['offlinequizid']}", *files],
                         capture_output=True, text=True)
    if out.returncode:
        sys.exit("PHP lỗi:\n" + out.stderr[-3000:] + out.stdout[-2000:])
    print("Đã đưa", len(files), "ảnh phiếu vào hàng đợi quét của Moodle:", out.stdout.strip().splitlines()[-1])
    res = lms.process_scans(exam)
    print(f"Moodle nhận diện & chấm: {res['results']} bài, {res['errorpages']} phiếu lỗi, {res['pending']} đang chờ")
    print("Đồng bộ:", moodle.sync_exam(db, exam.id))
    print("Phân tích:", results.analyze_exam(db, exam.id))
    with engine.connect() as c:
        q = lambda sql, **p: c.execute(text(sql), p).fetchall()  # noqa: E731
        rows = q(f"""SELECT s.student_code, a.total_score, r.sumgrades, v.version_code, CHAR(64 + g.groupnumber USING utf8mb4)
                     FROM exam_attempts a JOIN students s ON s.id = a.student_id
                     JOIN {MDL}offlinequiz_results r ON r.id = a.moodle_attempt_id AND r.offlinequizid = :oq
                     JOIN {MDL}offlinequiz_groups g ON g.id = r.offlinegroupid LEFT JOIN exam_versions v ON v.id = a.version_id
                     WHERE a.exam_id = :e""", oq=oq["offlinequizid"], e=exam.id)
        diff = [r for r in rows if round(float(r[1]), 2) != round(float(r[2]), 2) or r[3] != r[4]]
        got = {(r[0], r[1]): r[2] for r in q("""SELECT s.student_code, r.question_id, o.position - 1 FROM item_level_results r
                   JOIN exam_attempts a ON a.id = r.attempt_id JOIN students s ON s.id = a.student_id
                   LEFT JOIN question_options o ON o.id = r.selected_option_id WHERE a.exam_id = :e AND a.status = 'finished'""", e=exam.id)}
        spec_bad = [(u, qid) for u, picks in spec.items() for qid, p in picks.items() if got.get((u, qid)) != p]
        absent = q("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:e AND status='absent'", e=exam.id)[0][0]
    report = {"offlinequiz": oq["offlinequizid"], "ma_de": [g["letter"] for g in oq["groups"]], "phieu_quet": len(files),
              "moodle_da_cham": res["results"], "phieu_loi": res["errorpages"], "bai_dong_bo": len(rows), "sv_vang": absent,
              "lech_diem_hoac_ma_de": len(diff), "lech_phuong_an_so_voi_phieu_to": len(spec_bad)}
    print(json.dumps(report, ensure_ascii=False, indent=1))
    assert res["results"] == len(files) == len(rows) == 38 and absent == 2 and not diff and not spec_bad and not res["errorpages"]
    exam.publish_flag = True; db.commit()
    pushed = lms.push_results(db, exam)
    report["day_ket_qua_len_moodle"] = pushed["saved"]
    return report


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
