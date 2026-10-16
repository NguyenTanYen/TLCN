"""Đọc file PDF chương trình đào tạo (mẫu ĐH Công nghệ Kỹ thuật TP.HCM 2026) -> JSON + SQL nạp vào assessment_db.

Lấy ra:
  * thông tin chung (tên, mã ngành, số tín chỉ, số quyết định);
  * PLO và PI (mục 7.3) kèm trình độ năng lực, phân loại CĐR chung / chuyên biệt;
  * danh sách học phần (mục 9): mã, tên, tín chỉ tổng / LT / TH, học phần trước – tiên quyết, khối kiến thức, tự chọn;
  * học kỳ trong kế hoạch giảng dạy và mức đáp ứng của từng học phần với từng PI (Phụ lục II);
  * mô tả vắn tắt học phần và cấu trúc tín chỉ (Phụ lục I); các chương nếu phần mô tả liệt kê "Chương n: ...".

Cách dùng:  python doc_ctdt.py CTDT_CNTT_2026.pdf CNTT-2026  CTDT_KTDL_2026.pdf KTDL-2026  > ../../database/04_ctdt_2026.sql
(cần: pip install pdfplumber)
"""
from __future__ import annotations

import difflib
import json
import re
import sys
import unicodedata

import pdfplumber

CODE = re.compile(r"^[A-Z]{3,5}\d{6}$")
CODE_ANY = re.compile(r"[A-Z]{3,5}\d{6}")
PI_RE = re.compile(r"^PI\s*(\d+)\.(\d+)\s*(.*)$", re.S)

# Nội dung PLO lấy nguyên văn bảng 7.3 (ô bảng bị ngắt trang nên ghi tay để không mất chữ)
PLO_TEXT = {
    "KTDL": {
        1: "Khả năng áp dụng các nguyên tắc toán học, thuật toán, cũng như khoa học để xác định giải pháp cho vấn đề trong công nghệ thông tin.",
        2: "Khả năng nhận biết trách nhiệm nghề nghiệp và đưa ra những đánh giá sáng suốt trong xây dựng giải pháp kỹ thuật dữ liệu dựa trên các nền tảng pháp lý và đạo đức.",
        3: "Khả năng tiếp thu và áp dụng kiến thức mới, sử dụng các chiến lược học tập phù hợp.",
        4: "Khả năng hoạt động hiệu quả trong một nhóm mà các thành viên cùng nhau lãnh đạo, tạo ra một môi trường hợp tác và hòa nhập, thiết lập các mục tiêu, lập kế hoạch nhiệm vụ và đáp ứng các mục tiêu.",
        5: "Khả năng giao tiếp hiệu quả với nhiều đối tượng, và giao tiếp bằng tiếng Anh.",
        6: "Khả năng thiết kế, cài đặt, và đánh giá giải pháp để đáp ứng các yêu cầu cụ thể trong lĩnh vực Kỹ thuật dữ liệu.",
        7: "Khả năng áp dụng các công nghệ phù hợp để tạo ra các giải pháp về kỹ thuật dữ liệu.",
    },
    "CNTT": {
        1: "Khả năng áp dụng các nguyên tắc toán học, thuật toán, cũng như khoa học để xác định giải pháp cho vấn đề trong công nghệ thông tin.",
        2: "Khả năng nhận biết trách nhiệm nghề nghiệp và đưa ra những đánh giá sáng suốt trong xây dựng giải pháp Công nghệ thông tin dựa trên các nền tảng pháp lý và đạo đức.",
        3: "Khả năng tiếp thu và áp dụng kiến thức mới, sử dụng các chiến lược học tập phù hợp.",
        4: "Khả năng hoạt động hiệu quả trong một nhóm mà các thành viên cùng nhau lãnh đạo, tạo ra một môi trường hợp tác và hòa nhập, thiết lập các mục tiêu, lập kế hoạch nhiệm vụ và đáp ứng các mục tiêu.",
        5: "Khả năng giao tiếp hiệu quả với nhiều đối tượng, và giao tiếp bằng tiếng Anh.",
        6: "Khả năng thiết kế, cài đặt, và đánh giá giải pháp để đáp ứng các yêu cầu cụ thể trong lĩnh vực Công nghệ thông tin.",
        7: "Khả năng áp dụng các công nghệ phù hợp để tạo ra các giải pháp về Công nghệ thông tin.",
    },
}
# Số quyết định được điền tay trên bản PDF (lớp chú thích) nên không đọc được từ phần chữ
DECISION = {"CNTT": "3052/QĐ-ĐHCNKT ngày 14/8/2026", "KTDL": "3050/QĐ-ĐHCNKT ngày 14/8/2026"}
GROUPS = {"Kiến thức": 1, "Kỹ năng": 2, "Mức tự chủ": 3}


