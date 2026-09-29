@echo off
chcp 65001 >nul
cd /d "%~dp0"
call 0_CAU_HINH.bat
echo [1/5] Chep giao dien UTE LMS va plugin ket noi local_clo vao Moodle...
xcopy /E /I /Y "moodle\theme\ute" "%MOODLE_DIR%\theme\ute" >nul || goto :loi
xcopy /E /I /Y "moodle\local\clo" "%MOODLE_DIR%\local\clo" >nul || goto :loi
echo [2/5] Cai dat / nang cap plugin (admin\cli\upgrade.php)...
"%PHP_BIN%" -d max_input_vars=5000 "%MOODLE_DIR%\admin\cli\upgrade.php" --non-interactive || goto :loi
echo [3/5] Chon giao dien UTE LMS lam giao dien mac dinh...
"%PHP_BIN%" "%MOODLE_DIR%\admin\cli\cfg.php" --name=theme --set=ute || goto :loi
echo [4/5] Bat Web Service, tao token, khoa SSO va ghi vao backend\cau_hinh.env...
"%PHP_BIN%" "%MOODLE_DIR%\local\clo\cli\setup.php" --appurl=http://localhost:%APP_PORT% --envfile="%~dp0backend\cau_hinh.env" || goto :loi
echo [5/5] Xoa bo nho dem Moodle...
"%PHP_BIN%" "%MOODLE_DIR%\admin\cli\purge_caches.php"
echo.
echo Xong. Neu he thong (5_CHAY_HE_THONG.bat) dang chay, hay dong cua so do va chay lai de nhan cau hinh moi.
pause
exit /b 0
:loi
echo *** Co loi - kiem tra duong dan trong 0_CAU_HINH.bat ***
pause
exit /b 1
