@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0backend"
echo Luu y: XAMPP (MySQL/MariaDB) phai dang chay. Tai khoan lay tu backend\cau_hinh.env
echo.
echo [1/4] Tao CSDL assessment_db (39 bang) + du lieu tham chieu BM2, phan cong PIs...
"..\.venv\Scripts\python.exe" -m app.cli init-db || goto :loi
echo [2/4] Tao du lieu minh hoa (tai khoan, mon DBMS330284, CLO, 30 cau hoi, lop 40 SV)...
"..\.venv\Scripts\python.exe" -m app.cli seed-demo || goto :loi
echo [3/4] Mo phong bai thi giay 2 ma de va phan tich...
"..\.venv\Scripts\python.exe" -m app.cli simulate-paper || goto :loi
echo [4/4] Cai cau noi doc CSDL Moodle (moodle_db)...
"..\.venv\Scripts\python.exe" -m app.cli install-bridge || goto :loi
echo.
echo Xong. Tiep theo chay 3_CAI_GIAO_DIEN_MOODLE.bat
pause
exit /b 0
:loi
echo.
echo *** Co loi. Kiem tra XAMPP da bat MySQL va mat khau trong backend\cau_hinh.env ***
pause
exit /b 1
