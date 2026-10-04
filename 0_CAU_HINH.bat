@echo off
rem ======================================================================
rem  CAU HINH DUONG DAN - TU DO, dung chung cho moi may (khong can sua tep nay)
rem  Thu tu uu tien:
rem   1. Tep rieng cua may 0_CAU_HINH_MAY.bat (KHONG dua len git; chep tu 0_CAU_HINH_MAY.example.bat roi sua), VD:
rem        set "MOODLE_DIR=E:\TLCN_MoiTruong\web\moodle45"
rem        set "PHP_BIN=E:\hoc\xampp\php\php.exe"
rem        set "APP_PORT=8000"
rem   2. Bien moi truong co san (XAMPP_DIR, MOODLE_DIR, PHP_BIN, APP_PORT)
rem   3. XAMPP: Registry, thu muc xampp o o dia chua du an, C:, D:, E:, F: - lay XAMPP dau tien co Moodle 4.5
rem   4. PHP: php.exe cua XAMPP, hoac php tren PATH
rem   5. Moodle: htdocs\moodle45, htdocs\moodle cua XAMPP - chi nhan Moodle 4.5 tro len (doc version.php)
rem ======================================================================
if exist "%~dp00_CAU_HINH_MAY.bat" call "%~dp00_CAU_HINH_MAY.bat"
if not defined APP_PORT set "APP_PORT=8000"

rem Cac thu muc XAMPP ung vien: Registry, o dia chua du an, C: D: E: F: - chon XAMPP DAU TIEN co Moodle 4.5
set "_REG="
for /f "tokens=2,*" %%a in ('reg query "HKLM\SOFTWARE\xampp" /v Install_Dir 2^>nul') do if "%%a"=="REG_SZ" set "_REG=%%b"
if not defined _REG for /f "tokens=2,*" %%a in ('reg query "HKLM\SOFTWARE\WOW6432Node\xampp" /v Install_Dir 2^>nul') do if "%%a"=="REG_SZ" set "_REG=%%b"
if defined XAMPP_DIR if not defined MOODLE_DIR call :thu_xampp "%XAMPP_DIR%"
if not defined MOODLE_DIR for %%d in ("%_REG%" "%~d0\xampp" "C:\xampp" "D:\xampp" "E:\xampp" "F:\xampp") do if not defined MOODLE_DIR if not "%%~d"=="" call :thu_xampp "%%~d"
rem Khong co Moodle 4.5 nao: van lay XAMPP dau tien co php.exe (de bao loi ro rang o buoc 3/4)
if not defined XAMPP_DIR for %%d in ("%_REG%" "%~d0\xampp" "C:\xampp" "D:\xampp" "E:\xampp" "F:\xampp") do if not defined XAMPP_DIR if not "%%~d"=="" if exist "%%~d\php\php.exe" set "XAMPP_DIR=%%~d"
set "_REG="

if not defined PHP_BIN if defined XAMPP_DIR if exist "%XAMPP_DIR%\php\php.exe" set "PHP_BIN=%XAMPP_DIR%\php\php.exe"
if not defined PHP_BIN for /f "delims=" %%p in ('where php 2^>nul') do if not defined PHP_BIN set "PHP_BIN=%%p"

if not defined PHP_BIN echo [Canh bao] Khong tim thay php.exe - cai XAMPP hoac khai bao PHP_BIN trong 0_CAU_HINH_MAY.bat
if not defined MOODLE_DIR echo [Canh bao] Khong tim thay Moodle 4.5 trong XAMPP\htdocs - khai bao MOODLE_DIR trong 0_CAU_HINH_MAY.bat

rem Lan dau (vd. vua tai tu GitHub): tao backend\cau_hinh.env tu tep mau
if not exist "%~dp0backend\cau_hinh.env" copy /y "%~dp0backend\cau_hinh.env.example" "%~dp0backend\cau_hinh.env" >nul
goto :eof

rem ---- Thu mot thu muc XAMPP: co php.exe va htdocs\moodle45 hoac htdocs\moodle la Moodle 4.5 thi chon
:thu_xampp
if not exist "%~1\php\php.exe" goto :eof
for %%m in (moodle45 moodle) do if not defined MOODLE_DIR call :thu_moodle "%~1\htdocs\%%m"
if defined MOODLE_DIR if not defined XAMPP_DIR set "XAMPP_DIR=%~1"
goto :eof

rem ---- Nhan thu muc Moodle neu da cai (co config.php) va phien ban >= 4.5: dong "$version  = 2024100700.00;" trong version.php
:thu_moodle
if not exist "%~1\version.php" goto :eof
if not exist "%~1\config.php" goto :eof
set "_MV="
for /f "tokens=2 delims==;" %%v in ('findstr /b /c:"$version " "%~1\version.php"') do if not defined _MV set "_MV=%%v"
if defined _MV for /f "tokens=1 delims=. " %%n in ("%_MV%") do set "_MV=%%n"
if defined _MV if %_MV% GEQ 2024100700 set "MOODLE_DIR=%~1"
set "_MV="
goto :eof
