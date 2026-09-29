@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
call 0_CAU_HINH.bat
echo ================================================================
echo  TAO DU LIEU DEMO THAT TREN MOODLE (tuy chon)
echo  - Tao khoa hoc DBMS330284_01, 40 tai khoan SV (ten = MSSV, mat khau Sv@123456)
echo    va GV gv.son (Gv@123456) tren Moodle cua ban.
echo  - Nhap de thi Moodle XML do he thong xuat, tao Quiz xao tron phuong an,
echo    cho 38 SV lam bai bang API cua Moodle (Moodle tu cham diem).
echo  - Dung lai CSDL assessment_db, dong bo va doi chieu voi diem cua Moodle.
echo  - Cong bo ket qua: gui ket qua phan tich len Moodle cho SV xem (Web Service).
echo ================================================================
cd backend
set "PHP_BIN=%PHP_BIN%"
"..\.venv\Scripts\python.exe" "..\tools\moodle_e2e\run_real_moodle_e2e.py" "%MOODLE_DIR%"
pause
