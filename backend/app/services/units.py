from sqlalchemy import text

FACULTY_UNIT = "Khoa Công nghệ Thông tin"
OTHER_UNIT = "Đơn vị khác (khối kiến thức đại cương)"

PREFIX_UNITS = {
    "LLCT": "Khoa Lý luận chính trị",
    "GELA": "Khoa Lý luận chính trị",
    "PHED": "Khoa Giáo dục thể chất",
    "ENCO": "Khoa Ngoại ngữ",
    "ENGL": "Khoa Ngoại ngữ",
    "MATH": "Khoa Khoa học ứng dụng",
    "PHYS": "Khoa Khoa học ứng dụng",
    "EEEN": "Khoa Điện – Điện tử",
    "PRBE": "Khoa Điện – Điện tử",
    "DISY": "Khoa Điện – Điện tử",
}

GENERAL_ELECTIVE_PREFIX = "Khối tự chọn Khoa học xã hội nhân văn"


def classify_courses(conn) -> int:
    n = 0
    for prefix, unit in PREFIX_UNITS.items():
        n += conn.execute(text("UPDATE courses SET managing_unit=:u WHERE managing_unit=:f AND course_code LIKE :p"),
                          {"u": unit, "f": FACULTY_UNIT, "p": prefix + "%"}).rowcount
    n += conn.execute(text("""UPDATE courses c SET c.managing_unit=:o WHERE c.managing_unit=:f
                              AND EXISTS (SELECT 1 FROM program_courses pc WHERE pc.course_id=c.id AND pc.knowledge_block LIKE :b)
                              AND NOT EXISTS (SELECT 1 FROM program_courses pc WHERE pc.course_id=c.id
                                              AND (pc.knowledge_block IS NULL OR pc.knowledge_block NOT LIKE :b))"""),
                      {"o": OTHER_UNIT, "f": FACULTY_UNIT, "b": GENERAL_ELECTIVE_PREFIX + "%"}).rowcount
    return n
