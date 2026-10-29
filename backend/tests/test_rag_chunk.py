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
    assert len(code) == 1 and " ".join(code[0].body.split()) == sql   # nguyên vẹn (giữ xuống dòng), không cắt dù > MAX
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


# ---- feedback lần 4 ----

def test_single_overlong_row_split_into_wellformed_rows():
    head = "|Thuộc tính|Mô tả|Kiểu|\n|---|---|---|"
    long_desc = " ".join(["ghi chú dài về ràng buộc"] * 80)
    md = head + f"\n|GhiChu|{long_desc}|TEXT|"         # bảng CHỈ 1 hàng dữ liệu (trước đây không cắt gì)
    parts = chunk._table_parts(md, [(0, 0, 9, 9), (0, 10, 9, 19)])
    assert len(parts) >= 2
    rows = []
    for x, bbs in parts:
        assert len(x) <= chunk.MAX and x.startswith(head) and bbs == [(0, 0, 9, 9), (0, 10, 9, 19)]
        rows += [chunk._cells(row) for row in x.split("\n")[2:]]
    assert all(len(c) == 3 for c in rows)                                     # cấu trúc 3 cột còn nguyên
    assert rows[0][0] == "GhiChu" and rows[0][2] == "TEXT" and not rows[0][1].startswith(chunk.CONT_LEAD)
    for c in rows[1:]:                                   # hàng con sau: đánh dấu là phần tiếp theo của cùng bản ghi
        assert c[0] == "GhiChu" + chunk.CONT_MARK and c[2] == "TEXT" + chunk.CONT_MARK
        assert c[1].startswith(chunk.CONT_LEAD)
    joined = " ".join(c[1].removeprefix(chunk.CONT_LEAD) for c in rows)
    assert set(joined.split()) == set(long_desc.split())


def test_code_heavy_slides_do_not_turn_bullets_into_headings():
    doc = pymupdf.open()
    for i in range(4):
        pg = doc.new_page(width=720, height=540)
        _t(pg, (40, 60), f"Truy vấn {i}", 28)
        for k in range(3):
            _t(pg, (60, 110 + 30 * k), f"Gạch đầu dòng số {k} giải thích ý chính", 18)
        for k in range(8):                                   # nhiều code chữ nhỏ hơn thân bài
            pg.insert_text((60, 220 + 18 * k), f"SELECT a{k}, b{k} FROM T{k} WHERE c{k} = {k};", fontsize=14, fontname="cour")
    ps = _passages(doc)
    assert [p.breadcrumb for p in ps if not p.code] == [f"Truy vấn {i}" for i in range(4)]
    assert all("Gạch đầu dòng số 2" in p.body for p in ps if not p.code)


def test_overlap_when_last_sentence_is_long():
    long_s = "Câu dài " + " ".join(f"từ{i}" for i in range(70)) + "."     # > MAX/3 ký tự
    text = " ".join([long_s, long_s.replace("từ", "chữ"), long_s.replace("từ", "ý")])
    parts = chunk._split_long(text)
    assert len(parts) >= 2 and all(len(x) <= chunk.MAX for x in parts)
    for a, b in zip(parts, parts[1:]):                     # phần sau mở đầu bằng đuôi của phần trước
        head = b.split()[:5]
        assert " ".join(head) in a and 50 <= len(chunk._tail(a, chunk.OVERLAP_CHARS))


def test_roman_and_letter_headings_levels():
    doc = pymupdf.open()
    pg = doc.new_page()
    for y, (s, bold) in enumerate([("Chương 2. Mô hình quan hệ", True), ("I. Khái niệm", True),
                                   ("A. Quan hệ", True), ("Quan hệ là một bảng hai chiều gồm các bộ.", False),
                                   ("B. Thuộc tính", True), ("Thuộc tính là một cột của quan hệ.", False),
                                   ("II. Ràng buộc", True), ("Ràng buộc giới hạn dữ liệu hợp lệ.", False)]):
        (_b if bold else _t)(pg, (50, 60 + 30 * y), s, 11)
    ps = _passages(doc)
    assert [(p.breadcrumb, p.level) for p in ps] == [
        ("Chương 2. Mô hình quan hệ > I. Khái niệm > A. Quan hệ", 3),
        ("Chương 2. Mô hình quan hệ > I. Khái niệm > B. Thuộc tính", 3),
        ("Chương 2. Mô hình quan hệ > II. Ràng buộc", 2)]