def clean(s) -> str:
    s = unicodedata.normalize("NFC", str(s or ""))
    return re.sub(r"\s+", " ", s.replace("\n", " ")).strip()


def norm_name(s: str) -> str:
    s = clean(s).lower().replace("*", "")
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("–", "-").replace("–", "-")
    return " ".join(re.sub(r"[^0-9a-zà-ỹđ ]", " ", s).split())


def num(s):
    s = clean(s)
    m = re.match(r"^(\d+)", s)
    return int(m.group(1)) if m else None


def read_tables(pdf):
    out = []
    for i, p in enumerate(pdf.pages):
        for t in p.extract_tables():
            out.append((i + 1, [[c if c is not None else "" for c in r] for r in t]))
    return out


def read_text(pdf) -> str:
    return "\n".join((p.extract_text(layout=False) or "") for p in pdf.pages)


# ------------------------------------------------------------------ thông tin chung
def general(text: str) -> dict:
    g = {}
    for key, pat in (("name", r"Tên chương trình đào tạo Tiếng Việt\s*:\s*(.+)"), ("name_en", r"Tên chương trình đào tạo Tiếng Anh\s*:\s*(.+)"),
                     ("major_code", r"Mã ngành\s*:?\s*(\d{7})"), ("total_credits", r"Khối lượng học tập\s+(\d+)\s*TC"),
                     ("faculty", r"Đơn vị quản lý\s*:?\s*(Khoa[^\n]+)")):
        m = re.search(pat, text)
        if m:
            g[key] = clean(m.group(1))
    m = re.search(r"Kèm theo Quyết định số\s*(\d+)\s*/\s*QĐ[-–]ĐHCNKT\s*ngày\s*(\d+)\s*tháng\s*(\d+)\s*năm\s*(\d{4})", text)
    if m:
        g["decision_no"] = f"{m.group(1)}/QĐ-ĐHCNKT ngày {m.group(2)}/{m.group(3)}/{m.group(4)}"
    m = re.search(r"7\.1\.?\s*Mục tiêu chung\s*(.+?)7\.2", text, re.S)
    if m:
        g["objective"] = clean(m.group(1))
    return g


# ------------------------------------------------------------------ PLO / PI
def plos(tables, key: str):
    res, cur, group = {}, None, 1
    for page, rows in tables:
        if not rows or "Chỉ số thực hiện" not in clean(rows[0][2] if len(rows[0]) > 2 else ""):
            continue
        for r in rows[2:]:
            c0, c1 = clean(r[0]), clean(r[1])
            if c0 in ("1", "2", "3") and c1:
                group = next((v for k, v in GROUPS.items() if c1.startswith(k)), group)
                continue
            m = re.match(r"^PLO\s*(\d+)$", c0)
            if m:
                n = int(m.group(1))
                cur = res.setdefault(n, {"no": n, "group_no": group, "description": PLO_TEXT[key][n], "pis": [],
                                         "level": num(r[4]), "type": clean(r[5]).replace("CĐR chuyên biệt", "CĐR chuyên biệt") or None})
            pm = PI_RE.match(clean(r[2]))
            if pm and cur:
                n_plo = int(pm.group(1))
                tgt = res.get(n_plo) or cur
                tgt["pis"].append({"code": f"PI{pm.group(1)}.{pm.group(2)}", "description": clean(pm.group(3)), "level": num(r[3])})
    for p in res.values():
        p["type"] = p["type"] and p["type"].replace("CĐR chung", "CĐR chung")
    return [res[k] for k in sorted(res)]


