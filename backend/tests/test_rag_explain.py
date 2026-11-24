import httpx
from sqlalchemy import text

from app.database import SessionLocal
from app.services import lms
from app.services.rag import explain as X
from tests.test_rag_suggest import EXAM, INSTEAD_OF, PITR, material

OPTS = {"A": "DataNode", "B": "NameNode", "C": "TaskTracker", "D": "NodeManager"}
STEM = "Trong HDFS, thành phần nào quản lý siêu dữ liệu?"


def src(n, text=None):
    return X.Source("Bài giảng Hadoop", 17 + n, text or f"NameNode lưu trữ siêu dữ liệu của HDFS. Nội dung trang {n}. " * 8)


def test_context_numbers_sources_and_respects_the_budget():
    ctx, used = X.build_context([src(1), src(2)])
    assert ctx.startswith("[Nguồn 1] (Bài giảng Hadoop, trang 18)\n") and "[Nguồn 2] (Bài giảng Hadoop, trang 19)" in ctx
    assert len(used) == 2
    ctx, used = X.build_context([src(1, "a" * 5000), src(2), src(3)], limit=3000)
    assert [s.page_no for s in used] == [18, 19]
    assert "a" * 2500 in ctx and "a" * 2501 not in ctx
    assert X.build_context([src(1, "   ")]) == ("", [])


def test_prompt_carries_rules_question_correct_answer_and_context():
    p = X.build_prompt(STEM, OPTS, ["B"], "[Nguồn 1] (x, trang 18)\nnội dung")
    assert "CHỈ dùng thông tin trong phần TÀI LIỆU" in p and X.REFUSAL in p
    assert STEM in p and "A. DataNode" in p and "ĐÁP ÁN ĐÚNG: B. NameNode" in p
    assert p.index("TÀI LIỆU:\n[Nguồn 1]") > p.index("ĐÁP ÁN ĐÚNG") and p.endswith("[Nguồn k]):")


def test_check_requires_a_real_citation_and_honours_refusal():
    assert X.check("NameNode giữ metadata [Nguồn 1]. DataNode giữ khối [nguồn 2].", 2) == (
        "NameNode giữ metadata [Nguồn 1]. DataNode giữ khối [Nguồn 2].", [1, 2])
    assert X.check("Đúng vì thế [Nguồn 1] và [Nguồn 7].", 3) == ("Đúng vì thế [Nguồn 1] và .", [1])
    assert X.check("Roll-up đi lên mức tổng hợp (Nguồn 1). Drill-down ngược lại [Nguồn 1, 3].", 3) == (
        "Roll-up đi lên mức tổng hợp [Nguồn 1]. Drill-down ngược lại [Nguồn 1] [Nguồn 3].", [1, 3])
    assert X.check("NameNode giữ metadata.", 2) is None
    assert X.check("Vì vậy [Nguồn 5].", 2) is None
    assert X.check(f"{X.REFUSAL}.", 2) is None and X.check("không đủ căn cứ", 2) is None and X.check("", 2) is None


def test_explain_with_a_fake_llm(monkeypatch):
    seen = []
    monkeypatch.setattr(X.settings, "rag_llm_model", "llm-thu")
    monkeypatch.setattr(X, "generate", lambda prompt: seen.append(prompt) or "NameNode lưu siêu dữ liệu [Nguồn 2].")
    e = X.explain(STEM, OPTS, ["B"], [src(1), src(2)])
    assert (e.text, e.cited, [s.page_no for s in e.sources]) == ("NameNode lưu siêu dữ liệu [Nguồn 2].", [2], [18, 19])
    assert e.model == "llm-thu" and "[Nguồn 2] (Bài giảng Hadoop, trang 19)" in seen[0]
    assert X.explain(STEM, OPTS, ["B"], []) is None and len(seen) == 1
    monkeypatch.setattr(X, "generate", lambda prompt: X.REFUSAL)
    assert X.explain(STEM, OPTS, ["B"], [src(1)]).text == ""
    monkeypatch.setattr(X.settings, "rag_llm_model", "")
    monkeypatch.setattr(X.settings, "rag_vlm_model", "")
    monkeypatch.setattr(X, "generate", lambda prompt: 1 / 0)
    assert X.explain(STEM, OPTS, ["B"], [src(1)]) is None


