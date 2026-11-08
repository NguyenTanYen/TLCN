"""Liệt kê tệp trong khóa học Moodle của một lớp học phần – để GV chọn tệp nào là HỌC LIỆU."""
from __future__ import annotations

import json
import time
from urllib.parse import quote

from sqlalchemy import text
from sqlalchemy.orm import Session

from ...config import settings
from ..moodle import _has_table, _t

SUPPORTED_MIME = {"application/pdf"}
SUPPORTED_EXT = (".pdf",)


def _condition_open(node: dict, now: float) -> bool:
    """Một nút trong cây điều kiện "Giới hạn truy cập" (Restrict access) của Moodle đã mở với MỌI SV chưa."""
    if "c" in node:
        op = node.get("op", "&")
        parts = [_condition_open(c, now) for c in node.get("c") or []]
        if not parts:
            return True
        if op == "&":
            return all(parts)
        if op == "|":
            return any(parts)
        return False
    if node.get("type") == "date":
        t = node.get("t", 0)
        return now >= t if node.get("d") == ">=" else now < t
    return False


def available_now(availability: str | None, now: float | None = None) -> bool:
    """Tệp / chủ đề có điều kiện truy cập đã mở chưa (Moodle lưu NULL khi không giới hạn)."""
    if not availability or not availability.strip():
        return True
    try:
        tree = json.loads(availability)
    except ValueError:
        return False
    return _condition_open(tree, time.time() if now is None else now)


def supported(mimetype: str, filename: str) -> bool:
    return mimetype in SUPPORTED_MIME or filename.lower().endswith(SUPPORTED_EXT)


def file_url(contextid: int, modname: str, revision: int, filepath: str, filename: str) -> str:
    """Liên kết pluginfile của Moodle: tệp của hoạt động File nằm ở gốc (Moodle bỏ đường dẫn con), tệp trong Thư mục giữ đường dẫn con."""
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
