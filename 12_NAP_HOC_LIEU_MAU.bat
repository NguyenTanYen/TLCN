@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
echo ================================================================
echo  NAP HOC LIEU MAU + TAO GOI Y DOC (RAG) CHO DU LIEU DEMO
echo  - Nap slide 6 chuong + giao trinh trich vao hoc phan DBMS330284
echo  - Tao goi y "doc trang/slide nao" cho cac bai da phan tich
echo  - Hoi ban co muon day hoc lieu + ket qua len Moodle khong (can Moodle dang chay,
echo    da nang cap plugin local_clo 1.5.0 va bat Web Service).
echo ================================================================
cd backend
"..\.venv\Scripts\python.exe" -c "import pymupdf, pptx, docx" 2>nul || "..\.venv\Scripts\python.exe" -m pip install -q pymupdf python-pptx python-docx
set /p MD=Day len Moodle luon? (y/N): 
if /i "%MD%"=="y" ("..\.venv\Scripts\python.exe" "..\tools\demo\nap_hoc_lieu_mau.py" --moodle) else ("..\.venv\Scripts\python.exe" "..\tools\demo\nap_hoc_lieu_mau.py")
echo.
pause