def test_letter_c_is_letter_when_document_uses_letters():
    doc = pymupdf.open()
    pg = doc.new_page()
    for y, (s, bold) in enumerate([("A. Khóa chính", True), ("Nội dung về khóa chính của bảng.", False),
                                   ("B. Khóa ngoại", True), ("Nội dung về khóa ngoại của bảng.", False),
                                   ("C. Ràng buộc kiểm tra", True), ("Nội dung về ràng buộc kiểm tra.", False)]):
        (_b if bold else _t)(pg, (50, 60 + 30 * y), s, 11)
    assert [p.breadcrumb for p in _passages(doc)] == ["A. Khóa chính", "B. Khóa ngoại", "C. Ràng buộc kiểm tra"]


def test_colon_and_question_headings_kept():
    doc = pymupdf.open()
    pg = doc.new_page()
    _b(pg, (50, 60), "Ví dụ:")
    _t(pg, (50, 90), "Bảng SINHVIEN có khóa chính MaSV.", 11)
    _b(pg, (50, 130), "Câu hỏi thảo luận?")
    _t(pg, (50, 160), "Vì sao khóa chính không được NULL.", 11)
    assert [p.breadcrumb for p in _passages(doc)] == ["Ví dụ:", "Câu hỏi thảo luận?"]


# ---- feedback bước 3 ----

def test_autofit_slide_titles_stay_siblings():
    doc = pymupdf.open()
    _t(doc.new_page(width=720, height=540), (40, 70), "Chương 3: Ràng buộc", 40)
    for title, size in [("Khóa chính", 40), ("Khóa ngoại và ràng buộc tham chiếu", 36),
                        ("Ràng buộc kiểm tra CHECK trên cột", 32)]:     # PowerPoint tự thu nhỏ tiêu đề dài
        pg = doc.new_page(width=720, height=540)
        _t(pg, (40, 70), title, size)
        for k in range(3):
            _t(pg, (60, 150 + 30 * k), f"Ý chính số {k} của slide này", 20)
        _t(pg, (60, 300), "Ví dụ", 26)                                      # đề mục phụ trong slide
        _t(pg, (60, 340), "Một ví dụ minh họa cho slide.", 20)
    crumbs = [p.breadcrumb for p in _passages(doc)]
    assert crumbs == ["Chương 3: Ràng buộc",
                      "Chương 3: Ràng buộc > Khóa chính", "Chương 3: Ràng buộc > Khóa chính > Ví dụ",
                      "Chương 3: Ràng buộc > Khóa ngoại và ràng buộc tham chiếu",
                      "Chương 3: Ràng buộc > Khóa ngoại và ràng buộc tham chiếu > Ví dụ",
                      "Chương 3: Ràng buộc > Ràng buộc kiểm tra CHECK trên cột",
                      "Chương 3: Ràng buộc > Ràng buộc kiểm tra CHECK trên cột > Ví dụ"]


def test_noisy_heading_sizes_do_not_nest_endlessly():
    doc = pymupdf.open()
    pg = doc.new_page()                                      # trang dọc (giáo trình), không đánh số
    y = 60
    for i, size in enumerate([18, 17.6, 16, 15, 14, 13.4]):  # cỡ lẻ do PDF + nhiều cỡ tiêu đề
        _t(pg, (50, y), f"Đề mục {i}", size)
        _t(pg, (50, y + 25), f"Nội dung của đề mục số {i} trình bày một ý.", 10)
        y += 60
    ps = _passages(doc)
    assert max(p.level for p in ps) <= chunk.SIZE_DEPTH
    assert ps[1].breadcrumb == "Đề mục 1"                   # 18 và 17,6 làm tròn cùng 18 → ngang hàng


