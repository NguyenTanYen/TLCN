"""Sinh 03_seed_reference.sql từ dữ liệu trích xuất của biểu mẫu BM2 và bảng phân công đánh giá PIs."""
import json, re
d = json.load(open('bm2_extract.json', encoding='utf-8'))
q = lambda s: "'" + str(s).replace("\\", "\\\\").replace("'", "''") + "'" if s is not None else 'NULL'
out = ["-- Dữ liệu tham chiếu sinh tự động từ BM2 (KTDL) và bảng phân công đánh giá PIs HKI 2023-2024",
       "USE assessment_db;", "SET NAMES utf8mb4;"]
# Bloom
out.append("INSERT INTO bloom_levels (id, code, name_vi) VALUES (1,'Remember','Nhớ'),(2,'Understand','Hiểu'),(3,'Apply','Vận dụng'),(4,'Analyze','Phân tích'),(5,'Evaluate','Đánh giá'),(6,'Create','Sáng tạo');")
# Semesters
sems = {}
def sem(txt):
    m = re.search(r'HK\s*(I{1,2})\s*(\d{2})-(\d{2})', txt.replace(' ', ' '))
    if not m: return None
    term = 1 if m.group(1) == 'I' else 2
    y1, y2 = 2000 + int(m.group(2)), 2000 + int(m.group(3))
    return (f'{y1}-{y2}', term)
def add_sem(ay, term):
    y1, y2 = map(int, ay.split('-'))
    if (ay, term) in sems: return
    sems[(ay, term)] = (f'{y1}-09-05', f'{y2}-01-20') if term == 1 else (f'{y2}-02-10', f'{y2}-06-30')
for p in d['pis']:
    s = sem(p['time'])
    if s: add_sem(*s)
for ay in ['2023-2024', '2024-2025']:
    add_sem(ay, 1); add_sem(ay, 2)
rows = []
for (ay, t), (a, b) in sorted(sems.items()):
    rows.append(f"({q(ay)},{t},{q(('HKI ' if t==1 else 'HKII ') + ay[2:4] + '-' + ay[7:9])},{q(a)},{q(b)})")
out.append("INSERT INTO semesters (academic_year, term, name, start_date, end_date) VALUES\n " + ",\n ".join(rows) + ";")
# Program & PLOs
out.append("INSERT INTO programs (id, code, name, level, department, target_pct) VALUES (1,'KTDL','Kỹ thuật dữ liệu','Đại học','Bộ môn Kỹ thuật dữ liệu',75.00);")
rows = []
for i, p in enumerate(d['plos'], 1):
    rows.append(f"({i},1,{p['code'][0]},{q(p['code'])},{q(p['desc'])},{float(p['t1'].rstrip('%')):.2f})")
out.append("INSERT INTO plos (id, program_id, group_no, plo_code, description, target_pct) VALUES\n " + ",\n ".join(rows) + ";")
plo_id = {p['code']: i for i, p in enumerate(d['plos'], 1)}
rows = []
for p in d['plos']:
    rows.append(f"({plo_id[p['code']]},1,{q(p['y1'])},{float(p['t1'].rstrip('%')):.2f})")
    rows.append(f"({plo_id[p['code']]},2,{q(p['y2'])},{float(p['t2'].rstrip('%')):.2f})")
    rows.append(f"({plo_id[p['code']]},3,'2024-2025',75.00)")
out.append("INSERT INTO plo_measurement_plans (plo_id, round_no, academic_year, target_pct) VALUES\n " + ",\n ".join(rows) + ";")
# PIs
rows = []
pi_ids = []
for i, p in enumerate(d['pis'], 1):
    rows.append(f"({i},{plo_id[p['plo']]},{q(p['code'])},{q(p['desc'])})"); pi_ids.append(i)
out.append("INSERT INTO performance_indicators (id, plo_id, pi_code, description) VALUES\n " + ",\n ".join(rows) + ";")
# Courses (mã môn thật trong bảng phân công đánh giá PIs HKI 2023-2024)
courses = [('INDE131777','Nhập môn ngành Kỹ thuật dữ liệu'),('RPAN233577','Lập trình R cho phân tích'),
           ('BDAN333977','Big Data Analysis (Phân tích dữ liệu lớn)'),('BDES333877','Nhập môn dữ liệu lớn'),
           ('DBMS330284','Hệ quản trị cơ sở dữ liệu'),('DBSE431284','Bảo mật cơ sở dữ liệu'),
           ('PODE434277','Tiểu luận chuyên ngành Kỹ thuật dữ liệu'),('POIS431184','Tiểu luận chuyên ngành Hệ thống thông tin'),
           ('ECOM430984','Thương mại điện tử')]
