@echo off
rem Chay tu ban sao tam: lenh git co the doi chinh tep nay trong luc chay, cmd.exe se mat dong neu doc tu tep goc
if /i not "%~1"=="--tu-temp" (
  copy /y "%~f0" "%TEMP%\%~n0_tam.bat" >nul
  call "%TEMP%\%~n0_tam.bat" --tu-temp "%~dp0"
  exit /b
)
chcp 65001 >nul
cd /d "%~2"
set "BR=Tanyen"
echo ================================================================
echo  DAY DO AN LEN GITHUB - NHANH %BR% (KHONG DUNG TOI NHANH main)
echo  https://github.com/NguyenTanYen/TLCN/tree/%BR%
echo  1. Bo cac tep cu khong con dung (ma nguon cu, ban build giao dien cu, so do cu)
echo  2. Chuyen sang nhanh %BR% (tao moi neu chua co) - cac tep tren may giu nguyen
echo  3. Bo .venv, __pycache__, cau_hinh.env (mat khau, token)... theo .gitignore; commit
echo  4. Day len origin/%BR%
echo ================================================================
where git >nul 2>nul || (echo Chua cai Git. & pause & exit /b 1)
if not exist ".git" (echo Thu muc nay chua phai kho Git. & pause & exit /b 1)
if exist ".git\rebase-merge" (echo Dang co mot lan rebase chua xong - chay "git rebase --abort" truoc. & pause & exit /b 1)
if exist ".git\rebase-apply" (echo Dang co mot lan rebase chua xong - chay "git rebase --abort" truoc. & pause & exit /b 1)
echo [1/5] Bo cac tep cu khong con dung...
for %%f in (
  backend\cau_hinh.env.mau
  backend\app\routers\student.py
  frontend\src\pages\LearningPath.jsx
  frontend\src\pages\StudentHome.jsx
  frontend\src\pages\Program.jsx
  docs\diagrams\sd01.puml
  docs\diagrams\sd02.puml
  docs\diagrams\sd03.puml
  docs\diagrams\sd04.puml
  docs\diagrams\sd05.puml
  docs\diagrams\sd06.puml
) do if exist "%%f" del /q "%%f"
rem ban build giao dien cu: chi giu cac tep ma frontend\dist\index.html dang dung
for %%f in (frontend\dist\assets\index-*.*) do findstr /c:"%%~nxf" frontend\dist\index.html >nul || del /q "%%f"
echo [2/5] Chuyen sang nhanh %BR%...
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set "CUR=%%b"
if /i "%CUR%"=="%BR%" (echo Dang o nhanh %BR%.) else (
  git show-ref --verify --quiet refs/heads/%BR% && (git switch %BR% || goto :loi) || (git switch -c %BR% || goto :loi)
)
echo [3/5] Ap dung .gitignore va commit...
git rm -r -q --cached . || goto :loi
git add -A || goto :loi
git commit -q -m "Hoan thien theo gop y 15/10: CTDT 2026, de cuong, nhap diem, gop bai, phu dao, de giay + cham phieu, dong bo cau hoi; kiem thu toan bo (%date%)" && echo Da commit. || echo (Khong co thay doi moi de commit)
echo [4/5] Lay thay doi moi tren nhanh %BR% cua GitHub (neu co)...
git fetch origin || goto :loi
git show-ref --verify --quiet refs/remotes/origin/%BR% && (git pull --rebase origin %BR% || goto :xung_dot) || echo Nhanh %BR% chua co tren GitHub - se tao moi.
echo.
choice /m "[5/5] Day len GitHub nhanh %BR% ngay bay gio"
if errorlevel 2 goto :xong
git push -u origin %BR% || goto :loi
:xong
echo.
git log --oneline -5
echo Xong. Nhanh main tren GitHub KHONG bi thay doi.
pause
exit /b 0
:xung_dot
echo *** Thay doi tren may va tren nhanh %BR% cua GitHub trung cung mot cho - Git dung lai de ban chon.
echo     Huy: git rebase --abort   (moi thu tro ve nhu truoc khi chay)
pause
exit /b 1
:loi
echo *** Co loi - xem thong bao o tren (kiem tra mang / dang nhap GitHub). ***
pause
exit /b 1
