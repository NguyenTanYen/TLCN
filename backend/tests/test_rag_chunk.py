"""Gom khối chữ thành đoạn chữ / đoạn hình (app.services.rag.chunk). Không cần CSDL:
chạy riêng được bằng  pytest --noconftest tests/test_rag_chunk.py"""
import os

import pymupdf

from app.services.rag import chunk, ingest

FONT = os.path.join(os.path.dirname(__file__), "..", "app", "assets", "fonts", "DejaVuSans.ttf")


def _t(page, xy, s, size=14):
    page.insert_text(xy, s, fontsize=size, fontfile=FONT, fontname="dv")


def _passages(doc):
    return chunk.build_passages(ingest.read_pdf(doc.tobytes()))


def test_slide_bullets_become_one_passage_with_title():
    doc = pymupdf.open()
    pg = doc.new_page(width=720, height=540)
    _t(pg, (40, 60), "Khóa chính", 28)
    for i, s in enumerate(["Xác định duy nhất mỗi dòng", "Không được trùng", "Không được NULL"]):
        _t(pg, (60, 130 + 40 * i), "• " + s, 18)
    ps = _passages(doc)
    assert len(ps) == 1
    p = ps[0]
    assert (p.kind, p.page, p.title) == ("text", 1, "Khóa chính")
    assert p.body == "• Xác định duy nhất mỗi dòng • Không được trùng • Không được NULL"
    assert p.text.startswith("Khóa chính\n") and len(p.bboxes) == 3
    x0, y0, x1, y1 = p.bbox
    assert y0 < 130 < 210 < y1                       # khung bao cả 3 gạch đầu dòng


def test_heading_mid_page_and_carried_to_next_page():
    doc = pymupdf.open()
    pg = doc.new_page()
    _t(pg, (50, 60), "3.1 Khóa chính", 16)
    _t(pg, (50, 90), "Khóa chính là tập thuộc tính xác định duy nhất một bộ trong quan hệ.", 11)
    _t(pg, (50, 160), "3.2 Khóa ngoại", 16)
    _t(pg, (50, 190), "Khóa ngoại là tập thuộc tính tham chiếu tới khóa chính của quan hệ khác.", 11)
    pg2 = doc.new_page()
    _t(pg2, (50, 60), "Giá trị khóa ngoại phải tồn tại ở quan hệ được tham chiếu hoặc là NULL.", 11)
    ps = _passages(doc)
    assert [(p.page, p.title) for p in ps] == [(1, "3.1 Khóa chính"), (1, "3.2 Khóa ngoại"), (2, "3.2 Khóa ngoại")]
    assert ps[1].body.startswith("Khóa ngoại là")


def test_long_block_split_by_sentence_with_overlap():
    doc = pymupdf.open()
    pg = doc.new_page()
    sents = [f"Câu số {i} giải thích một ý về chuẩn hóa dữ liệu và phụ thuộc hàm trong thiết kế lược đồ." for i in range(20)]
    pg.insert_textbox(pymupdf.Rect(50, 50, 550, 800), " ".join(sents), fontsize=10, fontfile=FONT, fontname="dv")
    ps = _passages(doc)
    assert len(ps) >= 2 and all(len(p.body) <= chunk.MAX for p in ps)
    for a, b in zip(ps, ps[1:]):                     # chồng lấn: câu cuối đoạn trước = câu đầu đoạn sau
        assert chunk.sentences(a.body)[-1] == chunk.sentences(b.body)[0]
    joined = " ".join(p.body for p in ps)
    assert all(s in joined for s in sents)          # không mất câu nào


def test_vector_diagram_becomes_figure_with_labels_and_caption():
    doc = pymupdf.open()
    pg = doc.new_page(width=720, height=540)
    pg.draw_rect(pg.rect, color=None, fill=(0.95, 0.95, 1))   # nền slide phủ cả trang – không được nuốt sơ đồ
    _t(pg, (40, 60), "Ví dụ: sơ đồ ER", 28)
    for x, name in ((100, "SINHVIEN"), (420, "LOP")):
        pg.draw_rect(pymupdf.Rect(x, 150, x + 160, 230))
        _t(pg, (x + 20, 195), name, 14)
    pg.draw_line((260, 190), (420, 190))
    _t(pg, (320, 182), "n – 1", 12)
    _t(pg, (100, 265), "Hình 3.2: Sơ đồ ER quản lý sinh viên", 12)
    _t(pg, (40, 400), "Mỗi sinh viên thuộc đúng một lớp, một lớp có nhiều sinh viên.", 16)
    ps = _passages(doc)
    figs = [p for p in ps if p.kind == "figure"]
    texts = [p for p in ps if p.kind == "text"]
    assert len(figs) == 1
    f = figs[0]
    assert f.title == "Ví dụ: sơ đồ ER" and f.caption == "Hình 3.2: Sơ đồ ER quản lý sinh viên"
    assert "SINHVIEN" in f.body and "LOP" in f.body and f.vlm_desc == ""
    assert [t.body for t in texts] == ["Mỗi sinh viên thuộc đúng một lớp, một lớp có nhiều sinh viên."]
    assert "SINHVIEN" not in texts[0].text           # nhãn sơ đồ không bị lặp ở đoạn chữ


