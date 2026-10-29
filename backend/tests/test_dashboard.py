"""Trang Tổng quan: việc cần làm theo vai trò."""


def test_giang_vien_thay_viec_can_lam(client, gv):
    d = client.get("/api/dashboard", headers=gv).json()
    assert d["role"] == "lecturer" and d["stats"]["sections"] >= 1
    for t in d["todos"]:
        assert t["to"].startswith("/") and t["title"] and t["where"]
    steps = [t["step"] for t in d["todos"]]
    assert steps == sorted(steps)
    # lớp demo có CLO chưa đạt và chưa có hành động → phải được nhắc
    assert any(t["kind"] == "clo" for t in d["todos"])


def test_giang_vien_khac_khong_thay_viec_cua_nhau(client, gv, gv_other):
    a = {t["where"] for t in client.get("/api/dashboard", headers=gv).json()["todos"]}
    b = {t["where"] for t in client.get("/api/dashboard", headers=gv_other).json()["todos"]}
    assert not (a & b)


def test_bo_mon_thay_danh_sach_kiem_tra(client, admin):
    d = client.get("/api/dashboard", headers=admin).json()
    assert d["role"] == "admin" and len(d["checks"]) == 6
    for c in d["checks"]:
        assert c["done"] == (c["pending"] == 0) and c["to"].startswith("/")


def test_hanh_dong_cai_tien_lam_het_nhac_viec(client, gv):
    cs = next(s for s in client.get("/api/class-sections", headers=gv).json() if s["section_code"] == "DBMS330284_01")
    before = [t for t in client.get("/api/dashboard", headers=gv).json()["todos"] if t["kind"] == "clo" and t["where"] == cs["section_code"]]
    assert before
    clo = next(c for c in client.get(f"/api/class-sections/{cs['id']}/clo-results", headers=gv).json()["clos"] if c["is_achieved"] == 0)
    r = client.post(f"/api/class-sections/{cs['id']}/improvement-actions", headers=gv, json={"description": "Thêm bài tập", "clo_id": clo["clo_id"]})
    after = [t for t in client.get("/api/dashboard", headers=gv).json()["todos"] if t["kind"] == "clo" and t["where"] == cs["section_code"]]
    assert len(after) == len(before) - 1
    client.delete(f"/api/improvement-actions/{r.json()['id']}", headers=gv)
