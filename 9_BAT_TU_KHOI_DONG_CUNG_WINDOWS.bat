@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Dang dang ky tac vu: he thong tu chay khi ban dang nhap Windows, tu bat lai neu bi loi...
schtasks /Create /TN "TLCN_HeThongCDR" /TR "\"%~dp05b_CHAY_NEN_TU_KHOI_LAI.bat\"" /SC ONLOGON /RL LIMITED /F
if errorlevel 1 ( echo Khong dang ky duoc. Hay chuot phai tep nay - Run as administrator. & pause & exit /b 1 )
echo.
echo Xong. Khoi dong ngay bay gio:
schtasks /Run /TN "TLCN_HeThongCDR"
echo.
echo LUU Y: van can bat XAMPP (Apache + MariaDB) - mo XAMPP Control Panel, tich Service cho Apache va MySQL de chung tu chay cung Windows.
echo Xem nhat ky: logs\he_thong.log   - Go bo: chay 9b_TAT_TU_KHOI_DONG.bat
pause
