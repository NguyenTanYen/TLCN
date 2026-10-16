"""Kiểm thử đồng bộ ngân hàng câu hỏi HAI CHIỀU với Moodle THẬT (cần hệ thống đang chạy, Moodle có plugin local_clo ≥ 1.3).

    python kiem_tra_dong_bo_cau_hoi.py http://localhost:8000 gv.son Gv@123456 <id môn học> <id khóa học Moodle>

1. Tạo câu mới trên hệ thống  -> trạng thái only_system -> đẩy lên (Moodle tạo câu QB-n, phiên bản 1)
2. Sửa câu trên hệ thống       -> system_newer           -> đẩy lên (Moodle tạo phiên bản 2)
3. (tùy chọn) sửa câu trên Moodle bằng trình soạn câu hỏi rồi chạy lại: moodle_newer -> lấy về
4. Câu GV soạn trên Moodle chưa có idnumber -> only_moodle -> lấy về (tạo câu mới + gắn QB-n trên Moodle)
"""
import sys

import httpx

B, USER, PW, COURSE, MC = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
c = httpx.Client(base_url=B, timeout=300)
H = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"username": USER, "password": PW}).json()["access_token"]}


def cmp():
    return c.get(f"/api/courses/{COURSE}/moodle-sync?moodle_course_id={MC}", headers=H).json()


def apply(**kw):
    r = c.post(f"/api/courses/{COURSE}/moodle-sync", headers=H, json={"moodle_course_id": MC, **kw})
    assert r.status_code == 200, r.text
    return r.json()


clo = c.get(f"/api/courses/{COURSE}", headers=H).json()["clos"][0]["id"]
body = {"course_id": COURSE, "outline_id": None, "bloom_level_id": 2, "content": "Kiểm thử đồng bộ: ACID gồm mấy tính chất?",
        "options": [{"content": "3", "is_correct": False}, {"content": "4", "is_correct": True}, {"content": "5", "is_correct": False}],
        "clos": [{"clo_id": clo, "weight": 1}]}
qid = c.post("/api/questions", headers=H, json=body).json()["id"]
row = next(x for x in cmp()["rows"] if x["question_id"] == qid)
assert row["state"] == "only_system", row
print("1.", apply(push=[qid])["pushed"])
body["content"] = "Kiểm thử đồng bộ: ACID gồm bao nhiêu tính chất?"
assert c.put(f"/api/questions/{qid}", headers=H, json=body).status_code == 200
assert next(x for x in cmp()["rows"] if x["question_id"] == qid)["state"] == "system_newer"
print("2.", apply(push=[qid])["pushed"])
r = cmp()
pull = [x["question_id"] for x in r["rows"] if x["state"] == "moodle_newer" and x["action"] == "pull"]
new = [x["moodle_questionid"] for x in r["rows"] if x["state"] == "only_moodle" and x["action"] == "pull"]
if pull or new:
    print("3-4.", apply(pull=pull, import_new=new))
print("Sau đồng bộ:", cmp()["summary"])