def test_table_cell_with_backslash_and_pipes():
    doc = pymupdf.open()
    pg = doc.new_page()
    rows = [["Biểu thức", "Ý nghĩa"], ["a || b", "hoặc logic"], ["C:" + chr(92), "thư mục gốc"]]
    for r, row in enumerate(rows):
        for c, s in enumerate(row):
            rc = pymupdf.Rect(60 + 200 * c, 100 + 30 * r, 260 + 200 * c, 130 + 30 * r)
            pg.draw_rect(rc)
            _t(pg, (rc.x0 + 5, rc.y0 + 20), s, 12)
    md = ingest.read_pdf(doc.tobytes())[0].tables[0].markdown
    assert [chunk._cells(line) for line in md.split("\n")] == [rows[0], ["---", "---"], rows[1], rows[2]]


def test_split_row_keeps_escaped_pipes_intact():
    long_cell = " ".join(["a || b && c"] * 120)
    line = chunk._row(["OR", long_cell, "C:" + chr(92)])
    out = chunk._split_row(line, 300)
    assert len(out) >= 2
    for i, row in enumerate(out):
        cells = chunk._cells(row)
        mark = chunk.CONT_MARK if i else ""
        assert len(row) <= 300 and len(cells) == 3 and cells[0] == "OR" + mark and cells[2] == "C:" + chr(92) + mark
    assert " ".join(chunk._cells(r)[1] for r in out).count("||") >= 120


def test_hard_split_fuzz_bounds_and_coverage():
    import random
    rnd = random.Random(1)
    for _ in range(2000):
        lim = rnd.randint(5, 900)
        words = ["".join(rnd.choice("abc") for _ in range(rnd.choice([1, 3, 8, 40, 1200])))
                 for _ in range(rnd.randint(1, 300))]
        parts = chunk._hard_split(" ".join(words), lim)
        assert all(len(p) <= lim for p in parts)
        got = {w for p in parts for w in p.split()}
        assert {w[i:i + lim] for w in words for i in range(0, len(w), lim)} <= got


# ---- feedback: code giữ xuống dòng + thụt lề; từ viết tắt không phân biệt hoa thường ----

PY_CODE = ["def tinh_diem(ds):",
           "    tong = 0",
           "    for x in ds:",
           "        tong += x.diem",
           "    return tong / len(ds)"]


def test_python_code_keeps_newlines_and_indentation_from_x_offset():
    doc = pymupdf.open()
    pg = doc.new_page()
    for i, line in enumerate(PY_CODE):          # PDF không lưu khoảng trắng đầu dòng: dòng được đặt lùi bằng tọa độ x
        indent = len(line) - len(line.lstrip())
        pg.insert_text((50 + indent * 6.0, 60 + 14 * i), line.lstrip(), fontsize=10, fontname="cour")  # Courier 10: 6 pt/ký tự
    ps = _passages(doc)
    assert len(ps) == 1 and ps[0].code
    assert ps[0].body == "\n".join(PY_CODE)


def test_python_code_with_literal_leading_spaces():
    doc = pymupdf.open()
    pg = doc.new_page()
    for i, line in enumerate(PY_CODE):          # PDF có lưu khoảng trắng đầu dòng
        pg.insert_text((50, 60 + 14 * i), line, fontsize=10, fontname="cour")
    assert _passages(doc)[0].body == "\n".join(PY_CODE)


def test_prose_line_breaks_still_joined():
    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_textbox(pymupdf.Rect(50, 50, 250, 200), "Khóa ngoại là tập thuộc tính tham chiếu tới khóa chính của bảng khác.",
                      fontsize=11, fontfile=FONT, fontname="dv")
    ps = _passages(doc)
    assert ps[0].body == "Khóa ngoại là tập thuộc tính tham chiếu tới khóa chính của bảng khác."   # xuống dòng do khổ giấy bị nối