def test_embedded_image_with_caption():
    doc = pymupdf.open()
    pg = doc.new_page()
    _t(pg, (50, 60), "4.1 Cây B-tree", 16)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 30)); pix.clear_with(180)
    pg.insert_image(pymupdf.Rect(100, 100, 400, 300), pixmap=pix, keep_proportion=False)
    _t(pg, (100, 320), "Hình 4.1 – Cây B-tree bậc 3", 10)
    ps = _passages(doc)
    assert [(p.kind, p.title, p.caption) for p in ps] == [("figure", "4.1 Cây B-tree", "Hình 4.1 – Cây B-tree bậc 3")]
    assert ps[0].bboxes[0] == (100.0, 100.0, 400.0, 300.0)


def test_scanned_page_is_one_figure_waiting_for_vlm():
    doc = pymupdf.open()
    pg = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 80)); pix.clear_with(220)
    pg.insert_image(pg.rect, pixmap=pix)
    ps = _passages(doc)
    assert len(ps) == 1 and ps[0].kind == "figure" and ps[0].body == "" and ps[0].vlm_desc == ""
    assert ps[0].bbox == (0.0, 0.0, pg.rect.width, pg.rect.height)


def test_title_only_slide_still_searchable():
    doc = pymupdf.open()
    _t(doc.new_page(width=720, height=540), (200, 270), "Chương 5. Chuẩn hóa", 36)
    pg = doc.new_page(width=720, height=540)
    _t(pg, (40, 60), "Dạng chuẩn 1", 28)
    _t(pg, (60, 130), "Mọi thuộc tính đều nguyên tố.", 18)
    ps = _passages(doc)
    assert (ps[0].page, ps[0].title, ps[0].body) == (1, "Chương 5. Chuẩn hóa", "")
    assert (ps[1].page, ps[1].title) == (2, "Dạng chuẩn 1")


BOLD = os.path.join(os.path.dirname(FONT), "DejaVuSans-Bold.ttf")


def _b(page, xy, s, size=11):
    page.insert_text(xy, s, fontsize=size, fontfile=BOLD, fontname="dvb")


def test_table_becomes_markdown_passage_not_figure():
    doc = pymupdf.open()
    pg = doc.new_page()
    _t(pg, (60, 80), "Bảng 2.1: Thuộc tính của bảng SINHVIEN", 10)
    rows = [["Cột", "Kiểu", "Ràng buộc"], ["MaSV", "CHAR(8)", "PRIMARY KEY"], ["MaLop", "CHAR(6)", "FOREIGN KEY"]]
    for r, row in enumerate(rows):
        for c, s in enumerate(row):
            rc = pymupdf.Rect(60 + 150 * c, 100 + 30 * r, 210 + 150 * c, 130 + 30 * r)
            pg.draw_rect(rc); _t(pg, (rc.x0 + 5, rc.y0 + 20), s, 11)
    _t(pg, (60, 260), "Khóa ngoại MaLop tham chiếu tới bảng LOP để đảm bảo toàn vẹn tham chiếu.", 11)
    ps = _passages(doc)
    assert [p.kind for p in ps] == ["text", "table"]
    t = ps[1]
    assert t.caption == "Bảng 2.1: Thuộc tính của bảng SINHVIEN" and t.vlm_desc == ""
    assert "|MaSV|CHAR(8)|PRIMARY KEY|" in t.body and t.body.startswith("|Cột|Kiểu|Ràng buộc|")
    assert "PRIMARY KEY" not in ps[0].body           # chữ trong bảng không lặp ở đoạn chữ