# ------------------------------------------------------------------ học phần (mục 9)
def courses(tables):
    out, order = {}, []
    block, sub, group, elective, last = None, None, None, False, None
    started = False
    for page, rows in tables:
        hdr = [clean(x) for x in rows[0]]
        if not (hdr and hdr[0] == "TT" and hdr[1].startswith("Mã HP")):
            continue
        started = True
        for r in rows[1:]:
            cells = [clean(x) for x in r]
            if not any(cells) or cells[3:4] == ["Tổng"] or "Tổng" in cells[:8] and not any(CODE.match(c) for c in cells):
                continue
            c0 = cells[0]
            code_i = next((i for i, c in enumerate(cells) if CODE.match(c)), None)
            if code_i is None:
                txt = next((c for c in cells[1:] if c and not c.isdigit()), "")
                if re.match(r"^(I|II|III|IV)(\.\d+)*\.?$", c0):
                    top = c0.split(".")[0]
                    if top in ("III", "IV"):
                        block, last = ("Chuyên đề bổ trợ" if top == "IV" else None), None
                        continue
                    if c0.count(".") == 0 or (c0.count(".") == 1 and not c0.endswith(".")) or c0 == "II.6.":
                        block, sub = txt, None
                    else:
                        sub = txt
                    group, elective = None, "tự chọn" in txt.lower()
                    last = None
                elif c0.startswith("Nhóm"):
                    group, elective = c0, True
                    last = None
                elif not c0 and txt and not any(ch.isdigit() for ch in txt[:3]) and last and len(txt) < 30 and not re.search(r"chuyên ngành|Công Nghệ|Kiến thức|Sinh viên", txt, re.I):
                    last["name"] += " " + txt           # phần tên học phần xuống dòng
                elif not c0 and txt.startswith("Kiến thức chuyên ngành"):
                    block, sub, group, elective, last = txt, None, None, False, None
                elif not c0 and txt and re.search(r"chuyên ngành|Công Nghệ Phần Mềm", txt, re.I):
                    sub = txt
                    last = None
                continue
            if block is None:
                continue
            code = cells[code_i]
            rest = [c for c in cells[code_i + 1:]]
            name = next((c for c in rest if c and not re.match(r"^\d+$", c) and not CODE_ANY.match(c)), "")
            after = rest[rest.index(name) + 1:] if name in rest else rest
            nums = [num(c) for c in after if re.match(r"^\d+$", c)]
            prereq_cell = cells[-1] if cells[-1] != name else ""
            prereq = sorted(set(CODE_ANY.findall(prereq_cell)) - {code})
            note = None if CODE_ANY.search(prereq_cell) or not prereq_cell or re.match(r"^\d+$", prereq_cell) else prereq_cell
            c = {"code": code, "name": name.replace("**", "").replace("*", "").strip(), "credits": nums[0] if nums else None,
                 "lt": nums[1] if len(nums) > 1 else None, "th": nums[2] if len(nums) > 2 else None,
                 "prereq": prereq, "block": block, "sub": sub, "group": group,
                 "elective": bool(elective or c0.startswith("N")), "note": note}
            if code not in out:
                out[code] = c
                order.append(code)
            elif out[code]["elective"] and not c["elective"]:   # môn vừa ở nhóm tự chọn vừa bắt buộc: lấy dòng bắt buộc
                out[code].update({k: c[k] for k in ("block", "sub", "group", "elective")})
            last = out[code]
    return [out[k] for k in order], started


# ------------------------------------------------------------------ Phụ lục II: học kỳ + mức đáp ứng PI
def matrix(tables):
    res = {}
    for page, rows in tables:
        hdr = [clean(x) for x in rows[0]]
        if not hdr or not (hdr[0].startswith("PLO/PI") or hdr[0].startswith("PI PLO") or hdr[0] == "PI PLO"):
            continue
        pi_row = next((r for r in rows[:4] if sum(1 for c in r if re.match(r"^PI\d\.\d$", clean(c))) >= 5), None)
        if not pi_row:
            continue
        cols = {i: clean(c) for i, c in enumerate(pi_row) if re.match(r"^PI\d\.\d$", clean(c))}
        sem = None
        for r in rows:
            cells = [clean(x) for x in r]
            hk = next((c for c in cells if c.startswith("Học kỳ")), None)
            if hk:
                sem = num(hk.replace("Học kỳ", ""))
            if not CODE.match(cells[0]):
                continue
            d = res.setdefault(cells[0], {"semester": sem, "name": cells[1], "pis": {}})
            for i, pi in cols.items():
                v = cells[i] if i < len(cells) else ""
                if v and v not in ("-",):
                    d["pis"][pi] = v
    return res


# ------------------------------------------------------------------ mục 10: kế hoạch giảng dạy (học kỳ)
def teaching_plan(text: str) -> dict:
    start = text.find("Kế hoạch giảng dạy")
    end = text.find("11.", start + 20)
    sem, out = None, {}
    for ln in text[start:end if end > 0 else None].splitlines():
        m = re.match(r"^\s*Học kỳ\s*(\d+)", ln)
        if m:
            sem = int(m.group(1))
            continue
        for code in CODE_ANY.findall(ln):
            if sem and re.match(r"^\s*\d+\.?\s+" + code, ln) or (sem and ln.strip().startswith(code)):
                out.setdefault(code, sem)
    return out


