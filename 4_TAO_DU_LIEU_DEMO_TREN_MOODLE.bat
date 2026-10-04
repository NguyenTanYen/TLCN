@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
call 0_CAU_HINH.bat
if not defined MOODLE_DIR goto :thieu_duong_dan
if not defined PHP_BIN goto :thieu_duong_dan
if not exist "%MOODLE_DIR%\config.php" goto :thieu_duong_dan
echo ================================================================
echo  TAO DU LIEU DEMO THAT TREN MOODLE (tuy chon)
echo  - Tao khoa hoc DBMS330284_01, 40 tai khoan SV (ten = MSSV, mat khau Sv@123456)
echo    va GV gv.son (Gv@123456) tren Moodle cua ban.
echo  - Nhap de thi Moodle XML do he thong xuat, tao Quiz xao tron phuong an,
echo    cho 38 SV lam bai bang API cua Moodle (Moodle tu cham diem).
echo  - Dung lai CSDL assessment_db, dong bo va doi chieu voi diem cua Moodle.
echo  - Bai thi GIAY: tao Offline Quiz 2 ma de tren Moodle, to phieu tra loi cho 38 SV va dua anh quet
echo    vao Moodle - MOODLE nhan dien phieu va cham diem; he thong keo ket qua ve phan tich.
echo  - Cong bo ket qua: gui ket qua phan tich len Moodle cho SV xem (Web Service).
echo ================================================================
cd backend
"..\.venv\Scripts\python.exe" -c "import pymupdf" 2>nul || "..\.venv\Scripts\python.exe" -m pip install -q pymupdf
"..\.venv\Scripts\python.exe" "..\tools\moodle_e2e\run_real_moodle_e2e.py" "%MOODLE_DIR%" || (echo *** Co loi khi tao du lieu demo - xem thong bao o tren. & pause & exit /b 1)
rem Bat che do minh hoa: trang dang nhap hien nut dien nhanh tai khoan demo (khoi dong lai buoc 5 de ap dung)
findstr /b /c:"DEMO_MODE" cau_hinh.env >nul 2>&1 || (echo.>>cau_hinh.env & echo DEMO_MODE=true>>cau_hinh.env)
pause
exit /b 0

:thieu_duong_dan
echo *** Chua xac dinh duoc thu muc Moodle 4.5 / php.exe (MOODLE_DIR=%MOODLE_DIR%, PHP_BIN=%PHP_BIN%).
echo *** Tao tep 0_CAU_HINH_MAY.bat (chep tu 0_CAU_HINH_MAY.example.bat) va khai bao duong dan dung.
pause
exit /b 1
