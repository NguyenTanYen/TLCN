"""Sinh ERD (Graphviz) và từ điển dữ liệu trực tiếp từ information_schema của assessment_db."""
import json, subprocess
import pymysql

GROUPS = {
 "A. Người dùng và tổ chức": ["users", "lecturers", "students", "semesters"],
 "B. CTĐT và CĐR CTĐT": ["programs", "plos", "plo_measurement_plans", "performance_indicators", "program_courses", "pi_courses"],
 "C. Học phần và CĐR môn học": ["courses", "course_outlines", "bloom_levels", "clos", "clo_plo_mapping"],
 "D. Kế hoạch đo lường": ["clo_assessment_plans", "pi_assessment_plans", "pi_plan_clos", "assessment_assignments"],
 "E. Lớp HP và ngân hàng câu hỏi": ["class_sections", "enrollments", "question_bank", "question_options", "question_clo_mapping"],
 "F. Đề thi và nhóm đề": ["exams", "exam_questions", "exam_versions", "exam_version_questions", "exam_version_options"],
 "G. Kết quả và báo cáo": ["exam_attempts", "item_level_results", "item_statistics", "attempt_clo_results", "clo_results",
                          "pi_results", "plo_results", "personalized_learning_paths", "learning_path_items", "sync_runs"],
}
COLORS = {"A": "#FDF3E1", "B": "#E8F1FB", "C": "#EAF6EA", "D": "#F3ECFA", "E": "#FFF7D6", "F": "#FDE9E7", "G": "#E6F4F4"}
import os
c = pymysql.connect(host="127.0.0.1", port=int(os.environ.get("DBPORT", 3307)), user="root", password="1234", database="information_schema", charset="utf8mb4")
cur = c.cursor()
cur.execute("""SELECT table_name, column_name, column_type, is_nullable, column_key, column_default, extra, ordinal_position
               FROM columns WHERE table_schema='assessment_db' AND table_name IN (SELECT table_name FROM tables WHERE table_schema='assessment_db' AND table_type='BASE TABLE')
               ORDER BY table_name, ordinal_position""")
cols = {}
for t, col, typ, nul, key, dflt, extra, _ in cur.fetchall():
    cols.setdefault(t, []).append(dict(name=col, type=typ, null=nul == "YES", key=key, default=dflt, extra=extra))
cur.execute("""SELECT table_name, column_name, referenced_table_name, referenced_column_name, constraint_name FROM key_column_usage
               WHERE table_schema='assessment_db' AND referenced_table_name IS NOT NULL""")
fks = cur.fetchall()
cur.execute("""SELECT tc.table_name, tc.constraint_name, rc.delete_rule FROM table_constraints tc JOIN referential_constraints rc
               ON rc.constraint_schema=tc.constraint_schema AND rc.constraint_name=tc.constraint_name WHERE tc.table_schema='assessment_db'""")
rules = {(t, n): r for t, n, r in cur.fetchall()}
cur.execute("""SELECT table_name, index_name, GROUP_CONCAT(column_name ORDER BY seq_in_index) FROM statistics
               WHERE table_schema='assessment_db' AND non_unique=0 AND index_name<>'PRIMARY' GROUP BY table_name, index_name""")
uniques = {}
for t, i, cc in cur.fetchall():
    uniques.setdefault(t, []).append(cc)
cur.execute("""SELECT table_name, constraint_name FROM table_constraints WHERE table_schema='assessment_db' AND constraint_type='CHECK'""")
checks = {}
for t, n in cur.fetchall():
    checks.setdefault(t, []).append(n)
cur.execute("SELECT cc.constraint_name, cc.check_clause FROM check_constraints cc WHERE cc.constraint_schema='assessment_db'")
check_clause = dict(cur.fetchall())
all_tables = [t for g in GROUPS.values() for t in g]
assert set(all_tables) == set(cols), set(cols) ^ set(all_tables)
fk_cols = {(t, col) for t, col, *_ in fks}
group_of = {t: g for g, ts in GROUPS.items() for t in ts}


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def node(t, full=True, stub=False, nid=None):
    g = group_of[t][0]
    color = "#EEEEEE" if stub else COLORS[g]
    head = f'<b>{t}</b>' if full else f'<b>{t}</b> <font point-size="8" color="#64748b">({g})</font>'
    rows = [f'<tr><td bgcolor="{color}" colspan="2">{head}</td></tr>']
    if full:
        for col in cols[t]:
            mark = ("PK " if col["key"] == "PRI" else "") + ("FK" if (t, col["name"]) in fk_cols else "")
            name = f"<u>{esc(col['name'])}</u>" if col["key"] == "PRI" else esc(col["name"])
            typ = col["type"].replace(" unsigned", "")
            if len(typ) > 26:
                typ = typ[:24] + "…"
            tag = f' <font color="#1d4ed8" point-size="8">{mark.strip()}</font>' if mark.strip() else ""
            rows.append(f'<tr><td align="left" port="{col["name"]}">{name}{tag}</td>'
                        f'<td align="left"><font color="#555555">{esc(typ)}{"" if col["null"] else " NN"}</font></td></tr>')
    return f'"{nid or t}" [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="3">{"".join(rows)}</table>>];'


def _pts(d):
    import re
    return [(float(a), float(b)) for a, b in re.findall(r"(-?[\d.]+),(-?[\d.]+)", d)]