def test_running_header_kept_as_context_footer_dropped_mid_page_repeat_kept():
    doc = pymupdf.open()
    for i, title in enumerate(["Lược đồ quan hệ", "Thực thể", "Mối kết hợp", "Bản số"], 1):
        pg = doc.new_page(width=720, height=540)
        _t(pg, (500, 25), "Chương 2: Thiết kế CSDL", 10)      # đầu trang lặp ở mọi slide của chương
        _t(pg, (40, 90), title, 28)
        _t(pg, (60, 160), f"Nội dung slide {title.lower()} trình bày khái niệm và ví dụ.", 18)
        _t(pg, (60, 260), "Ví dụ minh họa", 18)              # lặp giữa trang → là nội dung, giữ lại
        _t(pg, (40, 525), f"Khoa CNTT – Cơ sở dữ liệu   {i}", 10)
    ps = _passages(doc)
    assert len(ps) == 4
    assert [p.breadcrumb for p in ps][:2] == ["Chương 2: Thiết kế CSDL > Lược đồ quan hệ", "Chương 2: Thiết kế CSDL > Thực thể"]
    assert all("Chương 2" not in p.body and "Khoa CNTT" not in p.text for p in ps)
    assert all("Ví dụ minh họa" in p.body for p in ps)
    assert ps[0].text.startswith("Chương 2: Thiết kế CSDL > Lược đồ quan hệ\n")   # tìm "thiết kế CSDL" vẫn thấy


def test_bold_headings_levels_and_breadcrumb():
    doc = pymupdf.open()
    pg = doc.new_page()
    _b(pg, (50, 60), "Chương 3. Ràng buộc toàn vẹn", 16)
    _b(pg, (50, 100), "3.1 Khóa chính")                   # in đậm, CÙNG cỡ chữ thân bài
    _b(pg, (50, 130), "3.1.1 Định nghĩa")
    _t(pg, (50, 160), "Khóa chính là tập thuộc tính xác định duy nhất một bộ trong quan hệ.", 11)
    _b(pg, (50, 190), "Lưu ý: khóa chính không được NULL.")   # câu in đậm nhấn mạnh → không phải đề mục
    _b(pg, (50, 230), "3.2 Khóa ngoại")
    _t(pg, (50, 260), "Khóa ngoại là tập thuộc tính tham chiếu tới khóa chính của quan hệ khác.", 11)
    ps = _passages(doc)
    assert [(p.breadcrumb, p.level) for p in ps] == [
        ("Chương 3. Ràng buộc toàn vẹn > 3.1 Khóa chính > 3.1.1 Định nghĩa", 3),
        ("Chương 3. Ràng buộc toàn vẹn > 3.2 Khóa ngoại", 2)]
    assert "Lưu ý: khóa chính không được NULL." in ps[0].body


def test_code_block_never_split_nor_mixed_with_prose():
    doc = pymupdf.open()
    pg = doc.new_page()
    _t(pg, (50, 60), "Ví dụ truy vấn có điều kiện trên nhiều bảng:", 11)
    sql = [f"SELECT sv.MaSV, sv.HoTen, l.TenLop FROM SINHVIEN sv JOIN LOP l ON sv.MaLop = l.MaLop WHERE l.Khoa = 'K{i}';"
           for i in range(10)]
    for i, line in enumerate(sql):
        pg.insert_text((50, 90 + 14 * i), line, fontsize=8, fontname="cour")
    _t(pg, (50, 260), "Kết quả trả về danh sách sinh viên kèm tên lớp tương ứng của từng khoa.", 11)
    ps = _passages(doc)
    code = [p for p in ps if p.code]
    assert len(code) == 1 and len(code[0].body) > chunk.MAX       # dài hơn MAX nhưng không bị cắt
    assert all(line in code[0].body for line in sql)
    assert all("SELECT" not in p.body for p in ps if not p.code)


def test_sentence_split_respects_abbreviations_and_identifiers():
    s = ("Giảng viên ThS. Nguyễn Văn A dạy tại TP. HCM từ năm 2020. Gọi System.out.println() để in: kết quả "
         "hiện ra. VD. bảng SINHVIEN có khóa MaSV!")
    assert chunk.sentences(s) == ["Giảng viên ThS. Nguyễn Văn A dạy tại TP. HCM từ năm 2020.",
                                  "Gọi System.out.println() để in: kết quả hiện ra.",
                                  "VD. bảng SINHVIEN có khóa MaSV!"]


# ---- feedback lần 2: mỗi test tái hiện đúng một lỗi đã xác nhận ----

