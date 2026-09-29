"""Sinh ERD (Graphviz) và từ điển dữ liệu trực tiếp từ information_schema của assessment_db."""
import json, subprocess
import pymysql

GROUPS = {
 "A. Người dùng & tổ chức": ["users", "lecturers", "students", "semesters"],
 "B. CTĐT & CĐR CTĐT": ["programs", "plos", "plo_measurement_plans", "performance_indicators", "program_courses", "pi_courses"],
 "C. Học phần & CĐR môn học": ["courses", "course_outlines", "bloom_levels", "clos", "clo_plo_mapping"],
 "D. Kế hoạch đo lường": ["clo_assessment_plans", "pi_assessment_plans", "pi_plan_clos", "assessment_assignments"],
 "E. Lớp HP & ngân hàng câu hỏi": ["class_sections", "enrollments", "question_bank", "question_options", "question_clo_mapping"],
 "F. Đề thi & mã đề": ["exams", "exam_questions", "exam_versions", "exam_version_questions", "exam_version_options"],
 "G. Kết quả & báo cáo": ["exam_attempts", "item_level_results", "item_statistics", "attempt_clo_results", "clo_results",
                          "pi_results", "plo_results", "personalized_learning_paths", "learning_path_items", "sync_runs"],
}
COLORS = {"A": "#FDF3E1", "B": "#E8F1FB", "C": "#EAF6EA", "D": "#F3ECFA", "E": "#FFF7D6", "F": "#FDE9E7", "G": "#E6F4F4"}
c = pymysql.connect(host="127.0.0.1", user="tlcn", password="tlcn123", database="information_schema", charset="utf8mb4")
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


def node(t, full=True, stub=False):
    g = group_of[t][0]
    color = "#EEEEEE" if stub else COLORS[g]
    rows = [f'<tr><td bgcolor="{color}" colspan="2"><b>{t}</b></td></tr>']
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
    return f'"{t}" [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="3">{"".join(rows)}</table>>];'


def render(name, tables, full=True, rankdir="LR", clusters=False, extra_attrs=""):
    lines = [f'digraph G {{ rankdir={rankdir}; graph [fontname="DejaVu Sans", nodesep=0.35, ranksep=0.7, dpi=160 {extra_attrs}];',
             'node [shape=plaintext, fontname="DejaVu Sans", fontsize=10]; edge [color="#555555", arrowhead=crow, arrowtail=none, dir=both, arrowsize=0.7];']
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
    lines += [node(t, False, stub=True) for t in sorted(stubs)]
    seen = set()
    for t, col, rt, rc, cn in fks:
        if t in tables and (rt in tables or rt in stubs):
            key = (t, rt, col)
            if key in seen:
                continue
            seen.add(key)
            if full and rt in tables:
                lines.append(f'"{rt}":"{rc}" -> "{t}":"{col}" [arrowtail=tee];')
            else:
                lines.append(f'"{rt}" -> "{t}" [arrowtail=tee];')
    lines.append("}")
    src = f"fig/{name}.dot"
    open(src, "w").write("\n".join(lines))
    subprocess.run(["dot", "-Tpng", src, "-o", f"fig/{name}.png"], check=True)


render("erd_overview", all_tables, full=False, clusters=True, rankdir="TB", extra_attrs=", concentrate=true, splines=spline, ranksep=0.9, nodesep=0.25")
for i, (g, ts) in enumerate(GROUPS.items()):
    render(f"erd_{g[0]}", ts, full=True, rankdir="LR")
json.dump({"groups": GROUPS, "cols": cols, "fks": fks, "rules": {f"{k[0]}|{k[1]}": v for k, v in rules.items()},
           "uniques": uniques, "checks": {t: [(n, check_clause.get(n, "")) for n in ns] for t, ns in checks.items()}},
          open("schema.json", "w"), ensure_ascii=False, indent=0, default=str)
print(len(cols), "tables", len(fks), "fks")
