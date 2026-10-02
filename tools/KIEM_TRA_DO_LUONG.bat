@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0..\backend"
echo Tinh lai doc lap cac do do (p, DI, CLO, BM6b, PI, PLO, CTDT) tu du lieu bai lam va so voi he thong...
"..\.venv\Scripts\python.exe" "..\tools\kiem_tra_do_luong.py"
pause
