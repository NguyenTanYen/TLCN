"""Trang Tổng quan: danh sách "việc cần làm" theo vai trò, mỗi việc kèm đường dẫn đến đúng trang để làm."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require
from ..models import User

router = APIRouter(prefix="/api", tags=["Tổng quan"])


def _rows(db, sql, **p):
    return [dict(r) for r in db.execute(text(sql), p).mappings()]


def _lecturer_todos(db, lid):
    todos = []
    for e in _rows(db, """SELECT e.id, e.exam_title, e.exam_type, e.status, e.publish_flag, e.moodle_quiz_id, e.moodle_offlinequiz_id,
                                 cs.id AS cs_id, cs.section_code
                          FROM exams e JOIN class_sections cs ON cs.id=e.class_section_id
                          WHERE cs.lecturer_id=:l ORDER BY cs.section_code, e.id""", l=lid):
        where = f"{e['section_code']} · {e['exam_title']}"
        if e["status"] == "Draft" and e["exam_type"] == "online" and not e["moodle_quiz_id"]:
            todos.append({"kind": "exam", "step": 1, "title": "Tạo bài trắc nghiệm trên Moodle", "where": where, "to": f"/exams/{e['id']}"})
        elif e["status"] in ("Draft", "Published", "Synced") and (e["moodle_quiz_id"] or e["moodle_offlinequiz_id"] or e["exam_type"] != "online"):
            todos.append({"kind": "exam", "step": 2, "title": "Lấy bài làm / nhập điểm và phân tích", "where": where, "to": f"/exams/{e['id']}"})
        elif e["status"] == "Analyzed" and not e["publish_flag"]:
            todos.append({"kind": "exam", "step": 3, "title": "Công bố kết quả cho sinh viên", "where": where, "to": f"/exams/{e['id']}"})
    for r in _rows(db, """SELECT cs.id AS cs_id, cs.section_code, c.clo_code FROM clo_results r JOIN class_sections cs ON cs.id=r.class_section_id
                          JOIN clos c ON c.id=r.clo_id
                          WHERE cs.lecturer_id=:l AND r.is_achieved=0
                            AND NOT EXISTS (SELECT 1 FROM improvement_actions a WHERE a.class_section_id=cs.id AND a.clo_id=r.clo_id AND a.status<>'verified')
                          ORDER BY cs.section_code, c.clo_code""", l=lid):
        todos.append({"kind": "clo", "step": 4, "title": f"{r['clo_code']} chưa đạt chỉ tiêu: ghi hành động cải tiến", "where": r["section_code"],
                      "to": f"/sections/{r['cs_id']}/clo?tab=bm6b"})
    for a in _rows(db, """SELECT cs.id AS cs_id, cs.section_code, a.description FROM improvement_actions a JOIN class_sections cs ON cs.id=a.class_section_id
                          WHERE cs.lecturer_id=:l AND a.status IN ('open','doing') AND a.due_date IS NOT NULL AND a.due_date < CURDATE()""", l=lid):
        todos.append({"kind": "overdue", "step": 5, "title": f"Quá hạn: {a['description'][:70]}", "where": a["section_code"], "to": f"/sections/{a['cs_id']}/clo?tab=bm6b"})
    todos.sort(key=lambda t: t["step"])
    return todos


def _count(db, sql, **p):
    return int(db.execute(text(sql), p).scalar() or 0)


@router.get("/dashboard")
def dashboard(u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    if u.role == "lecturer":
        lid = u.lecturer.id if u.lecturer else -1
        todos = _lecturer_todos(db, lid)
        stats = {"sections": _count(db, "SELECT COUNT(*) FROM class_sections WHERE lecturer_id=:l", l=lid),
                 "exams": _count(db, "SELECT COUNT(*) FROM exams e JOIN class_sections cs ON cs.id=e.class_section_id WHERE cs.lecturer_id=:l", l=lid),
                 "analyzed": _count(db, "SELECT COUNT(*) FROM exams e JOIN class_sections cs ON cs.id=e.class_section_id WHERE cs.lecturer_id=:l AND e.status='Analyzed'", l=lid),
                 "published": _count(db, "SELECT COUNT(*) FROM exams e JOIN class_sections cs ON cs.id=e.class_section_id WHERE cs.lecturer_id=:l AND e.publish_flag=1", l=lid)}
        return {"role": "lecturer", "todos": todos, "stats": stats}
    checks = []

    def add(key, title, hint, bad, to, total=None):
        checks.append({"key": key, "title": title, "hint": hint, "pending": bad, "done": bad == 0, "to": to, "total": total})
    add("program", "Có chương trình đào tạo với PLO và PI", "Khai báo CTĐT, chuẩn đầu ra (PLO) và chỉ báo đo (PI).",
        _count(db, "SELECT COUNT(*) FROM programs p WHERE NOT EXISTS (SELECT 1 FROM plos x WHERE x.program_id=p.id)"), "/programs",
        _count(db, "SELECT COUNT(*) FROM programs"))
    add("clo", "Mỗi học phần có CLO gắn với PI", "Học phần chưa có CLO thì không đo được chuẩn đầu ra.",
        _count(db, """SELECT COUNT(*) FROM courses c WHERE EXISTS (SELECT 1 FROM program_courses pc WHERE pc.course_id=c.id)
                      AND NOT EXISTS (SELECT 1 FROM clo_pi_mapping m JOIN clos k ON k.id=m.clo_id WHERE k.course_id=c.id)"""), "/courses",
        _count(db, "SELECT COUNT(DISTINCT course_id) FROM program_courses"))
    add("plan", "Mỗi PI có kế hoạch đo", "Chọn môn và học kỳ lấy minh chứng cho từng PI.",
        _count(db, "SELECT COUNT(*) FROM performance_indicators pi WHERE NOT EXISTS (SELECT 1 FROM pi_assessment_plans p WHERE p.pi_id=pi.id)"), "/pi-plans",
        _count(db, "SELECT COUNT(*) FROM performance_indicators"))
    add("section", "Lớp học phần đã gắn khóa học Moodle", "Lớp chưa gắn Moodle thì sinh viên chưa xem được kết quả.",
        _count(db, "SELECT COUNT(*) FROM class_sections WHERE moodle_course_id IS NULL"), "/sections", _count(db, "SELECT COUNT(*) FROM class_sections"))
    add("publish", "Bài đã phân tích được công bố cho sinh viên", "Giảng viên bấm Công bố sau khi kiểm tra kết quả.",
        _count(db, "SELECT COUNT(*) FROM exams WHERE status='Analyzed' AND publish_flag=0"), "/sections", _count(db, "SELECT COUNT(*) FROM exams WHERE status='Analyzed'"))
    add("loop", "Mọi CLO chưa đạt đều có hành động cải tiến", "Đóng vòng đánh giá: ghi hành động, người phụ trách, hạn.",
        _count(db, """SELECT COUNT(*) FROM clo_results r WHERE r.is_achieved=0 AND NOT EXISTS
                      (SELECT 1 FROM improvement_actions a WHERE a.class_section_id=r.class_section_id AND a.clo_id=r.clo_id AND a.status<>'verified')"""), "/sections",
        _count(db, "SELECT COUNT(*) FROM clo_results WHERE is_achieved=0"))
    return {"role": "admin", "checks": checks,
            "stats": {"programs": _count(db, "SELECT COUNT(*) FROM programs"), "courses": _count(db, "SELECT COUNT(*) FROM courses"),
                      "sections": _count(db, "SELECT COUNT(*) FROM class_sections"), "analyzed": _count(db, "SELECT COUNT(*) FROM exams WHERE status='Analyzed'")}}
