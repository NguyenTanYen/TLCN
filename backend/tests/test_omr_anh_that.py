from pathlib import Path

from app.services import omr
from app.services.paper import SheetOptions

ANH = Path(__file__).parent / "data" / "phieu_that_dien_thoai.jpg"


def test_doc_phieu_in_va_to_tay_chup_bang_dien_thoai():
    pages = omr.load_pages(ANH.read_bytes(), ANH.name)
    o = SheetOptions(n_questions=10, options_per_question=[4] * 10, student_digits=8, version_digits=2, version_codes=["01", "02"])
    r = omr.read_sheet(pages[0], o)
    assert r["student_code"] == "23110369"
    assert r["version_code"] == "01"
    assert r["answers"] == dict(zip(range(1, 11), ["A", "B", "A", "C", "D", "A", "C", "A", "C", "D"]))
    assert not r["issues"]


def test_do_phieu_nhanh_khi_dua_vao_khung_camera():
    import cv2
    import numpy as np
    assert omr.probe(ANH.read_bytes())["found"] is True
    trang = cv2.imencode(".jpg", np.full((600, 800), 235, np.uint8))[1].tobytes()
    assert omr.probe(trang)["found"] is False
    assert omr.probe(b"khong phai anh")["found"] is False