# ------------------------------------------------------------------ Phụ lục I: mô tả học phần
def descriptions(text: str):
    start = text.find("MÔ TẢ VẮN TẮT NỘI DUNG")
    end = text.find("PHỤ LỤC II", start)
    body = text[start:end if end > 0 else None]
    lines = body.splitlines()
    entries, cur = [], None
    head = re.compile(r"^\s*(\d{1,3})\.\s+(\S.{2,120})$")
    for i, ln in enumerate(lines):
        m = head.match(ln)
        look = " ".join(lines[i + 1:i + 4])
        if m and re.search(r"Mã môn học|Mã học phần|Cấu trúc học phần|Số tín chỉ", look):
            cur = {"title": clean(m.group(2)), "code": None, "structure": None, "desc": [], "in_desc": False}
            entries.append(cur)
            continue
        if not cur:
            continue
        s = ln.strip()
        mm = re.match(r"Mã (?:môn|học) (?:học|phần)\s*:\s*([A-Z]{3,5}\d{6})", s)
        if mm:
            cur["code"] = mm.group(1); continue
        mm = re.match(r"Cấu trúc học phần[^:]*:\s*(.+)", s)
        if mm:
            cur["structure"] = clean(mm.group(1)); continue
        if re.match(r"(Mô tả học phần|Tóm tắt nội dung học phần|Mô tả vắn tắt)\s*:?", s):
            cur["in_desc"] = True
            rest = re.sub(r"^(Mô tả học phần|Tóm tắt nội dung học phần|Mô tả vắn tắt)\s*:?", "", s).strip()
            if rest:
                cur["desc"].append(rest)
            continue
        if re.match(r"^(A|B|C)\s*[–-]\s*Phần", s) or re.match(r"^Kiến thức (giáo dục|cơ sở|chuyên)", s) and s.endswith(":"):
            cur["in_desc"] = False; continue
        if cur["in_desc"] and s and not re.match(r"^\d+$", s):
            cur["desc"].append(s)
    for e in entries:
        raw = e.pop("desc")
        e.pop("in_desc")
        e["chapters"] = []
        for s in raw:
            m = re.match(r"^[-–•]?\s*Chương\s*(\d+)\s*[:.\-–]\s*(.+)$", s)
            if m and len(e["chapters"]) < 20:
                e["chapters"].append((int(m.group(1)), clean(m.group(2))[:250]))
        e["description"] = clean(" ".join(raw))
    return entries


def match_desc(courses_list, entries):
    by_code = {e["code"]: e for e in entries if e["code"]}
    names = {}
    for e in entries:
        names.setdefault(norm_name(e["title"]), e)
    for c in courses_list:
        e = by_code.get(c["code"])
        if not e:
            key = norm_name(c["name"])
            e = names.get(key)
            if not e:
                cand = difflib.get_close_matches(key, list(names), n=1, cutoff=0.82)
                e = names[cand[0]] if cand else None
        if e:
            c["description"] = e["description"] or None
            c["structure"] = e["structure"]
            c["chapters"] = e["chapters"]


def parse(path: str, code: str) -> dict:
    key = code.split("-")[0]
    with pdfplumber.open(path) as pdf:
        tables = read_tables(pdf)
        text = read_text(pdf)
    prog = {"code": code, **general(text), "plos": plos(tables, key)}
    prog.setdefault("decision_no", DECISION.get(key))
    cl, _ = courses(tables)
    mx = matrix(tables)
    plan = teaching_plan(text)
    by_name = {norm_name(c["name"]): c for c in cl}
    for c in cl:
        m = mx.get(c["code"])
        c["semester"] = plan.get(c["code"]) or (m["semester"] if m else None)
        c["pi_levels"] = dict(m["pis"]) if m else {}
    # học phần chỉ có trong ma trận (không có ở mục 9): mã gõ sai trong Phụ lục II -> ghép theo tên; còn lại thêm mới
    known = {c["code"] for c in cl}
    for k, m in mx.items():
        if k in known:
            continue
        twin = by_name.get(norm_name(m["name"]))
        if twin:
            for pi, lv in m["pis"].items():
                twin["pi_levels"].setdefault(pi, lv)
            twin["semester"] = twin["semester"] or m["semester"]
            continue
        if True:
            cl.append({"code": k, "name": m["name"].replace("**", ""), "credits": None, "lt": None, "th": None, "prereq": [],
                       "block": "Chuyên đề bổ trợ" if k.startswith(("SEMI", "DICO")) else "Khác (theo Phụ lục II)", "sub": None, "group": None, "elective": False, "note": None,
                       "semester": plan.get(k) or m["semester"], "pi_levels": m["pis"]})
    match_desc(cl, descriptions(text))
    prog["courses"] = cl
    return prog


