@echo off
rem ====== Cau hinh duong dan (tu do tim, khong can sua) ======
rem Uu tien bien moi truong co san; neu chua co thi tim thu muc XAMPP o o dia chua du an, roi C:, D:, E:, F:.
rem Muon chi dinh tay: set XAMPP_DIR=E:\xampp (hoac MOODLE_DIR, PHP_BIN) truoc khi chay cac tep .bat.
if not defined XAMPP_DIR for %%d in ("%~d0\xampp" "C:\xampp" "D:\xampp" "E:\xampp" "F:\xampp") do if not defined XAMPP_DIR if exist "%%~d\php\php.exe" set "XAMPP_DIR=%%~d"
if not defined XAMPP_DIR set "XAMPP_DIR=C:\xampp"
if not defined MOODLE_DIR set "MOODLE_DIR=%XAMPP_DIR%\htdocs\moodle"
if not defined PHP_BIN set "PHP_BIN=%XAMPP_DIR%\php\php.exe"
if not defined APP_PORT set "APP_PORT=8000"
if not exist "%PHP_BIN%" echo [Canh bao] Khong thay PHP tai "%PHP_BIN%" - dat bien XAMPP_DIR hoac PHP_BIN cho dung.
if not exist "%MOODLE_DIR%\config.php" echo [Canh bao] Khong thay Moodle tai "%MOODLE_DIR%" - dat bien MOODLE_DIR cho dung.
rem Lan dau (vd. vua tai tu GitHub): tao backend\cau_hinh.env tu tep mau
if not exist "%~dp0backend\cau_hinh.env" copy /y "%~dp0backend\cau_hinh.env.mau" "%~dp0backend\cau_hinh.env" >nul
