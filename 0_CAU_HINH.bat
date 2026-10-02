@echo off
rem ======================================================================
rem  CAU HINH DUONG DAN - TU DO, dung chung cho moi may (khong can sua tep nay)
rem  Thu tu uu tien:
rem   1. Tep rieng cua may 0_CAU_HINH_MAY.bat (KHONG dua len git) - dat san bien, VD:
rem        set "MOODLE_DIR=E:\TLCN_MoiTruong\web\moodle45"
rem        set "PHP_BIN=E:\hoc\xampp\php\php.exe"
rem        set "APP_PORT=8000"
rem      (chep tu 0_CAU_HINH_MAY.example.bat roi sua)
rem   2. XAMPP: duong dan cai dat trong Registry, sau do thu C:\xampp, D:\xampp, E:\xampp, F:\xampp
rem   3. PHP: php.exe cua XAMPP, hoac php tren PATH
rem   4. Moodle: htdocs\moodle45, htdocs\moodle cua XAMPP - chi nhan Moodle 4.5 tro len (doc version.php)
rem ======================================================================
if exist "%~dp00_CAU_HINH_MAY.bat" call "%~dp00_CAU_HINH_MAY.bat"
if not defined APP_PORT set "APP_PORT=8000"

if not defined XAMPP_DIR for /f "tokens=2,*" %%a in ('reg query "HKLM\SOFTWARE\xampp" /v Install_Dir 2^>nul') do if "%%a"=="REG_SZ" set "XAMPP_DIR=%%b"
if not defined XAMPP_DIR for %%d in (C D E F) do if not defined XAMPP_DIR if exist "%%d:\xampp\php\php.exe" set "XAMPP_DIR=%%d:\xampp"

if not defined PHP_BIN if defined XAMPP_DIR if exist "%XAMPP_DIR%\php\php.exe" set "PHP_BIN=%XAMPP_DIR%\php\php.exe"
if not defined PHP_BIN for /f "delims=" %%p in ('where php 2^>nul') do if not defined PHP_BIN set "PHP_BIN=%%p"

if not defined MOODLE_DIR if defined XAMPP_DIR for %%m in (moodle45 moodle) do if not defined MOODLE_DIR call :thu_moodle "%XAMPP_DIR%\htdocs\%%m"

if not defined PHP_BIN echo [Canh bao] Khong tim thay php.exe - cai XAMPP hoac khai bao PHP_BIN trong 0_CAU_HINH_MAY.bat
if not defined MOODLE_DIR echo [Canh bao] Khong tim thay Moodle 4.5 trong XAMPP\htdocs - khai bao MOODLE_DIR trong 0_CAU_HINH_MAY.bat
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
