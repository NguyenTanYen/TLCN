"""Xuất đề thi sang định dạng Moodle XML (UC-02).

Mỗi câu hỏi mang <idnumber>QB-{id}</idnumber>; các <answer> theo thứ tự position tăng dần
để cầu nối CSDL khớp được đáp án gốc khi đồng bộ (Reverse Shuffle).
"""
from xml.sax.saxutils import escape

from ..models import Exam


def _cdata(s: str) -> str:
    return "<![CDATA[" + s.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def exam_to_moodle_xml(exam: Exam, category: str | None = None) -> str:
    cat = category or f"$course$/top/{exam.exam_title}"
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<quiz>",
             '  <question type="category">', f"    <category><text>{escape(cat)}</text></category>", "  </question>"]
    for eq in exam.questions:
        q = eq.question
        parts += [
            '  <question type="multichoice">',
            f"    <name><text>QB-{q.id}</text></name>",
            f'    <questiontext format="html"><text>{_cdata(q.content)}</text></questiontext>',
            '    <generalfeedback format="html"><text></text></generalfeedback>',
            f"    <defaultgrade>{float(eq.points):.2f}</defaultgrade>",
            "    <penalty>0</penalty>", "    <hidden>0</hidden>",
            f"    <idnumber>QB-{q.id}</idnumber>",
            "    <single>true</single>", "    <shuffleanswers>1</shuffleanswers>",
            "    <answernumbering>abc</answernumbering>",
        ]
        for opt in sorted(q.options, key=lambda o: o.position):
            frac = 100 if opt.is_correct else 0
            parts += [f'    <answer fraction="{frac}" format="html">', f"      <text>{_cdata(opt.content)}</text>",
                      '      <feedback format="html"><text></text></feedback>', "    </answer>"]
        parts.append("  </question>")
    parts.append("</quiz>")
    return "\n".join(parts) + "\n"