def test_generate_sends_a_text_only_chat_request(monkeypatch):
    sent = {}

    def post(url, timeout, json):
        sent.update(url=url, json=json)
        return httpx.Response(200, json={"message": {"content": "  Trả lời [Nguồn 1].  "}}, request=httpx.Request("POST", url))
    monkeypatch.setattr(X.httpx, "post", post)
    assert X.generate("PROMPT") == "Trả lời [Nguồn 1]."
    assert sent["url"].endswith("/api/chat") and sent["json"]["model"] == X.model_name()
    assert sent["json"]["messages"] == [{"role": "user", "content": "PROMPT"}] and sent["json"]["options"]["temperature"] == 0


def _url(q):
    return f"/api/exams/{EXAM}/questions/{q}/explanation"


def _preview(client, gv):
    r = client.get(f"/api/exams/{EXAM}/material-suggestions", headers=gv)
    assert r.status_code == 200, r.text
    return {x["question_id"]: x["explanation"] for x in r.json()}


def _sent_to_moodle(qid):
    db = SessionLocal()
    try:
        rows = lms.student_results(db, EXAM)
    finally:
        db.close()
    return [m for r in rows for m in lms.public_data(r["data"]).get("materials", []) if m["question_id"] == qid]


def _sql(sql, **p):
    db = SessionLocal()
    try:
        r = db.execute(text(sql), p)
        db.commit()
        return r
    finally:
        db.close()


def _clear(cs):
    _sql("DELETE FROM material_explanations WHERE class_section_id = :c", c=cs)


def test_explanation_is_generated_once_stored_and_regenerated_when_material_changes(client, gv, gv_other, material,
                                                                                     monkeypatch):
    mid, cs = material
    calls = []
    monkeypatch.setattr(X.settings, "rag_llm_model", "llm-thu")
    monkeypatch.setattr(X, "generate", lambda p: calls.append(p) or "Model FULL cho phép phục hồi về một thời điểm [Nguồn 1].")
    try:
        assert _preview(client, gv)[PITR] == {"status": "missing"} and calls == []
        r = client.post(_url(PITR), headers=gv)
        assert r.status_code == 200, r.text
        e = r.json()
        assert e["status"] == "ready" and e["text"].endswith("[Nguồn 1].") and e["cited"] == [1] and e["model"] == "llm-thu"
        assert {"title": "Slide sao lưu và trigger", "page_no": 1,
                "url": "http://moodle.test/pluginfile.php/1810/mod_resource/content/1/test_suggest.pdf#page=1"} in e["sources"]
        assert client.post(_url(PITR), headers=gv).json() == e and len(calls) == 1
        assert _preview(client, gv)[PITR] == e

        _sql("UPDATE material_passages SET body = CONCAT(body, ' Cần bản sao lưu nhật ký.') WHERE material_id = :m AND seq = 1",
             m=mid)
        assert _preview(client, gv)[PITR] == {"status": "missing"}
        assert client.post(_url(PITR), headers=gv).json()["status"] == "ready" and len(calls) == 2
        assert "Cần bản sao lưu nhật ký" in calls[-1]

        monkeypatch.setattr(X, "generate", lambda p: calls.append(p) or X.REFUSAL)
        r = client.post(_url(INSTEAD_OF), headers=gv).json()
        assert (r["status"], r["text"], r["cited"], r["model"]) == ("refused", None, [], "llm-thu") and r["sources"]
        assert _preview(client, gv)[INSTEAD_OF] == r
        n = len(calls)
        assert client.post(_url(INSTEAD_OF), headers=gv).json()["status"] == "refused" and len(calls) == n

        assert client.post(_url(PITR), headers=gv_other).status_code == 403
        assert client.post(f"/api/exams/{EXAM}/questions/999999/explanation", headers=gv).status_code == 404
    finally:
        _clear(cs)