def test_sql_pasted_in_normal_font_is_code_and_not_split():
    doc = pymupdf.open()
    pg = doc.new_page()
    sql = " ".join(f"SELECT a{i}, b{i} FROM T{i} WHERE c{i} = {i};" for i in range(30))   # Arial-like, không monospace
    pg.insert_textbox(pymupdf.Rect(50, 50, 550, 500), sql, fontsize=10, fontfile=FONT, fontname="dv")
    _t(pg, (50, 600), "Mệnh đề WHERE dùng để lọc các dòng thỏa điều kiện, còn FROM chỉ ra bảng nguồn được JOIN.", 11)
    ps = _passages(doc)
    code = [p for p in ps if p.code]
    assert len(code) == 1 and code[0].body == sql   # nguyên vẹn, không bị cắt dù > MAX
    prose = [p for p in ps if not p.code]
    assert len(prose) == 1 and prose[0].body.startswith("Mệnh đề WHERE")   # câu giảng giải nhắc từ khóa ≠ code


def test_looks_like_code_python_and_prose():
    assert ingest.looks_like_code("def tinh_diem(self, ds): tong = 0 for x in ds: tong += x.diem return tong / len(ds)")
    assert not ingest.looks_like_code("Hàm tinh_diem trả về điểm trung bình của danh sách sinh viên trong lớp.")
    assert not ingest.looks_like_code("Chapter 3 explains how a database stores records and why indexes matter.")


def test_slide_title_same_size_as_chapter_does_not_drop_chapter():
    doc = pymupdf.open()
    slides = [("Chương 2: Thiết kế CSDL", "Mở đầu chương về thiết kế cơ sở dữ liệu."),
              ("Thực thể", "Thực thể là đối tượng cần lưu trữ."),
              ("Ví dụ minh họa", "Ví dụ thực thể SINHVIEN có các thuộc tính MaSV, HoTen."),
              ("Chương 3: Chuẩn hóa", "Mở đầu chương về chuẩn hóa."),
              ("Dạng chuẩn 1", "Mọi thuộc tính đều nguyên tố.")]
    for title, body in slides:                     # mọi tiêu đề CÙNG cỡ 28
        pg = doc.new_page(width=720, height=540)
        _t(pg, (40, 90), title, 28); _t(pg, (60, 160), body, 18)
    assert [p.breadcrumb for p in _passages(doc)] == [
        "Chương 2: Thiết kế CSDL",
        "Chương 2: Thiết kế CSDL > Thực thể",
        "Chương 2: Thiết kế CSDL > Ví dụ minh họa",
        "Chương 3: Chuẩn hóa",
        "Chương 3: Chuẩn hóa > Dạng chuẩn 1"]


def test_unnumbered_heading_under_numbered_section():
    doc = pymupdf.open()
    pg = doc.new_page()
    _b(pg, (50, 60), "3.2 Khóa ngoại")
    _t(pg, (50, 90), "Khóa ngoại là tập thuộc tính tham chiếu tới khóa chính của quan hệ khác.", 11)
    _b(pg, (50, 130), "Ví dụ")
    _t(pg, (50, 160), "Bảng SINHVIEN có MaLop tham chiếu tới bảng LOP.", 11)
    _b(pg, (50, 200), "3.3 Ràng buộc kiểm tra")
    _t(pg, (50, 230), "Ràng buộc CHECK giới hạn miền giá trị của một thuộc tính.", 11)
    assert [p.breadcrumb for p in _passages(doc)] == ["3.2 Khóa ngoại", "3.2 Khóa ngoại > Ví dụ", "3.3 Ràng buộc kiểm tra"]


def test_glued_abbreviations_not_split():
    assert chunk.sentences("Giáo trình của PGS.TS. Nguyễn Văn A biên soạn. Chương 1 giới thiệu.") == [
        "Giáo trình của PGS.TS. Nguyễn Văn A biên soạn.", "Chương 1 giới thiệu."]


def test_hard_split_long_sentence_without_punctuation():
    words = [f"từ{i}" for i in range(220)]           # ~1300 ký tự, không có dấu câu
    parts = chunk._split_long(" ".join(words))
    assert len(parts) >= 2 and all(len(x) <= chunk.MAX for x in parts)
    for a, b in zip(parts, parts[1:]):               # chồng lấn đúng OVERLAP_WORDS từ
        assert a.split()[-chunk.OVERLAP_WORDS:] == b.split()[:chunk.OVERLAP_WORDS]
    assert set(" ".join(parts).split()) == set(words)  # không mất từ nào


# ---- feedback lần 3 ----

