"""UC-07: Báo cáo đo lường CĐR – xuất BM6 (lớp HP, từng bài KT), BM2/BM3 (CTĐT, Excel + Word BM2), phân công đánh giá PIs; tổng hợp PLO."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..http_utils import attachment
from ..deps import check_section_access, current_user, get_exam_for, require
from ..models import PLOResult, User
from ..schemas import PLONarrativeIn
from ..services import reports_excel, reports_word, results

router = APIRouter(prefix="/api/reports", tags=["UC-07 Báo cáo đo lường CĐR"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.get("/class-sections/{cs_id}/bm6.xlsx")
def bm6(cs_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    cs = check_section_access(db, u, cs_id)
    return Response(reports_excel.build_bm6(db, cs_id), media_type=XLSX,
                    headers=attachment(f"BM6_{cs.section_code}.xlsx"))


@router.get("/exams/{exam_id}/bm6c.xlsx")
def bm6_exam(exam_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """BM6c riêng cho một bài kiểm tra – minh chứng từng CLO bài KT đo (kèm MSSV, họ tên)."""
    e = get_exam_for(db, u, exam_id)
    if e.status != "Analyzed":
        raise HTTPException(409, "Bài kiểm tra chưa được phân tích – đồng bộ/nhập phiếu và phân tích trước khi xuất BM6c")
    cs = check_section_access(db, u, e.class_section_id)
    return Response(reports_excel.build_bm6_exam(db, exam_id), media_type=XLSX,
                    headers=attachment(f"BM6c_{cs.section_code}_{e.exam_title}.xlsx"))


@router.get("/programs/{pid}/bm3.xlsx")
def bm3(pid: int, academic_year: str, _=Depends(require("admin")), db: Session = Depends(get_db)):
    return Response(reports_excel.build_bm3(db, pid, academic_year), media_type=XLSX,
                    headers=attachment(f"BM2_BM3_{academic_year}.xlsx"))


@router.get("/programs/{pid}/bm2.docx")
def bm2_docx(pid: int, academic_year: str, _=Depends(require("admin")), db: Session = Depends(get_db)):
    """BM2 dạng Word như biểu mẫu gốc: BM2a (kế hoạch) + BM2b (báo cáo tổng kết)."""
    return Response(reports_word.build_bm2_docx(db, pid, academic_year), media_type=DOCX,
                    headers=attachment(f"BM2_{academic_year}.docx"))


@router.get("/semesters/{sem_id}/assignments.xlsx")
def assignments_xlsx(sem_id: int, _=Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    """Bảng "Phân công đánh giá PIs" của một học kỳ."""
    name = db.execute(text("SELECT name FROM semesters WHERE id=:s"), {"s": sem_id}).scalar()
    if not name:
        raise HTTPException(404, "Không tìm thấy học kỳ")
    return Response(reports_excel.build_assignments(db, sem_id), media_type=XLSX,
                    headers=attachment(f"Phân công đánh giá PIs {name}.xlsx"))


@router.get("/programs/{pid}/plo-summary")
def plo_summary(pid: int, academic_year: str, _=Depends(current_user), db: Session = Depends(get_db)):
    plos = [dict(r) for r in db.execute(text("""
        SELECT p.id AS plo_id, p.plo_code, p.description, p.target_pct AS plo_target,
               r.n_evaluated, r.n_achieved, r.achieved_pct, r.target_pct, r.is_achieved, r.data_summary, r.analysis,
               r.improvement_actions, r.improvement_results, r.evidence_tools,
               (SELECT COUNT(*) FROM pi_assessment_plans pl JOIN performance_indicators pi ON pi.id=pl.pi_id
                 JOIN semesters s ON s.id=pl.semester_id WHERE pi.plo_id=p.id AND s.academic_year=:y) AS n_plans
        FROM plos p LEFT JOIN plo_results r ON r.plo_id=p.id AND r.academic_year=:y
        WHERE p.program_id=:p ORDER BY p.plo_code"""), {"p": pid, "y": academic_year}).mappings()]
    measured = [x for x in plos if x["n_evaluated"]]
    ok = sum(x["n_achieved"] for x in measured); n = sum(x["n_evaluated"] for x in measured)
    target = float(db.execute(text("SELECT target_pct FROM programs WHERE id=:p"), {"p": pid}).scalar())
    return {"academic_year": academic_year, "plos": plos,
            "program_result": {"n_achieved": ok, "n_evaluated": n, "achieved_pct": round(100 * ok / n, 2) if n else None,
                               "target_pct": target, "is_achieved": bool(n) and 100 * ok / n + 1e-9 >= target}}


@router.post("/programs/{pid}/recompute")
def recompute(pid: int, _=Depends(require("admin")), db: Session = Depends(get_db)):
    results.recompute_pi_plans(db)
    return {"ok": True}


@router.put("/plo-results/{plo_id}/{academic_year}")
def plo_narrative(plo_id: int, academic_year: str, body: PLONarrativeIn, _=Depends(require("admin")), db: Session = Depends(get_db)):
    r = db.get(PLOResult, (plo_id, academic_year))
    if not r:
        raise HTTPException(404, "CĐR chưa có kết quả đo trong năm học này")
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    db.commit()
    return {"ok": True}
