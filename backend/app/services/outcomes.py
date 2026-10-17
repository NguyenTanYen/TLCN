"""Liên kết CĐR: CLO → PI → PLO (góp ý F2a – quản lý thêm một mức trên CLO).

clo_pi_mapping là ánh xạ gốc do Bộ môn khai báo; clo_plo_mapping (ma trận CLO – PLO của các báo cáo cũ) được suy ra:
với mỗi PLO, mức cao nhất (I < R < M) trong các PI của PLO đó mà CLO đóng góp.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import CLO, CLOPLOMapping

LEVEL_ORDER = {"I": 1, "R": 2, "M": 3}   # Giới thiệu < Củng cố < Thành thạo


def sync_clo_plo(db: Session, clo: CLO) -> None:
    """Ghi lại clo_plo_mapping của một CLO theo các PI mà CLO đóng góp."""
    best: dict[int, str] = {}
    for link in clo.pi_links:
        plo_id = link.pi.plo_id
        if plo_id not in best or LEVEL_ORDER[link.level] > LEVEL_ORDER[best[plo_id]]:
            best[plo_id] = link.level
    db.query(CLOPLOMapping).filter_by(clo_id=clo.id).delete()
    db.flush()
    for plo_id, level in best.items():
        db.add(CLOPLOMapping(clo_id=clo.id, plo_id=plo_id, level=level))


def set_clo_pis(db: Session, clo: CLO, maps: list[tuple[int, str]]) -> None:
    """Thay toàn bộ CLO → PI của một CLO rồi suy ra lại CLO → PLO. PI phải thuộc CTĐT có học phần này
    (học phần chưa gán CTĐT thì chọn được PI của mọi CTĐT). Lỗi dữ liệu → ValueError (router trả 422)."""
    from ..models import CLOPIMapping, PerformanceIndicator
    ids = [pi_id for pi_id, _ in maps]
    if len(ids) != len(set(ids)):
        raise ValueError("Mỗi PI chỉ được ánh xạ một lần")
    if any(lv not in LEVEL_ORDER for _, lv in maps):
        raise ValueError("Mức đóng góp CLO–PI phải là I, R hoặc M")
    pis = {p.id: p for p in db.query(PerformanceIndicator).filter(PerformanceIndicator.id.in_(ids)).all()} if ids else {}
    allowed = {r[0] for r in db.execute(text("SELECT program_id FROM program_courses WHERE course_id = :c"), {"c": clo.course_id})}
    for pi_id in ids:
        pi = pis.get(pi_id)
        if not pi:
            raise ValueError(f"PI {pi_id} không tồn tại")
        if allowed and pi.plo.program_id not in allowed:
            raise ValueError(f"PLO {pi.plo.plo_code} – {pi.pi_code} không thuộc CTĐT có học phần này")
    clo.pi_links.clear()
    db.flush()
    for pi_id, lv in maps:
        clo.pi_links.append(CLOPIMapping(pi_id=pi_id, level=lv, pi=pis[pi_id]))
    db.flush()
    sync_clo_plo(db, clo)


BACKFILL_SQL = """
INSERT IGNORE INTO clo_pi_mapping (clo_id, pi_id, level)
SELECT m.clo_id,
       COALESCE((SELECT MIN(pl.pi_id) FROM pi_plan_clos pc JOIN pi_assessment_plans pl ON pl.id = pc.plan_id
                 JOIN performance_indicators pi ON pi.id = pl.pi_id WHERE pc.clo_id = m.clo_id AND pi.plo_id = m.plo_id),
                (SELECT MIN(pi.id) FROM performance_indicators pi WHERE pi.plo_id = m.plo_id)),
       m.level
FROM clo_plo_mapping m JOIN clos c ON c.id = m.clo_id
WHERE NOT EXISTS (SELECT 1 FROM clo_pi_mapping x WHERE x.clo_id = m.clo_id)
  AND EXISTS (SELECT 1 FROM performance_indicators pi WHERE pi.plo_id = m.plo_id)
  AND (:c IS NULL OR c.course_id = :c)
"""


def backfill_clo_pi(conn, course_id: int | None = None) -> int:
    """Dữ liệu cũ chỉ có CLO → PLO: sinh CLO → PI cho các CLO chưa có, mỗi cặp CLO–PLO gắn với PI mà kế hoạch đo PI
    lấy CLO này làm minh chứng, nếu không có thì PI đầu tiên của PLO (mức giữ nguyên, nên ma trận CLO – PLO không đổi)."""
    return conn.execute(text(BACKFILL_SQL), {"c": course_id}).rowcount