def test_abbreviations_case_insensitive():
    for s in ["Do Ths. Nguyễn dạy. Câu sau.", "Do Ts. Lê dạy. Câu sau.", "Do pgs. Trần dạy. Câu sau."]:
        assert len(chunk.sentences(s)) == 2, s
    assert chunk.sentences("Xem cột a. Câu sau.") == ["Xem cột a.", "Câu sau."]   # chữ cái thường đơn vẫn hết câu
    assert chunk.sentences("Pi xấp xỉ 3.14. Tải http://a.com/b.pdf. Hết.") == ["Pi xấp xỉ 3.14.", "Tải http://a.com/b.pdf.", "Hết."]


# ---- review bước 3: câu vắt trang ----

def _textbook(first_page_end: str, second_page_start: str, landscape=False):
    doc = pymupdf.open()
    w, h = (842, 595) if landscape else (595, 842)
    p1 = doc.new_page(width=w, height=h)
    _t(p1, (50, 60), "3.2 Chuẩn hóa", 16)
    _t(p1, (50, h - 60), first_page_end, 11)
    p2 = doc.new_page(width=w, height=h)
    _t(p2, (50, 60), second_page_start, 11)
    _t(p2, (50, 90), "Dạng chuẩn 1 yêu cầu mọi thuộc tính nguyên tố.", 11)
    return _passages(doc)


def test_sentence_split_across_pages_is_completed():
    ps = _textbook("Quá trình chuẩn hóa CSDL nhằm mục đích", "loại bỏ dư thừa dữ liệu và đảm bảo toàn vẹn.")
    assert (ps[0].page, ps[0].body) == (1, "Quá trình chuẩn hóa CSDL nhằm mục đích loại bỏ dư thừa dữ liệu và đảm bảo toàn vẹn.")
    assert all(b[3] <= 842 for b in ps[0].bboxes) and len(ps[0].bboxes) == 1   # khung tô vẫn chỉ trên trang 1
    assert ps[1].page == 2 and ps[1].body.startswith("loại bỏ dư thừa")       # trang 2 giữ nguyên


def test_no_continuation_when_page_ends_with_full_sentence_or_next_starts_capital():
    ps = _textbook("Quá trình chuẩn hóa CSDL rất quan trọng.", "loại bỏ dư thừa dữ liệu.")
    assert ps[0].body == "Quá trình chuẩn hóa CSDL rất quan trọng."
    ps = _textbook("Danh sách các dạng chuẩn", "Dạng chuẩn Boyce-Codd được trình bày sau.")
    assert ps[0].body == "Danh sách các dạng chuẩn"


def test_no_continuation_on_slides():
    ps = _textbook("Quá trình chuẩn hóa CSDL nhằm mục đích", "loại bỏ dư thừa dữ liệu.", landscape=True)
    assert ps[0].body == "Quá trình chuẩn hóa CSDL nhằm mục đích"


def test_continuation_starting_with_proper_noun_after_connector():
    ps = _textbook("Hệ quản trị CSDL phổ biến hiện nay là", "Oracle Database và PostgreSQL.")
    assert ps[0].body == "Hệ quản trị CSDL phổ biến hiện nay là Oracle Database và PostgreSQL."
    ps = _textbook("Các hệ quản trị như MySQL,", "SQL Server cũng hỗ trợ giao tác.")
    assert ps[0].body.endswith("MySQL, SQL Server cũng hỗ trợ giao tác.")


def test_bullet_without_period_does_not_swallow_next_page():
    ps = _textbook("• Khóa ngoại", "Dạng chuẩn 1 yêu cầu mọi thuộc tính nguyên tố.")
    assert ps[0].body == "• Khóa ngoại"


def test_more_connectors_and_known_limit():
    ps = _textbook("Chương trình thực thi trên", "Linux kernel phiên bản 6.0.")
    assert ps[0].body.endswith("thực thi trên Linux kernel phiên bản 6.0.")
    ps = _textbook("Hệ điều hành sử dụng", "Windows Server để chạy SQL Server.")
    assert ps[0].body.endswith("sử dụng Windows Server để chạy SQL Server.")
    ps = _textbook("• Giao diện người dùng", "Phần này trình bày kiến trúc.")      # "người dùng" là danh từ → không nối
    assert ps[0].body == "• Giao diện người dùng"
    # giới hạn đã biết: dừng ở danh từ thường + trang sau mở đầu chữ hoa → không nhận ra (luật không phủ được)
    ps = _textbook("Mô hình ER biểu diễn thực thể", "Student và Course trong hệ thống.")
    assert ps[0].body == "Mô hình ER biểu diễn thực thể"