def test_ollama_down_is_reported_and_not_stored(client, gv, material, monkeypatch):
    _, cs = material
    monkeypatch.setattr(X.settings, "rag_llm_model", "llm-thu")

    def down(prompt):
        raise httpx.ConnectError("Ollama tắt")
    monkeypatch.setattr(X, "generate", down)
    r = client.post(_url(PITR), headers=gv)
    assert r.status_code == 503 and "Ollama" in r.json()["detail"]
    assert _sql("SELECT COUNT(*) FROM material_explanations WHERE class_section_id = :c", c=cs).scalar() == 0
    monkeypatch.setattr(X.settings, "rag_llm_model", "")
    monkeypatch.setattr(X.settings, "rag_vlm_model", "")
    assert client.post(_url(PITR), headers=gv).json() == {"status": "none"}


def test_results_sent_to_moodle_carry_only_stored_explanations(client, gv, material, monkeypatch):
    _, cs = material
    monkeypatch.setattr(X.settings, "rag_llm_model", "llm-thu")
    monkeypatch.setattr(X, "generate", lambda p: "Model FULL cho phép phục hồi về một thời điểm [Nguồn 1].")
    try:
        assert client.post(_url(PITR), headers=gv).json()["status"] == "ready"

        def no_llm(prompt):
            raise AssertionError("gửi kết quả không được gọi LLM")
        monkeypatch.setattr(X, "generate", no_llm)
        pitr = _sent_to_moodle(PITR)
        assert pitr and all(m["explanation"]["text"].endswith("[Nguồn 1].") for m in pitr)
        assert {"material": "Slide sao lưu và trigger", "page": 1,
                "url": "http://moodle.test/pluginfile.php/1810/mod_resource/content/1/test_suggest.pdf#page=1"} in pitr[0]["explanation"]["sources"]
        assert all("explanation" not in m for m in _sent_to_moodle(INSTEAD_OF))
    finally:
        _clear(cs)


def test_lecturer_rejects_a_wrong_explanation_so_students_never_get_it(client, gv, gv_other, material, monkeypatch):
    mid, cs = material
    calls = []
    monkeypatch.setattr(X.settings, "rag_llm_model", "llm-thu")
    monkeypatch.setattr(X, "generate", lambda p: calls.append(p) or "Khóa hai pha ngăn được bế tắc [Nguồn 1].")
    try:
        assert client.patch(_url(PITR), json={"rejected": True}, headers=gv).status_code == 409
        ready = client.post(_url(PITR), headers=gv).json()
        assert ready["status"] == "ready" and all("explanation" in m for m in _sent_to_moodle(PITR))

        assert client.patch(_url(PITR), json={"rejected": True}, headers=gv_other).status_code == 403
        r = client.patch(_url(PITR), json={"rejected": True}, headers=gv)
        assert r.status_code == 200, r.text
        assert r.json() == {**ready, "status": "rejected"}
        assert _preview(client, gv)[PITR]["status"] == "rejected"
        assert client.post(_url(PITR), headers=gv).json()["status"] == "rejected" and len(calls) == 1
        pitr = _sent_to_moodle(PITR)
        assert pitr and all("explanation" not in m and m["pages"] for m in pitr)

        assert client.patch(_url(PITR), json={"rejected": False}, headers=gv).json() == ready
        assert all("explanation" in m for m in _sent_to_moodle(PITR))
        client.patch(_url(PITR), json={"rejected": True}, headers=gv)

        _sql("UPDATE material_passages SET body = CONCAT(body, ' Bế tắc vẫn có thể xảy ra.') WHERE material_id = :m AND seq = 1",
             m=mid)
        assert _preview(client, gv)[PITR] == {"status": "missing"}
        assert client.patch(_url(PITR), json={"rejected": False}, headers=gv).status_code == 409
        assert client.post(_url(PITR), headers=gv).json()["status"] == "ready" and len(calls) == 2
        assert _sql("SELECT rejected_at, rejected_by FROM material_explanations WHERE class_section_id = :c",
                    c=cs).one() == (None, None)
    finally:
        _clear(cs)
