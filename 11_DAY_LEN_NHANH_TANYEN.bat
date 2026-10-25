@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================================
echo  DAY BAN HIEN TAI LEN NHANH "Tanyen" tren GitHub (KHONG dung toi nhanh main)
echo  Muc dich: may chu Google Cloud tai ma nguon ve de chay.
echo ================================================================
where git >nul 2>nul || (echo Chua cai Git. & pause & exit /b 1)
if not exist ".git" (echo Thu muc nay chua phai kho Git. & pause & exit /b 1)
git checkout -B Tanyen || goto :loi
git add -A || goto :loi
git commit -m "Ban nop TLCN Nhom 01 (de trien khai len may chu)" 
git push -u origin Tanyen || goto :loi
echo.
echo XONG. Da day len nhanh Tanyen.
pause
exit /b 0
:loi
echo.
echo *** CO LOI - chup man hinh nay de kiem tra.
pause
exit /b 1