# ---- lỗi tìm thấy khi chạy thử 8 PDF thật (slide BDES233877, giáo trình, bài báo, CTĐT) ----

def test_missing_space_rebuilt_from_character_gaps():
    doc = pymupdf.open()
    pg = doc.new_page(width=720, height=540)
    _t(pg, (40, 60), "Mục tiêu", 28)
    w = pymupdf.Font(fontfile=FONT).text_length("• Tìm hiểu về", fontsize=20)
    _t(pg, (60, 150), "• Tìm hiểu về", 20)
    _t(pg, (60 + w + 4.6, 150), "Apache Hadoop", 20)      # PowerPoint: không có ký tự dấu cách, chỉ có khoảng trống
    assert "về Apache Hadoop" in _passages(doc)[0].body


def test_rotated_margin_stamp_ignored():
    doc = pymupdf.open()
    pg = doc.new_page()
    _t(pg, (50, 80), "1 INTRODUCTION", 16)
    _t(pg, (50, 110), "Documents are visually rich structures that convey information.", 10)
    pg.insert_text((20, 700), "arXiv:2407.01449v6 [cs.IR] 28 Feb 2025", fontsize=16, fontfile=FONT, fontname="dv",
                   rotate=90)                              # dấu arXiv dọc lề trái
    ps = _passages(doc)
    assert all("arXiv" not in p.text for p in ps) and ps[0].breadcrumb == "1 INTRODUCTION"


def test_book_page_heads_varying_by_chapter_and_parity_removed():
    doc = pymupdf.open()
    for i in range(8):
        pg = doc.new_page()
        n = i + 51                                         # số trang in lệch số thứ tự tệp 50
        chap = "3 NoSQL Database" if i < 4 else "4 Hadoop Tools"
        head = f"{chap} {n}" if i % 2 == 0 else f"{n} Big Data Concepts"   # trang chẵn / lẻ khác nhau
        _t(pg, (50, 40), head, 9)
        _t(pg, (50, 120), f"Nội dung trang {n} trình bày một khái niệm của dữ liệu lớn.", 11)
    _t(doc[0], (50, 820), "Contents x", 9)
    ps = _passages(doc)
    assert all("NoSQL Database" not in p.text and "Big Data Concepts" not in p.text and "Contents" not in p.text
               for p in ps)


def test_date_only_running_header_not_in_breadcrumb():
    doc = pymupdf.open()
    for i in range(4):
        pg = doc.new_page(width=720, height=540)
        _t(pg, (600, 25), "8 / 24 / 2026", 10)
        _t(pg, (40, 90), f"Kho dữ liệu {i}", 28)
        _t(pg, (60, 160), "Kho dữ liệu tích hợp dữ liệu từ nhiều nguồn.", 18)
    assert [p.breadcrumb for p in _passages(doc)] == [f"Kho dữ liệu {i}" for i in range(4)]


def test_slide_title_on_template_banner_and_logo_are_not_figures():
    doc = pymupdf.open()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20))
    pix.clear_with(120)
    titles = ["MỤC TIÊU", "GIỚI THIỆU", "KIẾN TRÚC HADOOP", "HDFS"]
    for title in titles:
        pg = doc.new_page(width=720, height=540)
        pg.draw_rect(pymupdf.Rect(0, 20, 720, 85), color=None, fill=(0.1, 0.3, 0.6))   # banner của mẫu slide
        _t(pg, (40, 65), title, 28)                                                    # tiêu đề nằm TRÊN banner
        pg.insert_image(pymupdf.Rect(640, 470, 700, 520), pixmap=pix)                  # logo trường ở mọi slide
        _t(pg, (60, 160), f"Nội dung chính của phần {title.lower()} được trình bày ở đây.", 18)
    ps = _passages(doc)
    assert [p.kind for p in ps] == ["text"] * 4
    assert [p.breadcrumb for p in ps] == titles


