@echo off
chcp 65001 >nul
cd /d "%~dp0.."
call 0_CAU_HINH.bat
if not defined PHP_BIN (echo *** Khong tim thay php.exe - khai bao PHP_BIN trong 0_CAU_HINH_MAY.bat & pause & exit /b 1)
if not defined MOODLE_DIR (echo *** Chua xac dinh duoc thu muc Moodle 4.5 - khai bao MOODLE_DIR trong 0_CAU_HINH_MAY.bat & pause & exit /b 1)
echo Kiem tra nut "Phan tich CDR" (SSO) tu Moodle sang he thong...
"%PHP_BIN%" "%MOODLE_DIR%\local\clo\cli\testsso.php" --username=gv.son
pause
