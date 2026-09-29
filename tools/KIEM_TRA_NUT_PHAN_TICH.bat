@echo off
chcp 65001 >nul
cd /d "%~dp0.."
call 0_CAU_HINH.bat
echo Kiem tra nut "Phan tich CDR" (SSO) tu Moodle sang he thong...
"%PHP_BIN%" "%MOODLE_DIR%\local\clo\cli\testsso.php" --username=gv.son
pause