def test_text_box_with_fill_is_not_a_figure():
    doc = pymupdf.open()
    pg = doc.new_page(width=720, height=540)
    pg.draw_rect(pymupdf.Rect(36, 50, 330, 100), color=None, fill=(0.9, 0.9, 0.2))     # hộp chữ có nền
    _t(pg, (40, 90), "Kiến trúc Hadoop", 34)
    _t(pg, (60, 160), "Hadoop gồm HDFS và MapReduce.", 18)
    ps = _passages(doc)
    assert [p.kind for p in ps] == ["text"] and ps[0].breadcrumb == "Kiến trúc Hadoop"


def test_target_cut_only_at_sentence_end():
    doc = pymupdf.open()
    pg = doc.new_page()
    a = "Hadoop bao gồm hai thành phần chính là hệ thống tệp phân tán HDFS và công cụ xử lý MapReduce " * 3
    b = "kết nối với nhau để đảm bảo khả năng chịu lỗi và khả năng mở rộng của cụm máy."
    c = "• MapReduce xử lý dữ liệu song song trên toàn bộ cụm máy tính của hệ thống."
    for y, s in ((60, a.strip()), (160, b), (260, c)):     # PowerPoint tách MỘT câu thành hai khối
        pg.insert_textbox(pymupdf.Rect(50, y, 550, y + 90), s, fontsize=11, fontfile=FONT, fontname="dv")
    ps = _passages(doc)
    assert all(p.body.rstrip().endswith(".") for p in ps)  # không đoạn nào bị cắt giữa câu
    assert b in ps[0].body


def test_agenda_block_is_not_heading():
    doc = pymupdf.open()
    pg = doc.new_page(width=720, height=540)
    _t(pg, (40, 60), "NỘI DUNG", 28)
    _t(pg, (60, 140), "1. Giới thiệu 2. Kiến trúc 3. Hệ sinh thái", 24)
    assert [p.breadcrumb for p in _passages(doc)] == ["NỘI DUNG"]


def test_appendix_is_chapter_level_and_drops_list_item():
    doc = pymupdf.open()
    pg = doc.new_page()
    _b(pg, (50, 60), "69. Nâng cao năng lực số")
    _t(pg, (50, 90), "Học phần trang bị kỹ năng số cho sinh viên.", 11)
    _b(pg, (50, 140), "PHỤ LỤC II", 14)
    _t(pg, (50, 170), "Ma trận các học phần đáp ứng chuẩn đầu ra của chương trình.", 11)
    assert [p.breadcrumb for p in _passages(doc)] == ["69. Nâng cao năng lực số", "PHỤ LỤC II"]


def test_section_of_new_chapter_drops_old_chapter():
    doc = pymupdf.open()
    pg = doc.new_page()
    _b(pg, (50, 60), "Chapter 1 Refresher", 16)
    _t(pg, (50, 90), "This chapter reviews big data basics.", 11)
    _b(pg, (50, 140), "2.1 Cluster Computing")                      # trang mở đầu Chương 2 không nhận được
    _t(pg, (50, 170), "A cluster is a group of computers working together.", 11)
    assert [p.breadcrumb for p in _passages(doc)] == ["Chapter 1 Refresher", "2.1 Cluster Computing"]


def test_large_bullet_line_is_not_heading():
    doc = pymupdf.open()
    pg = doc.new_page(width=720, height=540)
    _t(pg, (40, 60), "Volume (Scale)", 32)
    _t(pg, (60, 130), "– 44x increase from 2009 to 2020", 24)      # gạch đầu dòng cỡ chữ lớn hơn thân bài
    _t(pg, (60, 180), "Data volume is increasing exponentially across every industry.", 18)
    _t(pg, (60, 220), "Most of the data is generated by machines and sensors.", 18)
    assert [p.breadcrumb for p in _passages(doc)] == ["Volume (Scale)"]


