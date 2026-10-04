@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================================
echo  Don dep kho Git: bo khoi Git cac tep KHONG nen dua len GitHub
echo  (.venv, __pycache__, cau_hinh.env co mat khau/token...) theo .gitignore.
echo  Tep tren may VAN GIU NGUYEN, chi khong con duoc Git theo doi.
echo ================================================================
where git >nul 2>nul || (echo Chua cai Git. & pause & exit /b 1)
if not exist ".git" (echo Thu muc nay chua phai kho Git. & pause & exit /b 1)
git rm -r -q --cached . || goto :loi
git add -A || goto :loi
git status --short | find /c /v "" 
git commit -m "Cap nhat he thong %date%" || echo (Khong co gi de commit)
echo.
choice /m "Day len GitHub (git push) ngay bay gio"
if errorlevel 2 goto :xong
git pull --rebase origin main && git push origin main || goto :loi
:xong
echo Xong.
pause
exit /b 0
:loi
echo *** Co loi - xem thong bao o tren. ***
pause
exit /b 1
