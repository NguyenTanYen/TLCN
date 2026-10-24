"""Phân tích THỜI GIAN LÀM BÀI trên Moodle Quiz để cảnh báo giảng viên các lượt làm bài bất thường.

Nguồn dữ liệu: mỗi lần SV lưu đáp án (chuyển trang, Moodle tự lưu định kỳ, nộp bài) question engine ghi một bước có
dữ liệu 'answer' kèm thời điểm. Thủ tục sp_sync_exam lấy về cho từng câu: lần chọn đầu, lần chọn cuối, số lần lưu;
cho từng lượt: bắt đầu, nộp, giới hạn thời gian của Quiz, lần chọn đáp án cuối cùng, có bị Moodle tự nộp khi hết giờ.

Thời gian trả lời một câu (response time) = khoảng cách từ lần chọn đáp án liền trước trong lượt (hoặc lúc bắt đầu) tới
lần đầu chọn đáp án câu đó. Khi Quiz đặt nhiều câu trên một trang, các câu cùng trang được lưu cùng một thời điểm – khi đó
khoảng thời gian của cả trang được chia đều cho các câu (ước lượng theo trang).

Các dấu hiệu (ngưỡng chỉnh được – DEFAULTS):
  LAM_NHANH  Làm bài quá nhanh / nghi chọn đại: thời gian làm trung bình < min_sec_per_q giây/câu (VD 50 câu trong 5 phút
             = 6 giây/câu), HOẶC tỷ lệ câu trả lời "chớp nhoáng" ≥ rapid_share. Câu chớp nhoáng: thời gian trả lời dưới
             max(rapid_sec, 10% trung vị thời gian của câu đó trong lớp) – phương pháp ngưỡng chuẩn NT10 (Wise & Ma, 2012),
             tối đa 10 giây. Kèm tỷ lệ đúng của các câu chớp nhoáng so với xác suất đoán mò (1/số phương án).
  BO_DO      Chọn rồi nghỉ (bỏ dở): ≥ 50% số câu bỏ trống và nộp sớm (không phải hết giờ).
  TREO_MAY   Chọn xong nhưng không nộp, để hết giờ Moodle tự nộp: bài nộp do hết giờ VÀ khoảng thời gian không thao tác
             từ lần chọn đáp án cuối tới lúc nộp ≥ idle_min phút và ≥ idle_share thời gian làm bài.
  NOP_MUON   (lưu ý) Tự bấm nộp nhưng trước đó để lâu không thao tác (cùng ngưỡng idle, không do hết giờ).
  DON_CUOI   (lưu ý) Dồn đáp án vào phút cuối: ≥ 30% số câu được chọn lần đầu trong 60 giây trước khi nộp.
Đây là DẤU HIỆU để GV xem lại (kết hợp quan sát phòng thi, nhật ký Moodle), không phải kết luận gian lận.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

DEFAULTS = {"min_sec_per_q": 6.0, "rapid_sec": 3.0, "rapid_share": 0.25, "idle_min": 10.0, "idle_share": 0.30}

def _n(x, d=1):
    """Số kiểu Việt Nam trong câu chữ: 0,7 – bỏ ,0 thừa khi là số nguyên."""
    if x is None:
        return "—"
    if d == 0 or float(x) == int(x):
        return f"{x:g}".replace(".", ",") if d == 0 else str(int(x))
    return f"{x:.{d}f}".replace(".", ",")

FLAG_INFO = {
    "LAM_NHANH": ("canh_bao", "Làm bài quá nhanh – nghi chọn đại"),
    "BO_DO": ("canh_bao", "Chọn vài câu rồi nghỉ – bỏ dở bài"),
    "TREO_MAY": ("canh_bao", "Chọn xong không nộp – để hết giờ tự nộp"),
    "NOP_MUON": ("luu_y", "Để lâu không thao tác rồi mới nộp"),
    "DON_CUOI": ("luu_y", "Dồn đáp án vào phút cuối"),
}


def _secs(a: datetime | None, b: datetime | None) -> float | None:
    return None if a is None or b is None else (b - a).total_seconds()


def response_times(started: datetime | None, first_times: list[datetime]) -> list[float]:
    """Thời gian trả lời từng câu (giây) từ các thời điểm chọn đáp án lần đầu ĐÃ SẮP TĂNG DẦN của một lượt làm bài.
    Các câu lưu cùng một thời điểm (nhiều câu trên một trang) chia đều khoảng thời gian của trang."""
    out, prev, i = [], started or (first_times[0] if first_times else None), 0
    while i < len(first_times):
        j = i
        while j + 1 < len(first_times) and first_times[j + 1] == first_times[i]:
            j += 1
        gap = max(0.0, _secs(prev, first_times[i]) or 0.0)
        out += [round(gap / (j - i + 1), 1)] * (j - i + 1)
        prev, i = first_times[i], j + 1
    return out


def compute_response_times(db: Session, exam_id: int) -> int:
    """Tính response_time_sec cho mọi câu đã trả lời của bài (gọi sau mỗi lần đồng bộ). Trả về số câu được tính."""
    rows = db.execute(text("""SELECT r.id, r.attempt_id, r.first_answer_at, a.started_at
                              FROM item_level_results r JOIN exam_attempts a ON a.id = r.attempt_id
                              WHERE a.exam_id = :e AND a.status = 'finished' AND r.first_answer_at IS NOT NULL
                              ORDER BY r.attempt_id, r.first_answer_at, r.id"""), {"e": exam_id}).fetchall()
    by_att = defaultdict(list)
    for r in rows:
        by_att[r.attempt_id].append(r)
    updates = []
    for items in by_att.values():
        rts = response_times(items[0].started_at, [it.first_answer_at for it in items])
        updates += [{"id": it.id, "t": t} for it, t in zip(items, rts)]
    if updates:
        db.execute(text("UPDATE item_level_results SET response_time_sec = :t WHERE id = :id"), updates)
    db.commit()
    return len(updates)


def _thresholds(th: dict | None) -> dict:
    out = dict(DEFAULTS)
    for k, v in (th or {}).items():
        if v is not None and k in out:
            out[k] = float(v)
    return out


def report(db: Session, exam_id: int, th: dict | None = None) -> dict:
    """Báo cáo thời gian làm bài và các dấu hiệu bất thường của một bài KT trực tuyến."""
    th = _thresholds(th)
    ex = db.execute(text("SELECT id, exam_type, status, max_score, duration_minutes FROM exams WHERE id = :e"), {"e": exam_id}).one()
    if ex.exam_type != "online":
        return {"available": False, "thresholds": th,
                "reason": "Chỉ bài làm trên Moodle Quiz mới có dữ liệu thời gian trả lời từng câu (bài giấy và bài nhập điểm không có)."}
    qs = db.execute(text("""SELECT eq.question_id, eq.order_index, eq.points, LEFT(q.content, 160) AS content,
                                   (SELECT COUNT(*) FROM question_options o WHERE o.question_id = q.id) AS n_options
                            FROM exam_questions eq JOIN question_bank q ON q.id = eq.question_id
                            WHERE eq.exam_id = :e ORDER BY eq.order_index"""), {"e": exam_id}).mappings().all()
    nq = len(qs)
    qinfo = {q["question_id"]: dict(q) for q in qs}
    raw_max = float(sum(q["points"] for q in qs)) or 1.0
    atts = db.execute(text("""SELECT a.id, a.student_id, s.student_code, s.full_name, a.started_at, a.finished_at, a.time_limit_sec,
                                     a.last_answer_at, a.finished_by_timeout, a.total_score
                              FROM exam_attempts a JOIN students s ON s.id = a.student_id
                              WHERE a.exam_id = :e AND a.status = 'finished' ORDER BY s.student_code"""), {"e": exam_id}).mappings().all()
    items = db.execute(text("""SELECT r.attempt_id, r.question_id, r.response_status, r.is_correct, r.first_answer_at,
                                      r.last_answer_at, r.n_answer_saves, r.response_time_sec
                               FROM item_level_results r JOIN exam_attempts a ON a.id = r.attempt_id
                               WHERE a.exam_id = :e AND a.status = 'finished'"""), {"e": exam_id}).mappings().all()
    has_timing = any(i["first_answer_at"] for i in items)
    if not atts or not has_timing:
        return {"available": False, "thresholds": th,
                "reason": "Chưa có dữ liệu thời gian: hãy đồng bộ bài làm từ Moodle (bản cầu nối có đọc thời điểm trả lời)."}
    by_att = defaultdict(list)
    for it in items:
        by_att[it["attempt_id"]].append(it)
    # trung vị thời gian trả lời từng câu trong lớp -> ngưỡng chớp nhoáng NT10 của từng câu
    rts = defaultdict(list)
    for it in items:
        if it["response_time_sec"] is not None and it["response_status"] == "answered":
            rts[it["question_id"]].append(float(it["response_time_sec"]))
    med_q = {q: statistics.median(v) for q, v in rts.items() if v}
    rapid_thr = {q: min(10.0, max(th["rapid_sec"], 0.1 * med_q.get(q, 0))) for q in qinfo}
    out_atts, flag_count = [], defaultdict(int)
    page_like = 0
    for a in atts:
        its = by_att[a["id"]]
        answered = [i for i in its if i["response_status"] == "answered"]
        n_ans, n_blank = len(answered), sum(1 for i in its if i["response_status"] == "blank")
        duration = _secs(a["started_at"], a["finished_at"]) or 0.0
        active = max(0.0, _secs(a["started_at"], a["last_answer_at"]) or 0.0)
        idle = max(0.0, _secs(a["last_answer_at"], a["finished_at"]) or 0.0) if a["last_answer_at"] else duration
        sec_per_q = active / nq if nq else None
        rapid = [i for i in answered if i["response_time_sec"] is not None and float(i["response_time_sec"]) < rapid_thr[i["question_id"]]]
        rapid_share = len(rapid) / n_ans if n_ans else 0.0
        rapid_acc = sum(1 for i in rapid if i["is_correct"]) / len(rapid) if rapid else None
        chance = statistics.mean(1 / max(2, qinfo[i["question_id"]]["n_options"]) for i in rapid) if rapid else None
        times = [i["first_answer_at"] for i in answered if i["first_answer_at"]]
        if times and len(set(times)) < 0.6 * len(times):
            page_like += 1
        last_min = sum(1 for t in times if a["finished_at"] and 0 <= _secs(t, a["finished_at"]) <= 60)
        changes = sum(max(0, (i["n_answer_saves"] or 1) - 1) for i in answered)
        flags = []
        if n_ans >= 3 and ((sec_per_q is not None and sec_per_q < th["min_sec_per_q"]) or (n_ans >= 5 and rapid_share >= th["rapid_share"])):
            why = []
            if sec_per_q is not None and sec_per_q < th["min_sec_per_q"]:
                why.append(f"chọn {n_ans}/{nq} câu trong {_n(active / 60)} phút (≈ {_n(sec_per_q)} giây/câu < {_n(th['min_sec_per_q'], 0)})")
            if n_ans >= 5 and rapid_share >= th["rapid_share"]:
                why.append(f"{len(rapid)}/{n_ans} câu trả lời chớp nhoáng ({rapid_share:.0%})")
            if rapid_acc is not None and chance is not None:
                why.append(f"đúng {rapid_acc:.0%} số câu chớp nhoáng (đoán mò ≈ {chance:.0%})")
            flags.append({"code": "LAM_NHANH", "detail": "; ".join(why)})
        if nq and n_blank >= 0.5 * nq and not a["finished_by_timeout"]:
            flags.append({"code": "BO_DO", "detail": f"bỏ trống {n_blank}/{nq} câu, nộp sau {_n(duration / 60)} phút"
                                                     + (f" / {a['time_limit_sec'] / 60:.0f} phút cho phép" if a["time_limit_sec"] else "")})
        idle_ok = idle >= th["idle_min"] * 60 and duration > 0 and idle / duration >= th["idle_share"]
        if a["finished_by_timeout"] and idle_ok:
            flags.append({"code": "TREO_MAY", "detail": f"chọn xong lúc phút {_n(active / 60)}, không thao tác {_n(idle / 60)} phút "
                                                        f"({idle / duration:.0%} thời gian) rồi Moodle tự nộp khi hết giờ"})
        elif idle_ok:
            flags.append({"code": "NOP_MUON", "detail": f"không thao tác {_n(idle / 60)} phút trước khi tự nộp"})
        if n_ans >= 5 and duration >= 300 and last_min >= 0.3 * n_ans and not a["finished_by_timeout"] and not any(f["code"] == "LAM_NHANH" for f in flags):
            flags.append({"code": "DON_CUOI", "detail": f"{last_min}/{n_ans} câu được chọn trong 60 giây cuối trước khi nộp"})
        for f in flags:
            f["level"], f["label"] = FLAG_INFO[f["code"]]
            flag_count[f["code"]] += 1
        out_atts.append({"attempt_id": a["id"], "student_id": a["student_id"], "student_code": a["student_code"], "full_name": a["full_name"],
                         "started_at": a["started_at"], "finished_at": a["finished_at"], "time_limit_min": round(a["time_limit_sec"] / 60, 1) if a["time_limit_sec"] else None,
                         "duration_min": round(duration / 60, 1), "active_min": round(active / 60, 1), "idle_min": round(idle / 60, 1),
                         "sec_per_q": round(sec_per_q, 1) if sec_per_q is not None else None,
                         "n_answered": n_ans, "n_blank": n_blank, "n_rapid": len(rapid), "rapid_share": round(rapid_share, 3),
                         "rapid_accuracy": None if rapid_acc is None else round(rapid_acc, 3), "chance": None if chance is None else round(chance, 3),
                         "n_changes": changes, "finished_by_timeout": bool(a["finished_by_timeout"]),
                         "score10": round(float(a["total_score"]) * float(ex.max_score) / raw_max, 2), "flags": flags,
                         "level": "canh_bao" if any(f["level"] == "canh_bao" for f in flags) else ("luu_y" if flags else None)})
    out_atts.sort(key=lambda x: ({"canh_bao": 0, "luu_y": 1, None: 2}[x["level"]], x["student_code"]))
    durs = [x["duration_min"] for x in out_atts]
    per_q = [{"question_id": q["question_id"], "order_index": q["order_index"], "content": q["content"],
              "median_sec": round(med_q[q["question_id"]], 1) if q["question_id"] in med_q else None,
              "rapid_threshold": round(rapid_thr[q["question_id"]], 1),
              "n_rapid": sum(1 for x in by_att.values() for i in x if i["question_id"] == q["question_id"] and i["response_status"] == "answered"
                             and i["response_time_sec"] is not None and float(i["response_time_sec"]) < rapid_thr[q["question_id"]])}
             for q in qs]
    limit = next((x["time_limit_min"] for x in out_atts if x["time_limit_min"]), None)
    return {"available": True, "thresholds": th, "n_questions": nq, "time_limit_min": limit,
            "summary": {"n_attempts": len(out_atts), "median_duration_min": round(statistics.median(durs), 1) if durs else None,
                        "min_duration_min": min(durs) if durs else None, "max_duration_min": max(durs) if durs else None,
                        "n_timeout": sum(1 for x in out_atts if x["finished_by_timeout"]),
                        "n_warning": sum(1 for x in out_atts if x["level"] == "canh_bao"),
                        "n_notice": sum(1 for x in out_atts if x["level"] == "luu_y"),
                        "flags": {k: flag_count.get(k, 0) for k in FLAG_INFO}},
            "page_resolution": page_like > 0.5 * len(out_atts),
            "flag_labels": {k: {"level": v[0], "label": v[1]} for k, v in FLAG_INFO.items()},
            "attempts": out_atts, "questions": per_q}


def student_timeline(db: Session, exam_id: int, student_id: int) -> dict:
    a = db.execute(text("""SELECT a.id, a.started_at, a.finished_at, a.time_limit_sec, a.last_answer_at, a.finished_by_timeout,
                                  s.student_code, s.full_name
                           FROM exam_attempts a JOIN students s ON s.id = a.student_id
                           WHERE a.exam_id = :e AND a.student_id = :s AND a.status = 'finished'"""), {"e": exam_id, "s": student_id}).mappings().first()
    if not a:
        return {}
    rows = db.execute(text("""SELECT eq.order_index, r.question_id, LEFT(q.content, 160) AS content, r.response_status, r.is_correct,
                                     r.first_answer_at, r.last_answer_at, r.n_answer_saves, r.response_time_sec,
                                     o.opt_label AS chosen, (SELECT opt_label FROM question_options c WHERE c.question_id = q.id AND c.is_correct = 1 LIMIT 1) AS answer
                              FROM item_level_results r JOIN exam_questions eq ON eq.exam_id = :e AND eq.question_id = r.question_id
                              JOIN question_bank q ON q.id = r.question_id LEFT JOIN question_options o ON o.id = r.selected_option_id
                              WHERE r.attempt_id = :a ORDER BY eq.order_index"""), {"e": exam_id, "a": a["id"]}).mappings().all()
    st = a["started_at"]
    items = [{**dict(r), "response_time_sec": None if r["response_time_sec"] is None else float(r["response_time_sec"]),
              "first_min": None if not r["first_answer_at"] or not st else round(_secs(st, r["first_answer_at"]) / 60, 2),
              "last_min": None if not r["last_answer_at"] or not st else round(_secs(st, r["last_answer_at"]) / 60, 2)} for r in rows]
    return {"student_code": a["student_code"], "full_name": a["full_name"], "started_at": a["started_at"], "finished_at": a["finished_at"],
            "time_limit_min": round(a["time_limit_sec"] / 60, 1) if a["time_limit_sec"] else None,
            "duration_min": round((_secs(st, a["finished_at"]) or 0) / 60, 2),
            "last_answer_min": round((_secs(st, a["last_answer_at"]) or 0) / 60, 2) if a["last_answer_at"] else None,
            "finished_by_timeout": bool(a["finished_by_timeout"]), "items": items}


def alerts_for_exams(db: Session, exam_ids: list[int]) -> dict[int, dict]:
    """Số lượt có cảnh báo / lưu ý của từng bài trực tuyến (ngưỡng mặc định) – hiển thị ở danh sách bài KT."""
    if not exam_ids:
        return {}
    ids = [r[0] for r in db.execute(text("""SELECT DISTINCT a.exam_id FROM exam_attempts a JOIN item_level_results r ON r.attempt_id = a.id
                                            JOIN exams e ON e.id = a.exam_id
                                            WHERE a.exam_id IN :ids AND e.exam_type = 'online' AND r.first_answer_at IS NOT NULL""")
                                     .bindparams(bindparam("ids", expanding=True)), {"ids": exam_ids})]
    out = {}
    for eid in ids:
        rep = report(db, eid)
        if rep.get("available"):
            out[eid] = {"n_warning": rep["summary"]["n_warning"], "n_notice": rep["summary"]["n_notice"]}
    return out


def report_xlsx(rep: dict, title: str) -> bytes:
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook(); ws = wb.active; ws.title = "Canh_bao"
    ws.append([title]); ws["A1"].font = Font(bold=True, size=12)
    t = rep["thresholds"]
    ws.append([f"Ngưỡng: < {_n(t['min_sec_per_q'], 0)} giây/câu; câu chớp nhoáng < max({_n(t['rapid_sec'], 0)} giây; 10% trung vị của câu), tối đa 10 giây; "
               f"cảnh báo khi ≥ {t['rapid_share']:.0%} số câu; treo máy khi không thao tác ≥ {_n(t['idle_min'], 0)} phút và ≥ {t['idle_share']:.0%} thời gian"])
    ws.append(["Dấu hiệu để giảng viên xem lại, không phải kết luận gian lận."])
    ws.append([])
    head = ["MSSV", "Họ tên", "Mức", "Dấu hiệu", "Chi tiết", "Thời gian làm (phút)", "Đến lần chọn cuối (phút)", "Không thao tác cuối (phút)",
            "Giây/câu", "Đã trả lời", "Bỏ trống", "Câu chớp nhoáng", "Đúng ở câu chớp nhoáng", "Hết giờ tự nộp", "Đổi đáp án", "Điểm (thang 10)"]
    ws.append(head)
    for c in ws[5]:
        c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="DCE6F1"); c.alignment = Alignment(wrap_text=True)
    for x in rep["attempts"]:
        ws.append([x["student_code"], x["full_name"], {"canh_bao": "Cảnh báo", "luu_y": "Lưu ý"}.get(x["level"], ""),
                   "; ".join(f["label"] for f in x["flags"]), " | ".join(f["detail"] for f in x["flags"]), x["duration_min"], x["active_min"],
                   x["idle_min"], x["sec_per_q"], x["n_answered"], x["n_blank"], x["n_rapid"],
                   None if x["rapid_accuracy"] is None else f"{x['rapid_accuracy']:.0%}", "Có" if x["finished_by_timeout"] else "", x["n_changes"], x["score10"]])
        if x["level"] == "canh_bao":
            for c in ws[ws.max_row]:
                c.fill = PatternFill("solid", fgColor="FDE2E1")
    for col, w in zip("ABCDEFGHIJKLMNOP", (11, 24, 10, 34, 70, 12, 12, 12, 9, 9, 9, 10, 12, 10, 9, 10)):
        ws.column_dimensions[col].width = w
    q = wb.create_sheet("Thoi_gian_tung_cau")
    q.append(["Câu", "Nội dung", "Trung vị thời gian trả lời (giây)", "Ngưỡng chớp nhoáng (giây)", "Số SV trả lời chớp nhoáng"])
    for x in rep["questions"]:
        q.append([x["order_index"], x["content"], x["median_sec"], x["rapid_threshold"], x["n_rapid"]])
    q.column_dimensions["B"].width = 80
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()