# ---- review đợt PDF thật: các heuristic không được bỏ nhầm nội dung thật ----

def test_repeated_diagram_in_middle_of_slides_is_kept():
    doc = pymupdf.open()
    for i in range(8):                                     # sơ đồ HDFS giữa slide, giảng từng bước qua 6/8 slide
        pg = doc.new_page(width=720, height=540)
        _t(pg, (40, 60), f"Kiến trúc HDFS - bước {i}", 28)
        if i < 6:
            for x in (150, 330, 510):
                pg.draw_rect(pymupdf.Rect(x, 200, x + 120, 300))
            pg.draw_line((270, 250), (330, 250))
            pg.draw_line((450, 250), (510, 250))
        _t(pg, (60, 450), f"Bước {i}: NameNode điều phối các DataNode.", 18)
    pages = ingest.read_pdf(doc.tobytes())
    assert [len(p.figures) for p in pages] == [1] * 6 + [0] * 2


def test_footnotes_numbered_in_step_with_pages_are_kept():
    doc = pymupdf.open()
    topics = ["HDFS", "YARN", "MapReduce", "Hive", "Pig"]
    for i, topic in enumerate(topics):
        pg = doc.new_page()
        _t(pg, (50, 100), f"Nội dung trang {i + 1} có một chú thích cuối trang.", 11)
        _t(pg, (50, 800), f"{i + 1} Xem thêm tài liệu về {topic}.", 8)   # số chú thích tăng cùng nhịp số trang
    kept = [b.text for p in ingest.read_pdf(doc.tobytes()) for b in p.blocks if "Xem thêm" in b.text]
    assert len(kept) == 5


def test_letter_spaced_title_not_broken_into_letters():
    doc = pymupdf.open()
    pg = doc.new_page()
    font = pymupdf.Font(fontfile=FONT)
    x = 50.0
    for ch in "HADOOP CLUSTER":                          # chữ giãn 0,2 em, không có ký tự dấu cách
        if ch != " ":
            _t(pg, (x, 100), ch, 20)
        x += font.text_length(ch, fontsize=20) + 0.2 * 20
    assert [b.text for b in ingest.read_pdf(doc.tobytes())[0].blocks] == ["HADOOP CLUSTER"]


def test_numbered_bold_heading_with_trailing_period():
    doc = pymupdf.open()
    pg = doc.new_page()
    _b(pg, (50, 60), "1. Kiến trúc Hadoop.")
    _t(pg, (50, 90), "Hadoop gồm HDFS và MapReduce chạy trên cụm máy.", 11)
    _b(pg, (50, 130), "Lưu ý: khóa chính không được NULL.")      # câu nhấn mạnh in đậm vẫn KHÔNG là đề mục
    _b(pg, (50, 170), "2. Hệ sinh thái")
    _t(pg, (50, 200), "Hệ sinh thái gồm Hive, Pig, HBase.", 11)
    ps = _passages(doc)
    assert [p.breadcrumb for p in ps] == ["1. Kiến trúc Hadoop.", "2. Hệ sinh thái"]
    assert "Lưu ý: khóa chính không được NULL." in ps[0].body


# ---- review: cỡ chữ thân bài theo từng slide, code font thường, chữ có dấu trong ô bảng ----

TITLES = ["Kiến trúc Hadoop", "Thành phần Hadoop", "Lưu trữ Hadoop", "Xử lý Hadoop", "Mở rộng Hadoop"]


def test_big_note_on_picture_slide_is_not_heading():
    doc = pymupdf.open()
    for i in range(10):                                    # 8 slide chữ dày cỡ 16 + 2 slide toàn hình, ghi chú cỡ 28
        pg = doc.new_page(width=720, height=540)
        _t(pg, (40, 60), TITLES[i % 5], 32)
        if i < 8:
            for k in range(4):
                _t(pg, (60, 140 + 30 * k), f"Gạch đầu dòng {k} của slide {i} giải thích một ý về Hadoop.", 16)
        else:
            _t(pg, (60, 300), f"Ghi chú lớn cho sơ đồ của slide {i}", 28)
    ps = [p for p in _passages(doc) if p.page in (9, 10)]
    assert [p.breadcrumb for p in ps] == [TITLES[3], TITLES[4]]
    assert ps[0].body == "Ghi chú lớn cho sơ đồ của slide 8"