# ------------------------------------------------------------------ sinh SQL
def q(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"


def to_sql(progs: list[dict]) -> str:
    out = ["-- Hai chương trình đào tạo 2026 (CNTT, KTDL) đọc từ file PDF bằng tools/ctdt_2026/doc_ctdt.py.",
           "-- Chạy lại an toàn: chỉ thêm phần còn thiếu, không ghi đè dữ liệu đã chỉnh trên hệ thống.", "",
           "SET NAMES utf8mb4;", ""]
    for p in progs:
        pc = q(p["code"])
        out.append(f"-- ===================== {p['code']}: {p.get('name')}")
        out.append("INSERT IGNORE INTO programs (code, name, name_en, level, department, faculty, major_code, cohort_year, total_credits, decision_no, objective, target_pct) VALUES "
                   f"({pc}, {q(p.get('name'))}, {q(p.get('name_en'))}, 'Đại học', NULL, {q(p.get('faculty'))}, {q(p.get('major_code'))}, 2026, "
                   f"{q(int(p['total_credits']) if p.get('total_credits') else None)}, {q(p.get('decision_no'))}, {q(p.get('objective'))}, 75.00);")
        out.append(f"SET @p := (SELECT id FROM programs WHERE code = {pc});")
        for plo in p["plos"]:
            code = f"PLO{plo['no']}"
            out.append("INSERT IGNORE INTO plos (program_id, group_no, plo_code, description, target_pct, competency_level, plo_type) VALUES "
                       f"(@p, {plo['group_no']}, {q(code)}, {q(plo['description'])}, 75.00, {q(plo['level'])}, {q(plo['type'])});")
            for pi in plo["pis"]:
                out.append("INSERT IGNORE INTO performance_indicators (plo_id, pi_code, description, competency_level) "
                           f"SELECT id, {q(pi['code'])}, {q(pi['description'])}, {q(pi['level'])} FROM plos WHERE program_id = @p AND plo_code = {q(code)};")
        out.append("")
        for c in p["courses"]:
            if not c.get("credits"):
                c["credits"] = int(re.match(r"\d+", c.get("structure") or "3").group(0)) if c.get("structure") else 3
            prereq = ", ".join(c["prereq"]) if c["prereq"] else None
            out.append("INSERT INTO courses (course_code, course_name, credits, credits_theory, credits_practice, course_structure, prerequisites, description) VALUES "
                       f"({q(c['code'])}, {q(c['name'][:255])}, {q(c['credits'])}, {q(c['lt'])}, {q(c['th'])}, {q(c.get('structure'))}, {q(prereq and prereq[:255])}, {q(c.get('description'))}) "
                       "ON DUPLICATE KEY UPDATE credits_theory = COALESCE(credits_theory, VALUES(credits_theory)), "
                       "credits_practice = COALESCE(credits_practice, VALUES(credits_practice)), course_structure = COALESCE(course_structure, VALUES(course_structure)), "
                       "prerequisites = COALESCE(prerequisites, VALUES(prerequisites)), description = COALESCE(description, VALUES(description));")
            blk = " – ".join(x for x in (c["block"], c["sub"], c["group"]) if x)
            out.append("INSERT IGNORE INTO program_courses (program_id, course_id, semester_no, knowledge_block, is_elective) "
                       f"SELECT @p, id, {q(c.get('semester'))}, {q(blk[:150] or None)}, {q(c['elective'])} FROM courses WHERE course_code = {q(c['code'])};")
            for pi, lv in sorted(c.get("pi_levels", {}).items()):
                out.append("INSERT IGNORE INTO pi_courses (pi_id, course_id, level) SELECT pi.id, c.id, " + q(lv[:2]) +
                           " FROM performance_indicators pi JOIN plos pl ON pl.id = pi.plo_id JOIN courses c ON c.course_code = " + q(c["code"]) +
                           f" WHERE pl.program_id = @p AND pi.pi_code = {q(pi)};")
            for n, name in c.get("chapters") or []:
                out.append("INSERT INTO course_outlines (course_id, chapter_number, chapter_name) SELECT c.id, "
                           f"{n}, {q(name)} FROM courses c WHERE c.course_code = {q(c['code'])} "
                           "AND NOT EXISTS (SELECT 1 FROM course_outlines o WHERE o.course_id = c.id AND o.chapter_number = " + str(n) + ");")
        out.append("")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2 or len(args) % 2:
        sys.exit(__doc__)
    progs = [parse(args[i], args[i + 1]) for i in range(0, len(args), 2)]
    if "--json" in sys.argv:
        print(json.dumps(progs, ensure_ascii=False, indent=1))
    else:
        sys.stdout.write(to_sql(progs))
