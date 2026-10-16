@echo off
rem Chay tu ban sao tam: lenh git co the tam cat/doi chinh tep nay trong luc chay, cmd.exe se mat dong neu doc tu tep goc
if /i not "%~1"=="--tu-temp" (
  copy /y "%~f0" "%TEMP%\%~n0_tam.bat" >nul
  call "%TEMP%\%~n0_tam.bat" --tu-temp "%~dp0"
  exit /b
)
chcp 65001 >nul
cd /d "%~2"
echo ================================================================
echo  LAY BAN MOI NHAT CUA NHANH DANG DUNG TU GITHUB VE MAY (https://github.com/NguyenTanYen/TLCN)
echo  - Nhan cac commit moi cua thanh vien khac
echo  - GIU NGUYEN cac chinh sua chua day len tren may nay (cat tam roi tra lai)
echo  - Khong dung toi .venv, cau_hinh.env, du lieu CSDL
echo  Nen chay buoc nay TRUOC khi sua do an; sua xong chay 7_DON_DEP_GIT.bat de day len.
echo ================================================================
where git >nul 2>nul || (echo Chua cai Git. & pause & exit /b 1)
if not exist ".git" (echo Thu muc nay chua phai kho Git. & pause & exit /b 1)
if exist ".git\rebase-merge" (echo Dang co mot lan rebase chua xong - chay "git rebase --abort" truoc. & pause & exit /b 1)
if exist ".git\rebase-apply" (echo Dang co mot lan rebase chua xong - chay "git rebase --abort" truoc. & pause & exit /b 1)
echo [1/4] Tai thong tin moi tu GitHub...
git fetch origin || goto :loi
set "STASHED="
git status --porcelain | findstr /r "." >nul && (
  echo [2/4] Cat tam cac chinh sua tren may...
  git stash push --include-untracked -m "tu dong truoc khi cap nhat tu GitHub" || goto :loi
  set "STASHED=1"
) || echo [2/4] May khong co chinh sua chua commit.
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set "CUR=%%b"
echo [3/4] Cap nhat nhanh %CUR% theo ban moi nhat tren GitHub...
git show-ref --verify --quiet refs/remotes/origin/%CUR% && (git rebase origin/%CUR% || goto :xung_dot) || echo Nhanh %CUR% chua co tren GitHub - bo qua.
if defined STASHED (
  echo [4/4] Tra lai cac chinh sua tren may...
  git stash pop || goto :stash_xung_dot
) else echo [4/4] Xong.
echo.
git log --oneline -5
git status --short
echo.
echo Da cap nhat theo GitHub. Neu da sua do an, chay 7_DON_DEP_GIT.bat de day len.
pause
exit /b 0
:xung_dot
git rebase --abort >nul 2>nul
if defined STASHED git stash pop >nul 2>nul
echo *** Commit tren may va tren GitHub sua trung mot cho - da huy, moi thu tro ve nhu cu.
pause
exit /b 1
:stash_xung_dot
echo *** Chinh sua tren may trung voi thay doi moi tai cac tep danh dau "UU" o tren.
echo     Ban sao chinh sua van con trong "git stash list" - mo tep, giu noi dung dung roi chay: git stash drop
git status --short
pause
exit /b 1
:loi
echo *** Co loi - xem thong bao o tren (kiem tra mang / dang nhap GitHub).
pause
exit /b 1