def test_sub_heading_on_dense_slide_kept_when_most_slides_use_big_font():
    doc = pymupdf.open()
    for i in range(10):                                    # 6 slide chữ to cỡ 24 + 4 slide chữ dày cỡ 14, đề mục phụ cỡ 20
        pg = doc.new_page(width=720, height=540)
        _t(pg, (40, 60), TITLES[i % 5], 32)
        if i < 6:
            for k in range(4):
                _t(pg, (60, 140 + 40 * k), f"Ý lớn {k} của slide {i} về dữ liệu lớn.", 24)
        else:
            _t(pg, (60, 130), "Đề mục phụ", 20)
            for k in range(3):
                _t(pg, (60, 170 + 22 * k), f"Dòng chi tiết {k} của slide {i} trình bày nội dung dày đặc hơn.", 14)
    assert [p.breadcrumb for p in _passages(doc) if p.page == 7] == [TITLES[1] + " > Đề mục phụ"]
    assert all(p.breadcrumb == TITLES[(p.page - 1) % 5] for p in _passages(doc) if p.page <= 6)


PY_LINES = ["def tinh_diem(ds):", "    tong = 0", "    for x in ds:", "        if x.diem >= 5:",
            "            tong += x.diem", "    return tong / len(ds)"]


def test_python_pasted_in_proportional_font_keeps_indent_levels():
    doc = pymupdf.open()
    pg = doc.new_page()
    _t(pg, (50, 40), "Ví dụ hàm tính điểm trung bình các bài đạt:", 11)
    space = pymupdf.Font(fontfile=FONT).text_length(" ", fontsize=11)
    for i, line in enumerate(PY_LINES):                    # font THƯỜNG, dòng lùi vào bằng tọa độ x
        indent = len(line) - len(line.lstrip())
        _t(pg, (50 + indent * space, 70 + 15 * i), line.lstrip(), 11)
    code = [p for p in _passages(doc) if p.code]
    assert len(code) == 1 and code[0].body == "\n".join(PY_LINES)


def test_table_cells_with_tall_diacritics_and_descenders_keep_all_chars():
    doc = pymupdf.open()
    pg = doc.new_page()
    rows = [["Mã", "Tên"], ["Ễ1", "QUẢN LÝ ĐỀ THI"], ["gy2", "jeopardy ghép"]]
    for r, row in enumerate(rows):
        for c, s in enumerate(row):
            rc = pymupdf.Rect(60 + 200 * c, 100 + 22 * r, 260 + 200 * c, 122 + 22 * r)   # hàng thấp, sát chữ
            pg.draw_rect(rc)
            _t(pg, (rc.x0 + 4, rc.y0 + 16), s, 14)
    md = ingest.read_pdf(doc.tobytes())[0].tables[0].markdown
    assert md.split("\n")[2:] == ["|Ễ1|QUẢN LÝ ĐỀ THI|", "|gy2|jeopardy ghép|"]


def test_font_size_noise_does_not_make_agenda_line_a_slide_title():
    doc = pymupdf.open()
    for i in range(3):
        pg = doc.new_page(width=720, height=540)
        _b(pg, (40, 40), "NỘI DUNG" if i == 0 else TITLES[i], 20)
        items = ["1. Giới thiệu Hadoop", "2. Quá trình phát triển", "3. Kiến trúc Hadoop"]
        for k, s in enumerate(items if i == 0 else [f"Ý {k} của slide {i} trình bày một nội dung." for k in range(3)]):
            _t(pg, (60, 90 + 36 * k), s, 20.1 if k == 1 else 20)   # nhiễu cỡ chữ 0,1 pt ở dòng thứ hai
    crumbs = [p.breadcrumb for p in _passages(doc)]
    assert crumbs == ["NỘI DUNG", TITLES[1], TITLES[2]]
