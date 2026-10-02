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
    assert sum(h["n"] for h in d["clo_count_hist"]) == k["n_finished"] == len(d["heatmap"])
    assert d["clo_count_hist"][-1]["n"] == k["n_all_clo"]
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
    assert sum(1 for c in ex["clos"] if c["achieved"]) == weak["n_achieved"]
    # SV yếu phải có chương cần học lại, và mọi CLO chưa đạt đều có trong lộ trình
    assert p["review"] and ex["items"]
    assert {c["code"] for c in ex["clos"] if not c["achieved"]} <= {i["clo"] for i in ex["items"]}
    assert p["overall_clos"]


def test_profile_access(client, gv, gv_other):
    cs = _analyzed_section(client, gv)
    sid = client.get(f"/api/class-sections/{cs}/students", headers=gv).json()[0]["id"]
    assert client.get(f"/api/class-sections/{cs}/students/{sid}/profile", headers=gv_other).status_code == 403
    assert client.get(f"/api/class-sections/{cs}/stats", headers=gv_other).status_code == 403
    assert client.get(f"/api/class-sections/{cs}/students/999999/profile", headers=gv).status_code == 404