def add_crowfoot(svg):
    """Vẽ ký hiệu quan hệ kiểu Crow's Foot ở hai đầu mỗi đường nối thẳng góc:
    phía bảng cha "một và chỉ một" (‖), phía bảng con "một hoặc nhiều" (chân chim + vạch)."""
    import re, math
    boxes = {}
    for m in re.finditer(r'<g id="node\d+" class="node">\s*<title>([^<]+)</title>(.*?)</g>', svg, re.S):
        xs, ys = [], []
        for d in re.findall(r'points="([^"]+)"', m.group(2)):
            for x, y in _pts(d):
                xs.append(x); ys.append(y)
        if xs:
            boxes[m.group(1).replace("&#45;", "-")] = (min(xs), min(ys), max(xs), max(ys))
    def dist(p, b):
        dx = max(b[0] - p[0], 0, p[0] - b[2]); dy = max(b[1] - p[1], 0, p[1] - b[3]); return math.hypot(dx, dy)
    marks = []
    col = "#334155"
    ln = lambda a, b: marks.append(f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" stroke="{col}" stroke-width="1.3"/>')
    for m in re.finditer(r'<g id="fk__(.+?)__(.+?)__.+?" class="edge">.*?<path[^>]* d="([^"]+)"', svg, re.S):
        parent, child, d = m.group(1), m.group(2), m.group(3)
        pts = _pts(d)
        if len(pts) < 2 or parent not in boxes or child not in boxes:
            continue
        a, b = pts[0], pts[-1]
        if dist(a, boxes[parent]) + dist(b, boxes[child]) > dist(b, boxes[parent]) + dist(a, boxes[child]):
            pts = pts[::-1]; a, b = b, a
        for end, seq, kind in ((a, pts, "one"), (b, pts[::-1], "many")):
            nxt = next((q for q in seq[1:] if math.hypot(q[0] - end[0], q[1] - end[1]) > 1), None)
            if not nxt:
                continue
            L = math.hypot(nxt[0] - end[0], nxt[1] - end[1]); ux, uy = (nxt[0] - end[0]) / L, (nxt[1] - end[1]) / L
            nx, ny = -uy, ux
            at = lambda k, s=0: (end[0] + ux * k + nx * s, end[1] + uy * k + ny * s)
            if kind == "one":
                for k in (5, 9):
                    ln(at(k, -5), at(k, 5))
            else:
                q = at(11)
                for s in (-6, 0, 6):
                    ln(q, at(0, s))
                ln(at(14, -5), at(14, 5))
    i = svg.rfind("</g>")
    return svg[:i] + "\n".join(marks) + "\n" + svg[i:]


def render(name, tables, full=True, rankdir="LR", clusters=False, extra_attrs=""):
    lines = [f'digraph G {{ rankdir={rankdir}; graph [fontname="DejaVu Sans", splines=ortho, nodesep=0.6, ranksep=0.9 {extra_attrs}];',
             'node [shape=none, margin=0, fontname="DejaVu Sans", fontsize=10]; edge [color="#334155", penwidth=1.2, dir=none];']
    stubs = set()
    for t, col, rt, rc, cn in fks:
        if t in tables and rt not in tables:
            stubs.add(rt)
    if clusters:
        for i, (g, ts) in enumerate(GROUPS.items()):
            lines.append(f'subgraph cluster_{i} {{ label="{g}"; style="rounded,filled"; fillcolor="{COLORS[g[0]]}40"; color="#999999"; fontsize=12;')
            lines += [node(t, full) for t in ts if t in tables]
            lines.append("}")
    else:
        lines += [node(t, full) for t in tables]
    # sơ đồ từng nhóm: mỗi bảng ngoài nhóm được vẽ riêng cạnh từng bảng con (tránh các đường nối chồng chéo)
    stub_ids = {}
    for t, col, rt, rc, cn in fks:
        if t in tables and rt in stubs and (rt, t) not in stub_ids:
            stub_ids[(rt, t)] = f"{rt}@{t}"
    lines += [node(rt, False, stub=True, nid=sid) for (rt, t), sid in sorted(stub_ids.items())]
    seen = set()
    for t, col, rt, rc, cn in fks:
        if t in tables and (rt in tables or rt in stubs):
            key = (t, rt)
            if key in seen:
                continue
            seen.add(key)
            # nét thẳng góc nối bảng cha (‖ một) – bảng con (chân chim nhiều), kiểu MySQL Workbench
            src_id = stub_ids.get((rt, t), rt)
            lines.append(f'"{src_id}" -> "{t}" [id="fk__{src_id}__{t}__{col}"];')
    lines.append("}")
    src = f"fig/{name}.dot"
    open(src, "w").write("\n".join(lines))
    svg = subprocess.run(["dot", "-Tsvg", src], check=True, capture_output=True, text=True, timeout=900).stdout
    svg = add_crowfoot(svg)
    open(f"fig/{name}.svg", "w").write(svg)
    import cairosvg
    cairosvg.svg2png(bytestring=svg.encode(), write_to=f"fig/{name}.png", scale=160 / 72, background_color="white")


for i, (g, ts) in enumerate(GROUPS.items()):
    render(f"erd_{g[0]}", ts, full=True, rankdir="LR")
import sys
if "--overview" in sys.argv:
    render("erd_overview", all_tables, full=False, clusters=False, rankdir="TB", extra_attrs=", ranksep=0.8, nodesep=0.3")
json.dump({"groups": GROUPS, "cols": cols, "fks": fks, "rules": {f"{k[0]}|{k[1]}": v for k, v in rules.items()},
           "uniques": uniques, "checks": {t: [(n, check_clause.get(n, "")) for n in ns] for t, ns in checks.items()}},
          open("schema.json", "w"), ensure_ascii=False, indent=0, default=str)
print(len(cols), "tables", len(fks), "fks")
