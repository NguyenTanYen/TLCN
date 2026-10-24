"""Hồ sơ kết quả từng SV và thống kê lớp (giảng viên xem)."""


def _analyzed_section(client, gv):
    for cs in client.get("/api/class-sections", headers=gv).json():
        exams = client.get(f"/api/class-sections/{cs['id']}/exams", headers=gv).json()
        if any(e["status"] == "Analyzed" for e in exams):
            return cs["id"]
    raise AssertionError("không có lớp đã phân tích")


def test_section_stats(client, gv):
    cs = _analyzed_section(client, gv)
    d = client.get(f"/api/class-sections/{cs}/stats", headers=gv).json()
    k = d["kpi"]
    assert d["exam"] and k["n_finished"] + k["n_absent"] == k["n_students"]
    assert k["n_finished"] == len(d["heatmap"]) and "clo_count_hist" not in d
    assert d["chapter_labels"] and all("chapters" in h and "clos" not in h for h in d["heatmap"])    # theo chương, không theo CLO của từng SV
    for c in d["clos"]:
        assert 0 <= c["achieved_pct"] <= 100 and c["n_achieved"] <= c["n"]
    assert all(0 < ch["n_students"] <= k["n_finished"] for ch in d["chapters"])
    assert sum(b["count"] for b in d["score_hist"]) == k["n_finished"]
    assert len(d["at_risk"]) == k["n_at_risk"]
    # chọn bài KT khác trong lớp
    for e in d["exams"]:
        assert client.get(f"/api/class-sections/{cs}/stats?exam_id={e['id']}", headers=gv).json()["exam"]["id"] == e["id"]
    assert client.get(f"/api/class-sections/{cs}/stats?exam_id=999999", headers=gv).status_code == 404


def test_student_profile(client, gv):
    cs = _analyzed_section(client, gv)
    stats = client.get(f"/api/class-sections/{cs}/stats", headers=gv).json()
    weak = stats["at_risk"][0]
    p = client.get(f"/api/class-sections/{cs}/students/{weak['student_id']}/profile", headers=gv).json()
    assert p["student"]["student_code"] == weak["student_code"]
    ex = next(e for e in p["exams"] if e["id"] == stats["exam"]["id"])
    assert ex["score"] == weak["score"] and ex["answers"]
    assert {a["result"] for a in ex["answers"]} <= {"correct", "wrong", "blank"}
    # SV yếu phải có chương cần học lại; hồ sơ SV không có kết quả CLO riêng của SV
    assert p["review"] and ex["items"] and "clos" not in ex and all("clos" not in r for r in p["review"])
    assert "overall_clos" not in p    # không đánh giá từng SV theo CLO


def test_profile_access(client, gv, gv_other):
    cs = _analyzed_section(client, gv)
    sid = client.get(f"/api/class-sections/{cs}/students", headers=gv).json()[0]["id"]
    assert client.get(f"/api/class-sections/{cs}/students/{sid}/profile", headers=gv_other).status_code == 403
    assert client.get(f"/api/class-sections/{cs}/stats", headers=gv_other).status_code == 403
    assert client.get(f"/api/class-sections/{cs}/students/999999/profile", headers=gv).status_code == 404