def test_single_word_longer_than_max_is_sliced():
    url = "https://example.com/" + "a" * 1500
    parts = chunk._split_long(f"xem {url} để biết thêm")
    assert all(len(x) <= chunk.MAX for x in parts)
    assert "".join(x.replace(" ", "") for x in parts).count("a") >= 1500   # không mất ký tự nào của chuỗi dài


def test_code_detection_needs_strong_keyword_and_ignores_comments():
    en = "Use NOT NULL AND UNIQUE ON the column AS required IN most cases OR SET a default value."
    assert not ingest.looks_like_code(en)            # toàn từ khóa "yếu" → câu tiếng Anh, không phải code
    sql = ("-- Lấy danh sách sinh viên thuộc lớp đang chọn để hiển thị\n"
           "SELECT sv.MaSV, sv.HoTen FROM SINHVIEN sv\n"
           "-- Chỉ lấy những sinh viên còn đang học, bỏ qua đã nghỉ\n"
           "WHERE sv.TrangThai = 1;")
    assert ingest.looks_like_code(sql)               # comment tiếng Việt có dấu không làm mất nhận diện


def test_sql_with_vietnamese_comments_in_pdf_stays_one_code_passage():
    doc = pymupdf.open()
    pg = doc.new_page()
    lines = ["-- Lấy danh sách sinh viên thuộc lớp đang chọn để hiển thị",
             "SELECT sv.MaSV, sv.HoTen, l.TenLop FROM SINHVIEN sv",
             "JOIN LOP l ON sv.MaLop = l.MaLop",
             "-- Chỉ lấy những sinh viên còn đang học, bỏ qua đã nghỉ",
             "WHERE sv.TrangThai = 1 ORDER BY sv.HoTen;"]
    pg.insert_textbox(pymupdf.Rect(50, 50, 550, 200), "\n".join(lines), fontsize=10, fontfile=FONT, fontname="dv")
    ps = _passages(doc)
    assert len(ps) == 1 and ps[0].code and all(" ".join(l.split()) in ps[0].body for l in lines)


def test_long_table_split_by_rows_with_header_repeated():
    doc = pymupdf.open()
    pg = doc.new_page()
    xs = [40, 80, 180, 420, 560]
    rows = [["STT", "MSSV", "Họ tên", "Lớp"]] + [[str(i), f"2211{i:04d}", f"Nguyễn Văn Sinh Viên Số {i}", "DHCNTT22A"]
                                                 for i in range(40)]
    for r, row in enumerate(rows):
        for c, s in enumerate(row):
            rc = pymupdf.Rect(xs[c], 60 + 18 * r, xs[c + 1], 78 + 18 * r)
            pg.draw_rect(rc); _t(pg, (rc.x0 + 3, rc.y0 + 13), s, 9)
    _t(pg, (40, 50), "Bảng 1.1: Danh sách lớp", 9)
    ps = _passages(doc)
    assert len(ps) >= 3 and all(p.kind == "table" for p in ps)
    assert all(len(p.body) <= chunk.MAX and p.body.startswith("|STT|MSSV|Họ tên|Lớp|\n|---|") for p in ps)
    assert all(p.caption == "Bảng 1.1: Danh sách lớp" for p in ps)
    body_rows = [ln for p in ps for ln in p.body.split("\n")[2:]]
    assert len(body_rows) == 40 and body_rows[0].startswith("|0|") and body_rows[-1].startswith("|39|")
    # khung tô của phần thứ 2 chỉ phủ các hàng của nó (nằm dưới phần 1), không phủ cả bảng
    assert ps[1].bboxes[1][1] > ps[0].bboxes[-1][1]


def test_overlong_table_row_keeps_header_in_every_piece():
    head = "|Thuộc tính|Mô tả|\n|---|---|"
    long_row = "|GhiChu|" + " ".join(["ghi chú dài về ràng buộc của thuộc tính"] * 40) + "|"
    md = "\n".join([head, "|MaSV|Mã số sinh viên|", long_row, "|HoTen|Họ và tên|"])
    rows = [(0, 10 * i, 100, 10 * i + 10) for i in range(4)]
    parts = chunk._table_parts(md, rows)
    assert len(parts) >= 3
    assert all(len(x) <= chunk.MAX and x.startswith(head) for x, _ in parts)
    assert all(bbs[0] == rows[0] for _, bbs in parts)   # khung header luôn đi kèm
    assert any("|MaSV|" in x for x, _ in parts) and any("|HoTen|" in x for x, _ in parts)
