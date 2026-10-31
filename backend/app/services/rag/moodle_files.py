"""Liệt kê tệp trong khóa học Moodle của một lớp học phần – để GV chọn tệp nào là HỌC LIỆU.

Đọc trực tiếp CSDL Moodle (cùng máy chủ MySQL, như services/moodle.py): hoạt động File (mod_resource) và Thư mục
(mod_folder) cùng các tệp của chúng (mdl_files, filearea 'content').
  - chỉ tài nguyên SV ĐANG XEM ĐƯỢC: hoạt động và chủ đề không ẩn, không đang bị xóa, và điều kiện giới hạn truy cập
    (Restrict access) đã mở – đọc cây điều kiện JSON ở Python (available_now): mốc ngày đã qua thì mở (bài giảng mở
    khóa theo tuần), điều kiện theo từng SV thì coi là chưa mở. Tệp SV đã xem được thì gợi ý trỏ tới nó không làm lộ gì thêm; đề thi trên Moodle là Quiz / Offline Quiz
    (câu hỏi trong ngân hàng, không phải tệp) nên không bao giờ nằm trong danh sách này;
  - kèm liên kết pluginfile để SV mở đúng trang (#page=N) bằng phiên đăng nhập Moodle của mình;
  - hiện mới nạp được PDF (supported, theo mimetype HOẶC đuôi .pdf) – Word/PowerPoint cần GV xuất PDF; nội dung thật sự
    có phải PDF không được kiểm tra lại khi tải tệp về (bước nạp).
"""
from __future__ import annotations

import json
import time
from urllib.parse import quote

from sqlalchemy import text
from sqlalchemy.orm import Session

from ...config import settings
from ..moodle import _has_table, _t

SUPPORTED_MIME = {"application/pdf"}
SUPPORTED_EXT = (".pdf",)   # Moodle cấu hình MIME không chuẩn có thể gán PDF thành application/octet-stream → xét cả đuôi tệp


def _condition_open(node: dict, now: float) -> bool:
    """Một nút trong cây điều kiện "Giới hạn truy cập" (Restrict access) của Moodle đã mở với MỌI SV chưa.
    Nhóm: {"op": "&" | "|" | "!&" | "!|", "c": [...]}; điều kiện ngày: {"type": "date", "d": ">=" (mở từ) | "<" (đến
    trước), "t": timestamp}. Điều kiện phụ thuộc từng SV (điểm, hoàn thành hoạt động, nhóm, hồ sơ...) không xét được cho
    cả lớp → coi là CHƯA mở (thà bỏ sót còn hơn gợi ý tài liệu SV chưa được xem, VD đáp án)."""
    if "c" in node:
        op = node.get("op", "&")
        parts = [_condition_open(c, now) for c in node.get("c") or []]
        if not parts:
            return True                                    # nhóm rỗng (đặt rồi xóa hết điều kiện) = không giới hạn
        if op == "&":
            return all(parts)
        if op == "|":
            return any(parts)
        return False                                       # "!&" / "!|": phủ định – không đánh giá an toàn được
    if node.get("type") == "date":
        t = node.get("t", 0)
        return now >= t if node.get("d") == ">=" else now < t
    return False


def available_now(availability: str | None, now: float | None = None) -> bool:
    """Tệp / chủ đề có điều kiện truy cập đã mở chưa (Moodle lưu NULL khi không giới hạn). Bài giảng "mở khóa theo
    tuần" đã qua mốc ngày → mở; đáp án "chỉ mở sau ngày thi" chưa tới ngày → chưa mở."""
    if not availability or not availability.strip():
        return True
    try:
        tree = json.loads(availability)
    except ValueError:
        return False                                       # JSON hỏng: coi là chưa mở
    return _condition_open(tree, time.time() if now is None else now)


def supported(mimetype: str, filename: str) -> bool:
    return mimetype in SUPPORTED_MIME or filename.lower().endswith(SUPPORTED_EXT)


def file_url(contextid: int, modname: str, revision: int, filepath: str, filename: str) -> str:
    """Liên kết pluginfile của Moodle: tệp của hoạt động File nằm ở gốc (Moodle bỏ đường dẫn con), tệp trong Thư mục
    giữ đường dẫn con."""
    path = "/" if modname == "resource" else filepath
    rel = f"/pluginfile.php/{contextid}/mod_{modname}/content/{revision}{quote(path)}{quote(filename)}"
    return settings.moodle_url.rstrip("/") + rel


def available() -> bool:
    return all(_has_table(t) for t in ("course_modules", "modules", "files", "resource", "folder"))


def list_course_files(db: Session, moodle_course_id: int) -> list[dict]:
    if not available():
        return []
    rows = db.execute(text(f"""
        SELECT cm.id AS cmid, m.name AS modname, COALESCE(r.name, fo.name) AS activity,
               cs.section AS section_no, cs.name AS section_name,
               f.contextid, f.filepath, f.filename, f.mimetype, f.filesize, f.contenthash, f.timemodified,
               COALESCE(r.revision, fo.revision, 0) AS revision,
               cm.availability AS cm_availability, cs.availability AS cs_availability
        FROM {_t('course_modules')} cm
        JOIN {_t('modules')} m ON m.id = cm.module AND m.name IN ('resource', 'folder')
        JOIN {_t('context')} cx ON cx.contextlevel = 70 AND cx.instanceid = cm.id
        JOIN {_t('files')} f ON f.contextid = cx.id AND f.component = CONCAT('mod_', m.name)
                             AND f.filearea = 'content' AND f.filename <> '.'
        LEFT JOIN {_t('resource')} r ON m.name = 'resource' AND r.id = cm.instance
        LEFT JOIN {_t('folder')} fo ON m.name = 'folder' AND fo.id = cm.instance
        LEFT JOIN {_t('course_sections')} cs ON cs.id = cm.section
        WHERE cm.course = :c AND cm.visible = 1 AND cm.deletioninprogress = 0 AND COALESCE(cs.visible, 1) = 1
        ORDER BY cs.section, cm.id, f.filepath, f.filename"""), {"c": moodle_course_id}).mappings().all()
    now = time.time()
    rows = [r for r in rows if available_now(r["cm_availability"], now) and available_now(r["cs_availability"], now)]
    return [{"cmid": int(r["cmid"]), "module": r["modname"], "activity": r["activity"],
             "section": r["section_name"] or (f"Chủ đề {r['section_no']}" if r["section_no"] is not None else ""),
             "path": r["filepath"], "file_name": r["filename"], "mimetype": r["mimetype"] or "",
             "file_size": int(r["filesize"]), "content_hash": r["contenthash"], "timemodified": int(r["timemodified"]),
             "url": file_url(int(r["contextid"]), r["modname"], int(r["revision"]), r["filepath"], r["filename"]),
             "supported": supported(r["mimetype"] or "", r["filename"])}
            for r in rows]