out.append("INSERT INTO courses (id, course_code, course_name, credits) VALUES\n " + ",\n ".join(
    f"({i},{q(c)},{q(n)},3)" for i, (c, n) in enumerate(courses, 1)) + ";")
out.append("INSERT INTO program_courses (program_id, course_id) VALUES " + ",".join(f"(1,{i})" for i in range(1, len(courses)+1)) + ";")
cid = {c: i for i, (c, _) in enumerate(courses, 1)}
alias = [(r'nhập môn\s*/?\s*ngành', 'INDE131777'), (r'nhập môn (dll|dữ liệu lớn)', 'BDES333877'),
         (r'(pt\s*bigdata|phân tích\s*/?\s*dữ liệu lớn|bigdata)', 'BDAN333977'), (r'^r$|lập trình r', 'RPAN233577'),
         (r'tlcn|tiểu luận', 'PODE434277'), (r'hệ quản trị csdl', 'DBMS330284')]
def match(name):
    n = re.sub(r'\s+', ' ', name.lower()).strip(' ,')
    for pat, code in alias:
        if re.search(pat, n): return cid[code]
    return None
# Lecturers
names = []
def lect(n):
    n = n.split('/')[0].strip()
    if not n or n.lower().startswith('gv '): return None
    if n not in names: names.append(n)
    return names.index(n) + 1
assign = [('INDE131777','Trần Trọng Bình','Đánh giá theo 7 CĐR'),('RPAN233577','Trần Trọng Bình','Đánh giá theo 19 CĐR'),
          ('BDAN333977','Lê Thị Minh Châu',None),('BDES333877','Lê Thị Minh Châu',None),('DBMS330284','Nguyễn Thành Sơn',None),
          ('DBSE431284','Lê Thị Minh Châu',None),('PODE434277',None,'Tất cả thầy/cô có HD'),('POIS431184',None,'Tất cả thầy/cô có HD'),
          ('ECOM430984','Võ Xuân Thể',None),('ECOM430984','Phạm Chí Công',None),('ECOM430984','Nguyễn Văn Thành',None)]
for a in assign:
    if a[1]: lect(a[1])
pi_course_rows, plan_rows = [], []
for i, p in enumerate(d['pis'], 1):
    for cn in re.split(r',', p['courses']):
        c = match(cn) if cn.strip() else None
        if c and f"({i},{c})" not in pi_course_rows: pi_course_rows.append(f"({i},{c})")
    c = match(p['evid']); s = sem(p['time'])
    if c and s:
        l = lect(p['gv'])
        if f"({i},{c})" not in pi_course_rows: pi_course_rows.append(f"({i},{c})")
        plan_rows.append((i, c, s, p['method'], p['cycle'], float(p['target'].rstrip('%')), l))
out.append("INSERT INTO lecturers (id, lecturer_code, full_name, department) VALUES\n " + ",\n ".join(
    f"({i},{q('GV%03d' % i)},{q(n)},'Bộ môn Kỹ thuật dữ liệu')" for i, n in enumerate(names, 1)) + ";")
out.append("INSERT INTO pi_courses (pi_id, course_id) VALUES " + ",".join(pi_course_rows) + ";")
if plan_rows:
    out.append("INSERT INTO pi_assessment_plans (pi_id, course_id, semester_id, method, cycle, target_pct, lecturer_id) VALUES\n " + ",\n ".join(
        f"({pi},{c},(SELECT id FROM semesters WHERE academic_year={q(s[0])} AND term={s[1]}),{q(m)},{q(cy)},{t:.2f},{l if l else 'NULL'})"
        for pi, c, s, m, cy, t, l in plan_rows) + ";")
# Môn TLCN/KLTN không giao cho một GV mà cho "tất cả thầy/cô có hướng dẫn" (all_supervisors = 1, lecturer_id NULL)
out.append("INSERT INTO assessment_assignments (semester_id, course_id, lecturer_id, all_supervisors, note) VALUES\n " + ",\n ".join(
    f"((SELECT id FROM semesters WHERE academic_year='2023-2024' AND term=1),{cid[c]},{names.index(n)+1 if n else 'NULL'},{0 if n else 1},{q(note)})"
    for c, n, note in assign) + ";")
open('03_seed_reference.sql', 'w', encoding='utf-8').write("\n\n".join(out) + "\n")
print('plans', len(plan_rows), 'pi_courses', len(pi_course_rows), 'lecturers', len(names), 'semesters', len(sems))
