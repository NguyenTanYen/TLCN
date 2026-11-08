@echo off
rem Tu do XAMPP, PHP, Moodle 4.5; goi tu cac tep khac. Ghi de bang scripts\cau_hinh_may.bat (mau: cau_hinh_may.example.bat).
set "ROOT=%~dp0.."
if exist "%~dp0cau_hinh_may.bat" call "%~dp0cau_hinh_may.bat"
if not defined APP_PORT set "APP_PORT=8000"

set "_REG="
for /f "tokens=2,*" %%a in ('reg query "HKLM\SOFTWARE\xampp" /v Install_Dir 2^>nul') do if "%%a"=="REG_SZ" set "_REG=%%b"
if not defined _REG for /f "tokens=2,*" %%a in ('reg query "HKLM\SOFTWARE\WOW6432Node\xampp" /v Install_Dir 2^>nul') do if "%%a"=="REG_SZ" set "_REG=%%b"
if defined XAMPP_DIR if not defined MOODLE_DIR call :thu_xampp "%XAMPP_DIR%"
if not defined MOODLE_DIR for %%d in ("%_REG%" "%~d0\xampp" "C:\xampp" "D:\xampp" "E:\xampp" "F:\xampp") do if not defined MOODLE_DIR if not "%%~d"=="" call :thu_xampp "%%~d"
if not defined XAMPP_DIR for %%d in ("%_REG%" "%~d0\xampp" "C:\xampp" "D:\xampp" "E:\xampp" "F:\xampp") do if not defined XAMPP_DIR if not "%%~d"=="" if exist "%%~d\php\php.exe" set "XAMPP_DIR=%%~d"
set "_REG="

if not defined PHP_BIN if defined XAMPP_DIR if exist "%XAMPP_DIR%\php\php.exe" set "PHP_BIN=%XAMPP_DIR%\php\php.exe"
if not defined PHP_BIN for /f "delims=" %%p in ('where php 2^>nul') do if not defined PHP_BIN set "PHP_BIN=%%p"
if not defined PHP_BIN echo [!] Khong thay php.exe: cai XAMPP hoac dat PHP_BIN trong cau_hinh_may.bat
if not defined MOODLE_DIR echo [!] Khong thay Moodle 4.5: dat MOODLE_DIR trong cau_hinh_may.bat

if not exist "%ROOT%\backend\cau_hinh.env" copy /y "%ROOT%\backend\cau_hinh.env.example" "%ROOT%\backend\cau_hinh.env" >nul
goto :eof

:thu_xampp
if not exist "%~1\php\php.exe" goto :eof
for %%m in (moodle45 moodle) do if not defined MOODLE_DIR call :thu_moodle "%~1\htdocs\%%m"
if defined MOODLE_DIR if not defined XAMPP_DIR set "XAMPP_DIR=%~1"
goto :eof

:thu_moodle
if not exist "%~1\version.php" goto :eof
if not exist "%~1\config.php" goto :eof
set "_MV="
for /f "tokens=2 delims==;" %%v in ('findstr /b /c:"$version " "%~1\version.php"') do if not defined _MV set "_MV=%%v"
if defined _MV for /f "tokens=1 delims=. " %%n in ("%_MV%") do set "_MV=%%n"
if defined _MV if %_MV% GEQ 2024100700 set "MOODLE_DIR=%~1"
set "_MV="
goto :eof
