"""UC-07: Báo cáo đo lường CĐR – xuất BM6 (môn học) và BM2/BM3 (CTĐT); tổng hợp PLO."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import check_section_access, current_user, require
from ..models import PLOResult, User
from ..schemas import PLONarrativeIn
from ..services import reports_excel, results

router = APIRouter(prefix="/api/reports", tags=["UC-07 Báo cáo đo lường CĐR"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/class-sections/{cs_id}/bm6.xlsx")
def bm6(cs_id: int, u: User = Depends(require("admin", "lecturer")), db: Session = Depends(get_db)):
    cs = check_section_access(db, u, cs_id)
    return Response(reports_excel.build_bm6(db, cs_id), media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="BM6_{cs.section_code}.xlsx"'})


@router.get("/programs/{pid}/bm3.xlsx")
def bm3(pid: int, academic_year: str, _=Depends(require("admin")), db: Session = Depends(get_db)):
    return Response(reports_excel.build_bm3(db, pid, academic_year), media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="BM2_BM3_{academic_year}.xlsx"'})


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
