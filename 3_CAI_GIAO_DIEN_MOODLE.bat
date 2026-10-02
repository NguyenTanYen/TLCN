@echo off
chcp 65001 >nul
cd /d "%~dp0"
call 0_CAU_HINH.bat
echo [1/6] Chep giao dien UTE LMS, plugin ket noi local_clo va plugin cham bai giay Offline Quiz vao Moodle...
xcopy /E /I /Y "moodle\theme\ute" "%MOODLE_DIR%\theme\ute" >nul || goto :loi
xcopy /E /I /Y "moodle\local\clo" "%MOODLE_DIR%\local\clo" >nul || goto :loi
if not exist "moodle\mod\offlinequiz\version.php" powershell -NoProfile -Command "Expand-Archive -Force 'moodle\mod\offlinequiz_v4.5.4.zip' 'moodle\mod'" || goto :loi
xcopy /E /I /Y "moodle\mod\offlinequiz" "%MOODLE_DIR%\mod\offlinequiz" >nul || goto :loi
echo [2/6] Cai dat / nang cap plugin (admin\cli\upgrade.php)...
"%PHP_BIN%" -d max_input_vars=5000 "%MOODLE_DIR%\admin\cli\upgrade.php" --non-interactive || goto :loi
echo [3/6] Chon giao dien UTE LMS lam giao dien mac dinh...
"%PHP_BIN%" "%MOODLE_DIR%\admin\cli\cfg.php" --name=theme --set=ute || goto :loi
echo [4/6] Bat Web Service, tao token, khoa SSO, cau hinh Offline Quiz (MSSV 8 so, nhan tieng Viet) va ghi backend\cau_hinh.env...
"%PHP_BIN%" "%MOODLE_DIR%\local\clo\cli\setup.php" --appurl=http://localhost:%APP_PORT% --envfile="%~dp0backend\cau_hinh.env" || goto :loi
echo [5/6] Tao tai khoan CSDL dac quyen toi thieu cho he thong (chi DOC CSDL Moodle)...
"%~dp0.venv\Scripts\python.exe" "%~dp0tools\tao_tai_khoan_csdl.py" "%~dp0backend\cau_hinh.env" || goto :loi
echo [6/6] Xoa bo nho dem Moodle...
"%PHP_BIN%" "%MOODLE_DIR%\admin\cli\purge_caches.php"
echo.
echo Xong. Neu he thong (5_CHAY_HE_THONG.bat) dang chay, hay dong cua so do va chay lai de nhan cau hinh moi.
pause
exit /b 0
:loi
echo *** Co loi - kiem tra duong dan trong 0_CAU_HINH.bat ***
pause
exit /b 1
