"""Đọc PDF học liệu thành trang + khối chữ (app.services.rag.ingest). Không cần CSDL:

chạy riêng được bằng  pytest --noconftest tests/test_rag_ingest.py"""

import os



import pymupdf



from app.services.rag import ingest



FONT = os.path.join(os.path.dirname(__file__), "..", "app", "assets", "fonts", "DejaVuSans.ttf")

FOOTER = "Cơ sở dữ liệu – Khoa CNTT"





def _text(page, xy, s, size=14):

    page.insert_text(xy, s, fontsize=size, fontfile=FONT, fontname="dv")





def _sample_pdf() -> bytes:

    doc = pymupdf.open()

    for i in range(1, 6):

        pg = doc.new_page(width=720, height=540)          # khổ slide 4:3

        if i == 4:                                        # trang scan: chỉ có một ảnh phủ kín trang

            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 45)); pix.clear_with(200)

            pg.insert_image(pg.rect, pixmap=pix)

            continue

        _text(pg, (40, 520), FOOTER, 10)

        _text(pg, (680, 520), str(i), 10)

        if i == 1:

            _text(pg, (40, 60), "Chương 3. Ràng buộc toàn vẹn", 24)

            _text(pg, (40, 120), "Khóa chính xác định duy nhất mỗi dòng trong bảng.")

        elif i == 2:

            _text(pg, (40, 60), "Khóa ngoại", 24)

            _text(pg, (40, 200), "Khóa ngoại tham chiếu tới khóa chính của bảng khác.")

        elif i == 3:                                      # slide sơ đồ: 1 tiêu đề + hình vẽ vector

            _text(pg, (40, 60), "Ví dụ", 24)

            for k in range(20):

                pg.draw_rect(pymupdf.Rect(60 + 30 * k, 150, 80 + 30 * k, 170))

        else:

            _text(pg, (40, 60), "So sánh với NULL phải dùng IS NULL, không dùng = NULL.")

    return doc.tobytes()





def test_read_pages_blocks_bbox_and_vietnamese():

    pages = ingest.read_pdf(_sample_pdf())

    assert [p.no for p in pages] == [1, 2, 3, 4, 5]

    p2 = pages[1]

    assert [b.text for b in p2.blocks] == ["Khóa ngoại", "Khóa ngoại tham chiếu tới khóa chính của bảng khác."]

    x0, y0, x1, y1 = p2.blocks[1].bbox

    assert 0 <= x0 < x1 <= p2.width and 150 < y0 < y1 < 220     # khối nằm đúng chỗ đã vẽ (y ~ 200)





def test_drop_footer_and_page_numbers():

    pages = ingest.read_pdf(_sample_pdf())

    alltext = " ".join(p.text for p in pages)

    assert FOOTER not in alltext                      # lặp 4/5 trang -> đầu/chân trang

    assert all(not b.text.isdigit() for p in pages for b in p.blocks)





def test_flags_scanned_and_visual_pages():

    pages = ingest.read_pdf(_sample_pdf())

    assert [p.scanned for p in pages] == [False, False, False, True, False]

    assert [p.visual for p in pages] == [False, False, True, False, False]

    assert pages[3].image_share > 0.95 and pages[2].drawings >= 20





def test_short_document_keeps_repeated_text(tmp_path):

    doc = pymupdf.open()

    for _ in range(2):

        _text(doc.new_page(), (40, 60), "Giới thiệu môn học")

    f = tmp_path / "ngan.pdf"; doc.save(f)

    pages = ingest.read_pdf(str(f))                   # đọc từ đường dẫn tệp

    assert all(p.text == "Giới thiệu môn học" for p in pages)





def test_render_page_png():

    png = ingest.render_page(_sample_pdf(), 2, dpi=50)

    assert png[:8] == b"\x89PNG\r\n\x1a\n"





def test_clean_dirty_pdf_characters():
    assert ingest.clean("khóa\u200bngoại") == "khóa ngoại"     # zero-width space giữa hai âm tiết
    assert ingest.clean("chuẩn\xadhóa") == "chuẩnhóa"         # soft hyphen (điểm ngắt dòng) bị bỏ
    assert ingest.clean("\ufeffBảng\u200d") == "Bảng"                    # BOM, zero-width joiner
    assert ingest.clean("\uf0b7 Khóa chính") == "• Khóa chính"   # bullet Wingdings (Private Use)
    assert ingest.clean("\uf0a7Ràng buộc") == "• Ràng buộc"      # bullet Symbol dính chữ
    assert ingest.clean("khóa\xa0chính") == "khóa chính"            # NBSP
    assert ingest.clean("Kho\u0301a ngoa\u0323i") == "Khóa ngoại"              # dấu tổ hợp (NFD) → NFC
    assert ingest.clean("\x00 Khóa\ufffd chính") == "Khóa chính"      # glyph không có mã Unicode


def test_dirty_characters_inside_pdf_blocks():
    doc = pymupdf.open()
    pg = doc.new_page()
    _text(pg, (40, 60), "\uf0b7 Khóa\u200bngoại tham chiếu\xad tới khóa chính.")
    blocks = ingest.read_pdf(doc.tobytes())[0].blocks
    # font thường không có glyph bullet → PyMuPDF trả mã 0 → bị bỏ; zero-width / soft hyphen được xử lý
    assert [b.text for b in blocks] == ["Khóa ngoại tham chiếu tới khóa chính."]
